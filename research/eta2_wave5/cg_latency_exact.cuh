#pragma once

__global__ void W5CgXRExact(double* __restrict__ x, double* __restrict__ r,
                            const double* __restrict__ p,
                            const double* __restrict__ Ap,
                            double alpha, int n) {
  int i = blockIdx.x * blockDim.x + threadIdx.x;
  if (i < n) {
    x[i] = __fma_rn(alpha, p[i], x[i]);
    r[i] = __fma_rn(-alpha, Ap[i], r[i]);
  }
}

__global__ void W5CgPExact(double* __restrict__ p,
                           const double* __restrict__ z,
                           double beta, int n) {
  int i = blockIdx.x * blockDim.x + threadIdx.x;
  if (i < n) {
    const double scaled = __dmul_rn(beta, p[i]);
    p[i] = __dadd_rn(z[i], scaled);
  }
}

