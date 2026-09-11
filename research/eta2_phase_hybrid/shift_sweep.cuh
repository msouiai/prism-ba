#pragma once
#include <array>
#include <algorithm>
#include <cmath>
#include <limits>
struct PrismHybridUpdate {
  double *X,*P,*r;int n;double al[5],be[5],z[5];
};
__global__ void PrismHybridVectors(PrismHybridUpdate a){
  int i=blockIdx.x*blockDim.x+threadIdx.x;if(i>=5*a.n)return;
  int l=i/a.n,j=i%a.n;double old=a.P[i];a.X[i]+=a.al[l]*old;a.P[i]=a.be[l]*old+a.z[l]*a.r[j];
}
struct PrismShiftSweep {
  int n,depth=0;double *X=nullptr,*P=nullptr,*r=nullptr,*Ap=nullptr,*tmp=nullptr,*gram=nullptr;
  double lambda[5]={},residual[5]={},G[25]={},norm[5]={};bool qualified=false;
  double raw_diameter=0,clipped_diameter=0;
  PrismShiftSweep(int size):n(size){
    CUDA_CHECK(cudaMalloc(&X,5ul*n*8));CUDA_CHECK(cudaMalloc(&P,5ul*n*8));
    CUDA_CHECK(cudaMalloc(&r,n*8ul));CUDA_CHECK(cudaMalloc(&Ap,n*8ul));CUDA_CHECK(cudaMalloc(&tmp,n*8ul));CUDA_CHECK(cudaMalloc(&gram,25*8ul));
  }
  ~PrismShiftSweep(){cudaFree(X);cudaFree(P);cudaFree(r);cudaFree(Ap);cudaFree(tmp);cudaFree(gram);}
  template<class Op> bool Solve(cublasHandle_t b,Op&& K,const double* rhs,double center,double eta,int cap){
    depth=0;qualified=false;raw_diameter=clipped_diameter=0;
    for(int l=0;l<5;++l){lambda[l]=center*std::pow(10.,l-2);residual[l]=std::numeric_limits<double>::infinity();}
    CUDA_CHECK(cudaMemset(X,0,5ul*n*8));CUDA_CHECK(cudaMemcpy(r,rhs,n*8ul,cudaMemcpyDeviceToDevice));
    for(int l=0;l<5;++l)CUDA_CHECK(cudaMemcpy(P+l*(size_t)n,rhs,n*8ul,cudaMemcpyDeviceToDevice));
    double rr=0;cublasDdot(b,n,r,1,r,1,&rr);double bn=std::sqrt(rr);
    if(!std::isfinite(bn)||!(center>0)||!std::isfinite(center))return false;
    double z[5]={1,1,1,1,1},zp[5]={1,1,1,1,1},oldalpha=1,oldbeta=0;
    for(int k=0;k<cap && rr>0;++k){
      K(P,Ap);cublasDaxpy(b,n,&lambda[0],P,1,Ap,1);
      double pAp=0,pp=0;cublasDdot(b,n,P,1,Ap,1,&pAp);cublasDdot(b,n,P,1,P,1,&pp);
      if(!(pAp>1e-14*pp)||!std::isfinite(pAp))return false;
      double alpha=rr/pAp,minus=-alpha;cublasDaxpy(b,n,&minus,Ap,1,r,1);
      double rn=0;cublasDdot(b,n,r,1,r,1,&rn);if(!(rn>=0)||!std::isfinite(rn))return false;
      double beta=rn/rr;PrismHybridUpdate u{};u.X=X;u.P=P;u.r=r;u.n=n;u.al[0]=alpha;u.be[0]=beta;u.z[0]=1;
      for(int l=1;l<5;++l){
        // Avoid underflow of z*z_previous long after a large shift converges.
        // A negligible residual scale freezes that lane; true residuals are
        // still checked at exit rather than declaring convergence from z alone.
        if(std::abs(z[l])<1e-150){u.al[l]=0;u.be[l]=1;u.z[l]=0;continue;}
        double den=alpha*oldbeta*(1-z[l]/zp[l])+oldalpha*(1+(lambda[l]-lambda[0])*alpha);
        if(den==0||!std::isfinite(den))return false;
        double ratio=oldalpha/den,zn=z[l]*ratio;
        u.al[l]=alpha*ratio;u.be[l]=beta*ratio*ratio;u.z[l]=zn;
        if(!std::isfinite(zn)||!std::isfinite(u.al[l])||!std::isfinite(u.be[l]))return false;
        zp[l]=z[l];z[l]=zn;
      }
      PrismHybridVectors<<<(5*n+255)/256,256>>>(u);depth=k+1;oldalpha=alpha;oldbeta=beta;rr=rn;
      if(std::sqrt(rr)<=eta*bn)break;
    }
    // Fresh exit products prevent recurrence drift from being called collapse.
    qualified=true;
    for(int l=0;l<5;++l){
      K(X+(size_t)l*n,tmp);cublasDaxpy(b,n,&lambda[l],X+(size_t)l*n,1,tmp,1);
      double m=-1;cublasDaxpy(b,n,&m,rhs,1,tmp,1);double nr;cublasDnrm2(b,n,tmp,1,&nr);
      residual[l]=nr/std::max(bn,1e-300);if(!std::isfinite(residual[l]))return false;
      qualified=qualified&&residual[l]<=1.01*eta;
    }
    const double one=1,zero=0;
    cublasDgemm(b,CUBLAS_OP_T,CUBLAS_OP_N,5,5,n,&one,X,n,X,n,&zero,gram,5);
    CUDA_CHECK(cudaMemcpy(G,gram,25*8ul,cudaMemcpyDeviceToHost));
    for(int l=0;l<5;++l){if(!std::isfinite(G[5*l+l])||G[5*l+l]<0)return false;norm[l]=sqrt(G[5*l+l]);}
    raw_diameter=Diameter(0);return true;
  }
  double Diameter(double radius){
    double scale[5],den=0,num=0;
    for(int l=0;l<5;++l){scale[l]=radius>0&&norm[l]>radius?radius/norm[l]:1.;den=std::max(den,G[5*l+l]*scale[l]*scale[l]);}
    for(int l=0;l<5;++l)for(int j=l+1;j<5;++j)num=std::max(num,G[5*l+l]*scale[l]*scale[l]+G[5*j+j]*scale[j]*scale[j]-2*G[5*l+j]*scale[l]*scale[j]);
    return den>0?std::sqrt(std::max(0.,num)/den):0.;
  }
};
