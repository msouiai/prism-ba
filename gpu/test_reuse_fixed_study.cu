#include <cuda_runtime.h>
#include <cublas_v2.h>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <limits>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>
#include "cg_capture.cuh"
#include "selective_reuse.h"
#include "reuse_fixed_study.cuh"
__global__ void DiagonalFixed(const double*x,double*y,int n){int i=threadIdx.x+blockIdx.x*blockDim.x;if(i<n)y[i]=(1.+i%8)*x[i];}
int main(){
 using prism_recycle::Check;cublasHandle_t h;Check(cublasCreate(&h));
 {const int n=257;prism_fixed::Buffer b(n);std::vector<double> host(n,1.);
 Check(cudaMemcpy(b.p,host.data(),n*sizeof(double),cudaMemcpyHostToDevice));
 auto apply=[&](const double*x,double*y){DiagonalFixed<<<2,256>>>(x,y,n);};double capture_time=0;
 auto out=prism_fixed::CG(h,n,b.p,{.01,.1,1.,10.,100.},apply,1e-10,128,nullptr,capture_time,true);
 if(!out.curvature||out.worst>1e-10)throw std::runtime_error("fixed multi-CG analytic residual gate failed");
 std::printf("PASS shared CG worst true residual %.3g\n",out.worst);
 prism_fixed::Run(h,n,b.p,{.01,.1,1.,10.,100.},1.,1e-6,128,0,8,0,{8,16,32,64,128},apply);
 }Check(cublasDestroy(h));
}
