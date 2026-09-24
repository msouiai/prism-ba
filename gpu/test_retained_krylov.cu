#include <cuda_runtime.h>
#include <cublas_v2.h>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <limits>
#include <stdexcept>
#include <vector>
#include "retained_krylov.cuh"
__global__ void Diagonal(const double*x,double*y,int n){int i=blockIdx.x*blockDim.x+threadIdx.x;if(i<n)y[i]=(1.+(i%8))*x[i];}
int main(){
 using namespace prism_recycle;
 cublasHandle_t h;Check(cublasCreate(&h));
 {int n=257;Basis basis(n,64);double *b,*x;Check(cudaMalloc((void**)&b,n*8));Check(cudaMalloc((void**)&x,n*8));
 std::vector<double> host(n,1.),sol(n);Check(cudaMemcpy(b,host.data(),n*8,cudaMemcpyHostToDevice));
 int calls=0;auto apply=[&](const double*in,double*out){Diagonal<<<2,256>>>(in,out,n);++calls;};
 basis.Reset(h,b);basis.Grow(h,apply,4);
 double residual,pred;basis.Solve(h,apply,b,.01,x,residual,pred);
 if(!(residual>1e-8))throw std::runtime_error("short basis unexpectedly exact");
 basis.Grow(h,apply,32);int depth=basis.m;
 for(double shift: {1.,.00001,100.}){
 int before=calls;
 if(!basis.Solve(h,apply,b,shift,x,residual,pred) || residual>1e-11 || calls-before!=1)
 throw std::runtime_error("reuse residual/call count failed");
 Check(cudaMemcpy(sol.data(),x,n*8,cudaMemcpyDeviceToHost));
 double exactpred=0;
 for(int i=0;i<n;++i){double expected=1/(1.+i%8+shift);exactpred+=.5*expected;
 if(std::abs(sol[i]-expected)>1e-11)throw std::runtime_error("analytic solution mismatch");}
 if(std::abs(pred-exactpred)>1e-10)throw std::runtime_error("prediction mismatch");
 std::printf("PASS shift=%g depth=%d residual=%.3g new_matvecs=%d\n",shift,depth,residual,calls-before);
 }
 if(basis.Solve(h,apply,b,-10.,x,residual,pred))throw std::runtime_error("indefinite projection accepted");
 basis.Reset(h,b);if(basis.m!=0)throw std::runtime_error("reset failed");
 cudaFree(b);cudaFree(x);}
 Check(cublasDestroy(h));
}
