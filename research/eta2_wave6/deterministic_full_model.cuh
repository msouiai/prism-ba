#pragma once

// Deterministic counterpart of full_step_model.cuh.  The disabled path keeps
// the original block-atomic implementation for compatibility; the enabled
// path stores private block sums and reduces them with one fixed tree.

__global__ void W6DirectFullModelAtomic(
    const int* ci,const int* pi,const double* uv,const double* R,const double* t,
    const double* X,const double* f,const double* k1,const double* k2,
    const double* step,int no,int nc,double k2mask,double* out) {
  int o=blockIdx.x*blockDim.x+threadIdx.x; double gd=0,jj=0;
  if(o<no){int c=ci[o],p=pi[o];const double* r=R+9*c;const double* x=X+3*p;
    double rx,ry,jx,jy;
    BalDirectional12(r,t+3*c,x,f[c],k1[c],k2[c],uv[2*o],uv[2*o+1],
                     step+9*c,step+9*nc+3*p,k2mask,rx,ry,jx,jy);
    gd=rx*jx+ry*jy;jj=jx*jx+jy*jy;
  }
  __shared__ double v[2][256];
  v[0][threadIdx.x]=gd;v[1][threadIdx.x]=jj;__syncthreads();
  for(int k=128;k>0;k>>=1){if(threadIdx.x<k){
    v[0][threadIdx.x]+=v[0][threadIdx.x+k];
    v[1][threadIdx.x]+=v[1][threadIdx.x+k];}__syncthreads();}
  if(threadIdx.x<2)atomicAdd(out+threadIdx.x,v[threadIdx.x][0]);
}

__global__ void W6DirectFullModelPartials(
    const int* ci,const int* pi,const double* uv,const double* R,const double* t,
    const double* X,const double* f,const double* k1,const double* k2,
    const double* step,int no,int nc,double k2mask,double* partials) {
  int o=blockIdx.x*blockDim.x+threadIdx.x; double gd=0,jj=0;
  if(o<no){int c=ci[o],p=pi[o];const double* r=R+9*c;const double* x=X+3*p;
    double rx,ry,jx,jy;
    BalDirectional12(r,t+3*c,x,f[c],k1[c],k2[c],uv[2*o],uv[2*o+1],
                     step+9*c,step+9*nc+3*p,k2mask,rx,ry,jx,jy);
    gd=rx*jx+ry*jy;jj=jx*jx+jy*jy;
  }
  __shared__ double v[2][256];
  v[0][threadIdx.x]=gd;v[1][threadIdx.x]=jj;__syncthreads();
  for(int k=128;k>0;k>>=1){if(threadIdx.x<k){
    v[0][threadIdx.x]+=v[0][threadIdx.x+k];
    v[1][threadIdx.x]+=v[1][threadIdx.x+k];}__syncthreads();}
  if(threadIdx.x==0){partials[2*blockIdx.x]=v[0][0];partials[2*blockIdx.x+1]=v[1][0];}
}

__global__ void W6ReduceTwoFixed(const double* __restrict__ partials,
                                 int count,double* __restrict__ output) {
  double a=0,b=0;
  for(int i=threadIdx.x;i<count;i+=blockDim.x){a+=partials[2*i];b+=partials[2*i+1];}
  __shared__ double v[2][256];v[0][threadIdx.x]=a;v[1][threadIdx.x]=b;__syncthreads();
  for(int k=128;k>0;k>>=1){if(threadIdx.x<k){
    v[0][threadIdx.x]+=v[0][threadIdx.x+k];
    v[1][threadIdx.x]+=v[1][threadIdx.x+k];}__syncthreads();}
  if(threadIdx.x<2)output[threadIdx.x]=v[threadIdx.x][0];
}

struct PrismFullModel {
  double* sums=nullptr; double* partials=nullptr; int capacity=0;
  struct Result {double slope=0,curvature=0,prediction=0;};
  PrismFullModel(){CUDA_CHECK(cudaMalloc(&sums,2*sizeof(double)));}
  ~PrismFullModel(){cudaFree(sums);cudaFree(partials);}
  PrismFullModel(const PrismFullModel&)=delete;
  Result Evaluate(const DeviceProblem& p,const DeviceState& s,
                  const double* step,double k2mask){
    if(PrismW6DeterministicEnabled()){
      const int blocks=GridSize(p.nobs);
      if(blocks>capacity){cudaFree(partials);CUDA_CHECK(cudaMalloc(&partials,2ul*blocks*sizeof(double)));capacity=blocks;}
      W6DirectFullModelPartials<<<blocks,256>>>(p.cam_idx,p.pt_idx,p.uv,s.R,s.t,s.X,
        INTR_F(p,s),INTR_K1(p,s),INTR_K2(p,s),step,p.nobs,p.ncam,k2mask,partials);
      W6ReduceTwoFixed<<<1,256>>>(partials,blocks,sums);
    }else{
      CUDA_CHECK(cudaMemset(sums,0,2*sizeof(double)));
      W6DirectFullModelAtomic<<<GridSize(p.nobs),256>>>(p.cam_idx,p.pt_idx,p.uv,s.R,s.t,s.X,
        INTR_F(p,s),INTR_K1(p,s),INTR_K2(p,s),step,p.nobs,p.ncam,k2mask,sums);
    }
    double h[2];CUDA_CHECK(cudaMemcpy(h,sums,2*sizeof(double),cudaMemcpyDeviceToHost));
    return Result{h[0],h[1],-h[0]-.5*h[1]};
  }
};
