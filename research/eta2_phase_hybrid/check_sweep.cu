#include <cuda_runtime.h>
#include <cublas_v2.h>
#include <cstdio>
#include <stdexcept>
#define CUDA_CHECK(x) do{auto e=(x);if(e!=cudaSuccess)throw std::runtime_error(cudaGetErrorString(e));}while(0)
#include "shift_sweep.cuh"
int main(int argc,char**argv){
  FILE*f=fopen(argv[1],"rb");int n,cap;double center,eta;fread(&n,4,1,f);fread(&cap,4,1,f);fread(&center,8,1,f);fread(&eta,8,1,f);
  double*H=new double[(size_t)n*n],*b=new double[n];fread(H,8,(size_t)n*n,f);fread(b,8,n,f);fclose(f);
  double *D,*rhs;CUDA_CHECK(cudaMalloc(&D,(size_t)n*n*8));CUDA_CHECK(cudaMalloc(&rhs,n*8ul));CUDA_CHECK(cudaMemcpy(D,H,(size_t)n*n*8,cudaMemcpyHostToDevice));CUDA_CHECK(cudaMemcpy(rhs,b,n*8ul,cudaMemcpyHostToDevice));
  cublasHandle_t blas;cublasCreate(&blas);int products=0;
  auto K=[&](const double*x,double*y){const double one=1,zero=0;cublasDgemv(blas,CUBLAS_OP_N,n,n,&one,D,n,x,1,&zero,y,1);++products;};
  PrismShiftSweep s(n);bool ok=s.Solve(blas,K,rhs,center,eta,cap);double*out=new double[5ul*n];CUDA_CHECK(cudaMemcpy(out,s.X,5ul*n*8,cudaMemcpyDeviceToHost));
  f=fopen(argv[2],"wb");fwrite(out,8,5ul*n,f);fwrite(s.residual,8,5,f);fwrite(s.G,8,25,f);fclose(f);
  printf("{\"ok\":%s,\"depth\":%d,\"products\":%d,\"qualified\":%s,\"raw\":%.17g,\"clipped\":%.17g}\n",ok?"true":"false",s.depth,products,s.qualified?"true":"false",s.raw_diameter,s.Diameter(.1));
}
