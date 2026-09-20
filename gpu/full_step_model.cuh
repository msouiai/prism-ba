#pragma once
// Full unregularized GN prediction for the actual mixed/scaled CD=9 step.
// No assumption that CG solved the regularized equations exactly.
__global__ void MFDirectFullModel(const int* ci,const int* pi,const double* uv,
    const double* R,const double* t,const double* X,const double* f,const double* k1,
    const double* k2,const double* step,int no,int nc,double k2mask,double* out){
  int o=blockIdx.x*blockDim.x+threadIdx.x;double gd=0,jj=0;
  if(o<no){int c=ci[o],p=pi[o];const double* r=R+9*c;const double* x=X+3*p;
    double gx[12],gy[12],rx,ry;
    BalResidualGrad12(r[0],r[1],r[2],r[3],r[4],r[5],r[6],r[7],r[8],
      t[3*c],t[3*c+1],t[3*c+2],x[0],x[1],x[2],f[c],k1[c],k2[c],uv[2*o],uv[2*o+1],gx,gy,&rx,&ry);
    gx[8]*=k2mask;gy[8]*=k2mask;double jx=0,jy=0;
    for(int i=0;i<9;++i){jx+=gx[i]*step[9*c+i];jy+=gy[i]*step[9*c+i];}
    for(int i=0;i<3;++i){jx+=gx[9+i]*step[9*nc+3*p+i];jy+=gy[9+i]*step[9*nc+3*p+i];}
    gd=rx*jx+ry*jy;jj=jx*jx+jy*jy;
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
    MFDirectFullModel<<<GridSize(p.nobs),256>>>(p.cam_idx,p.pt_idx,p.uv,s.R,s.t,s.X,
      INTR_F(p,s),INTR_K1(p,s),INTR_K2(p,s),step,p.nobs,p.ncam,k2mask,sums);
    double h[2];CUDA_CHECK(cudaMemcpy(h,sums,2*sizeof(double),cudaMemcpyDeviceToHost));
    return Result{h[0],h[1],-h[0]-.5*h[1]};
  }
};
