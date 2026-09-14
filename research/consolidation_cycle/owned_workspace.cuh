#pragma once

#ifdef PRISM_OWNED_WORKSPACE_TESTING
inline thread_local int prism_owned_workspace_fail_after=-1;
struct PrismOwnedWorkspaceSnapshot {
  const void *blas_partials,*blas_output,*cost_partials,*cost_output,
             *bounded_result,*count_output,*block_diag_output;
};
inline void (*prism_owned_workspace_observer)(const PrismOwnedWorkspaceSnapshot&)=nullptr;
#endif

inline cudaError_t OwnedWorkspaceMalloc(void** p,size_t bytes){
#ifdef PRISM_OWNED_WORKSPACE_TESTING
  if(prism_owned_workspace_fail_after==0)return cudaErrorMemoryAllocation;
  if(prism_owned_workspace_fail_after>0)--prism_owned_workspace_fail_after;
#endif
  return cudaMalloc(p,bytes);
}

inline bool PrismW6DeterministicEnabled() {
  static const bool enabled=[](){const char* v=std::getenv("OCA_W6_DETERMINISTIC");return v&&std::atoi(v)!=0;}();
  return enabled;
}

struct OwnedBalWorkspace {
  int device=-1;
  double *blas_partials=nullptr,*blas_output=nullptr;
  Scalar *cost_partials=nullptr,*cost_output=nullptr;
  void* bounded_result=nullptr;
  int *count_output=nullptr,*block_diag_output=nullptr;
  int blas_capacity=0,cost_capacity=0;

  OwnedBalWorkspace(int max_vector_count,int cost_blocks){
    CUDA_CHECK(cudaGetDevice(&device));
    blas_capacity=(max_vector_count+255)/256;cost_capacity=cost_blocks;
    try {
      CUDA_CHECK(OwnedWorkspaceMalloc((void**)&blas_partials,(size_t)blas_capacity*sizeof(double)));
      CUDA_CHECK(OwnedWorkspaceMalloc((void**)&blas_output,sizeof(double)));
      CUDA_CHECK(OwnedWorkspaceMalloc((void**)&cost_partials,(size_t)cost_capacity*sizeof(Scalar)));
      CUDA_CHECK(OwnedWorkspaceMalloc((void**)&cost_output,sizeof(Scalar)));
      CUDA_CHECK(OwnedWorkspaceMalloc(&bounded_result,2*sizeof(Scalar)));
      CUDA_CHECK(OwnedWorkspaceMalloc((void**)&count_output,sizeof(int)));
      CUDA_CHECK(OwnedWorkspaceMalloc((void**)&block_diag_output,sizeof(int)));
#ifdef PRISM_OWNED_WORKSPACE_TESTING
      if(prism_owned_workspace_observer)prism_owned_workspace_observer({blas_partials,blas_output,cost_partials,cost_output,bounded_result,count_output,block_diag_output});
#endif
    } catch (...) { ReleaseOnCurrentDevice(); throw; }
  }
  OwnedBalWorkspace(const OwnedBalWorkspace&)=delete;
  OwnedBalWorkspace& operator=(const OwnedBalWorkspace&)=delete;
  void ReleaseOnCurrentDevice() noexcept {
    cudaFree(block_diag_output);block_diag_output=nullptr;
    cudaFree(count_output);count_output=nullptr;
    cudaFree(bounded_result);bounded_result=nullptr;
    cudaFree(cost_output);cost_output=nullptr;
    cudaFree(cost_partials);cost_partials=nullptr;
    cudaFree(blas_output);blas_output=nullptr;
    cudaFree(blas_partials);blas_partials=nullptr;
  }
  ~OwnedBalWorkspace() noexcept {
    int prior=-1;if(cudaGetDevice(&prior)!=cudaSuccess)return;
    if(prior!=device && cudaSetDevice(device)!=cudaSuccess)return;
    cudaDeviceSynchronize();ReleaseOnCurrentDevice();
    if(prior!=device)cudaSetDevice(prior);
  }
};

inline thread_local OwnedBalWorkspace* prism_owned_workspace=nullptr;
struct OwnedWorkspaceBinding {
  OwnedBalWorkspace* previous=nullptr;
  explicit OwnedWorkspaceBinding(OwnedBalWorkspace& w):previous(prism_owned_workspace){
    if(previous)throw std::runtime_error("nested BAL workspace binding");
    prism_owned_workspace=&w;
  }
  ~OwnedWorkspaceBinding(){prism_owned_workspace=previous;}
};
inline OwnedBalWorkspace& OwnedWorkspaceCurrent(){
  if(!prism_owned_workspace)throw std::runtime_error("BAL workspace is not bound");
  int current=-1;CUDA_CHECK(cudaGetDevice(&current));
  if(current!=prism_owned_workspace->device)throw std::runtime_error("BAL workspace used on wrong CUDA device");
  return *prism_owned_workspace;
}

struct OwnedScopedCudaDevice {
  int previous=-1;
  OwnedScopedCudaDevice(){CUDA_CHECK(cudaGetDevice(&previous));}
  ~OwnedScopedCudaDevice(){if(previous>=0)cudaSetDevice(previous);}
};

__global__ void W6DotPartials(const double* x,int incx,const double* y,int incy,int n,double* partials){
  const int i=blockIdx.x*blockDim.x+threadIdx.x;double value=i<n?x[(size_t)i*incx]*y[(size_t)i*incy]:0.0;
  __shared__ double sums[256];sums[threadIdx.x]=value;__syncthreads();
  for(int stride=128;stride;stride>>=1){if(threadIdx.x<stride)sums[threadIdx.x]+=sums[threadIdx.x+stride];__syncthreads();}
  if(threadIdx.x==0)partials[blockIdx.x]=sums[0];
}
__global__ void W6DotFinal(const double* partials,int count,double* output){
  double value=0;for(int i=threadIdx.x;i<count;i+=blockDim.x)value+=partials[i];
  __shared__ double sums[256];sums[threadIdx.x]=value;__syncthreads();
  for(int stride=128;stride;stride>>=1){if(threadIdx.x<stride)sums[threadIdx.x]+=sums[threadIdx.x+stride];__syncthreads();}
  if(threadIdx.x==0)output[0]=sums[0];
}
__global__ void W6SqrtScalar(const double* input,double* output){if(threadIdx.x==0)output[0]=sqrt(fmax(input[0],0.0));}
inline double* W6LaunchFixedDot(cublasHandle_t handle,int n,const double*x,int incx,const double*y,int incy){
  auto& w=OwnedWorkspaceCurrent();const int blocks=(n+255)/256;
  if(blocks>w.blas_capacity)throw std::runtime_error("BAL workspace BLAS capacity exceeded");
  cudaStream_t stream=nullptr;CUBLAS_CHECK(cublasGetStream(handle,&stream));
  W6DotPartials<<<blocks,256,0,stream>>>(x,incx,y,incy,n,w.blas_partials);
  W6DotFinal<<<1,256,0,stream>>>(w.blas_partials,blocks,w.blas_output);return w.blas_output;
}
inline cublasStatus_t PrismW6Ddot(cublasHandle_t h,int n,const double*x,int ix,const double*y,int iy,double*r){
  if(!PrismW6DeterministicEnabled())return cublasDdot(h,n,x,ix,y,iy,r);double*out=W6LaunchFixedDot(h,n,x,ix,y,iy);
  cublasPointerMode_t mode;CUBLAS_CHECK(cublasGetPointerMode(h,&mode));cudaStream_t s=nullptr;CUBLAS_CHECK(cublasGetStream(h,&s));
  if(mode==CUBLAS_POINTER_MODE_DEVICE)CUDA_CHECK(cudaMemcpyAsync(r,out,sizeof(double),cudaMemcpyDeviceToDevice,s));
  else {CUDA_CHECK(cudaMemcpyAsync(r,out,sizeof(double),cudaMemcpyDeviceToHost,s));CUDA_CHECK(cudaStreamSynchronize(s));}return CUBLAS_STATUS_SUCCESS;
}
inline cublasStatus_t PrismW6Dnrm2(cublasHandle_t h,int n,const double*x,int ix,double*r){
  if(!PrismW6DeterministicEnabled())return cublasDnrm2(h,n,x,ix,r);double*out=W6LaunchFixedDot(h,n,x,ix,x,ix);
  cublasPointerMode_t mode;CUBLAS_CHECK(cublasGetPointerMode(h,&mode));cudaStream_t s=nullptr;CUBLAS_CHECK(cublasGetStream(h,&s));
  if(mode==CUBLAS_POINTER_MODE_DEVICE)W6SqrtScalar<<<1,1,0,s>>>(out,r);
  else {double v=0;CUDA_CHECK(cudaMemcpyAsync(&v,out,sizeof(double),cudaMemcpyDeviceToHost,s));CUDA_CHECK(cudaStreamSynchronize(s));*r=std::sqrt(std::max(0.0,v));}return CUBLAS_STATUS_SUCCESS;
}
