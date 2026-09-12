// GPU-only correctness gate. Compile freely; run only with GPU coordination.
#include <cuda_runtime.h>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <limits>
#include <random>
#include <stdexcept>
#include <vector>
#define CUDA_CHECK(expr) do {cudaError_t e=(expr);if(e!=cudaSuccess)throw std::runtime_error(cudaGetErrorString(e));}while(0)
#include "metric.cuh"

int main(){
  constexpr int nc=257; // crosses block boundary, including partial block.
  std::mt19937_64 rng(20260912);std::normal_distribution<double> normal;
  std::vector<double> L(81*nc,std::numeric_limits<double>::quiet_NaN()),x(9*nc),p(9*nc);
  for(int c=0;c<nc;++c){
    for(int i=0;i<9;++i)for(int j=0;j<=i;++j)
      L[81*c+9*i+j]=i==j?1.+std::fabs(normal(rng)):normal(rng);
    for(int i=0;i<9;++i){x[9*c+i]=normal(rng);p[9*c+i]=normal(rng);}
  }
  long double expected[3]={0,0,0};
  for(int c=0;c<nc;++c)for(int j=0;j<9;++j){
    long double u=0,v=0;
    for(int i=j;i<9;++i){u+=(long double)L[81*c+9*i+j]*x[9*c+i];v+=(long double)L[81*c+9*i+j]*p[9*c+i];}
    expected[0]+=u*u;expected[1]+=u*v;expected[2]+=v*v;
  }
  double *dL,*dx,*dp;
  CUDA_CHECK(cudaMalloc(&dL,L.size()*8));CUDA_CHECK(cudaMalloc(&dx,x.size()*8));CUDA_CHECK(cudaMalloc(&dp,p.size()*8));
  CUDA_CHECK(cudaMemcpy(dL,L.data(),L.size()*8,cudaMemcpyHostToDevice));
  CUDA_CHECK(cudaMemcpy(dx,x.data(),x.size()*8,cudaMemcpyHostToDevice));
  CUDA_CHECK(cudaMemcpy(dp,p.data(),p.size()*8,cudaMemcpyHostToDevice));
  PrismSteihaug st(nc);double got[3];st.Gram(dL,dx,dp,got);
  double maximum=0;
  for(int j=0;j<3;++j){double relative=std::fabs((got[j]-expected[j])/expected[j]);maximum=std::max(maximum,relative);
    if(!(relative<2e-12))throw std::runtime_error("GPU direct M Gram failed CPU long-double reference");}
  const double norm=st.Norm(dL,dx);
  if(!(std::fabs(norm/std::sqrt((double)expected[0])-1)<2e-12))throw std::runtime_error("GPU norm failed reference");
  CUDA_CHECK(cudaFree(dL));CUDA_CHECK(cudaFree(dx));CUDA_CHECK(cudaFree(dp));
  printf("STCG_METRIC_TEST status=passed cameras=%d gram_relative_error=%.17g norm=%.17g\n",nc,maximum,norm);
}
