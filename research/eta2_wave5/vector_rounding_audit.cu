#include <cublas_v2.h>
#include <cuda_runtime.h>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>
#include "cg_latency_exact.cuh"

#define OK(x) do { if ((x) != cudaSuccess) return 2; } while (0)
#define BLAS(x) do { if ((x) != CUBLAS_STATUS_SUCCESS) return 3; } while (0)

int main() {
  constexpr int n = 1000003;
  constexpr double alpha = -0.3712345678901234;
  constexpr double beta = 0.8123456789012345;
  std::mt19937_64 rng(0x65746132ULL);
  std::uniform_real_distribution<double> dist(-1e4, 1e4);
  std::vector<double> x(n), r(n), p(n), Ap(n), z(n);
  for (int i = 0; i < n; ++i) {
    x[i] = dist(rng); r[i] = dist(rng); p[i] = dist(rng);
    Ap[i] = dist(rng); z[i] = dist(rng);
  }
  double *dx0, *dr0, *dp0, *dx1, *dr1, *dp1, *dAp, *dz;
  OK(cudaMalloc(&dx0, n*8ul)); OK(cudaMalloc(&dr0, n*8ul)); OK(cudaMalloc(&dp0, n*8ul));
  OK(cudaMalloc(&dx1, n*8ul)); OK(cudaMalloc(&dr1, n*8ul)); OK(cudaMalloc(&dp1, n*8ul));
  OK(cudaMalloc(&dAp, n*8ul)); OK(cudaMalloc(&dz, n*8ul));
  const std::pair<double*,const double*> copies[] = {
    {dx0,x.data()}, {dx1,x.data()}, {dr0,r.data()}, {dr1,r.data()},
    {dp0,p.data()}, {dp1,p.data()}, {dAp,Ap.data()}, {dz,z.data()}};
  for (const auto& pair : copies)
    OK(cudaMemcpy(pair.first, pair.second, n*8ul, cudaMemcpyHostToDevice));
  cublasHandle_t blas; BLAS(cublasCreate(&blas));
  BLAS(cublasDaxpy(blas,n,&alpha,dp0,1,dx0,1));
  const double mal = -alpha, one = 1.0;
  BLAS(cublasDaxpy(blas,n,&mal,dAp,1,dr0,1));
  BLAS(cublasDscal(blas,n,&beta,dp0,1));
  BLAS(cublasDaxpy(blas,n,&one,dz,1,dp0,1));
  W5CgXRExact<<<(n+255)/256,256>>>(dx1,dr1,dp1,dAp,alpha,n);
  W5CgPExact<<<(n+255)/256,256>>>(dp1,dz,beta,n);
  std::vector<double> a(n), b(n); long long mismatch_x=0,mismatch_r=0,mismatch_p=0;
  auto compare = [&](double* u, double* v, long long& mismatch) {
    OK(cudaMemcpy(a.data(),u,n*8ul,cudaMemcpyDeviceToHost));
    OK(cudaMemcpy(b.data(),v,n*8ul,cudaMemcpyDeviceToHost));
    for (int i=0;i<n;++i) mismatch += std::memcmp(&a[i],&b[i],8)!=0;
    return 0;
  };
  if(compare(dx0,dx1,mismatch_x)||compare(dr0,dr1,mismatch_r)||compare(dp0,dp1,mismatch_p))return 4;
  std::printf("VECTOR_ROUNDING_AUDIT n=%d mismatch_x=%lld mismatch_r=%lld mismatch_p=%lld\n",
              n,mismatch_x,mismatch_r,mismatch_p);
  cublasDestroy(blas); cudaFree(dx0);cudaFree(dr0);cudaFree(dp0);cudaFree(dx1);cudaFree(dr1);cudaFree(dp1);cudaFree(dAp);cudaFree(dz);
  return (mismatch_x||mismatch_r||mismatch_p) ? 1 : 0;
}
