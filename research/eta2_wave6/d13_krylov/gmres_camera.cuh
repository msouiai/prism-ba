#pragma once

// Persistent device storage for one restarted right-preconditioned GMRES
// cycle.  M^-1 V is deliberately recomputed during the small solution update,
// so an m-vector cycle stores only m+1 residual-space vectors.
struct PrismD13GmresWorkspace {
  int n = 0;
  int m = 0;
  double* V = nullptr;

  PrismD13GmresWorkspace(int dimension, int restart) : n(dimension), m(restart) {
    const cudaError_t error = cudaMalloc(&V, (size_t)n * (m + 1) * sizeof(double));
    if (error != cudaSuccess)
      throw std::runtime_error(std::string("D13 GMRES allocation failed: ") +
                               cudaGetErrorString(error));
  }

  ~PrismD13GmresWorkspace() { cudaFree(V); }
};
