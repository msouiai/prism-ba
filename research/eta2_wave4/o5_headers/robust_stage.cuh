#pragma once
__device__ int w5_device_rk=0;
__device__ double w5_device_a2=0;
inline void W5SetRobust(int rk,double a2){
 CUDA_CHECK(cudaMemcpyToSymbol(w5_device_rk,&rk,sizeof(rk)));
 CUDA_CHECK(cudaMemcpyToSymbol(w5_device_a2,&a2,sizeof(a2)));
}
