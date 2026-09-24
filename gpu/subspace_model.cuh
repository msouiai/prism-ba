#pragma once
#include "subspace_box.h"
// Full unregularized GN prediction for the actual mixed/scaled CD=9 step.
// No assumption that CG solved the regularized equations exactly.
__global__ void MFSubspaceModel(const int* ci,const int* pi,const double* uv,
    const double* R,const double* t,const double* X,const double* f,const double* k1,
    const double* k2,const double* step,int no,int nc,double k2mask,double* out){
  int o=blockIdx.x*blockDim.x+threadIdx.x;double sums[5]={0,0,0,0,0};
  if(o<no){int c=ci[o],p=pi[o];const double* r=R+9*c;const double* x=X+3*p;
    double gx[12],gy[12],rx,ry;
    BalResidualGrad12(r[0],r[1],r[2],r[3],r[4],r[5],r[6],r[7],r[8],
      t[3*c],t[3*c+1],t[3*c+2],x[0],x[1],x[2],f[c],k1[c],k2[c],uv[2*o],uv[2*o+1],gx,gy,&rx,&ry);
    gx[8]*=k2mask;gy[8]*=k2mask;double cx=0,cy=0,px=0,py=0;
    for(int i=0;i<9;++i){cx+=gx[i]*step[9*c+i];cy+=gy[i]*step[9*c+i];}
    for(int i=0;i<3;++i){px+=gx[9+i]*step[9*nc+3*p+i];py+=gy[9+i]*step[9*nc+3*p+i];}
    sums[0]=rx*cx+ry*cy;sums[1]=rx*px+ry*py;
    sums[2]=cx*cx+cy*cy;sums[3]=cx*px+cy*py;sums[4]=px*px+py*py;
  }
  __shared__ double v[5][256];
  for(int j=0;j<5;++j)v[j][threadIdx.x]=sums[j];__syncthreads();
  for(int k=128;k>0;k>>=1){if(threadIdx.x<k)for(int j=0;j<5;++j)v[j][threadIdx.x]+=v[j][threadIdx.x+k];__syncthreads();}
  if(threadIdx.x<5)atomicAdd(out+threadIdx.x,v[threadIdx.x][0]);
}
struct PrismSubspaceModel {
  double* sums=nullptr;
  struct Result {double gc=0,gp=0,cc=0,cp=0,pp=0;};
  PrismSubspaceModel(){CUDA_CHECK(cudaMalloc(&sums,5*sizeof(double)));}
  ~PrismSubspaceModel(){cudaFree(sums);}
  PrismSubspaceModel(const PrismSubspaceModel&)=delete;
  Result Evaluate(const DeviceProblem& p,const DeviceState& s,const double* step,double k2mask){
    CUDA_CHECK(cudaMemset(sums,0,5*sizeof(double)));
    MFSubspaceModel<<<GridSize(p.nobs),256>>>(p.cam_idx,p.pt_idx,p.uv,s.R,s.t,s.X,
      INTR_F(p,s),INTR_K1(p,s),INTR_K2(p,s),step,p.nobs,p.ncam,k2mask,sums);
    double h[5];CUDA_CHECK(cudaMemcpy(h,sums,5*sizeof(double),cudaMemcpyDeviceToHost));
    return Result{h[0],h[1],h[2],h[3],h[4]};
  }
};
