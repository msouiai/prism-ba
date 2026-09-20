#include <cuda_runtime.h>
#include <cublas_v2.h>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <limits>
#include <stdexcept>
#include <vector>
#include "cg_capture.cuh"
__global__ void Diag(const double*x,double*y,int n){int i=blockIdx.x*blockDim.x+threadIdx.x;if(i<n)y[i]=(1.+i%8)*x[i];}
int main(){
 using namespace prism_recycle;cublasHandle_t h;Check(cublasCreate(&h));
 {int n=257;Basis basis(n,64);CgCapture capture(n,64);double *b,*x,*p,*r,*ap,*z;
 for(auto ptr:{&b,&x,&p,&r,&ap,&z})Check(cudaMalloc((void**)ptr,n*sizeof(double)));
 std::vector<double> host(n,1),reference(n),sol(n);
 for(auto ptr:{b,p,r})Check(cudaMemcpy(ptr,host.data(),n*sizeof(double),cudaMemcpyHostToDevice));
 Check(cudaMemset(x,0,n*sizeof(double)));double seed=10;capture.Reset(seed);int calls=0;
 auto apply=[&](const double*in,double*out){Diag<<<2,256>>>(in,out,n);++calls;};
 auto dot=[&](const double*a,const double*b){double d;Check(cublasDdot(h,n,a,1,b,1,&d));return d;};
 double rr=dot(r,r);const double one=1;
 for(int k=0;k<4;++k){apply(p,ap);Check(cublasDaxpy(h,n,&seed,p,1,ap,1));capture.Append(p,ap);
 double alpha=rr/dot(p,ap),negative=-alpha;Check(cublasDaxpy(h,n,&alpha,p,1,x,1));Check(cublasDaxpy(h,n,&negative,ap,1,r,1));
 double rn=dot(r,r),beta=rn/rr;Check(cublasDscal(h,n,&beta,p,1));Check(cublasDaxpy(h,n,&one,r,1,p,1));rr=rn;}
 Check(cudaMemcpy(reference.data(),x,n*sizeof(double),cudaMemcpyDeviceToHost));
 int before=calls;capture.Import(h,b,basis);if(calls!=before || basis.m!=4)throw std::runtime_error("import work/count failed");
 double residual,pred;if(!basis.Solve(h,apply,b,seed,z,residual,pred))throw std::runtime_error("seed solve failed");
 Check(cudaMemcpy(sol.data(),z,n*sizeof(double),cudaMemcpyDeviceToHost));
 for(int i=0;i<n;++i)if(std::abs(sol[i]-reference[i])>1e-12)throw std::runtime_error("CG iterate not reproduced");
 std::printf("PASS imported CG depth=%d seed iterate reproduced, import matvecs=0\n",basis.m);
 basis.Grow(h,apply,32);
 for(double shift:{.00001,1.,100.}){
 if(!basis.Solve(h,apply,b,shift,z,residual,pred)||residual>1e-10)throw std::runtime_error("expanded shift residual failed");
 Check(cudaMemcpy(sol.data(),z,n*sizeof(double),cudaMemcpyDeviceToHost));
 for(int i=0;i<n;++i)if(std::abs(sol[i]-1/(1.+i%8+shift))>1e-10)throw std::runtime_error("analytic shifted solution failed");
 double checked_prediction=pred;int before_fast=calls;
 if(!basis.Solve(h,apply,b,shift,z,residual,pred,false) || calls!=before_fast ||
    std::abs(pred-checked_prediction)>1e-10*std::max(1.,std::abs(pred)))
 throw std::runtime_error("unchecked reconstruction changes prediction or calls operator");
 Check(cudaMemcpy(sol.data(),z,n*sizeof(double),cudaMemcpyDeviceToHost));
 for(int i=0;i<n;++i)if(std::abs(sol[i]-1/(1.+i%8+shift))>1e-10)throw std::runtime_error("unchecked shifted solution failed");
 std::printf("PASS shift=%g depth=%d checked/unchecked solutions and predictions agree, reconstruction matvecs=0\n",shift,basis.m);}
 capture.Reset(1);if(capture.m)throw std::runtime_error("capture reset failed");
 for(auto ptr:{b,x,p,r,ap,z})cudaFree(ptr);}
 Check(cublasDestroy(h));
}
