#pragma once
#include <math_constants.h>
#include "camera_tr_math.h"
__global__ void MFTRUnscale(const double* d,const double* E,double* out,int n){
 int i=blockIdx.x*blockDim.x+threadIdx.x;
 if(i<n)out[i]=E[i]>0?d[i]/E[i]:(d[i]==0?0:CUDART_INF);
}
struct PrismCameraTR {
 struct Entry {double norm,bd,curvature;int sh,depth;};
 int n;double radius=0,tau=0,best_prediction=0,best_norm=0;int best_sh=-1,best_depth=0;
 long reuses=0,model_evals=0;double *bank=nullptr,*best=nullptr,*work=nullptr,*ax=nullptr;
 std::vector<Entry> entries;
 explicit PrismCameraTR(int size):n(size){
  CUDA_CHECK(cudaMalloc(&bank,64ul*n*sizeof(double)));
  CUDA_CHECK(cudaMalloc(&best,n*sizeof(double)));CUDA_CHECK(cudaMalloc(&work,n*sizeof(double)));
  CUDA_CHECK(cudaMalloc(&ax,n*sizeof(double)));
 }
 ~PrismCameraTR(){cudaFree(bank);cudaFree(best);cudaFree(work);cudaFree(ax);}
 void Reset(){best_prediction=0;best_sh=-1;best_depth=0;best_norm=0;}
 void Select(const double* x,const Entry& e,cublasHandle_t blas){
  if(!(std::isfinite(e.norm)&&std::isfinite(e.bd)&&std::isfinite(e.curvature)))return;
  double a=prism_camera_tr::scale(e.norm,radius);
  double pred=prism_camera_tr::prediction(e.bd,e.curvature,a);
  if(pred>best_prediction){best_prediction=pred;best_sh=e.sh;best_depth=e.depth;best_norm=a*e.norm;
   CUDA_CHECK(cudaMemcpy(best,x,n*sizeof(double),cudaMemcpyDeviceToDevice));cublasDscal(blas,n,&a,best,1);}
 }
 template<class Op> void Add(const double* x,int sh,int depth,const double* b,cublasHandle_t blas,Op op){
  if(entries.size()>=64)throw std::runtime_error("TR candidate bank exceeded bounded capacity");
  Entry e{};e.sh=sh;e.depth=depth;
  cublasDnrm2(blas,n,x,1,&e.norm);cublasDdot(blas,n,b,1,x,1,&e.bd);
  op(x,ax);++model_evals;cublasDdot(blas,n,x,1,ax,1,&e.curvature);
  double* saved=bank+entries.size()*n;
  CUDA_CHECK(cudaMemcpy(saved,x,n*sizeof(double),cudaMemcpyDeviceToDevice));entries.push_back(e);Select(saved,e,blas);
 }
 void Reconsider(cublasHandle_t blas){++reuses;for(size_t i=0;i<entries.size();++i)Select(bank+i*n,entries[i],blas);}
};
