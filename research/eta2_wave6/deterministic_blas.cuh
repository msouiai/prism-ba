#pragma once

inline bool PrismW6DeterministicEnabled() {
  static const bool enabled = []() {
    const char* value = std::getenv("OCA_W6_DETERMINISTIC");
    return value && std::atoi(value) != 0;
  }();
  return enabled;
}

__global__ void W6DotPartials(const double* __restrict__ x,int incx,
                              const double* __restrict__ y,int incy,
                              int n,double* __restrict__ partials){
  const int i=blockIdx.x*blockDim.x+threadIdx.x;
  double value=i<n?x[(size_t)i*incx]*y[(size_t)i*incy]:0.0;
  __shared__ double sums[256];sums[threadIdx.x]=value;__syncthreads();
  for(int stride=128;stride;stride>>=1){
    if(threadIdx.x<stride)sums[threadIdx.x]+=sums[threadIdx.x+stride];
    __syncthreads();
  }
  if(threadIdx.x==0)partials[blockIdx.x]=sums[0];
}

__global__ void W6DotFinal(const double* __restrict__ partials,int count,
                           double* __restrict__ output){
  double value=0.0;
  for(int i=threadIdx.x;i<count;i+=blockDim.x)value+=partials[i];
  __shared__ double sums[256];sums[threadIdx.x]=value;__syncthreads();
  for(int stride=128;stride;stride>>=1){
    if(threadIdx.x<stride)sums[threadIdx.x]+=sums[threadIdx.x+stride];
    __syncthreads();
  }
  if(threadIdx.x==0)output[0]=sums[0];
}

__global__ void W6SqrtScalar(const double* input,double* output){
  if(threadIdx.x==0)output[0]=sqrt(fmax(input[0],0.0));
}

struct W6BlasReductionWorkspace {
  double* partials=nullptr;
  double* output=nullptr;
  int capacity=0;
  ~W6BlasReductionWorkspace(){cudaFree(partials);cudaFree(output);}
};

inline W6BlasReductionWorkspace& W6BlasWorkspace(int blocks){
  static W6BlasReductionWorkspace workspace;
  if(blocks>workspace.capacity){
    cudaFree(workspace.partials);
    CUDA_CHECK(cudaMalloc(&workspace.partials,(size_t)blocks*sizeof(double)));
    workspace.capacity=blocks;
  }
  if(!workspace.output)CUDA_CHECK(cudaMalloc(&workspace.output,sizeof(double)));
  return workspace;
}

inline double* W6LaunchFixedDot(cublasHandle_t handle,int n,const double* x,
                                int incx,const double* y,int incy){
  const int blocks=(n+255)/256;auto& workspace=W6BlasWorkspace(blocks);
  cudaStream_t stream=nullptr;CUBLAS_CHECK(cublasGetStream(handle,&stream));
  W6DotPartials<<<blocks,256,0,stream>>>(x,incx,y,incy,n,workspace.partials);
  W6DotFinal<<<1,256,0,stream>>>(workspace.partials,blocks,workspace.output);
  return workspace.output;
}

inline cublasStatus_t PrismW6Ddot(cublasHandle_t handle,int n,
                                  const double* x,int incx,const double* y,
                                  int incy,double* result){
  if(!PrismW6DeterministicEnabled())return cublasDdot(handle,n,x,incx,y,incy,result);
  double* output=W6LaunchFixedDot(handle,n,x,incx,y,incy);
  cublasPointerMode_t mode;CUBLAS_CHECK(cublasGetPointerMode(handle,&mode));
  cudaStream_t stream=nullptr;CUBLAS_CHECK(cublasGetStream(handle,&stream));
  if(mode==CUBLAS_POINTER_MODE_DEVICE)
    CUDA_CHECK(cudaMemcpyAsync(result,output,sizeof(double),cudaMemcpyDeviceToDevice,stream));
  else{
    CUDA_CHECK(cudaMemcpyAsync(result,output,sizeof(double),cudaMemcpyDeviceToHost,stream));
    CUDA_CHECK(cudaStreamSynchronize(stream));
  }
  return CUBLAS_STATUS_SUCCESS;
}

inline cublasStatus_t PrismW6Dnrm2(cublasHandle_t handle,int n,
                                   const double* x,int incx,double* result){
  if(!PrismW6DeterministicEnabled())return cublasDnrm2(handle,n,x,incx,result);
  double* output=W6LaunchFixedDot(handle,n,x,incx,x,incx);
  cublasPointerMode_t mode;CUBLAS_CHECK(cublasGetPointerMode(handle,&mode));
  cudaStream_t stream=nullptr;CUBLAS_CHECK(cublasGetStream(handle,&stream));
  if(mode==CUBLAS_POINTER_MODE_DEVICE)W6SqrtScalar<<<1,1,0,stream>>>(output,result);
  else{
    double value=0;CUDA_CHECK(cudaMemcpyAsync(&value,output,sizeof(double),cudaMemcpyDeviceToHost,stream));
    CUDA_CHECK(cudaStreamSynchronize(stream));*result=std::sqrt(std::max(0.0,value));
  }
  return CUBLAS_STATUS_SUCCESS;
}
