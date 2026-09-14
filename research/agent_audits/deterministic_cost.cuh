#pragma once

// A fixed two-level reduction for the scored nonlinear objective.  Each
// observation belongs to one fixed 256-thread block, each block writes one
// private subtotal, and a single block reduces those subtotals in index order.
// This is intentionally a measurement path rather than a latency path.

__global__ void W6CostPartials(
    const int* __restrict__ cam_idx, const int* __restrict__ pt_idx,
    const Scalar* __restrict__ uv, const Scalar* __restrict__ R,
    const Scalar* __restrict__ t, const Scalar* __restrict__ X,
    const Scalar* __restrict__ f, const Scalar* __restrict__ k1,
    const Scalar* __restrict__ k2, int nobs, Scalar* __restrict__ partials,
    int rk, Scalar rk_a2) {
  const int o = blockIdx.x * blockDim.x + threadIdx.x;
  Scalar value = 0.0;
  if (o < nobs) {
    const int c = cam_idx[o], p = pt_idx[o];
    const Scalar* Rc = R + 9 * c;
    const Scalar* Xp = X + 3 * p;
    const Scalar Px = Rc[0]*Xp[0]+Rc[1]*Xp[1]+Rc[2]*Xp[2]+t[3*c];
    const Scalar Py = Rc[3]*Xp[0]+Rc[4]*Xp[1]+Rc[5]*Xp[2]+t[3*c+1];
    const Scalar Pz = Rc[6]*Xp[0]+Rc[7]*Xp[1]+Rc[8]*Xp[2]+t[3*c+2];
    const Scalar xp = -Px/Pz, yp = -Py/Pz;
    const Scalar r2 = xp*xp + yp*yp;
    const Scalar distortion = 1.0 + k1[c]*r2 + k2[c]*r2*r2;
    const Scalar rx = f[c]*distortion*xp - uv[2*o];
    const Scalar ry = f[c]*distortion*yp - uv[2*o+1];
    const Scalar ss = rx*rx + ry*ry;
    value = 0.5 * (rk ? OcaRho(rk, rk_a2, ss) : ss);
  }
  __shared__ Scalar sums[256];
  sums[threadIdx.x] = value;
  __syncthreads();
  for (int stride = 128; stride; stride >>= 1) {
    if (threadIdx.x < stride) sums[threadIdx.x] += sums[threadIdx.x + stride];
    __syncthreads();
  }
  if (threadIdx.x == 0) partials[blockIdx.x] = sums[0];
}

__global__ void W6ReduceScalarFixed(const Scalar* __restrict__ partials,
                                    int count, Scalar* __restrict__ output) {
  Scalar value = 0.0;
  for (int i = threadIdx.x; i < count; i += blockDim.x) value += partials[i];
  __shared__ Scalar sums[256];
  sums[threadIdx.x] = value;
  __syncthreads();
  for (int stride = 128; stride; stride >>= 1) {
    if (threadIdx.x < stride) sums[threadIdx.x] += sums[threadIdx.x + stride];
    __syncthreads();
  }
  if (threadIdx.x == 0) output[0] = sums[0];
}

inline Scalar PrismW6DeterministicCost(const DeviceProblem& p,
                                       const DeviceState& s,
                                       int rk, Scalar rk_a2) {
  static Scalar* partials = nullptr;
  static Scalar* output = nullptr;
  static int capacity = 0;
  const int blocks = GridSize(p.nobs);
#ifdef PRISM_AUDIT_WORKSPACE
  Scalar* use_partials=p.audit_cost_partials;
  Scalar* use_output=p.audit_cost_scratch;
  if(use_partials){
    int device=-1;CUDA_CHECK(cudaGetDevice(&device));
    if(device!=p.audit_workspace_device||blocks>p.audit_cost_capacity)
      throw std::runtime_error("deterministic cost workspace mismatch");
  }else{
    if (blocks > capacity) {
      cudaFree(partials);
      CUDA_CHECK(cudaMalloc(&partials, (size_t)blocks * sizeof(Scalar)));
      capacity = blocks;
    }
    if (!output) CUDA_CHECK(cudaMalloc(&output, sizeof(Scalar)));
    use_partials=partials;use_output=output;
  }
#else
  if (blocks > capacity) {
    cudaFree(partials);
    CUDA_CHECK(cudaMalloc(&partials, (size_t)blocks * sizeof(Scalar)));
    capacity = blocks;
  }
  if (!output) CUDA_CHECK(cudaMalloc(&output, sizeof(Scalar)));
  Scalar* use_partials=partials;Scalar* use_output=output;
#endif
  W6CostPartials<<<blocks, 256>>>(
      p.cam_idx, p.pt_idx, p.uv, s.R, s.t, s.X,
      INTR_F(p,s), INTR_K1(p,s), INTR_K2(p,s), p.nobs, use_partials, rk, rk_a2);
  W6ReduceScalarFixed<<<1,256>>>(use_partials, blocks, use_output);
  Scalar cost = 0.0;
  CUDA_CHECK(cudaMemcpy(&cost, use_output, sizeof(Scalar), cudaMemcpyDeviceToHost));
  return cost;
}
