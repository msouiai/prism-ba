#pragma once

// Full unregularised prediction of the actual camera/point step.  During D9's
// opening this uses the same scalar-weight Schur complement as MFAssemble.
__global__ void MFDirectFullModel(const int* ci,const int* pi,const double* uv,
    const double* R,const double* t,const double* X,const double* f,const double* k1,
    const double* k2,const double* step,int no,int nc,double k2mask,double* out,
    const double* lift_weights,double lift_tau2,double lift_lambda){
  int o=blockIdx.x*blockDim.x+threadIdx.x;double gd=0,jj=0;
  if(o<no){int c=ci[o],p=pi[o];const double* r=R+9*c;const double* x=X+3*p;
    double rx,ry,jx,jy;
    BalDirectional12(r,t+3*c,x,f[c],k1[c],k2[c],uv[2*o],uv[2*o+1],step+9*c,step+9*nc+3*p,k2mask,rx,ry,jx,jy);
    if(lift_weights){
      const double w=lift_weights[o],w2=w*w,r2=rx*rx+ry*ry;
      const double denom=r2+2.0*lift_tau2*w2+lift_lambda;
      const double dot=rx*jx+ry*jy;
      if(denom>0.0){
        const double gfac=w2*(1.0-(r2+lift_tau2*(w2-1.0))/denom);
        gd=gfac*dot;
        jj=w2*(jx*jx+jy*jy-dot*dot/denom);
      }
    }else{gd=rx*jx+ry*jy;jj=jx*jx+jy*jy;}
  }
  __shared__ double v[2][256];v[0][threadIdx.x]=gd;v[1][threadIdx.x]=jj;__syncthreads();
  for(int k=128;k>0;k>>=1){if(threadIdx.x<k){v[0][threadIdx.x]+=v[0][threadIdx.x+k];v[1][threadIdx.x]+=v[1][threadIdx.x+k];}__syncthreads();}
  if(threadIdx.x<2)atomicAdd(out+threadIdx.x,v[threadIdx.x][0]);
}
struct PrismFullModel {
  double* sums=nullptr;
  struct Result {double slope=0,curvature=0,prediction=0;};
  PrismFullModel(){CUDA_CHECK(cudaMalloc(&sums,2*sizeof(double)));}
  ~PrismFullModel(){cudaFree(sums);}
  PrismFullModel(const PrismFullModel&)=delete;
  Result Evaluate(const DeviceProblem& p,const DeviceState& s,const double* step,double k2mask){
    CUDA_CHECK(cudaMemset(sums,0,2*sizeof(double)));
    const double* weights=w6_lift_host.active?w6_lift_host.weights:nullptr;
    MFDirectFullModel<<<GridSize(p.nobs),256>>>(p.cam_idx,p.pt_idx,p.uv,s.R,s.t,s.X,
      INTR_F(p,s),INTR_K1(p,s),INTR_K2(p,s),step,p.nobs,p.ncam,k2mask,sums,
      weights,w6_lift_host.tau2,w6_lift_host.lambda);
    double h[2];CUDA_CHECK(cudaMemcpy(h,sums,2*sizeof(double),cudaMemcpyDeviceToHost));
    return Result{h[0],h[1],-h[0]-.5*h[1]};
  }
};

