#pragma once
#include "boundary.h"

// Factor B is the same lower triangular L used by PrismPcg::Apply.
// One thread per camera, followed by a fixed block reduction. Each block
// contributes three FP64 atomics, never one atomic per observation.
__global__ void StcgMetricGram(int nc,const double* B,const double* x,
                             const double* p,double* out) {
  const int c=blockIdx.x*blockDim.x+threadIdx.x;
  double xx=0,xp=0,pp=0;
  if(c<nc) {
    const double* L=B+81ul*c;
    for(int j=0;j<9;++j) {
      double u=0,v=0;
      for(int i=j;i<9;++i) {
        u+=L[9*i+j]*x[9*c+i];
        if(p) v+=L[9*i+j]*p[9*c+i];
      }
      xx+=u*u;xp+=u*v;pp+=v*v;
    }
  }
  __shared__ double s[3][128];
  const int t=threadIdx.x;s[0][t]=xx;s[1][t]=xp;s[2][t]=pp;
  __syncthreads();
  for(int stride=64;stride;stride>>=1) {
    if(t<stride)for(int k=0;k<3;++k)s[k][t]+=s[k][t+stride];
    __syncthreads();
  }
  if(!t)for(int k=0;k<3;++k)atomicAdd(out+k,s[k][0]);
}

struct PrismSteihaug {
  int nc;double* sums=nullptr;
  double metric_seconds=0,trial_norm=std::numeric_limits<double>::quiet_NaN(),bootstrap_gradient_radius=1;
  long gram_calls=0,boundaries=0,curvature_boundaries=0,invalid=0,bootstraps=0;
  int attempt_reason=0; // 0 interior/cap, 1 radius, 2 finite cutoff, 3 invalid.
  explicit PrismSteihaug(int cameras):nc(cameras){CUDA_CHECK(cudaMalloc(&sums,3*sizeof(double)));}
  ~PrismSteihaug(){cudaFree(sums);}
  void Gram(const double* B,const double* x,const double* p,double* host) {
    const auto start=std::chrono::steady_clock::now();
    CUDA_CHECK(cudaMemset(sums,0,3*sizeof(double)));
    StcgMetricGram<<<(nc+127)/128,128>>>(nc,B,x,p,sums);
    CUDA_CHECK(cudaGetLastError());
    CUDA_CHECK(cudaMemcpy(host,sums,3*sizeof(double),cudaMemcpyDeviceToHost));
    ++gram_calls;
    metric_seconds+=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
  }
  double Norm(const double* B,const double* x) {
    double g[3];Gram(B,x,nullptr,g);
    return g[0]>=0?std::sqrt(g[0]):std::numeric_limits<double>::quiet_NaN();
  }
  void Start(double rz) {
    attempt_reason=0;trial_norm=std::numeric_limits<double>::quiet_NaN();
    bootstrap_gradient_radius=std::isfinite(rz)&&rz>0?std::sqrt(rz):1;
  }
};
