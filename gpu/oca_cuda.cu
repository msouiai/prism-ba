// CUDA implementation of OCA (Optimal Control Algorithm) bundle adjustment,
// Xu, Wang, Han & Zhang, arXiv:2411.06343, plus LM (Algorithm 1) for comparison.
// This is the parallel port of reference_oca.py -- see that file for the algorithm
// derivations (Algorithm 1/2/3 = solve_lm/solve_oca/solve_oca_adaptive) and
// bal_hessian_generated.py / validate_hessian.py for the analytic-Hessian
// correctness gate. The CUDA per-observation Hessian (bal_hessian_generated.cuh)
// is generated from the SAME symbolic derivation as the numpy version (see
// derive_hessian_cuda.py), not hand-transcribed, and independently verified to
// match it to ~1e-15 (test_hessian_cuda.cu) -- so the only new correctness surface
// here is the parallel assembly/solve orchestration, not the per-observation math.
//
// Precision: fp64 (Scalar=double) throughout, matching reference_oca.py and this
// whole codebase's established BA convention.
//
// Parallelization: OCA's TRUE Hessian couples every camera to every point it
// observes (unlike DABA's block-Jacobi/majorization split in daba_mm.cu), so this
// is a genuinely global dense (lam*I+H) solve, not independent per-camera/per-point
// systems. The two parallel opportunities this file exploits:
//   (1) per-observation grad+Hessian assembly is embarrassingly parallel (one
//       thread per observation, atomicAdd-scattered into the dense global system,
//       same pattern as daba_mm.cu's KernelJacobianAccumulate);
//   (2) Algorithm 2/3's own structure -- factorize (lam*I+H) ONCE per outer
//       iteration k, then reuse that factorization for k+1 cheap triangular solves
//       -- is preserved exactly, via cuSOLVER's dense Cholesky (cusolverDnDpotrf
//       once, cusolverDnDpotrs k+1 times), so the O(n^3) factorization cost is
//       still paid only once per outer iteration, matching the numpy reference.
// Dense O(n^2) memory / O(n^3) factorization is a deliberate first-cut scope
// match to reference_oca.py's own dense assemble_grad_hessian (see its docstring):
// this targets exact reproduction of the validated reference at its validated
// scale first; a sparse/Schur-complement port for real BAL-scale problems is
// future work, not attempted here (see README).
#include <cuda_runtime.h>
#include <cusolverDn.h>
#include <cublas_v2.h>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <deque>
#include <fstream>
#include <limits>
#include <sstream>
#include <string>
#include <unordered_map>
#include <vector>

#include <stdexcept>

using Scalar = double;

namespace oca_detail {
struct CudaError : std::runtime_error {
  explicit CudaError(const std::string& what) : std::runtime_error(what) {}
};
}  // namespace oca_detail

// Throws rather than exits: this translation unit is also compiled into the
// embeddable core (see oca_core.h), where a CUDA OOM must surface as a failed
// Solve() the host can fall back from -- not as std::exit taking the caller's
// whole process down. The CLI catches it in main() and returns 1, so the
// observable behaviour of oca_cuda is unchanged.
#define CUDA_CHECK(call)                                                     \
  do {                                                                       \
    cudaError_t err__ = (call);                                              \
    if (err__ != cudaSuccess) {                                              \
      throw ::oca_detail::CudaError(std::string("CUDA error ") + __FILE__ +  \
                                    ":" + std::to_string(__LINE__) + ": " +  \
                                    cudaGetErrorString(err__));              \
    }                                                                        \
  } while (0)

#define CUSOLVER_CHECK(call)                                                 \
  do {                                                                       \
    cusolverStatus_t st__ = (call);                                          \
    if (st__ != CUSOLVER_STATUS_SUCCESS) {                                   \
      std::fprintf(stderr, "cuSOLVER error %s:%d: %d\n", __FILE__, __LINE__, \
                    (int)st__);                                              \
      std::exit(EXIT_FAILURE);                                               \
    }                                                                        \
  } while (0)

#define CUBLAS_CHECK(call)                                                   \
  do {                                                                       \
    cublasStatus_t st__ = (call);                                            \
    if (st__ != CUBLAS_STATUS_SUCCESS) {                                     \
      std::fprintf(stderr, "cuBLAS error %s:%d: %d\n", __FILE__, __LINE__,   \
                    (int)st__);                                              \
      std::exit(EXIT_FAILURE);                                               \
    }                                                                        \
  } while (0)

#include "bal_hessian_generated.cuh"
#include "bal_grad12_generated.cuh"  // ROUND 10: 12-param GN gradient (pose 6 + f,k1,k2 + point 3)

// ============================================================== BAL loading (same format as daba_cuda)
struct BalData {
  int ncam = 0, npt = 0, nobs = 0;
  std::vector<int> cam_idx, pt_idx;
  std::vector<Scalar> uv;    // 2*nobs
  std::vector<Scalar> cams;  // 9*ncam: angle-axis(3), t(3), f, k1, k2
  std::vector<Scalar> pts;   // 3*npt
};

BalData LoadBal(const std::string& path) {
  std::ifstream fh(path);
  if (!fh) {
    std::fprintf(stderr, "Cannot open %s\n", path.c_str());
    std::exit(EXIT_FAILURE);
  }
  BalData d;
  fh >> d.ncam >> d.npt >> d.nobs;
  d.cam_idx.resize(d.nobs);
  d.pt_idx.resize(d.nobs);
  d.uv.resize(2 * d.nobs);
  for (int o = 0; o < d.nobs; ++o) {
    fh >> d.cam_idx[o] >> d.pt_idx[o] >> d.uv[2 * o] >> d.uv[2 * o + 1];
  }
  d.cams.resize(9 * d.ncam);
  for (auto& v : d.cams) fh >> v;
  d.pts.resize(3 * d.npt);
  for (auto& v : d.pts) fh >> v;
  return d;
}

// ============================================================== SO(3) helpers (same convention as daba_mm.cu)
__device__ __forceinline__ void ExpSO3(const Scalar* a, Scalar* R) {
  Scalar th = std::sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2]);
  if (th < 1e-12) {
    R[0] = 1; R[1] = 0; R[2] = 0;
    R[3] = 0; R[4] = 1; R[5] = 0;
    R[6] = 0; R[7] = 0; R[8] = 1;
    return;
  }
  Scalar kx = a[0] / th, ky = a[1] / th, kz = a[2] / th;
  Scalar c = std::cos(th), s = std::sin(th), C = 1 - c;
  R[0] = c + kx * kx * C;      R[1] = kx * ky * C - kz * s; R[2] = kx * kz * C + ky * s;
  R[3] = ky * kx * C + kz * s; R[4] = c + ky * ky * C;      R[5] = ky * kz * C - kx * s;
  R[6] = kz * kx * C - ky * s; R[7] = kz * ky * C + kx * s; R[8] = c + kz * kz * C;
}

__device__ __forceinline__ void Mat3Mul(const Scalar* A, const Scalar* B, Scalar* out) {
  for (int i = 0; i < 3; ++i)
    for (int j = 0; j < 3; ++j) {
      Scalar s = 0;
      for (int k = 0; k < 3; ++k) s += A[3 * i + k] * B[3 * k + j];
      out[3 * i + j] = s;
    }
}

__global__ void KernelExpSO3All(const Scalar* __restrict__ omega, Scalar* __restrict__ R, int ncam) {
  int c = blockIdx.x * blockDim.x + threadIdx.x;
  if (c >= ncam) return;
  ExpSO3(omega + 3 * c, R + 9 * c);
}

// R_new = Exp(domega) @ R_old  (retraction convention, matches reference_oca.py's retract())
__global__ void KernelRetractCameras(const Scalar* __restrict__ R_old, const Scalar* __restrict__ t_old,
                                      const Scalar* __restrict__ d, Scalar* __restrict__ R_new,
                                      Scalar* __restrict__ t_new, int ncam) {
  int c = blockIdx.x * blockDim.x + threadIdx.x;
  if (c >= ncam) return;
  Scalar dR[9];
  ExpSO3(d + 6 * c, dR);
  Mat3Mul(dR, R_old + 9 * c, R_new + 9 * c);
  for (int i = 0; i < 3; ++i) t_new[3 * c + i] = t_old[3 * c + i] + d[6 * c + 3 + i];
}

__global__ void KernelRetractPoints(const Scalar* __restrict__ X_old, const Scalar* __restrict__ d,
                                     Scalar* __restrict__ X_new, int npt, int ncam) {
  int p = blockIdx.x * blockDim.x + threadIdx.x;
  if (p >= npt) return;
  const Scalar* dp = d + 6 * ncam + 3 * p;
  for (int i = 0; i < 3; ++i) X_new[3 * p + i] = X_old[3 * p + i] + dp[i];
}

// ============================================================== robust kernels
// IRLS kernels shared by the cost and the assembly. s = |r|^2, a2 = the
// kernel's squared scale (delta^2 huber, c^2 cauchy, nu*sigma^2 student-t).
// Identical formulas to the CPU port's RobustRho/RobustW (mfree_cpu.h), the
// reference the GPU is gated against. k == 0 is exactly L2, and every call
// site keeps its pre-robust arithmetic when k == 0 (bit-compat).
__host__ __device__ __forceinline__ Scalar OcaRho(int k, Scalar a2, Scalar s) {
  if (k == 1) return s <= a2 ? s : 2.0*sqrt(a2*s) - a2;
  if (k == 2 || k == 3) return a2*log1p(s/a2);
  return s;
}
__host__ __device__ __forceinline__ Scalar OcaRobustW(int k, Scalar a2, Scalar s) {
  if (k == 1) return s <= a2 ? 1.0 : sqrt(a2/s);
  if (k == 2 || k == 3) return 1.0/(1.0 + s/a2);
  return 1.0;
}

// ============================================================== cost + assembly kernels
__global__ void KernelCost(const int* __restrict__ cam_idx, const int* __restrict__ pt_idx,
                            const Scalar* __restrict__ uv, const Scalar* __restrict__ R,
                            const Scalar* __restrict__ t, const Scalar* __restrict__ X,
                            const Scalar* __restrict__ f, const Scalar* __restrict__ k1,
                            const Scalar* __restrict__ k2, int nobs, Scalar* __restrict__ cost_out,
                            int rk = 0, Scalar rk_a2 = 0.0) {
  int o = blockIdx.x * blockDim.x + threadIdx.x;
  if (o >= nobs) return;
  int c = cam_idx[o], p = pt_idx[o];
  const Scalar* Rc = R + 9 * c;
  const Scalar* Xp = X + 3 * p;
  Scalar Px = Rc[0]*Xp[0]+Rc[1]*Xp[1]+Rc[2]*Xp[2] + t[3*c];
  Scalar Py = Rc[3]*Xp[0]+Rc[4]*Xp[1]+Rc[5]*Xp[2] + t[3*c+1];
  Scalar Pz = Rc[6]*Xp[0]+Rc[7]*Xp[1]+Rc[8]*Xp[2] + t[3*c+2];
  Scalar xp = -Px / Pz, yp = -Py / Pz;
  Scalar r2 = xp*xp + yp*yp;
  Scalar dist = 1.0 + k1[c]*r2 + k2[c]*r2*r2;
  Scalar rx = f[c]*dist*xp - uv[2*o];
  Scalar ry = f[c]*dist*yp - uv[2*o+1];
  const Scalar ss = rx*rx + ry*ry;
  atomicAdd(cost_out, 0.5 * (rk ? OcaRho(rk, rk_a2, ss) : ss));
}

// Block-reduced cost kernel. KernelCost above funnels EVERY observation's
// contribution through a single global atomicAdd -- 5-29M threads serializing
// on one address. Measured on venice-1778: 7.0ms per cost eval where the pure
// bandwidth cost is ~1ms. This variant reduces within the block in shared
// memory and issues ONE atomicAdd per 256-thread block (~20k atomics instead
// of millions). Same math; summation order differs (rounding-level).
// Selected by OCA_COST_BLOCKRED=1; default off = bit-compat.
__global__ void KernelCostBlockRed(const int* __restrict__ cam_idx, const int* __restrict__ pt_idx,
                            const Scalar* __restrict__ uv, const Scalar* __restrict__ R,
                            const Scalar* __restrict__ t, const Scalar* __restrict__ X,
                            const Scalar* __restrict__ f, const Scalar* __restrict__ k1,
                            const Scalar* __restrict__ k2, int nobs, Scalar* __restrict__ cost_out,
                            int rk, Scalar rk_a2) {
  int o = blockIdx.x * blockDim.x + threadIdx.x;
  Scalar v = 0.0;
  if (o < nobs) {
    int c = cam_idx[o], p = pt_idx[o];
    const Scalar* Rc = R + 9 * c;
    const Scalar* Xp = X + 3 * p;
    Scalar Px = Rc[0]*Xp[0]+Rc[1]*Xp[1]+Rc[2]*Xp[2] + t[3*c];
    Scalar Py = Rc[3]*Xp[0]+Rc[4]*Xp[1]+Rc[5]*Xp[2] + t[3*c+1];
    Scalar Pz = Rc[6]*Xp[0]+Rc[7]*Xp[1]+Rc[8]*Xp[2] + t[3*c+2];
    Scalar xp = -Px / Pz, yp = -Py / Pz;
    Scalar r2 = xp*xp + yp*yp;
    Scalar dist = 1.0 + k1[c]*r2 + k2[c]*r2*r2;
    Scalar rx = f[c]*dist*xp - uv[2*o];
    Scalar ry = f[c]*dist*yp - uv[2*o+1];
    const Scalar ss = rx*rx + ry*ry;
    v = 0.5 * (rk ? OcaRho(rk, rk_a2, ss) : ss);
  }
  __shared__ Scalar sh[256];
  sh[threadIdx.x] = v;
  __syncthreads();
  for (int st = 128; st > 0; st >>= 1) {
    if (threadIdx.x < st) sh[threadIdx.x] += sh[threadIdx.x + st];
    __syncthreads();
  }
  if (threadIdx.x == 0) atomicAdd(cost_out, sh[0]);
}

// Strided clone of KernelCost (subsampled candidate scoring). Same body.
__global__ void KernelCostStride(const int* __restrict__ cam_idx, const int* __restrict__ pt_idx,
                            const Scalar* __restrict__ uv, const Scalar* __restrict__ R,
                            const Scalar* __restrict__ t, const Scalar* __restrict__ X,
                            const Scalar* __restrict__ f, const Scalar* __restrict__ k1,
                            const Scalar* __restrict__ k2, int nobs, int stride,
                            Scalar* __restrict__ cost_out, int rk, Scalar rk_a2) {
  int o = blockIdx.x * blockDim.x + threadIdx.x;
  if (o >= nobs) return;
  int c = cam_idx[o], p = pt_idx[o];
  if (p % stride) return;   // point-level subset (see MFPass1Stride)
  const Scalar* Rc = R + 9 * c;
  const Scalar* Xp = X + 3 * p;
  Scalar Px = Rc[0]*Xp[0]+Rc[1]*Xp[1]+Rc[2]*Xp[2] + t[3*c];
  Scalar Py = Rc[3]*Xp[0]+Rc[4]*Xp[1]+Rc[5]*Xp[2] + t[3*c+1];
  Scalar Pz = Rc[6]*Xp[0]+Rc[7]*Xp[1]+Rc[8]*Xp[2] + t[3*c+2];
  Scalar xp = -Px / Pz, yp = -Py / Pz;
  Scalar r2 = xp*xp + yp*yp;
  Scalar dist = 1.0 + k1[c]*r2 + k2[c]*r2*r2;
  Scalar rx = f[c]*dist*xp - uv[2*o];
  Scalar ry = f[c]*dist*yp - uv[2*o+1];
  const Scalar ss = rx*rx + ry*ry;
  atomicAdd(cost_out, 0.5 * (rk ? OcaRho(rk, rk_a2, ss) : ss));
}

// Per-observation squared residual, for the student-t EM scale estimate. The
// body is KernelCost's verbatim (same Snavely -P/Pz convention) so the scale
// is never estimated from a re-derived projection -- a sign slip there makes
// sigma explode and the kernel silently degenerates to L2 (measured while
// prototyping the CPU version).
__global__ void KernelResidSq(const int* __restrict__ cam_idx, const int* __restrict__ pt_idx,
                              const Scalar* __restrict__ uv, const Scalar* __restrict__ R,
                              const Scalar* __restrict__ t, const Scalar* __restrict__ X,
                              const Scalar* __restrict__ f, const Scalar* __restrict__ k1,
                              const Scalar* __restrict__ k2, int nobs, Scalar* __restrict__ s_out) {
  int o = blockIdx.x * blockDim.x + threadIdx.x;
  if (o >= nobs) return;
  int c = cam_idx[o], p = pt_idx[o];
  const Scalar* Rc = R + 9 * c;
  const Scalar* Xp = X + 3 * p;
  Scalar Px = Rc[0]*Xp[0]+Rc[1]*Xp[1]+Rc[2]*Xp[2] + t[3*c];
  Scalar Py = Rc[3]*Xp[0]+Rc[4]*Xp[1]+Rc[5]*Xp[2] + t[3*c+1];
  Scalar Pz = Rc[6]*Xp[0]+Rc[7]*Xp[1]+Rc[8]*Xp[2] + t[3*c+2];
  Scalar xp = -Px / Pz, yp = -Py / Pz;
  Scalar r2 = xp*xp + yp*yp;
  Scalar dist = 1.0 + k1[c]*r2 + k2[c]*r2*r2;
  Scalar rx = f[c]*dist*xp - uv[2*o];
  Scalar ry = f[c]*dist*yp - uv[2*o+1];
  s_out[o] = rx*rx + ry*ry;
}

// One EM M-step accumulation: sum_i u_i s_i, u_i = (nu+2)/(nu+s_i/sigma^2).
__global__ void KernelTEMSum(const Scalar* __restrict__ sv, int nobs, Scalar nu,
                             Scalar sig2, Scalar* __restrict__ acc) {
  int o = blockIdx.x * blockDim.x + threadIdx.x;
  if (o >= nobs) return;
  const Scalar u = (nu + 2.0)/(nu + sv[o]/sig2);
  atomicAdd(acc, u*sv[o]);
}

// Watertightness check (see task history): raw sum-of-squared-residuals cost
// alone can't rule out a degenerate solution (e.g. points collapsed near a
// camera center, which can produce a deceptively small residual while being
// physically meaningless). Reports the same two diagnostics colmap_ba_compare
// already reports for Ceres/Caspar -- median reprojection error in pixels
// (robust to outliers, unlike RMS) and cheirality violations (points ending
// up behind a camera that observes them) -- so every solver in this file gets
// the same scrutiny before its final cost is trusted. Violating observations
// are excluded from the reprojection-error array (their error is physically
// undefined) rather than included with some sentinel value that would bias
// the median.
//
// Cheirality sign: this file's residual formula (xp=-Px/Pz, matching every
// solver's assembly kernel and the original bal_hessian_generated derivation)
// uses the standard BAL/Bundler convention -- the camera looks down the -Z
// axis in camera space, so a point IN FRONT of the camera has Pz<0, not
// Pz>0. A violation is therefore Pz>=0 (caught the hard way: an early version
// of this check used Pz<=0, which flagged 99.99% of ladybug-598's
// observations as violations even at the unmodified initial state -- the
// residual/optimizer code was never wrong, only this diagnostic's own sign).
__global__ void KernelDiagnostics(
    const int* __restrict__ cam_idx, const int* __restrict__ pt_idx, const Scalar* __restrict__ uv,
    const Scalar* __restrict__ R, const Scalar* __restrict__ t, const Scalar* __restrict__ X,
    const Scalar* __restrict__ f, const Scalar* __restrict__ k1, const Scalar* __restrict__ k2, int nobs,
    Scalar* __restrict__ reproj_err, int* __restrict__ obs_cheirality, int* __restrict__ pt_cheirality) {
  int o = blockIdx.x * blockDim.x + threadIdx.x;
  if (o >= nobs) return;
  int c = cam_idx[o], p = pt_idx[o];
  const Scalar* Rc = R + 9*c; const Scalar* Xp = X + 3*p;
  Scalar Px = Rc[0]*Xp[0]+Rc[1]*Xp[1]+Rc[2]*Xp[2] + t[3*c];
  Scalar Py = Rc[3]*Xp[0]+Rc[4]*Xp[1]+Rc[5]*Xp[2] + t[3*c+1];
  Scalar Pz = Rc[6]*Xp[0]+Rc[7]*Xp[1]+Rc[8]*Xp[2] + t[3*c+2];
  if (Pz >= 0.0) {
    obs_cheirality[o] = 1;
    reproj_err[o] = -1.0;  // sentinel: excluded from median on the host side
    atomicMax(&pt_cheirality[p], 1);
    return;
  }
  obs_cheirality[o] = 0;
  Scalar xp = -Px/Pz, yp = -Py/Pz; Scalar r2 = xp*xp+yp*yp;
  Scalar dist = 1.0 + k1[c]*r2 + k2[c]*r2*r2;
  Scalar rx = f[c]*dist*xp - uv[2*o];
  Scalar ry = f[c]*dist*yp - uv[2*o+1];
  reproj_err[o] = std::sqrt(rx*rx + ry*ry);
}

// Per-observation TRUE cost contribution, computed UNCONDITIONALLY on Pz sign -- this is
// exactly KernelCost's per-thread body (the formula the real optimizer cost sums), just
// written per-observation instead of atomicAdd-reduced. Unlike KernelDiagnostics (which
// sentinels cheirality-violating observations to -1, appropriate for its median-error use
// but NOT for reconstructing the true total cost), this lets an offline analysis exactly
// partition F = sum_o cost_out[o] into any subset (e.g. "clean in both of two solvers'
// final states") and have the parts actually sum to the reported total.
__global__ void KernelTrueResidualDump(const int* __restrict__ cam_idx, const int* __restrict__ pt_idx,
                                        const Scalar* __restrict__ uv, const Scalar* __restrict__ R,
                                        const Scalar* __restrict__ t, const Scalar* __restrict__ X,
                                        const Scalar* __restrict__ f, const Scalar* __restrict__ k1,
                                        const Scalar* __restrict__ k2, int nobs,
                                        Scalar* __restrict__ cost_out, int* __restrict__ obs_cheirality) {
  int o = blockIdx.x * blockDim.x + threadIdx.x;
  if (o >= nobs) return;
  int c = cam_idx[o], p = pt_idx[o];
  const Scalar* Rc = R + 9*c; const Scalar* Xp = X + 3*p;
  Scalar Px = Rc[0]*Xp[0]+Rc[1]*Xp[1]+Rc[2]*Xp[2] + t[3*c];
  Scalar Py = Rc[3]*Xp[0]+Rc[4]*Xp[1]+Rc[5]*Xp[2] + t[3*c+1];
  Scalar Pz = Rc[6]*Xp[0]+Rc[7]*Xp[1]+Rc[8]*Xp[2] + t[3*c+2];
  obs_cheirality[o] = (Pz >= 0.0) ? 1 : 0;
  Scalar xp = -Px/Pz, yp = -Py/Pz; Scalar r2 = xp*xp+yp*yp;
  Scalar dist = 1.0 + k1[c]*r2 + k2[c]*r2*r2;
  Scalar rx = f[c]*dist*xp - uv[2*o];
  Scalar ry = f[c]*dist*yp - uv[2*o+1];
  cost_out[o] = 0.5 * (rx*rx + ry*ry);
}

// One thread per observation: computes the per-observation TRUE 9x9 Hessian block
// (H9 = outer(gx,gx)+outer(gy,gy)+rx*hx+ry*hy) and the Gauss-Newton-only block
// (H9_gn = outer(gx,gx)+outer(gy,gy)), then atomically scatters both into the dense
// global (n x n) systems -- H_true for OCA, H_gn for LM (Algorithm 1 uses ONLY the
// Gauss-Newton Hessian per Eq.2, exactly like reference_oca.py's solve_lm, so the
// LM-vs-OCA comparison isn't confounded by also upgrading LM's Hessian).
// n = 6*ncam + 3*npt; camera blocks first (domega(3),dt(3)), then point blocks (dX(3)).
__global__ void KernelAssembleGradHess(
    const int* __restrict__ cam_idx, const int* __restrict__ pt_idx, const Scalar* __restrict__ uv,
    const Scalar* __restrict__ R, const Scalar* __restrict__ t, const Scalar* __restrict__ X,
    const Scalar* __restrict__ f, const Scalar* __restrict__ k1, const Scalar* __restrict__ k2,
    int nobs, int ncam, int npt, int n,
    Scalar* __restrict__ grad, Scalar* __restrict__ H, Scalar* __restrict__ H_gn) {
  int o = blockIdx.x * blockDim.x + threadIdx.x;
  if (o >= nobs) return;
  int c = cam_idx[o], p = pt_idx[o];
  const Scalar* Rc = R + 9 * c;
  const Scalar* Xp = X + 3 * p;
  Scalar Px = Rc[0]*Xp[0]+Rc[1]*Xp[1]+Rc[2]*Xp[2] + t[3*c];
  Scalar Py = Rc[3]*Xp[0]+Rc[4]*Xp[1]+Rc[5]*Xp[2] + t[3*c+1];
  Scalar Pz = Rc[6]*Xp[0]+Rc[7]*Xp[1]+Rc[8]*Xp[2] + t[3*c+2];
  Scalar xp = -Px / Pz, yp = -Py / Pz;
  Scalar r2 = xp*xp + yp*yp;
  Scalar dist = 1.0 + k1[c]*r2 + k2[c]*r2*r2;
  Scalar rx = f[c]*dist*xp - uv[2*o];
  Scalar ry = f[c]*dist*yp - uv[2*o+1];

  Scalar gx[9], gy[9], hx[81], hy[81];
  BalResidualGradHess(Rc[0],Rc[1],Rc[2],Rc[3],Rc[4],Rc[5],Rc[6],Rc[7],Rc[8],
                       t[3*c],t[3*c+1],t[3*c+2],Xp[0],Xp[1],Xp[2],
                       f[c],k1[c],k2[c],uv[2*o],uv[2*o+1], gx,gy,hx,hy);

  Scalar g9[9], H9[81], H9gn[81];
#pragma unroll
  for (int i = 0; i < 9; ++i) g9[i] = rx*gx[i] + ry*gy[i];
#pragma unroll
  for (int i = 0; i < 9; ++i)
#pragma unroll
    for (int j = 0; j < 9; ++j) {
      Scalar gn = gx[i]*gx[j] + gy[i]*gy[j];
      H9gn[9*i+j] = gn;
      H9[9*i+j] = gn + rx*hx[9*i+j] + ry*hy[9*i+j];
    }

  int cs = 6 * c, ps = 6 * ncam + 3 * p;
#pragma unroll
  for (int i = 0; i < 6; ++i) atomicAdd(&grad[cs + i], g9[i]);
#pragma unroll
  for (int i = 0; i < 3; ++i) atomicAdd(&grad[ps + i], g9[6 + i]);

  // Scatter 9x9 -> the 6x6 camera-camera, 3x3 point-point, and 6x3/3x6
  // camera-point cross blocks of the dense n x n system (row-major).
#pragma unroll
  for (int i = 0; i < 6; ++i) {
    for (int j = 0; j < 6; ++j) {
      atomicAdd(&H[(cs+i)*n + (cs+j)], H9[9*i+j]);
      atomicAdd(&H_gn[(cs+i)*n + (cs+j)], H9gn[9*i+j]);
    }
    for (int j = 0; j < 3; ++j) {
      atomicAdd(&H[(cs+i)*n + (ps+j)], H9[9*i + 6+j]);
      atomicAdd(&H[(ps+j)*n + (cs+i)], H9[9*(6+j)+i]);
      atomicAdd(&H_gn[(cs+i)*n + (ps+j)], H9gn[9*i + 6+j]);
      atomicAdd(&H_gn[(ps+j)*n + (cs+i)], H9gn[9*(6+j)+i]);
    }
  }
#pragma unroll
  for (int i = 0; i < 3; ++i)
    for (int j = 0; j < 3; ++j) {
      atomicAdd(&H[(ps+i)*n + (ps+j)], H9[9*(6+i)+(6+j)]);
      atomicAdd(&H_gn[(ps+i)*n + (ps+j)], H9gn[9*(6+i)+(6+j)]);
    }
}

// ============================================================== Schur-complement assembly (Phase 2)
// Exact algebraic reformulation of the dense (lam*I+H) solve, exploiting BAL's
// arrowhead sparsity (see reference_oca_schur.py's docstring for the full
// derivation): a single observation touches exactly one camera and one point,
// so the raw Hessian is block-diagonal in camera-camera space (Hcc, NC
// independent 6x6 blocks) and point-point space (Hpp, NP independent 3x3
// blocks) -- only camera-point cross terms (Hcp) exist. Eliminating the
// points (cheap, since Hpp is block-diagonal) reduces the system to a much
// smaller camera-only Schur complement S (6*NC x 6*NC, dense -- eliminating
// points shared by multiple cameras is what couples those cameras).
//
// Hcc/Hpp/grad_c/grad_p are accumulated as small per-camera/per-point blocks
// (matching reference_oca_schur.py's assemble_schur_blocks). Hcp is
// accumulated DIRECTLY into a dense n_c x n_p COLUMN-MAJOR buffer (cuBLAS/
// cuSOLVER's native layout) -- dense-per-pair storage, same scale limitation
// as the numpy Phase-1 reference (a real sparse Hcp is future work for
// BAL-scale problems, noted in README).
__global__ void KernelAssembleSchurBlocks(
    const int* __restrict__ cam_idx, const int* __restrict__ pt_idx, const Scalar* __restrict__ uv,
    const Scalar* __restrict__ R, const Scalar* __restrict__ t, const Scalar* __restrict__ X,
    const Scalar* __restrict__ f, const Scalar* __restrict__ k1, const Scalar* __restrict__ k2,
    int nobs, int ncam, int npt, int n_c,
    Scalar* __restrict__ Hcc, Scalar* __restrict__ Hpp, Scalar* __restrict__ Hcp_full,
    Scalar* __restrict__ grad_c, Scalar* __restrict__ grad_p) {
  int o = blockIdx.x * blockDim.x + threadIdx.x;
  if (o >= nobs) return;
  int c = cam_idx[o], p = pt_idx[o];
  const Scalar* Rc = R + 9 * c;
  const Scalar* Xp = X + 3 * p;
  Scalar Px = Rc[0]*Xp[0]+Rc[1]*Xp[1]+Rc[2]*Xp[2] + t[3*c];
  Scalar Py = Rc[3]*Xp[0]+Rc[4]*Xp[1]+Rc[5]*Xp[2] + t[3*c+1];
  Scalar Pz = Rc[6]*Xp[0]+Rc[7]*Xp[1]+Rc[8]*Xp[2] + t[3*c+2];
  Scalar xp = -Px / Pz, yp = -Py / Pz;
  Scalar r2 = xp*xp + yp*yp;
  Scalar dist = 1.0 + k1[c]*r2 + k2[c]*r2*r2;
  Scalar rx = f[c]*dist*xp - uv[2*o];
  Scalar ry = f[c]*dist*yp - uv[2*o+1];

  Scalar gx[9], gy[9], hx[81], hy[81];
  BalResidualGradHess(Rc[0],Rc[1],Rc[2],Rc[3],Rc[4],Rc[5],Rc[6],Rc[7],Rc[8],
                       t[3*c],t[3*c+1],t[3*c+2],Xp[0],Xp[1],Xp[2],
                       f[c],k1[c],k2[c],uv[2*o],uv[2*o+1], gx,gy,hx,hy);

  Scalar g9[9], H9[81];
#pragma unroll
  for (int i = 0; i < 9; ++i) g9[i] = rx*gx[i] + ry*gy[i];
#pragma unroll
  for (int i = 0; i < 9; ++i)
#pragma unroll
    for (int j = 0; j < 9; ++j) H9[9*i+j] = gx[i]*gx[j] + gy[i]*gy[j] + rx*hx[9*i+j] + ry*hy[9*i+j];

#pragma unroll
  for (int i = 0; i < 6; ++i) atomicAdd(&grad_c[6*c+i], g9[i]);
#pragma unroll
  for (int i = 0; i < 3; ++i) atomicAdd(&grad_p[3*p+i], g9[6+i]);
#pragma unroll
  for (int i = 0; i < 6; ++i)
#pragma unroll
    for (int j = 0; j < 6; ++j) atomicAdd(&Hcc[36*c + 6*i+j], H9[9*i+j]);
#pragma unroll
  for (int i = 0; i < 3; ++i)
#pragma unroll
    for (int j = 0; j < 3; ++j) atomicAdd(&Hpp[9*p + 3*i+j], H9[9*(6+i)+(6+j)]);
#pragma unroll
  for (int i = 0; i < 6; ++i)
#pragma unroll
    for (int j = 0; j < 3; ++j) {
      int row = 6*c+i, col = 3*p+j;
      atomicAdd(&Hcp_full[row + (size_t)col*n_c], H9[9*i + (6+j)]);
    }
}

// H_gn @ v, matrix-free, using the ALREADY-ASSEMBLED sparse Schur-form blocks (Hcc, Hpp,
// obs_Hcp) -- needed for Task P3 (subspace minimization over the OCA-generated basis
// G=[g_0,g_1,...]): forming S_tilde = G^T H_gn G requires H_gn@g_j for each column of G.
// Two-launch split: the cross (camera-point) term is atomic-scattered per observation (each
// observation touches exactly one camera and one point, so both accumulations use atomicAdd);
// the block-diagonal term is a second, non-atomic launch since each camera/point index is
// written by exactly one thread there -- ordering between the two launches on the same
// stream is implicit (sequential), so the diagonal term's plain += is safe to run after the
// cross term's atomic writes have completed.
__global__ void KernelHgnMatVecCross(const Scalar* __restrict__ obs_Hcp, const int* __restrict__ cam_idx,
                                      const int* __restrict__ pt_idx, int nobs,
                                      const Scalar* __restrict__ vc, const Scalar* __restrict__ vp,
                                      Scalar* __restrict__ out_c, Scalar* __restrict__ out_p) {
  int o = blockIdx.x * blockDim.x + threadIdx.x;
  if (o >= nobs) return;
  int c = cam_idx[o], p = pt_idx[o];
  const Scalar* H = obs_Hcp + 18*o;  // 6x3 row-major
  const Scalar* vpp = vp + 3*p;
  const Scalar* vcc = vc + 6*c;
#pragma unroll
  for (int i = 0; i < 6; ++i) {
    Scalar s = 0;
#pragma unroll
    for (int j = 0; j < 3; ++j) s += H[3*i+j]*vpp[j];
    atomicAdd(&out_c[6*c+i], s);
  }
#pragma unroll
  for (int j = 0; j < 3; ++j) {
    Scalar s = 0;
#pragma unroll
    for (int i = 0; i < 6; ++i) s += H[3*i+j]*vcc[i];
    atomicAdd(&out_p[3*p+j], s);
  }
}
__global__ void KernelHgnMatVecDiagCam(const Scalar* __restrict__ Hcc, int ncam,
                                        const Scalar* __restrict__ vc, Scalar* __restrict__ out_c) {
  int c = blockIdx.x * blockDim.x + threadIdx.x;
  if (c >= ncam) return;
  const Scalar* H = Hcc + 36*c; const Scalar* v = vc + 6*c;
#pragma unroll
  for (int a = 0; a < 6; ++a) {
    Scalar s = 0;
#pragma unroll
    for (int b = 0; b < 6; ++b) s += H[6*a+b]*v[b];
    out_c[6*c+a] += s;
  }
}
__global__ void KernelHgnMatVecDiagPt(const Scalar* __restrict__ Hpp, int npt,
                                       const Scalar* __restrict__ vp, Scalar* __restrict__ out_p) {
  int p = blockIdx.x * blockDim.x + threadIdx.x;
  if (p >= npt) return;
  const Scalar* H = Hpp + 9*p; const Scalar* v = vp + 3*p;
#pragma unroll
  for (int a = 0; a < 3; ++a) {
    Scalar s = 0;
#pragma unroll
    for (int b = 0; b < 3; ++b) s += H[3*a+b]*v[b];
    out_p[3*p+a] += s;
  }
}

__global__ void KernelBuildAccFull(const Scalar* __restrict__ Hcc, Scalar lam,
                                    Scalar* __restrict__ Acc_full, int ncam, int n_c) {
  int c = blockIdx.x * blockDim.x + threadIdx.x;
  if (c >= ncam) return;
#pragma unroll
  for (int i = 0; i < 6; ++i)
#pragma unroll
    for (int j = 0; j < 6; ++j) {
      Scalar v = Hcc[36*c + 6*i+j] + (i == j ? lam : 0.0);
      int row = 6*c+i, col = 6*c+j;
      Acc_full[row + (size_t)col*n_c] = v;  // unique per (c,i,j) -- no atomics needed
    }
}

// In-place 3x3 Cholesky of (H+lam*I) then explicit inverse via 3 forward/back
// substitutions (same small-dense-Cholesky style as daba_mm.cu's
// CholeskySolve<N> template). Returns false if not PD -- a legitimate,
// expected outcome (the true Hessian isn't guaranteed PSD), not an error.
__device__ __forceinline__ bool Cholesky3x3Inv(const Scalar H[3][3], Scalar lam, Scalar Inv[3][3]) {
  Scalar A[3][3];
#pragma unroll
  for (int i = 0; i < 3; ++i)
#pragma unroll
    for (int j = 0; j < 3; ++j) A[i][j] = H[i][j] + (i == j ? lam : 0.0);
  Scalar L[3][3] = {{0,0,0},{0,0,0},{0,0,0}};
#pragma unroll
  for (int j = 0; j < 3; ++j) {
    Scalar s = A[j][j];
#pragma unroll
    for (int k = 0; k < j; ++k) s -= L[j][k]*L[j][k];
    if (s <= 1e-300) return false;
    L[j][j] = std::sqrt(s);
#pragma unroll
    for (int i = j+1; i < 3; ++i) {
      Scalar s2 = A[i][j];
#pragma unroll
      for (int k = 0; k < j; ++k) s2 -= L[i][k]*L[j][k];
      L[i][j] = s2 / L[j][j];
    }
  }
#pragma unroll
  for (int col = 0; col < 3; ++col) {
    Scalar b[3] = {col==0?1.0:0.0, col==1?1.0:0.0, col==2?1.0:0.0};
    Scalar y[3];
#pragma unroll
    for (int i = 0; i < 3; ++i) {
      Scalar s = b[i];
#pragma unroll
      for (int k = 0; k < i; ++k) s -= L[i][k]*y[k];
      y[i] = s / L[i][i];
    }
    Scalar xcol[3];
#pragma unroll
    for (int i = 2; i >= 0; --i) {
      Scalar s = y[i];
#pragma unroll
      for (int k = i+1; k < 3; ++k) s -= L[k][i]*xcol[k];
      xcol[i] = s / L[i][i];
    }
#pragma unroll
    for (int i = 0; i < 3; ++i) Inv[i][col] = xcol[i];
  }
  return true;
}

__global__ void KernelInvertAppBlocks(const Scalar* __restrict__ Hpp, Scalar lam,
                                       Scalar* __restrict__ App_inv, int* __restrict__ ok_flags, int npt) {
  int p = blockIdx.x * blockDim.x + threadIdx.x;
  if (p >= npt) return;
  Scalar H[3][3];
#pragma unroll
  for (int i = 0; i < 3; ++i)
#pragma unroll
    for (int j = 0; j < 3; ++j) H[i][j] = Hpp[9*p + 3*i+j];
  Scalar Inv[3][3];
  bool ok = Cholesky3x3Inv(H, lam, Inv);
  ok_flags[p] = ok ? 1 : 0;
  if (ok) {
#pragma unroll
    for (int i = 0; i < 3; ++i)
#pragma unroll
      for (int j = 0; j < 3; ++j) App_inv[9*p + 3*i+j] = Inv[i][j];
  }
}

// ---- Round-2 kernels (BA_Round2_Research_Directions.pdf) ----------------------------
// P.NEW.4: per-point RELATIVE point damping, replacing the grid-searched scalar lam_pt.
// Round 1 empirically found lam_pt driven to the search floor on every dataset; the
// round-2 roundtable's unanimous reading is that this is a VarPro rediscovery (point
// blocks are 3x3, block-diagonal, and generically well-conditioned, so they need only
// enough damping to stay invertible -- not a searched trust-region parameter). Two forms:
//   marquardt=false: H_ii += tau * tr(H)/3     (the doc's explicit relative-floor formula)
//   marquardt=true : H_ii += tau * H_ii        (parameterization-invariant Marquardt form,
//                                               with the tr-based value as a floor so a
//                                               near-zero diagonal still gets damped)
// Either way lam_pt leaves the search entirely -> the lambda grid becomes 1-D.
__global__ void KernelInvertAppBlocksRel(const Scalar* __restrict__ Hpp, Scalar tau, bool marquardt,
                                          Scalar* __restrict__ App_inv, int* __restrict__ ok_flags, int npt) {
  int p = blockIdx.x * blockDim.x + threadIdx.x;
  if (p >= npt) return;
  Scalar H[3][3];
#pragma unroll
  for (int i = 0; i < 3; ++i)
#pragma unroll
    for (int j = 0; j < 3; ++j) H[i][j] = Hpp[9*p + 3*i+j];
  Scalar tr = H[0][0] + H[1][1] + H[2][2];
  Scalar floor_i = tau * tr / 3.0;
  if (!(floor_i > 0.0)) floor_i = 1e-32;  // fully degenerate block (unobserved point)
#pragma unroll
  for (int i = 0; i < 3; ++i) {
    Scalar d = marquardt ? tau * H[i][i] : floor_i;
    if (marquardt && !(d > 1e-3 * floor_i)) d = 1e-3 * floor_i;
    H[i][i] += d;
  }
  Scalar Inv[3][3];
  bool ok = Cholesky3x3Inv(H, 0.0, Inv);   // damping already folded into H
  ok_flags[p] = ok ? 1 : 0;
  if (ok) {
#pragma unroll
    for (int i = 0; i < 3; ++i)
#pragma unroll
      for (int j = 0; j < 3; ++j) App_inv[9*p + 3*i+j] = Inv[i][j];
  }
}

// P.NEW.4 companion: the OCA recursion is g_j = A^-1(b + R g_{j-1}), so the b-side correction
// must use the SAME damping matrix R that was folded into A. With per-point relative damping R
// is blkdiag(D_i) rather than a scalar, so the point-side update is per-coordinate, not a
// single KernelAxpy with one lambda. (Getting this wrong -- using lam_pt=0 on the b side while
// A had per-point damping -- makes the recursion converge to the wrong fixed point; it cost a
// full ablation round before being caught.)
__global__ void KernelAxpyPerPointDamp(Scalar* __restrict__ bp_j, const Scalar* __restrict__ gp_prev,
                                        const Scalar* __restrict__ Hpp, Scalar tau, bool marquardt, int npt) {
  int p = blockIdx.x * blockDim.x + threadIdx.x;
  if (p >= npt) return;
  Scalar tr = Hpp[9*p+0] + Hpp[9*p+4] + Hpp[9*p+8];
  Scalar floor_i = tau * tr / 3.0;
  if (!(floor_i > 0.0)) floor_i = 1e-32;
#pragma unroll
  for (int i = 0; i < 3; ++i) {
    Scalar dmp = marquardt ? tau * Hpp[9*p + 3*i+i] : floor_i;
    if (marquardt && !(dmp > 1e-3 * floor_i)) dmp = 1e-3 * floor_i;
    bp_j[3*p+i] += dmp * gp_prev[3*p+i];
  }
}

// P.NEW.5: Jacobi/diagonal camera damping D=diag(H_cc) instead of scalar lam*I. BA camera
// parameters span orders of magnitude in curvature (focal vs radial vs translation), so
// lam*I is scale-non-invariant; this is the natural per-coordinate continuation of P5's
// 2-group cam/pt split. (Ceres applies Jacobi scaling by default, which is also relevant
// to the LM-GN baseline comparison.) Falls back to the trace-average when a diagonal entry
// is non-positive so a gauge-free direction still receives damping.
__global__ void KernelBuildAccFullJacobi(const Scalar* __restrict__ Hcc, Scalar lam,
                                          Scalar* __restrict__ Acc_full, int ncam, int n_c) {
  int c = blockIdx.x * blockDim.x + threadIdx.x;
  if (c >= ncam) return;
  Scalar tr = 0.0;
#pragma unroll
  for (int i = 0; i < 6; ++i) tr += Hcc[36*c + 6*i+i];
  Scalar avg = tr / 6.0;
  if (!(avg > 0.0)) avg = 1e-32;
#pragma unroll
  for (int i = 0; i < 6; ++i)
#pragma unroll
    for (int j = 0; j < 6; ++j) {
      Scalar v = Hcc[36*c + 6*i+j];
      if (i == j) {
        Scalar dii = Hcc[36*c + 6*i+i];
        v += lam * ((dii > 0.0) ? dii : avg);
      }
      int row = 6*c+i, col = 6*c+j;
      Acc_full[row + (size_t)col*n_c] = v;  // unique per (c,i,j) -- no atomics needed
    }
}

// P5 (round 3): PER-POINT ADAPTIVE damping. Instead of a single global tau (which has a hard
// cliff at ~1e-3 where under-observed 3x3 blocks stop being invertible), cap each block's
// condition number directly:  damp_i = lambda_max(C_i) / kappa_target.
// lambda_max is upper-bounded by the Gershgorin radius (max row sum), which is exact enough for
// a damping heuristic and costs nothing. Well-observed points (large lambda_min) then receive
// far LESS damping than tau=3e-3 would give them, while 1-2-view points still get real damping
// -- which is precisely the structural claim: no single tau can serve both populations.
__device__ __forceinline__ Scalar GershgorinMax3(const Scalar* C) {
  Scalar m = 0.0;
#pragma unroll
  for (int i = 0; i < 3; ++i) {
    Scalar r = C[3*i+i];
#pragma unroll
    for (int j = 0; j < 3; ++j) if (j != i) r += fabs(C[3*i+j]);
    m = fmax(m, r);
  }
  return m;
}

__global__ void KernelInvertAppBlocksAdaptive(const Scalar* __restrict__ Hpp, Scalar kappa,
                                               Scalar* __restrict__ App_inv, int* __restrict__ ok_flags,
                                               Scalar* __restrict__ damp_out, int npt) {
  int p = blockIdx.x * blockDim.x + threadIdx.x;
  if (p >= npt) return;
  Scalar H[3][3];
#pragma unroll
  for (int i = 0; i < 3; ++i)
#pragma unroll
    for (int j = 0; j < 3; ++j) H[i][j] = Hpp[9*p + 3*i+j];
  Scalar lmax = GershgorinMax3(&Hpp[9*p]);
  Scalar d = lmax / kappa;
  if (!(d > 0.0)) d = 1e-32;
  damp_out[p] = d;                       // recursion needs the SAME R on the b-side
#pragma unroll
  for (int i = 0; i < 3; ++i) H[i][i] += d;
  Scalar Inv[3][3];
  bool ok = Cholesky3x3Inv(H, 0.0, Inv);
  ok_flags[p] = ok ? 1 : 0;
  if (ok) {
#pragma unroll
    for (int i = 0; i < 3; ++i)
#pragma unroll
      for (int j = 0; j < 3; ++j) App_inv[9*p + 3*i+j] = Inv[i][j];
  }
}

__global__ void KernelAxpyAdaptiveDampTheta(Scalar* __restrict__ bp_j, const Scalar* __restrict__ gp_prev,
                                             const Scalar* __restrict__ damp, Scalar theta, int npt) {
  int p = blockIdx.x * blockDim.x + threadIdx.x;
  if (p >= npt) return;
  Scalar d = theta * damp[p];
#pragma unroll
  for (int i = 0; i < 3; ++i) bp_j[3*p+i] += d * gp_prev[3*p+i];
}

__global__ void KernelAxpyAdaptiveDamp(Scalar* __restrict__ bp_j, const Scalar* __restrict__ gp_prev,
                                        const Scalar* __restrict__ damp, int npt) {
  int p = blockIdx.x * blockDim.x + threadIdx.x;
  if (p >= npt) return;
  Scalar d = damp[p];
#pragma unroll
  for (int i = 0; i < 3; ++i) bp_j[3*p+i] += d * gp_prev[3*p+i];
}

// Camera-side counterpart of KernelAxpyPerPointDamp, for Jacobi camera damping: R_cam =
// lam*diag(H_cc), so the recursion's b-side correction is lam*diag(H_cc)*g_{j-1,cam}.
__global__ void KernelAxpyPerCamDamp(Scalar* __restrict__ bc_j, const Scalar* __restrict__ gc_prev,
                                      const Scalar* __restrict__ Hcc, Scalar lam, int ncam) {
  int c = blockIdx.x * blockDim.x + threadIdx.x;
  if (c >= ncam) return;
  Scalar tr = 0.0;
#pragma unroll
  for (int i = 0; i < 6; ++i) tr += Hcc[36*c + 6*i+i];
  Scalar avg = tr / 6.0;
  if (!(avg > 0.0)) avg = 1e-32;
#pragma unroll
  for (int i = 0; i < 6; ++i) {
    Scalar dii = Hcc[36*c + 6*i+i];
    bc_j[6*c+i] += lam * ((dii > 0.0) ? dii : avg) * gc_prev[6*c+i];
  }
}

// P.NEW.3 support: extract the n_c camera-Hessian diagonal so the host can form a RELATIVE
// damping floor (eps_rel * max_i H_ii) instead of round 1's absolute lam0*1e-8. Using the
// undamped H_cc (not S(lambda)) keeps the floor lambda-independent, so it can be computed
// once per outer iteration rather than per candidate.
__global__ void KernelExtractDiagHcc(const Scalar* __restrict__ Hcc, int ncam,
                                      Scalar* __restrict__ diag_out) {
  int idx = blockIdx.x * blockDim.x + threadIdx.x;
  if (idx >= 6*ncam) return;
  int c = idx / 6, i = idx % 6;
  diag_out[idx] = Hcc[36*c + 6*i + i];
}

__global__ void KernelBuildAppInvFull(const Scalar* __restrict__ App_inv,
                                       Scalar* __restrict__ App_inv_full, int npt, int n_p) {
  int p = blockIdx.x * blockDim.x + threadIdx.x;
  if (p >= npt) return;
#pragma unroll
  for (int i = 0; i < 3; ++i)
#pragma unroll
    for (int j = 0; j < 3; ++j) {
      int row = 3*p+i, col = 3*p+j;
      App_inv_full[row + (size_t)col*n_p] = App_inv[9*p + 3*i+j];
    }
}

// ============================================================== Sparse per-point Schur (Phase 4b)
// Fixes the actual scale blocker: KernelAssembleSchurBlocks/schur_factorize
// above store Hcp and App_inv as DENSE (n_c x n_p)/(n_p x n_p) buffers, which
// scale with POINT count -- fine at toy scale (NP=20) but ~295GB for
// App_inv_full alone at venice-52's NP=64053. The reduced camera-only system
// S was never the problem (n_c scales with CAMERA count, always modest).
// Fix: each point is observed by only a handful of cameras (venice-52
// averages ~5.4 observations/point, max degree 46 -- bounded by NC, no
// pathological outliers), so accumulate each point's contribution directly
// into the small S/bc_corr via a CSR-style point->observation index, never
// materializing anything point-count-sized beyond the O(NP) App_inv blocks.
// Exact same math as the dense path (verified in reference_oca_schur_sparse.py
// against reference_oca_schur.py, bit-for-precision on the toy problem) --
// this is a storage/parallelization change, not a different algorithm.

// Writes this observation's raw 6x3 camera-point Hessian cross-block to its
// own unique slot in a per-observation buffer (nobs,6,3 row-major) -- unlike
// the dense path's Hcp_full, no atomics needed here (each observation owns
// exactly one slot), and nothing here scales with NP x NC.
template <class HT>
__global__ void KernelAssembleSchurSparse(
    const int* __restrict__ cam_idx, const int* __restrict__ pt_idx, const Scalar* __restrict__ uv,
    const Scalar* __restrict__ R, const Scalar* __restrict__ t, const Scalar* __restrict__ X,
    const Scalar* __restrict__ f, const Scalar* __restrict__ k1, const Scalar* __restrict__ k2,
    int nobs,
    Scalar* __restrict__ Hcc, Scalar* __restrict__ Hpp, HT* __restrict__ obs_Hcp,
    Scalar* __restrict__ grad_c, Scalar* __restrict__ grad_p) {
  int o = blockIdx.x * blockDim.x + threadIdx.x;
  if (o >= nobs) return;
  int c = cam_idx[o], p = pt_idx[o];
  const Scalar* Rc = R + 9 * c;
  const Scalar* Xp = X + 3 * p;
  Scalar Px = Rc[0]*Xp[0]+Rc[1]*Xp[1]+Rc[2]*Xp[2] + t[3*c];
  Scalar Py = Rc[3]*Xp[0]+Rc[4]*Xp[1]+Rc[5]*Xp[2] + t[3*c+1];
  Scalar Pz = Rc[6]*Xp[0]+Rc[7]*Xp[1]+Rc[8]*Xp[2] + t[3*c+2];
  Scalar xp = -Px / Pz, yp = -Py / Pz;
  Scalar r2 = xp*xp + yp*yp;
  Scalar dist = 1.0 + k1[c]*r2 + k2[c]*r2*r2;
  Scalar rx = f[c]*dist*xp - uv[2*o];
  Scalar ry = f[c]*dist*yp - uv[2*o+1];
  Scalar gx[9], gy[9], hx[81], hy[81];
  BalResidualGradHess(Rc[0],Rc[1],Rc[2],Rc[3],Rc[4],Rc[5],Rc[6],Rc[7],Rc[8],
                       t[3*c],t[3*c+1],t[3*c+2],Xp[0],Xp[1],Xp[2],
                       f[c],k1[c],k2[c],uv[2*o],uv[2*o+1], gx,gy,hx,hy);
  Scalar g9[9], H9[81];
#pragma unroll
  for (int i = 0; i < 9; ++i) g9[i] = rx*gx[i] + ry*gy[i];
#pragma unroll
  for (int i = 0; i < 9; ++i)
#pragma unroll
    for (int j = 0; j < 9; ++j) H9[9*i+j] = gx[i]*gx[j] + gy[i]*gy[j] + rx*hx[9*i+j] + ry*hy[9*i+j];
#pragma unroll
  for (int i = 0; i < 6; ++i) atomicAdd(&grad_c[6*c+i], g9[i]);
#pragma unroll
  for (int i = 0; i < 3; ++i) atomicAdd(&grad_p[3*p+i], g9[6+i]);
#pragma unroll
  for (int i = 0; i < 6; ++i)
#pragma unroll
    for (int j = 0; j < 6; ++j) atomicAdd(&Hcc[36*c + 6*i+j], H9[9*i+j]);
#pragma unroll
  for (int i = 0; i < 3; ++i)
#pragma unroll
    for (int j = 0; j < 3; ++j) atomicAdd(&Hpp[9*p + 3*i+j], H9[9*(6+i)+(6+j)]);
#pragma unroll
  for (int i = 0; i < 6; ++i)
#pragma unroll
    for (int j = 0; j < 3; ++j) obs_Hcp[18*o + 3*i+j] = (HT)H9[9*i + (6+j)];
}

// Forms S -= sum over points of (per-point D_p x D_p pairwise block updates)
// -- one thread per point, gathering that point's actual observing cameras
// via the CSR index (point_obs_offsets/point_obs_list), bounded work per
// thread (D_p <= NC, no pathological degree). Must run AFTER S's diagonal
// has been set by KernelBuildAccFull on the SAME stream (relies on in-order
// kernel execution, no explicit sync needed) -- every entry here is an
// atomicAdd since multiple points sharing a camera pair all contribute to
// the same S block.
template <class HT>
__global__ void KernelFormSSparse(
    const HT* __restrict__ obs_Hcp, const int* __restrict__ cam_idx,
    const int* __restrict__ point_obs_offsets, const int* __restrict__ point_obs_list,
    const Scalar* __restrict__ App_inv, int npt, int n_c, Scalar* __restrict__ S) {
  int p = blockIdx.x * blockDim.x + threadIdx.x;
  if (p >= npt) return;
  int start = point_obs_offsets[p], end = point_obs_offsets[p+1];
  int D = end - start;
  if (D == 0) return;
  const Scalar* Ainv = App_inv + 9*p;
  for (int di = 0; di < D; ++di) {
    int od = point_obs_list[start+di];
    int cd = cam_idx[od];
    const HT* Hd = obs_Hcp + 18*od;  // 6x3 row-major
    Scalar Td[18];  // Td = Hd @ Ainv (6x3)
    for (int i = 0; i < 6; ++i)
      for (int l = 0; l < 3; ++l) {
        Scalar s = 0;
        for (int k = 0; k < 3; ++k) s += Hd[3*i+k]*Ainv[3*k+l];
        Td[3*i+l] = s;
      }
    for (int ei = 0; ei < D; ++ei) {
      int oe = point_obs_list[start+ei];
      int ce = cam_idx[oe];
      const HT* He = obs_Hcp + 18*oe;  // 6x3
      for (int i = 0; i < 6; ++i)
        for (int j = 0; j < 6; ++j) {
          Scalar s = 0;
          for (int l = 0; l < 3; ++l) s += Td[3*i+l]*He[3*j+l];
          int row = 6*cd+i, col = 6*ce+j;
          atomicAdd(&S[row + (size_t)col*n_c], -s);
        }
    }
  }
}

// ============================================================== Round-4 Q1: atomic-free Schur formation via the persistent
// edge-CSR. Splits KernelFormSSparse's work into two disjoint parts:
//   - DIAGONAL (d==e, i.e. a point's contribution to its own camera's block): O(N_obs) work,
//     one block per point per camera pair with itself -- cheap regardless of atomics, left as a
//     lightweight atomic scatter (KernelFormSDiag).
//   - OFF-DIAGONAL (d!=e, camera pairs): this is the O(sum_p D_p^2) term that dominates runtime.
//     Reorganized around the edge-CSR (unique camera pairs -> their shared observation-index
//     pairs, built once at load time): ONE thread block owns each edge exclusively, accumulates
//     over every point that pair co-observes in shared memory, and writes the finished 6x6 block
//     ONCE (and its transpose into the symmetric block) -- zero atomics, deterministic.
template <class HT>
__global__ void KernelFormSDiag(const HT* __restrict__ obs_Hcp, const int* __restrict__ cam_idx,
                                 const int* __restrict__ pt_idx, const Scalar* __restrict__ App_inv,
                                 int nobs, int n_c, Scalar* __restrict__ S) {
  int o = blockIdx.x * blockDim.x + threadIdx.x;
  if (o >= nobs) return;
  int c = cam_idx[o], pt = pt_idx[o];
  const HT* H = obs_Hcp + 18*o;
  const Scalar* Ainv = App_inv + 9*pt;
  Scalar T[18];
  for (int i = 0; i < 6; ++i)
    for (int l = 0; l < 3; ++l) {
      Scalar s = 0;
      for (int k = 0; k < 3; ++k) s += H[3*i+k]*Ainv[3*k+l];
      T[3*i+l] = s;
    }
  for (int i = 0; i < 6; ++i)
    for (int j = 0; j < 6; ++j) {
      Scalar s = 0;
      for (int l = 0; l < 3; ++l) s += T[3*i+l]*H[3*j+l];
      atomicAdd(&S[(6*c+i) + (size_t)(6*c+j)*n_c], -s);
    }
}

// One CTA (36 threads, one per output entry (i,j)) per edge. Loops over the edge's shared
// observation-index pairs, staging each pair's H blocks and the point's App_inv in shared memory
// (288 bytes/pair: 18+18 Hcp doubles + 9 App_inv doubles, padded), accumulates T=Hd@Ainv@He^T in
// per-thread registers across the whole pair list, then writes the finished block twice (once at
// (ci,cj), once transposed at (cj,ci)) -- both writes are plain stores: this edge is the only
// writer of either block, by construction of the edge-CSR.
template <class HT>
__global__ void KernelFormSEdges(const HT* __restrict__ obs_Hcp, const int* __restrict__ pt_idx,
                                  const int* __restrict__ edge_ci, const int* __restrict__ edge_cj,
                                  const int* __restrict__ edge_offsets, const int* __restrict__ edge_obs_d,
                                  const int* __restrict__ edge_obs_e, const Scalar* __restrict__ App_inv,
                                  int n_edges, int n_c, Scalar* __restrict__ S) {
  int e = blockIdx.x;
  if (e >= n_edges) return;
  int tid = threadIdx.x;              // 0..35
  int i = tid / 6, j = tid % 6;
  __shared__ Scalar Hd[18], He[18], Vinv[9], Td[18];
  int start = edge_offsets[e], end = edge_offsets[e+1];
  Scalar acc = 0.0;
  for (int k = start; k < end; ++k) {
    int od = edge_obs_d[k], oe = edge_obs_e[k];
    if (tid < 18) Hd[tid] = obs_Hcp[18*od + tid];
    else if (tid < 36) He[tid-18] = obs_Hcp[18*oe + (tid-18)];
    if (tid < 9) Vinv[tid] = App_inv[9*pt_idx[od] + tid];
    __syncthreads();
    if (tid < 18) {                   // Td = Hd @ Vinv (6x3), computed once, shared by all 6 j's
      int ii = tid/3, l = tid%3;
      Scalar s = 0;
      for (int kk = 0; kk < 3; ++kk) s += Hd[3*ii+kk]*Vinv[3*kk+l];
      Td[3*ii+l] = s;
    }
    __syncthreads();
    Scalar s = 0;
    for (int l = 0; l < 3; ++l) s += Td[3*i+l]*He[3*j+l];
    acc += s;
    __syncthreads();                  // before next pair overwrites shared Hd/He/Vinv/Td
  }
  int ci = edge_ci[e], cj = edge_cj[e];
  S[(6*ci+i) + (size_t)(6*cj+j)*n_c] = -acc;
  S[(6*cj+j) + (size_t)(6*ci+i)*n_c] = -acc;
}

// RHS-dependent correction (must be recomputed each inner-recursion step,
// since bp changes every step): bc_corr[c] += sum over this point's
// observations of Hcp[d] @ (App_inv[p] @ bp[p]).
template <class HT>
__global__ void KernelRHSCorrectionSparse(
    const HT* __restrict__ obs_Hcp, const int* __restrict__ cam_idx,
    const int* __restrict__ point_obs_offsets, const int* __restrict__ point_obs_list,
    const Scalar* __restrict__ App_inv, const Scalar* __restrict__ bp, int npt,
    Scalar* __restrict__ bc_corr) {
  int p = blockIdx.x * blockDim.x + threadIdx.x;
  if (p >= npt) return;
  int start = point_obs_offsets[p], end = point_obs_offsets[p+1];
  int D = end - start;
  if (D == 0) return;
  const Scalar* Ainv = App_inv + 9*p;
  Scalar bpp[3] = {bp[3*p], bp[3*p+1], bp[3*p+2]};
  Scalar bp_prime[3];
  for (int l = 0; l < 3; ++l) { Scalar s=0; for (int k=0;k<3;++k) s+=Ainv[3*l+k]*bpp[k]; bp_prime[l]=s; }
  for (int di = 0; di < D; ++di) {
    int od = point_obs_list[start+di];
    int cd = cam_idx[od];
    const HT* Hd = obs_Hcp + 18*od;
    for (int i = 0; i < 6; ++i) {
      Scalar s = 0;
      for (int l = 0; l < 3; ++l) s += Hd[3*i+l]*bp_prime[l];
      atomicAdd(&bc_corr[6*cd+i], s);
    }
  }
}

// Local back-substitution for this point's own step -- no atomics (each
// point writes only its own xp slice), needs the now-globally-known xc.
template <class HT>
__global__ void KernelBackSubstituteSparse(
    const HT* __restrict__ obs_Hcp, const int* __restrict__ cam_idx,
    const int* __restrict__ point_obs_offsets, const int* __restrict__ point_obs_list,
    const Scalar* __restrict__ App_inv, const Scalar* __restrict__ bp, const Scalar* __restrict__ xc,
    int npt, Scalar* __restrict__ xp) {
  int p = blockIdx.x * blockDim.x + threadIdx.x;
  if (p >= npt) return;
  int start = point_obs_offsets[p], end = point_obs_offsets[p+1];
  int D = end - start;
  const Scalar* Ainv = App_inv + 9*p;
  Scalar corr[3] = {0, 0, 0};
  for (int di = 0; di < D; ++di) {
    int od = point_obs_list[start+di];
    int cd = cam_idx[od];
    const HT* Hd = obs_Hcp + 18*od;
    const Scalar* xcd = xc + 6*cd;
    for (int l = 0; l < 3; ++l) {
      Scalar s = 0;
      for (int i = 0; i < 6; ++i) s += Hd[3*i+l]*xcd[i];
      corr[l] += s;
    }
  }
  Scalar rhs[3] = {bp[3*p]-corr[0], bp[3*p+1]-corr[1], bp[3*p+2]-corr[2]};
  for (int l = 0; l < 3; ++l) {
    Scalar s = 0; for (int k = 0; k < 3; ++k) s += Ainv[3*l+k]*rhs[k];
    xp[3*p+l] = s;
  }
}

// ============================================================================
// ROUND 9: matrix-free multi-shift Krylov linear core   (--algo mfree_shifted_cg)
// K = H_cc - H_cp V^-1 H_cp^T is NEVER formed and never factorised.  The whole
// lambda grid is solved from ONE Krylov space via the shifted-CG scalar
// recurrences, so the extra shifts cost zero matvecs.
// Validated against the explicit path at 6e-15 relative (gate G0).
// ============================================================================
// ROUND 10: camera-block dimension CD templated. CD=6 is the round-9 solver
// bit-for-bit (pose only); CD=9 appends [df,dk1,dk2] to the camera block using
// the FD-validated 12-parameter gradient (bal_grad12_generated.cuh). k2mask
// multiplies the dk2 column: 0.0 holds k2 fixed EXACTLY (gradient and all
// Gauss-Newton products in that coordinate are identically zero, so CG never
// moves it), matching Caspar's SIMPLE_RADIAL merged f+k1 block; 1.0 frees it.
template <int CD, class HT>
__global__ void MFAssemble(const int* __restrict__ ci,const int* __restrict__ pi,const Scalar* __restrict__ uv,
    const Scalar* __restrict__ R,const Scalar* __restrict__ t,const Scalar* __restrict__ X,
    const Scalar* __restrict__ f,const Scalar* __restrict__ k1,const Scalar* __restrict__ k2,
    const int* __restrict__ o2p,const int* __restrict__ o2c,int nobs,
    Scalar* __restrict__ Hcc,Scalar* __restrict__ Cdiag,HT* __restrict__ Gp,HT* __restrict__ Gc,
    HT* __restrict__ Bo,Scalar* __restrict__ bc,Scalar* __restrict__ bp,Scalar k2mask=1.0,
    Scalar* __restrict__ r2acc=nullptr,Scalar* __restrict__ obscnt=nullptr,
    int rk=0,Scalar rk_a2=0.0){
  int o=blockIdx.x*blockDim.x+threadIdx.x; if(o>=nobs)return;
  int c=ci[o],p=pi[o];
  const Scalar* Rc=R+9*c; const Scalar* Xp=X+3*p;
  Scalar Px=Rc[0]*Xp[0]+Rc[1]*Xp[1]+Rc[2]*Xp[2]+t[3*c];
  Scalar Py=Rc[3]*Xp[0]+Rc[4]*Xp[1]+Rc[5]*Xp[2]+t[3*c+1];
  Scalar Pz=Rc[6]*Xp[0]+Rc[7]*Xp[1]+Rc[8]*Xp[2]+t[3*c+2];
  Scalar xq=-Px/Pz,yq=-Py/Pz,r2=xq*xq+yq*yq;
  Scalar dist=1.0+k1[c]*r2+k2[c]*r2*r2;
  Scalar rx=f[c]*dist*xq-uv[2*o], ry=f[c]*dist*yq-uv[2*o+1];
  Scalar gx[CD+3],gy[CD+3];
  if constexpr (CD == 6) {
    Scalar hx[81],hy[81];
    BalResidualGradHess(Rc[0],Rc[1],Rc[2],Rc[3],Rc[4],Rc[5],Rc[6],Rc[7],Rc[8],
        t[3*c],t[3*c+1],t[3*c+2],Xp[0],Xp[1],Xp[2],f[c],k1[c],k2[c],uv[2*o],uv[2*o+1],gx,gy,hx,hy);
  } else {
    Scalar r0x,r0y;
    BalResidualGrad12(Rc[0],Rc[1],Rc[2],Rc[3],Rc[4],Rc[5],Rc[6],Rc[7],Rc[8],
        t[3*c],t[3*c+1],t[3*c+2],Xp[0],Xp[1],Xp[2],f[c],k1[c],k2[c],uv[2*o],uv[2*o+1],gx,gy,&r0x,&r0y);
    gx[8]*=k2mask; gy[8]*=k2mask;
    if(r2acc){ atomicAdd(&r2acc[c],r2); atomicAdd(&obscnt[c],(Scalar)1.0); }
  }
  // IRLS: sqrt-weight the residual AND the Jacobian rows, exactly as the CPU
  // port does (and after r2acc, which accumulates the geometric radius and is
  // independent of the weighting). Everything downstream -- Hcc, b, the point
  // block, the fragments -- is then the weighted GN system.
  if(rk){
    const Scalar sw = sqrt(OcaRobustW(rk, rk_a2, rx*rx + ry*ry));
    rx *= sw; ry *= sw;
    for(int i=0;i<CD+3;++i){ gx[i] *= sw; gy[i] *= sw; }
  }
  for(int i=0;i<CD;++i) atomicAdd(&bc[CD*c+i], rx*gx[i]+ry*gy[i]);
  for(int i=0;i<3;++i) atomicAdd(&bp[3*p+i], rx*gx[CD+i]+ry*gy[CD+i]);
  for(int i=0;i<CD;++i) for(int j=0;j<CD;++j) atomicAdd(&Hcc[CD*CD*c+CD*i+j], gx[i]*gx[j]+gy[i]*gy[j]);
  for(int i=0;i<3;++i) atomicAdd(&Cdiag[3*p+i], gx[CD+i]*gx[CD+i]+gy[CD+i]*gy[CD+i]);
  int kp=o2p[o], kc=o2c[o];
  for(int i=0;i<CD;++i) for(int j=0;j<3;++j){
    Scalar g=gx[i]*gx[CD+j]+gy[i]*gy[CD+j];
    Gp[(size_t)(3*i+j)*nobs+kp]=(HT)g;
    Gc[(size_t)(3*i+j)*nobs+kc]=(HT)g; }
  for(int j=0;j<3;++j){ Bo[6*o+j]=(HT)gx[CD+j]; Bo[6*o+3+j]=(HT)gy[CD+j]; }
}
__device__ __forceinline__ void MFGivens(Scalar* Rp, Scalar* v){
  const int ix[3][3]={{0,1,2},{-1,3,4},{-1,-1,5}};
  for(int j=0;j<3;++j){
    Scalar vj=v[j]; if(vj==0.0) continue;
    Scalar rjj=Rp[ix[j][j]];
    Scalar rr=hypot(rjj,vj); if(rr==0.0) continue;
    Scalar cs=rjj/rr, sn=vj/rr; Rp[ix[j][j]]=rr;
    for(int k=j+1;k<3;++k){ Scalar t1=Rp[ix[j][k]],t2=v[k];
      Rp[ix[j][k]]=cs*t1+sn*t2; v[k]=-sn*t1+cs*t2; }
    v[j]=0.0; }
}
// s2.4 augmented QR:  [B_p ; D_p^{1/2}] = Q R,  V = R^T R exactly, kappa(R)=kappa(V)^{1/2}
template <class HT>
__global__ void MFPointFactor(const HT* __restrict__ Bo,const Scalar* __restrict__ Cdiag,
    const int* __restrict__ poff,const int* __restrict__ plist,Scalar tau,int npt,
    Scalar* __restrict__ Rf,int* __restrict__ ok){
  int p=blockIdx.x*blockDim.x+threadIdx.x; if(p>=npt)return;
  Scalar cd[3]={Cdiag[3*p],Cdiag[3*p+1],Cdiag[3*p+2]};
  Scalar tr=cd[0]+cd[1]+cd[2], fl=tau*tr/3.0; if(!(fl>0.0)) fl=1e-32;
  Scalar Rp[6]={0,0,0,0,0,0};
  int s=poff[p],e=poff[p+1];
  for(int k=s;k<e;++k){ int o=plist[k];
    Scalar v0[3]={(Scalar)Bo[6*o],(Scalar)Bo[6*o+1],(Scalar)Bo[6*o+2]};   MFGivens(Rp,v0);
    Scalar v1[3]={(Scalar)Bo[6*o+3],(Scalar)Bo[6*o+4],(Scalar)Bo[6*o+5]}; MFGivens(Rp,v1); }
  for(int i=0;i<3;++i){ Scalar q=tau*cd[i]; if(!(q>1e-3*fl)) q=1e-3*fl;
    Scalar v[3]={0,0,0}; v[i]=sqrt(q); MFGivens(Rp,v); }
  ok[p]=((Rp[0]>0.0)&&(Rp[3]>0.0)&&(Rp[5]>0.0))?1:0;
  for(int i=0;i<6;++i) Rf[6*p+i]=Rp[i];
}
// GAP-4090 F5 (2026-09-03): tau-SPLIT point factor. The O(nobs) Givens sweep
// above is tau-independent -- tau enters only the 3 trailing augmentation
// rows. Since R from Givens QR is invariant to the row order actually used
// here (obs rows first, tau rows last, same as the fused kernel), caching the
// post-obs R (6 doubles/pt) once per ASSEMBLY and replaying only the tau rows
// per ATTEMPT is bit-identical to MFPointFactor while cutting the per-retry
// cost from a full fragment stream to a 6-double/pt pass. Default ON
// (OCA_TAU_SPLIT=0 restores the fused kernel).
template <class HT>
__global__ void MFPointFactorObs(const HT* __restrict__ Bo,
    const int* __restrict__ poff,const int* __restrict__ plist,int npt,
    Scalar* __restrict__ R0f){
  int p=blockIdx.x*blockDim.x+threadIdx.x; if(p>=npt)return;
  Scalar Rp[6]={0,0,0,0,0,0};
  int s=poff[p],e=poff[p+1];
  for(int k=s;k<e;++k){ int o=plist[k];
    Scalar v0[3]={(Scalar)Bo[6*o],(Scalar)Bo[6*o+1],(Scalar)Bo[6*o+2]};   MFGivens(Rp,v0);
    Scalar v1[3]={(Scalar)Bo[6*o+3],(Scalar)Bo[6*o+4],(Scalar)Bo[6*o+5]}; MFGivens(Rp,v1); }
  for(int i=0;i<6;++i) R0f[6*p+i]=Rp[i];
}
// PER-POINT DAMPING (2026-09-05). The uniform floor tau>=c*lam is right for
// thin, badly-conditioned tracks (near-parallel rays: a step along the ray
// bisector is a near-null direction of the cost, so an undamped point half
// flings the point to infinity while the TRUE COST BARELY MOVES -- which is
// exactly why no menu widening, deeper CG or better scorer can ever see it)
// and wrong for well-conditioned tracks, whose free relaxation is what gives
// the asymmetric solver its large win on final-4585. The conflict is global
// only because the knob is global, so: apply the floor per point.
// `poff` gives each point's observation count for free (CSR offsets already
// built for the factor sweep). maxobs<=0 => floor everyone (legacy).
// GEOMETRIC GATE (2026-09-06). Observation COUNT is the wrong statistic: a
// 2-view point at 30 degrees is fine, a 5-view point on a straight vehicle
// track at 0.5 degrees is a flight risk. What matters is the CONDITIONING of
// V_p, i.e. how nearly parallel the rays are. The tau-split factor already
// computes R0f = qr(B_p) WITHOUT any damping, so the undamped point block's
// conditioning is free: V_p = R0f^T R0f, and the diagonal of the triangular
// factor gives cond(V_p)^(1/2) ~ max|r_ii| / min|r_ii|. Gate the floor on
// (min/max) < condthr instead of on the track length. R0f layout is the same
// packed upper triangle the solve uses: [r00, r01, r02, r11, r12, r22].
__global__ void MFPointFactorTauSel(const Scalar* __restrict__ Cdiag,
    const Scalar* __restrict__ R0f,const int* __restrict__ poff,
    Scalar tau_base,Scalar tau_floor,int maxobs,Scalar condthr,int npt,
    Scalar* __restrict__ Rf,int* __restrict__ ok){
  int p=blockIdx.x*blockDim.x+threadIdx.x; if(p>=npt)return;
  bool weak;
  if(condthr>0.0){
    const Scalar a=fabs(R0f[6*p+0]), b=fabs(R0f[6*p+3]), c=fabs(R0f[6*p+5]);
    const Scalar mn=fmin(a,fmin(b,c)), mx=fmax(a,fmax(b,c));
    weak = !(mn > condthr*mx);       // ill-conditioned (or degenerate) point
  } else {
    const int nobs_p = poff[p+1]-poff[p];
    weak = (maxobs<=0 || nobs_p<=maxobs);
  }
  const Scalar tau = weak ? tau_floor : tau_base;
  Scalar cd[3]={Cdiag[3*p],Cdiag[3*p+1],Cdiag[3*p+2]};
  Scalar tr=cd[0]+cd[1]+cd[2], fl=tau*tr/3.0; if(!(fl>0.0)) fl=1e-32;
  Scalar Rp[6]; for(int i=0;i<6;++i) Rp[i]=R0f[6*p+i];
  for(int i=0;i<3;++i){ Scalar q=tau*cd[i]; if(!(q>1e-3*fl)) q=1e-3*fl;
    Scalar v[3]={0,0,0}; v[i]=sqrt(q); MFGivens(Rp,v); }
  ok[p]=((Rp[0]>0.0)&&(Rp[3]>0.0)&&(Rp[5]>0.0))?1:0;
  for(int i=0;i<6;++i) Rf[6*p+i]=Rp[i];
}
__global__ void MFPointFactorTau(const Scalar* __restrict__ Cdiag,
    const Scalar* __restrict__ R0f,Scalar tau,int npt,
    Scalar* __restrict__ Rf,int* __restrict__ ok){
  int p=blockIdx.x*blockDim.x+threadIdx.x; if(p>=npt)return;
  Scalar cd[3]={Cdiag[3*p],Cdiag[3*p+1],Cdiag[3*p+2]};
  Scalar tr=cd[0]+cd[1]+cd[2], fl=tau*tr/3.0; if(!(fl>0.0)) fl=1e-32;
  Scalar Rp[6]; for(int i=0;i<6;++i) Rp[i]=R0f[6*p+i];
  for(int i=0;i<3;++i){ Scalar q=tau*cd[i]; if(!(q>1e-3*fl)) q=1e-3*fl;
    Scalar v[3]={0,0,0}; v[i]=sqrt(q); MFGivens(Rp,v); }
  ok[p]=((Rp[0]>0.0)&&(Rp[3]>0.0)&&(Rp[5]>0.0))?1:0;
  for(int i=0;i<6;++i) Rf[6*p+i]=Rp[i];
}
__device__ __forceinline__ void MFVinv(const Scalar* Rp,const Scalar* tv,Scalar* u){
  Scalar y0=tv[0]/Rp[0];
  Scalar y1=(tv[1]-Rp[1]*y0)/Rp[3];
  Scalar y2=(tv[2]-Rp[2]*y0-Rp[4]*y1)/Rp[5];
  u[2]=y2/Rp[5]; u[1]=(y1-Rp[4]*u[2])/Rp[3]; u[0]=(y0-Rp[1]*u[1]-Rp[2]*u[2])/Rp[0];
}
template <int CD, class HT>
__global__ void MFPass1(const HT* __restrict__ Gp,const int* __restrict__ scam,
    const int* __restrict__ spt,const Scalar* __restrict__ v,int nobs,Scalar* __restrict__ tacc){
  int k=blockIdx.x*blockDim.x+threadIdx.x; if(k>=nobs)return;
  int p=spt[k]; const Scalar* vc=v+CD*scam[k];
  for(int j=0;j<3;++j){ Scalar q=0;
    for(int i=0;i<CD;++i) q+=Gp[(size_t)(3*i+j)*nobs+k]*vc[i];
    atomicAdd(&tacc[3*p+j],q); }
}
// GAP-4090 F2 (2026-09-03): MULTI-RHS Pass1. At a scoring checkpoint the menu
// evaluates up to L candidates, each paying a full Gp stream (27 doubles/obs)
// -- the dominant bandwidth of the candidate phase (45% of storm wall).
// Reading the fragment ONCE and applying it to all candidates cuts the menu's
// Gp traffic by ~L. Per-candidate arithmetic is identical to MFPass1 (same
// products, same per-obs atomicAdd); only atomic arrival order changes, the
// same nondeterminism class every scoring pass already has.
template <int CD, class HT>
__global__ void MFPass1Multi(const HT* __restrict__ Gp,const int* __restrict__ scam,
    const int* __restrict__ spt,const Scalar* __restrict__ XCU,int n_cf,int nl,
    int nobs,Scalar* __restrict__ TACC,int n_p){
  int k=blockIdx.x*blockDim.x+threadIdx.x; if(k>=nobs)return;
  int p=spt[k]; int cbase=CD*scam[k];
  Scalar g[3*CD];
  for(int t=0;t<3*CD;++t) g[t]=(Scalar)Gp[(size_t)t*nobs+k];
  for(int l=0;l<nl;++l){
    const Scalar* vc=XCU+(size_t)l*n_cf+cbase;
    for(int j=0;j<3;++j){ Scalar q=0;
      for(int i=0;i<CD;++i) q+=g[3*i+j]*vc[i];
      atomicAdd(&TACC[(size_t)l*n_p+3*p+j],q); }
  }
}
template <int CD, class HT>
__global__ void MFPass1Stride(const HT* __restrict__ Gp,const int* __restrict__ scam,
    const int* __restrict__ spt,const Scalar* __restrict__ v,int nobs,int stride,Scalar* __restrict__ tacc){
  // POINT-level subset: include ALL observations of points with p%stride==0.
  // Obs-level striding is fundamentally wrong here: the backsub map
  // xp = Vinv(bp - W^T xc) is exact per point, and a point's W^T xc sampled at
  // 1-in-S of its handful of observations has O(1) per-point error that no
  // scaling fixes (measured: venice diverged to 1.2e8 under a scaled obs
  // stride). With the point subset, subset points get EXACT steps and the
  // subset cost (same filter, below) is an unbiased 1/S sample of the
  // objective. The big Gp streams are only read by active threads, so the
  // bandwidth saving is ~1/S even though the launch covers all nobs.
  int k=blockIdx.x*blockDim.x+threadIdx.x; if(k>=nobs)return;
  int p=spt[k]; if(p%stride) return;
  const Scalar* vc=v+CD*scam[k];
  for(int j=0;j<3;++j){ Scalar q=0;
    for(int i=0;i<CD;++i) q+=Gp[(size_t)(3*i+j)*nobs+k]*vc[i];
    atomicAdd(&tacc[3*p+j],q); }
}
// ============================================================================
// OCA_JIT_J=1 (tier-1 Caspar-codegen adaptation): ON-THE-FLY JACOBIANS.
// The stored fragments Gp/Gc hold W = A^T B per observation (3*CD doubles) and
// re-reading them is the bandwidth floor of every matvec and scoring pass
// (7+GB per matvec at 16.7M obs fp64). Caspar's core advantage is that it
// never stores J -- generated kernels recompute it from state inside every
// product, turning a bandwidth-bound op into a compute-bound one. These
// kernels do the same for OUR two-block Schur matvec: recompute gx,gy via the
// FD-validated BalResidualGrad12 (CSE'd, ~200 flops) and apply
// W^T v = B^T(A v) / W u = A^T(B u) without ever forming W. Reads per obs:
// state gathers only (cam 9+3+3, point 3, uv 2) instead of 27 stored doubles.
// Exact same math as the stored path modulo product associativity (rounding).
// CD=9 only (CD=6 uses a different generated grad). Default off, bit-compat.
template <int CD>
__global__ void MFPass1JIT(const int* __restrict__ ci,const int* __restrict__ pi,
    const Scalar* __restrict__ uv,const Scalar* __restrict__ R,const Scalar* __restrict__ t,
    const Scalar* __restrict__ X,const Scalar* __restrict__ f,const Scalar* __restrict__ k1,
    const Scalar* __restrict__ k2,const Scalar* __restrict__ v,int nobs,Scalar k2mask,
    int rk,Scalar rk_a2,Scalar* __restrict__ tacc){
  static_assert(CD==9,"JIT path is dof9-only");
  int o=blockIdx.x*blockDim.x+threadIdx.x; if(o>=nobs)return;
  int c=ci[o],p=pi[o];
  const Scalar* Rc=R+9*c; const Scalar* Xp=X+3*p;
  Scalar gx[12],gy[12],r0x,r0y;
  BalResidualGrad12(Rc[0],Rc[1],Rc[2],Rc[3],Rc[4],Rc[5],Rc[6],Rc[7],Rc[8],
      t[3*c],t[3*c+1],t[3*c+2],Xp[0],Xp[1],Xp[2],f[c],k1[c],k2[c],uv[2*o],uv[2*o+1],gx,gy,&r0x,&r0y);
  gx[8]*=k2mask; gy[8]*=k2mask;
  if(rk){
    const Scalar sw=sqrt(OcaRobustW(rk,rk_a2,r0x*r0x+r0y*r0y));
    for(int i=0;i<12;++i){ gx[i]*=sw; gy[i]*=sw; }
  }
  const Scalar* vc=v+CD*c;
  Scalar ax=0,ay=0;
  for(int i=0;i<CD;++i){ ax+=gx[i]*vc[i]; ay+=gy[i]*vc[i]; }
  for(int j=0;j<3;++j) atomicAdd(&tacc[3*p+j], gx[CD+j]*ax+gy[CD+j]*ay);
}
template <int CD>
__global__ void MFHccMulJIT(const Scalar* __restrict__ Hcc,const Scalar* __restrict__ v,int ncam,Scalar* __restrict__ w){
  int c=blockIdx.x*blockDim.x+threadIdx.x; if(c>=ncam)return;
  const Scalar* H=Hcc+(size_t)CD*CD*c; const Scalar* vc=v+CD*c;
  for(int i=0;i<CD;++i){ Scalar q=0;
    for(int j=0;j<CD;++j) q+=H[CD*i+j]*vc[j];
    w[CD*c+i]=q; }
}
template <int CD>
__global__ void MFPass2JIT(const int* __restrict__ ci,const int* __restrict__ pi,
    const Scalar* __restrict__ uv,const Scalar* __restrict__ R,const Scalar* __restrict__ t,
    const Scalar* __restrict__ X,const Scalar* __restrict__ f,const Scalar* __restrict__ k1,
    const Scalar* __restrict__ k2,const Scalar* __restrict__ u,int nobs,Scalar k2mask,
    int rk,Scalar rk_a2,Scalar* __restrict__ wout){
  static_assert(CD==9,"JIT path is dof9-only");
  int o=blockIdx.x*blockDim.x+threadIdx.x; if(o>=nobs)return;
  int c=ci[o],p=pi[o];
  const Scalar* Rc=R+9*c; const Scalar* Xp=X+3*p;
  Scalar gx[12],gy[12],r0x,r0y;
  BalResidualGrad12(Rc[0],Rc[1],Rc[2],Rc[3],Rc[4],Rc[5],Rc[6],Rc[7],Rc[8],
      t[3*c],t[3*c+1],t[3*c+2],Xp[0],Xp[1],Xp[2],f[c],k1[c],k2[c],uv[2*o],uv[2*o+1],gx,gy,&r0x,&r0y);
  gx[8]*=k2mask; gy[8]*=k2mask;
  if(rk){
    const Scalar sw=sqrt(OcaRobustW(rk,rk_a2,r0x*r0x+r0y*r0y));
    for(int i=0;i<12;++i){ gx[i]*=sw; gy[i]*=sw; }
  }
  const Scalar* up=u+3*p;
  Scalar bx=0,by=0;
  for(int j=0;j<3;++j){ bx+=gx[CD+j]*up[j]; by+=gy[CD+j]*up[j]; }
  for(int i=0;i<CD;++i) atomicAdd(&wout[CD*c+i], -(gx[i]*bx+gy[i]*by));
}
__global__ void MFVinvApply(const Scalar* __restrict__ Rf,const Scalar* __restrict__ tacc,int npt,Scalar* __restrict__ u){
  int p=blockIdx.x*blockDim.x+threadIdx.x; if(p>=npt)return;
  const Scalar* Rp=Rf+6*p;
  if(!(Rp[0]>0.0&&Rp[3]>0.0&&Rp[5]>0.0)){ u[3*p]=u[3*p+1]=u[3*p+2]=0.0; return; }
  Scalar tv[3]={tacc[3*p],tacc[3*p+1],tacc[3*p+2]},uu[3]; MFVinv(Rp,tv,uu);
  u[3*p]=uu[0];u[3*p+1]=uu[1];u[3*p+2]=uu[2];
}
template <int CD, class HT>
__global__ void MFPass2(const HT* __restrict__ Gc,const int* __restrict__ cspt,
    const int* __restrict__ coff,const Scalar* __restrict__ u,const Scalar* __restrict__ Hcc,
    const Scalar* __restrict__ v,int nobs,Scalar* __restrict__ w){
  int c=blockIdx.x; int s=coff[c],e=coff[c+1];
  Scalar acc[CD];
  for(int i=0;i<CD;++i) acc[i]=0;
  for(int k=s+threadIdx.x;k<e;k+=blockDim.x){
    int p=cspt[k]; Scalar up[3]={u[3*p],u[3*p+1],u[3*p+2]};
    for(int i=0;i<CD;++i){ Scalar q=0;
      for(int j=0;j<3;++j) q+=Gc[(size_t)(3*i+j)*nobs+k]*up[j];
      acc[i]+=q; } }
  __shared__ Scalar sh[CD][256];
  for(int i=0;i<CD;++i) sh[i][threadIdx.x]=acc[i];
  __syncthreads();
  for(int st=128;st>0;st>>=1){ if(threadIdx.x<st) for(int i=0;i<CD;++i) sh[i][threadIdx.x]+=sh[i][threadIdx.x+st]; __syncthreads(); }
  if(threadIdx.x==0) for(int i=0;i<CD;++i){
    Scalar q=0; for(int j=0;j<CD;++j) q+=Hcc[CD*CD*c+CD*i+j]*v[CD*c+j];
    w[CD*c+i]=q-sh[i][0]; }
}
__global__ void MFBackSub(const Scalar* __restrict__ Rf,const Scalar* __restrict__ bp,
    const Scalar* __restrict__ tacc,int npt,Scalar* __restrict__ xp){
  int p=blockIdx.x*blockDim.x+threadIdx.x; if(p>=npt)return;
  const Scalar* Rp=Rf+6*p;
  if(!(Rp[0]>0.0&&Rp[3]>0.0&&Rp[5]>0.0)){ xp[3*p]=xp[3*p+1]=xp[3*p+2]=0.0; return; }
  Scalar rhs[3]={bp[3*p]-tacc[3*p],bp[3*p+1]-tacc[3*p+1],bp[3*p+2]-tacc[3*p+2]},uu[3];
  MFVinv(Rp,rhs,uu); xp[3*p]=uu[0];xp[3*p+1]=uu[1];xp[3*p+2]=uu[2];
}
template <int CD, class HT>
__global__ void MFRhsPrime(const HT* __restrict__ Gp,const int* __restrict__ scam,
    const int* __restrict__ spt,const Scalar* __restrict__ ub,int nobs,Scalar* __restrict__ corr){
  int k=blockIdx.x*blockDim.x+threadIdx.x; if(k>=nobs)return;
  int p=spt[k],c=scam[k]; Scalar up[3]={ub[3*p],ub[3*p+1],ub[3*p+2]};
  for(int i=0;i<CD;++i){ Scalar q=0;
    for(int j=0;j<3;++j) q+=Gp[(size_t)(3*i+j)*nobs+k]*up[j];
    atomicAdd(&corr[CD*c+i],q); }
}
template <int CD, class HT>
__global__ void MFDiagK(const HT* __restrict__ Gp,const int* __restrict__ spt,
    const int* __restrict__ scam,const Scalar* __restrict__ Rf,int nobs,Scalar* __restrict__ dk){
  int k=blockIdx.x*blockDim.x+threadIdx.x; if(k>=nobs)return;
  int p=spt[k],c=scam[k]; const Scalar* Rp=Rf+6*p;
  if(!(Rp[0]>0.0&&Rp[3]>0.0&&Rp[5]>0.0)) return;
  for(int i=0;i<CD;++i){
    Scalar g[3]={Gp[(size_t)(3*i+0)*nobs+k],Gp[(size_t)(3*i+1)*nobs+k],Gp[(size_t)(3*i+2)*nobs+k]},uu[3];
    MFVinv(Rp,g,uu);
    atomicAdd(&dk[CD*c+i], -(g[0]*uu[0]+g[1]*uu[1]+g[2]*uu[2])); }
}
template <int CD>
__global__ void MFDiagHcc(const Scalar* __restrict__ Hcc,int ncam,Scalar* __restrict__ dk){
  int c=blockIdx.x*blockDim.x+threadIdx.x; if(c>=ncam)return;
  for(int i=0;i<CD;++i) dk[CD*c+i]+=Hcc[CD*CD*c+CD*i+i];
}
// ===== REVIEW: block-congruence scaling (OCA_BLOCKEQ=1) ======================
// Jacobi equilibration scales S by a DIAGONAL D (D S D + sigma I). The same
// congruence works with the per-camera CDxCD diagonal BLOCK of the Schur
// complement: S_c = Hcc_c - sum_obs W Vinv W^T, factor S_c = L L^T, solve
// L^-1 S L^-T + sigma I. The shift still enters as sigma*I in the transformed
// space, so multi-shift CG and the zeta recurrence are UNCHANGED -- unlike a
// general preconditioner M, which turns the shift into sigma*M^-1 and destroys
// the shared Krylov space. Measured in the CPU prototype: 68-93% fewer
// matvecs, 1.1-2.6x less wall, better final on 4 of 6 datasets.
template <int CD, typename HT>
__global__ void MFBlockSchur(const HT* __restrict__ Gp,const int* __restrict__ spt,
    const int* __restrict__ scam,const Scalar* __restrict__ Rf,int nobs,
    Scalar* __restrict__ Bk){
  int k=blockIdx.x*blockDim.x+threadIdx.x; if(k>=nobs)return;
  int p=spt[k],c=scam[k]; const Scalar* Rp=Rf+6*p;
  if(!(Rp[0]>0.0&&Rp[3]>0.0&&Rp[5]>0.0)) return;
  Scalar W[CD*3], U[CD*3];
  for(int i=0;i<CD;++i){
    W[3*i+0]=Gp[(size_t)(3*i+0)*nobs+k];
    W[3*i+1]=Gp[(size_t)(3*i+1)*nobs+k];
    W[3*i+2]=Gp[(size_t)(3*i+2)*nobs+k];
    MFVinv(Rp,&W[3*i],&U[3*i]);
  }
  for(int i=0;i<CD;++i)
    for(int j=0;j<CD;++j)
      atomicAdd(&Bk[(size_t)CD*CD*c+CD*i+j],
                -(W[3*i+0]*U[3*j+0]+W[3*i+1]*U[3*j+1]+W[3*i+2]*U[3*j+2]));
}
// CAMERA-MAJOR Schur block build -- same result as MFBlockSchur but with NO
// atomics.  One warp per camera walks that camera's own observation run via the
// existing CSR (coff/cspt, the MFPass2 pattern), accumulates in registers, and
// reduces down a fixed shuffle tree, so the summation order is identical on
// every launch.  The atomicAdd version is run-to-run nondeterministic (81 float
// adds per observation arriving in arbitrary order); on ladybug-1723 that
// variance reaches 15% at L=5 and 698% at L=1, while the diagonal path is
// bit-identical across repeats -- the suspected cause of that dataset's
// long-standing block-preconditioner failure.
// Only the lower triangle is accumulated (S_c is symmetric and MFBlockChol
// symmetrises anyway), halving both registers and work.
template <int CD, typename HT>
__global__ void MFBlockSchurCM(const HT* __restrict__ Gc,const int* __restrict__ cspt,
    const int* __restrict__ coff,const Scalar* __restrict__ Rf,int nobs,
    Scalar* __restrict__ Bk){
  const int c=blockIdx.x; const int s=coff[c],e=coff[c+1];
  constexpr int NT=(CD*(CD+1))/2;
  Scalar acc[NT];
  for(int t=0;t<NT;++t) acc[t]=0.0;
  for(int k=s+threadIdx.x;k<e;k+=warpSize){
    int p=cspt[k]; const Scalar* Rp=Rf+6*p;
    if(!(Rp[0]>0.0&&Rp[3]>0.0&&Rp[5]>0.0)) continue;
    Scalar W[CD*3],U[CD*3];
    for(int i=0;i<CD;++i){
      W[3*i+0]=Gc[(size_t)(3*i+0)*nobs+k];
      W[3*i+1]=Gc[(size_t)(3*i+1)*nobs+k];
      W[3*i+2]=Gc[(size_t)(3*i+2)*nobs+k];
      MFVinv(Rp,&W[3*i],&U[3*i]);
    }
    int t=0;
    for(int i=0;i<CD;++i) for(int j=0;j<=i;++j,++t)
      acc[t]-=(W[3*i+0]*U[3*j+0]+W[3*i+1]*U[3*j+1]+W[3*i+2]*U[3*j+2]);
  }
  __shared__ Scalar red[NT];
  for(int t=0;t<NT;++t){
    Scalar v=acc[t];
    for(int off=16;off>0;off>>=1) v+=__shfl_down_sync(0xffffffffu,v,off);
    if(threadIdx.x==0) red[t]=v;
  }
  __syncthreads();
  if(threadIdx.x==0){
    int t=0;
    for(int i=0;i<CD;++i) for(int j=0;j<=i;++j,++t){
      Bk[(size_t)CD*CD*c+CD*i+j]+=red[t];
      if(i!=j) Bk[(size_t)CD*CD*c+CD*j+i]+=red[t];
    }
  }
}
template <int CD>
__global__ void MFBlockAddHcc(const Scalar* __restrict__ Hcc,int ncam,Scalar* __restrict__ Bk){
  int c=blockIdx.x*blockDim.x+threadIdx.x; if(c>=ncam)return;
  for(int i=0;i<CD*CD;++i) Bk[(size_t)CD*CD*c+i]+=Hcc[(size_t)CD*CD*c+i];
}
// ---- SHARED-INTRINSICS reduced space -------------------------------------
// The CG works in [6*ncam poses | 3*ncalib calibration] = B^T S B, so the
// per-camera 9x9 blocks cannot be used directly. Split them instead:
//   pose block  (6x6, one per camera)  = top-left 6x6 of the 9x9
//   calib block (3x3, one per GROUP)   = sum of the bottom-right 3x3 over the
//                                        cameras in that group
// This is the exact block-diagonal of B^T S B EXCEPT for cross-camera terms
// c != c' within a group (cameras sharing points). Those are dropped -- a
// block-diagonal preconditioner is an approximation regardless -- so the
// calibration block is a lower bound on the true group curvature.
// Pose-calibration cross terms are likewise off-block and dropped.
template <int CD>
__global__ void MFBlockRedSplit(const Scalar* __restrict__ Bk,
    const int* __restrict__ calib_of_cam,int ncam,
    Scalar* __restrict__ Bp,Scalar* __restrict__ Bg){
  int c=blockIdx.x*blockDim.x+threadIdx.x; if(c>=ncam)return;
  const Scalar* B=Bk+(size_t)CD*CD*c;
  for(int i=0;i<6;++i)
    for(int j=0;j<6;++j) Bp[(size_t)36*c+6*i+j]=B[CD*i+j];
  const int g=calib_of_cam[c];
  for(int i=0;i<3;++i)
    for(int j=0;j<3;++j)
      atomicAdd(&Bg[(size_t)9*g+3*i+j],B[CD*(6+i)+(6+j)]);
}
// Cholesky of each block, in place: lower triangle of Bk becomes L.
// Degrades to diagonal scaling if the block is not positive definite.
// OCA_RI_OPEN helper: Levenberg damping of a per-camera block diagonal
// (B_ii *= 1+lam, with an absolute floor so an all-zero block stays SPD).
template <int CD>
__global__ void MFBlockDampDiag(Scalar* __restrict__ Bk,int ncam,Scalar lam){
  int c=blockIdx.x*blockDim.x+threadIdx.x; if(c>=ncam)return;
  Scalar* B=Bk+(size_t)CD*CD*c;
  for(int i=0;i<CD;++i){
    Scalar d=B[CD*i+i];
    B[CD*i+i]=d*((Scalar)1.0+lam)+lam*(Scalar)1e-12;
  }
}
template <int CD>
__global__ void MFBlockChol(Scalar* __restrict__ Bk,int ncam,Scalar eps,
                            int* __restrict__ nfail=nullptr){
  int c=blockIdx.x*blockDim.x+threadIdx.x; if(c>=ncam)return;
  Scalar* B=Bk+(size_t)CD*CD*c;
  Scalar mx=0.0;
  for(int i=0;i<CD;++i){ Scalar d=fabs(B[CD*i+i]); if(d>mx)mx=d; }
  const Scalar fl=fmax(mx*eps,(Scalar)1e-30);
  for(int i=0;i<CD;++i) if(!(B[CD*i+i]>fl)) B[CD*i+i]=fl;
  bool ok=true;
  Scalar L[CD*CD];
  for(int i=0;i<CD*CD;++i) L[i]=0.0;
  for(int i=0;i<CD&&ok;++i)
    for(int j=0;j<=i;++j){
      Scalar sum=(Scalar)0.5*(B[CD*i+j]+B[CD*j+i]);
      for(int k=0;k<j;++k) sum-=L[CD*i+k]*L[CD*j+k];
      if(i==j){ if(!(sum>0.0)){ ok=false; break; } L[CD*i+j]=sqrt(sum); }
      else      L[CD*i+j]=sum/L[CD*j+j];
    }
  if(!ok){ if(nfail) atomicAdd(nfail,1);
           for(int i=0;i<CD*CD;++i) L[i]=0.0;
           for(int i=0;i<CD;++i) L[CD*i+i]=sqrt(fmax(B[CD*i+i],fl)); }
  for(int i=0;i<CD*CD;++i) B[i]=L[i];
}
// y = L^-1 x  (mode 0)   /   y = L^-T x  (mode 1), per camera
template <int CD>
__global__ void MFBlockSolve(const Scalar* __restrict__ Bk,const Scalar* __restrict__ x,
                             int ncam,int mode,Scalar* __restrict__ y){
  int c=blockIdx.x*blockDim.x+threadIdx.x; if(c>=ncam)return;
  const Scalar* L=Bk+(size_t)CD*CD*c;
  const Scalar* xc=x+CD*c; Scalar* yc=y+CD*c;
  if(mode==0){
    for(int i=0;i<CD;++i){ Scalar s=xc[i];
      for(int k=0;k<i;++k) s-=L[CD*i+k]*yc[k];
      yc[i]=s/L[CD*i+i]; }
  } else {
    for(int i=CD-1;i>=0;--i){ Scalar s=xc[i];
      for(int k=i+1;k<CD;++k) s-=L[CD*k+i]*yc[k];
      yc[i]=s/L[CD*i+i]; }
  }
}
__global__ void MFMakeEquil(const Scalar* dk,int n,Scalar* E){
  int i=blockIdx.x*blockDim.x+threadIdx.x; if(i>=n)return;
  Scalar d=dk[i]; E[i]=(d>0.0)?1.0/sqrt(d):1.0;
}
// ROUND 10: absolute per-coordinate damping for the intrinsics columns of the
// 9-DOF camera block. The equilibration+shift scheme implements RELATIVE
// (Marquardt) damping, which by construction cannot regularize a near-null
// direction -- and the intrinsics columns HAVE near-null directions (a camera
// whose observations cluster near the image centre has H_k1k1 ~ Sum(f r^2 x)^2
// ~ 0; final-4585's f spans 325..1.5e10, and an unregularized run drove one
// camera's k1 from ~1e-6 to 9.8e11, permanently poisoning the state). This
// adds 1/sigma^2 curvature per intrinsic coordinate, calibrated to physical
// scales: sigma_f = f/2 (a half-focal move costs one whitened residual),
// sigma_k1 = 1/rbar2 and sigma_k2 = 1/rbar2^2 (the coefficient change that
// alters the distortion factor by O(1) at the camera's own characteristic
// radius rbar2 = mean r^2 over its observations). Where the data constrains
// the coordinate at all, the real curvature dominates and this is negligible;
// where it does not, the step is bounded to a physically meaningful size.
__global__ void KernelDampIntr9(Scalar* __restrict__ Hcc,const Scalar* __restrict__ f,
    const Scalar* __restrict__ r2acc,const Scalar* __restrict__ obscnt,int ncam,
    Scalar w,Scalar k2mask){
  int c=blockIdx.x*blockDim.x+threadIdx.x; if(c>=ncam)return;
  Scalar cnt=obscnt[c]; if(!(cnt>0.0))return;
  Scalar rbar2=r2acc[c]/cnt; if(!(rbar2>1e-12)) rbar2=1e-12;
  Scalar sf=0.5*fabs(f[c])+1e-3;
  Hcc[81*c+9*6+6]+=w/(sf*sf);
  Hcc[81*c+9*7+7]+=w*rbar2*rbar2;
  if(k2mask>0.0) Hcc[81*c+9*8+8]+=w*rbar2*rbar2*rbar2*rbar2;
}

// ROUND 10: per-camera-block RELATIVE floor on the equilibrated diagonal.
// The 9-DOF camera block can contain near-null curvature directions (a camera
// whose observations cluster near the image centre has d(r)/d(k1) ~ r^2 ~ 0),
// and the unfloored 1/sqrt(d) then assigns that coordinate an astronomically
// large scale: measured on final-4585 --dof9, accepted steps with |x_c|~3e11
// that fling k1/f to absurd values, after which every later candidate is
// rejected (the point-relaxation component V^-1 b_p alone evaluates 7x worse
// than the current cost) and lambda ratchets into permanent null steps.
// Flooring d at eps * max(d) WITHIN the camera's own block keeps the
// non-dimensionalization scale-invariant while bounding the amplification of
// near-null coordinates, whose damping is then dominated by the CG shift.
template <int CD>
__global__ void MFMakeEquilBlocked(const Scalar* dk,int ncam,Scalar eps,Scalar* E){
  int c=blockIdx.x*blockDim.x+threadIdx.x; if(c>=ncam)return;
  Scalar dmax=0.0;
  for(int i=0;i<CD;++i){ Scalar d=dk[CD*c+i]; if(d>dmax)dmax=d; }
  Scalar fl=eps*dmax;
  for(int i=0;i<CD;++i){ Scalar d=dk[CD*c+i]; if(d<fl)d=fl;
    E[CD*c+i]=(d>0.0)?1.0/sqrt(d):1.0; }
}
// ---- ROUND 11: shared intrinsics as a linear constraint -------------------
// COLMAP shares one camera across many images, but the solver's camera block
// carries one intrinsics triple PER POSE. Rather than re-index every kernel,
// impose the sharing as a linear constraint and solve in the reduced space.
//
// Let B : R^(6*ncam + 3*ncalib) -> R^(9*ncam) copy each group's intrinsics out
// to every pose in it (MFCalibBroadcast). The constrained Gauss-Newton system
// is exactly (B^T S B) y = B^T b, so every existing kernel is reused unchanged:
// a matvec becomes broadcast -> S -> reduce, where reduce is B^T
// (MFCalibReduce). The step in the full space is B y, so poses sharing a
// calibration receive IDENTICAL intrinsics updates and can never drift apart.
//
// The preconditioner stays diagonal: B^T diag(S) B sums each group's entries.
// That misses cross-camera terms within a group, but those live in the Schur
// complement, which is never formed -- the unshared path already approximates
// the diagonal the same way, so sharing costs no extra accuracy here.
__global__ void MFCalibBroadcast(const Scalar* __restrict__ vr,
    const int* __restrict__ calib_of_cam,int ncam,int ncalib,
    Scalar* __restrict__ vfull){
  int c=blockIdx.x*blockDim.x+threadIdx.x; if(c>=ncam)return;
  const Scalar* pose=vr+6*c;
  const Scalar* cal =vr+6*ncam+3*calib_of_cam[c];
  Scalar* out=vfull+9*c;
  for(int i=0;i<6;++i) out[i]=pose[i];
  for(int j=0;j<3;++j) out[6+j]=cal[j];
}
// B^T. Poses map one-to-one; intrinsics ACCUMULATE over the group, so the
// calibration section must be zeroed by the caller before launching.
__global__ void MFCalibReduce(const Scalar* __restrict__ vfull,
    const int* __restrict__ calib_of_cam,int ncam,int ncalib,
    Scalar* __restrict__ vr){
  int c=blockIdx.x*blockDim.x+threadIdx.x; if(c>=ncam)return;
  const Scalar* in=vfull+9*c;
  for(int i=0;i<6;++i) vr[6*c+i]=in[i];
  Scalar* cal=vr+6*ncam+3*calib_of_cam[c];
  for(int j=0;j<3;++j) atomicAdd(&cal[j],in[6+j]);
}
__global__ void MFScaleVec(Scalar* v,const Scalar* s,int n){int i=blockIdx.x*blockDim.x+threadIdx.x;if(i<n)v[i]*=s[i];}
__global__ void MFNeg(Scalar* v,int n){int i=blockIdx.x*blockDim.x+threadIdx.x;if(i<n)v[i]=-v[i];}
__global__ void MFAlphaScale(Scalar* __restrict__ out,const Scalar* __restrict__ src,Scalar ac,Scalar ap,int n_c,int n){
  int i=blockIdx.x*blockDim.x+threadIdx.x; if(i>=n)return;
  out[i]=src[i]*((i<n_c)?ac:ap);
}

// ============================================================== DABA-style decoupled OCA (Phase 5)
// Tests whether OCA's growing recursion still converges well when grafted onto
// a DABA-style (Fan et al., RSS 2023; see daba_cuda/reference_mm.py's
// accumulate_grad_hess+solve_retract) block-diagonal Hessian approximation:
// the camera-point cross term is dropped entirely (never computed, not
// Schur-eliminated), each camera's 6x6 block and each point's 3x3 block
// inflated by a majorization factor and solved completely independently. No
// coupled linear solve anywhere -- this is what makes DABA's own solve step
// embarrassingly parallel/communication-free (stronger than the Schur
// version, which still needs one small coupled solve per outer iteration).
// See reference_oca_daba_style.py for the numpy validation: with no
// compensating factor this doesn't just converge slower, it converges to the
// WRONG answer; with DABA's own majorization factor (2.0) it reaches the same
// optimum but needs ~15-20x more iterations than the coupled version on the
// toy problem -- this file extends that same empirical comparison to
// venice-52 scale.
__device__ __forceinline__ bool Cholesky6x6Inv(const Scalar H[6][6], Scalar lam, Scalar factor, Scalar Inv[6][6]) {
  Scalar A[6][6];
#pragma unroll
  for (int i = 0; i < 6; ++i)
#pragma unroll
    for (int j = 0; j < 6; ++j) A[i][j] = factor*H[i][j] + (i == j ? lam : 0.0);
  Scalar L[6][6];
#pragma unroll
  for (int i = 0; i < 6; ++i)
#pragma unroll
    for (int j = 0; j < 6; ++j) L[i][j] = 0;
#pragma unroll
  for (int j = 0; j < 6; ++j) {
    Scalar s = A[j][j];
#pragma unroll
    for (int k = 0; k < j; ++k) s -= L[j][k]*L[j][k];
    if (s <= 1e-300) return false;
    L[j][j] = std::sqrt(s);
#pragma unroll
    for (int i = j+1; i < 6; ++i) {
      Scalar s2 = A[i][j];
#pragma unroll
      for (int k = 0; k < j; ++k) s2 -= L[i][k]*L[j][k];
      L[i][j] = s2 / L[j][j];
    }
  }
#pragma unroll
  for (int col = 0; col < 6; ++col) {
    Scalar b[6];
#pragma unroll
    for (int i = 0; i < 6; ++i) b[i] = (i == col) ? 1.0 : 0.0;
    Scalar y[6];
#pragma unroll
    for (int i = 0; i < 6; ++i) {
      Scalar s = b[i];
#pragma unroll
      for (int k = 0; k < i; ++k) s -= L[i][k]*y[k];
      y[i] = s / L[i][i];
    }
    Scalar xcol[6];
#pragma unroll
    for (int i = 5; i >= 0; --i) {
      Scalar s = y[i];
#pragma unroll
      for (int k = i+1; k < 6; ++k) s -= L[k][i]*xcol[k];
      xcol[i] = s / L[i][i];
    }
#pragma unroll
    for (int i = 0; i < 6; ++i) Inv[i][col] = xcol[i];
  }
  return true;
}

__global__ void KernelInvertCamBlocks(const Scalar* __restrict__ Hcc, Scalar lam, Scalar factor,
                                       Scalar* __restrict__ Hcc_inv, int* __restrict__ ok_flags, int ncam) {
  int c = blockIdx.x * blockDim.x + threadIdx.x;
  if (c >= ncam) return;
  Scalar H[6][6];
#pragma unroll
  for (int i = 0; i < 6; ++i)
#pragma unroll
    for (int j = 0; j < 6; ++j) H[i][j] = Hcc[36*c + 6*i+j];
  Scalar Inv[6][6];
  bool ok = Cholesky6x6Inv(H, lam, factor, Inv);
  ok_flags[c] = ok ? 1 : 0;
  if (ok) {
#pragma unroll
    for (int i = 0; i < 6; ++i)
#pragma unroll
      for (int j = 0; j < 6; ++j) Hcc_inv[36*c + 6*i+j] = Inv[i][j];
  }
}

// Folds `factor` into H before calling Cholesky3x3Inv (which itself adds
// lam*I) -- matches factor*H + lam*I, same convention as KernelInvertCamBlocks.
__global__ void KernelInvertPtBlocksFactored(const Scalar* __restrict__ Hpp, Scalar lam, Scalar factor,
                                              Scalar* __restrict__ Hpp_inv, int* __restrict__ ok_flags, int npt) {
  int p = blockIdx.x * blockDim.x + threadIdx.x;
  if (p >= npt) return;
  Scalar H[3][3];
#pragma unroll
  for (int i = 0; i < 3; ++i)
#pragma unroll
    for (int j = 0; j < 3; ++j) H[i][j] = factor * Hpp[9*p + 3*i+j];
  Scalar Inv[3][3];
  bool ok = Cholesky3x3Inv(H, lam, Inv);
  ok_flags[p] = ok ? 1 : 0;
  if (ok) {
#pragma unroll
    for (int i = 0; i < 3; ++i)
#pragma unroll
      for (int j = 0; j < 3; ++j) Hpp_inv[9*p + 3*i+j] = Inv[i][j];
  }
}

// out[k] = Inv[k] @ (grad[k] + lam*prev[k]) (prev==nullptr for j=0: out[k]=Inv[k]@grad[k]).
// Safe to call with out==prev for in-place recursion: each thread only reads
// and writes its own block's indices, no cross-thread dependency.
__global__ void KernelBlockApply6(const Scalar* __restrict__ Inv, const Scalar* __restrict__ grad,
                                   const Scalar* __restrict__ prev, Scalar lam, int K, Scalar* __restrict__ out) {
  int k = blockIdx.x * blockDim.x + threadIdx.x;
  if (k >= K) return;
  Scalar rhs[6];
#pragma unroll
  for (int i = 0; i < 6; ++i) rhs[i] = grad[6*k+i] + (prev ? lam*prev[6*k+i] : 0.0);
  const Scalar* Ik = Inv + 36*k;
  Scalar outk[6];
#pragma unroll
  for (int i = 0; i < 6; ++i) {
    Scalar s = 0;
#pragma unroll
    for (int j = 0; j < 6; ++j) s += Ik[6*i+j]*rhs[j];
    outk[i] = s;
  }
#pragma unroll
  for (int i = 0; i < 6; ++i) out[6*k+i] = outk[i];
}
__global__ void KernelBlockApply3(const Scalar* __restrict__ Inv, const Scalar* __restrict__ grad,
                                   const Scalar* __restrict__ prev, Scalar lam, int K, Scalar* __restrict__ out) {
  int k = blockIdx.x * blockDim.x + threadIdx.x;
  if (k >= K) return;
  Scalar rhs[3];
#pragma unroll
  for (int i = 0; i < 3; ++i) rhs[i] = grad[3*k+i] + (prev ? lam*prev[3*k+i] : 0.0);
  const Scalar* Ik = Inv + 9*k;
  Scalar outk[3];
#pragma unroll
  for (int i = 0; i < 3; ++i) {
    Scalar s = 0;
#pragma unroll
    for (int j = 0; j < 3; ++j) s += Ik[3*i+j]*rhs[j];
    outk[i] = s;
  }
#pragma unroll
  for (int i = 0; i < 3; ++i) out[3*k+i] = outk[i];
}

// ============================================================== DABA-style multi-lambda OCA (Phase 6)
// Replaces the fixed-lambda decoupled OCA's hand-tuned global lambda (which
// needed per-dataset trial and error, e.g. venice-1778 needing 1e11) with
// DABA's own per-block multi-lambda adaptive regularization (Fan et al. RSS
// 2023's solve_retract_multilambda, ported from reference_mm.py -- see
// reference_oca_daba_multilambda.py for the full numpy derivation/rationale).
// Each camera/point tries a small grid of candidate lambda multipliers
// (cheap: one more tiny 6x6/3x3 solve each), keeps whichever gives the best
// TRUE local cost, and freezes (doesn't move) if even the best candidate
// doesn't improve -- provably non-increasing total cost, no global lambda
// tuning required. OCA's growing recursion (g_1..g_k) then runs using each
// block's SELECTED lambda, with a second true-cost accept/reject on the
// step actually applied (g_k), not just the g_0 proxy used for selection.

// Per-camera: solve (factor*Hcc[c]+lam*I)^-1 @ (-grad_c[c]) for n_lambda
// candidate lam values (logspace grid around base_lam_cam[c]). A PD failure
// for a given candidate defaults to a zero step (harmless: it can only lose
// the argmin to a real candidate, or -- if all candidates fail/are bad --
// get caught by the accept/reject gate downstream, same as a legitimately
// bad candidate).
__global__ void KernelCamCandidateSolve(
    const Scalar* __restrict__ Hcc, const Scalar* __restrict__ grad_c, const Scalar* __restrict__ base_lam_cam,
    Scalar factor, const Scalar* __restrict__ lam_mult, int n_lambda, int ncam,
    Scalar* __restrict__ dC, Scalar* __restrict__ lam_grid) {
  int c = blockIdx.x * blockDim.x + threadIdx.x;
  if (c >= ncam) return;
  Scalar H[6][6];
#pragma unroll
  for (int i = 0; i < 6; ++i)
#pragma unroll
    for (int j = 0; j < 6; ++j) H[i][j] = Hcc[36*c + 6*i+j];
  Scalar g[6];
#pragma unroll
  for (int i = 0; i < 6; ++i) g[i] = grad_c[6*c+i];
  for (int n = 0; n < n_lambda; ++n) {
    Scalar lam = base_lam_cam[c] * lam_mult[n];
    lam_grid[c*n_lambda+n] = lam;
    Scalar Inv[6][6];
    bool ok = Cholesky6x6Inv(H, lam, factor, Inv);
    Scalar* out = dC + (size_t)(c*n_lambda+n)*6;
    if (!ok) { for (int i = 0; i < 6; ++i) out[i] = 0.0; continue; }
#pragma unroll
    for (int i = 0; i < 6; ++i) {
      Scalar s = 0;
#pragma unroll
      for (int j = 0; j < 6; ++j) s -= Inv[i][j]*g[j];
      out[i] = s;
    }
  }
}
__global__ void KernelPtCandidateSolve(
    const Scalar* __restrict__ Hpp, const Scalar* __restrict__ grad_p, const Scalar* __restrict__ base_lam_pt,
    Scalar factor, const Scalar* __restrict__ lam_mult, int n_lambda, int npt,
    Scalar* __restrict__ dX, Scalar* __restrict__ lam_grid) {
  int p = blockIdx.x * blockDim.x + threadIdx.x;
  if (p >= npt) return;
  Scalar H[3][3];
#pragma unroll
  for (int i = 0; i < 3; ++i)
#pragma unroll
    for (int j = 0; j < 3; ++j) H[i][j] = factor * Hpp[9*p + 3*i+j];
  Scalar g[3];
#pragma unroll
  for (int i = 0; i < 3; ++i) g[i] = grad_p[3*p+i];
  for (int n = 0; n < n_lambda; ++n) {
    Scalar lam = base_lam_pt[p] * lam_mult[n];
    lam_grid[p*n_lambda+n] = lam;
    Scalar Inv[3][3];
    bool ok = Cholesky3x3Inv(H, lam, Inv);
    Scalar* out = dX + (size_t)(p*n_lambda+n)*3;
    if (!ok) { for (int i = 0; i < 3; ++i) out[i] = 0.0; continue; }
#pragma unroll
    for (int i = 0; i < 3; ++i) {
      Scalar s = 0;
#pragma unroll
      for (int j = 0; j < 3; ++j) s -= Inv[i][j]*g[j];
      out[i] = s;
    }
  }
}

// True (non-linearized) candidate cost, one thread per observation, looping
// n_lambda candidates internally -- points held fixed for camera candidates
// and vice versa (matches DABA's own linearization-point assumption, see
// reference_mm.py). Also used for the SINGLE final-step evaluation (n_lambda=1).
__global__ void KernelCamCandidateCost(
    const int* __restrict__ cam_idx, const int* __restrict__ pt_idx, const Scalar* __restrict__ uv,
    const Scalar* __restrict__ R, const Scalar* __restrict__ t, const Scalar* __restrict__ X,
    const Scalar* __restrict__ f, const Scalar* __restrict__ k1, const Scalar* __restrict__ k2,
    const Scalar* __restrict__ dC, int n_lambda, int nobs, Scalar* __restrict__ cam_cost_cand) {
  int o = blockIdx.x * blockDim.x + threadIdx.x;
  if (o >= nobs) return;
  int c = cam_idx[o], p = pt_idx[o];
  const Scalar* Xp = X + 3*p;
  for (int n = 0; n < n_lambda; ++n) {
    const Scalar* dCcn = dC + (size_t)(c*n_lambda+n)*6;
    Scalar dR[9]; ExpSO3(dCcn, dR);
    Scalar Rc[9]; Mat3Mul(dR, R+9*c, Rc);
    Scalar tc0 = t[3*c]+dCcn[3], tc1 = t[3*c+1]+dCcn[4], tc2 = t[3*c+2]+dCcn[5];
    Scalar Px = Rc[0]*Xp[0]+Rc[1]*Xp[1]+Rc[2]*Xp[2]+tc0;
    Scalar Py = Rc[3]*Xp[0]+Rc[4]*Xp[1]+Rc[5]*Xp[2]+tc1;
    Scalar Pz = Rc[6]*Xp[0]+Rc[7]*Xp[1]+Rc[8]*Xp[2]+tc2;
    Scalar xp = -Px/Pz, yp = -Py/Pz; Scalar r2 = xp*xp+yp*yp;
    Scalar dist = 1.0+k1[c]*r2+k2[c]*r2*r2;
    Scalar rx = f[c]*dist*xp-uv[2*o], ry = f[c]*dist*yp-uv[2*o+1];
    atomicAdd(&cam_cost_cand[c*n_lambda+n], 0.5*(rx*rx+ry*ry));
  }
}
__global__ void KernelPtCandidateCost(
    const int* __restrict__ cam_idx, const int* __restrict__ pt_idx, const Scalar* __restrict__ uv,
    const Scalar* __restrict__ R, const Scalar* __restrict__ t, const Scalar* __restrict__ X,
    const Scalar* __restrict__ f, const Scalar* __restrict__ k1, const Scalar* __restrict__ k2,
    const Scalar* __restrict__ dX, int n_lambda, int nobs, Scalar* __restrict__ pt_cost_cand) {
  int o = blockIdx.x * blockDim.x + threadIdx.x;
  if (o >= nobs) return;
  int c = cam_idx[o], p = pt_idx[o];
  const Scalar* Rc = R + 9*c;
  for (int n = 0; n < n_lambda; ++n) {
    const Scalar* dXpn = dX + (size_t)(p*n_lambda+n)*3;
    Scalar Xp0 = X[3*p]+dXpn[0], Xp1 = X[3*p+1]+dXpn[1], Xp2 = X[3*p+2]+dXpn[2];
    Scalar Px = Rc[0]*Xp0+Rc[1]*Xp1+Rc[2]*Xp2+t[3*c];
    Scalar Py = Rc[3]*Xp0+Rc[4]*Xp1+Rc[5]*Xp2+t[3*c+1];
    Scalar Pz = Rc[6]*Xp0+Rc[7]*Xp1+Rc[8]*Xp2+t[3*c+2];
    Scalar xp = -Px/Pz, yp = -Py/Pz; Scalar r2 = xp*xp+yp*yp;
    Scalar dist = 1.0+k1[c]*r2+k2[c]*r2*r2;
    Scalar rx = f[c]*dist*xp-uv[2*o], ry = f[c]*dist*yp-uv[2*o+1];
    atomicAdd(&pt_cost_cand[p*n_lambda+n], 0.5*(rx*rx+ry*ry));
  }
}

// Current (pre-step) per-block true cost -- the baseline the final g_k step
// must beat to be accepted.
__global__ void KernelPerBlockCostNow(
    const int* __restrict__ cam_idx, const int* __restrict__ pt_idx, const Scalar* __restrict__ uv,
    const Scalar* __restrict__ R, const Scalar* __restrict__ t, const Scalar* __restrict__ X,
    const Scalar* __restrict__ f, const Scalar* __restrict__ k1, const Scalar* __restrict__ k2, int nobs,
    Scalar* __restrict__ cam_cost_now, Scalar* __restrict__ pt_cost_now) {
  int o = blockIdx.x * blockDim.x + threadIdx.x;
  if (o >= nobs) return;
  int c = cam_idx[o], p = pt_idx[o];
  const Scalar* Rc = R+9*c; const Scalar* Xp = X+3*p;
  Scalar Px = Rc[0]*Xp[0]+Rc[1]*Xp[1]+Rc[2]*Xp[2]+t[3*c];
  Scalar Py = Rc[3]*Xp[0]+Rc[4]*Xp[1]+Rc[5]*Xp[2]+t[3*c+1];
  Scalar Pz = Rc[6]*Xp[0]+Rc[7]*Xp[1]+Rc[8]*Xp[2]+t[3*c+2];
  Scalar xp = -Px/Pz, yp = -Py/Pz; Scalar r2 = xp*xp+yp*yp;
  Scalar dist = 1.0+k1[c]*r2+k2[c]*r2*r2;
  Scalar rx = f[c]*dist*xp-uv[2*o], ry = f[c]*dist*yp-uv[2*o+1];
  Scalar cost_o = 0.5*(rx*rx+ry*ry);
  atomicAdd(&cam_cost_now[c], cost_o);
  atomicAdd(&pt_cost_now[p], cost_o);
}

__global__ void KernelSelectLam(const Scalar* __restrict__ cost_cand, const Scalar* __restrict__ lam_grid,
                                 int n_lambda, int K, Scalar* __restrict__ chosen_lam) {
  int k = blockIdx.x * blockDim.x + threadIdx.x;
  if (k >= K) return;
  int best = 0; Scalar bestv = cost_cand[k*n_lambda];
  for (int n = 1; n < n_lambda; ++n) {
    Scalar v = cost_cand[k*n_lambda+n];
    if (v < bestv) { bestv = v; best = n; }
  }
  chosen_lam[k] = lam_grid[k*n_lambda+best];
}

// Variable-per-block-lambda variants of KernelInvertCamBlocks/KernelInvertPtBlocksFactored/
// KernelBlockApply6/KernelBlockApply3 (those take one scalar lam for every
// block; these take a per-block lam array, needed once each block has its
// own multi-lambda-selected value).
__global__ void KernelInvertCamBlocksVarLam(const Scalar* __restrict__ Hcc, const Scalar* __restrict__ lam_arr,
                                             Scalar factor, Scalar* __restrict__ Hcc_inv,
                                             int* __restrict__ ok_flags, int ncam) {
  int c = blockIdx.x * blockDim.x + threadIdx.x;
  if (c >= ncam) return;
  Scalar H[6][6];
#pragma unroll
  for (int i = 0; i < 6; ++i)
#pragma unroll
    for (int j = 0; j < 6; ++j) H[i][j] = Hcc[36*c + 6*i+j];
  Scalar Inv[6][6];
  bool ok = Cholesky6x6Inv(H, lam_arr[c], factor, Inv);
  ok_flags[c] = ok ? 1 : 0;
  if (ok) {
#pragma unroll
    for (int i = 0; i < 6; ++i)
#pragma unroll
      for (int j = 0; j < 6; ++j) Hcc_inv[36*c + 6*i+j] = Inv[i][j];
  }
}
__global__ void KernelInvertPtBlocksVarLamFactored(const Scalar* __restrict__ Hpp, const Scalar* __restrict__ lam_arr,
                                                     Scalar factor, Scalar* __restrict__ Hpp_inv,
                                                     int* __restrict__ ok_flags, int npt) {
  int p = blockIdx.x * blockDim.x + threadIdx.x;
  if (p >= npt) return;
  Scalar H[3][3];
#pragma unroll
  for (int i = 0; i < 3; ++i)
#pragma unroll
    for (int j = 0; j < 3; ++j) H[i][j] = factor * Hpp[9*p + 3*i+j];
  Scalar Inv[3][3];
  bool ok = Cholesky3x3Inv(H, lam_arr[p], Inv);
  ok_flags[p] = ok ? 1 : 0;
  if (ok) {
#pragma unroll
    for (int i = 0; i < 3; ++i)
#pragma unroll
      for (int j = 0; j < 3; ++j) Hpp_inv[9*p + 3*i+j] = Inv[i][j];
  }
}
__global__ void KernelBlockApply6VarLam(const Scalar* __restrict__ Inv, const Scalar* __restrict__ grad,
                                         const Scalar* __restrict__ prev, const Scalar* __restrict__ lam_arr,
                                         int K, Scalar* __restrict__ out) {
  int k = blockIdx.x * blockDim.x + threadIdx.x;
  if (k >= K) return;
  Scalar rhs[6];
#pragma unroll
  for (int i = 0; i < 6; ++i) rhs[i] = grad[6*k+i] + (prev ? lam_arr[k]*prev[6*k+i] : 0.0);
  const Scalar* Ik = Inv + 36*k;
  Scalar outk[6];
#pragma unroll
  for (int i = 0; i < 6; ++i) {
    Scalar s = 0;
#pragma unroll
    for (int j = 0; j < 6; ++j) s += Ik[6*i+j]*rhs[j];
    outk[i] = s;
  }
#pragma unroll
  for (int i = 0; i < 6; ++i) out[6*k+i] = outk[i];
}
__global__ void KernelBlockApply3VarLam(const Scalar* __restrict__ Inv, const Scalar* __restrict__ grad,
                                         const Scalar* __restrict__ prev, const Scalar* __restrict__ lam_arr,
                                         int K, Scalar* __restrict__ out) {
  int k = blockIdx.x * blockDim.x + threadIdx.x;
  if (k >= K) return;
  Scalar rhs[3];
#pragma unroll
  for (int i = 0; i < 3; ++i) rhs[i] = grad[3*k+i] + (prev ? lam_arr[k]*prev[3*k+i] : 0.0);
  const Scalar* Ik = Inv + 9*k;
  Scalar outk[3];
#pragma unroll
  for (int i = 0; i < 3; ++i) {
    Scalar s = 0;
#pragma unroll
    for (int j = 0; j < 3; ++j) s += Ik[3*i+j]*rhs[j];
    outk[i] = s;
  }
#pragma unroll
  for (int i = 0; i < 3; ++i) out[3*k+i] = outk[i];
}

__device__ __forceinline__ Scalar ClipScalar(Scalar v, Scalar lo, Scalar hi) {
  return v < lo ? lo : (v > hi ? hi : v);
}

// Final accept/reject on the step ACTUALLY applied (gcj/gpj = g_k, negated to
// get the retraction direction) -- writes the new (or unchanged) camera/point
// state, updates base_lam for next outer iteration (accept: shrink /3;
// reject: grow x10, matching reference_mm.py's own adaptation rule), and
// reports the accepted step (0 if rejected) for the step-norm convergence check.
__global__ void KernelAcceptUpdateCam(
    const Scalar* __restrict__ cam_cost_final, const Scalar* __restrict__ cam_cost_now,
    const Scalar* __restrict__ gcj, const Scalar* __restrict__ chosen_lam_cam,
    Scalar lam_floor, Scalar lam_ceil, int ncam,
    const Scalar* __restrict__ R_old, const Scalar* __restrict__ t_old,
    Scalar* __restrict__ R_new, Scalar* __restrict__ t_new,
    Scalar* __restrict__ base_lam_cam, Scalar* __restrict__ d_out) {
  int c = blockIdx.x * blockDim.x + threadIdx.x;
  if (c >= ncam) return;
  bool accept = cam_cost_final[c] < cam_cost_now[c];
  if (accept) {
    Scalar dneg[6];
#pragma unroll
    for (int i = 0; i < 6; ++i) dneg[i] = -gcj[6*c+i];
    Scalar dR[9]; ExpSO3(dneg, dR);
    Scalar Rn[9]; Mat3Mul(dR, R_old+9*c, Rn);
#pragma unroll
    for (int i = 0; i < 9; ++i) R_new[9*c+i] = Rn[i];
#pragma unroll
    for (int i = 0; i < 3; ++i) t_new[3*c+i] = t_old[3*c+i] + dneg[3+i];
    base_lam_cam[c] = ClipScalar(chosen_lam_cam[c]/3.0, lam_floor, lam_ceil);
#pragma unroll
    for (int i = 0; i < 6; ++i) d_out[6*c+i] = dneg[i];
  } else {
#pragma unroll
    for (int i = 0; i < 9; ++i) R_new[9*c+i] = R_old[9*c+i];
#pragma unroll
    for (int i = 0; i < 3; ++i) t_new[3*c+i] = t_old[3*c+i];
    base_lam_cam[c] = ClipScalar(base_lam_cam[c]*10.0, lam_floor, lam_ceil);
#pragma unroll
    for (int i = 0; i < 6; ++i) d_out[6*c+i] = 0.0;
  }
}
__global__ void KernelAcceptUpdatePt(
    const Scalar* __restrict__ pt_cost_final, const Scalar* __restrict__ pt_cost_now,
    const Scalar* __restrict__ gpj, const Scalar* __restrict__ chosen_lam_pt,
    Scalar lam_floor, Scalar lam_ceil, int npt,
    const Scalar* __restrict__ X_old, Scalar* __restrict__ X_new,
    Scalar* __restrict__ base_lam_pt, Scalar* __restrict__ d_out) {
  int p = blockIdx.x * blockDim.x + threadIdx.x;
  if (p >= npt) return;
  bool accept = pt_cost_final[p] < pt_cost_now[p];
  if (accept) {
#pragma unroll
    for (int i = 0; i < 3; ++i) {
      Scalar dneg = -gpj[3*p+i];
      X_new[3*p+i] = X_old[3*p+i] + dneg;
      d_out[3*p+i] = dneg;
    }
    base_lam_pt[p] = ClipScalar(chosen_lam_pt[p]/3.0, lam_floor, lam_ceil);
  } else {
#pragma unroll
    for (int i = 0; i < 3; ++i) { X_new[3*p+i] = X_old[3*p+i]; d_out[3*p+i] = 0.0; }
    base_lam_pt[p] = ClipScalar(base_lam_pt[p]*10.0, lam_floor, lam_ceil);
  }
}

// Gauss-Newton-only variant of KernelAssembleSchurSparse (drops the rx*hx+ry*hy
// residual-curvature term) -- LM's Hessian per Algorithm 1/Eq.2 is J^T J only,
// which has the EXACT SAME block-sparsity as OCA's true Hessian (same
// per-observation camera/point/cross structure), so the same sparse-Schur
// machinery (KernelFormSSparse etc.) applies unchanged; only the per-observation
// assembly differs by which terms it includes.
// Partitioned variant of KernelAssembleSchurSparseGN: cameras and points are
// each assigned to a "device" (device_of_cam/device_of_pt). Observations
// where camera and point are on the SAME device ("intra") contribute
// EXACTLY as before -- full coupling, obs_Hcp written normally. Observations
// where they're on DIFFERENT devices ("cross") contribute to Hcc/Hpp only,
// with DABA's majorization factor applied (matching the paper's P_ij+Q_ij
// separable surrogate, Eq.21 of arXiv:2305.07026), and obs_Hcp is left at
// ZERO for that observation -- deliberately NOT built as a smaller/reduced
// array. This is the key simplification: every downstream kernel
// (KernelFormSSparse, KernelRHSCorrectionSparse, KernelBackSubstituteSparse,
// the growing recursion, multi-lambda) needs NO changes at all, since a zero
// Hcp block is already exactly "no coupling contribution" to them. The
// resulting Schur complement S is then PROVABLY block-diagonal across
// devices: a point p (owned by device beta) only contributes nonzero
// coupling between cameras that BOTH observe it intra-device, which by
// construction can only be cameras also on device beta -- so no point ever
// creates an S-block linking two different devices. Gradient is NEVER
// scaled by factor (only curvature) -- a majorizer must match the true
// local gradient exactly at the current point, only its curvature needs to
// be inflated to remain a valid upper bound elsewhere.
template <class HT>
__global__ void KernelAssembleSchurPartitioned(
    const int* __restrict__ cam_idx, const int* __restrict__ pt_idx, const Scalar* __restrict__ uv,
    const Scalar* __restrict__ R, const Scalar* __restrict__ t, const Scalar* __restrict__ X,
    const Scalar* __restrict__ f, const Scalar* __restrict__ k1, const Scalar* __restrict__ k2,
    const int* __restrict__ device_of_cam, const int* __restrict__ device_of_pt, Scalar factor,
    int nobs,
    Scalar* __restrict__ Hcc, Scalar* __restrict__ Hpp, HT* __restrict__ obs_Hcp,
    Scalar* __restrict__ grad_c, Scalar* __restrict__ grad_p) {
  int o = blockIdx.x * blockDim.x + threadIdx.x;
  if (o >= nobs) return;
  int c = cam_idx[o], p = pt_idx[o];
  bool intra = (device_of_cam[c] == device_of_pt[p]);
  Scalar curv_scale = intra ? (Scalar)1.0 : factor;
  const Scalar* Rc = R + 9 * c;
  const Scalar* Xp = X + 3 * p;
  Scalar Px = Rc[0]*Xp[0]+Rc[1]*Xp[1]+Rc[2]*Xp[2] + t[3*c];
  Scalar Py = Rc[3]*Xp[0]+Rc[4]*Xp[1]+Rc[5]*Xp[2] + t[3*c+1];
  Scalar Pz = Rc[6]*Xp[0]+Rc[7]*Xp[1]+Rc[8]*Xp[2] + t[3*c+2];
  Scalar xp = -Px / Pz, yp = -Py / Pz;
  Scalar r2 = xp*xp + yp*yp;
  Scalar dist = 1.0 + k1[c]*r2 + k2[c]*r2*r2;
  Scalar rx = f[c]*dist*xp - uv[2*o];
  Scalar ry = f[c]*dist*yp - uv[2*o+1];
  Scalar gx[9], gy[9], hx[81], hy[81];
  BalResidualGradHess(Rc[0],Rc[1],Rc[2],Rc[3],Rc[4],Rc[5],Rc[6],Rc[7],Rc[8],
                       t[3*c],t[3*c+1],t[3*c+2],Xp[0],Xp[1],Xp[2],
                       f[c],k1[c],k2[c],uv[2*o],uv[2*o+1], gx,gy,hx,hy);
  Scalar g9[9], H9[81];
#pragma unroll
  for (int i = 0; i < 9; ++i) g9[i] = rx*gx[i] + ry*gy[i];
#pragma unroll
  for (int i = 0; i < 9; ++i)
#pragma unroll
    for (int j = 0; j < 9; ++j) H9[9*i+j] = gx[i]*gx[j] + gy[i]*gy[j];
#pragma unroll
  for (int i = 0; i < 6; ++i) atomicAdd(&grad_c[6*c+i], g9[i]);
#pragma unroll
  for (int i = 0; i < 3; ++i) atomicAdd(&grad_p[3*p+i], g9[6+i]);
#pragma unroll
  for (int i = 0; i < 6; ++i)
#pragma unroll
    for (int j = 0; j < 6; ++j) atomicAdd(&Hcc[36*c + 6*i+j], curv_scale * H9[9*i+j]);
#pragma unroll
  for (int i = 0; i < 3; ++i)
#pragma unroll
    for (int j = 0; j < 3; ++j) atomicAdd(&Hpp[9*p + 3*i+j], curv_scale * H9[9*(6+i)+(6+j)]);
  if (intra) {
#pragma unroll
    for (int i = 0; i < 6; ++i)
#pragma unroll
      for (int j = 0; j < 3; ++j) obs_Hcp[18*o + 3*i+j] = (HT)H9[9*i + (6+j)];
  } else {
#pragma unroll
    for (int i = 0; i < 6; ++i)
#pragma unroll
      for (int j = 0; j < 3; ++j) obs_Hcp[18*o + 3*i+j] = (Scalar)0.0;
  }
}

template <class HT>
__global__ void KernelAssembleSchurSparseGN(
    const int* __restrict__ cam_idx, const int* __restrict__ pt_idx, const Scalar* __restrict__ uv,
    const Scalar* __restrict__ R, const Scalar* __restrict__ t, const Scalar* __restrict__ X,
    const Scalar* __restrict__ f, const Scalar* __restrict__ k1, const Scalar* __restrict__ k2,
    int nobs,
    Scalar* __restrict__ Hcc, Scalar* __restrict__ Hpp, HT* __restrict__ obs_Hcp,
    Scalar* __restrict__ grad_c, Scalar* __restrict__ grad_p) {
  int o = blockIdx.x * blockDim.x + threadIdx.x;
  if (o >= nobs) return;
  int c = cam_idx[o], p = pt_idx[o];
  const Scalar* Rc = R + 9 * c;
  const Scalar* Xp = X + 3 * p;
  Scalar Px = Rc[0]*Xp[0]+Rc[1]*Xp[1]+Rc[2]*Xp[2] + t[3*c];
  Scalar Py = Rc[3]*Xp[0]+Rc[4]*Xp[1]+Rc[5]*Xp[2] + t[3*c+1];
  Scalar Pz = Rc[6]*Xp[0]+Rc[7]*Xp[1]+Rc[8]*Xp[2] + t[3*c+2];
  Scalar xp = -Px / Pz, yp = -Py / Pz;
  Scalar r2 = xp*xp + yp*yp;
  Scalar dist = 1.0 + k1[c]*r2 + k2[c]*r2*r2;
  Scalar rx = f[c]*dist*xp - uv[2*o];
  Scalar ry = f[c]*dist*yp - uv[2*o+1];
  Scalar gx[9], gy[9], hx[81], hy[81];
  BalResidualGradHess(Rc[0],Rc[1],Rc[2],Rc[3],Rc[4],Rc[5],Rc[6],Rc[7],Rc[8],
                       t[3*c],t[3*c+1],t[3*c+2],Xp[0],Xp[1],Xp[2],
                       f[c],k1[c],k2[c],uv[2*o],uv[2*o+1], gx,gy,hx,hy);
  Scalar g9[9], H9[81];
#pragma unroll
  for (int i = 0; i < 9; ++i) g9[i] = rx*gx[i] + ry*gy[i];
#pragma unroll
  for (int i = 0; i < 9; ++i)
#pragma unroll
    for (int j = 0; j < 9; ++j) H9[9*i+j] = gx[i]*gx[j] + gy[i]*gy[j];  // GN only -- no rx*hx/ry*hy
#pragma unroll
  for (int i = 0; i < 6; ++i) atomicAdd(&grad_c[6*c+i], g9[i]);
#pragma unroll
  for (int i = 0; i < 3; ++i) atomicAdd(&grad_p[3*p+i], g9[6+i]);
#pragma unroll
  for (int i = 0; i < 6; ++i)
#pragma unroll
    for (int j = 0; j < 6; ++j) atomicAdd(&Hcc[36*c + 6*i+j], H9[9*i+j]);
#pragma unroll
  for (int i = 0; i < 3; ++i)
#pragma unroll
    for (int j = 0; j < 3; ++j) atomicAdd(&Hpp[9*p + 3*i+j], H9[9*(6+i)+(6+j)]);
#pragma unroll
  for (int i = 0; i < 6; ++i)
#pragma unroll
    for (int j = 0; j < 3; ++j) obs_Hcp[18*o + 3*i+j] = (HT)H9[9*i + (6+j)];
}


// ---- ROUND 9 (Caspar transfer probe): identical to KernelAssembleSchurSparseGN except that
// the per-observation Jacobian rows gx,gy (and the residual rx,ry) are ROUNDED TO fp32 before
// any product is formed.  This has exactly the numerics of storing J in fp32 on device.
// Why round J and not obs_Hcp: 6*3 == 2*6 + 2*3 == 18 scalars, so the factored Jacobian costs
// the SAME memory as the H_cp block it generates, while keeping H = sum_o J_o^T J_o positive
// semidefinite for ANY J -- so Theorem 0's majorization survives the perturbation exactly,
// which is NOT true if H_cp alone is rounded.
template <class HT>
__global__ void KernelAssembleSchurSparseGN_J32(
    const int* __restrict__ cam_idx, const int* __restrict__ pt_idx, const Scalar* __restrict__ uv,
    const Scalar* __restrict__ R, const Scalar* __restrict__ t, const Scalar* __restrict__ X,
    const Scalar* __restrict__ f, const Scalar* __restrict__ k1, const Scalar* __restrict__ k2,
    int nobs,
    Scalar* __restrict__ Hcc, Scalar* __restrict__ Hpp, HT* __restrict__ obs_Hcp,
    Scalar* __restrict__ grad_c, Scalar* __restrict__ grad_p) {
  int o = blockIdx.x * blockDim.x + threadIdx.x;
  if (o >= nobs) return;
  int c = cam_idx[o], p = pt_idx[o];
  const Scalar* Rc = R + 9 * c;
  const Scalar* Xp = X + 3 * p;
  Scalar Px = Rc[0]*Xp[0]+Rc[1]*Xp[1]+Rc[2]*Xp[2] + t[3*c];
  Scalar Py = Rc[3]*Xp[0]+Rc[4]*Xp[1]+Rc[5]*Xp[2] + t[3*c+1];
  Scalar Pz = Rc[6]*Xp[0]+Rc[7]*Xp[1]+Rc[8]*Xp[2] + t[3*c+2];
  Scalar xp = -Px / Pz, yp = -Py / Pz;
  Scalar r2 = xp*xp + yp*yp;
  Scalar dist = 1.0 + k1[c]*r2 + k2[c]*r2*r2;
  Scalar rx = f[c]*dist*xp - uv[2*o];
  Scalar ry = f[c]*dist*yp - uv[2*o+1];
  Scalar gx[9], gy[9], hx[81], hy[81];
  BalResidualGradHess(Rc[0],Rc[1],Rc[2],Rc[3],Rc[4],Rc[5],Rc[6],Rc[7],Rc[8],
                       t[3*c],t[3*c+1],t[3*c+2],Xp[0],Xp[1],Xp[2],
                       f[c],k1[c],k2[c],uv[2*o],uv[2*o+1], gx,gy,hx,hy);
#pragma unroll
  for (int i = 0; i < 9; ++i) { gx[i] = (Scalar)(float)gx[i]; gy[i] = (Scalar)(float)gy[i]; }
  rx = (Scalar)(float)rx; ry = (Scalar)(float)ry;
  Scalar g9[9], H9[81];
#pragma unroll
  for (int i = 0; i < 9; ++i) g9[i] = rx*gx[i] + ry*gy[i];
#pragma unroll
  for (int i = 0; i < 9; ++i)
#pragma unroll
    for (int j = 0; j < 9; ++j) H9[9*i+j] = gx[i]*gx[j] + gy[i]*gy[j];
#pragma unroll
  for (int i = 0; i < 6; ++i) atomicAdd(&grad_c[6*c+i], g9[i]);
#pragma unroll
  for (int i = 0; i < 3; ++i) atomicAdd(&grad_p[3*p+i], g9[6+i]);
#pragma unroll
  for (int i = 0; i < 6; ++i)
#pragma unroll
    for (int j = 0; j < 6; ++j) atomicAdd(&Hcc[36*c + 6*i+j], H9[9*i+j]);
#pragma unroll
  for (int i = 0; i < 3; ++i)
#pragma unroll
    for (int j = 0; j < 3; ++j) atomicAdd(&Hpp[9*p + 3*i+j], H9[9*(6+i)+(6+j)]);
#pragma unroll
  for (int i = 0; i < 6; ++i)
#pragma unroll
    for (int j = 0; j < 3; ++j) obs_Hcp[18*o + 3*i+j] = (HT)H9[9*i + (6+j)];
}

// d^T (J^T J) d = ||J d||^2 = sum over observations of (gx.d_obs)^2+(gy.d_obs)^2,
// where d_obs gathers this observation's camera(6)+point(3) slice of the full
// step d -- used for LM's trust-region predicted-decrease (Eq.3-4), avoids ever
// forming a Hessian-vector product through the (unassembled) sparse structure.
__global__ void KernelJdSquaredSum(
    const int* __restrict__ cam_idx, const int* __restrict__ pt_idx, const Scalar* __restrict__ uv,
    const Scalar* __restrict__ R, const Scalar* __restrict__ t, const Scalar* __restrict__ X,
    const Scalar* __restrict__ f, const Scalar* __restrict__ k1, const Scalar* __restrict__ k2,
    const Scalar* __restrict__ d, int nobs, int ncam, Scalar* __restrict__ out) {
  int o = blockIdx.x * blockDim.x + threadIdx.x;
  if (o >= nobs) return;
  int c = cam_idx[o], p = pt_idx[o];
  const Scalar* Rc = R + 9 * c;
  const Scalar* Xp = X + 3 * p;
  Scalar Px = Rc[0]*Xp[0]+Rc[1]*Xp[1]+Rc[2]*Xp[2] + t[3*c];
  Scalar Py = Rc[3]*Xp[0]+Rc[4]*Xp[1]+Rc[5]*Xp[2] + t[3*c+1];
  Scalar Pz = Rc[6]*Xp[0]+Rc[7]*Xp[1]+Rc[8]*Xp[2] + t[3*c+2];
  Scalar xp = -Px / Pz, yp = -Py / Pz;
  Scalar r2 = xp*xp + yp*yp;
  Scalar dist = 1.0 + k1[c]*r2 + k2[c]*r2*r2;
  Scalar rx = f[c]*dist*xp - uv[2*o];
  Scalar ry = f[c]*dist*yp - uv[2*o+1];
  Scalar gx[9], gy[9], hx[81], hy[81];
  BalResidualGradHess(Rc[0],Rc[1],Rc[2],Rc[3],Rc[4],Rc[5],Rc[6],Rc[7],Rc[8],
                       t[3*c],t[3*c+1],t[3*c+2],Xp[0],Xp[1],Xp[2],
                       f[c],k1[c],k2[c],uv[2*o],uv[2*o+1], gx,gy,hx,hy);
  Scalar dobs[9];
#pragma unroll
  for (int i = 0; i < 6; ++i) dobs[i] = d[6*c+i];
#pragma unroll
  for (int i = 0; i < 3; ++i) dobs[6+i] = d[6*ncam + 3*p + i];
  Scalar jx = 0, jy = 0;
#pragma unroll
  for (int i = 0; i < 9; ++i) { jx += gx[i]*dobs[i]; jy += gy[i]*dobs[i]; }
  atomicAdd(out, jx*jx + jy*jy);
}

__global__ void KernelSubtractVec(Scalar* __restrict__ out, const Scalar* __restrict__ a,
                                   const Scalar* __restrict__ b, int n) {
  int i = blockIdx.x * blockDim.x + threadIdx.x; if (i >= n) return; out[i] = a[i] - b[i];
}

__global__ void KernelNegateInPlace(Scalar* __restrict__ v, int n) {
  int i = blockIdx.x * blockDim.x + threadIdx.x;
  if (i >= n) return;
  v[i] = -v[i];
}

__global__ void KernelAddDiag(Scalar* __restrict__ A, int n, Scalar val) {
  int i = blockIdx.x * blockDim.x + threadIdx.x;
  if (i >= n) return;
  A[i * n + i] += val;
}

__global__ void KernelAxpy(Scalar* __restrict__ y, const Scalar* __restrict__ x, Scalar a, int n) {
  int i = blockIdx.x * blockDim.x + threadIdx.x;
  if (i >= n) return;
  y[i] += a * x[i];
}

__global__ void KernelScaleAdd(Scalar* __restrict__ out, const Scalar* __restrict__ grad,
                                const Scalar* __restrict__ g_prev, Scalar lam, int n) {
  int i = blockIdx.x * blockDim.x + threadIdx.x;
  if (i >= n) return;
  out[i] = grad[i] + lam * g_prev[i];
}

// ============================================================== host-side dense state + cuSOLVER
struct DeviceProblem {
  int ncam, npt, nobs, n;
  int *cam_idx, *pt_idx;
  Scalar *uv, *f, *k1, *k2;
  int *point_obs_offsets = nullptr, *point_obs_list = nullptr;  // CSR point->observation index (sparse Schur only)
  int *obs2pslot=nullptr,*obs2cslot=nullptr,*mf_scam=nullptr,*mf_spt=nullptr,*mf_coff=nullptr,*mf_cspt=nullptr;  // ROUND 9 matrix-free indexing
  // Round-4 Q1: persistent edge-CSR over the camera co-visibility graph, for atomic-free Schur
  // formation (see KernelFormSEdges below). Built once at problem load; the PATTERN is invariant
  // across outer iterations and lambda (only the H_cp/App_inv VALUES gathered through it change).
  // ROUND 11: shared intrinsics. calib_of_cam[c] is the calibration group of
  // camera c; ncalib is the number of groups. When ncalib == ncam (or the map
  // is null) every camera owns its intrinsics and the solver behaves exactly
  // as before -- the CD=9 CLI path is unaffected.
  int ncalib = 0;
  int* calib_of_cam = nullptr;

  int n_edges = 0;
  int *edge_ci = nullptr, *edge_cj = nullptr;         // size n_edges: the two cameras of each edge
  int *edge_offsets = nullptr;                        // size n_edges+1: CSR into edge_obs_d/e
  int *edge_obs_d = nullptr, *edge_obs_e = nullptr;   // size sum_p C(D_p,2): observation-index pairs
};

struct DeviceState {
  Scalar *R, *t, *X;  // ncam*9, ncam*3, npt*3
  // ROUND 10: mutable per-camera intrinsics, laid out [f(ncam)|k1(ncam)|k2(ncam)]
  // so f = intr, k1 = intr+ncam, k2 = intr+2*ncam are drop-in replacements for
  // the p.f/p.k1/p.k2 pointers every existing kernel already takes. Non-null
  // only in --dof9 runs; every 6-DOF solver leaves it null and is unaffected.
  Scalar *intr = nullptr;
  int ncam_for_intr = 0;
};
// Intrinsics pointer selection: state-owned when present, else the fixed problem arrays.
#define INTR_F(p, s)  ((s).intr ? (s).intr : (p).f)
#define INTR_K1(p, s) ((s).intr ? (s).intr + (s).ncam_for_intr : (p).k1)
#define INTR_K2(p, s) ((s).intr ? (s).intr + 2*(s).ncam_for_intr : (p).k2)

static int GridSize(int n, int block = 256) { return (n + block - 1) / block; }


// ---- Problem indexing, shared by the CLI and the embeddable core -----------
// Both wrappers MUST build these identically; when this lived only inside
// main() the core silently ran the matrix-free kernels against null index
// pointers. Keep it here so there is exactly one construction.

// Point -> observation CSR (topology only, built once). Returns the
// observation order the CSR is expressed in; BuildMFreeIndex needs it.
static std::vector<int> BuildPointObsCSR(DeviceProblem& p, const int* pt_idx,
                                         int npt, int nobs,
                                         std::vector<int>* offsets_out = nullptr) {
  // Stable COUNTING sort by pt_idx (keys are dense in [0,npt)), not a
  // comparison sort. Identical output to the std::stable_sort it replaces --
  // placing observations in increasing original index within each bucket is
  // exactly stability -- so every downstream index, and therefore every
  // atomicAdd order and every bit of the trajectory, is unchanged. The
  // comparison sort was the dominant setup cost: random-access comparisons
  // over 9.1M observations on final-4585.
  std::vector<int> offsets(npt + 1, 0);
  for (int o = 0; o < nobs; ++o) offsets[pt_idx[o] + 1]++;
  for (int pp = 0; pp < npt; ++pp) offsets[pp + 1] += offsets[pp];
  std::vector<int> order(nobs);
  {
    std::vector<int> cursor(offsets.begin(), offsets.end() - 1);
    for (int o = 0; o < nobs; ++o) order[cursor[pt_idx[o]]++] = o;
  }
  CUDA_CHECK(cudaMalloc(&p.point_obs_offsets, (npt + 1) * sizeof(int)));
  CUDA_CHECK(cudaMalloc(&p.point_obs_list, nobs * sizeof(int)));
  CUDA_CHECK(cudaMemcpy(p.point_obs_offsets, offsets.data(),
                        (npt + 1) * sizeof(int), cudaMemcpyHostToDevice));
  CUDA_CHECK(cudaMemcpy(p.point_obs_list, order.data(), nobs * sizeof(int),
                        cudaMemcpyHostToDevice));
  if (offsets_out) *offsets_out = std::move(offsets);
  return order;
}

// ROUND 9 matrix-free indexing: point-sorted and camera-sorted observation
// slots plus the per-camera CSR offsets. Required by SolveMFreeShiftedCG.
static void BuildMFreeIndex(DeviceProblem& p, const int* cam_idx,
                            const int* pt_idx, const std::vector<int>& order,
                            int ncam, int nobs) {
  std::vector<int> o2p(nobs);
  for (int kk = 0; kk < nobs; ++kk) o2p[order[kk]] = kk;
  std::vector<int> h_scam(nobs), h_spt(nobs);
  for (int kk = 0; kk < nobs; ++kk) {
    h_scam[kk] = cam_idx[order[kk]];
    h_spt[kk] = pt_idx[order[kk]];
  }
  // Same stable counting sort, keyed on cam_idx (dense in [0,ncam)). The
  // histogram doubles as the CSR offset array, so the separate counting pass
  // over the sorted order disappears too.
  std::vector<int> coff(ncam + 1, 0);
  for (int o = 0; o < nobs; ++o) coff[cam_idx[o] + 1]++;
  for (int c = 0; c < ncam; ++c) coff[c + 1] += coff[c];
  std::vector<int> cord(nobs);
  {
    std::vector<int> cursor(coff.begin(), coff.end() - 1);
    for (int o = 0; o < nobs; ++o) cord[cursor[cam_idx[o]]++] = o;
  }
  std::vector<int> o2c(nobs), h_cspt(nobs);
  for (int kk = 0; kk < nobs; ++kk) {
    o2c[cord[kk]] = kk;
    h_cspt[kk] = pt_idx[cord[kk]];
  }
  auto up = [&](int** d, const std::vector<int>& h) {
    CUDA_CHECK(cudaMalloc(d, h.size() * sizeof(int)));
    CUDA_CHECK(cudaMemcpy(*d, h.data(), h.size() * sizeof(int),
                          cudaMemcpyHostToDevice));
  };
  up(&p.obs2pslot, o2p);  up(&p.obs2cslot, o2c);  up(&p.mf_scam, h_scam);
  up(&p.mf_spt, h_spt);   up(&p.mf_coff, coff);   up(&p.mf_cspt, h_cspt);
}


// ---- ROUND 9: dump the current state as a BAL file so the matrix-free probe can
// be run at a real mid-trajectory geometry (CONTEXT s6: check the licensing
// quantity at the operating point, not only at initialisation).
static void DumpBalState(const std::string& path, const BalData& bal,
                         const DeviceState& s, int ncam, int npt) {
  std::vector<Scalar> hR(9*(size_t)ncam), ht(3*(size_t)ncam), hX(3*(size_t)npt);
  CUDA_CHECK(cudaMemcpy(hR.data(), s.R, 9*(size_t)ncam*sizeof(Scalar), cudaMemcpyDeviceToHost));
  CUDA_CHECK(cudaMemcpy(ht.data(), s.t, 3*(size_t)ncam*sizeof(Scalar), cudaMemcpyDeviceToHost));
  CUDA_CHECK(cudaMemcpy(hX.data(), s.X, 3*(size_t)npt*sizeof(Scalar), cudaMemcpyDeviceToHost));
  // ROUND 10: a --dof9 run owns its intrinsics; dump the refined values, not the input's.
  std::vector<Scalar> hI;
  if (s.intr) {
    hI.resize(3*(size_t)ncam);
    CUDA_CHECK(cudaMemcpy(hI.data(), s.intr, 3*(size_t)ncam*sizeof(Scalar), cudaMemcpyDeviceToHost));
  }
  FILE* f = std::fopen(path.c_str(), "w");
  if (!f) { std::fprintf(stderr, "cannot write %s\n", path.c_str()); return; }
  std::fprintf(f, "%d %d %d\n", ncam, npt, bal.nobs);
  for (int o = 0; o < bal.nobs; ++o)
    std::fprintf(f, "%d %d %.17g %.17g\n", bal.cam_idx[o], bal.pt_idx[o], bal.uv[2*o], bal.uv[2*o+1]);
  for (int c = 0; c < ncam; ++c) {
    const Scalar* R = hR.data() + 9*c;
    Scalar tr = R[0] + R[4] + R[8];
    Scalar ct = 0.5*(tr - 1.0); ct = std::max((Scalar)-1.0, std::min((Scalar)1.0, ct));
    Scalar th = std::acos(ct);
    Scalar vx = R[7]-R[5], vy = R[2]-R[6], vz = R[3]-R[1];
    Scalar sc = (th < 1e-9) ? 0.5 : th/(2.0*std::sin(th));
    std::fprintf(f, "%.17g\n%.17g\n%.17g\n", sc*vx, sc*vy, sc*vz);
    std::fprintf(f, "%.17g\n%.17g\n%.17g\n", ht[3*c], ht[3*c+1], ht[3*c+2]);
    if (s.intr)
      std::fprintf(f, "%.17g\n%.17g\n%.17g\n", hI[c], hI[ncam+c], hI[2*ncam+c]);
    else
      std::fprintf(f, "%.17g\n%.17g\n%.17g\n", bal.cams[9*c+6], bal.cams[9*c+7], bal.cams[9*c+8]);
  }
  for (int p = 0; p < npt; ++p)
    std::fprintf(f, "%.17g\n%.17g\n%.17g\n", hX[3*p], hX[3*p+1], hX[3*p+2]);
  std::fclose(f);
  std::fprintf(stderr, "[R9] dumped BAL state to %s\n", path.c_str());
}
static std::string g_dump_prefix; static std::vector<int> g_dump_iters;
// ---- ROUND 9: durable per-iteration convergence logging (--csv).
// Every solver that supports it writes iter,cost,wall_s so convergence plots
// never require re-running the solver.
// ---- ROUND 9: device-memory accounting (OCA_MEMREPORT=1) ----
static size_t g_mem_base = 0;
static void MemMark(const char* tag) {
  if (!getenv("OCA_MEMREPORT")) return;
  size_t f, t; cudaMemGetInfo(&f, &t);
  size_t used = t - f;
  if (g_mem_base == 0) g_mem_base = used;
  std::printf("  [MEM] %-38s device used = %7.1f MiB   (delta from ctx+data = %+8.1f MiB)\n",
              tag, used/1048576.0, (double)((long long)used - (long long)g_mem_base)/1048576.0);
}
static std::string g_csv_problem;
static std::string g_csv_path; static FILE* g_csv = nullptr;
static std::chrono::steady_clock::time_point g_csv_t0;
static void CsvOpen(const char* algo, const char* problem) {
  if (g_csv_path.empty()) return;
  g_csv = std::fopen(g_csv_path.c_str(), "w");
  if (!g_csv) { std::fprintf(stderr, "[R9] cannot write %s\n", g_csv_path.c_str()); return; }
  std::fprintf(g_csv, "# algo=%s problem=%s\niter,cost,wall_s\n", algo, problem);
  g_csv_t0 = std::chrono::steady_clock::now();
}
static void CsvRow(int it, double cost) {
  if (!g_csv) return;
  double w = std::chrono::duration<double>(std::chrono::steady_clock::now() - g_csv_t0).count();
  std::fprintf(g_csv, "%d,%.10f,%.4f\n", it, cost, w);
  std::fflush(g_csv);
}
static void CsvClose() { if (g_csv) { std::fclose(g_csv); g_csv = nullptr;
  std::fprintf(stderr, "[R9] wrote %s\n", g_csv_path.c_str()); } }
static const BalData* g_bal_ptr = nullptr;

void AllocState(DeviceState& s, int ncam, int npt, bool with_intr = false) {
  CUDA_CHECK(cudaMalloc(&s.R, 9 * ncam * sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&s.t, 3 * ncam * sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&s.X, 3 * npt * sizeof(Scalar)));
  if (with_intr) {  // ROUND 10
    CUDA_CHECK(cudaMalloc(&s.intr, 3 * ncam * sizeof(Scalar)));
    s.ncam_for_intr = ncam;
  }
}

void CopyState(const DeviceState& dst, const DeviceState& src, int ncam, int npt) {
  CUDA_CHECK(cudaMemcpy(dst.R, src.R, 9*ncam*sizeof(Scalar), cudaMemcpyDeviceToDevice));
  CUDA_CHECK(cudaMemcpy(dst.t, src.t, 3*ncam*sizeof(Scalar), cudaMemcpyDeviceToDevice));
  CUDA_CHECK(cudaMemcpy(dst.X, src.X, 3*npt*sizeof(Scalar), cudaMemcpyDeviceToDevice));
  if (dst.intr && src.intr)  // ROUND 10
    CUDA_CHECK(cudaMemcpy(dst.intr, src.intr, 3*ncam*sizeof(Scalar), cudaMemcpyDeviceToDevice));
}

struct Diagnostics {
  Scalar median_reproj_err_px;
  int num_obs_cheirality_violations;
  int num_pt_cheirality_violations;
  int num_valid_obs;
};

Diagnostics ComputeDiagnostics(const DeviceProblem& p, const DeviceState& s) {
  Scalar *reproj_err; int *obs_cheirality, *pt_cheirality;
  CUDA_CHECK(cudaMalloc(&reproj_err, p.nobs*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&obs_cheirality, p.nobs*sizeof(int)));
  CUDA_CHECK(cudaMalloc(&pt_cheirality, p.npt*sizeof(int)));
  CUDA_CHECK(cudaMemset(pt_cheirality, 0, p.npt*sizeof(int)));
  KernelDiagnostics<<<GridSize(p.nobs),256>>>(p.cam_idx, p.pt_idx, p.uv, s.R, s.t, s.X,
                                                INTR_F(p,s), INTR_K1(p,s), INTR_K2(p,s),
                                                p.nobs, reproj_err, obs_cheirality, pt_cheirality);
  std::vector<Scalar> h_err(p.nobs);
  std::vector<int> h_obs_cheir(p.nobs), h_pt_cheir(p.npt);
  CUDA_CHECK(cudaMemcpy(h_err.data(), reproj_err, p.nobs*sizeof(Scalar), cudaMemcpyDeviceToHost));
  CUDA_CHECK(cudaMemcpy(h_obs_cheir.data(), obs_cheirality, p.nobs*sizeof(int), cudaMemcpyDeviceToHost));
  CUDA_CHECK(cudaMemcpy(h_pt_cheir.data(), pt_cheirality, p.npt*sizeof(int), cudaMemcpyDeviceToHost));
  cudaFree(reproj_err); cudaFree(obs_cheirality); cudaFree(pt_cheirality);

  std::vector<Scalar> valid_err;
  valid_err.reserve(p.nobs);
  int num_obs_viol = 0;
  for (int o = 0; o < p.nobs; ++o) {
    if (h_obs_cheir[o]) { ++num_obs_viol; continue; }
    valid_err.push_back(h_err[o]);
  }
  Scalar median = 0.0;
  if (!valid_err.empty()) {
    size_t mid = valid_err.size()/2;
    std::nth_element(valid_err.begin(), valid_err.begin()+mid, valid_err.end());
    median = valid_err[mid];
    if (valid_err.size() % 2 == 0) {
      std::nth_element(valid_err.begin(), valid_err.begin()+mid-1, valid_err.end());
      median = 0.5*(median + valid_err[mid-1]);
    }
  }
  int num_pt_viol = 0; for (int v : h_pt_cheir) num_pt_viol += v;
  return Diagnostics{median, num_obs_viol, num_pt_viol, (int)valid_err.size()};
}

Scalar ComputeCost(const DeviceProblem& p, const DeviceState& s,
                   int rk = 0, Scalar rk_a2 = 0.0) {
  // REVIEW 2026-09-02: persistent scalar (d_nf pattern). This function runs
  // thousands of times per solve; a cudaMalloc/Free pair per call serializes
  // the stream on allocator traffic (~3-15% of scoring wall at scale).
  static Scalar* d_cost = nullptr;
  if (!d_cost) CUDA_CHECK(cudaMalloc(&d_cost, sizeof(Scalar)));
  CUDA_CHECK(cudaMemset(d_cost, 0, sizeof(Scalar)));
  // GAP-4090 (2026-09-03): default ON. The single-scalar-atomic KernelCost
  // serializes millions of threads (measured 43.6 ms/eval at 29M obs vs
  // 2.3 ms block-reduced = ~35% of default per-outer wall). Rounding-order
  // change only; OCA_COST_BLOCKRED=0 restores the legacy kernel.
  static const bool cost_blockred = [](){ const char* e=getenv("OCA_COST_BLOCKRED");
    return e ? atoi(e)!=0 : true; }();
  if (cost_blockred)
    KernelCostBlockRed<<<GridSize(p.nobs), 256>>>(p.cam_idx, p.pt_idx, p.uv, s.R, s.t, s.X,
                                        INTR_F(p,s), INTR_K1(p,s), INTR_K2(p,s), p.nobs, d_cost,
                                        rk, rk_a2);
  else
    KernelCost<<<GridSize(p.nobs), 256>>>(p.cam_idx, p.pt_idx, p.uv, s.R, s.t, s.X,
                                        INTR_F(p,s), INTR_K1(p,s), INTR_K2(p,s), p.nobs, d_cost,
                                        rk, rk_a2);
  Scalar cost;
  CUDA_CHECK(cudaMemcpy(&cost, d_cost, sizeof(Scalar), cudaMemcpyDeviceToHost));
  return cost;
}

// Strided variants for SUBSAMPLED CANDIDATE SCORING (OCA_SCORE_STRIDE=S).
// Score every candidate on obs k with k%S==0 only; the winner is re-scored on
// the full data before the accept decision, so accept/rho/trajectory semantics
// remain exact -- the subset only decides WHO gets the full evaluation.
// Self-consistent: each scored observation's point receives its Pass1
// contributions from exactly the scored subset. Validated idea: the sketch
// round measured 15%-of-obs scoring 0.03%-equal on plain L2 (unsafe only with
// saturating robust kernels; these runs are L2).
Scalar ComputeCostStride(const DeviceProblem& p, const DeviceState& s, int stride,
                         int rk = 0, Scalar rk_a2 = 0.0) {
  static Scalar* d_cost = nullptr;
  if (!d_cost) CUDA_CHECK(cudaMalloc(&d_cost, sizeof(Scalar)));
  CUDA_CHECK(cudaMemset(d_cost, 0, sizeof(Scalar)));
  KernelCostStride<<<GridSize(p.nobs), 256>>>(p.cam_idx, p.pt_idx, p.uv, s.R, s.t, s.X,
                                            INTR_F(p,s), INTR_K1(p,s), INTR_K2(p,s), p.nobs, stride,
                                            d_cost, rk, rk_a2);
  Scalar cost;
  CUDA_CHECK(cudaMemcpy(&cost, d_cost, sizeof(Scalar), cudaMemcpyDeviceToHost));
  return cost;
}

// Cheap cheirality-violation COUNT only (no per-observation reproj-error array, no
// per-point dedup) -- a single atomicAdd reduction, same cost shape as ComputeCost
// above, for use as a safety gate. Motivation: the reprojection cost xp=-Px/Pz,
// yp=-Py/Pz (KernelCost above) is a pure ratio, invariant under negating
// (Px,Py,Pz) together -- a point and its antipodal reflection BEHIND the camera
// along the same ray produce IDENTICAL cost. The true-cost accept-gate used by
// every solver in this file cannot detect this degeneracy by construction. This
// was found to matter in practice: an outer-Nesterov-momentum experiment
// (SolveOCAJointLambdaCamPtDepthNesterov) took a large enough extrapolated step on
// ladybug-49 to flip ~all points through this blind spot in one iteration, landing
// at the SAME cost as the true optimum via a completely degenerate reconstruction
// (31->31,812 of 31,843 observations). Conservative, aggressive-step solvers (large
// gamma, no candidate-search bound on step size) need an explicit guard the
// candidate-search solvers never needed, because their step sizes were implicitly
// bounded by true-cost comparison across a SMALL local menu, not by cost alone.
__global__ void KernelCountCheirality(const int* __restrict__ cam_idx, const int* __restrict__ pt_idx,
                                       const Scalar* __restrict__ R, const Scalar* __restrict__ t,
                                       const Scalar* __restrict__ X, int nobs, int* __restrict__ count_out) {
  int o = blockIdx.x * blockDim.x + threadIdx.x;
  if (o >= nobs) return;
  int c = cam_idx[o], p = pt_idx[o];
  const Scalar* Rc = R + 9*c; const Scalar* Xp = X + 3*p;
  Scalar Pz = Rc[6]*Xp[0]+Rc[7]*Xp[1]+Rc[8]*Xp[2] + t[3*c+2];
  if (Pz >= 0.0) atomicAdd(count_out, 1);
}

int CountCheiralityViolations(const DeviceProblem& p, const DeviceState& s) {
  static int* d_count = nullptr;
  if (!d_count) CUDA_CHECK(cudaMalloc(&d_count, sizeof(int)));
  CUDA_CHECK(cudaMemset(d_count, 0, sizeof(int)));
  KernelCountCheirality<<<GridSize(p.nobs), 256>>>(p.cam_idx, p.pt_idx, s.R, s.t, s.X, p.nobs, d_count);
  int count;
  CUDA_CHECK(cudaMemcpy(&count, d_count, sizeof(int), cudaMemcpyDeviceToHost));
  return count;
}

// REVIEW 2026-09-02 (code review, CG launch batching): the multi-shift menu
// update issues 3*(L-1) cublas launches per CG iteration (axpy into xs[l],
// scal ps[l], axpy r into ps[l]). These are elementwise, so one launch can
// process all shifts: xs[l][i] += als[l]*ps[l][i], then
// ps[l][i] = bes[l]*ps[l][i] + znext[l]*r[i]. Rounding is written to mirror
// the cublas sequence (fma for axpy, separate rounding for scal), but exact
// bit-compat with cublas internals is EMPIRICAL -- hence opt-in via
// OCA_MENU_FUSE=1 until validated. MSMAX bounds the menu width (L<=8).
constexpr int MSMAX = 8;
struct MSArgs {
  Scalar* xs[MSMAX]; Scalar* ps[MSMAX];
  Scalar als[MSMAX], bes[MSMAX], znext[MSMAX];
};
__global__ void MFMenuXUpdate(MSArgs a, int nl, int n) {
  int idx = blockIdx.x * blockDim.x + threadIdx.x;
  if (idx >= nl * n) return;
  int l = idx / n, i = idx - l * n;
  a.xs[l][i] = __fma_rn(a.als[l], a.ps[l][i], a.xs[l][i]);
}
__global__ void MFMenuPUpdate(MSArgs a, const Scalar* __restrict__ r, int nl, int n) {
  int idx = blockIdx.x * blockDim.x + threadIdx.x;
  if (idx >= nl * n) return;
  int l = idx / n, i = idx - l * n;
  Scalar t = a.bes[l] * a.ps[l][i];          // cublas Dscal rounding
  a.ps[l][i] = __fma_rn(a.znext[l], r[i], t); // cublas Daxpy fma
}

// RE-TRIANGULATION REPAIR (2026-09-07, idea #10 of the feedback list).
// The damping story says an undamped point half-step can fling a thin-track
// point out of the scene, and that a Newton-type step cannot pull it back
// (motion along the ray bisector is a near-null direction of the cost). If
// that is right, a BOUNDED CLOSED-FORM reset should recover it where a
// gradient method cannot: re-triangulate the point from its current cameras
// by the linear DLT/midpoint solution of the ray system, and keep the result
// only if the point's own reprojection cost improves.
//
// This is a mechanism fix with NO signal, NO threshold and NO per-scene
// decision: it is a projection back onto the feasible set, gated per point by
// its own cost. Points whose triangulation is well conditioned barely move.
__global__ void KernelRetriangulate(const int* __restrict__ cam_idx,
    const int* __restrict__ pt_idx, const Scalar* __restrict__ uv,
    const int* __restrict__ poff, const int* __restrict__ plist,
    const Scalar* __restrict__ R, const Scalar* __restrict__ t,
    const Scalar* __restrict__ f, const Scalar* __restrict__ k1,
    const Scalar* __restrict__ k2, Scalar* __restrict__ X, int npt,
    int* __restrict__ nfixed) {
  int p = blockIdx.x * blockDim.x + threadIdx.x; if (p >= npt) return;
  const int s = poff[p], e = poff[p+1];
  if (e - s < 2) return;                       // need >=2 rays
  // Normal equations of the ray system: sum_i (I - d_i d_i^T) x = sum_i (I - d_i d_i^T) c_i
  // with c_i the camera centre and d_i the unit viewing direction.
  Scalar A[9]={0,0,0,0,0,0,0,0,0}, b[3]={0,0,0};
  for (int k = s; k < e; ++k) {
    const int o = plist[k], c = cam_idx[o];
    const Scalar* Rc = R + 9*c;
    // undistort approximately: invert the radial model by one fixed-point step
    Scalar xn = uv[2*o]/f[c], yn = uv[2*o+1]/f[c];
    Scalar r2 = xn*xn + yn*yn;
    Scalar sc = 1.0 + k1[c]*r2 + k2[c]*r2*r2;
    if (sc > 1e-12) { xn /= sc; yn /= sc; }
    // BAL convention: project with p = -X/Z, so the ray direction in camera
    // frame is (-xn, -yn, 1) normalised; rotate to world by R^T.
    Scalar dc[3] = {-xn, -yn, (Scalar)1.0};
    Scalar d[3];
    for (int i = 0; i < 3; ++i) d[i] = Rc[i]*dc[0] + Rc[3+i]*dc[1] + Rc[6+i]*dc[2];
    Scalar nrm = sqrt(d[0]*d[0]+d[1]*d[1]+d[2]*d[2]); if (!(nrm>1e-12)) continue;
    d[0]/=nrm; d[1]/=nrm; d[2]/=nrm;
    // camera centre c = -R^T t
    Scalar cc[3];
    for (int i = 0; i < 3; ++i) cc[i] = -(Rc[i]*t[3*c+0] + Rc[3+i]*t[3*c+1] + Rc[6+i]*t[3*c+2]);
    for (int i = 0; i < 3; ++i) {
      for (int j = 0; j < 3; ++j) {
        const Scalar m = (i==j ? (Scalar)1.0 : (Scalar)0.0) - d[i]*d[j];
        A[3*i+j] += m;
        b[i]     += m * cc[j];
      }
    }
  }
  // Solve the 3x3 SPD system by Cholesky; bail out if it is not usable.
  Scalar L[9]={0,0,0,0,0,0,0,0,0};
  for (int i = 0; i < 3; ++i)
    for (int j = 0; j <= i; ++j) {
      Scalar sum = (Scalar)0.5*(A[3*i+j]+A[3*j+i]);
      for (int q = 0; q < j; ++q) sum -= L[3*i+q]*L[3*j+q];
      if (i==j) { if (!(sum > 1e-12)) return; L[3*i+j] = sqrt(sum); }
      else       L[3*i+j] = sum / L[3*j+j];
    }
  Scalar y[3], xnew[3];
  for (int i = 0; i < 3; ++i) { Scalar v=b[i]; for (int q=0;q<i;++q) v-=L[3*i+q]*y[q]; y[i]=v/L[3*i+i]; }
  for (int i = 2; i >= 0; --i) { Scalar v=y[i]; for (int q=i+1;q<3;++q) v-=L[3*q+i]*xnew[q]; xnew[i]=v/L[3*i+i]; }
  if (!(isfinite(xnew[0]) && isfinite(xnew[1]) && isfinite(xnew[2]))) return;
  // Accept only if this point's own reprojection cost improves.
  Scalar cold = 0, cnew = 0;
  for (int k = s; k < e; ++k) {
    const int o = plist[k], c = cam_idx[o];
    const Scalar* Rc = R + 9*c;
    for (int which = 0; which < 2; ++which) {
      const Scalar* Xp = which ? xnew : (X + 3*p);
      Scalar Px = Rc[0]*Xp[0]+Rc[1]*Xp[1]+Rc[2]*Xp[2] + t[3*c];
      Scalar Py = Rc[3]*Xp[0]+Rc[4]*Xp[1]+Rc[5]*Xp[2] + t[3*c+1];
      Scalar Pz = Rc[6]*Xp[0]+Rc[7]*Xp[1]+Rc[8]*Xp[2] + t[3*c+2];
      if (!(fabs(Pz) > 1e-12)) { if (which) return; else continue; }
      Scalar xp = -Px/Pz, yp = -Py/Pz, r2 = xp*xp+yp*yp;
      Scalar dist = 1.0 + k1[c]*r2 + k2[c]*r2*r2;
      Scalar rx = f[c]*dist*xp - uv[2*o], ry = f[c]*dist*yp - uv[2*o+1];
      (which ? cnew : cold) += rx*rx + ry*ry;
    }
  }
  if (cnew < cold) {
    X[3*p+0]=xnew[0]; X[3*p+1]=xnew[1]; X[3*p+2]=xnew[2];
    atomicAdd(nfixed, 1);
  }
}

// H_gn must be a valid, distinct (n x n) buffer (never nullptr / aliased to H) --
// the kernel scatters into both every observation, so aliasing would corrupt H
// with Gauss-Newton-only contributions. Callers that don't need H_gn still pass a
// real scratch buffer and simply discard it.
void AssembleGradHess(const DeviceProblem& p, const DeviceState& s, Scalar* grad, Scalar* H, Scalar* H_gn) {
  CUDA_CHECK(cudaMemset(grad, 0, p.n * sizeof(Scalar)));
  CUDA_CHECK(cudaMemset(H, 0, (size_t)p.n * p.n * sizeof(Scalar)));
  CUDA_CHECK(cudaMemset(H_gn, 0, (size_t)p.n * p.n * sizeof(Scalar)));
  KernelAssembleGradHess<<<GridSize(p.nobs), 256>>>(
      p.cam_idx, p.pt_idx, p.uv, s.R, s.t, s.X, p.f, p.k1, p.k2, p.nobs, p.ncam, p.npt, p.n,
      grad, H, H_gn);
}

void Retract(const DeviceProblem& p, const DeviceState& s, const Scalar* d, const DeviceState& out) {
  KernelRetractCameras<<<GridSize(p.ncam), 256>>>(s.R, s.t, d, out.R, out.t, p.ncam);
  KernelRetractPoints<<<GridSize(p.npt), 256>>>(s.X, d, out.X, p.npt, p.ncam);
}

// ---- ROUND 10: 9-DOF retraction. Camera block d[9c..9c+8] = [dw(3), dt(3),
// df, dk1, dk2]; pose part uses the same Exp(dw) R convention, intrinsics are
// additive. Point block starts at 9*ncam.
__global__ void KernelRetractCameras9(const Scalar* __restrict__ R_old, const Scalar* __restrict__ t_old,
                                       const Scalar* __restrict__ intr_old, const Scalar* __restrict__ d,
                                       Scalar* __restrict__ R_new, Scalar* __restrict__ t_new,
                                       Scalar* __restrict__ intr_new, int ncam) {
  int c = blockIdx.x * blockDim.x + threadIdx.x;
  if (c >= ncam) return;
  Scalar dR[9];
  ExpSO3(d + 9 * c, dR);
  Mat3Mul(dR, R_old + 9 * c, R_new + 9 * c);
  for (int i = 0; i < 3; ++i) t_new[3 * c + i] = t_old[3 * c + i] + d[9 * c + 3 + i];
  intr_new[c]          = intr_old[c]          + d[9 * c + 6];  // f
  intr_new[ncam + c]   = intr_old[ncam + c]   + d[9 * c + 7];  // k1
  intr_new[2*ncam + c] = intr_old[2*ncam + c] + d[9 * c + 8];  // k2
}
__global__ void KernelRetractPoints9(const Scalar* __restrict__ X_old, const Scalar* __restrict__ d,
                                      Scalar* __restrict__ X_new, int npt, int ncam) {
  int p = blockIdx.x * blockDim.x + threadIdx.x;
  if (p >= npt) return;
  const Scalar* dp = d + 9 * ncam + 3 * p;
  for (int i = 0; i < 3; ++i) X_new[3 * p + i] = X_old[3 * p + i] + dp[i];
}
void RetractDof9(const DeviceProblem& p, const DeviceState& s, const Scalar* d, const DeviceState& out) {
  KernelRetractCameras9<<<GridSize(p.ncam), 256>>>(s.R, s.t, s.intr, d, out.R, out.t, out.intr, p.ncam);
  KernelRetractPoints9<<<GridSize(p.npt), 256>>>(s.X, d, out.X, p.npt, p.ncam);
}

// Cholesky factorize A (n x n, device, row-major treated as column-major-symmetric --
// A is symmetric so row-major == column-major numerically) via cuSOLVER, then solve
// A x = b in place of b. Returns false (ok=false) if not positive definite (checked
// via cusolver's devInfo), matching reference_oca.py's _cholesky_factor contract.
struct CholeskyWorkspace {
  cusolverDnHandle_t handle;
  Scalar* d_work = nullptr;
  int lwork = 0;
  int* d_info = nullptr;
  int n = 0;
  void Init(cusolverDnHandle_t h, int n_) {
    handle = h; n = n_;
    CUDA_CHECK(cudaMalloc(&d_info, sizeof(int)));
    CUSOLVER_CHECK(cusolverDnDpotrf_bufferSize(handle, CUBLAS_FILL_MODE_LOWER, n, nullptr, n, &lwork));
    CUDA_CHECK(cudaMalloc(&d_work, lwork * sizeof(Scalar)));
  }
};

// Factorizes A in place (overwritten with the Cholesky factor). Returns true if SPD.
bool CholeskyFactor(CholeskyWorkspace& ws, Scalar* A) {
  CUSOLVER_CHECK(cusolverDnDpotrf(ws.handle, CUBLAS_FILL_MODE_LOWER, ws.n, A, ws.n, ws.d_work, ws.lwork, ws.d_info));
  int info;
  CUDA_CHECK(cudaMemcpy(&info, ws.d_info, sizeof(int), cudaMemcpyDeviceToHost));
  return info == 0;
}

// Solves the already-factorized system for rhs (n,) in place -> becomes the solution.
void CholeskySolveVec(CholeskyWorkspace& ws, const Scalar* A_factored, Scalar* rhs) {
  CUSOLVER_CHECK(cusolverDnDpotrs(ws.handle, CUBLAS_FILL_MODE_LOWER, ws.n, 1, A_factored, ws.n, rhs, ws.n, ws.d_info));
}

// fp32 Cholesky path -- SEPARATE from CholeskyWorkspace above, not a global precision change.
// Motivated by direct profiling (not the borrowed "10-50x" estimate from an external cross-model
// synthesis document): on ladybug-598, PD-check+Cholesky measured at 88% of SolveOCAJointLambdaDepth's
// wall-clock (60.4s of 79.6s), dwarfing assembly (0.2%), the recursion (9.5%), and cost evaluation (1.3%).
// Scoped to the GN-Hessian joint-lambda-depth solver specifically, where lambda stays far more modest
// than the true-Hessian/MINRES family's documented extreme escalation (1e14-1e20 elsewhere in this file)
// -- reduced precision is a materially different risk on a well-behaved PSD system than on the
// persistently near-singular systems seen in that other family, but still validated empirically (not
// assumed) below by comparing final cost against the fp64 baseline before being trusted.
struct CholeskyWorkspaceF32 {
  cusolverDnHandle_t handle;
  float* d_work = nullptr;
  int lwork = 0;
  int* d_info = nullptr;
  int n = 0;
  void Init(cusolverDnHandle_t h, int n_) {
    handle = h; n = n_;
    CUDA_CHECK(cudaMalloc(&d_info, sizeof(int)));
    CUSOLVER_CHECK(cusolverDnSpotrf_bufferSize(handle, CUBLAS_FILL_MODE_LOWER, n, nullptr, n, &lwork));
    CUDA_CHECK(cudaMalloc(&d_work, lwork * sizeof(float)));
  }
};
bool CholeskyFactorF32(CholeskyWorkspaceF32& ws, float* A) {
  CUSOLVER_CHECK(cusolverDnSpotrf(ws.handle, CUBLAS_FILL_MODE_LOWER, ws.n, A, ws.n, ws.d_work, ws.lwork, ws.d_info));
  int info;
  CUDA_CHECK(cudaMemcpy(&info, ws.d_info, sizeof(int), cudaMemcpyDeviceToHost));
  return info == 0;
}
void CholeskySolveVecF32(CholeskyWorkspaceF32& ws, const float* A_factored, float* rhs) {
  CUSOLVER_CHECK(cusolverDnSpotrs(ws.handle, CUBLAS_FILL_MODE_LOWER, ws.n, 1, A_factored, ws.n, rhs, ws.n, ws.d_info));
}
__global__ void KernelCastD2F(const double* __restrict__ in, float* __restrict__ out, int n) {
  int i = blockIdx.x*blockDim.x+threadIdx.x; if (i>=n) return; out[i] = (float)in[i];
}
__global__ void KernelCastF2D(const float* __restrict__ in, double* __restrict__ out, int n) {
  int i = blockIdx.x*blockDim.x+threadIdx.x; if (i>=n) return; out[i] = (double)in[i];
}

// ============================================================== Algorithm 1: LM
struct RunLog {
  std::vector<int> iters;
  std::vector<Scalar> costs;
};

// REVIEW 2026-09-02 (code review F5, structure): everything from here to the
// champion is RESEARCH-ERA solvers (24 variants, ~5,600 lines) plus their
// private helpers (Sturm/Tridiag). They are reachable only from the CLI
// dispatch, which already sits behind !OCA_CORE_LIBRARY -- compiling them
// into the embedding library tripled its build time and binary for zero
// callers. Guarded, not deleted: the CLI keeps every variant for experiment
// reproduction.
#ifndef OCA_CORE_LIBRARY
RunLog SolveLM(const DeviceProblem& p, DeviceState& s, Scalar mu0, Scalar tol, int max_iter, bool verbose) {
  int n = p.n;
  Scalar *grad, *H_true, *H_gn, *A, *d;
  CUDA_CHECK(cudaMalloc(&grad, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&H_true, (size_t)n*n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&H_gn, (size_t)n*n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&A, (size_t)n*n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&d, n*sizeof(Scalar)));
  DeviceState s_new; AllocState(s_new, p.ncam, p.npt);

  cusolverDnHandle_t handle; cusolverDnCreate(&handle);
  CholeskyWorkspace ws; ws.Init(handle, n);

  std::vector<Scalar> h_grad(n), h_Hgn(n*(size_t)n), h_d(n);

  Scalar mu = mu0;
  Scalar cost = ComputeCost(p, s);
  RunLog log; log.iters.push_back(0); log.costs.push_back(cost);

  for (int k = 0; k < max_iter; ++k) {
    AssembleGradHess(p, s, grad, H_true, H_gn);
    CUDA_CHECK(cudaMemcpy(A, H_gn, (size_t)n*n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
    KernelAddDiag<<<GridSize(n),256>>>(A, n, mu);
    // Solve A d = -grad  =>  d = -(A^-1 grad). Copy grad into d (rhs), Cholesky-solve, negate.
    CUDA_CHECK(cudaMemcpy(d, grad, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
    if (!CholeskyFactor(ws, A)) {
      std::fprintf(stderr, "LM: (H_gn + mu*I) not PD at k=%d -- should not happen (Gauss-Newton PSD + mu*I>0)\n", k);
      std::exit(EXIT_FAILURE);
    }
    CholeskySolveVec(ws, A, d);
    // negate d: d := -d
    {
      std::vector<Scalar> tmp(n);
      CUDA_CHECK(cudaMemcpy(tmp.data(), d, n*sizeof(Scalar), cudaMemcpyDeviceToHost));
      for (auto& v : tmp) v = -v;
      CUDA_CHECK(cudaMemcpy(d, tmp.data(), n*sizeof(Scalar), cudaMemcpyHostToDevice));
    }

    Retract(p, s, d, s_new);
    Scalar cost_new = ComputeCost(p, s_new);

    // predicted decrease from the LOCAL Gauss-Newton quadratic model, Eq.3-4:
    // P(d) = cost + grad.d + 0.5 d^T H_gn d  (host-side small reduction over n)
    CUDA_CHECK(cudaMemcpy(h_grad.data(), grad, n*sizeof(Scalar), cudaMemcpyDeviceToHost));
    CUDA_CHECK(cudaMemcpy(h_Hgn.data(), H_gn, (size_t)n*n*sizeof(Scalar), cudaMemcpyDeviceToHost));
    CUDA_CHECK(cudaMemcpy(h_d.data(), d, n*sizeof(Scalar), cudaMemcpyDeviceToHost));
    Scalar grad_dot_d = 0.0;
    for (int i = 0; i < n; ++i) grad_dot_d += h_grad[i] * h_d[i];
    Scalar quad = 0.0;
    for (int i = 0; i < n; ++i) {
      Scalar Hd_i = 0.0;
      for (int j = 0; j < n; ++j) Hd_i += h_Hgn[(size_t)i*n+j] * h_d[j];
      quad += h_d[i] * Hd_i;
    }
    Scalar pred_decrease = -(grad_dot_d + 0.5 * quad);
    Scalar actual_decrease = cost - cost_new;
    Scalar xi = (std::fabs(pred_decrease) > 1e-300) ? actual_decrease / pred_decrease : 0.0;

    Scalar step_norm = 0.0;
    for (int i = 0; i < n; ++i) step_norm += h_d[i]*h_d[i];
    step_norm = std::sqrt(step_norm);

    // Algorithm 1 ALWAYS accepts the step (matches reference_oca.py's solve_lm exactly
    // -- no rejection gate on xi, only used to adapt mu).
    std::swap(s.R, s_new.R); std::swap(s.t, s_new.t); std::swap(s.X, s_new.X);
    cost = cost_new;
    if (xi < 0.25) mu *= 10.0; else if (xi > 0.75) mu *= 0.1;

    log.iters.push_back(k+1); log.costs.push_back(cost);
    if (verbose) std::printf("  LM it%4d cost=%.6e mu=%.3e xi=%.3f |d|=%.3e\n", k+1, cost, mu, xi, step_norm);
    if (step_norm < tol) break;
  }

  cusolverDnDestroy(handle);
  cudaFree(grad); cudaFree(H_true); cudaFree(H_gn); cudaFree(A); cudaFree(d);
  cudaFree(s_new.R); cudaFree(s_new.t); cudaFree(s_new.X);
  return log;
}

// ============================================================== Algorithm 2: OCA (fixed lam)
RunLog SolveOCA(const DeviceProblem& p, DeviceState& s, Scalar lam, Scalar tol, int max_iter, bool verbose) {
  int n = p.n;
  Scalar *grad, *H, *H_dummy, *A, *g_prev, *rhs, *d;
  CUDA_CHECK(cudaMalloc(&grad, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&H, (size_t)n*n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&H_dummy, (size_t)n*n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&A, (size_t)n*n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&g_prev, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&rhs, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&d, n*sizeof(Scalar)));
  DeviceState s_new; AllocState(s_new, p.ncam, p.npt);

  cusolverDnHandle_t handle; cusolverDnCreate(&handle);
  CholeskyWorkspace ws; ws.Init(handle, n);

  Scalar cost = ComputeCost(p, s);
  RunLog log; log.iters.push_back(0); log.costs.push_back(cost);

  for (int k = 0; k < max_iter; ++k) {
    AssembleGradHess(p, s, grad, H, H_dummy);
    CUDA_CHECK(cudaMemcpy(A, H, (size_t)n*n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
    KernelAddDiag<<<GridSize(n),256>>>(A, n, lam);
    if (!CholeskyFactor(ws, A)) {
      std::fprintf(stderr, "OCA (fixed lam=%.4g): (lam*I+H) not PD at outer iter k=%d -- "
                            "increase lam or use --algo oca_adaptive\n", lam, k);
      std::exit(EXIT_FAILURE);
    }
    // g_0 = A^-1 grad
    CUDA_CHECK(cudaMemcpy(g_prev, grad, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
    CholeskySolveVec(ws, A, g_prev);
    // g_j = A^-1 (grad + lam*g_{j-1}) for j=1..k, reusing the SAME factorization
    for (int j = 1; j <= k; ++j) {
      CUDA_CHECK(cudaMemcpy(rhs, grad, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      KernelAxpy<<<GridSize(n),256>>>(rhs, g_prev, lam, n);
      CholeskySolveVec(ws, A, rhs);
      std::swap(g_prev, rhs);
    }
    // d = -g_prev
    {
      std::vector<Scalar> tmp(n);
      CUDA_CHECK(cudaMemcpy(tmp.data(), g_prev, n*sizeof(Scalar), cudaMemcpyDeviceToHost));
      for (auto& v : tmp) v = -v;
      CUDA_CHECK(cudaMemcpy(d, tmp.data(), n*sizeof(Scalar), cudaMemcpyHostToDevice));
    }
    Retract(p, s, d, s_new);
    std::swap(s.R, s_new.R); std::swap(s.t, s_new.t); std::swap(s.X, s_new.X);
    cost = ComputeCost(p, s);

    std::vector<Scalar> h_d(n);
    CUDA_CHECK(cudaMemcpy(h_d.data(), d, n*sizeof(Scalar), cudaMemcpyDeviceToHost));
    Scalar step_norm = 0.0; for (auto v : h_d) step_norm += v*v; step_norm = std::sqrt(step_norm);

    log.iters.push_back(k+1); log.costs.push_back(cost);
    if (verbose) std::printf("  OCA it%4d cost=%.6e inner_steps=%d |d|=%.3e\n", k+1, cost, k+1, step_norm);
    if (step_norm < tol) break;
  }

  cusolverDnDestroy(handle);
  cudaFree(grad); cudaFree(H); cudaFree(H_dummy); cudaFree(A); cudaFree(g_prev); cudaFree(rhs); cudaFree(d);
  cudaFree(s_new.R); cudaFree(s_new.t); cudaFree(s_new.X);
  return log;
}

// ============================================================== Algorithm 3: OCA adaptive lam
// Inner solve helper: returns ok=false if (lam*I+H) is not PD (a legitimate outcome
// -- the true Hessian isn't guaranteed PSD -- matching reference_oca.py's inner_solve).
// g_prev_rhs/rhs_scratch are taken BY REFERENCE: the j-loop below repeatedly swaps
// which buffer holds "the latest g_j" vs. "scratch", and for odd k the final answer
// ends up in what was originally the scratch buffer -- by-reference parameters make
// that swap visible to the caller too, so the caller's own variable always names
// whichever buffer actually holds the current result (by-value pointer args would
// silently leave the caller reading stale data whenever k is odd).
bool InnerSolve(CholeskyWorkspace& ws, const Scalar* H, Scalar* A_scratch, int n, Scalar lam,
                 const Scalar* grad, Scalar*& g_prev_rhs, Scalar*& rhs_scratch, int k) {
  CUDA_CHECK(cudaMemcpy(A_scratch, H, (size_t)n*n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
  KernelAddDiag<<<GridSize(n),256>>>(A_scratch, n, lam);
  if (!CholeskyFactor(ws, A_scratch)) return false;
  CUDA_CHECK(cudaMemcpy(g_prev_rhs, grad, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
  CholeskySolveVec(ws, A_scratch, g_prev_rhs);
  for (int j = 1; j <= k; ++j) {
    CUDA_CHECK(cudaMemcpy(rhs_scratch, grad, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
    KernelAxpy<<<GridSize(n),256>>>(rhs_scratch, g_prev_rhs, lam, n);
    CholeskySolveVec(ws, A_scratch, rhs_scratch);
    std::swap(g_prev_rhs, rhs_scratch);
  }
  return true;
}

Scalar CostAfterStep(const DeviceProblem& p, const DeviceState& s, const Scalar* g, DeviceState& s_tmp) {
  int n = p.n;
  std::vector<Scalar> tmp(n);
  CUDA_CHECK(cudaMemcpy(tmp.data(), g, n*sizeof(Scalar), cudaMemcpyDeviceToHost));
  for (auto& v : tmp) v = -v;
  Scalar* d; CUDA_CHECK(cudaMalloc(&d, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMemcpy(d, tmp.data(), n*sizeof(Scalar), cudaMemcpyHostToDevice));
  Retract(p, s, d, s_tmp);
  Scalar c = ComputeCost(p, s_tmp);
  cudaFree(d);
  return c;
}

RunLog SolveOCAAdaptive(const DeviceProblem& p, DeviceState& s, Scalar lam0, Scalar lam1,
                         Scalar tol, int max_iter, bool verbose) {
  int n = p.n;
  Scalar *grad, *H, *H_dummy, *A, *g_k, *g_c, *rhs_a, *rhs_b, *d;
  CUDA_CHECK(cudaMalloc(&grad, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&H, (size_t)n*n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&H_dummy, (size_t)n*n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&A, (size_t)n*n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&g_k, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&g_c, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&rhs_a, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&rhs_b, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&d, n*sizeof(Scalar)));
  DeviceState s_new; AllocState(s_new, p.ncam, p.npt);
  DeviceState s_tmp; AllocState(s_tmp, p.ncam, p.npt);

  cusolverDnHandle_t handle; cusolverDnCreate(&handle);
  CholeskyWorkspace ws; ws.Init(handle, n);

  Scalar cost = ComputeCost(p, s);
  RunLog log; log.iters.push_back(0); log.costs.push_back(cost);
  Scalar lam_prev = lam0;

  for (int k = 0; k < max_iter; ++k) {
    AssembleGradHess(p, s, grad, H, H_dummy);
    Scalar lam_k;
    if (k <= 1) {
      lam_k = (k == 0) ? lam0 : lam1;
      bool ok = InnerSolve(ws, H, A, n, lam_k, grad, g_k, rhs_a, k);
      if (!ok) {
        std::fprintf(stderr, "OCA-adaptive: (R+H) indefinite at k=%d with fixed lam=%.4g "
                              "(no bisection runs for k<=1) -- increase lam0/lam1\n", k, lam_k);
        std::exit(EXIT_FAILURE);
      }
    } else {
      lam_k = lam_prev;
      bool ok = InnerSolve(ws, H, A, n, lam_k, grad, g_k, rhs_a, k);
      if (!ok) {
        std::fprintf(stderr, "OCA-adaptive: (R+H) indefinite at k=%d even at previous lam=%.4g\n", k, lam_k);
        std::exit(EXIT_FAILURE);
      }
      Scalar cost1 = CostAfterStep(p, s, g_k, s_tmp);
      Scalar a = 0.0, b = lam_prev, c = b;
      while ((b - a) > 0.1) {
        c = (a + b) / 2.0;
        bool ok_c = InnerSolve(ws, H, A, n, c, grad, g_c, rhs_b, k);
        Scalar cost2 = ok_c ? CostAfterStep(p, s, g_c, s_tmp) : std::numeric_limits<Scalar>::infinity();
        if (!ok_c) { a = c; continue; }
        if (cost1 > cost2) {
          b = c; cost1 = cost2;
          CUDA_CHECK(cudaMemcpy(g_k, g_c, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
        } else if (cost1 < cost2) {
          a = c; cost1 = cost2;
          CUDA_CHECK(cudaMemcpy(g_k, g_c, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
        } else {
          break;
        }
      }
      if ((b - a) <= 0.1) lam_k = c;
    }

    {
      std::vector<Scalar> tmp(n);
      CUDA_CHECK(cudaMemcpy(tmp.data(), g_k, n*sizeof(Scalar), cudaMemcpyDeviceToHost));
      for (auto& v : tmp) v = -v;
      CUDA_CHECK(cudaMemcpy(d, tmp.data(), n*sizeof(Scalar), cudaMemcpyHostToDevice));
    }
    Retract(p, s, d, s_new);
    std::swap(s.R, s_new.R); std::swap(s.t, s_new.t); std::swap(s.X, s_new.X);
    cost = ComputeCost(p, s);
    lam_prev = lam_k;

    std::vector<Scalar> h_d(n);
    CUDA_CHECK(cudaMemcpy(h_d.data(), d, n*sizeof(Scalar), cudaMemcpyDeviceToHost));
    Scalar step_norm = 0.0; for (auto v : h_d) step_norm += v*v; step_norm = std::sqrt(step_norm);

    log.iters.push_back(k+1); log.costs.push_back(cost);
    if (verbose) std::printf("  OCA-adapt it%4d cost=%.6e lam=%.3e |d|=%.3e\n", k+1, cost, lam_k, step_norm);
    if (step_norm < tol) break;
  }

  cusolverDnDestroy(handle);
  cudaFree(grad); cudaFree(H); cudaFree(H_dummy); cudaFree(A); cudaFree(g_k); cudaFree(g_c); cudaFree(rhs_a); cudaFree(rhs_b); cudaFree(d);
  cudaFree(s_new.R); cudaFree(s_new.t); cudaFree(s_new.X);
  cudaFree(s_tmp.R); cudaFree(s_tmp.t); cudaFree(s_tmp.X);
  return log;
}

// ============================================================== Schur-complement factorize/solve (host)
// Factorizes (lam*I+H) once via the Schur reduction (App^-1 for all NP point
// blocks + Cholesky(S) for the n_c x n_c reduced camera system) -- reused for
// all k+1 inner-recursion solves in the calling outer iteration, exactly like
// the dense path reuses its one big Cholesky factor, just against a much
// smaller factorization.
struct SchurFactorization {
  Scalar *Hcp_full = nullptr, *App_inv_full = nullptr, *S = nullptr;  // column-major
  int n_c = 0, n_p = 0;
};

void AllocSchurFactorization(SchurFactorization& sf, int n_c, int n_p) {
  sf.n_c = n_c; sf.n_p = n_p;
  CUDA_CHECK(cudaMalloc(&sf.Hcp_full, (size_t)n_c*n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&sf.App_inv_full, (size_t)n_p*n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&sf.S, (size_t)n_c*n_c*sizeof(Scalar)));
}

void FreeSchurFactorization(SchurFactorization& sf) {
  cudaFree(sf.Hcp_full); cudaFree(sf.App_inv_full); cudaFree(sf.S);
}

// Returns false (indefinite, matching reference_oca_schur.py's Haynsworth-theorem
// contract: A is PD iff every App block is PD AND S is PD) without touching sf.S
// further -- caller must not attempt SchurSolveVec after a false return.
bool SchurFactorizeSystem(cublasHandle_t blas, CholeskyWorkspace& ws_s,
                           const Scalar* Hcc, const Scalar* Hpp, const Scalar* Hcp_full_src,
                           Scalar lam, int ncam, int npt, SchurFactorization& sf,
                           Scalar* App_inv_blocks, int* ok_flags, Scalar* Acc_full, Scalar* T1) {
  int n_c = sf.n_c, n_p = sf.n_p;
  CUDA_CHECK(cudaMemcpy(sf.Hcp_full, Hcp_full_src, (size_t)n_c*n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));

  KernelInvertAppBlocks<<<GridSize(npt),256>>>(Hpp, lam, App_inv_blocks, ok_flags, npt);
  std::vector<int> h_ok(npt);
  CUDA_CHECK(cudaMemcpy(h_ok.data(), ok_flags, npt*sizeof(int), cudaMemcpyDeviceToHost));
  for (int p = 0; p < npt; ++p) if (!h_ok[p]) return false;  // App not PD -> A not PD (Haynsworth)
  CUDA_CHECK(cudaMemset(sf.App_inv_full, 0, (size_t)n_p*n_p*sizeof(Scalar)));
  KernelBuildAppInvFull<<<GridSize(npt),256>>>(App_inv_blocks, sf.App_inv_full, npt, n_p);

  CUDA_CHECK(cudaMemset(Acc_full, 0, (size_t)n_c*n_c*sizeof(Scalar)));
  KernelBuildAccFull<<<GridSize(ncam),256>>>(Hcc, lam, Acc_full, ncam, n_c);

  const Scalar one = 1.0, zero = 0.0, neg_one = -1.0;
  // T1 (n_c x n_p) = Hcp_full (n_c x n_p) @ App_inv_full (n_p x n_p)
  CUBLAS_CHECK(cublasDgemm(blas, CUBLAS_OP_N, CUBLAS_OP_N, n_c, n_p, n_p,
                            &one, sf.Hcp_full, n_c, sf.App_inv_full, n_p, &zero, T1, n_c));
  // S = Acc_full - T1 @ Hcp_full^T
  CUDA_CHECK(cudaMemcpy(sf.S, Acc_full, (size_t)n_c*n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
  CUBLAS_CHECK(cublasDgemm(blas, CUBLAS_OP_N, CUBLAS_OP_T, n_c, n_c, n_p,
                            &neg_one, T1, n_c, sf.Hcp_full, n_c, &one, sf.S, n_c));

  return CholeskyFactor(ws_s, sf.S);  // false => S not PD -> A not PD (Haynsworth)
}

// Solves (lam*I+H) x = b (b = [bc(n_c); bp(n_p)]) using a factorization from
// SchurFactorizeSystem. x written as a flat n_c+n_p device vector, camera
// block first -- same ordering the dense path and Retract already use.
void SchurSolveVec(cublasHandle_t blas, CholeskyWorkspace& ws_s, const SchurFactorization& sf,
                    const Scalar* b, Scalar* x, Scalar* scratch_p /* n_p */) {
  int n_c = sf.n_c, n_p = sf.n_p;
  const Scalar* bc = b; const Scalar* bp = b + n_c;
  Scalar* xc = x; Scalar* xp = x + n_c;
  const Scalar one = 1.0, zero = 0.0, neg_one = -1.0;

  // bp' = App_inv_full @ bp
  CUBLAS_CHECK(cublasDgemv(blas, CUBLAS_OP_N, n_p, n_p, &one, sf.App_inv_full, n_p, bp, 1, &zero, scratch_p, 1));
  // xc (used as scratch for bc') = bc - Hcp_full @ bp'
  CUDA_CHECK(cudaMemcpy(xc, bc, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
  CUBLAS_CHECK(cublasDgemv(blas, CUBLAS_OP_N, n_c, n_p, &neg_one, sf.Hcp_full, n_c, scratch_p, 1, &one, xc, 1));
  // xc = S^-1 @ bc'  (in place)
  CholeskySolveVec(ws_s, sf.S, xc);
  // xp = App_inv_full @ (bp - Hcp_full^T @ xc)
  CUDA_CHECK(cudaMemcpy(scratch_p, bp, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));
  CUBLAS_CHECK(cublasDgemv(blas, CUBLAS_OP_T, n_c, n_p, &neg_one, sf.Hcp_full, n_c, xc, 1, &one, scratch_p, 1));
  CUBLAS_CHECK(cublasDgemv(blas, CUBLAS_OP_N, n_p, n_p, &one, sf.App_inv_full, n_p, scratch_p, 1, &zero, xp, 1));
}

// ============================================================== Algorithm 2/3: OCA via Schur complement
RunLog SolveOCASchur(const DeviceProblem& p, DeviceState& s, Scalar lam, Scalar tol, int max_iter, bool verbose) {
  int ncam = p.ncam, npt = p.npt, n_c = 6*ncam, n_p = 3*npt, n = n_c + n_p;
  Scalar *Hcc, *Hpp, *Hcp_full, *grad_c, *grad_p, *grad, *App_inv_blocks, *Acc_full, *T1, *scratch_p, *g_prev, *rhs, *d;
  int* ok_flags;
  CUDA_CHECK(cudaMalloc(&Hcc, 36*(size_t)ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&Hpp, 9*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&Hcp_full, (size_t)n_c*n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&grad_c, 6*(size_t)ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&grad_p, 3*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&grad, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&App_inv_blocks, 9*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&Acc_full, (size_t)n_c*n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&T1, (size_t)n_c*n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&scratch_p, n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&g_prev, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&rhs, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&d, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&ok_flags, npt*sizeof(int)));
  DeviceState s_new; AllocState(s_new, ncam, npt);

  cusolverDnHandle_t handle; cusolverDnCreate(&handle);
  CholeskyWorkspace ws_s; ws_s.Init(handle, n_c);
  cublasHandle_t blas; cublasCreate(&blas);
  SchurFactorization sf; AllocSchurFactorization(sf, n_c, n_p);

  Scalar cost = ComputeCost(p, s);
  RunLog log; log.iters.push_back(0); log.costs.push_back(cost);

  for (int k = 0; k < max_iter; ++k) {
    CUDA_CHECK(cudaMemset(Hcc, 0, 36*(size_t)ncam*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(Hpp, 0, 9*(size_t)npt*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(Hcp_full, 0, (size_t)n_c*n_p*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(grad_c, 0, 6*(size_t)ncam*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(grad_p, 0, 3*(size_t)npt*sizeof(Scalar)));
    KernelAssembleSchurBlocks<<<GridSize(p.nobs),256>>>(
        p.cam_idx, p.pt_idx, p.uv, s.R, s.t, s.X, p.f, p.k1, p.k2, p.nobs, ncam, npt, n_c,
        Hcc, Hpp, Hcp_full, grad_c, grad_p);
    CUDA_CHECK(cudaMemcpy(grad, grad_c, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
    CUDA_CHECK(cudaMemcpy(grad+n_c, grad_p, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));

    if (!SchurFactorizeSystem(blas, ws_s, Hcc, Hpp, Hcp_full, lam, ncam, npt, sf,
                               App_inv_blocks, ok_flags, Acc_full, T1)) {
      std::fprintf(stderr, "OCA-Schur (fixed lam=%.4g): (lam*I+H) not PD at outer iter k=%d -- "
                            "increase lam or use --algo oca_adaptive_schur\n", lam, k);
      std::exit(EXIT_FAILURE);
    }
    SchurSolveVec(blas, ws_s, sf, grad, g_prev, scratch_p);  // g_0
    for (int j = 1; j <= k; ++j) {
      CUDA_CHECK(cudaMemcpy(rhs, grad, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      KernelAxpy<<<GridSize(n),256>>>(rhs, g_prev, lam, n);
      SchurSolveVec(blas, ws_s, sf, rhs, g_prev, scratch_p);  // g_j (overwrite g_prev)
    }
    {
      std::vector<Scalar> tmp(n);
      CUDA_CHECK(cudaMemcpy(tmp.data(), g_prev, n*sizeof(Scalar), cudaMemcpyDeviceToHost));
      for (auto& v : tmp) v = -v;
      CUDA_CHECK(cudaMemcpy(d, tmp.data(), n*sizeof(Scalar), cudaMemcpyHostToDevice));
    }
    Retract(p, s, d, s_new);
    std::swap(s.R, s_new.R); std::swap(s.t, s_new.t); std::swap(s.X, s_new.X);
    cost = ComputeCost(p, s);

    std::vector<Scalar> h_d(n);
    CUDA_CHECK(cudaMemcpy(h_d.data(), d, n*sizeof(Scalar), cudaMemcpyDeviceToHost));
    Scalar step_norm = 0.0; for (auto v : h_d) step_norm += v*v; step_norm = std::sqrt(step_norm);

    log.iters.push_back(k+1); log.costs.push_back(cost);
    if (verbose) std::printf("  OCA-Schur it%4d cost=%.6e inner_steps=%d |d|=%.3e\n", k+1, cost, k+1, step_norm);
    if (step_norm < tol) break;
  }

  cusolverDnDestroy(handle); cublasDestroy(blas);
  FreeSchurFactorization(sf);
  cudaFree(Hcc); cudaFree(Hpp); cudaFree(Hcp_full); cudaFree(grad_c); cudaFree(grad_p); cudaFree(grad);
  cudaFree(App_inv_blocks); cudaFree(Acc_full); cudaFree(T1); cudaFree(scratch_p);
  cudaFree(g_prev); cudaFree(rhs); cudaFree(d); cudaFree(ok_flags);
  cudaFree(s_new.R); cudaFree(s_new.t); cudaFree(s_new.X);
  return log;
}

RunLog SolveOCAAdaptiveSchur(const DeviceProblem& p, DeviceState& s, Scalar lam0, Scalar lam1,
                              Scalar tol, int max_iter, bool verbose) {
  int ncam = p.ncam, npt = p.npt, n_c = 6*ncam, n_p = 3*npt, n = n_c + n_p;
  Scalar *Hcc, *Hpp, *Hcp_full, *grad_c, *grad_p, *grad, *App_inv_blocks, *Acc_full, *T1, *scratch_p;
  Scalar *g_k, *g_c, *d;
  int* ok_flags;
  CUDA_CHECK(cudaMalloc(&Hcc, 36*(size_t)ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&Hpp, 9*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&Hcp_full, (size_t)n_c*n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&grad_c, 6*(size_t)ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&grad_p, 3*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&grad, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&App_inv_blocks, 9*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&Acc_full, (size_t)n_c*n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&T1, (size_t)n_c*n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&scratch_p, n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&g_k, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&g_c, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&d, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&ok_flags, npt*sizeof(int)));
  DeviceState s_new; AllocState(s_new, ncam, npt);
  DeviceState s_tmp; AllocState(s_tmp, ncam, npt);

  cusolverDnHandle_t handle; cusolverDnCreate(&handle);
  CholeskyWorkspace ws_s; ws_s.Init(handle, n_c);
  cublasHandle_t blas; cublasCreate(&blas);
  SchurFactorization sf; AllocSchurFactorization(sf, n_c, n_p);
  Scalar* rhs; CUDA_CHECK(cudaMalloc(&rhs, n*sizeof(Scalar)));

  auto inner_solve = [&](Scalar lam_val, int k, Scalar* out) -> bool {
    if (!SchurFactorizeSystem(blas, ws_s, Hcc, Hpp, Hcp_full, lam_val, ncam, npt, sf,
                               App_inv_blocks, ok_flags, Acc_full, T1))
      return false;
    SchurSolveVec(blas, ws_s, sf, grad, out, scratch_p);
    for (int j = 1; j <= k; ++j) {
      CUDA_CHECK(cudaMemcpy(rhs, grad, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      KernelAxpy<<<GridSize(n),256>>>(rhs, out, lam_val, n);
      SchurSolveVec(blas, ws_s, sf, rhs, out, scratch_p);
    }
    return true;
  };

  Scalar cost = ComputeCost(p, s);
  RunLog log; log.iters.push_back(0); log.costs.push_back(cost);
  Scalar lam_prev = lam0;

  for (int k = 0; k < max_iter; ++k) {
    CUDA_CHECK(cudaMemset(Hcc, 0, 36*(size_t)ncam*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(Hpp, 0, 9*(size_t)npt*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(Hcp_full, 0, (size_t)n_c*n_p*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(grad_c, 0, 6*(size_t)ncam*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(grad_p, 0, 3*(size_t)npt*sizeof(Scalar)));
    KernelAssembleSchurBlocks<<<GridSize(p.nobs),256>>>(
        p.cam_idx, p.pt_idx, p.uv, s.R, s.t, s.X, p.f, p.k1, p.k2, p.nobs, ncam, npt, n_c,
        Hcc, Hpp, Hcp_full, grad_c, grad_p);
    CUDA_CHECK(cudaMemcpy(grad, grad_c, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
    CUDA_CHECK(cudaMemcpy(grad+n_c, grad_p, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));

    Scalar lam_k;
    if (k <= 1) {
      lam_k = (k == 0) ? lam0 : lam1;
      if (!inner_solve(lam_k, k, g_k)) {
        std::fprintf(stderr, "OCA-Schur-adaptive: (R+H) indefinite at k=%d with fixed lam=%.4g "
                              "(no bisection runs for k<=1) -- increase lam0/lam1\n", k, lam_k);
        std::exit(EXIT_FAILURE);
      }
    } else {
      lam_k = lam_prev;
      if (!inner_solve(lam_k, k, g_k)) {
        std::fprintf(stderr, "OCA-Schur-adaptive: (R+H) indefinite at k=%d even at previous lam=%.4g\n", k, lam_k);
        std::exit(EXIT_FAILURE);
      }
      Scalar cost1 = CostAfterStep(p, s, g_k, s_tmp);
      Scalar a = 0.0, b = lam_prev, c = b;
      while ((b - a) > 0.1) {
        c = (a + b) / 2.0;
        bool ok_c = inner_solve(c, k, g_c);
        Scalar cost2 = ok_c ? CostAfterStep(p, s, g_c, s_tmp) : std::numeric_limits<Scalar>::infinity();
        if (!ok_c) { a = c; continue; }
        if (cost1 > cost2) {
          b = c; cost1 = cost2;
          CUDA_CHECK(cudaMemcpy(g_k, g_c, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
        } else if (cost1 < cost2) {
          a = c; cost1 = cost2;
          CUDA_CHECK(cudaMemcpy(g_k, g_c, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
        } else {
          break;
        }
      }
      if ((b - a) <= 0.1) lam_k = c;
    }

    {
      std::vector<Scalar> tmp(n);
      CUDA_CHECK(cudaMemcpy(tmp.data(), g_k, n*sizeof(Scalar), cudaMemcpyDeviceToHost));
      for (auto& v : tmp) v = -v;
      CUDA_CHECK(cudaMemcpy(d, tmp.data(), n*sizeof(Scalar), cudaMemcpyHostToDevice));
    }
    Retract(p, s, d, s_new);
    std::swap(s.R, s_new.R); std::swap(s.t, s_new.t); std::swap(s.X, s_new.X);
    cost = ComputeCost(p, s);
    lam_prev = lam_k;

    std::vector<Scalar> h_d(n);
    CUDA_CHECK(cudaMemcpy(h_d.data(), d, n*sizeof(Scalar), cudaMemcpyDeviceToHost));
    Scalar step_norm = 0.0; for (auto v : h_d) step_norm += v*v; step_norm = std::sqrt(step_norm);

    log.iters.push_back(k+1); log.costs.push_back(cost);
    if (verbose) std::printf("  OCA-Schur-adapt it%4d cost=%.6e lam=%.3e |d|=%.3e\n", k+1, cost, lam_k, step_norm);
    if (step_norm < tol) break;
  }

  cusolverDnDestroy(handle); cublasDestroy(blas);
  FreeSchurFactorization(sf);
  cudaFree(Hcc); cudaFree(Hpp); cudaFree(Hcp_full); cudaFree(grad_c); cudaFree(grad_p); cudaFree(grad);
  cudaFree(App_inv_blocks); cudaFree(Acc_full); cudaFree(T1); cudaFree(scratch_p);
  cudaFree(g_k); cudaFree(g_c); cudaFree(d); cudaFree(ok_flags); cudaFree(rhs);
  cudaFree(s_new.R); cudaFree(s_new.t); cudaFree(s_new.X);
  cudaFree(s_tmp.R); cudaFree(s_tmp.t); cudaFree(s_tmp.X);
  return log;
}

// ============================================================== Algorithm 2/3: OCA via sparse per-point Schur (Phase 4b)
// Requires p.point_obs_offsets/point_obs_list to be populated (see main()).
// No cuBLAS needed here -- the sparse kernels replace the dense GEMMs
// entirely; only cuSOLVER (for the small n_c x n_c reduced system) is used.
RunLog SolveOCASchurSparse(const DeviceProblem& p, DeviceState& s, Scalar lam, Scalar tol, int max_iter, bool verbose) {
  int ncam = p.ncam, npt = p.npt, n_c = 6*ncam, n_p = 3*npt, n = n_c + n_p;
  Scalar *Hcc, *Hpp, *obs_Hcp, *grad_c, *grad_p, *App_inv, *S;
  Scalar *bc_corr, *bc_prime, *xc, *xp, *gc_prev, *gp_prev, *bp_j, *bc_j, *d;
  int* ok_flags;
  CUDA_CHECK(cudaMalloc(&Hcc, 36*(size_t)ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&Hpp, 9*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&obs_Hcp, 18*(size_t)p.nobs*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&grad_c, 6*(size_t)ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&grad_p, 3*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&App_inv, 9*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&S, (size_t)n_c*n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bc_corr, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bc_prime, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&xc, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&xp, n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&gc_prev, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&gp_prev, n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bp_j, n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bc_j, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&d, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&ok_flags, npt*sizeof(int)));
  DeviceState s_new; AllocState(s_new, ncam, npt);

  cusolverDnHandle_t handle; cusolverDnCreate(&handle);
  CholeskyWorkspace ws; ws.Init(handle, n_c);

  Scalar cost = ComputeCost(p, s);
  RunLog log; log.iters.push_back(0); log.costs.push_back(cost);

  for (int k = 0; k < max_iter; ++k) {
    CUDA_CHECK(cudaMemset(Hcc, 0, 36*(size_t)ncam*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(Hpp, 0, 9*(size_t)npt*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(grad_c, 0, 6*(size_t)ncam*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(grad_p, 0, 3*(size_t)npt*sizeof(Scalar)));
    KernelAssembleSchurSparse<<<GridSize(p.nobs),256>>>(
        p.cam_idx, p.pt_idx, p.uv, s.R, s.t, s.X, p.f, p.k1, p.k2, p.nobs,
        Hcc, Hpp, obs_Hcp, grad_c, grad_p);
    KernelInvertAppBlocks<<<GridSize(npt),256>>>(Hpp, lam, App_inv, ok_flags, npt);
    { std::vector<int> h_ok(npt);
      CUDA_CHECK(cudaMemcpy(h_ok.data(), ok_flags, npt*sizeof(int), cudaMemcpyDeviceToHost));
      for (int v : h_ok) if (!v) {
        std::fprintf(stderr, "OCA-Schur-sparse (fixed lam=%.4g): (lam*I+H) not PD at k=%d\n", lam, k);
        std::exit(EXIT_FAILURE);
      }
    }
    CUDA_CHECK(cudaMemset(S, 0, (size_t)n_c*n_c*sizeof(Scalar)));
    KernelBuildAccFull<<<GridSize(ncam),256>>>(Hcc, lam, S, ncam, n_c);
    KernelFormSSparse<<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                              App_inv, npt, n_c, S);
    if (!CholeskyFactor(ws, S)) {
      std::fprintf(stderr, "OCA-Schur-sparse (fixed lam=%.4g): reduced system not PD at k=%d\n", lam, k);
      std::exit(EXIT_FAILURE);
    }

    CUDA_CHECK(cudaMemset(gc_prev, 0, n_c*sizeof(Scalar)));
    for (int j = 0; j <= k; ++j) {
      CUDA_CHECK(cudaMemcpy(bp_j, grad_p, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      CUDA_CHECK(cudaMemcpy(bc_j, grad_c, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      if (j > 0) {
        KernelAxpy<<<GridSize(n_p),256>>>(bp_j, gp_prev, lam, n_p);
        KernelAxpy<<<GridSize(n_c),256>>>(bc_j, gc_prev, lam, n_c);
      }
      CUDA_CHECK(cudaMemset(bc_corr, 0, n_c*sizeof(Scalar)));
      KernelRHSCorrectionSparse<<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                                         App_inv, bp_j, npt, bc_corr);
      KernelSubtractVec<<<GridSize(n_c),256>>>(bc_prime, bc_j, bc_corr, n_c);
      CUDA_CHECK(cudaMemcpy(xc, bc_prime, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      CholeskySolveVec(ws, S, xc);
      KernelBackSubstituteSparse<<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                                          App_inv, bp_j, xc, npt, xp);
      CUDA_CHECK(cudaMemcpy(gc_prev, xc, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      CUDA_CHECK(cudaMemcpy(gp_prev, xp, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));
    }
    CUDA_CHECK(cudaMemcpy(d, gc_prev, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
    CUDA_CHECK(cudaMemcpy(d+n_c, gp_prev, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));
    { std::vector<Scalar> tmp(n);
      CUDA_CHECK(cudaMemcpy(tmp.data(), d, n*sizeof(Scalar), cudaMemcpyDeviceToHost));
      for (auto& v : tmp) v = -v;
      CUDA_CHECK(cudaMemcpy(d, tmp.data(), n*sizeof(Scalar), cudaMemcpyHostToDevice));
    }

    Retract(p, s, d, s_new);
    std::swap(s.R, s_new.R); std::swap(s.t, s_new.t); std::swap(s.X, s_new.X);
    cost = ComputeCost(p, s);

    std::vector<Scalar> h_d(n);
    CUDA_CHECK(cudaMemcpy(h_d.data(), d, n*sizeof(Scalar), cudaMemcpyDeviceToHost));
    Scalar step_norm = 0.0; for (auto v : h_d) step_norm += v*v; step_norm = std::sqrt(step_norm);

    log.iters.push_back(k+1); log.costs.push_back(cost);
    if (verbose) std::printf("  OCA-Schur-sparse it%4d cost=%.6e inner_steps=%d |d|=%.3e\n", k+1, cost, k+1, step_norm);
    if (step_norm < tol) break;
  }

  cusolverDnDestroy(handle);
  cudaFree(Hcc); cudaFree(Hpp); cudaFree(obs_Hcp); cudaFree(grad_c); cudaFree(grad_p);
  cudaFree(App_inv); cudaFree(S); cudaFree(bc_corr); cudaFree(bc_prime); cudaFree(xc); cudaFree(xp);
  cudaFree(gc_prev); cudaFree(gp_prev); cudaFree(bp_j); cudaFree(bc_j); cudaFree(d); cudaFree(ok_flags);
  cudaFree(s_new.R); cudaFree(s_new.t); cudaFree(s_new.X);
  return log;
}

// Gauss-Newton variant of SolveOCASchurSparse: identical growing-recursion
// structure, but H = J^T J (KernelAssembleSchurSparseGN) instead of the true
// (non-Gauss-Newton) Hessian. J^T J is always PSD, so (unlike the true-
// Hessian version) this never needs gauge-fixing or a PD-failure exit path --
// lam*I>0 keeps everything positive definite in exact arithmetic for any
// lam>0. Validated (numpy reference, this investigation) to reach a lower
// cost than plain LM-GN at the same outer-iteration count on real BAL data,
// at the cost of more total linear solves (growing k+1 depth vs LM's single
// solve) -- see SolveOCASchurSparseGNMultiLambda below for the version that
// fixes lam selection instead of leaving it fixed.
RunLog SolveOCASchurSparseGN(const DeviceProblem& p, DeviceState& s, Scalar lam, Scalar tol, int max_iter, bool verbose) {
  int ncam = p.ncam, npt = p.npt, n_c = 6*ncam, n_p = 3*npt, n = n_c + n_p;
  Scalar *Hcc, *Hpp, *obs_Hcp, *grad_c, *grad_p, *App_inv, *S;
  Scalar *bc_corr, *bc_prime, *xc, *xp, *gc_prev, *gp_prev, *bp_j, *bc_j, *d;
  int* ok_flags;
  CUDA_CHECK(cudaMalloc(&Hcc, 36*(size_t)ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&Hpp, 9*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&obs_Hcp, 18*(size_t)p.nobs*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&grad_c, 6*(size_t)ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&grad_p, 3*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&App_inv, 9*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&S, (size_t)n_c*n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bc_corr, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bc_prime, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&xc, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&xp, n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&gc_prev, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&gp_prev, n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bp_j, n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bc_j, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&d, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&ok_flags, npt*sizeof(int)));
  DeviceState s_new; AllocState(s_new, ncam, npt);

  cusolverDnHandle_t handle; cusolverDnCreate(&handle);
  CholeskyWorkspace ws; ws.Init(handle, n_c);

  Scalar cost = ComputeCost(p, s);
  RunLog log; log.iters.push_back(0); log.costs.push_back(cost);

  for (int k = 0; k < max_iter; ++k) {
    CUDA_CHECK(cudaMemset(Hcc, 0, 36*(size_t)ncam*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(Hpp, 0, 9*(size_t)npt*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(grad_c, 0, 6*(size_t)ncam*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(grad_p, 0, 3*(size_t)npt*sizeof(Scalar)));
    KernelAssembleSchurSparseGN<<<GridSize(p.nobs),256>>>(
        p.cam_idx, p.pt_idx, p.uv, s.R, s.t, s.X, p.f, p.k1, p.k2, p.nobs,
        Hcc, Hpp, obs_Hcp, grad_c, grad_p);
    KernelInvertAppBlocks<<<GridSize(npt),256>>>(Hpp, lam, App_inv, ok_flags, npt);
    { std::vector<int> h_ok(npt);
      CUDA_CHECK(cudaMemcpy(h_ok.data(), ok_flags, npt*sizeof(int), cudaMemcpyDeviceToHost));
      for (int v : h_ok) if (!v) {
        std::fprintf(stderr, "OCA-Schur-sparse-GN (fixed lam=%.4g): (lam*I+H) not PD at k=%d -- should never "
                              "happen for GN (H is always PSD); indicates lam<=0 or a real bug\n", lam, k);
        std::exit(EXIT_FAILURE);
      }
    }
    CUDA_CHECK(cudaMemset(S, 0, (size_t)n_c*n_c*sizeof(Scalar)));
    KernelBuildAccFull<<<GridSize(ncam),256>>>(Hcc, lam, S, ncam, n_c);
    KernelFormSSparse<<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                              App_inv, npt, n_c, S);
    if (!CholeskyFactor(ws, S)) {
      std::fprintf(stderr, "OCA-Schur-sparse-GN (fixed lam=%.4g): reduced system not PD at k=%d\n", lam, k);
      std::exit(EXIT_FAILURE);
    }

    CUDA_CHECK(cudaMemset(gc_prev, 0, n_c*sizeof(Scalar)));
    for (int j = 0; j <= k; ++j) {
      CUDA_CHECK(cudaMemcpy(bp_j, grad_p, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      CUDA_CHECK(cudaMemcpy(bc_j, grad_c, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      if (j > 0) {
        KernelAxpy<<<GridSize(n_p),256>>>(bp_j, gp_prev, lam, n_p);
        KernelAxpy<<<GridSize(n_c),256>>>(bc_j, gc_prev, lam, n_c);
      }
      CUDA_CHECK(cudaMemset(bc_corr, 0, n_c*sizeof(Scalar)));
      KernelRHSCorrectionSparse<<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                                         App_inv, bp_j, npt, bc_corr);
      KernelSubtractVec<<<GridSize(n_c),256>>>(bc_prime, bc_j, bc_corr, n_c);
      CUDA_CHECK(cudaMemcpy(xc, bc_prime, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      CholeskySolveVec(ws, S, xc);
      KernelBackSubstituteSparse<<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                                          App_inv, bp_j, xc, npt, xp);
      CUDA_CHECK(cudaMemcpy(gc_prev, xc, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      CUDA_CHECK(cudaMemcpy(gp_prev, xp, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));
    }
    CUDA_CHECK(cudaMemcpy(d, gc_prev, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
    CUDA_CHECK(cudaMemcpy(d+n_c, gp_prev, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));
    { std::vector<Scalar> tmp(n);
      CUDA_CHECK(cudaMemcpy(tmp.data(), d, n*sizeof(Scalar), cudaMemcpyDeviceToHost));
      for (auto& v : tmp) v = -v;
      CUDA_CHECK(cudaMemcpy(d, tmp.data(), n*sizeof(Scalar), cudaMemcpyHostToDevice));
    }

    Retract(p, s, d, s_new);
    std::swap(s.R, s_new.R); std::swap(s.t, s_new.t); std::swap(s.X, s_new.X);
    cost = ComputeCost(p, s);

    std::vector<Scalar> h_d(n);
    CUDA_CHECK(cudaMemcpy(h_d.data(), d, n*sizeof(Scalar), cudaMemcpyDeviceToHost));
    Scalar step_norm = 0.0; for (auto v : h_d) step_norm += v*v; step_norm = std::sqrt(step_norm);

    log.iters.push_back(k+1); log.costs.push_back(cost);
    if (verbose) std::printf("  OCA-Schur-sparse-GN it%4d cost=%.6e inner_steps=%d |d|=%.3e\n", k+1, cost, k+1, step_norm);
    if (step_norm < tol) break;
  }

  cusolverDnDestroy(handle);
  cudaFree(Hcc); cudaFree(Hpp); cudaFree(obs_Hcp); cudaFree(grad_c); cudaFree(grad_p);
  cudaFree(App_inv); cudaFree(S); cudaFree(bc_corr); cudaFree(bc_prime); cudaFree(xc); cudaFree(xp);
  cudaFree(gc_prev); cudaFree(gp_prev); cudaFree(bp_j); cudaFree(bc_j); cudaFree(d); cudaFree(ok_flags);
  cudaFree(s_new.R); cudaFree(s_new.t); cudaFree(s_new.X);
  return log;
}

// ============================================================== Partitioned OCA-GN (Task #28/#29): partial decoupling matching DABA's ACTUAL
// design (Eq.21 of arXiv:2305.07026), not the fully-decoupled SolveOCADabaStyle
// above. Cameras/points are each assigned to a "device"; intra-device
// observations keep their full obs_Hcp coupling (identical to
// SolveOCASchurSparseGN), cross-device observations are majorized (Hcc/Hpp
// only, DABA's `factor`) with obs_Hcp left at zero. Reuses the EXACT same
// Schur-solve machinery as SolveOCASchurSparseGN (KernelFormSSparse etc.)
// unchanged -- only the assembly kernel differs. num_devices=1 (all cameras
// and points on device 0) must reduce EXACTLY to SolveOCASchurSparseGN, since
// every observation is then intra-device and factor never applies; this is
// checked by RunPartitionSanityChecks() below rather than asserted here.
RunLog SolveOCASchurPartitioned(const DeviceProblem& p, DeviceState& s,
                                 const std::vector<int>& device_of_cam_h,
                                 const std::vector<int>& device_of_pt_h,
                                 Scalar factor, Scalar lam, Scalar tol, int max_iter, bool verbose) {
  int ncam = p.ncam, npt = p.npt, n_c = 6*ncam, n_p = 3*npt, n = n_c + n_p;
  Scalar *Hcc, *Hpp, *obs_Hcp, *grad_c, *grad_p, *App_inv, *S;
  Scalar *bc_corr, *bc_prime, *xc, *xp, *gc_prev, *gp_prev, *bp_j, *bc_j, *d;
  int* ok_flags;
  int *device_of_cam, *device_of_pt;
  CUDA_CHECK(cudaMalloc(&Hcc, 36*(size_t)ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&Hpp, 9*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&obs_Hcp, 18*(size_t)p.nobs*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&grad_c, 6*(size_t)ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&grad_p, 3*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&App_inv, 9*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&S, (size_t)n_c*n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bc_corr, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bc_prime, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&xc, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&xp, n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&gc_prev, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&gp_prev, n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bp_j, n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bc_j, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&d, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&ok_flags, npt*sizeof(int)));
  CUDA_CHECK(cudaMalloc(&device_of_cam, ncam*sizeof(int)));
  CUDA_CHECK(cudaMalloc(&device_of_pt, npt*sizeof(int)));
  CUDA_CHECK(cudaMemcpy(device_of_cam, device_of_cam_h.data(), ncam*sizeof(int), cudaMemcpyHostToDevice));
  CUDA_CHECK(cudaMemcpy(device_of_pt, device_of_pt_h.data(), npt*sizeof(int), cudaMemcpyHostToDevice));
  DeviceState s_new; AllocState(s_new, ncam, npt);

  cusolverDnHandle_t handle; cusolverDnCreate(&handle);
  CholeskyWorkspace ws; ws.Init(handle, n_c);

  Scalar cost = ComputeCost(p, s);
  RunLog log; log.iters.push_back(0); log.costs.push_back(cost);

  for (int k = 0; k < max_iter; ++k) {
    CUDA_CHECK(cudaMemset(Hcc, 0, 36*(size_t)ncam*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(Hpp, 0, 9*(size_t)npt*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(grad_c, 0, 6*(size_t)ncam*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(grad_p, 0, 3*(size_t)npt*sizeof(Scalar)));
    KernelAssembleSchurPartitioned<<<GridSize(p.nobs),256>>>(
        p.cam_idx, p.pt_idx, p.uv, s.R, s.t, s.X, p.f, p.k1, p.k2,
        device_of_cam, device_of_pt, factor, p.nobs,
        Hcc, Hpp, obs_Hcp, grad_c, grad_p);
    KernelInvertAppBlocks<<<GridSize(npt),256>>>(Hpp, lam, App_inv, ok_flags, npt);
    { std::vector<int> h_ok(npt);
      CUDA_CHECK(cudaMemcpy(h_ok.data(), ok_flags, npt*sizeof(int), cudaMemcpyDeviceToHost));
      for (int v : h_ok) if (!v) {
        std::fprintf(stderr, "OCA-Schur-partitioned (lam=%.4g, factor=%.4g): (lam*I+H) not PD at k=%d\n", lam, factor, k);
        std::exit(EXIT_FAILURE);
      }
    }
    CUDA_CHECK(cudaMemset(S, 0, (size_t)n_c*n_c*sizeof(Scalar)));
    KernelBuildAccFull<<<GridSize(ncam),256>>>(Hcc, lam, S, ncam, n_c);
    KernelFormSSparse<<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                              App_inv, npt, n_c, S);
    if (verbose && k == 0) {
      std::vector<Scalar> h_S((size_t)n_c*n_c);
      CUDA_CHECK(cudaMemcpy(h_S.data(), S, (size_t)n_c*n_c*sizeof(Scalar), cudaMemcpyDeviceToHost));
      Scalar max_cross = 0.0;
      for (int ci = 0; ci < ncam; ++ci)
        for (int cj = 0; cj < ncam; ++cj) {
          if (device_of_cam_h[ci] == device_of_cam_h[cj]) continue;
          for (int i = 0; i < 6; ++i)
            for (int j = 0; j < 6; ++j) {
              int row = 6*ci+i, col = 6*cj+j;
              max_cross = std::max(max_cross, std::abs(h_S[row + (size_t)col*n_c]));
            }
        }
      std::printf("  OCA-Schur-partitioned: max |S| over cross-device camera-camera blocks = %.3e (should be 0 for a valid partition)\n", max_cross);
    }
    if (!CholeskyFactor(ws, S)) {
      std::fprintf(stderr, "OCA-Schur-partitioned (lam=%.4g, factor=%.4g): reduced system not PD at k=%d\n", lam, factor, k);
      std::exit(EXIT_FAILURE);
    }

    CUDA_CHECK(cudaMemset(gc_prev, 0, n_c*sizeof(Scalar)));
    for (int j = 0; j <= k; ++j) {
      CUDA_CHECK(cudaMemcpy(bp_j, grad_p, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      CUDA_CHECK(cudaMemcpy(bc_j, grad_c, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      if (j > 0) {
        KernelAxpy<<<GridSize(n_p),256>>>(bp_j, gp_prev, lam, n_p);
        KernelAxpy<<<GridSize(n_c),256>>>(bc_j, gc_prev, lam, n_c);
      }
      CUDA_CHECK(cudaMemset(bc_corr, 0, n_c*sizeof(Scalar)));
      KernelRHSCorrectionSparse<<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                                         App_inv, bp_j, npt, bc_corr);
      KernelSubtractVec<<<GridSize(n_c),256>>>(bc_prime, bc_j, bc_corr, n_c);
      CUDA_CHECK(cudaMemcpy(xc, bc_prime, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      CholeskySolveVec(ws, S, xc);
      KernelBackSubstituteSparse<<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                                          App_inv, bp_j, xc, npt, xp);
      CUDA_CHECK(cudaMemcpy(gc_prev, xc, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      CUDA_CHECK(cudaMemcpy(gp_prev, xp, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));
    }
    CUDA_CHECK(cudaMemcpy(d, gc_prev, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
    CUDA_CHECK(cudaMemcpy(d+n_c, gp_prev, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));
    { std::vector<Scalar> tmp(n);
      CUDA_CHECK(cudaMemcpy(tmp.data(), d, n*sizeof(Scalar), cudaMemcpyDeviceToHost));
      for (auto& v : tmp) v = -v;
      CUDA_CHECK(cudaMemcpy(d, tmp.data(), n*sizeof(Scalar), cudaMemcpyHostToDevice));
    }

    Retract(p, s, d, s_new);
    std::swap(s.R, s_new.R); std::swap(s.t, s_new.t); std::swap(s.X, s_new.X);
    cost = ComputeCost(p, s);

    std::vector<Scalar> h_d(n);
    CUDA_CHECK(cudaMemcpy(h_d.data(), d, n*sizeof(Scalar), cudaMemcpyDeviceToHost));
    Scalar step_norm = 0.0; for (auto v : h_d) step_norm += v*v; step_norm = std::sqrt(step_norm);

    log.iters.push_back(k+1); log.costs.push_back(cost);
    if (verbose) std::printf("  OCA-Schur-partitioned it%4d cost=%.6e inner_steps=%d |d|=%.3e\n", k+1, cost, k+1, step_norm);
    if (step_norm < tol) break;
  }

  cusolverDnDestroy(handle);
  cudaFree(Hcc); cudaFree(Hpp); cudaFree(obs_Hcp); cudaFree(grad_c); cudaFree(grad_p);
  cudaFree(App_inv); cudaFree(S); cudaFree(bc_corr); cudaFree(bc_prime); cudaFree(xc); cudaFree(xp);
  cudaFree(gc_prev); cudaFree(gp_prev); cudaFree(bp_j); cudaFree(bc_j); cudaFree(d); cudaFree(ok_flags);
  cudaFree(device_of_cam); cudaFree(device_of_pt);
  cudaFree(s_new.R); cudaFree(s_new.t); cudaFree(s_new.X);
  return log;
}

// Task #29: simplest possible partitioning heuristic -- contiguous camera-index
// ranges (cameras [0,ncam/K), [ncam/K,2ncam/K), ...), each point assigned to
// the device of the FIRST camera (in observation order) that observes it.
// Real graph partitioning (e.g. METIS on the camera-point bipartite graph, to
// minimize cross-device edges) is a refinement left for later -- this is
// intentionally the crudest thing that could work, to validate the mechanism
// before optimizing the split itself.
void BuildContiguousPartition(int ncam, int npt, int num_devices,
                               const std::vector<int>& cam_idx_h, const std::vector<int>& pt_idx_h,
                               std::vector<int>& device_of_cam, std::vector<int>& device_of_pt) {
  device_of_cam.assign(ncam, 0);
  int chunk = (ncam + num_devices - 1) / num_devices;
  for (int c = 0; c < ncam; ++c) device_of_cam[c] = std::min(c / std::max(chunk,1), num_devices-1);
  device_of_pt.assign(npt, -1);
  int nobs = (int)cam_idx_h.size();
  for (int o = 0; o < nobs; ++o) {
    int p = pt_idx_h[o];
    if (device_of_pt[p] == -1) device_of_pt[p] = device_of_cam[cam_idx_h[o]];
  }
  for (int p = 0; p < npt; ++p) if (device_of_pt[p] == -1) device_of_pt[p] = 0;  // unobserved point, arbitrary
}

// ============================================================== Task #30: outer Nesterov extrapolation + true-cost accept/restart, wrapped
// around the partitioned solve above. This is deliberately structured to
// match what the critique identified as DABA's REAL design (Eq.22 of
// arXiv:2305.07026): momentum lives at the OUTER iterate sequence
// (x_bar_k = Retract(x_k, gamma_k*d_{k-1})), NOT inside any inner linear
// solve -- unlike OCA's growing recursion, which was found to have zero
// measured benefit when tried as an INNER accelerant. The per-iteration
// local solve is a SINGLE step (depth fixed at the trivial GN/Newton step,
// not OCA's k+1-deep recursion) -- matching the critique's point that DABA's
// local subproblems need only one successful inner step, and sidestepping
// the depth=outer-iteration issue entirely (task #31 will later make depth
// itself adaptive/jointly-searched; this task isolates the momentum
// mechanism on its own first, which is why depth is pinned at 1 here).
//
// Momentum bookkeeping: d_{k-1} (the tangent vector that retracted x_{k-1}
// to x_k) is reused as an approximate momentum direction at x_k's own
// tangent space -- the standard cheap approximation for retraction-based
// Nesterov (no parallel transport), consistent with how this file already
// treats composed tangent-space steps as Euclidean elsewhere (e.g. the
// growing recursion's gc_prev/gp_prev accumulation across lambda-scaled
// terms). FISTA's t_k schedule drives gamma_k = (t_k-1)/t_{k+1}.
//
// Accept/restart: the extrapolated candidate is accepted only if it
// strictly improves TRUE cost (pragmatic choice over reimplementing DABA's
// unverified-in-detail local surrogate-gap criterion, Eq.28-31). On reject,
// momentum resets (d=0, t=1) and a plain gamma=0 step from the CURRENT
// point is taken instead and applied unconditionally -- matching every
// other fixed-lambda solver in this file, none of which do line search.
RunLog SolveOCAPartitionedNesterov(const DeviceProblem& p, DeviceState& s,
                                    const std::vector<int>& device_of_cam_h,
                                    const std::vector<int>& device_of_pt_h,
                                    Scalar factor, Scalar lam, Scalar tol, int max_iter, bool verbose,
                                    bool use_momentum = true, int max_escalations = 25,
                                    Scalar gamma_cap = 1.0, Scalar gamma_fixed = -1.0) {
  int ncam = p.ncam, npt = p.npt, n_c = 6*ncam, n_p = 3*npt, n = n_c + n_p;
  Scalar *Hcc, *Hpp, *obs_Hcp, *grad_c, *grad_p, *App_inv, *S;
  Scalar *bc_corr, *bc_prime, *xc, *xp, *delta, *d_bar, *d_prev;
  int* ok_flags;
  int *device_of_cam, *device_of_pt;
  CUDA_CHECK(cudaMalloc(&Hcc, 36*(size_t)ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&Hpp, 9*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&obs_Hcp, 18*(size_t)p.nobs*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&grad_c, 6*(size_t)ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&grad_p, 3*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&App_inv, 9*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&S, (size_t)n_c*n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bc_corr, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bc_prime, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&xc, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&xp, n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&delta, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&d_bar, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&d_prev, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&ok_flags, npt*sizeof(int)));
  CUDA_CHECK(cudaMalloc(&device_of_cam, ncam*sizeof(int)));
  CUDA_CHECK(cudaMalloc(&device_of_pt, npt*sizeof(int)));
  CUDA_CHECK(cudaMemcpy(device_of_cam, device_of_cam_h.data(), ncam*sizeof(int), cudaMemcpyHostToDevice));
  CUDA_CHECK(cudaMemcpy(device_of_pt, device_of_pt_h.data(), npt*sizeof(int), cudaMemcpyHostToDevice));
  CUDA_CHECK(cudaMemset(d_prev, 0, n*sizeof(Scalar)));
  DeviceState s_bar, s_cand; AllocState(s_bar, ncam, npt); AllocState(s_cand, ncam, npt);

  cusolverDnHandle_t handle; cusolverDnCreate(&handle);
  CholeskyWorkspace ws; ws.Init(handle, n_c);

  // One assemble + single-depth (j=0 only) solve + retract, from `from_state` extrapolated
  // by `d_extrap` (may be all-zero), landing in `to_state`. Returns the new cost and writes
  // the applied tangent step (in `from_state`'s frame) into `step_out` (host vector).
  // `lam_io` is escalated (x10) in place on PD failure and never de-escalated -- same
  // one-directional-ratchet convention as the rest of this file's escalating solvers,
  // needed because real BA datasets (e.g. ladybug-598/810) require lam far above 1 just
  // to reach PD, and this depth-1 design has no other damping-search mechanism.
  auto single_step = [&](const DeviceState& from_state, const Scalar* d_extrap,
                          DeviceState& mid_state, DeviceState& to_state,
                          std::vector<Scalar>& step_out, Scalar& lam_io) -> Scalar {
    Retract(p, from_state, d_extrap, mid_state);
    CUDA_CHECK(cudaMemset(Hcc, 0, 36*(size_t)ncam*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(Hpp, 0, 9*(size_t)npt*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(grad_c, 0, 6*(size_t)ncam*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(grad_p, 0, 3*(size_t)npt*sizeof(Scalar)));
    KernelAssembleSchurPartitioned<<<GridSize(p.nobs),256>>>(
        p.cam_idx, p.pt_idx, p.uv, mid_state.R, mid_state.t, mid_state.X, p.f, p.k1, p.k2,
        device_of_cam, device_of_pt, factor, p.nobs,
        Hcc, Hpp, obs_Hcp, grad_c, grad_p);
    int esc = 0;
    for (;; ++esc) {
      KernelInvertAppBlocks<<<GridSize(npt),256>>>(Hpp, lam_io, App_inv, ok_flags, npt);
      bool pd_ok = true;
      { std::vector<int> h_ok(npt);
        CUDA_CHECK(cudaMemcpy(h_ok.data(), ok_flags, npt*sizeof(int), cudaMemcpyDeviceToHost));
        for (int v : h_ok) if (!v) pd_ok = false;
      }
      if (pd_ok) {
        CUDA_CHECK(cudaMemset(S, 0, (size_t)n_c*n_c*sizeof(Scalar)));
        KernelBuildAccFull<<<GridSize(ncam),256>>>(Hcc, lam_io, S, ncam, n_c);
        KernelFormSSparse<<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                                  App_inv, npt, n_c, S);
        pd_ok = CholeskyFactor(ws, S);
      }
      if (pd_ok) break;
      if (esc >= max_escalations) {
        std::fprintf(stderr, "OCA-Partitioned-Nesterov: not PD even after escalating lam to %.4g (factor=%.4g)\n", lam_io, factor);
        std::exit(EXIT_FAILURE);
      }
      lam_io *= 10.0;
    }
    CUDA_CHECK(cudaMemset(bc_corr, 0, n_c*sizeof(Scalar)));
    KernelRHSCorrectionSparse<<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                                       App_inv, grad_p, npt, bc_corr);
    KernelSubtractVec<<<GridSize(n_c),256>>>(bc_prime, grad_c, bc_corr, n_c);
    CUDA_CHECK(cudaMemcpy(xc, bc_prime, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
    CholeskySolveVec(ws, S, xc);
    KernelBackSubstituteSparse<<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                                        App_inv, grad_p, xc, npt, xp);
    CUDA_CHECK(cudaMemcpy(delta, xc, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
    CUDA_CHECK(cudaMemcpy(delta+n_c, xp, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));
    std::vector<Scalar> tmp(n);
    CUDA_CHECK(cudaMemcpy(tmp.data(), delta, n*sizeof(Scalar), cudaMemcpyDeviceToHost));
    for (auto& v : tmp) v = -v;
    CUDA_CHECK(cudaMemcpy(delta, tmp.data(), n*sizeof(Scalar), cudaMemcpyHostToDevice));
    step_out = tmp;  // this is the step actually applied, in from_state/mid_state's tangent frame

    Retract(p, mid_state, delta, to_state);
    return ComputeCost(p, to_state);
  };

  Scalar cost = ComputeCost(p, s);
  RunLog log; log.iters.push_back(0); log.costs.push_back(cost);
  Scalar t_mom = 1.0;
  Scalar lam_cur = lam;
  int n_restarts = 0;

  for (int k = 0; k < max_iter; ++k) {
    Scalar t_new = (1.0 + std::sqrt(1.0 + 4.0*t_mom*t_mom)) / 2.0;
    Scalar gamma;
    if (!use_momentum) gamma = 0.0;
    else if (gamma_fixed >= 0.0) gamma = gamma_fixed;   // classic heavy-ball: constant coefficient, no FISTA schedule
    else gamma = std::min((t_mom - 1.0) / t_new, gamma_cap);  // FISTA schedule, optionally capped below its asymptote of 1

    std::vector<Scalar> h_dprev(n);
    CUDA_CHECK(cudaMemcpy(h_dprev.data(), d_prev, n*sizeof(Scalar), cudaMemcpyDeviceToHost));
    for (auto& v : h_dprev) v *= gamma;
    CUDA_CHECK(cudaMemcpy(d_bar, h_dprev.data(), n*sizeof(Scalar), cudaMemcpyHostToDevice));

    std::vector<Scalar> step_extrap;
    Scalar cost_extrap = single_step(s, d_bar, s_bar, s_cand, step_extrap, lam_cur);

    bool accepted;
    Scalar step_norm;
    if (cost_extrap < cost) {
      accepted = true;
      std::swap(s.R, s_cand.R); std::swap(s.t, s_cand.t); std::swap(s.X, s_cand.X);
      cost = cost_extrap;
      std::vector<Scalar> h_dnew(n);
      for (int i = 0; i < n; ++i) h_dnew[i] = h_dprev[i] + step_extrap[i];  // gamma*d_prev + delta
      CUDA_CHECK(cudaMemcpy(d_prev, h_dnew.data(), n*sizeof(Scalar), cudaMemcpyHostToDevice));
      t_mom = t_new;
      step_norm = 0.0; for (auto v : step_extrap) step_norm += v*v; step_norm = std::sqrt(step_norm);
    } else {
      accepted = false;
      ++n_restarts;
      CUDA_CHECK(cudaMemset(d_bar, 0, n*sizeof(Scalar)));  // gamma=0 fallback from the actual current point
      std::vector<Scalar> step_plain;
      Scalar cost_plain = single_step(s, d_bar, s_bar, s_cand, step_plain, lam_cur);
      std::swap(s.R, s_cand.R); std::swap(s.t, s_cand.t); std::swap(s.X, s_cand.X);
      cost = cost_plain;
      CUDA_CHECK(cudaMemcpy(d_prev, step_plain.data(), n*sizeof(Scalar), cudaMemcpyHostToDevice));
      t_mom = 1.0;
      step_norm = 0.0; for (auto v : step_plain) step_norm += v*v; step_norm = std::sqrt(step_norm);
    }

    log.iters.push_back(k+1); log.costs.push_back(cost);
    if (verbose) std::printf("  OCA-Partitioned-Nesterov it%4d cost=%.6e |d|=%.3e gamma=%.3f lam=%.3e %s\n",
                              k+1, cost, step_norm, gamma, lam_cur, accepted ? "" : "[restart]");
    if (step_norm < tol) break;
  }
  if (verbose) std::printf("  OCA-Partitioned-Nesterov: %d/%d iterations restarted\n", n_restarts, (int)log.iters.size()-1);

  cusolverDnDestroy(handle);
  cudaFree(Hcc); cudaFree(Hpp); cudaFree(obs_Hcp); cudaFree(grad_c); cudaFree(grad_p);
  cudaFree(App_inv); cudaFree(S); cudaFree(bc_corr); cudaFree(bc_prime); cudaFree(xc); cudaFree(xp);
  cudaFree(delta); cudaFree(d_bar); cudaFree(d_prev); cudaFree(ok_flags);
  cudaFree(device_of_cam); cudaFree(device_of_pt);
  cudaFree(s_bar.R); cudaFree(s_bar.t); cudaFree(s_bar.X);
  cudaFree(s_cand.R); cudaFree(s_cand.t); cudaFree(s_cand.X);
  return log;
}

// LM-style SINGLE-lambda trust-region adaptation wrapped around OCA-GN's
// growing recursion: exactly SolveLMSchurSparse's own xi-ratio adaptive mu
// (grow/shrink by 10x based on the trust-region ratio, reject-and-retry with
// a larger lambda if a step doesn't improve cost) -- but the per-iteration
// solve is the k+1-depth growing recursion instead of LM's single solve.
// Isolates whether OCA's recursion mechanism helps when paired with CHEAP
// (one candidate, not a 5-wide grid) adaptive damping, at much lower
// per-iteration overhead than SolveOCASchurSparseGNMultiLambda.
RunLog SolveOCASchurSparseGNLMAdaptive(const DeviceProblem& p, DeviceState& s, Scalar mu0, Scalar tol,
                                        int max_iter, bool verbose, Scalar grad_tol_rel = 1e-8) {
  int ncam = p.ncam, npt = p.npt, n_c = 6*ncam, n_p = 3*npt, n = n_c + n_p;
  Scalar *Hcc, *Hpp, *obs_Hcp, *grad_c, *grad_p, *App_inv, *S;
  Scalar *bc_corr, *bc_prime, *xc, *xp, *gc_prev, *gp_prev, *bp_j, *bc_j, *d, *jd_sum;
  int* ok_flags;
  CUDA_CHECK(cudaMalloc(&Hcc, 36*(size_t)ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&Hpp, 9*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&obs_Hcp, 18*(size_t)p.nobs*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&grad_c, 6*(size_t)ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&grad_p, 3*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&App_inv, 9*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&S, (size_t)n_c*n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bc_corr, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bc_prime, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&xc, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&xp, n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&gc_prev, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&gp_prev, n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bp_j, n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bc_j, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&d, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&jd_sum, sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&ok_flags, npt*sizeof(int)));
  DeviceState s_new; AllocState(s_new, ncam, npt);

  cusolverDnHandle_t handle; cusolverDnCreate(&handle);
  CholeskyWorkspace ws; ws.Init(handle, n_c);

  Scalar mu = mu0;
  Scalar cost = ComputeCost(p, s);
  RunLog log; log.iters.push_back(0); log.costs.push_back(cost);
  Scalar grad_norm0 = -1.0;

  for (int k = 0; k < max_iter; ++k) {
    CUDA_CHECK(cudaMemset(Hcc, 0, 36*(size_t)ncam*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(Hpp, 0, 9*(size_t)npt*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(grad_c, 0, 6*(size_t)ncam*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(grad_p, 0, 3*(size_t)npt*sizeof(Scalar)));
    KernelAssembleSchurSparseGN<<<GridSize(p.nobs),256>>>(
        p.cam_idx, p.pt_idx, p.uv, s.R, s.t, s.X, p.f, p.k1, p.k2, p.nobs,
        Hcc, Hpp, obs_Hcp, grad_c, grad_p);

    Scalar grad_norm;
    { std::vector<Scalar> h_grad_full(n);
      CUDA_CHECK(cudaMemcpy(h_grad_full.data(), grad_c, n_c*sizeof(Scalar), cudaMemcpyDeviceToHost));
      CUDA_CHECK(cudaMemcpy(h_grad_full.data()+n_c, grad_p, n_p*sizeof(Scalar), cudaMemcpyDeviceToHost));
      Scalar s2 = 0.0; for (auto v : h_grad_full) s2 += v*v;
      grad_norm = std::sqrt(s2);
    }
    if (grad_norm0 < 0.0) grad_norm0 = std::max(grad_norm, (Scalar)1e-300);

    Scalar cost_new, xi = 0.0, step_norm = 0.0;
    for (int attempt = 0;; ++attempt) {
      KernelInvertAppBlocks<<<GridSize(npt),256>>>(Hpp, mu, App_inv, ok_flags, npt);
      bool pd_ok = true;
      { std::vector<int> h_ok(npt);
        CUDA_CHECK(cudaMemcpy(h_ok.data(), ok_flags, npt*sizeof(int), cudaMemcpyDeviceToHost));
        for (int v : h_ok) if (!v) pd_ok = false;
      }
      if (pd_ok) {
        CUDA_CHECK(cudaMemset(S, 0, (size_t)n_c*n_c*sizeof(Scalar)));
        KernelBuildAccFull<<<GridSize(ncam),256>>>(Hcc, mu, S, ncam, n_c);
        KernelFormSSparse<<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                                  App_inv, npt, n_c, S);
        pd_ok = CholeskyFactor(ws, S);
      }
      if (!pd_ok) {
        if (attempt >= 30) {
          std::fprintf(stderr, "OCA-Schur-sparse-GN-LMAdaptive: (Hpp+mu*I)/S not PD at k=%d even after growing mu to %.4g\n", k, mu);
          std::exit(EXIT_FAILURE);
        }
        mu *= 10.0;
        continue;
      }

      // growing recursion at depth k+1, SAME structure as SolveOCASchurSparseGN, but at this attempt's mu
      CUDA_CHECK(cudaMemset(gc_prev, 0, n_c*sizeof(Scalar)));
      for (int j = 0; j <= k; ++j) {
        CUDA_CHECK(cudaMemcpy(bp_j, grad_p, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));
        CUDA_CHECK(cudaMemcpy(bc_j, grad_c, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
        if (j > 0) {
          KernelAxpy<<<GridSize(n_p),256>>>(bp_j, gp_prev, mu, n_p);
          KernelAxpy<<<GridSize(n_c),256>>>(bc_j, gc_prev, mu, n_c);
        }
        CUDA_CHECK(cudaMemset(bc_corr, 0, n_c*sizeof(Scalar)));
        KernelRHSCorrectionSparse<<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                                           App_inv, bp_j, npt, bc_corr);
        KernelSubtractVec<<<GridSize(n_c),256>>>(bc_prime, bc_j, bc_corr, n_c);
        CUDA_CHECK(cudaMemcpy(xc, bc_prime, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
        CholeskySolveVec(ws, S, xc);
        KernelBackSubstituteSparse<<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                                            App_inv, bp_j, xc, npt, xp);
        CUDA_CHECK(cudaMemcpy(gc_prev, xc, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
        CUDA_CHECK(cudaMemcpy(gp_prev, xp, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      }
      CUDA_CHECK(cudaMemcpy(d, gc_prev, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      CUDA_CHECK(cudaMemcpy(d+n_c, gp_prev, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      { std::vector<Scalar> tmp(n);
        CUDA_CHECK(cudaMemcpy(tmp.data(), d, n*sizeof(Scalar), cudaMemcpyDeviceToHost));
        for (auto& v : tmp) v = -v;
        CUDA_CHECK(cudaMemcpy(d, tmp.data(), n*sizeof(Scalar), cudaMemcpyHostToDevice));
      }

      Retract(p, s, d, s_new);
      cost_new = ComputeCost(p, s_new);

      CUDA_CHECK(cudaMemset(jd_sum, 0, sizeof(Scalar)));
      KernelJdSquaredSum<<<GridSize(p.nobs),256>>>(p.cam_idx, p.pt_idx, p.uv, s.R, s.t, s.X, p.f, p.k1, p.k2,
                                                    d, p.nobs, ncam, jd_sum);
      Scalar quad; CUDA_CHECK(cudaMemcpy(&quad, jd_sum, sizeof(Scalar), cudaMemcpyDeviceToHost));
      std::vector<Scalar> h_grad(n), h_d(n);
      CUDA_CHECK(cudaMemcpy(h_grad.data(), grad_c, n_c*sizeof(Scalar), cudaMemcpyDeviceToHost));
      CUDA_CHECK(cudaMemcpy(h_grad.data()+n_c, grad_p, n_p*sizeof(Scalar), cudaMemcpyDeviceToHost));
      CUDA_CHECK(cudaMemcpy(h_d.data(), d, n*sizeof(Scalar), cudaMemcpyDeviceToHost));
      Scalar grad_dot_d = 0.0; for (int i = 0; i < n; ++i) grad_dot_d += h_grad[i]*h_d[i];
      Scalar pred_decrease = -(grad_dot_d + 0.5*quad);
      Scalar actual_decrease = cost - cost_new;
      xi = (std::fabs(pred_decrease) > 1e-300) ? actual_decrease/pred_decrease : 0.0;
      step_norm = 0.0; for (auto v : h_d) step_norm += v*v; step_norm = std::sqrt(step_norm);

      if (cost_new <= cost || attempt >= 20) break;
      mu *= 10.0;
    }

    std::swap(s.R, s_new.R); std::swap(s.t, s_new.t); std::swap(s.X, s_new.X);
    cost = cost_new;
    if (xi < 0.25) mu *= 10.0; else if (xi > 0.75) mu *= 0.1;

    log.iters.push_back(k+1); log.costs.push_back(cost);
    if (verbose) std::printf("  OCA-GN-LMAdapt it%4d cost=%.6e mu=%.3e xi=%.3f |d|=%.3e |grad|/|grad0|=%.3e\n",
                              k+1, cost, mu, xi, step_norm, grad_norm/grad_norm0);
    if (step_norm < tol && grad_norm < grad_tol_rel * grad_norm0) break;
  }

  cusolverDnDestroy(handle);
  cudaFree(Hcc); cudaFree(Hpp); cudaFree(obs_Hcp); cudaFree(grad_c); cudaFree(grad_p);
  cudaFree(App_inv); cudaFree(S); cudaFree(bc_corr); cudaFree(bc_prime); cudaFree(xc); cudaFree(xp);
  cudaFree(gc_prev); cudaFree(gp_prev); cudaFree(bp_j); cudaFree(bc_j); cudaFree(d); cudaFree(jd_sum); cudaFree(ok_flags);
  cudaFree(s_new.R); cudaFree(s_new.t); cudaFree(s_new.X);
  return log;
}

// Multi-lambda wrapper around SolveOCASchurSparseGN's per-iteration solve:
// adapts DABA multi-lambda's philosophy (candidate grid, true-cost accept,
// escalate-and-retry if nothing improves) to the COUPLED Schur system, where
// there's one global system rather than independent per-block ones -- so
// this is a global-lambda-grid version (n_candidates values tried each outer
// iteration), not literal per-block multi-lambda (that needs the decoupled
// DABA-style formulation, SolveOCADabaMultiLambda above, instead). Validated
// (numpy reference) to reach plain fixed-lambda OCA-GN's cost in 4x fewer
// outer iterations on real BAL data.
RunLog SolveOCASchurSparseGNMultiLambda(const DeviceProblem& p, DeviceState& s, Scalar lam0, Scalar tol,
                                         int max_iter, bool verbose, int n_candidates = 5,
                                         Scalar decade_span = 1.0, int max_escalations = 25) {
  int ncam = p.ncam, npt = p.npt, n_c = 6*ncam, n_p = 3*npt, n = n_c + n_p;
  Scalar *Hcc, *Hpp, *obs_Hcp, *grad_c, *grad_p, *App_inv, *S;
  Scalar *bc_corr, *bc_prime, *xc, *xp, *gc_prev, *gp_prev, *bp_j, *bc_j, *d, *d_best;
  int* ok_flags;
  CUDA_CHECK(cudaMalloc(&Hcc, 36*(size_t)ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&Hpp, 9*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&obs_Hcp, 18*(size_t)p.nobs*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&grad_c, 6*(size_t)ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&grad_p, 3*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&App_inv, 9*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&S, (size_t)n_c*n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bc_corr, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bc_prime, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&xc, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&xp, n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&gc_prev, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&gp_prev, n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bp_j, n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bc_j, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&d, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&d_best, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&ok_flags, npt*sizeof(int)));
  DeviceState s_new; AllocState(s_new, ncam, npt);

  cusolverDnHandle_t handle; cusolverDnCreate(&handle);
  CholeskyWorkspace ws; ws.Init(handle, n_c);

  Scalar cost = ComputeCost(p, s);
  RunLog log; log.iters.push_back(0); log.costs.push_back(cost);
  Scalar lam_center = lam0;
  Scalar grad_norm0 = -1.0;   // captured at k=0 -- see the grad-norm convergence check below

  // Runs the growing recursion (depth k+1) at a single lambda value, writing
  // the resulting step into `d` and returning the retracted true cost --
  // does NOT commit the step to s (caller decides after comparing candidates).
  auto try_lambda = [&](int k, Scalar lam_val) -> Scalar {
    KernelInvertAppBlocks<<<GridSize(npt),256>>>(Hpp, lam_val, App_inv, ok_flags, npt);
    { std::vector<int> h_ok(npt);
      CUDA_CHECK(cudaMemcpy(h_ok.data(), ok_flags, npt*sizeof(int), cudaMemcpyDeviceToHost));
      for (int v : h_ok) if (!v) return std::numeric_limits<Scalar>::infinity();
    }
    CUDA_CHECK(cudaMemset(S, 0, (size_t)n_c*n_c*sizeof(Scalar)));
    KernelBuildAccFull<<<GridSize(ncam),256>>>(Hcc, lam_val, S, ncam, n_c);
    KernelFormSSparse<<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                              App_inv, npt, n_c, S);
    if (!CholeskyFactor(ws, S)) return std::numeric_limits<Scalar>::infinity();

    CUDA_CHECK(cudaMemset(gc_prev, 0, n_c*sizeof(Scalar)));
    for (int j = 0; j <= k; ++j) {
      CUDA_CHECK(cudaMemcpy(bp_j, grad_p, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      CUDA_CHECK(cudaMemcpy(bc_j, grad_c, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      if (j > 0) {
        KernelAxpy<<<GridSize(n_p),256>>>(bp_j, gp_prev, lam_val, n_p);
        KernelAxpy<<<GridSize(n_c),256>>>(bc_j, gc_prev, lam_val, n_c);
      }
      CUDA_CHECK(cudaMemset(bc_corr, 0, n_c*sizeof(Scalar)));
      KernelRHSCorrectionSparse<<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                                         App_inv, bp_j, npt, bc_corr);
      KernelSubtractVec<<<GridSize(n_c),256>>>(bc_prime, bc_j, bc_corr, n_c);
      CUDA_CHECK(cudaMemcpy(xc, bc_prime, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      CholeskySolveVec(ws, S, xc);
      KernelBackSubstituteSparse<<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                                          App_inv, bp_j, xc, npt, xp);
      CUDA_CHECK(cudaMemcpy(gc_prev, xc, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      CUDA_CHECK(cudaMemcpy(gp_prev, xp, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));
    }
    CUDA_CHECK(cudaMemcpy(d, gc_prev, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
    CUDA_CHECK(cudaMemcpy(d+n_c, gp_prev, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));
    { std::vector<Scalar> tmp(n);
      CUDA_CHECK(cudaMemcpy(tmp.data(), d, n*sizeof(Scalar), cudaMemcpyDeviceToHost));
      for (auto& v : tmp) v = -v;
      CUDA_CHECK(cudaMemcpy(d, tmp.data(), n*sizeof(Scalar), cudaMemcpyHostToDevice));
    }
    Retract(p, s, d, s_new);
    return ComputeCost(p, s_new);
  };

  for (int k = 0; k < max_iter; ++k) {
    CUDA_CHECK(cudaMemset(Hcc, 0, 36*(size_t)ncam*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(Hpp, 0, 9*(size_t)npt*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(grad_c, 0, 6*(size_t)ncam*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(grad_p, 0, 3*(size_t)npt*sizeof(Scalar)));
    KernelAssembleSchurSparseGN<<<GridSize(p.nobs),256>>>(
        p.cam_idx, p.pt_idx, p.uv, s.R, s.t, s.X, p.f, p.k1, p.k2, p.nobs,
        Hcc, Hpp, obs_Hcp, grad_c, grad_p);

    // Gradient-norm convergence signal, independent of step size -- a step
    // forced tiny by an artificially huge lambda (needed on some datasets:
    // ladybug-598 needs lambda~1e14 just to reach a PD system at k=0) has
    // step_norm~0 even though the true gradient is still enormous. Same
    // fix as SolveLMSchurSparse's own grad_norm0 check, ported here after
    // this exact failure mode was caught on ladybug-598 (multi-lambda
    // silently "converged" after 1 iteration at cost 7791267 vs the true
    // ~60-iteration solve reaching ~2.87e5 with LM-GN).
    Scalar grad_norm;
    { std::vector<Scalar> h_grad_full(n);
      CUDA_CHECK(cudaMemcpy(h_grad_full.data(), grad_c, n_c*sizeof(Scalar), cudaMemcpyDeviceToHost));
      CUDA_CHECK(cudaMemcpy(h_grad_full.data()+n_c, grad_p, n_p*sizeof(Scalar), cudaMemcpyDeviceToHost));
      Scalar s2 = 0.0; for (auto v : h_grad_full) s2 += v*v;
      grad_norm = std::sqrt(s2);
    }
    if (grad_norm0 < 0.0) grad_norm0 = std::max(grad_norm, (Scalar)1e-300);

    Scalar cost_current = cost, cost_best = std::numeric_limits<Scalar>::infinity(), lam_best = lam_center;
    int n_esc = 0;
    for (;; ++n_esc) {
      cost_best = std::numeric_limits<Scalar>::infinity();
      for (int ci = 0; ci < n_candidates; ++ci) {
        Scalar frac = n_candidates > 1 ? (Scalar)ci / (n_candidates - 1) : 0.5;
        Scalar exponent = -decade_span + 2.0 * decade_span * frac;
        Scalar lam_val = lam_center * std::pow((Scalar)10.0, exponent);
        Scalar c = try_lambda(k, lam_val);
        if (c < cost_best) {
          cost_best = c; lam_best = lam_val;
          CUDA_CHECK(cudaMemcpy(d_best, d, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
        }
      }
      if (cost_best < cost_current || n_esc >= max_escalations) break;
      lam_center *= 10.0;
    }

    if (cost_best >= cost_current) {
      if (verbose) std::printf("  OCA-GN-ML: converged / no improving lambda found at k=%d (cost=%.6e)\n", k, cost);
      break;
    }
    lam_center = std::max(lam_best * 0.5, lam0 * 1e-8);

    Retract(p, s, d_best, s_new);
    std::swap(s.R, s_new.R); std::swap(s.t, s_new.t); std::swap(s.X, s_new.X);
    cost = cost_best;

    std::vector<Scalar> h_d(n);
    CUDA_CHECK(cudaMemcpy(h_d.data(), d_best, n*sizeof(Scalar), cudaMemcpyDeviceToHost));
    Scalar step_norm = 0.0; for (auto v : h_d) step_norm += v*v; step_norm = std::sqrt(step_norm);

    log.iters.push_back(k+1); log.costs.push_back(cost);
    if (verbose) std::printf("  OCA-GN-ML it%4d cost=%.6e |d|=%.3e lam_best=%.3e n_esc=%d |grad|/|grad0|=%.3e\n",
                              k+1, cost, step_norm, lam_best, n_esc, grad_norm/grad_norm0);
    if (step_norm < tol && grad_norm < 1e-8 * grad_norm0) break;
  }

  cusolverDnDestroy(handle);
  cudaFree(Hcc); cudaFree(Hpp); cudaFree(obs_Hcp); cudaFree(grad_c); cudaFree(grad_p);
  cudaFree(App_inv); cudaFree(S); cudaFree(bc_corr); cudaFree(bc_prime); cudaFree(xc); cudaFree(xp);
  cudaFree(gc_prev); cudaFree(gp_prev); cudaFree(bp_j); cudaFree(bc_j); cudaFree(d); cudaFree(d_best); cudaFree(ok_flags);
  cudaFree(s_new.R); cudaFree(s_new.t); cudaFree(s_new.X);
  return log;
}

// ============================================================== Task #31: joint (lambda, depth) search. SolveOCASchurSparseGNMultiLambda
// above ranks candidate lambdas using a SHALLOW probe (g_0) then commits to a
// much DEEPER solve (depth k+1, growing with the outer iteration count) for
// the winner only -- a mismatch the dossier itself already flagged, and
// which the critique separately identified as suspect on its own terms: once
// an outer loop runs into the hundreds/thousands of iterations, depth=k+1
// mechanically amplifies whatever negative-curvature modes survive at
// lambda>0 (rho_i=lambda/(mu_i+lambda)>1 for any negative mu_i), and even
// for the PSD Gauss-Newton Hessian used here, growing depth without bound is
// pure wasted compute once the recursion's marginal benefit saturates.
//
// This function evaluates EVERY (lambda, depth) combination on true
// retracted cost from the SAME set of per-lambda factorizations already
// being computed -- for each lambda candidate, factor S ONCE, then walk the
// growing recursion to increasing depth, taking a true-cost checkpoint at
// each depth in `depths` (0,1,2,4,8 by default) instead of only at the
// final one. Depth is a fixed small menu, NOT tied to the outer iteration
// counter k -- this is the "adaptive shallow depth" the critique proposed in
// place of OCA's depth=outer-iteration rule. The winning (lambda, depth)
// pair is selected purely by true cost, same acceptance test as
// SolveOCASchurSparseGNMultiLambda (escalate lambda_center if nothing beats
// the current cost).
std::vector<Scalar> SolveSmallSPD(std::vector<std::vector<Scalar>> A, std::vector<Scalar> b);  // defined below; forward-declared for use in P3's subspace solve

RunLog SolveOCAJointLambdaDepth(const DeviceProblem& p, DeviceState& s, Scalar lam0, Scalar tol,
                                 int max_iter, bool verbose, int n_candidates = 5,
                                 Scalar decade_span = 1.0, int max_escalations = 25,
                                 std::vector<int> depths = {0,1,2,4,8}, bool fp32_cholesky = false,
                                 bool subspace_min = false) {
  int ncam = p.ncam, npt = p.npt, n_c = 6*ncam, n_p = 3*npt, n = n_c + n_p;
  Scalar *Hcc, *Hpp, *obs_Hcp, *grad_c, *grad_p, *App_inv, *S;
  Scalar *bc_corr, *bc_prime, *xc, *xp, *gc_prev, *gp_prev, *bp_j, *bc_j, *d, *d_best;
  int* ok_flags;
  // Task P3: subspace minimization over G=[g_j : j in depths] -- see the derivation right above
  // the closure below. G is (n x |depths|) device, column-major; d_sub/Hv_col are n-dim scratch.
  int n_depths = (int)depths.size();
  Scalar *G_basis = nullptr, *G_best = nullptr, *Hv_col = nullptr, *d_sub = nullptr;
  if (subspace_min) {
    CUDA_CHECK(cudaMalloc(&G_basis, (size_t)n*n_depths*sizeof(Scalar)));
    CUDA_CHECK(cudaMalloc(&G_best, (size_t)n*n_depths*sizeof(Scalar)));
    CUDA_CHECK(cudaMalloc(&Hv_col, n*sizeof(Scalar)));
    CUDA_CHECK(cudaMalloc(&d_sub, n*sizeof(Scalar)));
  }
  CUDA_CHECK(cudaMalloc(&Hcc, 36*(size_t)ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&Hpp, 9*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&obs_Hcp, 18*(size_t)p.nobs*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&grad_c, 6*(size_t)ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&grad_p, 3*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&App_inv, 9*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&S, (size_t)n_c*n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bc_corr, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bc_prime, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&xc, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&xp, n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&gc_prev, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&gp_prev, n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bp_j, n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bc_j, n_c*sizeof(Scalar)));
  Scalar *d_cand;
  CUDA_CHECK(cudaMalloc(&d, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&d_best, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&d_cand, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&ok_flags, npt*sizeof(int)));
  DeviceState s_new; AllocState(s_new, ncam, npt);

  cusolverDnHandle_t handle; cusolverDnCreate(&handle);
  CholeskyWorkspace ws; ws.Init(handle, n_c);
  cublasHandle_t blas_sub;
  if (subspace_min) CUBLAS_CHECK(cublasCreate(&blas_sub));
  CholeskyWorkspaceF32 wsf;
  float *S_f32 = nullptr, *xc_f32 = nullptr;
  if (fp32_cholesky) {
    wsf.Init(handle, n_c);
    CUDA_CHECK(cudaMalloc(&S_f32, (size_t)n_c*n_c*sizeof(float)));
    CUDA_CHECK(cudaMalloc(&xc_f32, n_c*sizeof(float)));
  }

  Scalar cost = ComputeCost(p, s);
  RunLog log; log.iters.push_back(0); log.costs.push_back(cost);
  Scalar lam_center = lam0;
  Scalar grad_norm0 = -1.0;
  int max_depth = 0; for (int dd : depths) max_depth = std::max(max_depth, dd);

  // Factor S once at lam_val, then walk the growing recursion to max_depth,
  // true-cost-checking at each depth in `depths`. Returns the best
  // (cost, depth) found for this lambda; writes the corresponding step to
  // `d_out` (device, length n). Does NOT commit to s.
  bool prof = (std::getenv("OCA_PROFILE") != nullptr);
  double t_pdchol = 0, t_recursion = 0, t_checkpoint = 0;
  auto now = [](){ return std::chrono::steady_clock::now(); };

  auto try_lambda_multidepth = [&](Scalar lam_val, Scalar* d_out, int& depth_out) -> Scalar {
    std::chrono::steady_clock::time_point t0;
    if (prof) { cudaDeviceSynchronize(); t0 = now(); }
    KernelInvertAppBlocks<<<GridSize(npt),256>>>(Hpp, lam_val, App_inv, ok_flags, npt);
    { std::vector<int> h_ok(npt);
      CUDA_CHECK(cudaMemcpy(h_ok.data(), ok_flags, npt*sizeof(int), cudaMemcpyDeviceToHost));
      for (int v : h_ok) if (!v) return std::numeric_limits<Scalar>::infinity();
    }
    CUDA_CHECK(cudaMemset(S, 0, (size_t)n_c*n_c*sizeof(Scalar)));
    KernelBuildAccFull<<<GridSize(ncam),256>>>(Hcc, lam_val, S, ncam, n_c);
    KernelFormSSparse<<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                              App_inv, npt, n_c, S);
    if (fp32_cholesky) {
      KernelCastD2F<<<GridSize(n_c*n_c),256>>>(S, S_f32, n_c*n_c);
      if (!CholeskyFactorF32(wsf, S_f32)) return std::numeric_limits<Scalar>::infinity();
    } else {
      if (!CholeskyFactor(ws, S)) return std::numeric_limits<Scalar>::infinity();
    }
    if (prof) { cudaDeviceSynchronize(); t_pdchol += std::chrono::duration<double>(now()-t0).count(); }

    Scalar best_cost = std::numeric_limits<Scalar>::infinity();
    depth_out = depths.empty() ? 0 : depths[0];
    CUDA_CHECK(cudaMemset(gc_prev, 0, n_c*sizeof(Scalar)));
    for (int j = 0; j <= max_depth; ++j) {
      if (prof) { cudaDeviceSynchronize(); t0 = now(); }
      CUDA_CHECK(cudaMemcpy(bp_j, grad_p, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      CUDA_CHECK(cudaMemcpy(bc_j, grad_c, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      if (j > 0) {
        KernelAxpy<<<GridSize(n_p),256>>>(bp_j, gp_prev, lam_val, n_p);
        KernelAxpy<<<GridSize(n_c),256>>>(bc_j, gc_prev, lam_val, n_c);
      }
      CUDA_CHECK(cudaMemset(bc_corr, 0, n_c*sizeof(Scalar)));
      KernelRHSCorrectionSparse<<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                                         App_inv, bp_j, npt, bc_corr);
      KernelSubtractVec<<<GridSize(n_c),256>>>(bc_prime, bc_j, bc_corr, n_c);
      CUDA_CHECK(cudaMemcpy(xc, bc_prime, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      if (fp32_cholesky) {
        KernelCastD2F<<<GridSize(n_c),256>>>(xc, xc_f32, n_c);
        CholeskySolveVecF32(wsf, S_f32, xc_f32);
        KernelCastF2D<<<GridSize(n_c),256>>>(xc_f32, xc, n_c);
      } else {
        CholeskySolveVec(ws, S, xc);
      }
      KernelBackSubstituteSparse<<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                                          App_inv, bp_j, xc, npt, xp);
      CUDA_CHECK(cudaMemcpy(gc_prev, xc, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      CUDA_CHECK(cudaMemcpy(gp_prev, xp, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      if (prof) { cudaDeviceSynchronize(); t_recursion += std::chrono::duration<double>(now()-t0).count(); }

      if (std::find(depths.begin(), depths.end(), j) == depths.end()) continue;
      if (prof) { cudaDeviceSynchronize(); t0 = now(); }
      CUDA_CHECK(cudaMemcpy(d_cand, gc_prev, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      CUDA_CHECK(cudaMemcpy(d_cand+n_c, gp_prev, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      if (subspace_min) {
        // Stash the UN-negated g_j (== d_cand right now) into G's next column, before negation
        // mutates d_cand in place -- P3 needs the raw g_j's, not the retraction steps.
        int col = (int)(std::find(depths.begin(), depths.end(), j) - depths.begin());
        CUDA_CHECK(cudaMemcpy(G_basis + (size_t)col*n, d_cand, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      }
      // On-device negation (KernelNegateInPlace), not a host round-trip: this checkpoint fires up to
      // n_candidates*|depths| times per outer iteration (25 at the default 5x5), and the stream-parallel
      // multi-lambda work earlier in this file already established that ANY blocking host cudaMemcpy here
      // is pure serialization overhead with no numerical purpose -- same fix, applied to this solver too.
      KernelNegateInPlace<<<GridSize(n),256>>>(d_cand, n);
      Retract(p, s, d_cand, s_new);
      Scalar c = ComputeCost(p, s_new);
      if (c < best_cost) {
        best_cost = c; depth_out = j;
        CUDA_CHECK(cudaMemcpy(d_out, d_cand, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));  // d_out != d_cand: a real copy, not a self-copy
      }
      if (prof) { cudaDeviceSynchronize(); t_checkpoint += std::chrono::duration<double>(now()-t0).count(); }
    }

    return best_cost;
  };

  // ---- Task P3: subspace minimization over G=[g_j : j in depths] ----
  // Provably >= best single checkpoint on the LOCAL quadratic model, since checkpoint selection
  // is the special case alpha=one-hot: with v=-G*alpha, m(v)=f(x)-b~^T alpha+(1/2)alpha^T S~ alpha
  // where S~=G^T H_gn G, b~=G^T b -- minimized by S~ alpha=b~ (the SAME normal-equations form as
  // the original system, just projected onto span(G)). True-cost-gated: a locally-optimal model
  // minimizer is not automatically globally trustworthy.
  //
  // Deliberately called ONCE per outer iteration (on G_best, the checkpoint-winning candidate's
  // already-computed G -- free byproduct of the depth recursion every candidate does anyway), NOT
  // once per lambda candidate. First version called this inside try_lambda_multidepth (5x/iter at
  // the default n_candidates=5); on ladybug-598 (n=211,242) that added ~3s/iter of matvec+dot work
  // for 4 discarded candidates' worth of nothing, enough to erase the fewer-iterations win seen at
  // ladybug-49 scale. Cholesky is 88% of wall-clock (measured via OCA_PROFILE) and is unavoidably
  // paid once per candidate regardless of subspace_min, so the only thing worth deferring to
  // "winner only" is this genuinely-extra work, not the recursion itself.
  auto try_subspace_refine = [&](Scalar* d_best_io, Scalar& cost_best_io, int& depth_best_io) {
    std::vector<std::vector<Scalar>> Stilde(n_depths, std::vector<Scalar>(n_depths, 0.0));
    std::vector<Scalar> btilde(n_depths, 0.0);
    Scalar* bfull; CUDA_CHECK(cudaMalloc(&bfull, n*sizeof(Scalar)));
    CUDA_CHECK(cudaMemcpy(bfull, grad_c, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
    CUDA_CHECK(cudaMemcpy(bfull+n_c, grad_p, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));
    for (int col = 0; col < n_depths; ++col) {
      CUDA_CHECK(cudaMemset(Hv_col, 0, n*sizeof(Scalar)));
      KernelHgnMatVecCross<<<GridSize(p.nobs),256>>>(obs_Hcp, p.cam_idx, p.pt_idx, p.nobs,
                                                      G_best + (size_t)col*n, G_best + (size_t)col*n + n_c,
                                                      Hv_col, Hv_col + n_c);
      KernelHgnMatVecDiagCam<<<GridSize(ncam),256>>>(Hcc, ncam, G_best + (size_t)col*n, Hv_col);
      KernelHgnMatVecDiagPt<<<GridSize(npt),256>>>(Hpp, npt, G_best + (size_t)col*n + n_c, Hv_col + n_c);
      for (int row = 0; row < n_depths; ++row) {
        Scalar dot; CUBLAS_CHECK(cublasDdot(blas_sub, n, G_best + (size_t)row*n, 1, Hv_col, 1, &dot));
        Stilde[row][col] = dot;
      }
      Scalar bdot; CUBLAS_CHECK(cublasDdot(blas_sub, n, G_best + (size_t)col*n, 1, bfull, 1, &bdot));
      btilde[col] = bdot;
    }
    cudaFree(bfull);
    for (int i = 0; i < n_depths; ++i) Stilde[i][i] += 1e-9 * std::max(Stilde[i][i], (Scalar)1.0);  // ridge, numerical safety only
    std::vector<Scalar> alpha = SolveSmallSPD(Stilde, btilde);
    for (auto& v : alpha) v = -v;  // d_sub = G @ (-alpha)
    CUDA_CHECK(cudaMemcpy(Hv_col, alpha.data(), n_depths*sizeof(Scalar), cudaMemcpyHostToDevice));  // reuse Hv_col's device mem as a tiny alpha buffer (n_depths << n)
    const Scalar one_ = 1.0, zero_ = 0.0;
    CUBLAS_CHECK(cublasDgemv(blas_sub, CUBLAS_OP_N, n, n_depths, &one_, G_best, n, Hv_col, 1, &zero_, d_sub, 1));
    Retract(p, s, d_sub, s_new);
    Scalar c_sub = ComputeCost(p, s_new);
    if (c_sub < cost_best_io) {
      cost_best_io = c_sub; depth_best_io = -1;  // -1 marks "subspace-combined step", not a single checkpoint depth
      CUDA_CHECK(cudaMemcpy(d_best_io, d_sub, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
    }
  };

  double t_assembly = 0;
  for (int k = 0; k < max_iter; ++k) {
    std::chrono::steady_clock::time_point tk0;
    if (prof) { cudaDeviceSynchronize(); tk0 = now(); }
    CUDA_CHECK(cudaMemset(Hcc, 0, 36*(size_t)ncam*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(Hpp, 0, 9*(size_t)npt*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(grad_c, 0, 6*(size_t)ncam*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(grad_p, 0, 3*(size_t)npt*sizeof(Scalar)));
    KernelAssembleSchurSparseGN<<<GridSize(p.nobs),256>>>(
        p.cam_idx, p.pt_idx, p.uv, s.R, s.t, s.X, p.f, p.k1, p.k2, p.nobs,
        Hcc, Hpp, obs_Hcp, grad_c, grad_p);
    if (prof) { cudaDeviceSynchronize(); t_assembly += std::chrono::duration<double>(now()-tk0).count(); }

    Scalar grad_norm;
    { std::vector<Scalar> h_grad_full(n);
      CUDA_CHECK(cudaMemcpy(h_grad_full.data(), grad_c, n_c*sizeof(Scalar), cudaMemcpyDeviceToHost));
      CUDA_CHECK(cudaMemcpy(h_grad_full.data()+n_c, grad_p, n_p*sizeof(Scalar), cudaMemcpyDeviceToHost));
      Scalar s2 = 0.0; for (auto v : h_grad_full) s2 += v*v;
      grad_norm = std::sqrt(s2);
    }
    if (grad_norm0 < 0.0) grad_norm0 = std::max(grad_norm, (Scalar)1e-300);

    Scalar cost_current = cost, cost_best = std::numeric_limits<Scalar>::infinity(), lam_best = lam_center;
    int depth_best = 0, n_esc = 0;
    for (;; ++n_esc) {
      cost_best = std::numeric_limits<Scalar>::infinity();
      for (int ci = 0; ci < n_candidates; ++ci) {
        Scalar frac = n_candidates > 1 ? (Scalar)ci / (n_candidates - 1) : 0.5;
        Scalar exponent = -decade_span + 2.0 * decade_span * frac;
        Scalar lam_val = lam_center * std::pow((Scalar)10.0, exponent);
        int depth_this;
        Scalar c = try_lambda_multidepth(lam_val, d, depth_this);
        if (c < cost_best) {
          cost_best = c; lam_best = lam_val; depth_best = depth_this;
          CUDA_CHECK(cudaMemcpy(d_best, d, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
          if (subspace_min) CUDA_CHECK(cudaMemcpy(G_best, G_basis, (size_t)n*n_depths*sizeof(Scalar), cudaMemcpyDeviceToDevice));
        }
      }
      if (cost_best < cost_current || n_esc >= max_escalations) break;
      lam_center *= 10.0;
    }

    if (cost_best >= cost_current) {
      if (verbose) std::printf("  OCA-Joint-LD: converged / no improving (lambda,depth) found at k=%d (cost=%.6e)\n", k, cost);
      break;
    }
    if (subspace_min) try_subspace_refine(d_best, cost_best, depth_best);
    lam_center = std::max(lam_best * 0.5, lam0 * 1e-8);

    Retract(p, s, d_best, s_new);
    std::swap(s.R, s_new.R); std::swap(s.t, s_new.t); std::swap(s.X, s_new.X);
    cost = cost_best;

    std::vector<Scalar> h_d(n);
    CUDA_CHECK(cudaMemcpy(h_d.data(), d_best, n*sizeof(Scalar), cudaMemcpyDeviceToHost));
    Scalar step_norm = 0.0; for (auto v : h_d) step_norm += v*v; step_norm = std::sqrt(step_norm);

    log.iters.push_back(k+1); log.costs.push_back(cost);
    if (verbose) std::printf("  OCA-Joint-LD it%4d cost=%.6e |d|=%.3e lam_best=%.3e depth_best=%d n_esc=%d |grad|/|grad0|=%.3e\n",
                              k+1, cost, step_norm, lam_best, depth_best, n_esc, grad_norm/grad_norm0);
    if (step_norm < tol && grad_norm < 1e-8 * grad_norm0) break;
  }
  if (prof) std::printf("  [PROFILE] assembly=%.3fs  pd_check+cholesky=%.3fs  recursion(non-checkpoint)=%.3fs  checkpoint(retract+cost)=%.3fs\n",
                         t_assembly, t_pdchol, t_recursion, t_checkpoint);

  cusolverDnDestroy(handle);
  if (subspace_min) cublasDestroy(blas_sub);
  if (fp32_cholesky) { cudaFree(S_f32); cudaFree(xc_f32); }
  if (subspace_min) { cudaFree(G_basis); cudaFree(G_best); cudaFree(Hv_col); cudaFree(d_sub); }
  cudaFree(Hcc); cudaFree(Hpp); cudaFree(obs_Hcp); cudaFree(grad_c); cudaFree(grad_p);
  cudaFree(App_inv); cudaFree(S); cudaFree(bc_corr); cudaFree(bc_prime); cudaFree(xc); cudaFree(xp);
  cudaFree(gc_prev); cudaFree(gp_prev); cudaFree(bp_j); cudaFree(bc_j); cudaFree(d); cudaFree(d_best); cudaFree(d_cand); cudaFree(ok_flags);
  cudaFree(s_new.R); cudaFree(s_new.t); cudaFree(s_new.X);
  return log;
}

// ============================================================== Task: Strategy #5 from OCA_Acceleration_Strategies.pdf -- structured/
// blockwise damping on the COUPLED Schur system. Every solver in this file
// up to now (including the champion SolveOCAJointLambdaDepth) uses ONE
// scalar lambda for both the camera and point diagonal blocks -- but OCA is
// naturally written with a PD control matrix R, only ever specialized here
// to R=lambda*I. A single scalar can be dominated by whichever class (camera
// or point) has the worse-conditioned/more-negative-curvature blocks,
// over-damping the OTHER class's perfectly healthy directions in the
// process. This generalizes R to R=blkdiag(lam_cam*I6,...,lam_pt*I3,...)
// -- two classes (not yet full per-block), searched as an independent 2D
// grid instead of SolveOCAJointLambdaDepth's 1D grid, otherwise identical
// (same true-cost depth-menu checkpointing, same escalate/shrink pattern).
//
// The growing recursion generalizes directly: g_j = A^-1(b + R g_{j-1})
// becomes, block-wise, g_{j,cam} using lam_cam's correction and g_{j,pt}
// using lam_pt's -- the same derivation OCA's own paper uses for R=lambda*I,
// just not collapsing R to a single scalar. Camera-side kernels
// (KernelBuildAccFull, the bc_j correction) get lam_cam; point-side kernels
// (KernelInvertAppBlocks, the bp_j correction) get lam_pt.
RunLog SolveOCAJointLambdaCamPtDepth(const DeviceProblem& p, DeviceState& s, Scalar lam0, Scalar tol,
                                      int max_iter, bool verbose, int n_cam_candidates = 3, int n_pt_candidates = 3,
                                      Scalar decade_span = 1.0, int max_escalations = 25,
                                      std::vector<int> depths = {0,1,2,4,8}, bool subspace_min = false) {
  int ncam = p.ncam, npt = p.npt, n_c = 6*ncam, n_p = 3*npt, n = n_c + n_p;
  Scalar *Hcc, *Hpp, *obs_Hcp, *grad_c, *grad_p, *App_inv, *S;
  Scalar *bc_corr, *bc_prime, *xc, *xp, *gc_prev, *gp_prev, *bp_j, *bc_j, *d, *d_best, *d_cand;
  int* ok_flags;
  // Task P3 (see SolveOCAJointLambdaDepth for the full derivation/validation history), reused here
  // combining it with Strategy #5's structured cam/pt damping -- the "combine the pieces" direction
  // OCA_Acceleration_Strategies.pdf section 9 recommends. Deferred to once/outer-iteration on the
  // winning (lam_cam,lam_pt) combo's already-computed G, same restructuring that turned this from a
  // regression into a genuine win on SolveOCAJointLambdaDepth.
  int n_depths = (int)depths.size();
  Scalar *G_basis = nullptr, *G_best = nullptr, *Hv_col = nullptr, *d_sub = nullptr;
  cublasHandle_t blas_sub;
  if (subspace_min) {
    CUDA_CHECK(cudaMalloc(&G_basis, (size_t)n*n_depths*sizeof(Scalar)));
    CUDA_CHECK(cudaMalloc(&G_best, (size_t)n*n_depths*sizeof(Scalar)));
    CUDA_CHECK(cudaMalloc(&Hv_col, n*sizeof(Scalar)));
    CUDA_CHECK(cudaMalloc(&d_sub, n*sizeof(Scalar)));
    CUBLAS_CHECK(cublasCreate(&blas_sub));
  }
  CUDA_CHECK(cudaMalloc(&Hcc, 36*(size_t)ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&Hpp, 9*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&obs_Hcp, 18*(size_t)p.nobs*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&grad_c, 6*(size_t)ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&grad_p, 3*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&App_inv, 9*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&S, (size_t)n_c*n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bc_corr, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bc_prime, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&xc, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&xp, n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&gc_prev, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&gp_prev, n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bp_j, n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bc_j, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&d, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&d_best, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&d_cand, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&ok_flags, npt*sizeof(int)));
  DeviceState s_new; AllocState(s_new, ncam, npt);

  cusolverDnHandle_t handle; cusolverDnCreate(&handle);
  CholeskyWorkspace ws; ws.Init(handle, n_c);

  Scalar cost = ComputeCost(p, s);
  RunLog log; log.iters.push_back(0); log.costs.push_back(cost);
  Scalar lam_cam_center = lam0, lam_pt_center = lam0;
  Scalar grad_norm0 = -1.0;
  int max_depth = 0; for (int dd : depths) max_depth = std::max(max_depth, dd);

  auto try_lambda_pair = [&](Scalar lam_cam, Scalar lam_pt, Scalar* d_out, int& depth_out) -> Scalar {
    KernelInvertAppBlocks<<<GridSize(npt),256>>>(Hpp, lam_pt, App_inv, ok_flags, npt);
    { std::vector<int> h_ok(npt);
      CUDA_CHECK(cudaMemcpy(h_ok.data(), ok_flags, npt*sizeof(int), cudaMemcpyDeviceToHost));
      for (int v : h_ok) if (!v) return std::numeric_limits<Scalar>::infinity();
    }
    CUDA_CHECK(cudaMemset(S, 0, (size_t)n_c*n_c*sizeof(Scalar)));
    KernelBuildAccFull<<<GridSize(ncam),256>>>(Hcc, lam_cam, S, ncam, n_c);
    KernelFormSSparse<<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                              App_inv, npt, n_c, S);
    if (!CholeskyFactor(ws, S)) return std::numeric_limits<Scalar>::infinity();

    Scalar best_cost = std::numeric_limits<Scalar>::infinity();
    depth_out = depths.empty() ? 0 : depths[0];
    CUDA_CHECK(cudaMemset(gc_prev, 0, n_c*sizeof(Scalar)));
    for (int j = 0; j <= max_depth; ++j) {
      CUDA_CHECK(cudaMemcpy(bp_j, grad_p, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      CUDA_CHECK(cudaMemcpy(bc_j, grad_c, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      if (j > 0) {
        KernelAxpy<<<GridSize(n_p),256>>>(bp_j, gp_prev, lam_pt, n_p);
        KernelAxpy<<<GridSize(n_c),256>>>(bc_j, gc_prev, lam_cam, n_c);
      }
      CUDA_CHECK(cudaMemset(bc_corr, 0, n_c*sizeof(Scalar)));
      KernelRHSCorrectionSparse<<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                                         App_inv, bp_j, npt, bc_corr);
      KernelSubtractVec<<<GridSize(n_c),256>>>(bc_prime, bc_j, bc_corr, n_c);
      CUDA_CHECK(cudaMemcpy(xc, bc_prime, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      CholeskySolveVec(ws, S, xc);
      KernelBackSubstituteSparse<<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                                          App_inv, bp_j, xc, npt, xp);
      CUDA_CHECK(cudaMemcpy(gc_prev, xc, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      CUDA_CHECK(cudaMemcpy(gp_prev, xp, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));

      if (std::find(depths.begin(), depths.end(), j) == depths.end()) continue;
      CUDA_CHECK(cudaMemcpy(d_cand, gc_prev, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      CUDA_CHECK(cudaMemcpy(d_cand+n_c, gp_prev, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      if (subspace_min) {
        // Stash the UN-negated g_j into G's next column before negation mutates d_cand in place.
        int col = (int)(std::find(depths.begin(), depths.end(), j) - depths.begin());
        CUDA_CHECK(cudaMemcpy(G_basis + (size_t)col*n, d_cand, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      }
      // On-device negation (KernelNegateInPlace), not a host round-trip: this checkpoint fires up to
      // n_candidates*|depths| times per outer iteration (25 at the default 5x5), and the stream-parallel
      // multi-lambda work earlier in this file already established that ANY blocking host cudaMemcpy here
      // is pure serialization overhead with no numerical purpose -- same fix, applied to this solver too.
      KernelNegateInPlace<<<GridSize(n),256>>>(d_cand, n);
      Retract(p, s, d_cand, s_new);
      Scalar c = ComputeCost(p, s_new);
      if (c < best_cost) {
        best_cost = c; depth_out = j;
        CUDA_CHECK(cudaMemcpy(d_out, d_cand, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      }
    }
    return best_cost;
  };

  auto try_subspace_refine = [&](Scalar* d_best_io, Scalar& cost_best_io, int& depth_best_io) {
    std::vector<std::vector<Scalar>> Stilde(n_depths, std::vector<Scalar>(n_depths, 0.0));
    std::vector<Scalar> btilde(n_depths, 0.0);
    Scalar* bfull; CUDA_CHECK(cudaMalloc(&bfull, n*sizeof(Scalar)));
    CUDA_CHECK(cudaMemcpy(bfull, grad_c, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
    CUDA_CHECK(cudaMemcpy(bfull+n_c, grad_p, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));
    for (int col = 0; col < n_depths; ++col) {
      CUDA_CHECK(cudaMemset(Hv_col, 0, n*sizeof(Scalar)));
      KernelHgnMatVecCross<<<GridSize(p.nobs),256>>>(obs_Hcp, p.cam_idx, p.pt_idx, p.nobs,
                                                      G_best + (size_t)col*n, G_best + (size_t)col*n + n_c,
                                                      Hv_col, Hv_col + n_c);
      KernelHgnMatVecDiagCam<<<GridSize(ncam),256>>>(Hcc, ncam, G_best + (size_t)col*n, Hv_col);
      KernelHgnMatVecDiagPt<<<GridSize(npt),256>>>(Hpp, npt, G_best + (size_t)col*n + n_c, Hv_col + n_c);
      for (int row = 0; row < n_depths; ++row) {
        Scalar dot; CUBLAS_CHECK(cublasDdot(blas_sub, n, G_best + (size_t)row*n, 1, Hv_col, 1, &dot));
        Stilde[row][col] = dot;
      }
      Scalar bdot; CUBLAS_CHECK(cublasDdot(blas_sub, n, G_best + (size_t)col*n, 1, bfull, 1, &bdot));
      btilde[col] = bdot;
    }
    cudaFree(bfull);
    for (int i = 0; i < n_depths; ++i) Stilde[i][i] += 1e-9 * std::max(Stilde[i][i], (Scalar)1.0);
    std::vector<Scalar> alpha = SolveSmallSPD(Stilde, btilde);
    for (auto& v : alpha) v = -v;
    CUDA_CHECK(cudaMemcpy(Hv_col, alpha.data(), n_depths*sizeof(Scalar), cudaMemcpyHostToDevice));
    const Scalar one_ = 1.0, zero_ = 0.0;
    CUBLAS_CHECK(cublasDgemv(blas_sub, CUBLAS_OP_N, n, n_depths, &one_, G_best, n, Hv_col, 1, &zero_, d_sub, 1));
    Retract(p, s, d_sub, s_new);
    Scalar c_sub = ComputeCost(p, s_new);
    if (c_sub < cost_best_io) {
      cost_best_io = c_sub; depth_best_io = -1;
      CUDA_CHECK(cudaMemcpy(d_best_io, d_sub, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
    }
  };

  for (int k = 0; k < max_iter; ++k) {
    CUDA_CHECK(cudaMemset(Hcc, 0, 36*(size_t)ncam*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(Hpp, 0, 9*(size_t)npt*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(grad_c, 0, 6*(size_t)ncam*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(grad_p, 0, 3*(size_t)npt*sizeof(Scalar)));
    KernelAssembleSchurSparseGN<<<GridSize(p.nobs),256>>>(
        p.cam_idx, p.pt_idx, p.uv, s.R, s.t, s.X, p.f, p.k1, p.k2, p.nobs,
        Hcc, Hpp, obs_Hcp, grad_c, grad_p);

    Scalar grad_norm;
    { std::vector<Scalar> h_grad_full(n);
      CUDA_CHECK(cudaMemcpy(h_grad_full.data(), grad_c, n_c*sizeof(Scalar), cudaMemcpyDeviceToHost));
      CUDA_CHECK(cudaMemcpy(h_grad_full.data()+n_c, grad_p, n_p*sizeof(Scalar), cudaMemcpyDeviceToHost));
      Scalar s2 = 0.0; for (auto v : h_grad_full) s2 += v*v;
      grad_norm = std::sqrt(s2);
    }
    if (grad_norm0 < 0.0) grad_norm0 = std::max(grad_norm, (Scalar)1e-300);

    Scalar cost_current = cost, cost_best = std::numeric_limits<Scalar>::infinity();
    Scalar lam_cam_best = lam_cam_center, lam_pt_best = lam_pt_center;
    int depth_best = 0, n_esc = 0;
    for (;; ++n_esc) {
      cost_best = std::numeric_limits<Scalar>::infinity();
      for (int ci = 0; ci < n_cam_candidates; ++ci) {
        Scalar frac_c = n_cam_candidates > 1 ? (Scalar)ci / (n_cam_candidates - 1) : 0.5;
        Scalar lam_cam_val = lam_cam_center * std::pow((Scalar)10.0, -decade_span + 2.0*decade_span*frac_c);
        for (int pi = 0; pi < n_pt_candidates; ++pi) {
          Scalar frac_p = n_pt_candidates > 1 ? (Scalar)pi / (n_pt_candidates - 1) : 0.5;
          Scalar lam_pt_val = lam_pt_center * std::pow((Scalar)10.0, -decade_span + 2.0*decade_span*frac_p);
          int depth_this;
          Scalar c = try_lambda_pair(lam_cam_val, lam_pt_val, d, depth_this);
          if (c < cost_best) {
            cost_best = c; lam_cam_best = lam_cam_val; lam_pt_best = lam_pt_val; depth_best = depth_this;
            CUDA_CHECK(cudaMemcpy(d_best, d, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
            if (subspace_min) CUDA_CHECK(cudaMemcpy(G_best, G_basis, (size_t)n*n_depths*sizeof(Scalar), cudaMemcpyDeviceToDevice));
          }
        }
      }
      if (cost_best < cost_current || n_esc >= max_escalations) break;
      lam_cam_center *= 10.0; lam_pt_center *= 10.0;
    }

    if (cost_best >= cost_current) {
      if (verbose) std::printf("  OCA-Joint-CamPt-LD: converged / no improving combo found at k=%d (cost=%.6e)\n", k, cost);
      break;
    }
    if (subspace_min) try_subspace_refine(d_best, cost_best, depth_best);
    lam_cam_center = std::max(lam_cam_best * 0.5, lam0 * 1e-8);
    lam_pt_center = std::max(lam_pt_best * 0.5, lam0 * 1e-8);

    Retract(p, s, d_best, s_new);
    std::swap(s.R, s_new.R); std::swap(s.t, s_new.t); std::swap(s.X, s_new.X);
    cost = cost_best;

    std::vector<Scalar> h_d(n);
    CUDA_CHECK(cudaMemcpy(h_d.data(), d_best, n*sizeof(Scalar), cudaMemcpyDeviceToHost));
    Scalar step_norm = 0.0; for (auto v : h_d) step_norm += v*v; step_norm = std::sqrt(step_norm);

    log.iters.push_back(k+1); log.costs.push_back(cost);
    if (verbose) std::printf("  OCA-Joint-CamPt-LD it%4d cost=%.6e |d|=%.3e lam_cam=%.3e lam_pt=%.3e depth_best=%d n_esc=%d |grad|/|grad0|=%.3e\n",
                              k+1, cost, step_norm, lam_cam_best, lam_pt_best, depth_best, n_esc, grad_norm/grad_norm0);
    if (step_norm < tol && grad_norm < 1e-8 * grad_norm0) break;
  }

  cusolverDnDestroy(handle);
  if (subspace_min) { cublasDestroy(blas_sub); cudaFree(G_basis); cudaFree(G_best); cudaFree(Hv_col); cudaFree(d_sub); }
  cudaFree(Hcc); cudaFree(Hpp); cudaFree(obs_Hcp); cudaFree(grad_c); cudaFree(grad_p);
  cudaFree(App_inv); cudaFree(S); cudaFree(bc_corr); cudaFree(bc_prime); cudaFree(xc); cudaFree(xp);
  cudaFree(gc_prev); cudaFree(gp_prev); cudaFree(bp_j); cudaFree(bc_j); cudaFree(d); cudaFree(d_best); cudaFree(d_cand); cudaFree(ok_flags);
  cudaFree(s_new.R); cudaFree(s_new.t); cudaFree(s_new.X);
  return log;
}

// ============================================================== Task: Section 6 (Anderson/NGMRES) wrapping the champion
// (structured cam/pt damping + optional subspace_min), rather than plain LM
// as in SolveLMSchurSparseAA above -- same Type-I Anderson Acceleration
// (Walker & Ni 2011, successive-differences form), applied at the OUTER
// level around the champion's own per-iteration choice, matching this file's
// established "acceleration goes outside the inner solve, not inside it"
// pattern. Dx/Df history is built from the PLAIN champion step (the
// candidate sweep's chosen d_best, after any subspace refinement -- i.e.
// exactly what SolveOCAJointLambdaCamPtDepth would have applied on its own),
// never from the AA-extrapolated candidate; the small G=Df^T Df system
// (ridge-regularized) and candidate d_aa = f_k - Dx@gamma are identical in
// form to SolveLMSchurSparseAA. AA's candidate is accepted only if its true
// retracted cost beats the plain step's -- the same true-cost gate as every
// other candidate class in this file. Lambda-center adaptation is driven by
// the PLAIN step's (lam_cam_best,lam_pt_best) regardless of whether AA's
// candidate is the one actually applied, mirroring SolveLMSchurSparseAA's mu
// adaptation being independent of AA acceptance.
RunLog SolveOCAJointLambdaCamPtDepthAA(const DeviceProblem& p, DeviceState& s, Scalar lam0, Scalar tol,
                                        int max_iter, bool verbose, int n_cam_candidates = 3, int n_pt_candidates = 3,
                                        Scalar decade_span = 1.0, int max_escalations = 25,
                                        std::vector<int> depths = {0,1,2,4,8}, bool subspace_min = false,
                                        int aa_window = 2, Scalar aa_reg = 1e-10) {
  int ncam = p.ncam, npt = p.npt, n_c = 6*ncam, n_p = 3*npt, n = n_c + n_p;
  Scalar *Hcc, *Hpp, *obs_Hcp, *grad_c, *grad_p, *App_inv, *S;
  Scalar *bc_corr, *bc_prime, *xc, *xp, *gc_prev, *gp_prev, *bp_j, *bc_j, *d, *d_best, *d_cand, *d_aa_dev;
  int* ok_flags;
  int n_depths = (int)depths.size();
  Scalar *G_basis = nullptr, *G_best = nullptr, *Hv_col = nullptr, *d_sub = nullptr;
  cublasHandle_t blas_sub;
  if (subspace_min) {
    CUDA_CHECK(cudaMalloc(&G_basis, (size_t)n*n_depths*sizeof(Scalar)));
    CUDA_CHECK(cudaMalloc(&G_best, (size_t)n*n_depths*sizeof(Scalar)));
    CUDA_CHECK(cudaMalloc(&Hv_col, n*sizeof(Scalar)));
    CUDA_CHECK(cudaMalloc(&d_sub, n*sizeof(Scalar)));
    CUBLAS_CHECK(cublasCreate(&blas_sub));
  }
  CUDA_CHECK(cudaMalloc(&Hcc, 36*(size_t)ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&Hpp, 9*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&obs_Hcp, 18*(size_t)p.nobs*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&grad_c, 6*(size_t)ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&grad_p, 3*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&App_inv, 9*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&S, (size_t)n_c*n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bc_corr, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bc_prime, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&xc, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&xp, n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&gc_prev, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&gp_prev, n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bp_j, n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bc_j, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&d, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&d_best, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&d_cand, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&d_aa_dev, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&ok_flags, npt*sizeof(int)));
  DeviceState s_new; AllocState(s_new, ncam, npt);
  DeviceState s_aa; AllocState(s_aa, ncam, npt);

  cusolverDnHandle_t handle; cusolverDnCreate(&handle);
  CholeskyWorkspace ws; ws.Init(handle, n_c);

  Scalar cost = ComputeCost(p, s);
  RunLog log; log.iters.push_back(0); log.costs.push_back(cost);
  Scalar lam_cam_center = lam0, lam_pt_center = lam0;
  Scalar grad_norm0 = -1.0;
  int max_depth = 0; for (int dd : depths) max_depth = std::max(max_depth, dd);

  auto try_lambda_pair = [&](Scalar lam_cam, Scalar lam_pt, Scalar* d_out, int& depth_out) -> Scalar {
    KernelInvertAppBlocks<<<GridSize(npt),256>>>(Hpp, lam_pt, App_inv, ok_flags, npt);
    { std::vector<int> h_ok(npt);
      CUDA_CHECK(cudaMemcpy(h_ok.data(), ok_flags, npt*sizeof(int), cudaMemcpyDeviceToHost));
      for (int v : h_ok) if (!v) return std::numeric_limits<Scalar>::infinity();
    }
    CUDA_CHECK(cudaMemset(S, 0, (size_t)n_c*n_c*sizeof(Scalar)));
    KernelBuildAccFull<<<GridSize(ncam),256>>>(Hcc, lam_cam, S, ncam, n_c);
    KernelFormSSparse<<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                              App_inv, npt, n_c, S);
    if (!CholeskyFactor(ws, S)) return std::numeric_limits<Scalar>::infinity();

    Scalar best_cost = std::numeric_limits<Scalar>::infinity();
    depth_out = depths.empty() ? 0 : depths[0];
    CUDA_CHECK(cudaMemset(gc_prev, 0, n_c*sizeof(Scalar)));
    for (int j = 0; j <= max_depth; ++j) {
      CUDA_CHECK(cudaMemcpy(bp_j, grad_p, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      CUDA_CHECK(cudaMemcpy(bc_j, grad_c, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      if (j > 0) {
        KernelAxpy<<<GridSize(n_p),256>>>(bp_j, gp_prev, lam_pt, n_p);
        KernelAxpy<<<GridSize(n_c),256>>>(bc_j, gc_prev, lam_cam, n_c);
      }
      CUDA_CHECK(cudaMemset(bc_corr, 0, n_c*sizeof(Scalar)));
      KernelRHSCorrectionSparse<<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                                         App_inv, bp_j, npt, bc_corr);
      KernelSubtractVec<<<GridSize(n_c),256>>>(bc_prime, bc_j, bc_corr, n_c);
      CUDA_CHECK(cudaMemcpy(xc, bc_prime, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      CholeskySolveVec(ws, S, xc);
      KernelBackSubstituteSparse<<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                                          App_inv, bp_j, xc, npt, xp);
      CUDA_CHECK(cudaMemcpy(gc_prev, xc, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      CUDA_CHECK(cudaMemcpy(gp_prev, xp, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));

      if (std::find(depths.begin(), depths.end(), j) == depths.end()) continue;
      CUDA_CHECK(cudaMemcpy(d_cand, gc_prev, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      CUDA_CHECK(cudaMemcpy(d_cand+n_c, gp_prev, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      if (subspace_min) {
        int col = (int)(std::find(depths.begin(), depths.end(), j) - depths.begin());
        CUDA_CHECK(cudaMemcpy(G_basis + (size_t)col*n, d_cand, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      }
      KernelNegateInPlace<<<GridSize(n),256>>>(d_cand, n);
      Retract(p, s, d_cand, s_new);
      Scalar c = ComputeCost(p, s_new);
      if (c < best_cost) {
        best_cost = c; depth_out = j;
        CUDA_CHECK(cudaMemcpy(d_out, d_cand, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      }
    }
    return best_cost;
  };

  auto try_subspace_refine = [&](Scalar* d_best_io, Scalar& cost_best_io, int& depth_best_io) {
    std::vector<std::vector<Scalar>> Stilde(n_depths, std::vector<Scalar>(n_depths, 0.0));
    std::vector<Scalar> btilde(n_depths, 0.0);
    Scalar* bfull; CUDA_CHECK(cudaMalloc(&bfull, n*sizeof(Scalar)));
    CUDA_CHECK(cudaMemcpy(bfull, grad_c, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
    CUDA_CHECK(cudaMemcpy(bfull+n_c, grad_p, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));
    for (int col = 0; col < n_depths; ++col) {
      CUDA_CHECK(cudaMemset(Hv_col, 0, n*sizeof(Scalar)));
      KernelHgnMatVecCross<<<GridSize(p.nobs),256>>>(obs_Hcp, p.cam_idx, p.pt_idx, p.nobs,
                                                      G_best + (size_t)col*n, G_best + (size_t)col*n + n_c,
                                                      Hv_col, Hv_col + n_c);
      KernelHgnMatVecDiagCam<<<GridSize(ncam),256>>>(Hcc, ncam, G_best + (size_t)col*n, Hv_col);
      KernelHgnMatVecDiagPt<<<GridSize(npt),256>>>(Hpp, npt, G_best + (size_t)col*n + n_c, Hv_col + n_c);
      for (int row = 0; row < n_depths; ++row) {
        Scalar dot; CUBLAS_CHECK(cublasDdot(blas_sub, n, G_best + (size_t)row*n, 1, Hv_col, 1, &dot));
        Stilde[row][col] = dot;
      }
      Scalar bdot; CUBLAS_CHECK(cublasDdot(blas_sub, n, G_best + (size_t)col*n, 1, bfull, 1, &bdot));
      btilde[col] = bdot;
    }
    cudaFree(bfull);
    for (int i = 0; i < n_depths; ++i) Stilde[i][i] += 1e-9 * std::max(Stilde[i][i], (Scalar)1.0);
    std::vector<Scalar> alpha = SolveSmallSPD(Stilde, btilde);
    for (auto& v : alpha) v = -v;
    CUDA_CHECK(cudaMemcpy(Hv_col, alpha.data(), n_depths*sizeof(Scalar), cudaMemcpyHostToDevice));
    const Scalar one_ = 1.0, zero_ = 0.0;
    CUBLAS_CHECK(cublasDgemv(blas_sub, CUBLAS_OP_N, n, n_depths, &one_, G_best, n, Hv_col, 1, &zero_, d_sub, 1));
    Retract(p, s, d_sub, s_new);
    Scalar c_sub = ComputeCost(p, s_new);
    if (c_sub < cost_best_io) {
      cost_best_io = c_sub; depth_best_io = -1;
      CUDA_CHECK(cudaMemcpy(d_best_io, d_sub, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
    }
  };

  std::vector<std::vector<Scalar>> Dx_hist, Df_hist;
  std::vector<Scalar> f_prev;
  int n_aa_accepted = 0;

  for (int k = 0; k < max_iter; ++k) {
    CUDA_CHECK(cudaMemset(Hcc, 0, 36*(size_t)ncam*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(Hpp, 0, 9*(size_t)npt*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(grad_c, 0, 6*(size_t)ncam*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(grad_p, 0, 3*(size_t)npt*sizeof(Scalar)));
    KernelAssembleSchurSparseGN<<<GridSize(p.nobs),256>>>(
        p.cam_idx, p.pt_idx, p.uv, s.R, s.t, s.X, p.f, p.k1, p.k2, p.nobs,
        Hcc, Hpp, obs_Hcp, grad_c, grad_p);

    Scalar grad_norm;
    { std::vector<Scalar> h_grad_full(n);
      CUDA_CHECK(cudaMemcpy(h_grad_full.data(), grad_c, n_c*sizeof(Scalar), cudaMemcpyDeviceToHost));
      CUDA_CHECK(cudaMemcpy(h_grad_full.data()+n_c, grad_p, n_p*sizeof(Scalar), cudaMemcpyDeviceToHost));
      Scalar s2 = 0.0; for (auto v : h_grad_full) s2 += v*v;
      grad_norm = std::sqrt(s2);
    }
    if (grad_norm0 < 0.0) grad_norm0 = std::max(grad_norm, (Scalar)1e-300);

    // ---- plain champion step: identical to SolveOCAJointLambdaCamPtDepth's own body ----
    Scalar cost_current = cost, cost_best = std::numeric_limits<Scalar>::infinity();
    Scalar lam_cam_best = lam_cam_center, lam_pt_best = lam_pt_center;
    int depth_best = 0, n_esc = 0;
    for (;; ++n_esc) {
      cost_best = std::numeric_limits<Scalar>::infinity();
      for (int ci = 0; ci < n_cam_candidates; ++ci) {
        Scalar frac_c = n_cam_candidates > 1 ? (Scalar)ci / (n_cam_candidates - 1) : 0.5;
        Scalar lam_cam_val = lam_cam_center * std::pow((Scalar)10.0, -decade_span + 2.0*decade_span*frac_c);
        for (int pi = 0; pi < n_pt_candidates; ++pi) {
          Scalar frac_p = n_pt_candidates > 1 ? (Scalar)pi / (n_pt_candidates - 1) : 0.5;
          Scalar lam_pt_val = lam_pt_center * std::pow((Scalar)10.0, -decade_span + 2.0*decade_span*frac_p);
          int depth_this;
          Scalar c = try_lambda_pair(lam_cam_val, lam_pt_val, d, depth_this);
          if (c < cost_best) {
            cost_best = c; lam_cam_best = lam_cam_val; lam_pt_best = lam_pt_val; depth_best = depth_this;
            CUDA_CHECK(cudaMemcpy(d_best, d, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
            if (subspace_min) CUDA_CHECK(cudaMemcpy(G_best, G_basis, (size_t)n*n_depths*sizeof(Scalar), cudaMemcpyDeviceToDevice));
          }
        }
      }
      if (cost_best < cost_current || n_esc >= max_escalations) break;
      lam_cam_center *= 10.0; lam_pt_center *= 10.0;
    }

    if (cost_best >= cost_current) {
      if (verbose) std::printf("  OCA-Joint-CamPt-LD-AA: converged / no improving combo found at k=%d (cost=%.6e)\n", k, cost);
      break;
    }
    if (subspace_min) try_subspace_refine(d_best, cost_best, depth_best);
    lam_cam_center = std::max(lam_cam_best * 0.5, lam0 * 1e-8);
    lam_pt_center = std::max(lam_pt_best * 0.5, lam0 * 1e-8);

    std::vector<Scalar> h_d(n);
    CUDA_CHECK(cudaMemcpy(h_d.data(), d_best, n*sizeof(Scalar), cudaMemcpyDeviceToHost));

    // ---- Anderson Acceleration: try to do better than the plain champion step using history ----
    std::vector<Scalar> applied = h_d;
    Scalar cost_final = cost_best;
    bool accepted_aa = false;
    bool used_s_aa = false;
    if (!Dx_hist.empty()) {
      int mcur = (int)Dx_hist.size();
      std::vector<std::vector<Scalar>> G(mcur, std::vector<Scalar>(mcur, 0.0));
      std::vector<Scalar> rhs(mcur, 0.0);
      for (int i = 0; i < mcur; ++i) {
        for (int j = 0; j < mcur; ++j) {
          Scalar dot = 0.0; for (int t = 0; t < n; ++t) dot += Df_hist[i][t]*Df_hist[j][t];
          G[i][j] = dot + (i == j ? aa_reg : (Scalar)0.0);
        }
        Scalar dot = 0.0; for (int t = 0; t < n; ++t) dot += Df_hist[i][t]*h_d[t];
        rhs[i] = dot;
      }
      std::vector<Scalar> gamma = SolveSmallSPD(G, rhs);
      std::vector<Scalar> d_aa(n);
      for (int t = 0; t < n; ++t) {
        Scalar corr = 0.0; for (int i = 0; i < mcur; ++i) corr += gamma[i]*Dx_hist[i][t];
        d_aa[t] = h_d[t] - corr;
      }
      CUDA_CHECK(cudaMemcpy(d_aa_dev, d_aa.data(), n*sizeof(Scalar), cudaMemcpyHostToDevice));
      Retract(p, s, d_aa_dev, s_aa);
      Scalar cost_aa = ComputeCost(p, s_aa);
      if (cost_aa < cost_final) {
        applied = d_aa; cost_final = cost_aa; accepted_aa = true; used_s_aa = true;
      }
    }

    if (!f_prev.empty()) {
      std::vector<Scalar> df(n);
      for (int t = 0; t < n; ++t) df[t] = h_d[t] - f_prev[t];
      Dx_hist.push_back(applied);
      Df_hist.push_back(df);
      if ((int)Dx_hist.size() > aa_window) { Dx_hist.erase(Dx_hist.begin()); Df_hist.erase(Df_hist.begin()); }
    }
    f_prev = h_d;

    if (used_s_aa) { std::swap(s.R, s_aa.R); std::swap(s.t, s_aa.t); std::swap(s.X, s_aa.X); }
    else { Retract(p, s, d_best, s_new); std::swap(s.R, s_new.R); std::swap(s.t, s_new.t); std::swap(s.X, s_new.X); }
    cost = cost_final;
    n_aa_accepted += (int)accepted_aa;

    Scalar step_norm = 0.0; for (auto v : applied) step_norm += v*v; step_norm = std::sqrt(step_norm);
    log.iters.push_back(k+1); log.costs.push_back(cost);
    if (verbose) std::printf("  OCA-Joint-CamPt-LD-AA it%4d cost=%.6e |d|=%.3e lam_cam=%.3e lam_pt=%.3e depth_best=%d n_esc=%d |grad|/|grad0|=%.3e %s\n",
                              k+1, cost, step_norm, lam_cam_best, lam_pt_best, depth_best, n_esc, grad_norm/grad_norm0, accepted_aa ? "[AA]" : "");
    if (step_norm < tol && grad_norm < 1e-8 * grad_norm0) break;
  }
  if (verbose) std::printf("  OCA-Joint-CamPt-LD-AA: AA accepted %d/%d iterations\n", n_aa_accepted, (int)log.iters.size()-1);

  cusolverDnDestroy(handle);
  if (subspace_min) { cublasDestroy(blas_sub); cudaFree(G_basis); cudaFree(G_best); cudaFree(Hv_col); cudaFree(d_sub); }
  cudaFree(Hcc); cudaFree(Hpp); cudaFree(obs_Hcp); cudaFree(grad_c); cudaFree(grad_p);
  cudaFree(App_inv); cudaFree(S); cudaFree(bc_corr); cudaFree(bc_prime); cudaFree(xc); cudaFree(xp);
  cudaFree(gc_prev); cudaFree(gp_prev); cudaFree(bp_j); cudaFree(bc_j); cudaFree(d); cudaFree(d_best); cudaFree(d_cand); cudaFree(d_aa_dev); cudaFree(ok_flags);
  cudaFree(s_new.R); cudaFree(s_new.t); cudaFree(s_new.X);
  cudaFree(s_aa.R); cudaFree(s_aa.t); cudaFree(s_aa.X);
  return log;
}

// ============================================================== Task: Section 7 (curvature-aware solver switching), adapted to the
// champion. SolveOCACurvatureSwitch's own version (below) is built on the
// TRUE-Hessian MINRES/Lanczos architecture, where the whole point of regime
// detection is to tell indefinite (unsafe) apart from confidently-PD (safe
// for a single cheap exact solve) via an explicit Lanczos + Sturm-sequence
// eigenvalue estimate. None of that applies here: the champion is built on
// the Gauss-Newton Hessian, which is provably PSD, so S(lam_cam,lam_pt) is
// unconditionally PD for any lam>0 -- there is no indefiniteness to detect,
// and running a Lanczos probe on a system with no curvature question to
// answer would be pure overhead with no information gained.
//
// What DOES transfer is the underlying shape of the idea, not its specific
// eigenvalue machinery: try a cheap single solve first, and only pay for the
// expensive multi-candidate search when the cheap one fails. Concretely: try
// ONE (lam_cam_center,lam_pt_center) pair (the champion's own currently-
// tracked scale, carried over from the previous iteration's escalation) --
// one Cholesky factorization plus its depth-checkpoint walk, exactly
// try_lambda_pair's normal per-candidate cost -- and accept it directly if
// it improves cost, skipping the OTHER (n_cam_candidates*n_pt_candidates-1)
// candidates entirely for that iteration. Only fall back to the full 2D
// grid + escalation when the cheap single trial doesn't improve. True-cost
// gated exactly like every other candidate class in this file.
RunLog SolveOCAJointLambdaCamPtDepthCurv(const DeviceProblem& p, DeviceState& s, Scalar lam0, Scalar tol,
                                          int max_iter, bool verbose, int n_cam_candidates = 3, int n_pt_candidates = 3,
                                          Scalar decade_span = 1.0, int max_escalations = 25,
                                          std::vector<int> depths = {0,1,2,4,8}, bool subspace_min = false) {
  int ncam = p.ncam, npt = p.npt, n_c = 6*ncam, n_p = 3*npt, n = n_c + n_p;
  Scalar *Hcc, *Hpp, *obs_Hcp, *grad_c, *grad_p, *App_inv, *S;
  Scalar *bc_corr, *bc_prime, *xc, *xp, *gc_prev, *gp_prev, *bp_j, *bc_j, *d, *d_best, *d_cand;
  int* ok_flags;
  int n_depths = (int)depths.size();
  Scalar *G_basis = nullptr, *G_best = nullptr, *Hv_col = nullptr, *d_sub = nullptr;
  cublasHandle_t blas_sub;
  if (subspace_min) {
    CUDA_CHECK(cudaMalloc(&G_basis, (size_t)n*n_depths*sizeof(Scalar)));
    CUDA_CHECK(cudaMalloc(&G_best, (size_t)n*n_depths*sizeof(Scalar)));
    CUDA_CHECK(cudaMalloc(&Hv_col, n*sizeof(Scalar)));
    CUDA_CHECK(cudaMalloc(&d_sub, n*sizeof(Scalar)));
    CUBLAS_CHECK(cublasCreate(&blas_sub));
  }
  CUDA_CHECK(cudaMalloc(&Hcc, 36*(size_t)ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&Hpp, 9*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&obs_Hcp, 18*(size_t)p.nobs*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&grad_c, 6*(size_t)ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&grad_p, 3*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&App_inv, 9*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&S, (size_t)n_c*n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bc_corr, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bc_prime, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&xc, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&xp, n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&gc_prev, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&gp_prev, n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bp_j, n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bc_j, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&d, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&d_best, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&d_cand, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&ok_flags, npt*sizeof(int)));
  DeviceState s_new; AllocState(s_new, ncam, npt);

  cusolverDnHandle_t handle; cusolverDnCreate(&handle);
  CholeskyWorkspace ws; ws.Init(handle, n_c);

  Scalar cost = ComputeCost(p, s);
  RunLog log; log.iters.push_back(0); log.costs.push_back(cost);
  Scalar lam_cam_center = lam0, lam_pt_center = lam0;
  Scalar grad_norm0 = -1.0;
  int max_depth = 0; for (int dd : depths) max_depth = std::max(max_depth, dd);
  int n_cheap_used = 0, n_full_used = 0;

  auto try_lambda_pair = [&](Scalar lam_cam, Scalar lam_pt, Scalar* d_out, int& depth_out) -> Scalar {
    KernelInvertAppBlocks<<<GridSize(npt),256>>>(Hpp, lam_pt, App_inv, ok_flags, npt);
    { std::vector<int> h_ok(npt);
      CUDA_CHECK(cudaMemcpy(h_ok.data(), ok_flags, npt*sizeof(int), cudaMemcpyDeviceToHost));
      for (int v : h_ok) if (!v) return std::numeric_limits<Scalar>::infinity();
    }
    CUDA_CHECK(cudaMemset(S, 0, (size_t)n_c*n_c*sizeof(Scalar)));
    KernelBuildAccFull<<<GridSize(ncam),256>>>(Hcc, lam_cam, S, ncam, n_c);
    KernelFormSSparse<<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                              App_inv, npt, n_c, S);
    if (!CholeskyFactor(ws, S)) return std::numeric_limits<Scalar>::infinity();

    Scalar best_cost = std::numeric_limits<Scalar>::infinity();
    depth_out = depths.empty() ? 0 : depths[0];
    CUDA_CHECK(cudaMemset(gc_prev, 0, n_c*sizeof(Scalar)));
    for (int j = 0; j <= max_depth; ++j) {
      CUDA_CHECK(cudaMemcpy(bp_j, grad_p, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      CUDA_CHECK(cudaMemcpy(bc_j, grad_c, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      if (j > 0) {
        KernelAxpy<<<GridSize(n_p),256>>>(bp_j, gp_prev, lam_pt, n_p);
        KernelAxpy<<<GridSize(n_c),256>>>(bc_j, gc_prev, lam_cam, n_c);
      }
      CUDA_CHECK(cudaMemset(bc_corr, 0, n_c*sizeof(Scalar)));
      KernelRHSCorrectionSparse<<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                                         App_inv, bp_j, npt, bc_corr);
      KernelSubtractVec<<<GridSize(n_c),256>>>(bc_prime, bc_j, bc_corr, n_c);
      CUDA_CHECK(cudaMemcpy(xc, bc_prime, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      CholeskySolveVec(ws, S, xc);
      KernelBackSubstituteSparse<<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                                          App_inv, bp_j, xc, npt, xp);
      CUDA_CHECK(cudaMemcpy(gc_prev, xc, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      CUDA_CHECK(cudaMemcpy(gp_prev, xp, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));

      if (std::find(depths.begin(), depths.end(), j) == depths.end()) continue;
      CUDA_CHECK(cudaMemcpy(d_cand, gc_prev, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      CUDA_CHECK(cudaMemcpy(d_cand+n_c, gp_prev, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      if (subspace_min) {
        int col = (int)(std::find(depths.begin(), depths.end(), j) - depths.begin());
        CUDA_CHECK(cudaMemcpy(G_basis + (size_t)col*n, d_cand, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      }
      KernelNegateInPlace<<<GridSize(n),256>>>(d_cand, n);
      Retract(p, s, d_cand, s_new);
      Scalar c = ComputeCost(p, s_new);
      if (c < best_cost) {
        best_cost = c; depth_out = j;
        CUDA_CHECK(cudaMemcpy(d_out, d_cand, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      }
    }
    return best_cost;
  };

  auto try_subspace_refine = [&](Scalar* d_best_io, Scalar& cost_best_io, int& depth_best_io) {
    std::vector<std::vector<Scalar>> Stilde(n_depths, std::vector<Scalar>(n_depths, 0.0));
    std::vector<Scalar> btilde(n_depths, 0.0);
    Scalar* bfull; CUDA_CHECK(cudaMalloc(&bfull, n*sizeof(Scalar)));
    CUDA_CHECK(cudaMemcpy(bfull, grad_c, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
    CUDA_CHECK(cudaMemcpy(bfull+n_c, grad_p, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));
    for (int col = 0; col < n_depths; ++col) {
      CUDA_CHECK(cudaMemset(Hv_col, 0, n*sizeof(Scalar)));
      KernelHgnMatVecCross<<<GridSize(p.nobs),256>>>(obs_Hcp, p.cam_idx, p.pt_idx, p.nobs,
                                                      G_best + (size_t)col*n, G_best + (size_t)col*n + n_c,
                                                      Hv_col, Hv_col + n_c);
      KernelHgnMatVecDiagCam<<<GridSize(ncam),256>>>(Hcc, ncam, G_best + (size_t)col*n, Hv_col);
      KernelHgnMatVecDiagPt<<<GridSize(npt),256>>>(Hpp, npt, G_best + (size_t)col*n + n_c, Hv_col + n_c);
      for (int row = 0; row < n_depths; ++row) {
        Scalar dot; CUBLAS_CHECK(cublasDdot(blas_sub, n, G_best + (size_t)row*n, 1, Hv_col, 1, &dot));
        Stilde[row][col] = dot;
      }
      Scalar bdot; CUBLAS_CHECK(cublasDdot(blas_sub, n, G_best + (size_t)col*n, 1, bfull, 1, &bdot));
      btilde[col] = bdot;
    }
    cudaFree(bfull);
    for (int i = 0; i < n_depths; ++i) Stilde[i][i] += 1e-9 * std::max(Stilde[i][i], (Scalar)1.0);
    std::vector<Scalar> alpha = SolveSmallSPD(Stilde, btilde);
    for (auto& v : alpha) v = -v;
    CUDA_CHECK(cudaMemcpy(Hv_col, alpha.data(), n_depths*sizeof(Scalar), cudaMemcpyHostToDevice));
    const Scalar one_ = 1.0, zero_ = 0.0;
    CUBLAS_CHECK(cublasDgemv(blas_sub, CUBLAS_OP_N, n, n_depths, &one_, G_best, n, Hv_col, 1, &zero_, d_sub, 1));
    Retract(p, s, d_sub, s_new);
    Scalar c_sub = ComputeCost(p, s_new);
    if (c_sub < cost_best_io) {
      cost_best_io = c_sub; depth_best_io = -1;
      CUDA_CHECK(cudaMemcpy(d_best_io, d_sub, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
    }
  };

  for (int k = 0; k < max_iter; ++k) {
    CUDA_CHECK(cudaMemset(Hcc, 0, 36*(size_t)ncam*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(Hpp, 0, 9*(size_t)npt*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(grad_c, 0, 6*(size_t)ncam*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(grad_p, 0, 3*(size_t)npt*sizeof(Scalar)));
    KernelAssembleSchurSparseGN<<<GridSize(p.nobs),256>>>(
        p.cam_idx, p.pt_idx, p.uv, s.R, s.t, s.X, p.f, p.k1, p.k2, p.nobs,
        Hcc, Hpp, obs_Hcp, grad_c, grad_p);

    Scalar grad_norm;
    { std::vector<Scalar> h_grad_full(n);
      CUDA_CHECK(cudaMemcpy(h_grad_full.data(), grad_c, n_c*sizeof(Scalar), cudaMemcpyDeviceToHost));
      CUDA_CHECK(cudaMemcpy(h_grad_full.data()+n_c, grad_p, n_p*sizeof(Scalar), cudaMemcpyDeviceToHost));
      Scalar s2 = 0.0; for (auto v : h_grad_full) s2 += v*v;
      grad_norm = std::sqrt(s2);
    }
    if (grad_norm0 < 0.0) grad_norm0 = std::max(grad_norm, (Scalar)1e-300);

    Scalar cost_current = cost, cost_best = std::numeric_limits<Scalar>::infinity();
    Scalar lam_cam_best = lam_cam_center, lam_pt_best = lam_pt_center;
    int depth_best = 0, n_esc = 0;
    bool used_cheap = false;

    // ---- cheap branch: ONE trial at the currently-tracked (lam_cam_center,lam_pt_center) ----
    {
      int depth_this;
      Scalar c = try_lambda_pair(lam_cam_center, lam_pt_center, d, depth_this);
      if (c < cost_current) {
        cost_best = c; lam_cam_best = lam_cam_center; lam_pt_best = lam_pt_center; depth_best = depth_this;
        CUDA_CHECK(cudaMemcpy(d_best, d, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
        if (subspace_min) CUDA_CHECK(cudaMemcpy(G_best, G_basis, (size_t)n*n_depths*sizeof(Scalar), cudaMemcpyDeviceToDevice));
        used_cheap = true;
      }
    }

    // ---- fall back to the full 2D grid + escalation only if the cheap trial didn't improve ----
    if (!used_cheap) {
      for (;; ++n_esc) {
        cost_best = std::numeric_limits<Scalar>::infinity();
        for (int ci = 0; ci < n_cam_candidates; ++ci) {
          Scalar frac_c = n_cam_candidates > 1 ? (Scalar)ci / (n_cam_candidates - 1) : 0.5;
          Scalar lam_cam_val = lam_cam_center * std::pow((Scalar)10.0, -decade_span + 2.0*decade_span*frac_c);
          for (int pi = 0; pi < n_pt_candidates; ++pi) {
            Scalar frac_p = n_pt_candidates > 1 ? (Scalar)pi / (n_pt_candidates - 1) : 0.5;
            Scalar lam_pt_val = lam_pt_center * std::pow((Scalar)10.0, -decade_span + 2.0*decade_span*frac_p);
            int depth_this;
            Scalar c = try_lambda_pair(lam_cam_val, lam_pt_val, d, depth_this);
            if (c < cost_best) {
              cost_best = c; lam_cam_best = lam_cam_val; lam_pt_best = lam_pt_val; depth_best = depth_this;
              CUDA_CHECK(cudaMemcpy(d_best, d, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
              if (subspace_min) CUDA_CHECK(cudaMemcpy(G_best, G_basis, (size_t)n*n_depths*sizeof(Scalar), cudaMemcpyDeviceToDevice));
            }
          }
        }
        if (cost_best < cost_current || n_esc >= max_escalations) break;
        lam_cam_center *= 10.0; lam_pt_center *= 10.0;
      }
    }

    if (cost_best >= cost_current) {
      if (verbose) std::printf("  OCA-Joint-CamPt-LD-Curv: converged / no improving combo found at k=%d (cost=%.6e)\n", k, cost);
      break;
    }
    if (subspace_min) try_subspace_refine(d_best, cost_best, depth_best);
    if (used_cheap) { n_cheap_used++; } else { n_full_used++; }
    lam_cam_center = std::max(lam_cam_best * 0.5, lam0 * 1e-8);
    lam_pt_center = std::max(lam_pt_best * 0.5, lam0 * 1e-8);

    Retract(p, s, d_best, s_new);
    std::swap(s.R, s_new.R); std::swap(s.t, s_new.t); std::swap(s.X, s_new.X);
    cost = cost_best;

    std::vector<Scalar> h_d(n);
    CUDA_CHECK(cudaMemcpy(h_d.data(), d_best, n*sizeof(Scalar), cudaMemcpyDeviceToHost));
    Scalar step_norm = 0.0; for (auto v : h_d) step_norm += v*v; step_norm = std::sqrt(step_norm);

    log.iters.push_back(k+1); log.costs.push_back(cost);
    if (verbose) std::printf("  OCA-Joint-CamPt-LD-Curv it%4d cost=%.6e |d|=%.3e lam_cam=%.3e lam_pt=%.3e depth_best=%d n_esc=%d mode=%-5s |grad|/|grad0|=%.3e\n",
                              k+1, cost, step_norm, lam_cam_best, lam_pt_best, depth_best, n_esc, used_cheap ? "cheap" : "full", grad_norm/grad_norm0);
    if (step_norm < tol && grad_norm < 1e-8 * grad_norm0) break;
  }
  if (verbose) std::printf("  OCA-Joint-CamPt-LD-Curv: cheap-branch used %d/%d iterations, full grid used %d/%d\n",
                            n_cheap_used, (int)log.iters.size()-1, n_full_used, (int)log.iters.size()-1);

  cusolverDnDestroy(handle);
  if (subspace_min) { cublasDestroy(blas_sub); cudaFree(G_basis); cudaFree(G_best); cudaFree(Hv_col); cudaFree(d_sub); }
  cudaFree(Hcc); cudaFree(Hpp); cudaFree(obs_Hcp); cudaFree(grad_c); cudaFree(grad_p);
  cudaFree(App_inv); cudaFree(S); cudaFree(bc_corr); cudaFree(bc_prime); cudaFree(xc); cudaFree(xp);
  cudaFree(gc_prev); cudaFree(gp_prev); cudaFree(bp_j); cudaFree(bc_j); cudaFree(d); cudaFree(d_best); cudaFree(d_cand); cudaFree(ok_flags);
  cudaFree(s_new.R); cudaFree(s_new.t); cudaFree(s_new.X);
  return log;
}

// ============================================================== Task: Section 3 (outer Nesterov momentum, "the momentum DABA actually
// uses") wrapped around the champion. Matches SolveOCAPartitionedNesterov's
// established design (see that function's own comment for the full FISTA
// derivation) -- momentum lives at the OUTER iterate sequence
// (x_bar_k = Retract(x_k, gamma_k*d_{k-1})), NOT inside OCA's inner
// recursion, and the extrapolated candidate is accepted only if it beats
// TRUE cost; on reject, momentum resets and a plain gamma=0 step from the
// ACTUAL current point is taken instead -- so this only pays for the
// champion's full (expensive) 2D-grid+depth-checkpoint search TWICE on an
// iteration where momentum fails, not on every iteration. Unlike
// SolveOCAPartitionedNesterov (which pins depth=1 and drops camera-point
// coupling to isolate the momentum mechanism on its own), this wraps the
// champion's OWN full per-iteration solve unchanged -- same structured
// cam/pt 2D grid, same depth-checkpoint menu, same optional subspace
// refinement -- so assembly and the per-candidate solve are parameterized on
// an explicit `from_state` instead of implicitly closing over `s`.
RunLog SolveOCAJointLambdaCamPtDepthNesterov(const DeviceProblem& p, DeviceState& s, Scalar lam0, Scalar tol,
                                              int max_iter, bool verbose, int n_cam_candidates = 3, int n_pt_candidates = 3,
                                              Scalar decade_span = 1.0, int max_escalations = 25,
                                              std::vector<int> depths = {0,1,2,4,8}, bool subspace_min = false,
                                              bool use_momentum = true, Scalar gamma_cap = 1.0) {
  int ncam = p.ncam, npt = p.npt, n_c = 6*ncam, n_p = 3*npt, n = n_c + n_p;
  Scalar *Hcc, *Hpp, *obs_Hcp, *grad_c, *grad_p, *App_inv, *S;
  Scalar *bc_corr, *bc_prime, *xc, *xp, *gc_prev, *gp_prev, *bp_j, *bc_j, *d, *d_best, *d_cand;
  Scalar *d_bar, *d_prev;
  int* ok_flags;
  int n_depths = (int)depths.size();
  Scalar *G_basis = nullptr, *G_best = nullptr, *Hv_col = nullptr, *d_sub = nullptr;
  cublasHandle_t blas_sub;
  if (subspace_min) {
    CUDA_CHECK(cudaMalloc(&G_basis, (size_t)n*n_depths*sizeof(Scalar)));
    CUDA_CHECK(cudaMalloc(&G_best, (size_t)n*n_depths*sizeof(Scalar)));
    CUDA_CHECK(cudaMalloc(&Hv_col, n*sizeof(Scalar)));
    CUDA_CHECK(cudaMalloc(&d_sub, n*sizeof(Scalar)));
    CUBLAS_CHECK(cublasCreate(&blas_sub));
  }
  CUDA_CHECK(cudaMalloc(&Hcc, 36*(size_t)ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&Hpp, 9*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&obs_Hcp, 18*(size_t)p.nobs*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&grad_c, 6*(size_t)ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&grad_p, 3*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&App_inv, 9*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&S, (size_t)n_c*n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bc_corr, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bc_prime, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&xc, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&xp, n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&gc_prev, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&gp_prev, n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bp_j, n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bc_j, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&d, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&d_best, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&d_cand, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&d_bar, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&d_prev, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMemset(d_prev, 0, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&ok_flags, npt*sizeof(int)));
  DeviceState s_new; AllocState(s_new, ncam, npt);
  DeviceState s_bar; AllocState(s_bar, ncam, npt);
  DeviceState s_cand; AllocState(s_cand, ncam, npt);

  cusolverDnHandle_t handle; cusolverDnCreate(&handle);
  CholeskyWorkspace ws; ws.Init(handle, n_c);

  Scalar grad_norm0 = -1.0;
  int max_depth = 0; for (int dd : depths) max_depth = std::max(max_depth, dd);

  // Identical to the champion's own try_lambda_pair/try_subspace_refine, except assembly and
  // retraction both operate on an explicit `from` state instead of implicitly closing over `s`.
  Scalar *cur_grad_c = grad_c, *cur_grad_p = grad_p;  // aliases so try_lambda_pair/try_subspace_refine read this iteration's assembled gradient regardless of which state it was assembled from
  const DeviceState* from_ptr = &s;
  auto try_lambda_pair = [&](Scalar lam_cam, Scalar lam_pt, Scalar* d_out, int& depth_out) -> Scalar {
    KernelInvertAppBlocks<<<GridSize(npt),256>>>(Hpp, lam_pt, App_inv, ok_flags, npt);
    { std::vector<int> h_ok(npt);
      CUDA_CHECK(cudaMemcpy(h_ok.data(), ok_flags, npt*sizeof(int), cudaMemcpyDeviceToHost));
      for (int v : h_ok) if (!v) return std::numeric_limits<Scalar>::infinity();
    }
    CUDA_CHECK(cudaMemset(S, 0, (size_t)n_c*n_c*sizeof(Scalar)));
    KernelBuildAccFull<<<GridSize(ncam),256>>>(Hcc, lam_cam, S, ncam, n_c);
    KernelFormSSparse<<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                              App_inv, npt, n_c, S);
    if (!CholeskyFactor(ws, S)) return std::numeric_limits<Scalar>::infinity();

    Scalar best_cost = std::numeric_limits<Scalar>::infinity();
    depth_out = depths.empty() ? 0 : depths[0];
    CUDA_CHECK(cudaMemset(gc_prev, 0, n_c*sizeof(Scalar)));
    for (int j = 0; j <= max_depth; ++j) {
      CUDA_CHECK(cudaMemcpy(bp_j, cur_grad_p, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      CUDA_CHECK(cudaMemcpy(bc_j, cur_grad_c, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      if (j > 0) {
        KernelAxpy<<<GridSize(n_p),256>>>(bp_j, gp_prev, lam_pt, n_p);
        KernelAxpy<<<GridSize(n_c),256>>>(bc_j, gc_prev, lam_cam, n_c);
      }
      CUDA_CHECK(cudaMemset(bc_corr, 0, n_c*sizeof(Scalar)));
      KernelRHSCorrectionSparse<<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                                         App_inv, bp_j, npt, bc_corr);
      KernelSubtractVec<<<GridSize(n_c),256>>>(bc_prime, bc_j, bc_corr, n_c);
      CUDA_CHECK(cudaMemcpy(xc, bc_prime, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      CholeskySolveVec(ws, S, xc);
      KernelBackSubstituteSparse<<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                                          App_inv, bp_j, xc, npt, xp);
      CUDA_CHECK(cudaMemcpy(gc_prev, xc, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      CUDA_CHECK(cudaMemcpy(gp_prev, xp, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));

      if (std::find(depths.begin(), depths.end(), j) == depths.end()) continue;
      CUDA_CHECK(cudaMemcpy(d_cand, gc_prev, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      CUDA_CHECK(cudaMemcpy(d_cand+n_c, gp_prev, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      if (subspace_min) {
        int col = (int)(std::find(depths.begin(), depths.end(), j) - depths.begin());
        CUDA_CHECK(cudaMemcpy(G_basis + (size_t)col*n, d_cand, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      }
      KernelNegateInPlace<<<GridSize(n),256>>>(d_cand, n);
      Retract(p, *from_ptr, d_cand, s_new);
      Scalar c = ComputeCost(p, s_new);
      if (c < best_cost) {
        best_cost = c; depth_out = j;
        CUDA_CHECK(cudaMemcpy(d_out, d_cand, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      }
    }
    return best_cost;
  };

  auto try_subspace_refine = [&](Scalar* d_best_io, Scalar& cost_best_io, int& depth_best_io) {
    std::vector<std::vector<Scalar>> Stilde(n_depths, std::vector<Scalar>(n_depths, 0.0));
    std::vector<Scalar> btilde(n_depths, 0.0);
    Scalar* bfull; CUDA_CHECK(cudaMalloc(&bfull, n*sizeof(Scalar)));
    CUDA_CHECK(cudaMemcpy(bfull, cur_grad_c, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
    CUDA_CHECK(cudaMemcpy(bfull+n_c, cur_grad_p, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));
    for (int col = 0; col < n_depths; ++col) {
      CUDA_CHECK(cudaMemset(Hv_col, 0, n*sizeof(Scalar)));
      KernelHgnMatVecCross<<<GridSize(p.nobs),256>>>(obs_Hcp, p.cam_idx, p.pt_idx, p.nobs,
                                                      G_best + (size_t)col*n, G_best + (size_t)col*n + n_c,
                                                      Hv_col, Hv_col + n_c);
      KernelHgnMatVecDiagCam<<<GridSize(ncam),256>>>(Hcc, ncam, G_best + (size_t)col*n, Hv_col);
      KernelHgnMatVecDiagPt<<<GridSize(npt),256>>>(Hpp, npt, G_best + (size_t)col*n + n_c, Hv_col + n_c);
      for (int row = 0; row < n_depths; ++row) {
        Scalar dot; CUBLAS_CHECK(cublasDdot(blas_sub, n, G_best + (size_t)row*n, 1, Hv_col, 1, &dot));
        Stilde[row][col] = dot;
      }
      Scalar bdot; CUBLAS_CHECK(cublasDdot(blas_sub, n, G_best + (size_t)col*n, 1, bfull, 1, &bdot));
      btilde[col] = bdot;
    }
    cudaFree(bfull);
    for (int i = 0; i < n_depths; ++i) Stilde[i][i] += 1e-9 * std::max(Stilde[i][i], (Scalar)1.0);
    std::vector<Scalar> alpha = SolveSmallSPD(Stilde, btilde);
    for (auto& v : alpha) v = -v;
    CUDA_CHECK(cudaMemcpy(Hv_col, alpha.data(), n_depths*sizeof(Scalar), cudaMemcpyHostToDevice));
    const Scalar one_ = 1.0, zero_ = 0.0;
    CUBLAS_CHECK(cublasDgemv(blas_sub, CUBLAS_OP_N, n, n_depths, &one_, G_best, n, Hv_col, 1, &zero_, d_sub, 1));
    Retract(p, *from_ptr, d_sub, s_new);
    Scalar c_sub = ComputeCost(p, s_new);
    if (c_sub < cost_best_io) {
      cost_best_io = c_sub; depth_best_io = -1;
      CUDA_CHECK(cudaMemcpy(d_best_io, d_sub, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
    }
  };

  // Runs the champion's FULL per-iteration search (assemble at `from`, 2D lambda grid + depth
  // checkpoint, optional subspace refine) and writes the resulting state into `to`. Returns the
  // new cost and the applied tangent step (in `from`'s frame, host vector) via `step_out`.
  Scalar lam_cam_center = lam0, lam_pt_center = lam0;
  auto run_full_search = [&](const DeviceState& from, DeviceState& to, std::vector<Scalar>& step_out) -> Scalar {
    from_ptr = &from;
    CUDA_CHECK(cudaMemset(Hcc, 0, 36*(size_t)ncam*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(Hpp, 0, 9*(size_t)npt*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(grad_c, 0, 6*(size_t)ncam*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(grad_p, 0, 3*(size_t)npt*sizeof(Scalar)));
    KernelAssembleSchurSparseGN<<<GridSize(p.nobs),256>>>(
        p.cam_idx, p.pt_idx, p.uv, from.R, from.t, from.X, p.f, p.k1, p.k2, p.nobs,
        Hcc, Hpp, obs_Hcp, grad_c, grad_p);

    Scalar cost_from = ComputeCost(p, from);
    Scalar cost_current = cost_from, cost_best = std::numeric_limits<Scalar>::infinity();
    Scalar lam_cam_best = lam_cam_center, lam_pt_best = lam_pt_center;
    int depth_best = 0, n_esc = 0;
    for (;; ++n_esc) {
      cost_best = std::numeric_limits<Scalar>::infinity();
      for (int ci = 0; ci < n_cam_candidates; ++ci) {
        Scalar frac_c = n_cam_candidates > 1 ? (Scalar)ci / (n_cam_candidates - 1) : 0.5;
        Scalar lam_cam_val = lam_cam_center * std::pow((Scalar)10.0, -decade_span + 2.0*decade_span*frac_c);
        for (int pi = 0; pi < n_pt_candidates; ++pi) {
          Scalar frac_p = n_pt_candidates > 1 ? (Scalar)pi / (n_pt_candidates - 1) : 0.5;
          Scalar lam_pt_val = lam_pt_center * std::pow((Scalar)10.0, -decade_span + 2.0*decade_span*frac_p);
          int depth_this;
          Scalar c = try_lambda_pair(lam_cam_val, lam_pt_val, d, depth_this);
          if (c < cost_best) {
            cost_best = c; lam_cam_best = lam_cam_val; lam_pt_best = lam_pt_val; depth_best = depth_this;
            CUDA_CHECK(cudaMemcpy(d_best, d, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
            if (subspace_min) CUDA_CHECK(cudaMemcpy(G_best, G_basis, (size_t)n*n_depths*sizeof(Scalar), cudaMemcpyDeviceToDevice));
          }
        }
      }
      if (cost_best < cost_current || n_esc >= max_escalations) break;
      lam_cam_center *= 10.0; lam_pt_center *= 10.0;
    }

    if (cost_best >= cost_current) return std::numeric_limits<Scalar>::infinity();  // caller checks vs its own reference cost
    if (subspace_min) try_subspace_refine(d_best, cost_best, depth_best);
    lam_cam_center = std::max(lam_cam_best * 0.5, lam0 * 1e-8);
    lam_pt_center = std::max(lam_pt_best * 0.5, lam0 * 1e-8);

    step_out.resize(n);
    CUDA_CHECK(cudaMemcpy(step_out.data(), d_best, n*sizeof(Scalar), cudaMemcpyDeviceToHost));
    Retract(p, from, d_best, to);
    return cost_best;
  };

  Scalar cost = ComputeCost(p, s);
  RunLog log; log.iters.push_back(0); log.costs.push_back(cost);
  Scalar t_mom = 1.0;
  int n_restarts = 0;
  int n_cheir_blocked = 0;
  // Cheirality safety margin for the accept-gate below -- see CountCheiralityViolations'
  // comment for why this guard exists at all (true cost alone cannot detect a point flipped
  // behind its camera). Permissive on purpose: every solver in this file's own accepted steps
  // already drift cheirality violations up gradually over an entire run (single digits to a few
  // dozen, out of thousands of observations) as ordinary, harmless optimization noise -- this
  // must not block that. It only needs to catch a single-step catastrophe (the observed failure
  // flipped ~all of nobs in ONE iteration), so the bar is deliberately far above normal drift.
  int cheir_margin = std::max(20, (int)(0.01 * p.nobs));
  int cheir_cur = CountCheiralityViolations(p, s);

  for (int k = 0; k < max_iter; ++k) {
    Scalar t_new = (1.0 + std::sqrt(1.0 + 4.0*t_mom*t_mom)) / 2.0;
    Scalar gamma = use_momentum ? std::min((t_mom - 1.0) / t_new, gamma_cap) : 0.0;

    std::vector<Scalar> h_dprev(n);
    CUDA_CHECK(cudaMemcpy(h_dprev.data(), d_prev, n*sizeof(Scalar), cudaMemcpyDeviceToHost));
    for (auto& v : h_dprev) v *= gamma;
    CUDA_CHECK(cudaMemcpy(d_bar, h_dprev.data(), n*sizeof(Scalar), cudaMemcpyHostToDevice));
    Retract(p, s, d_bar, s_bar);

    std::vector<Scalar> step_extrap;
    Scalar cost_extrap = run_full_search(s_bar, s_cand, step_extrap);
    bool extrap_cheir_ok = true;
    if (cost_extrap < cost) {
      int c_extrap = CountCheiralityViolations(p, s_cand);
      if (c_extrap > cheir_cur + cheir_margin) { extrap_cheir_ok = false; ++n_cheir_blocked; }
    }

    bool accepted;
    Scalar step_norm;
    Scalar grad_norm;
    { std::vector<Scalar> h_grad_full(n);
      CUDA_CHECK(cudaMemcpy(h_grad_full.data(), grad_c, n_c*sizeof(Scalar), cudaMemcpyDeviceToHost));
      CUDA_CHECK(cudaMemcpy(h_grad_full.data()+n_c, grad_p, n_p*sizeof(Scalar), cudaMemcpyDeviceToHost));
      Scalar s2 = 0.0; for (auto v : h_grad_full) s2 += v*v;
      grad_norm = std::sqrt(s2);
    }
    if (grad_norm0 < 0.0) grad_norm0 = std::max(grad_norm, (Scalar)1e-300);

    if (cost_extrap < cost && extrap_cheir_ok) {
      accepted = true;
      std::swap(s.R, s_cand.R); std::swap(s.t, s_cand.t); std::swap(s.X, s_cand.X);
      cost = cost_extrap;
      cheir_cur = CountCheiralityViolations(p, s);
      std::vector<Scalar> h_dnew(n);
      for (int i = 0; i < n; ++i) h_dnew[i] = h_dprev[i] + step_extrap[i];
      CUDA_CHECK(cudaMemcpy(d_prev, h_dnew.data(), n*sizeof(Scalar), cudaMemcpyHostToDevice));
      t_mom = t_new;
      step_norm = 0.0; for (auto v : step_extrap) step_norm += v*v; step_norm = std::sqrt(step_norm);
    } else {
      accepted = false;
      ++n_restarts;
      std::vector<Scalar> step_plain;
      Scalar cost_plain = run_full_search(s, s_cand, step_plain);
      bool plain_cheir_ok = true;
      if (cost_plain < cost) {
        int c_plain = CountCheiralityViolations(p, s_cand);
        if (c_plain > cheir_cur + cheir_margin) plain_cheir_ok = false;
      }
      if (cost_plain >= cost || !plain_cheir_ok) {
        if (verbose) std::printf("  OCA-Joint-CamPt-LD-Nesterov: converged / no improving step found at k=%d (cost=%.6e)\n", k, cost);
        break;
      }
      std::swap(s.R, s_cand.R); std::swap(s.t, s_cand.t); std::swap(s.X, s_cand.X);
      cost = cost_plain;
      cheir_cur = CountCheiralityViolations(p, s);
      CUDA_CHECK(cudaMemcpy(d_prev, step_plain.data(), n*sizeof(Scalar), cudaMemcpyHostToDevice));
      t_mom = 1.0;
      step_norm = 0.0; for (auto v : step_plain) step_norm += v*v; step_norm = std::sqrt(step_norm);
    }

    log.iters.push_back(k+1); log.costs.push_back(cost);
    if (verbose) std::printf("  OCA-Joint-CamPt-LD-Nesterov it%4d cost=%.6e |d|=%.3e gamma=%.3f cheir=%d |grad|/|grad0|=%.3e %s\n",
                              k+1, cost, step_norm, gamma, cheir_cur, grad_norm/grad_norm0, accepted ? "" : "[restart]");
    if (step_norm < tol && grad_norm < 1e-8 * grad_norm0) break;
  }
  if (verbose) std::printf("  OCA-Joint-CamPt-LD-Nesterov: %d/%d iterations restarted, %d candidates blocked by cheirality safety gate\n",
                            n_restarts, (int)log.iters.size()-1, n_cheir_blocked);

  cusolverDnDestroy(handle);
  if (subspace_min) { cublasDestroy(blas_sub); cudaFree(G_basis); cudaFree(G_best); cudaFree(Hv_col); cudaFree(d_sub); }
  cudaFree(Hcc); cudaFree(Hpp); cudaFree(obs_Hcp); cudaFree(grad_c); cudaFree(grad_p);
  cudaFree(App_inv); cudaFree(S); cudaFree(bc_corr); cudaFree(bc_prime); cudaFree(xc); cudaFree(xp);
  cudaFree(gc_prev); cudaFree(gp_prev); cudaFree(bp_j); cudaFree(bc_j); cudaFree(d); cudaFree(d_best); cudaFree(d_cand);
  cudaFree(d_bar); cudaFree(d_prev); cudaFree(ok_flags);
  cudaFree(s_new.R); cudaFree(s_new.t); cudaFree(s_new.X);
  cudaFree(s_bar.R); cudaFree(s_bar.t); cudaFree(s_bar.X);
  cudaFree(s_cand.R); cudaFree(s_cand.t); cudaFree(s_cand.X);
  return log;
}

// ============================================================== Task: "Principled subspace momentum" (cross-model synthesis document,
// attributed to Claude there) -- structurally the SAME idea as P3's subspace
// minimization above (SolveOCAJointLambdaCamPtDepth's try_subspace_refine),
// reusing the identical machinery (matrix-free H_gn@v via
// KernelHgnMatVecCross/DiagCam/DiagPt, SolveSmallSPD for the small
// projected-normal-equations solve), but with a DIFFERENT basis: instead of
// this iteration's depth-checkpoint vectors g_0,g_1,...,g_8 (all live only
// within one outer iteration), the basis is [d_best, dx_{t-1}, ..., dx_{t-m}]
// -- the CURRENT champion step plus the last m ACCEPTED OUTER steps. This is
// the same "recovers Anderson-type acceleration in the linear regime,
// degrades gracefully to GN otherwise" property P3 already has (checkpoint
// selection / plain-GN-step selection is the special case alpha=one-hot),
// just applied one level up. Unlike SolveOCAJointLambdaCamPtDepthAA's
// Type-I Anderson (least-squares fit to Df history), the momentum
// coefficients here are chosen by minimizing the TRUE local GN quadratic
// model over the basis (the doc's own distinguishing description), with an
// explicit trust-region cap on the combined step's norm relative to the
// plain step's -- the safety margin the doc calls out as necessary since,
// unlike P3's depth-checkpoint basis (all generated from the SAME
// factorization at the SAME point), history vectors come from DIFFERENT
// points/Hessians, so the local quadratic model is a much rougher
// approximation this far from where most of the basis was generated.
RunLog SolveOCAJointLambdaCamPtDepthSubspaceMomentum(const DeviceProblem& p, DeviceState& s, Scalar lam0, Scalar tol,
                                                       int max_iter, bool verbose, int n_cam_candidates = 3, int n_pt_candidates = 3,
                                                       Scalar decade_span = 1.0, int max_escalations = 25,
                                                       std::vector<int> depths = {0,1,2,4,8}, int mom_window = 6,
                                                       Scalar trust_radius = 2.0, Scalar reg = 1e-9) {
  int ncam = p.ncam, npt = p.npt, n_c = 6*ncam, n_p = 3*npt, n = n_c + n_p;
  Scalar *Hcc, *Hpp, *obs_Hcp, *grad_c, *grad_p, *App_inv, *S;
  Scalar *bc_corr, *bc_prime, *xc, *xp, *gc_prev, *gp_prev, *bp_j, *bc_j, *d, *d_best, *d_cand;
  Scalar *G_basis, *Hv_col, *d_mom;
  int* ok_flags;
  int max_basis = mom_window + 1;  // +1 for d_best itself
  CUDA_CHECK(cudaMalloc(&G_basis, (size_t)n*max_basis*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&Hv_col, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&d_mom, n*sizeof(Scalar)));
  cublasHandle_t blas_sub; CUBLAS_CHECK(cublasCreate(&blas_sub));
  CUDA_CHECK(cudaMalloc(&Hcc, 36*(size_t)ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&Hpp, 9*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&obs_Hcp, 18*(size_t)p.nobs*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&grad_c, 6*(size_t)ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&grad_p, 3*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&App_inv, 9*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&S, (size_t)n_c*n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bc_corr, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bc_prime, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&xc, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&xp, n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&gc_prev, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&gp_prev, n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bp_j, n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bc_j, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&d, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&d_best, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&d_cand, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&ok_flags, npt*sizeof(int)));
  DeviceState s_new; AllocState(s_new, ncam, npt);

  cusolverDnHandle_t handle; cusolverDnCreate(&handle);
  CholeskyWorkspace ws; ws.Init(handle, n_c);

  Scalar cost = ComputeCost(p, s);
  RunLog log; log.iters.push_back(0); log.costs.push_back(cost);
  Scalar lam_cam_center = lam0, lam_pt_center = lam0;
  Scalar grad_norm0 = -1.0;
  int max_depth = 0; for (int dd : depths) max_depth = std::max(max_depth, dd);
  int n_mom_accepted = 0;
  std::deque<std::vector<Scalar>> hist;  // last mom_window ACCEPTED tangent steps, host vectors

  auto try_lambda_pair = [&](Scalar lam_cam, Scalar lam_pt, Scalar* d_out, int& depth_out) -> Scalar {
    KernelInvertAppBlocks<<<GridSize(npt),256>>>(Hpp, lam_pt, App_inv, ok_flags, npt);
    { std::vector<int> h_ok(npt);
      CUDA_CHECK(cudaMemcpy(h_ok.data(), ok_flags, npt*sizeof(int), cudaMemcpyDeviceToHost));
      for (int v : h_ok) if (!v) return std::numeric_limits<Scalar>::infinity();
    }
    CUDA_CHECK(cudaMemset(S, 0, (size_t)n_c*n_c*sizeof(Scalar)));
    KernelBuildAccFull<<<GridSize(ncam),256>>>(Hcc, lam_cam, S, ncam, n_c);
    KernelFormSSparse<<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                              App_inv, npt, n_c, S);
    if (!CholeskyFactor(ws, S)) return std::numeric_limits<Scalar>::infinity();

    Scalar best_cost = std::numeric_limits<Scalar>::infinity();
    depth_out = depths.empty() ? 0 : depths[0];
    CUDA_CHECK(cudaMemset(gc_prev, 0, n_c*sizeof(Scalar)));
    for (int j = 0; j <= max_depth; ++j) {
      CUDA_CHECK(cudaMemcpy(bp_j, grad_p, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      CUDA_CHECK(cudaMemcpy(bc_j, grad_c, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      if (j > 0) {
        KernelAxpy<<<GridSize(n_p),256>>>(bp_j, gp_prev, lam_pt, n_p);
        KernelAxpy<<<GridSize(n_c),256>>>(bc_j, gc_prev, lam_cam, n_c);
      }
      CUDA_CHECK(cudaMemset(bc_corr, 0, n_c*sizeof(Scalar)));
      KernelRHSCorrectionSparse<<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                                         App_inv, bp_j, npt, bc_corr);
      KernelSubtractVec<<<GridSize(n_c),256>>>(bc_prime, bc_j, bc_corr, n_c);
      CUDA_CHECK(cudaMemcpy(xc, bc_prime, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      CholeskySolveVec(ws, S, xc);
      KernelBackSubstituteSparse<<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                                          App_inv, bp_j, xc, npt, xp);
      CUDA_CHECK(cudaMemcpy(gc_prev, xc, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      CUDA_CHECK(cudaMemcpy(gp_prev, xp, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));

      if (std::find(depths.begin(), depths.end(), j) == depths.end()) continue;
      CUDA_CHECK(cudaMemcpy(d_cand, gc_prev, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      CUDA_CHECK(cudaMemcpy(d_cand+n_c, gp_prev, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      KernelNegateInPlace<<<GridSize(n),256>>>(d_cand, n);
      Retract(p, s, d_cand, s_new);
      Scalar c = ComputeCost(p, s_new);
      if (c < best_cost) {
        best_cost = c; depth_out = j;
        CUDA_CHECK(cudaMemcpy(d_out, d_cand, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      }
    }
    return best_cost;
  };

  for (int k = 0; k < max_iter; ++k) {
    CUDA_CHECK(cudaMemset(Hcc, 0, 36*(size_t)ncam*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(Hpp, 0, 9*(size_t)npt*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(grad_c, 0, 6*(size_t)ncam*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(grad_p, 0, 3*(size_t)npt*sizeof(Scalar)));
    KernelAssembleSchurSparseGN<<<GridSize(p.nobs),256>>>(
        p.cam_idx, p.pt_idx, p.uv, s.R, s.t, s.X, p.f, p.k1, p.k2, p.nobs,
        Hcc, Hpp, obs_Hcp, grad_c, grad_p);

    Scalar grad_norm;
    { std::vector<Scalar> h_grad_full(n);
      CUDA_CHECK(cudaMemcpy(h_grad_full.data(), grad_c, n_c*sizeof(Scalar), cudaMemcpyDeviceToHost));
      CUDA_CHECK(cudaMemcpy(h_grad_full.data()+n_c, grad_p, n_p*sizeof(Scalar), cudaMemcpyDeviceToHost));
      Scalar s2 = 0.0; for (auto v : h_grad_full) s2 += v*v;
      grad_norm = std::sqrt(s2);
    }
    if (grad_norm0 < 0.0) grad_norm0 = std::max(grad_norm, (Scalar)1e-300);

    Scalar cost_current = cost, cost_best = std::numeric_limits<Scalar>::infinity();
    Scalar lam_cam_best = lam_cam_center, lam_pt_best = lam_pt_center;
    int depth_best = 0, n_esc = 0;
    for (;; ++n_esc) {
      cost_best = std::numeric_limits<Scalar>::infinity();
      for (int ci = 0; ci < n_cam_candidates; ++ci) {
        Scalar frac_c = n_cam_candidates > 1 ? (Scalar)ci / (n_cam_candidates - 1) : 0.5;
        Scalar lam_cam_val = lam_cam_center * std::pow((Scalar)10.0, -decade_span + 2.0*decade_span*frac_c);
        for (int pi = 0; pi < n_pt_candidates; ++pi) {
          Scalar frac_p = n_pt_candidates > 1 ? (Scalar)pi / (n_pt_candidates - 1) : 0.5;
          Scalar lam_pt_val = lam_pt_center * std::pow((Scalar)10.0, -decade_span + 2.0*decade_span*frac_p);
          int depth_this;
          Scalar c = try_lambda_pair(lam_cam_val, lam_pt_val, d, depth_this);
          if (c < cost_best) {
            cost_best = c; lam_cam_best = lam_cam_val; lam_pt_best = lam_pt_val; depth_best = depth_this;
            CUDA_CHECK(cudaMemcpy(d_best, d, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
          }
        }
      }
      if (cost_best < cost_current || n_esc >= max_escalations) break;
      lam_cam_center *= 10.0; lam_pt_center *= 10.0;
    }

    if (cost_best >= cost_current) {
      if (verbose) std::printf("  OCA-Joint-CamPt-LD-SubMom: converged / no improving combo found at k=%d (cost=%.6e)\n", k, cost);
      break;
    }
    lam_cam_center = std::max(lam_cam_best * 0.5, lam0 * 1e-8);
    lam_pt_center = std::max(lam_pt_best * 0.5, lam0 * 1e-8);

    // ---- principled subspace momentum: basis = [d_best, hist...], coefficients from the
    // true local GN quadratic model, trust-region capped, true-cost gated ----
    Scalar cost_final = cost_best;
    bool accepted_mom = false;
    std::vector<Scalar> h_dbest(n);
    CUDA_CHECK(cudaMemcpy(h_dbest.data(), d_best, n*sizeof(Scalar), cudaMemcpyDeviceToHost));
    Scalar dbest_norm = 0.0; for (auto v : h_dbest) dbest_norm += v*v; dbest_norm = std::sqrt(dbest_norm);

    if (!hist.empty()) {
      int m = std::min((int)hist.size(), mom_window);
      int nb = m + 1;
      CUDA_CHECK(cudaMemcpy(G_basis, d_best, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      for (int i = 0; i < m; ++i)
        CUDA_CHECK(cudaMemcpy(G_basis + (size_t)(i+1)*n, hist[i].data(), n*sizeof(Scalar), cudaMemcpyHostToDevice));

      std::vector<std::vector<Scalar>> Stilde(nb, std::vector<Scalar>(nb, 0.0));
      std::vector<Scalar> btilde(nb, 0.0);
      for (int col = 0; col < nb; ++col) {
        CUDA_CHECK(cudaMemset(Hv_col, 0, n*sizeof(Scalar)));
        KernelHgnMatVecCross<<<GridSize(p.nobs),256>>>(obs_Hcp, p.cam_idx, p.pt_idx, p.nobs,
                                                        G_basis + (size_t)col*n, G_basis + (size_t)col*n + n_c,
                                                        Hv_col, Hv_col + n_c);
        KernelHgnMatVecDiagCam<<<GridSize(ncam),256>>>(Hcc, ncam, G_basis + (size_t)col*n, Hv_col);
        KernelHgnMatVecDiagPt<<<GridSize(npt),256>>>(Hpp, npt, G_basis + (size_t)col*n + n_c, Hv_col + n_c);
        for (int row = 0; row < nb; ++row) {
          Scalar dot; CUBLAS_CHECK(cublasDdot(blas_sub, n, G_basis + (size_t)row*n, 1, Hv_col, 1, &dot));
          Stilde[row][col] = dot;
        }
        // grad_c/grad_p are two separate buffers (not contiguous with each other in general),
        // so b~=G^T[grad_c;grad_p] is built as two partial cublasDdot calls per column instead
        // of the single-buffer trick used where a genuine contiguous bfull already exists (P3).
        Scalar bc_dot, bp_dot;
        CUBLAS_CHECK(cublasDdot(blas_sub, n_c, G_basis + (size_t)col*n, 1, grad_c, 1, &bc_dot));
        CUBLAS_CHECK(cublasDdot(blas_sub, n_p, G_basis + (size_t)col*n + n_c, 1, grad_p, 1, &bp_dot));
        btilde[col] = bc_dot + bp_dot;
      }
      for (int i = 0; i < nb; ++i) Stilde[i][i] += reg * std::max(Stilde[i][i], (Scalar)1.0);
      std::vector<Scalar> alpha = SolveSmallSPD(Stilde, btilde);
      for (auto& v : alpha) v = -v;
      std::vector<Scalar> h_alpha_pad(alpha);
      CUDA_CHECK(cudaMemcpy(Hv_col, h_alpha_pad.data(), nb*sizeof(Scalar), cudaMemcpyHostToDevice));
      const Scalar one_ = 1.0, zero_ = 0.0;
      CUBLAS_CHECK(cublasDgemv(blas_sub, CUBLAS_OP_N, n, nb, &one_, G_basis, n, Hv_col, 1, &zero_, d_mom, 1));

      std::vector<Scalar> h_dmom(n);
      CUDA_CHECK(cudaMemcpy(h_dmom.data(), d_mom, n*sizeof(Scalar), cudaMemcpyDeviceToHost));
      Scalar dmom_norm = 0.0; for (auto v : h_dmom) dmom_norm += v*v; dmom_norm = std::sqrt(dmom_norm);
      Scalar trust_cap = trust_radius * std::max(dbest_norm, (Scalar)1e-300);
      if (dmom_norm > trust_cap) {
        Scalar scale = trust_cap / dmom_norm;
        for (auto& v : h_dmom) v *= scale;
        CUDA_CHECK(cudaMemcpy(d_mom, h_dmom.data(), n*sizeof(Scalar), cudaMemcpyHostToDevice));
      }
      Retract(p, s, d_mom, s_new);
      Scalar cost_mom = ComputeCost(p, s_new);
      if (cost_mom < cost_final) { cost_final = cost_mom; accepted_mom = true; }
    }

    Scalar step_norm;
    std::vector<Scalar> applied;
    if (accepted_mom) {
      std::swap(s.R, s_new.R); std::swap(s.t, s_new.t); std::swap(s.X, s_new.X);
      applied.resize(n);
      CUDA_CHECK(cudaMemcpy(applied.data(), d_mom, n*sizeof(Scalar), cudaMemcpyDeviceToHost));
      ++n_mom_accepted;
    } else {
      Retract(p, s, d_best, s_new);
      std::swap(s.R, s_new.R); std::swap(s.t, s_new.t); std::swap(s.X, s_new.X);
      applied = h_dbest;
    }
    cost = cost_final;
    step_norm = 0.0; for (auto v : applied) step_norm += v*v; step_norm = std::sqrt(step_norm);
    hist.push_front(applied);
    if ((int)hist.size() > mom_window) hist.pop_back();

    log.iters.push_back(k+1); log.costs.push_back(cost);
    if (verbose) std::printf("  OCA-Joint-CamPt-LD-SubMom it%4d cost=%.6e |d|=%.3e lam_cam=%.3e lam_pt=%.3e depth_best=%d n_esc=%d |grad|/|grad0|=%.3e %s\n",
                              k+1, cost, step_norm, lam_cam_best, lam_pt_best, depth_best, n_esc, grad_norm/grad_norm0, accepted_mom ? "[MOM]" : "");
    if (step_norm < tol && grad_norm < 1e-8 * grad_norm0) break;
  }
  if (verbose) std::printf("  OCA-Joint-CamPt-LD-SubMom: momentum accepted %d/%d iterations\n", n_mom_accepted, (int)log.iters.size()-1);

  cusolverDnDestroy(handle);
  cublasDestroy(blas_sub);
  cudaFree(G_basis); cudaFree(Hv_col); cudaFree(d_mom);
  cudaFree(Hcc); cudaFree(Hpp); cudaFree(obs_Hcp); cudaFree(grad_c); cudaFree(grad_p);
  cudaFree(App_inv); cudaFree(S); cudaFree(bc_corr); cudaFree(bc_prime); cudaFree(xc); cudaFree(xp);
  cudaFree(gc_prev); cudaFree(gp_prev); cudaFree(bp_j); cudaFree(bc_j); cudaFree(d); cudaFree(d_best); cudaFree(d_cand); cudaFree(ok_flags);
  cudaFree(s_new.R); cudaFree(s_new.t); cudaFree(s_new.X);
  return log;
}

// ============================================================== ROUND 2 (BA_Round2_Research_Directions.pdf)
// One solver carrying every round-2 recommendation as an independently-toggleable flag, so
// each can be ablated against the round-1 champion rather than shipped as a bundle (round 1
// established that individually-validated techniques do NOT compose: P7+subspace_min was
// ~10% worse than either alone).
//
//   use_relpt   P.NEW.4  per-point relative lam_pt (removes lam_pt from the grid -> 1-D search)
//   use_jacobi  P.NEW.5  Jacobi camera damping D=diag(H_cc) instead of lam*I
//   use_audit   P.NEW.3  sigma-spread AUDIT + RELATIVE lambda floor (the P7-trap fix)
//   use_aitken  P.NEW.6  Aitken/geometric-tail extrapolation of the OCA depth sequence
//   use_alpha   P.NEW.9  two-parameter (alpha_cam, alpha_pt) step-length search
//   oracle      P.NEW.1  diagnostic: run the full grid every iteration WITHOUT accepting it,
//                        logging per-iteration regret, to separate "early termination" from
//                        "genuinely worse basin" as the cause of the venice-52 P7 trap
//
// Scheduler is P7's cheap-first (one trial at the tracked lambda, full grid on failure),
// since round 1 measured that as a 2.3x wall-clock win on ladybug-598; AUDIT is what makes
// it safe on datasets that are PD from iteration 0.
RunLog SolveOCARound2(const DeviceProblem& p, DeviceState& s, Scalar lam0, Scalar tol,
                       int max_iter, bool verbose, int n_cam_candidates = 3, int n_pt_candidates = 3,
                       Scalar decade_span = 1.0, int max_escalations = 25,
                       std::vector<int> depths = {0,1,2,4,8},
                       bool use_relpt = false, Scalar tau_pt = 1e-7, bool marquardt_pt = false,
                       bool use_jacobi = false, bool use_audit = false, bool use_aitken = false,
                       bool use_alpha = false, bool oracle = false, bool cheap_first = true,
                       Scalar eps_rel = 1e-9, bool fp32_refine = false, int n_ir = 2,
                       Scalar ir_tol = 1e-10, bool adaptive_pt = false, Scalar kappa_pt = 1e4,
                       Scalar theta = 1.0, bool use_edge_csr = false, bool span_min = false,
                       bool cheb_filter = false, Scalar cheb_tplus = 0.99,
                       std::vector<int> cheb_k_menu = {4, 6},
                       std::vector<int> hybrid_r_menu = {0, 0},
                       bool cheir_gate = false, bool fp32_jac = false) {
  int ncam = p.ncam, npt = p.npt, n_c = 6*ncam, n_p = 3*npt, n = n_c + n_p;
  Scalar *Hcc, *Hpp, *obs_Hcp, *grad_c, *grad_p, *App_inv, *S;
  float* obs_Hcp32 = nullptr;   // ROUND 9: fp32 Jacobian-block storage (--fp32_jac)
  Scalar *bc_corr, *bc_prime, *xc, *xp, *gc_prev, *gp_prev, *bp_j, *bc_j, *d, *d_best, *d_cand;
  Scalar *g0_buf, *ga_buf, *gb_buf, *glast_buf, *tmp1, *tmp2, *d_alpha, *diagHcc, *jd_sum;
  int* ok_flags;
  CUDA_CHECK(cudaMalloc(&Hcc, 36*(size_t)ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&Hpp, 9*(size_t)npt*sizeof(Scalar)));
  if (fp32_jac) CUDA_CHECK(cudaMalloc(&obs_Hcp32, 18*(size_t)p.nobs*sizeof(float)));
  else          CUDA_CHECK(cudaMalloc(&obs_Hcp,   18*(size_t)p.nobs*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&grad_c, 6*(size_t)ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&grad_p, 3*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&App_inv, 9*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&S, (size_t)n_c*n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bc_corr, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bc_prime, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&xc, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&xp, n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&gc_prev, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&gp_prev, n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bp_j, n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bc_j, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&d, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&d_best, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&d_cand, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&g0_buf, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&ga_buf, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&gb_buf, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&glast_buf, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&tmp1, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&tmp2, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&d_alpha, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&diagHcc, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&jd_sum, sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&ok_flags, npt*sizeof(int)));
  Scalar* pt_damp = nullptr;
  if (adaptive_pt) CUDA_CHECK(cudaMalloc(&pt_damp, npt*sizeof(Scalar)));
  // ---- lambda-invariant Schur correction (round-4, Q1) --------------------------------
  // V = H_pp + D_p depends only on H_pp and tau/kappa -- NOT on lambda_cam. Hence
  // K := -H_cp V^{-1} H_cp^T is identical for every lambda_cam candidate, and
  //      S(lambda_cam) = H_cc + lambda_cam I + K
  // so the O(sum_p D_p^2) accumulation (39.5% of runtime) can be hoisted OUT of the
  // candidate loop and done ONCE per outer iteration. Only valid when lambda_pt is not
  // itself being searched, i.e. exactly the champion configuration.
  bool hoist_K = (use_relpt || adaptive_pt);
  Scalar* K_inv = nullptr;
  if (hoist_K) CUDA_CHECK(cudaMalloc(&K_inv, (size_t)n_c*n_c*sizeof(Scalar)));
  bool K_ready = false;
  DeviceState s_new; AllocState(s_new, ncam, npt);

  cusolverDnHandle_t handle; cusolverDnCreate(&handle);
  CholeskyWorkspace ws; ws.Init(handle, n_c);
  cublasHandle_t blas; CUBLAS_CHECK(cublasCreate(&blas));

  // ---- P1.2 (round 3): FP32 POTRF + FP64 iterative refinement ----
  // D2 microbench on this GPU (RTX 2000 Ada, fp64 at 1/64 rate) measured DPOTRF/SPOTRF at
  // 15.8x (n=3588) and 24.6x (n=10032) -- far above the round-3 doc's 2x go/no-go gate and its
  // assumed 4x. With factorization at 87.5% of runtime, Amdahl predicts ~5.5-6.2x rather than
  // the doc's 2.9x. S is kept in FP64 (untouched) so the refinement residual r = b - S x is
  // computed exactly; only the factorization and the inner triangular solves run in FP32.
  CholeskyWorkspaceF32 wsf;
  float *S32 = nullptr, *v32 = nullptr;
  Scalar *x_acc = nullptr, *r_vec = nullptr, *dlt = nullptr, *xc_save = nullptr;
  if (fp32_refine) {
    wsf.Init(handle, n_c);
    CUDA_CHECK(cudaMalloc(&S32, (size_t)n_c*n_c*sizeof(float)));
    CUDA_CHECK(cudaMalloc(&v32, n_c*sizeof(float)));
    CUDA_CHECK(cudaMalloc(&x_acc, n_c*sizeof(Scalar)));
    CUDA_CHECK(cudaMalloc(&r_vec, n_c*sizeof(Scalar)));
    CUDA_CHECK(cudaMalloc(&dlt, n_c*sizeof(Scalar)));
    CUDA_CHECK(cudaMalloc(&xc_save, n_c*sizeof(Scalar)));
  }
  long n_ir_steps = 0, n_solves = 0, n_ir_fallback = 0, n_fp32_bailout = 0;


  // Solve S x = rhs (rhs overwritten with x). FP32 factor + FP64 residual refinement:
  //   x <- 0 ; r <- b ; repeat: delta = U^-1 L^-1 r (fp32) ; x += delta ; r = b - S x (fp64)
  // Falls back to reporting a failure if the fp64 relative residual never drops below ir_tol,
  // so a badly-conditioned S cannot silently return a wrong step (the true-cost gate would not
  // reliably catch that -- same class as the cheirality blind spot).
  auto SolveRefined = [&](const Scalar* S_fp64, Scalar* rhs) -> bool {
    ++n_solves;
    CUDA_CHECK(cudaMemcpy(r_vec, rhs, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));   // r = b
    CUDA_CHECK(cudaMemset(x_acc, 0, n_c*sizeof(Scalar)));
    Scalar bnorm; CUBLAS_CHECK(cublasDnrm2(blas, n_c, rhs, 1, &bnorm));
    if (!(bnorm > 0.0)) { CUDA_CHECK(cudaMemset(rhs, 0, n_c*sizeof(Scalar))); return true; }
    const Scalar one = 1.0, neg_one = -1.0, zero = 0.0;
    bool converged = false;
    for (int it = 0; it < n_ir; ++it) {
      KernelCastD2F<<<GridSize(n_c),256>>>(r_vec, v32, n_c);
      CholeskySolveVecF32(wsf, S32, v32);
      KernelCastF2D<<<GridSize(n_c),256>>>(v32, dlt, n_c);
      CUBLAS_CHECK(cublasDaxpy(blas, n_c, &one, dlt, 1, x_acc, 1));                     // x += delta
      ++n_ir_steps;
      CUDA_CHECK(cudaMemcpy(r_vec, rhs, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      CUBLAS_CHECK(cublasDgemv(blas, CUBLAS_OP_N, n_c, n_c, &neg_one, S_fp64, n_c,
                               x_acc, 1, &one, r_vec, 1));                              // r = b - S x
      Scalar rn; CUBLAS_CHECK(cublasDnrm2(blas, n_c, r_vec, 1, &rn));
      if (rn <= ir_tol * bnorm) { converged = true; break; }
    }
    if (!converged) ++n_ir_fallback;
    CUDA_CHECK(cudaMemcpy(rhs, x_acc, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
    (void)zero;
    return converged;
  };

  Scalar cost = ComputeCost(p, s);
  RunLog log; log.iters.push_back(0); log.costs.push_back(cost);
  Scalar lam_cam_center = lam0, lam_pt_center = lam0;
  Scalar grad_norm0 = -1.0;
  int max_depth = 0; for (int dd : depths) max_depth = std::max(max_depth, dd);
  // ---- Round-4 diagnostics (env-gated, zero cost when unset) ----------------------------
  // Exploits the identity that follows from A g_j = b + D g_{j-1} with A = H + D:
  //        H g_j = b - D (g_j - g_{j-1})
  // so the linear residual, the predicted decrease, and the Gram matrix G_jk = g_j^T H g_k are
  // ALL available from vectors the recursion already produced -- no extra solves, no H matvec.
  //   OCA_DIAG=<first outer iteration to log>   OCA_DIAG_FILE=<csv path>
  const char* diag_env = std::getenv("OCA_DIAG");
  int diag_from = diag_env ? std::atoi(diag_env) : -1;
  bool diag = (diag_from >= 0);
  std::FILE* dfp = nullptr;
  // ---- one-shot S dump for the S-entry-dynamic-range measurement (math_b, round 7) -------
  // OCA_DUMP_S=<0-indexed outer iteration>  OCA_DUMP_S_FILE=<path>. Dumps the FIRST S formed
  // during that outer iteration (the cheap-first incumbent-lambda candidate, which under the
  // champion config runs exactly once per iteration before any escalation) to a raw binary file:
  // int32 n_c, then n_c*n_c float64 in the same row-major-treated-as-col-major layout S already
  // uses. Dumped BEFORE Cholesky factorization overwrites S in place. One dump per process, not
  // gated behind fp32_refine -- independent of which precision path is under test.
  const char* dump_s_env = std::getenv("OCA_DUMP_S");
  int dump_s_iter = dump_s_env ? std::atoi(dump_s_env) : -1;
  const char* dump_s_file_env = std::getenv("OCA_DUMP_S_FILE");
  std::string dump_s_file = dump_s_file_env ? dump_s_file_env : "/tmp/oca_S_dump.bin";
  bool dump_s_done = false;
  Scalar *G_hist = nullptr, *Dv = nullptr, *diff = nullptr, *v_span = nullptr;
  // P7 (round 4): constrained span minimization reuses this same basis-capture buffer, so the
  // allocation is needed whenever EITHER diagnostics or span_min is active.
  bool need_basis = diag || span_min;
  if (diag) {
    const char* f = std::getenv("OCA_DIAG_FILE");
    dfp = std::fopen(f ? f : "/tmp/oca_diag.csv", "w");
    std::fprintf(dfp, "iter,lam_cam,j,gD_norm,g2_norm,dF_pred,dF_actual,rho_j,gram_row\n");
  }
  if (need_basis) {
    CUDA_CHECK(cudaMalloc(&G_hist, (size_t)n*(max_depth+1)*sizeof(Scalar)));
    CUDA_CHECK(cudaMalloc(&Dv, n*sizeof(Scalar)));
    CUDA_CHECK(cudaMalloc(&diff, n*sizeof(Scalar)));
  }
  // span_min's own Gram/beta computation is batched via GEMM/GEMV (see below) instead of the
  // O(m^2) individual cublasDdot calls the diagnostics block above uses -- each cublasDdot with
  // the default host pointer mode blocks on a device sync, and m^2 of those (~90 for the default
  // depth menu) measurably dominated wall-clock in an earlier version of this code.
  Scalar *ADiffs = nullptr, *b_full = nullptr, *beta_dev = nullptr, *Gtmp_dev = nullptr;
  if (span_min) {
    CUDA_CHECK(cudaMalloc(&v_span, n*sizeof(Scalar)));
    CUDA_CHECK(cudaMalloc(&ADiffs, (size_t)n*(max_depth+1)*sizeof(Scalar)));
    CUDA_CHECK(cudaMalloc(&b_full, n*sizeof(Scalar)));
    CUDA_CHECK(cudaMalloc(&beta_dev, (max_depth+1)*sizeof(Scalar)));
    CUDA_CHECK(cudaMalloc(&Gtmp_dev, (size_t)(max_depth+1)*(max_depth+1)*sizeof(Scalar)));
  }
  long n_span_win = 0;
  int diag_k = 0;                      // current outer iteration, for logging

  // ---- A1: HYBRID spectral filter (MM-derived, off by default) --------------------------
  // p(t) = t^r * [ T_k(z(t))/T_k(z(1)) ]^2 ,  z(t) = 2t/tplus - 1     (r=0 => pure sqCheb)
  // Q(t) = (1-p(t))/(1-t)   -- exact degree-(r+2k-1) polynomial since p(1)=1
  // step = Q(M) g0 ,  M = A^-1 D                -- (r+2k-1) applications of M
  // p(t) in [0,1] on (0,1) for ANY tplus in (0,1), ANY integer r>=0, ANY k>=1 (product of a
  // nonnegative power and a square, both <=1 there) => gain=1-p(t) in [0,1] -- the majorization
  // admissibility condition from CONTEXT S5. Verified both symbolically and numerically (host
  // script r6/cuda/hybrid_validate.py, all errors <=1e-12 against dense reference, including
  // an eigenvalue exactly at the gauge value t=1). Coefficients depend only on (r,k,tplus) --
  // all fixed CLI constants -- so computed ONCE on the host at solver start.
  struct ChebPoly { int r, k; Scalar tplus; std::vector<Scalar> Q_coeffs; };
  std::vector<ChebPoly> cheb_polys;
  auto ChebT_scalar = [](int kk, Scalar x) -> Scalar {
    if (kk == 0) return (Scalar)1.0;
    Scalar T0 = 1.0, T1 = x;
    for (int i = 2; i <= kk; ++i) { Scalar T2 = 2*x*T1 - T0; T0 = T1; T1 = T2; }
    return T1;
  };
  auto p_scalar = [&](Scalar t, int rr, int kk, Scalar tplus) -> Scalar {
    Scalar z1 = 2.0/tplus - 1.0, Tk_z1 = ChebT_scalar(kk, z1);
    Scalar z = 2.0*t/tplus - 1.0, q = ChebT_scalar(kk, z) / Tk_z1;
    return std::pow(t, rr) * q * q;
  };
  if (cheb_filter) {
    for (size_t mi = 0; mi < cheb_k_menu.size(); ++mi) {
      int kk = cheb_k_menu[mi];
      int rr = (mi < hybrid_r_menu.size()) ? hybrid_r_menu[mi] : (hybrid_r_menu.empty() ? 0 : hybrid_r_menu.back());
      if (kk < 1 || rr < 0) continue;
      ChebPoly cp; cp.r = rr; cp.k = kk; cp.tplus = cheb_tplus;
      int N = rr + 2*kk;   // Q has degree N-1; N Chebyshev-Gauss nodes interpolate it exactly
      std::vector<Scalar> zi(N), ti(N), Qi(N);
      for (int i = 0; i < N; ++i) {
        zi[i] = std::cos((i + 0.5) * M_PI / N);
        ti[i] = cheb_tplus * (zi[i] + 1.0) / 2.0;
        Scalar pi_ = p_scalar(ti[i], rr, kk, cheb_tplus);
        Qi[i] = (1.0 - pi_) / (1.0 - ti[i]);
      }
      cp.Q_coeffs.assign(N, 0.0);
      for (int j = 0; j < N; ++j) {
        Scalar w = (j == 0) ? (1.0/N) : (2.0/N);
        Scalar acc = 0.0;
        for (int i = 0; i < N; ++i) acc += Qi[i] * ChebT_scalar(j, zi[i]);
        cp.Q_coeffs[j] = w * acc;
      }
      // Report the theoretical gain range over t in (0, tplus] -- the range the filter can
      // realize GIVEN (r,k,tplus); not the empirical spectrum of M (no eigendecomposition here).
      Scalar gmin = 1.0, gmax = 0.0;
      for (int i = 0; i <= 2000; ++i) {
        Scalar t = 1e-9 + (cheb_tplus - 1e-9) * i / 2000.0;
        Scalar g = 1.0 - p_scalar(t, rr, kk, cheb_tplus);
        gmin = std::min(gmin, g); gmax = std::max(gmax, g);
      }
      if (verbose) std::printf("  [A1] HYB(r=%d,k=%d) tplus=%.4f  theoretical gain range on (0,tplus]: [%.6f, %.6f]"
                                "  (%d M-applications)\n", rr, kk, (double)cheb_tplus, (double)gmin, (double)gmax, N-1);
      if (gmin < -1e-9 || gmax > 1.0 + 1e-9) {
        std::fprintf(stderr, "  [A1] ADMISSIBILITY VIOLATION for HYB(r=%d,k=%d) tplus=%.4f: gain range [%.9f,%.9f] "
                              "escapes [0,1] -- STOPPING, this falsifies the derivation.\n",
                              rr, kk, (double)cheb_tplus, (double)gmin, (double)gmax);
        std::exit(3);
      }
      cheb_polys.push_back(cp);
    }
  }
  Scalar *cheb_Dv = nullptr, *cheb_Mv = nullptr, *cheb_b1 = nullptr, *cheb_b2 = nullptr,
         *cheb_b0 = nullptr, *cheb_step = nullptr;
  if (cheb_filter && !cheb_polys.empty()) {
    CUDA_CHECK(cudaMalloc(&cheb_Dv, n*sizeof(Scalar)));
    CUDA_CHECK(cudaMalloc(&cheb_Mv, n*sizeof(Scalar)));
    CUDA_CHECK(cudaMalloc(&cheb_b1, n*sizeof(Scalar)));
    CUDA_CHECK(cudaMalloc(&cheb_b2, n*sizeof(Scalar)));
    CUDA_CHECK(cudaMalloc(&cheb_b0, n*sizeof(Scalar)));
    CUDA_CHECK(cudaMalloc(&cheb_step, n*sizeof(Scalar)));
  }
  long n_cheb_win = 0;
  std::vector<long> n_cheb_win_by_k(cheb_polys.size(), 0);
  // Applies the SAME block-structured D used by the recursion:  out = D v
  auto ApplyD = [&](const Scalar* v, Scalar* out, Scalar lam_cam) {
    CUDA_CHECK(cudaMemset(out, 0, n*sizeof(Scalar)));
    if (adaptive_pt)    KernelAxpyAdaptiveDamp<<<GridSize(npt),256>>>(out + n_c, v + n_c, pt_damp, npt);
    else if (use_relpt) KernelAxpyPerPointDamp<<<GridSize(npt),256>>>(out + n_c, v + n_c, Hpp, tau_pt, marquardt_pt, npt);
    else                KernelAxpy<<<GridSize(n_p),256>>>(out + n_c, v + n_c, lam_pt_center, n_p);
    if (use_jacobi) KernelAxpyPerCamDamp<<<GridSize(ncam),256>>>(out, v, Hcc, lam_cam, ncam);
    else            KernelAxpy<<<GridSize(n_c),256>>>(out, v, lam_cam, n_c);
  };
  // AUDIT state
  int K_audit = 4, iters_since_audit = 0, floor_streak = 0;
  Scalar rho_prev = 1.0, lam_floor = lam0 * 1e-8;
  int n_cheap = 0, n_full = 0, n_audit_fired = 0, n_aitken_win = 0, n_alpha_win = 0;
  Scalar sigma_last = 1.0;
  // ---- cheirality gate (off by default): lexicographic candidate selection -----------------
  // The true-cost gate is BLIND to antipodal flips by construction (CONTEXT S8.1: (x,y) is a
  // ratio, invariant to negating P). Cheirality is already computed by a cheap kernel; this
  // reuses it to make candidate selection prefer candidates that don't INCREASE the violation
  // count relative to the current (incumbent) state, breaking ties by cost, with a fallback to
  // plain min-cost if no candidate qualifies (never stalls the solver).
  int cheir_incumbent = 0;
  int* cheir_gate_buf = nullptr;
  Scalar* d_out_elig = nullptr;
  if (cheir_gate) { CUDA_CHECK(cudaMalloc(&cheir_gate_buf, sizeof(int))); CUDA_CHECK(cudaMalloc(&d_out_elig, n*sizeof(Scalar))); }
  auto CountCheirFast = [&](const DeviceState& st) -> int {
    CUDA_CHECK(cudaMemset(cheir_gate_buf, 0, sizeof(int)));
    KernelCountCheirality<<<GridSize(p.nobs),256>>>(p.cam_idx, p.pt_idx, st.R, st.t, st.X, p.nobs, cheir_gate_buf);
    int cnt; CUDA_CHECK(cudaMemcpy(&cnt, cheir_gate_buf, sizeof(int), cudaMemcpyDeviceToHost));
    return cnt;
  };
  // profiling (P.NEW.2) -- env-gated, zero cost when unset
  bool prof = (std::getenv("OCA_PROFILE") != nullptr);
  double t_assembly = 0, t_factor = 0, t_recursion = 0, t_eval = 0, t_potrf = 0, t_other = 0;
  double t_gradnorm = 0, t_alpha_b = 0, t_rho_b = 0, t_accept = 0;
  auto now = [](){ return std::chrono::steady_clock::now(); };

  // Runs one (lam_cam, lam_pt) candidate: ONE factorization, walk the recursion to
  // max_depth, true-cost-checkpoint at every depth in D. Returns best cost, writes the
  // corresponding step to d_out. Also reports sigma-spread (AUDIT trigger E) and, when
  // enabled, tries the Aitken-extrapolated "depth-infinity" candidate for free.
  // Round-4 Q1: dispatch Schur formation to either the original atomic-scatter kernel or the
  // atomic-free edge-CSR pair (diagonal atomic-but-cheap O(N_obs), off-diagonal via persistent
  // edges). `out` must already be zeroed by the caller; both paths only ADD into it.
  auto FormS = [&](Scalar* out) {
    if (use_edge_csr) {
      if (fp32_jac) {
        KernelFormSDiag<float><<<GridSize(p.nobs),256>>>(obs_Hcp32, p.cam_idx, p.pt_idx, App_inv, p.nobs, n_c, out);
      } else {
        KernelFormSDiag<Scalar><<<GridSize(p.nobs),256>>>(obs_Hcp, p.cam_idx, p.pt_idx, App_inv, p.nobs, n_c, out);
      }
      if (p.n_edges > 0)
        if (fp32_jac) {
          KernelFormSEdges<float><<<p.n_edges,36>>>(obs_Hcp32, p.pt_idx, p.edge_ci, p.edge_cj, p.edge_offsets,
                                              p.edge_obs_d, p.edge_obs_e, App_inv, p.n_edges, n_c, out);
        } else {
          KernelFormSEdges<Scalar><<<p.n_edges,36>>>(obs_Hcp, p.pt_idx, p.edge_ci, p.edge_cj, p.edge_offsets,
                                              p.edge_obs_d, p.edge_obs_e, App_inv, p.n_edges, n_c, out);
        }
    } else {
      if (fp32_jac) {
        KernelFormSSparse<float><<<GridSize(npt),256>>>(obs_Hcp32, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                                  App_inv, npt, n_c, out);
      } else {
        KernelFormSSparse<Scalar><<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                                  App_inv, npt, n_c, out);
      }
    }
  };

  auto try_lambda_pair = [&](Scalar lam_cam, Scalar lam_pt, Scalar* d_out, int& depth_out,
                              Scalar* sigma_out) -> Scalar {
    std::chrono::steady_clock::time_point t0;
    if (prof) { cudaDeviceSynchronize(); t0 = now(); }
    if (!hoist_K || !K_ready) {
      if (adaptive_pt)    KernelInvertAppBlocksAdaptive<<<GridSize(npt),256>>>(Hpp, kappa_pt, App_inv, ok_flags, pt_damp, npt);
      else if (use_relpt) KernelInvertAppBlocksRel<<<GridSize(npt),256>>>(Hpp, tau_pt, marquardt_pt, App_inv, ok_flags, npt);
      else                KernelInvertAppBlocks<<<GridSize(npt),256>>>(Hpp, lam_pt, App_inv, ok_flags, npt);
      { std::vector<int> h_ok(npt);
        CUDA_CHECK(cudaMemcpy(h_ok.data(), ok_flags, npt*sizeof(int), cudaMemcpyDeviceToHost));
        for (int v : h_ok) if (!v) return std::numeric_limits<Scalar>::infinity();
      }
      if (hoist_K) {   // accumulate the lambda-invariant part once
        CUDA_CHECK(cudaMemset(K_inv, 0, (size_t)n_c*n_c*sizeof(Scalar)));
        FormS(K_inv);
        K_ready = true;
      }
    }
    CUDA_CHECK(cudaMemset(S, 0, (size_t)n_c*n_c*sizeof(Scalar)));
    if (use_jacobi) KernelBuildAccFullJacobi<<<GridSize(ncam),256>>>(Hcc, lam_cam, S, ncam, n_c);
    else            KernelBuildAccFull<<<GridSize(ncam),256>>>(Hcc, lam_cam, S, ncam, n_c);
    if (hoist_K) { const Scalar one_k = 1.0;                       // S = H_cc + lam I + K
      CUBLAS_CHECK(cublasDaxpy(blas, n_c*n_c, &one_k, K_inv, 1, S, 1)); }
    else FormS(S);
    if (dump_s_iter >= 0 && diag_k == dump_s_iter && !dump_s_done) {
      std::vector<Scalar> S_host((size_t)n_c*n_c);
      CUDA_CHECK(cudaMemcpy(S_host.data(), S, (size_t)n_c*n_c*sizeof(Scalar), cudaMemcpyDeviceToHost));
      std::FILE* sfp = std::fopen(dump_s_file.c_str(), "wb");
      if (sfp) {
        int nc32 = n_c;
        std::fwrite(&nc32, sizeof(int), 1, sfp);
        std::fwrite(S_host.data(), sizeof(Scalar), S_host.size(), sfp);
        std::fclose(sfp);
        if (verbose) std::printf("  [OCA_DUMP_S] wrote S (n_c=%d, lam_cam=%.6e) to %s at outer iter %d\n",
                                  n_c, (double)lam_cam, dump_s_file.c_str(), diag_k);
      }
      dump_s_done = true;
    }
    std::chrono::steady_clock::time_point tp0;
    if (prof) { cudaDeviceSynchronize(); tp0 = now(); }
    bool fp32_active = fp32_refine;
    if (fp32_refine) {
      // S (fp64) is left INTACT -- only the fp32 copy is destroyed by the factorization, so the
      // refinement residual can be formed against the exact operator.
      KernelCastD2F<<<GridSize(n_c*n_c),256>>>(S, S32, n_c*n_c);
      if (!CholeskyFactorF32(wsf, S32)) return std::numeric_limits<Scalar>::infinity();
    } else {
      if (!CholeskyFactor(ws, S)) return std::numeric_limits<Scalar>::infinity();
    }
    if (prof) { cudaDeviceSynchronize(); t_potrf += std::chrono::duration<double>(now()-tp0).count(); }
    // RECURSION-CONSISTENCY GUARD (round-3 doc section 3.1): the operator A(lambda) must be
    // IDENTICAL at every depth of g_j = A^-1(b + R g_{j-1}); mixing an FP32-solved g_0..g_{j-1}
    // with an FP64-solved tail changes the fixed point mid-recursion. So the FP32-vs-FP64
    // decision is made ONCE per candidate here, with a single throwaway probe solve, and never
    // revisited inside the depth loop. (Deciding it lazily inside the loop was tried first and
    // produced erratic, non-monotonic costs -- exactly the documented trap.)
    if (fp32_active) {
      CUDA_CHECK(cudaMemcpy(xc_save, grad_c, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      if (!SolveRefined(S, xc_save)) {
        ++n_fp32_bailout;
        fp32_active = false;
        if (!CholeskyFactor(ws, S)) return std::numeric_limits<Scalar>::infinity();
      }
    }
    if (prof) { cudaDeviceSynchronize(); t_factor += std::chrono::duration<double>(now()-t0).count(); }

    Scalar best_cost = std::numeric_limits<Scalar>::infinity();
    depth_out = depths.empty() ? 0 : depths[0];
    Scalar sigma = 0.0, g0_norm = 0.0;
    Scalar best_cost_elig = std::numeric_limits<Scalar>::infinity();
    int depth_out_elig = 0;
    // Considers one candidate for both the plain min-cost incumbent (existing behaviour,
    // always updated) and, when cheir_gate is on, the cheirality-eligible incumbent (candidates
    // whose violation count does not exceed the CURRENT state's). cand_state must hold the
    // retracted state for THIS candidate at call time.
    auto ConsiderCandidate = [&](Scalar cand_cost, Scalar* cand_buf, int cand_label, const DeviceState& cand_state) -> bool {
      bool updated_any = false;
      if (cand_cost < best_cost) {
        best_cost = cand_cost; depth_out = cand_label;
        CUDA_CHECK(cudaMemcpy(d_out, cand_buf, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
        updated_any = true;
      }
      if (cheir_gate) {
        int cand_cheir = CountCheirFast(cand_state);
        if (cand_cheir <= cheir_incumbent && cand_cost < best_cost_elig) {
          best_cost_elig = cand_cost; depth_out_elig = cand_label;
          CUDA_CHECK(cudaMemcpy(d_out_elig, cand_buf, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
        }
      }
      return updated_any;
    };
    CUDA_CHECK(cudaMemset(gc_prev, 0, n_c*sizeof(Scalar)));
    for (int j = 0; j <= max_depth; ++j) {
      if (prof) { cudaDeviceSynchronize(); t0 = now(); }
      CUDA_CHECK(cudaMemcpy(bp_j, grad_p, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      CUDA_CHECK(cudaMemcpy(bc_j, grad_c, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      if (j > 0) {
        // The recursion's R must match the damping actually folded into A, per block:
        // scalar lam*I -> plain axpy; per-point/Jacobi diagonal D -> per-coordinate scaling.
        // P4 (round 4): theta-relaxed recursion  g_j = A^-1(b + theta*D*g_{j-1}).
        // rho(M_theta) = theta/(1+w_min) = theta < 1 unconditionally, so the recursion contracts
        // even though w_min = 0 from the 7-dof gauge null space. Fixed point moves to
        // g_inf = (H + (1-theta)D)^-1 b. Zero overhead: theta only scales an existing axpy.
        if (adaptive_pt)    KernelAxpyAdaptiveDampTheta<<<GridSize(npt),256>>>(bp_j, gp_prev, pt_damp, theta, npt);
        else if (use_relpt) KernelAxpyPerPointDamp<<<GridSize(npt),256>>>(bp_j, gp_prev, Hpp, theta*tau_pt, marquardt_pt, npt);
        else                KernelAxpy<<<GridSize(n_p),256>>>(bp_j, gp_prev, theta*lam_pt, n_p);
        if (use_jacobi) KernelAxpyPerCamDamp<<<GridSize(ncam),256>>>(bc_j, gc_prev, Hcc, theta*lam_cam, ncam);
        else            KernelAxpy<<<GridSize(n_c),256>>>(bc_j, gc_prev, theta*lam_cam, n_c);
      }
      CUDA_CHECK(cudaMemset(bc_corr, 0, n_c*sizeof(Scalar)));
      if (fp32_jac) {
        KernelRHSCorrectionSparse<float><<<GridSize(npt),256>>>(obs_Hcp32, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                                           App_inv, bp_j, npt, bc_corr);
      } else {
        KernelRHSCorrectionSparse<Scalar><<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                                           App_inv, bp_j, npt, bc_corr);
      }
      KernelSubtractVec<<<GridSize(n_c),256>>>(bc_prime, bc_j, bc_corr, n_c);
      CUDA_CHECK(cudaMemcpy(xc, bc_prime, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      if (fp32_active) SolveRefined(S, xc); else CholeskySolveVec(ws, S, xc);
      if (fp32_jac) {
        KernelBackSubstituteSparse<float><<<GridSize(npt),256>>>(obs_Hcp32, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                                            App_inv, bp_j, xc, npt, xp);
      } else {
        KernelBackSubstituteSparse<Scalar><<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                                            App_inv, bp_j, xc, npt, xp);
      }
      CUDA_CHECK(cudaMemcpy(gc_prev, xc, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      CUDA_CHECK(cudaMemcpy(gp_prev, xp, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      if (prof) { cudaDeviceSynchronize(); t_recursion += std::chrono::duration<double>(now()-t0).count(); }

      // raw (un-negated) g_j -- Aitken and sigma-spread both operate on the raw iterates
      CUDA_CHECK(cudaMemcpy(d_cand, gc_prev, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      CUDA_CHECK(cudaMemcpy(d_cand+n_c, gp_prev, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      if (j == 0) {
        CUDA_CHECK(cudaMemcpy(g0_buf, d_cand, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
        CUBLAS_CHECK(cublasDnrm2(blas, n, g0_buf, 1, &g0_norm));
      }
      if ((diag && diag_k >= diag_from) || span_min)
        CUDA_CHECK(cudaMemcpy(G_hist + (size_t)j*n, d_cand, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      if (use_aitken) {
        if (j == max_depth-2) CUDA_CHECK(cudaMemcpy(ga_buf, d_cand, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
        if (j == max_depth-1) CUDA_CHECK(cudaMemcpy(gb_buf, d_cand, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
        if (j == max_depth)   CUDA_CHECK(cudaMemcpy(glast_buf, d_cand, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      }
      if (std::find(depths.begin(), depths.end(), j) == depths.end()) continue;
      if (j > 0 && g0_norm > 0.0) {
        // sigma = max_j ||g_j - g_0|| / ||g_0||  (AUDIT trigger E: depth dimension collapsed)
        CUDA_CHECK(cudaMemcpy(tmp1, d_cand, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
        const Scalar neg1 = -1.0;
        CUBLAS_CHECK(cublasDaxpy(blas, n, &neg1, g0_buf, 1, tmp1, 1));
        Scalar dn; CUBLAS_CHECK(cublasDnrm2(blas, n, tmp1, 1, &dn));
        sigma = std::max(sigma, dn / g0_norm);
      }
      if (prof) { cudaDeviceSynchronize(); t0 = now(); }
      KernelNegateInPlace<<<GridSize(n),256>>>(d_cand, n);
      Retract(p, s, d_cand, s_new);
      Scalar c = ComputeCost(p, s_new);
      if (prof) { cudaDeviceSynchronize(); t_eval += std::chrono::duration<double>(now()-t0).count(); }
      ConsiderCandidate(c, d_cand, j, s_new);
    }

    // ---- A1: HYBRID filter candidates -- same true-cost gate as every other candidate ----
    // step = Q(M) g0, Q applied via general Clenshaw series with host-precomputed coefficients.
    // Uses g0_buf = A^-1 b, already computed at j==0 above regardless of whether 0 is in the
    // depth menu. Each application of M = A^-1 D reuses the EXACT Schur machinery the depth
    // recursion uses on this SAME factorization S -- consistency guard (CONTEXT S8.2) holds
    // because A is identical at every application within one candidate.
    if (!cheb_polys.empty()) {
      auto ApplyM = [&](const Scalar* v_in, Scalar* v_out) {
        ApplyD(v_in, cheb_Dv, lam_cam);
        CUDA_CHECK(cudaMemset(bc_corr, 0, n_c*sizeof(Scalar)));
        if (fp32_jac) {
          KernelRHSCorrectionSparse<float><<<GridSize(npt),256>>>(obs_Hcp32, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                                             App_inv, cheb_Dv + n_c, npt, bc_corr);
        } else {
          KernelRHSCorrectionSparse<Scalar><<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                                             App_inv, cheb_Dv + n_c, npt, bc_corr);
        }
        KernelSubtractVec<<<GridSize(n_c),256>>>(bc_prime, cheb_Dv, bc_corr, n_c);
        CUDA_CHECK(cudaMemcpy(v_out, bc_prime, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
        if (fp32_active) SolveRefined(S, v_out); else CholeskySolveVec(ws, S, v_out);
        if (fp32_jac) {
          KernelBackSubstituteSparse<float><<<GridSize(npt),256>>>(obs_Hcp32, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                                              App_inv, cheb_Dv + n_c, v_out, npt, v_out + n_c);
        } else {
          KernelBackSubstituteSparse<Scalar><<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                                              App_inv, cheb_Dv + n_c, v_out, npt, v_out + n_c);
        }
      };
      auto ZOp = [&](const Scalar* x, Scalar* out) {   // out = (2/tplus) M x - x = z(M) x ; out != x required
        ApplyM(x, cheb_Mv);
        CUDA_CHECK(cudaMemcpy(out, cheb_Mv, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
        Scalar scale = 2.0 / cheb_tplus; CUBLAS_CHECK(cublasDscal(blas, n, &scale, out, 1));
        const Scalar neg1 = -1.0; CUBLAS_CHECK(cublasDaxpy(blas, n, &neg1, x, 1, out, 1));
      };
      for (size_t ki = 0; ki < cheb_polys.size(); ++ki) {
        const ChebPoly& cp = cheb_polys[ki];
        int N = (int)cp.Q_coeffs.size();   // degree N-1, N-1 M-applications total
        // General Clenshaw series in M applied directly to g0:
        //   Q(M) g0 = c_0 g0 + z(M) b_1 - b_2 ,  b_j = c_j g0 + 2 z(M) b_{j+1} - b_{j+2}
        CUDA_CHECK(cudaMemset(cheb_b1, 0, n*sizeof(Scalar)));
        CUDA_CHECK(cudaMemset(cheb_b2, 0, n*sizeof(Scalar)));
        for (int j = N - 1; j >= 1; --j) {
          ZOp(cheb_b1, cheb_Mv);                                                       // Mv = z(M) b1 (reuse cheb_Mv as scratch)
          CUDA_CHECK(cudaMemcpy(cheb_b0, g0_buf, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
          Scalar cj = cp.Q_coeffs[j]; CUBLAS_CHECK(cublasDscal(blas, n, &cj, cheb_b0, 1));       // b0 = c_j g0
          Scalar two = 2.0; CUBLAS_CHECK(cublasDaxpy(blas, n, &two, cheb_Mv, 1, cheb_b0, 1));    // += 2 z(M) b1
          const Scalar neg1 = -1.0; CUBLAS_CHECK(cublasDaxpy(blas, n, &neg1, cheb_b2, 1, cheb_b0, 1)); // -= b2
          std::swap(cheb_b2, cheb_b1); std::swap(cheb_b1, cheb_b0);   // 3-buffer cyclic rotation
        }
        ZOp(cheb_b1, cheb_Mv);
        CUDA_CHECK(cudaMemcpy(cheb_step, g0_buf, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
        Scalar c0 = cp.Q_coeffs[0]; CUBLAS_CHECK(cublasDscal(blas, n, &c0, cheb_step, 1));
        { Scalar one = 1.0; CUBLAS_CHECK(cublasDaxpy(blas, n, &one, cheb_Mv, 1, cheb_step, 1)); }
        { const Scalar neg1 = -1.0; CUBLAS_CHECK(cublasDaxpy(blas, n, &neg1, cheb_b2, 1, cheb_step, 1)); }

        if (prof) { cudaDeviceSynchronize(); t0 = now(); }
        KernelNegateInPlace<<<GridSize(n),256>>>(cheb_step, n);
        Retract(p, s, cheb_step, s_new);
        Scalar cc = ComputeCost(p, s_new);
        if (prof) { cudaDeviceSynchronize(); t_eval += std::chrono::duration<double>(now()-t0).count(); }
        if (ConsiderCandidate(cc, cheb_step, -(1000 + cp.r*100 + cp.k), s_new)) {   // sentinel: A1 candidate HYB(r,k)
          ++n_cheb_win; ++n_cheb_win_by_k[ki];
        }
      }
    }

    if (diag && diag_k >= diag_from) {
      // b = [grad_c; grad_p] is not contiguous, so dot products against it are done in two parts.
      Scalar F0 = ComputeCost(p, s);
      for (int j = 0; j <= max_depth; ++j) {
        const Scalar* gj = G_hist + (size_t)j*n;
        // ||g_j||_2 and ||g_j||_D
        Scalar g2; CUBLAS_CHECK(cublasDnrm2(blas, n, gj, 1, &g2));
        ApplyD(gj, Dv, lam_cam);
        Scalar gDg; CUBLAS_CHECK(cublasDdot(blas, n, gj, 1, Dv, 1, &gDg));
        // diff = g_j - g_{j-1}   (g_{-1} := 0, consistent with g_0 = A^-1 b)
        CUDA_CHECK(cudaMemcpy(diff, gj, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
        if (j > 0) { const Scalar m1 = -1.0;
          CUBLAS_CHECK(cublasDaxpy(blas, n, &m1, G_hist + (size_t)(j-1)*n, 1, diff, 1)); }
        ApplyD(diff, Dv, lam_cam);
        Scalar gjDdiff; CUBLAS_CHECK(cublasDdot(blas, n, gj, 1, Dv, 1, &gjDdiff));
        Scalar bc_d, bp_d;
        CUBLAS_CHECK(cublasDdot(blas, n_c, gj, 1, grad_c, 1, &bc_d));
        CUBLAS_CHECK(cublasDdot(blas, n_p, gj + n_c, 1, grad_p, 1, &bp_d));
        Scalar bg = bc_d + bp_d;
        Scalar dF_pred = 0.5*(bg + gjDdiff);              // free: no H matvec
        // true decrease for this depth
        CUDA_CHECK(cudaMemcpy(d_cand, gj, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
        KernelNegateInPlace<<<GridSize(n),256>>>(d_cand, n);
        Retract(p, s, d_cand, s_new);
        Scalar dF_act = F0 - ComputeCost(p, s_new);
        Scalar rho_j = (std::fabs(dF_pred) > 1e-300) ? dF_act/dF_pred : 0.0;
        // Gram row G_jk = g_j^T H g_k = g_j^T (b - D(g_k - g_{k-1})), free
        std::string row;
        for (int kk = 0; kk <= max_depth; ++kk) {
          const Scalar* gk = G_hist + (size_t)kk*n;
          CUDA_CHECK(cudaMemcpy(diff, gk, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
          if (kk > 0) { const Scalar m1 = -1.0;
            CUBLAS_CHECK(cublasDaxpy(blas, n, &m1, G_hist + (size_t)(kk-1)*n, 1, diff, 1)); }
          ApplyD(diff, Dv, lam_cam);
          Scalar t1, t2, t3;
          CUBLAS_CHECK(cublasDdot(blas, n_c, gj, 1, grad_c, 1, &t1));
          CUBLAS_CHECK(cublasDdot(blas, n_p, gj + n_c, 1, grad_p, 1, &t2));
          CUBLAS_CHECK(cublasDdot(blas, n, gj, 1, Dv, 1, &t3));
          char buf[40]; std::snprintf(buf, sizeof(buf), "%s%.10e", kk ? " " : "", (double)(t1 + t2 - t3));
          row += buf;
        }
        std::fprintf(dfp, "%d,%.6e,%d,%.10e,%.10e,%.10e,%.10e,%.6f,%s\n",
                     diag_k, (double)lam_cam, j, (double)std::sqrt(std::fabs(gDg)), (double)g2,
                     (double)dF_pred, (double)dF_act, (double)rho_j, row.c_str());
      }
      std::fflush(dfp);
    }

    // P7 (round 4): constrained span minimization. The depth loop above already solved the SAME
    // recursion m = max_depth+1 times, giving m Richardson iterates g_0..g_max_depth stashed in
    // G_hist. Rather than accepting one of them individually, search affine combinations
    // v = sum_j a_j g_j for one that beats the best single depth -- using the SAME free identity
    // as the diagnostics above (H g_j = b - D(g_j-g_{j-1})), so the Gram matrix G_jk = g_j^T H g_k
    // and beta_j = g_j^T b cost nothing beyond O(m^2) BLAS dots (m is typically 9).
    // Unconstrained minimization over span{g_j} was tried first and REJECTED (round-4 report):
    // predicted gain tracked step-length inflation almost exactly -- it was finding long steps,
    // not good ones. The fix is the constraint a>=0, sum(a)<=1: by the triangle inequality
    // ||v||_D <= sum_j a_j ||g_j||_D <= max_j ||g_j||_D, so the combined step can never be longer
    // (in the D-metric) than the single longest candidate already being tried -- removing exactly
    // the failure mode that sank the unconstrained version. Final accept is still true-cost-gated,
    // same discipline as every other candidate here.
    if (span_min && max_depth >= 1) {
      int m = max_depth + 1;
      // Batched Gram/beta computation: build diff_k = g_k - g_{k-1} and D*diff_k column-by-column
      // (m cheap device-only kernel launches, no host sync), then get beta = Gh^T b_full via ONE
      // GEMV and the cross term Gh^T (D*Diffs) via ONE GEMM -- replacing what would otherwise be
      // ~m^2 individually-synced cublasDdot calls with exactly 2 device->host copies total.
      CUDA_CHECK(cudaMemcpy(b_full, grad_c, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      CUDA_CHECK(cudaMemcpy(b_full+n_c, grad_p, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      for (int kk = 0; kk < m; ++kk) {
        const Scalar* gk = G_hist + (size_t)kk*n;
        CUDA_CHECK(cudaMemcpy(diff, gk, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
        if (kk > 0) { const Scalar m1 = -1.0;
          CUBLAS_CHECK(cublasDaxpy(blas, n, &m1, G_hist + (size_t)(kk-1)*n, 1, diff, 1)); }
        ApplyD(diff, ADiffs + (size_t)kk*n, lam_cam);
      }
      const Scalar one_g = 1.0, zero_g = 0.0, neg_one_g = -1.0;
      // beta_j = g_j . b_full   (Gh^T b_full, m x n times n)
      CUBLAS_CHECK(cublasDgemv(blas, CUBLAS_OP_T, n, m, &one_g, G_hist, n, b_full, 1, &zero_g, beta_dev, 1));
      // Gtmp(j,k) = -g_j . D.diff_k   (Gh^T ADiffs, m x n times n x m -> m x m, column-major)
      CUBLAS_CHECK(cublasDgemm(blas, CUBLAS_OP_T, CUBLAS_OP_N, m, m, n, &neg_one_g,
                                G_hist, n, ADiffs, n, &zero_g, Gtmp_dev, m));
      std::vector<Scalar> beta_span(m), Gflat((size_t)m*m);
      CUDA_CHECK(cudaMemcpy(beta_span.data(), beta_dev, m*sizeof(Scalar), cudaMemcpyDeviceToHost));
      CUDA_CHECK(cudaMemcpy(Gflat.data(), Gtmp_dev, (size_t)m*m*sizeof(Scalar), cudaMemcpyDeviceToHost));
      std::vector<Scalar> Gmat((size_t)m*m, 0.0);
      for (int j = 0; j < m; ++j) for (int kk = 0; kk < m; ++kk)
        Gmat[(size_t)j*m + kk] = beta_span[j] + Gflat[(size_t)kk*m + j];  // Gtmp col-major: (j,k)@k*m+j
      // symmetrize: H is symmetric, but the identity-based estimate picks up small asymmetric
      // floating-point noise since G_jk and G_kj are computed via different vector pairs.
      for (int j = 0; j < m; ++j) for (int kk = j+1; kk < m; ++kk) {
        Scalar avg = 0.5*(Gmat[(size_t)j*m+kk] + Gmat[(size_t)kk*m+j]);
        Gmat[(size_t)j*m+kk] = Gmat[(size_t)kk*m+j] = avg;
      }
      // Lipschitz constant of the quadratic via power iteration (m is tiny, cost is negligible)
      std::vector<Scalar> pv(m, 1.0/std::sqrt((Scalar)m)), pw(m);
      Scalar L = 1.0;
      for (int it = 0; it < 50; ++it) {
        for (int j = 0; j < m; ++j) { Scalar s = 0; for (int kk = 0; kk < m; ++kk) s += Gmat[(size_t)j*m+kk]*pv[kk]; pw[j] = s; }
        Scalar nrm = 0; for (auto v : pw) nrm += v*v; nrm = std::sqrt(nrm);
        if (nrm < 1e-300) break;
        L = nrm;
        for (int j = 0; j < m; ++j) pv[j] = pw[j] / nrm;
      }
      L = std::max(L, (Scalar)1e-12);
      Scalar pg_step = 1.0 / L;
      // Euclidean projection onto the capped simplex {a>=0, sum(a)<=1} (Wang & Carreira-Perpinan):
      // clip negatives; if the sum already fits, that's the projection; else project the clipped
      // point onto the sum=1 simplex via the standard sort-and-threshold construction.
      auto project_capped_simplex = [&](std::vector<Scalar>& x) {
        Scalar s = 0.0;
        for (auto& v : x) { v = std::max(v, (Scalar)0.0); s += v; }
        if (s <= 1.0) return;
        std::vector<Scalar> sorted = x;
        std::sort(sorted.begin(), sorted.end(), std::greater<Scalar>());
        Scalar cumsum = 0.0, theta = 0.0;
        for (int i = 0; i < m; ++i) {
          cumsum += sorted[i];
          Scalar t = (cumsum - 1.0) / (i + 1);
          if (i == m-1 || sorted[i+1] <= t) { theta = t; break; }
        }
        for (auto& v : x) v = std::max(v - theta, (Scalar)0.0);
      };
      std::vector<Scalar> a_span(m, 0.0), grad_span(m);
      for (int it = 0; it < 200; ++it) {
        for (int j = 0; j < m; ++j) { Scalar s = -beta_span[j]; for (int kk = 0; kk < m; ++kk) s += Gmat[(size_t)j*m+kk]*a_span[kk]; grad_span[j] = s; }
        for (int j = 0; j < m; ++j) a_span[j] -= pg_step * grad_span[j];
        project_capped_simplex(a_span);
      }
      Scalar a_sum = 0.0; for (auto v : a_span) a_sum += v;
      if (a_sum > 1e-12) {
        CUDA_CHECK(cudaMemset(v_span, 0, n*sizeof(Scalar)));
        for (int j = 0; j < m; ++j) {
          if (a_span[j] <= 0.0) continue;
          CUBLAS_CHECK(cublasDaxpy(blas, n, &a_span[j], G_hist + (size_t)j*n, 1, v_span, 1));
        }
        if (prof) { cudaDeviceSynchronize(); t0 = now(); }
        KernelNegateInPlace<<<GridSize(n),256>>>(v_span, n);
        Retract(p, s, v_span, s_new);
        Scalar c = ComputeCost(p, s_new);
        if (prof) { cudaDeviceSynchronize(); t_eval += std::chrono::duration<double>(now()-t0).count(); }
        if (c < best_cost) {
          best_cost = c; depth_out = -3;             // -3 marks the span-min candidate
          ++n_span_win;
          CUDA_CHECK(cudaMemcpy(d_out, v_span, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
        }
      }
    }

    // P.NEW.6 Aitken: the recursion g_j = A^-1(b + lam g_{j-1}) is an affine fixed-point
    // iteration whose error contracts geometrically with rate ~lam/(lam+mu). Estimate that
    // rate from the last three iterates and sum the remaining tail to get a free
    // "depth-infinity" candidate -- no extra factorization, no extra triangular solve.
    if (use_aitken && max_depth >= 2) {
      const Scalar neg1 = -1.0;
      CUDA_CHECK(cudaMemcpy(tmp1, gb_buf, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      CUBLAS_CHECK(cublasDaxpy(blas, n, &neg1, ga_buf, 1, tmp1, 1));           // d1 = g_{m-1} - g_{m-2}
      CUDA_CHECK(cudaMemcpy(tmp2, glast_buf, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      CUBLAS_CHECK(cublasDaxpy(blas, n, &neg1, gb_buf, 1, tmp2, 1));           // d2 = g_m - g_{m-1}
      Scalar d1d1, d2d1;
      CUBLAS_CHECK(cublasDdot(blas, n, tmp1, 1, tmp1, 1, &d1d1));
      CUBLAS_CHECK(cublasDdot(blas, n, tmp2, 1, tmp1, 1, &d2d1));
      if (d1d1 > 0.0) {
        Scalar r = d2d1 / d1d1;
        if (r > 0.0 && r < 0.999) {                    // only extrapolate a genuinely contracting tail
          Scalar w = r / (1.0 - r);
          CUDA_CHECK(cudaMemcpy(d_cand, glast_buf, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
          CUBLAS_CHECK(cublasDaxpy(blas, n, &w, tmp2, 1, d_cand, 1));          // g_inf ~= g_m + r/(1-r) * d2
          if (prof) { cudaDeviceSynchronize(); t0 = now(); }
          KernelNegateInPlace<<<GridSize(n),256>>>(d_cand, n);
          Retract(p, s, d_cand, s_new);
          Scalar c = ComputeCost(p, s_new);
          if (prof) { cudaDeviceSynchronize(); t_eval += std::chrono::duration<double>(now()-t0).count(); }
          if (c < best_cost) {
            best_cost = c; depth_out = -2;             // -2 marks the Aitken depth-inf candidate
            ++n_aitken_win;
            CUDA_CHECK(cudaMemcpy(d_out, d_cand, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
          }
        }
      }
    }
    // Lexicographic override: if ANY candidate did not increase cheirality violations relative
    // to the incumbent, always prefer the best (min-cost) such candidate over a lower-cost but
    // cheirality-increasing one -- this is the [0,8.1] fix, applied after aitken/span_min so it
    // has final say. If no candidate qualified, best_cost/d_out (the plain min-cost result,
    // computed above exactly as without the gate) stands unchanged -- the gate never stalls.
    if (cheir_gate && best_cost_elig < std::numeric_limits<Scalar>::infinity()) {
      best_cost = best_cost_elig; depth_out = depth_out_elig;
      CUDA_CHECK(cudaMemcpy(d_out, d_out_elig, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
    }
    if (sigma_out) *sigma_out = sigma;
    return best_cost;
  };

  // Full 2-D grid sweep with escalation. Returns best cost (inf if nothing improves).
  auto run_full_grid = [&](Scalar cost_current, Scalar* d_out, int& depth_out,
                            Scalar& lam_cam_best, Scalar& lam_pt_best, int& n_esc_out) -> Scalar {
    Scalar cost_best = std::numeric_limits<Scalar>::infinity();
    int n_esc = 0;
    int n_pt_eff = (use_relpt || adaptive_pt) ? 1 : n_pt_candidates;   // lam_pt no longer searched (P.NEW.4/P5)
    for (;; ++n_esc) {
      cost_best = std::numeric_limits<Scalar>::infinity();
      for (int ci = 0; ci < n_cam_candidates; ++ci) {
        Scalar frac_c = n_cam_candidates > 1 ? (Scalar)ci / (n_cam_candidates - 1) : 0.5;
        Scalar lam_cam_val = lam_cam_center * std::pow((Scalar)10.0, -decade_span + 2.0*decade_span*frac_c);
        for (int pi = 0; pi < n_pt_eff; ++pi) {
          Scalar frac_p = n_pt_eff > 1 ? (Scalar)pi / (n_pt_eff - 1) : 0.5;
          Scalar lam_pt_val = (use_relpt || adaptive_pt) ? 0.0
                                        : lam_pt_center * std::pow((Scalar)10.0, -decade_span + 2.0*decade_span*frac_p);
          int depth_this; Scalar sig;
          Scalar c = try_lambda_pair(lam_cam_val, lam_pt_val, d, depth_this, &sig);
          if (c < cost_best) {
            cost_best = c; lam_cam_best = lam_cam_val; lam_pt_best = lam_pt_val; depth_out = depth_this;
            sigma_last = sig;
            CUDA_CHECK(cudaMemcpy(d_out, d, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
          }
        }
      }
      if (cost_best < cost_current || n_esc >= max_escalations) break;
      lam_cam_center *= 10.0; if (!use_relpt && !adaptive_pt) lam_pt_center *= 10.0;
    }
    n_esc_out = n_esc;
    return cost_best;
  };

  MemMark("oca_round2 solver allocations");
  CsvOpen("oca_round2", g_csv_problem.c_str()); CsvRow(0, (double)cost);
  for (int k = 0; k < max_iter; ++k) {
    diag_k = k;
    if (cheir_gate) cheir_incumbent = CountCheirFast(s);   // incumbent violation count for this outer iter
    K_ready = false;   // H_pp changed: the hoisted Schur correction must be rebuilt
    std::chrono::steady_clock::time_point tk0;
    if (g_bal_ptr && std::find(g_dump_iters.begin(), g_dump_iters.end(), k) != g_dump_iters.end())
      DumpBalState(g_dump_prefix + "_it" + std::to_string(k) + ".txt", *g_bal_ptr, s, ncam, npt);
    if (prof) { cudaDeviceSynchronize(); tk0 = now(); }
    CUDA_CHECK(cudaMemset(Hcc, 0, 36*(size_t)ncam*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(Hpp, 0, 9*(size_t)npt*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(grad_c, 0, 6*(size_t)ncam*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(grad_p, 0, 3*(size_t)npt*sizeof(Scalar)));
    if (fp32_jac)
      KernelAssembleSchurSparseGN_J32<float><<<GridSize(p.nobs),256>>>(
          p.cam_idx, p.pt_idx, p.uv, s.R, s.t, s.X, p.f, p.k1, p.k2, p.nobs,
          Hcc, Hpp, obs_Hcp32, grad_c, grad_p);
    else
      KernelAssembleSchurSparseGN<Scalar><<<GridSize(p.nobs),256>>>(
          p.cam_idx, p.pt_idx, p.uv, s.R, s.t, s.X, p.f, p.k1, p.k2, p.nobs,
          Hcc, Hpp, obs_Hcp, grad_c, grad_p);
    if (prof) { cudaDeviceSynchronize(); t_assembly += std::chrono::duration<double>(now()-tk0).count(); }

    Scalar grad_norm;
    { std::chrono::steady_clock::time_point q0; if (prof){cudaDeviceSynchronize(); q0=now();}
      std::vector<Scalar> h_grad_full(n);
      CUDA_CHECK(cudaMemcpy(h_grad_full.data(), grad_c, n_c*sizeof(Scalar), cudaMemcpyDeviceToHost));
      CUDA_CHECK(cudaMemcpy(h_grad_full.data()+n_c, grad_p, n_p*sizeof(Scalar), cudaMemcpyDeviceToHost));
      Scalar s2 = 0.0; for (auto v : h_grad_full) s2 += v*v;
      grad_norm = std::sqrt(s2);
      if (prof){cudaDeviceSynchronize(); t_gradnorm += std::chrono::duration<double>(now()-q0).count();}
    }
    if (grad_norm0 < 0.0) grad_norm0 = std::max(grad_norm, (Scalar)1e-300);

    // P.NEW.3: RELATIVE damping floor, recomputed per iteration from the (lambda-independent)
    // camera Hessian diagonal -- round 1 used an absolute lam0*1e-8, which is what let
    // lam_cam collapse to a meaningless value on a well-scaled problem.
    if (use_audit) {
      KernelExtractDiagHcc<<<GridSize(n_c),256>>>(Hcc, ncam, diagHcc);
      std::vector<Scalar> h_diag(n_c);
      CUDA_CHECK(cudaMemcpy(h_diag.data(), diagHcc, n_c*sizeof(Scalar), cudaMemcpyDeviceToHost));
      Scalar mx = 0.0; for (auto v : h_diag) mx = std::max(mx, std::fabs(v));
      lam_floor = eps_rel * std::max(mx, (Scalar)1e-300);
      lam_cam_center = std::max(lam_cam_center, lam_floor);
    }

    Scalar cost_current = cost, cost_best = std::numeric_limits<Scalar>::infinity();
    Scalar lam_cam_best = lam_cam_center, lam_pt_best = lam_pt_center;
    int depth_best = 0, n_esc = 0;
    bool used_cheap = false, audit_fired = false;
    const char* audit_why = "";

    // ---- decide cheap vs full ----
    bool force_full = !cheap_first;
    if (use_audit && !force_full) {
      if (lam_cam_center <= 10.0 * lam_floor)      { force_full = true; audit_why = "A:floor-prox"; }
      else if (rho_prev < 0.5)                      { force_full = true; audit_why = "B:rho"; }
      else if (floor_streak >= 2)                   { force_full = true; audit_why = "C:floor-streak"; }
      else if (iters_since_audit >= K_audit)        { force_full = true; audit_why = "D:periodic"; }
      else if (sigma_last < 1e-3)                   { force_full = true; audit_why = "E:sigma"; }
    }

    if (!force_full) {
      int depth_this; Scalar sig;
      Scalar c = try_lambda_pair(lam_cam_center, lam_pt_center, d, depth_this, &sig);
      if (c < cost_current) {
        cost_best = c; lam_cam_best = lam_cam_center; lam_pt_best = lam_pt_center;
        depth_best = depth_this; sigma_last = sig; used_cheap = true;
        CUDA_CHECK(cudaMemcpy(d_best, d, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      } else { audit_why = "F:cheap-failed"; }
    }

    // P.NEW.1 oracle trace: also run the full grid (without accepting it) so the per-iteration
    // regret of the cheap path can be logged. Diagnostic only -- costs a full grid every iter.
    Scalar oracle_full_cost = std::numeric_limits<Scalar>::infinity();
    if (oracle && used_cheap) {
      Scalar lc, lp; int dd, ne;
      Scalar save_cam = lam_cam_center, save_pt = lam_pt_center;
      oracle_full_cost = run_full_grid(cost_current, d_alpha, dd, lc, lp, ne);
      lam_cam_center = save_cam; lam_pt_center = save_pt;   // do NOT let the probe move state
    }

    if (!used_cheap) {
      audit_fired = true; ++n_audit_fired;
      cost_best = run_full_grid(cost_current, d_best, depth_best, lam_cam_best, lam_pt_best, n_esc);
      K_audit = std::max(2, K_audit / 2);
      iters_since_audit = 0;
      ++n_full;
    } else {
      K_audit = std::min(16, K_audit * 2);
      ++iters_since_audit;
      ++n_cheap;
    }

    if (cost_best >= cost_current) {
      if (verbose) std::printf("  OCA-Round2: converged / no improving step at k=%d (cost=%.6e)\n", k, cost);
      break;
    }

    // P.NEW.9 two-parameter step-length search: P5 established cameras and points want
    // DIFFERENT damping, so they plausibly want different step lengths too. Pure residual
    // evaluations -- no linear algebra, no factorization.
    if (use_alpha) {
      std::chrono::steady_clock::time_point q0; if (prof){cudaDeviceSynchronize(); q0=now();}
      const Scalar alphas[3] = {0.7, 1.0, 1.4};
      Scalar best_a = cost_best;
      for (int ia = 0; ia < 3; ++ia) for (int ib = 0; ib < 3; ++ib) {
        if (alphas[ia] == 1.0 && alphas[ib] == 1.0) continue;   // already have it
        CUDA_CHECK(cudaMemcpy(d_alpha, d_best, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
        CUBLAS_CHECK(cublasDscal(blas, n_c, &alphas[ia], d_alpha, 1));
        CUBLAS_CHECK(cublasDscal(blas, n_p, &alphas[ib], d_alpha + n_c, 1));
        Retract(p, s, d_alpha, s_new);
        Scalar c = ComputeCost(p, s_new);
        if (c < best_a) {
          best_a = c; ++n_alpha_win;
          CUDA_CHECK(cudaMemcpy(d, d_alpha, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
        }
      }
      if (best_a < cost_best) {
        cost_best = best_a;
        CUDA_CHECK(cudaMemcpy(d_best, d, n*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      }
      if (prof){cudaDeviceSynchronize(); t_alpha_b += std::chrono::duration<double>(now()-q0).count();}
    }

    // rho = actual / predicted reduction, for AUDIT trigger B next iteration
    {
      std::chrono::steady_clock::time_point q0; if (prof){cudaDeviceSynchronize(); q0=now();}
      CUDA_CHECK(cudaMemset(jd_sum, 0, sizeof(Scalar)));
      KernelJdSquaredSum<<<GridSize(p.nobs),256>>>(p.cam_idx, p.pt_idx, p.uv, s.R, s.t, s.X, p.f, p.k1, p.k2,
                                                    d_best, p.nobs, ncam, jd_sum);
      Scalar quad; CUDA_CHECK(cudaMemcpy(&quad, jd_sum, sizeof(Scalar), cudaMemcpyDeviceToHost));
      std::vector<Scalar> h_g(n), h_d(n);
      CUDA_CHECK(cudaMemcpy(h_g.data(), grad_c, n_c*sizeof(Scalar), cudaMemcpyDeviceToHost));
      CUDA_CHECK(cudaMemcpy(h_g.data()+n_c, grad_p, n_p*sizeof(Scalar), cudaMemcpyDeviceToHost));
      CUDA_CHECK(cudaMemcpy(h_d.data(), d_best, n*sizeof(Scalar), cudaMemcpyDeviceToHost));
      Scalar gd = 0.0; for (int i = 0; i < n; ++i) gd += h_g[i]*h_d[i];
      Scalar pred = -(gd + 0.5*quad);
      rho_prev = (std::fabs(pred) > 1e-300) ? (cost_current - cost_best) / pred : 0.0;
      if (prof){cudaDeviceSynchronize(); t_rho_b += std::chrono::duration<double>(now()-q0).count();}
    }

    lam_cam_center = std::max(lam_cam_best * 0.5, use_audit ? lam_floor : lam0 * 1e-8);
    if (!use_relpt && !adaptive_pt) lam_pt_center = std::max(lam_pt_best * 0.5, lam0 * 1e-8);
    floor_streak = (lam_cam_center <= 10.0 * lam_floor) ? floor_streak + 1 : 0;

    Retract(p, s, d_best, s_new);
    std::swap(s.R, s_new.R); std::swap(s.t, s_new.t); std::swap(s.X, s_new.X);
    cost = cost_best;

    std::vector<Scalar> h_d(n);
    CUDA_CHECK(cudaMemcpy(h_d.data(), d_best, n*sizeof(Scalar), cudaMemcpyDeviceToHost));
    Scalar step_norm = 0.0; for (auto v : h_d) step_norm += v*v; step_norm = std::sqrt(step_norm);

    log.iters.push_back(k+1); log.costs.push_back(cost);
    CsvRow(k+1, (double)cost);
    if (verbose) {
      if (oracle && used_cheap) {
        Scalar regret = cost_best - oracle_full_cost;
        std::printf("  OCA-Round2 it%4d cost=%.6e |d|=%.3e lam_cam=%.3e depth=%d mode=cheap sigma=%.3e rho=%.3f ORACLE_full=%.6e regret=%+.6e\n",
                    k+1, cost, step_norm, lam_cam_best, depth_best, sigma_last, rho_prev, oracle_full_cost, regret);
      } else {
        std::printf("  OCA-Round2 it%4d cost=%.6e |d|=%.3e lam_cam=%.3e lam_pt=%.3e depth=%d n_esc=%d mode=%-5s%s sigma=%.3e rho=%.3f |g|/|g0|=%.3e |g|=%.6e\n",
                    k+1, cost, step_norm, lam_cam_best, lam_pt_best, depth_best, n_esc,
                    used_cheap ? "cheap" : "full", audit_fired ? audit_why : "", sigma_last, rho_prev, grad_norm/grad_norm0, grad_norm);
      }
    }
    if (step_norm < tol && grad_norm < 1e-8 * grad_norm0) break;
  }
  if (verbose) {
    std::printf("  OCA-Round2: cheap=%d full=%d audits=%d aitken_wins=%d alpha_wins=%d span_wins=%ld cheb_wins=%ld\n",
                n_cheap, n_full, n_audit_fired, n_aitken_win, n_alpha_win, n_span_win, n_cheb_win);
    if (!cheb_polys.empty()) {
      std::string brk;
      for (size_t ki = 0; ki < cheb_polys.size(); ++ki) {
        char buf[48]; std::snprintf(buf, sizeof(buf), "%sHYB(%d,%d)=%ld", ki?" ":"", cheb_polys[ki].r, cheb_polys[ki].k, n_cheb_win_by_k[ki]);
        brk += buf;
      }
      std::printf("  [A1] wins by k: %s\n", brk.c_str());
    }
    if (fp32_refine) std::printf("  OCA-Round2[fp32+IR]: solves=%ld ir_steps=%ld (%.2f/solve) not_converged=%ld (%.2f%%)\n",
                                 n_solves, n_ir_steps, n_solves ? (double)n_ir_steps/n_solves : 0.0,
                                 n_ir_fallback, n_solves ? 100.0*n_ir_fallback/n_solves : 0.0),
                     std::printf("  OCA-Round2[fp32+IR]: fp64 refactor bailouts = %ld\n", n_fp32_bailout);
    if (prof) std::printf("  [PROFILE] assembly=%.3fs schur+factor=%.3fs (of which POTRF=%.3fs, schur_form=%.3fs) recursion=%.3fs eval=%.3fs\n",
                          t_assembly, t_factor, t_potrf, t_factor - t_potrf, t_recursion, t_eval);
    if (prof) std::printf("  [PROFILE2] gradnorm=%.3fs alpha=%.3fs rho=%.3fs\n",
                          t_gradnorm, t_alpha_b, t_rho_b);
  }

  cusolverDnDestroy(handle); cublasDestroy(blas);
  cudaFree(Hcc); cudaFree(Hpp); cudaFree(obs_Hcp); cudaFree(obs_Hcp32); cudaFree(grad_c); cudaFree(grad_p);
  cudaFree(App_inv); cudaFree(S); cudaFree(bc_corr); cudaFree(bc_prime); cudaFree(xc); cudaFree(xp);
  cudaFree(gc_prev); cudaFree(gp_prev); cudaFree(bp_j); cudaFree(bc_j); cudaFree(d); cudaFree(d_best); cudaFree(d_cand);
  if (fp32_refine) { cudaFree(S32); cudaFree(v32); cudaFree(x_acc); cudaFree(r_vec); cudaFree(dlt); cudaFree(xc_save); }
  if (hoist_K) cudaFree(K_inv);
  if (diag) std::fclose(dfp);
  if (need_basis) { cudaFree(G_hist); cudaFree(Dv); cudaFree(diff); }
  if (span_min) { cudaFree(v_span); cudaFree(ADiffs); cudaFree(b_full); cudaFree(beta_dev); cudaFree(Gtmp_dev); }
  if (cheb_filter && !cheb_polys.empty()) {
    cudaFree(cheb_Dv); cudaFree(cheb_Mv); cudaFree(cheb_b1); cudaFree(cheb_b2); cudaFree(cheb_b0); cudaFree(cheb_step);
  }
  if (cheir_gate) { cudaFree(cheir_gate_buf); cudaFree(d_out_elig); }
  if (adaptive_pt) cudaFree(pt_damp);
  cudaFree(g0_buf); cudaFree(ga_buf); cudaFree(gb_buf); cudaFree(glast_buf);
  cudaFree(tmp1); cudaFree(tmp2); cudaFree(d_alpha); cudaFree(diagHcc); cudaFree(jd_sum); cudaFree(ok_flags);
  cudaFree(s_new.R); cudaFree(s_new.t); cudaFree(s_new.X);
  CsvClose();
  return log;
}

// Task #7 (OCA_Acceleration_Strategies.pdf): cheap mu_min/mu_max estimate of
// a small symmetric tridiagonal matrix (diagonal `a`, off-diagonal `b`,
// b[0] unused/ignored -- matches this file's Lanczos alpha_h/beta_h
// convention where beta_h[0]=0) via bisection on the Sturm-sequence sign-
// count, the classical method for tridiagonal eigenvalue LOCALIZATION (not
// full diagonalization -- we only want the two extremes, and only to a few
// significant figures, since this is a REGIME DETECTOR not a precise
// eigensolver). Gershgorin bounds the initial bracket; count(x) = number of
// eigenvalues < x via the standard three-term Sturm recursion
// d_0=a_0-x, d_i=(a_i-x)-b_i^2/d_{i-1}, count = #{d_i<0}, with the
// classical near-zero-pivot safeguard (d_{i-1}->tiny treated as a sign
// change, avoiding division blowup without needing exact zero detection).
int SturmCount(const std::vector<Scalar>& a, const std::vector<Scalar>& b, Scalar x) {
  int m = (int)a.size();
  int count = 0;
  Scalar d = a[0] - x;
  if (d < 0) ++count;
  for (int i = 1; i < m; ++i) {
    Scalar denom = (std::fabs(d) < 1e-300) ? (Scalar)1e-300 : d;
    d = (a[i] - x) - b[i]*b[i] / denom;
    if (d < 0) ++count;
  }
  return count;
}

void TridiagExtremeEigenvalues(const std::vector<Scalar>& a, const std::vector<Scalar>& b,
                                Scalar& mu_min, Scalar& mu_max, int bisect_iters = 60) {
  int m = (int)a.size();
  Scalar lo = a[0], hi = a[0];
  for (int i = 0; i < m; ++i) {
    Scalar radius = (i > 0 ? std::fabs(b[i]) : 0.0) + (i+1 < m ? std::fabs(b[i+1]) : 0.0);
    lo = std::min(lo, a[i] - radius); hi = std::max(hi, a[i] + radius);
  }
  // mu_min: smallest x with count(x) >= 1 (i.e. the smallest eigenvalue itself)
  Scalar lo1 = lo, hi1 = hi;
  for (int it = 0; it < bisect_iters; ++it) {
    Scalar mid = 0.5*(lo1+hi1);
    if (SturmCount(a, b, mid) >= 1) hi1 = mid; else lo1 = mid;
  }
  mu_min = hi1;
  // mu_max: smallest x with count(x) >= m (all eigenvalues below x)
  Scalar lo2 = lo, hi2 = hi;
  for (int it = 0; it < bisect_iters; ++it) {
    Scalar mid = 0.5*(lo2+hi2);
    if (SturmCount(a, b, mid) >= m) hi2 = mid; else lo2 = mid;
  }
  mu_max = hi2;
}

// Solves a small (m x m) SPD system via in-place Cholesky -- used by both
// the MINRES depth-checkpoint least-squares solve below and Anderson
// Acceleration's small coefficient solve further down -- m never exceeds a
// few dozen in either use, so no cuSOLVER needed; this runs on the host in
// microseconds regardless of problem scale.
std::vector<Scalar> SolveSmallSPD(std::vector<std::vector<Scalar>> A, std::vector<Scalar> b) {
  int m = (int)b.size();
  for (int i = 0; i < m; ++i) {
    for (int j = 0; j <= i; ++j) {
      Scalar sum = A[i][j];
      for (int k = 0; k < j; ++k) sum -= A[i][k]*A[j][k];
      if (i == j) A[i][j] = std::sqrt(std::max(sum, (Scalar)1e-300));
      else A[i][j] = sum / A[j][j];
    }
  }
  std::vector<Scalar> y(m);
  for (int i = 0; i < m; ++i) {
    Scalar sum = b[i];
    for (int k = 0; k < i; ++k) sum -= A[i][k]*y[k];
    y[i] = sum / A[i][i];
  }
  std::vector<Scalar> x(m);
  for (int i = m-1; i >= 0; --i) {
    Scalar sum = y[i];
    for (int k = i+1; k < m; ++k) sum -= A[k][i]*x[k];
    x[i] = sum / A[i][i];
  }
  return x;
}

// ============================================================== Task: MINRES-based candidate generation replacing OCA's growing-depth
// Richardson recursion, on the TRUE (non-Gauss-Newton, genuinely indefinite)
// Hessian -- Strategy #2 of OCA_Acceleration_Strategies.pdf, numpy-validated
// first: on ladybug-49 at a matched 20-iteration budget, this beat the
// existing coupled-OCA-true-Hessian baseline by ~32% (23,958 vs 35,231),
// using a MODEST point-block regularization (lambda_pt~3e3) vs the
// baseline's need for a single global lambda~1e6 to force the whole
// reduced system PD for Cholesky.
//
// Why MINRES applies here where OCA's own recursion (dossier Sec 3) and
// Chebyshev/Nesterov (Sec 7) do not: OCA's recursion is a Richardson
// iteration with contraction factor rho=lambda/(mu+lambda), which EXCEEDS 1
// for ANY lambda>0 whenever H has a negative eigenvalue mu -- i.e. it is
// mechanically unsafe on indefinite H. MINRES is specifically designed for
// symmetric INDEFINITE systems: its iterate sequence x_0,x_1,...,x_j
// minimizes ||Sx-b|| over the growing Krylov subspace, a quantity that is
// PROVABLY NON-INCREASING at every step, with no positive-definiteness
// requirement on S at all.
//
// Implementation: build the Schur complement S (n_c x n_c, DENSE but small
// -- a few hundred to few thousand dims -- so an explicit dense matrix and
// cuBLAS dgemv/ddot/dnrm2/daxpy are the right tool, no custom sparse
// infrastructure needed) from the TRUE Hessian's Hcc/Hpp/obs_Hcp, with only
// a SMALL regularizing lambda_pt on the POINT blocks (needed to keep the
// per-point Schur elimination itself well-defined -- Happ+lambda_pt*I must
// be PD for KernelInvertAppBlocks' Cholesky-based inverse -- NOT to make S
// itself PD, which would defeat the entire point of using MINRES over
// Cholesky). S is left otherwise unregularized (lambda=0 on the camera
// diagonal, via KernelBuildAccFull's existing lambda parameter).
//
// Runs j_max steps of Lanczos tridiagonalization on (S, bc) via cuBLAS
// (matvec, dot, axpy, nrm2 all provided; only the small (<=j_max) tridiagonal
// least-squares solve per depth checkpoint is hand-rolled, reusing
// SolveSmallSPD via the normal equations on the explicitly-formed small
// Hessenberg/tridiagonal matrix -- exact in the same sense joint-lambda-
// depth's growing recursion reuses one factorization for multiple depths,
// just via Lanczos's incremental structure instead of a single Cholesky).
// True-cost-checks EVERY depth 1..m from the one Lanczos run and keeps the
// best, exactly like SolveOCAJointLambdaDepth's own accept-by-true-cost
// design -- same escalate-on-PD-failure/shrink-on-success pattern for
// lambda_pt as every other solver in this file.
RunLog SolveOCAMinresSchurSparse(const DeviceProblem& p, DeviceState& s, Scalar lam_pt0, int j_max,
                                  Scalar tol, int max_iter, bool verbose, int max_escalations = 25) {
  int ncam = p.ncam, npt = p.npt, n_c = 6*ncam, n_p = 3*npt, n = n_c + n_p;
  Scalar *Hcc, *Hpp, *obs_Hcp, *grad_c, *grad_p, *App_inv, *S;
  Scalar *bc, *bc_corr, *xc, *xp, *d, *d_best, *Q, *w, *y_dev;
  int* ok_flags;
  CUDA_CHECK(cudaMalloc(&Hcc, 36*(size_t)ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&Hpp, 9*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&obs_Hcp, 18*(size_t)p.nobs*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&grad_c, 6*(size_t)ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&grad_p, 3*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&App_inv, 9*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&S, (size_t)n_c*n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bc, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bc_corr, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&xc, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&xp, n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&d, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&d_best, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&Q, (size_t)n_c*(j_max+1)*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&w, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&y_dev, (size_t)j_max*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&ok_flags, npt*sizeof(int)));
  DeviceState s_cand; AllocState(s_cand, ncam, npt);

  cublasHandle_t blas; CUBLAS_CHECK(cublasCreate(&blas));
  std::vector<Scalar> alpha_h(j_max), beta_h(j_max+1, 0.0);

  Scalar cost = ComputeCost(p, s);
  RunLog log; log.iters.push_back(0); log.costs.push_back(cost);
  Scalar lam_pt = lam_pt0;
  Scalar grad_norm0 = -1.0;  // see the grad-norm convergence check below

  for (int k = 0; k < max_iter; ++k) {
    CUDA_CHECK(cudaMemset(Hcc, 0, 36*(size_t)ncam*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(Hpp, 0, 9*(size_t)npt*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(grad_c, 0, 6*(size_t)ncam*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(grad_p, 0, 3*(size_t)npt*sizeof(Scalar)));
    KernelAssembleSchurSparse<<<GridSize(p.nobs),256>>>(
        p.cam_idx, p.pt_idx, p.uv, s.R, s.t, s.X, p.f, p.k1, p.k2, p.nobs,
        Hcc, Hpp, obs_Hcp, grad_c, grad_p);

    // Gradient-norm convergence signal, independent of step size -- the SAME false-convergence
    // failure mode documented and fixed elsewhere in this file (SolveLMSchurSparse,
    // SolveOCASchurSparseGNMultiLambda): an escalated lam_pt can force a tiny step
    // (step_norm<tol) while the true gradient is still large, exactly what ladybug-598
    // showed here (lam_pt escalating to ~1e19-5e19, |d| dropping to ~1e-8 after only 5
    // outer iterations while cost was still ~6.3e6, nowhere near converged).
    Scalar grad_norm;
    { std::vector<Scalar> h_grad_full(n);
      CUDA_CHECK(cudaMemcpy(h_grad_full.data(), grad_c, n_c*sizeof(Scalar), cudaMemcpyDeviceToHost));
      CUDA_CHECK(cudaMemcpy(h_grad_full.data()+n_c, grad_p, n_p*sizeof(Scalar), cudaMemcpyDeviceToHost));
      Scalar s2 = 0.0; for (auto v : h_grad_full) s2 += v*v;
      grad_norm = std::sqrt(s2);
    }
    if (grad_norm0 < 0.0) grad_norm0 = std::max(grad_norm, (Scalar)1e-300);

    int esc = 0;
    for (;; ++esc) {
      KernelInvertAppBlocks<<<GridSize(npt),256>>>(Hpp, lam_pt, App_inv, ok_flags, npt);
      bool pd_ok = true;
      { std::vector<int> h_ok(npt);
        CUDA_CHECK(cudaMemcpy(h_ok.data(), ok_flags, npt*sizeof(int), cudaMemcpyDeviceToHost));
        for (int v : h_ok) if (!v) pd_ok = false;
      }
      if (pd_ok) break;
      if (esc >= max_escalations) {
        std::fprintf(stderr, "OCA-MINRES: point blocks (Happ+lam_pt*I) not PD at k=%d even after escalating lam_pt to %.4g\n", k, lam_pt);
        std::exit(EXIT_FAILURE);
      }
      lam_pt *= 10.0;
    }

    CUDA_CHECK(cudaMemset(S, 0, (size_t)n_c*n_c*sizeof(Scalar)));
    KernelBuildAccFull<<<GridSize(ncam),256>>>(Hcc, (Scalar)0.0, S, ncam, n_c);  // NO damping on S itself -- MINRES doesn't need PD
    KernelFormSSparse<<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                              App_inv, npt, n_c, S);

    CUDA_CHECK(cudaMemset(bc_corr, 0, n_c*sizeof(Scalar)));
    KernelRHSCorrectionSparse<<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                                       App_inv, grad_p, npt, bc_corr);
    KernelSubtractVec<<<GridSize(n_c),256>>>(bc, grad_c, bc_corr, n_c);

    Scalar beta_rhs; CUBLAS_CHECK(cublasDnrm2(blas, n_c, bc, 1, &beta_rhs));
    if (beta_rhs < 1e-300) {
      if (verbose) std::printf("  OCA-MINRES: |grad| numerically zero at k=%d, converged\n", k);
      break;
    }
    CUDA_CHECK(cudaMemcpy(Q, bc, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
    { Scalar inv_beta = 1.0/beta_rhs; CUBLAS_CHECK(cublasDscal(blas, n_c, &inv_beta, Q, 1)); }

    int m = 0;
    const Scalar one = 1.0, zero = 0.0;
    for (int j = 0; j < j_max; ++j) {
      CUBLAS_CHECK(cublasDgemv(blas, CUBLAS_OP_N, n_c, n_c, &one, S, n_c, Q + (size_t)j*n_c, 1, &zero, w, 1));
      Scalar alpha_j; CUBLAS_CHECK(cublasDdot(blas, n_c, Q + (size_t)j*n_c, 1, w, 1, &alpha_j));
      alpha_h[j] = alpha_j;
      { Scalar neg = -alpha_j; CUBLAS_CHECK(cublasDaxpy(blas, n_c, &neg, Q + (size_t)j*n_c, 1, w, 1)); }
      if (j > 0) { Scalar neg = -beta_h[j]; CUBLAS_CHECK(cublasDaxpy(blas, n_c, &neg, Q + (size_t)(j-1)*n_c, 1, w, 1)); }
      // one full-reorthogonalization pass against all prior Lanczos vectors -- j_max is small
      // (a few dozen at most) so this is cheap, and it's the standard fix for the classical
      // three-term recurrence's known loss-of-orthogonality at moderate depth.
      for (int jj = 0; jj <= j; ++jj) {
        Scalar dp; CUBLAS_CHECK(cublasDdot(blas, n_c, Q + (size_t)jj*n_c, 1, w, 1, &dp));
        Scalar neg = -dp; CUBLAS_CHECK(cublasDaxpy(blas, n_c, &neg, Q + (size_t)jj*n_c, 1, w, 1));
      }
      Scalar beta_next; CUBLAS_CHECK(cublasDnrm2(blas, n_c, w, 1, &beta_next));
      beta_h[j+1] = beta_next;
      m = j + 1;
      if (beta_next < 1e-12 * beta_rhs) break;  // Krylov subspace exhausted -- exact solution reached
      if (j + 1 < j_max) {
        CUDA_CHECK(cudaMemcpy(Q + (size_t)(j+1)*n_c, w, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
        Scalar inv_beta = 1.0/beta_next; CUBLAS_CHECK(cublasDscal(blas, n_c, &inv_beta, Q + (size_t)(j+1)*n_c, 1));
      }
    }

    // Task #7: cheap curvature-regime estimate, entirely FREE (reuses the
    // Lanczos tridiagonal already built above for depth generation) -- the
    // Ritz values of T_m (its own eigenvalues) approximate S's extreme
    // eigenvalues, the classical Lanczos property that this whole method
    // already implicitly relies on for its OWN convergence, just not
    // previously extracted or reported.
    Scalar mu_min_est = 0.0, mu_max_est = 0.0;
    { std::vector<Scalar> a_tri(alpha_h.begin(), alpha_h.begin()+m);
      std::vector<Scalar> b_tri(m, 0.0); for (int i = 1; i < m; ++i) b_tri[i] = beta_h[i];
      TridiagExtremeEigenvalues(a_tri, b_tri, mu_min_est, mu_max_est);
    }

    Scalar best_cost = std::numeric_limits<Scalar>::infinity();
    int best_depth = 0;
    for (int depth = 1; depth <= m; ++depth) {
      // Explicit (depth+1) x depth Lanczos tridiagonal M_d; normal-equations least-squares
      // (reusing SolveSmallSPD) for y_d = argmin ||M_d y - beta_rhs*e_0||_2.
      std::vector<std::vector<Scalar>> Mrows(depth+1, std::vector<Scalar>(depth, 0.0));
      for (int i = 0; i < depth; ++i) Mrows[i][i] = alpha_h[i];
      for (int i = 0; i < depth-1; ++i) { Mrows[i][i+1] = beta_h[i+1]; Mrows[i+1][i] = beta_h[i+1]; }
      Mrows[depth][depth-1] = beta_h[depth];
      std::vector<std::vector<Scalar>> G(depth, std::vector<Scalar>(depth, 0.0));
      std::vector<Scalar> rhs(depth, 0.0);
      for (int a = 0; a < depth; ++a) {
        for (int b = 0; b < depth; ++b) {
          Scalar sum = 0.0; for (int r = 0; r <= depth; ++r) sum += Mrows[r][a]*Mrows[r][b];
          G[a][b] = sum;
        }
        rhs[a] = beta_rhs * Mrows[0][a];
      }
      std::vector<Scalar> y = SolveSmallSPD(G, rhs);
      std::vector<Scalar> y_pad(m, 0.0);
      for (int i = 0; i < depth; ++i) y_pad[i] = y[i];
      CUDA_CHECK(cudaMemcpy(y_dev, y_pad.data(), m*sizeof(Scalar), cudaMemcpyHostToDevice));
      CUBLAS_CHECK(cublasDgemv(blas, CUBLAS_OP_N, n_c, m, &one, Q, n_c, y_dev, 1, &zero, xc, 1));

      KernelBackSubstituteSparse<<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                                          App_inv, grad_p, xc, npt, xp);
      CUDA_CHECK(cudaMemcpy(d, xc, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      CUDA_CHECK(cudaMemcpy(d+n_c, xp, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      KernelNegateInPlace<<<GridSize(n),256>>>(d, n);

      Retract(p, s, d, s_cand);
      Scalar c = ComputeCost(p, s_cand);
      if (c < best_cost) { best_cost = c; best_depth = depth; CUDA_CHECK(cudaMemcpy(d_best, d, n*sizeof(Scalar), cudaMemcpyDeviceToDevice)); }
    }

    if (best_cost >= cost) {
      if (verbose) std::printf("  OCA-MINRES: no improving depth found at k=%d (cost=%.6e, m=%d)\n", k, cost, m);
      break;
    }
    lam_pt = std::max(lam_pt * 0.5, lam_pt0);

    Retract(p, s, d_best, s_cand);
    std::swap(s.R, s_cand.R); std::swap(s.t, s_cand.t); std::swap(s.X, s_cand.X);
    cost = best_cost;

    std::vector<Scalar> h_d(n);
    CUDA_CHECK(cudaMemcpy(h_d.data(), d_best, n*sizeof(Scalar), cudaMemcpyDeviceToHost));
    Scalar step_norm = 0.0; for (auto v : h_d) step_norm += v*v; step_norm = std::sqrt(step_norm);

    log.iters.push_back(k+1); log.costs.push_back(cost);
    if (verbose) std::printf("  OCA-MINRES it%4d cost=%.6e best_depth=%d/%d lam_pt=%.3e |d|=%.3e |grad|/|grad0|=%.3e mu_min(S)~%.3e mu_max(S)~%.3e\n",
                              k+1, cost, best_depth, m, lam_pt, step_norm, grad_norm/grad_norm0, mu_min_est, mu_max_est);
    if (step_norm < tol && grad_norm < 1e-8 * grad_norm0) break;
  }

  cublasDestroy(blas);
  cudaFree(Hcc); cudaFree(Hpp); cudaFree(obs_Hcp); cudaFree(grad_c); cudaFree(grad_p);
  cudaFree(App_inv); cudaFree(S); cudaFree(bc); cudaFree(bc_corr); cudaFree(xc); cudaFree(xp);
  cudaFree(d); cudaFree(d_best); cudaFree(Q); cudaFree(w); cudaFree(y_dev); cudaFree(ok_flags);
  cudaFree(s_cand.R); cudaFree(s_cand.t); cudaFree(s_cand.X);
  return log;
}

// ============================================================== Task #7: curvature-regime solver switch. Empirically motivated by
// mu_min(S)'s actually-measured trajectory (via SolveOCAMinresSchurSparse's
// new logging) on real BAL data: contrary to this investigation's earlier
// toy-scale characterization of the RAW, unregularized Hessian staying
// persistently indefinite, the SCHUR-REDUCED, point-regularized camera
// system S starts indefinite and TRANSITIONS to confidently PD as
// optimization proceeds -- after just 1 outer iteration on ladybug-49, only
// around iteration 18-20 on the harder ladybug-598. Once S is PD, paying
// for MINRES's full Lanczos-plus-multi-depth-checkpoint machinery is wasted
// work: a single exact Cholesky solve is both cheaper AND gives the exact
// (not j_max-truncated) reduced-system solution.
//
// Regime detection is FREE -- it's just the PD check every Cholesky-based
// solver in this file already needs to do, tried on the UNDAMPED S (matching
// MINRES's own choice not to damp the camera block): if Cholesky succeeds,
// we are (by definition) in the confidently-PD regime; solve exactly, and
// true-cost-gate the result exactly like every other solver here (a PD local
// model still isn't automatically trustworthy far from the current point).
// If Cholesky fails OR the resulting step doesn't improve cost, fall back to
// MINRES's safe indefinite-regime candidate generation (identical code to
// SolveOCAMinresSchurSparse, duplicated rather than factored out -- this
// function is an experimental variant, not a replacement).
RunLog SolveOCACurvatureSwitch(const DeviceProblem& p, DeviceState& s, Scalar lam_pt0, int j_max,
                                Scalar tol, int max_iter, bool verbose, int max_escalations = 25) {
  int ncam = p.ncam, npt = p.npt, n_c = 6*ncam, n_p = 3*npt, n = n_c + n_p;
  Scalar *Hcc, *Hpp, *obs_Hcp, *grad_c, *grad_p, *App_inv, *S, *S_chol;
  Scalar *bc, *bc_corr, *xc, *xp, *d, *d_best, *Q, *w, *y_dev;
  int* ok_flags;
  CUDA_CHECK(cudaMalloc(&Hcc, 36*(size_t)ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&Hpp, 9*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&obs_Hcp, 18*(size_t)p.nobs*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&grad_c, 6*(size_t)ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&grad_p, 3*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&App_inv, 9*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&S, (size_t)n_c*n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&S_chol, (size_t)n_c*n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bc, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bc_corr, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&xc, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&xp, n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&d, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&d_best, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&Q, (size_t)n_c*(j_max+1)*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&w, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&y_dev, (size_t)j_max*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&ok_flags, npt*sizeof(int)));
  DeviceState s_cand; AllocState(s_cand, ncam, npt);

  cublasHandle_t blas; CUBLAS_CHECK(cublasCreate(&blas));
  cusolverDnHandle_t handle; cusolverDnCreate(&handle);
  CholeskyWorkspace ws; ws.Init(handle, n_c);
  std::vector<Scalar> alpha_h(j_max), beta_h(j_max+1, 0.0);

  Scalar cost = ComputeCost(p, s);
  RunLog log; log.iters.push_back(0); log.costs.push_back(cost);
  Scalar lam_pt = lam_pt0;
  Scalar grad_norm0 = -1.0;
  int n_exact_used = 0, n_minres_used = 0;

  for (int k = 0; k < max_iter; ++k) {
    CUDA_CHECK(cudaMemset(Hcc, 0, 36*(size_t)ncam*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(Hpp, 0, 9*(size_t)npt*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(grad_c, 0, 6*(size_t)ncam*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(grad_p, 0, 3*(size_t)npt*sizeof(Scalar)));
    KernelAssembleSchurSparse<<<GridSize(p.nobs),256>>>(
        p.cam_idx, p.pt_idx, p.uv, s.R, s.t, s.X, p.f, p.k1, p.k2, p.nobs,
        Hcc, Hpp, obs_Hcp, grad_c, grad_p);

    Scalar grad_norm;
    { std::vector<Scalar> h_grad_full(n);
      CUDA_CHECK(cudaMemcpy(h_grad_full.data(), grad_c, n_c*sizeof(Scalar), cudaMemcpyDeviceToHost));
      CUDA_CHECK(cudaMemcpy(h_grad_full.data()+n_c, grad_p, n_p*sizeof(Scalar), cudaMemcpyDeviceToHost));
      Scalar s2 = 0.0; for (auto v : h_grad_full) s2 += v*v;
      grad_norm = std::sqrt(s2);
    }
    if (grad_norm0 < 0.0) grad_norm0 = std::max(grad_norm, (Scalar)1e-300);

    int esc = 0;
    for (;; ++esc) {
      KernelInvertAppBlocks<<<GridSize(npt),256>>>(Hpp, lam_pt, App_inv, ok_flags, npt);
      bool pd_ok = true;
      { std::vector<int> h_ok(npt);
        CUDA_CHECK(cudaMemcpy(h_ok.data(), ok_flags, npt*sizeof(int), cudaMemcpyDeviceToHost));
        for (int v : h_ok) if (!v) pd_ok = false;
      }
      if (pd_ok) break;
      if (esc >= max_escalations) {
        std::fprintf(stderr, "OCA-CurvatureSwitch: point blocks not PD at k=%d even after escalating lam_pt to %.4g\n", k, lam_pt);
        std::exit(EXIT_FAILURE);
      }
      lam_pt *= 10.0;
    }

    CUDA_CHECK(cudaMemset(S, 0, (size_t)n_c*n_c*sizeof(Scalar)));
    KernelBuildAccFull<<<GridSize(ncam),256>>>(Hcc, (Scalar)0.0, S, ncam, n_c);
    KernelFormSSparse<<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                              App_inv, npt, n_c, S);
    CUDA_CHECK(cudaMemset(bc_corr, 0, n_c*sizeof(Scalar)));
    KernelRHSCorrectionSparse<<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                                       App_inv, grad_p, npt, bc_corr);
    KernelSubtractVec<<<GridSize(n_c),256>>>(bc, grad_c, bc_corr, n_c);

    // ---- cheap branch: try direct Cholesky on the UNDAMPED S first ----
    CUDA_CHECK(cudaMemcpy(S_chol, S, (size_t)n_c*n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
    bool chol_ok = CholeskyFactor(ws, S_chol);
    Scalar cost_new = std::numeric_limits<Scalar>::infinity();
    bool used_exact = false;
    const char* mode = "minres";
    if (chol_ok) {
      CUDA_CHECK(cudaMemcpy(xc, bc, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      CholeskySolveVec(ws, S_chol, xc);
      KernelBackSubstituteSparse<<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                                          App_inv, grad_p, xc, npt, xp);
      CUDA_CHECK(cudaMemcpy(d, xc, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      CUDA_CHECK(cudaMemcpy(d+n_c, xp, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      KernelNegateInPlace<<<GridSize(n),256>>>(d, n);
      Retract(p, s, d, s_cand);
      cost_new = ComputeCost(p, s_cand);
      if (cost_new < cost) { used_exact = true; mode = "exact-PD"; CUDA_CHECK(cudaMemcpy(d_best, d, n*sizeof(Scalar), cudaMemcpyDeviceToDevice)); }
    }

    Scalar mu_min_est = 0.0, mu_max_est = 0.0;
    int best_depth = 0, m = 0;
    if (!used_exact) {
      // ---- fall back: MINRES's Lanczos-based safe candidate generation (identical to
      // SolveOCAMinresSchurSparse -- see that function for the derivation/comments) ----
      Scalar beta_rhs; CUBLAS_CHECK(cublasDnrm2(blas, n_c, bc, 1, &beta_rhs));
      if (beta_rhs < 1e-300) {
        if (verbose) std::printf("  OCA-CurvatureSwitch: |grad| numerically zero at k=%d, converged\n", k);
        break;
      }
      CUDA_CHECK(cudaMemcpy(Q, bc, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      { Scalar inv_beta = 1.0/beta_rhs; CUBLAS_CHECK(cublasDscal(blas, n_c, &inv_beta, Q, 1)); }

      const Scalar one = 1.0, zero = 0.0;
      for (int j = 0; j < j_max; ++j) {
        CUBLAS_CHECK(cublasDgemv(blas, CUBLAS_OP_N, n_c, n_c, &one, S, n_c, Q + (size_t)j*n_c, 1, &zero, w, 1));
        Scalar alpha_j; CUBLAS_CHECK(cublasDdot(blas, n_c, Q + (size_t)j*n_c, 1, w, 1, &alpha_j));
        alpha_h[j] = alpha_j;
        { Scalar neg = -alpha_j; CUBLAS_CHECK(cublasDaxpy(blas, n_c, &neg, Q + (size_t)j*n_c, 1, w, 1)); }
        if (j > 0) { Scalar neg = -beta_h[j]; CUBLAS_CHECK(cublasDaxpy(blas, n_c, &neg, Q + (size_t)(j-1)*n_c, 1, w, 1)); }
        for (int jj = 0; jj <= j; ++jj) {
          Scalar dp; CUBLAS_CHECK(cublasDdot(blas, n_c, Q + (size_t)jj*n_c, 1, w, 1, &dp));
          Scalar neg = -dp; CUBLAS_CHECK(cublasDaxpy(blas, n_c, &neg, Q + (size_t)jj*n_c, 1, w, 1));
        }
        Scalar beta_next; CUBLAS_CHECK(cublasDnrm2(blas, n_c, w, 1, &beta_next));
        beta_h[j+1] = beta_next;
        m = j + 1;
        if (beta_next < 1e-12 * beta_rhs) break;
        if (j + 1 < j_max) {
          CUDA_CHECK(cudaMemcpy(Q + (size_t)(j+1)*n_c, w, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
          Scalar inv_beta = 1.0/beta_next; CUBLAS_CHECK(cublasDscal(blas, n_c, &inv_beta, Q + (size_t)(j+1)*n_c, 1));
        }
      }
      { std::vector<Scalar> a_tri(alpha_h.begin(), alpha_h.begin()+m);
        std::vector<Scalar> b_tri(m, 0.0); for (int i = 1; i < m; ++i) b_tri[i] = beta_h[i];
        TridiagExtremeEigenvalues(a_tri, b_tri, mu_min_est, mu_max_est);
      }

      Scalar best_cost = std::numeric_limits<Scalar>::infinity();
      for (int depth = 1; depth <= m; ++depth) {
        std::vector<std::vector<Scalar>> Mrows(depth+1, std::vector<Scalar>(depth, 0.0));
        for (int i = 0; i < depth; ++i) Mrows[i][i] = alpha_h[i];
        for (int i = 0; i < depth-1; ++i) { Mrows[i][i+1] = beta_h[i+1]; Mrows[i+1][i] = beta_h[i+1]; }
        Mrows[depth][depth-1] = beta_h[depth];
        std::vector<std::vector<Scalar>> G(depth, std::vector<Scalar>(depth, 0.0));
        std::vector<Scalar> rhs(depth, 0.0);
        for (int a = 0; a < depth; ++a) {
          for (int b = 0; b < depth; ++b) {
            Scalar sum = 0.0; for (int r = 0; r <= depth; ++r) sum += Mrows[r][a]*Mrows[r][b];
            G[a][b] = sum;
          }
          rhs[a] = beta_rhs * Mrows[0][a];
        }
        std::vector<Scalar> y = SolveSmallSPD(G, rhs);
        std::vector<Scalar> y_pad(m, 0.0);
        for (int i = 0; i < depth; ++i) y_pad[i] = y[i];
        CUDA_CHECK(cudaMemcpy(y_dev, y_pad.data(), m*sizeof(Scalar), cudaMemcpyHostToDevice));
        const Scalar one2 = 1.0, zero2 = 0.0;
        CUBLAS_CHECK(cublasDgemv(blas, CUBLAS_OP_N, n_c, m, &one2, Q, n_c, y_dev, 1, &zero2, xc, 1));

        KernelBackSubstituteSparse<<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                                            App_inv, grad_p, xc, npt, xp);
        CUDA_CHECK(cudaMemcpy(d, xc, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
        CUDA_CHECK(cudaMemcpy(d+n_c, xp, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));
        KernelNegateInPlace<<<GridSize(n),256>>>(d, n);

        Retract(p, s, d, s_cand);
        Scalar c = ComputeCost(p, s_cand);
        if (c < best_cost) { best_cost = c; best_depth = depth; CUDA_CHECK(cudaMemcpy(d_best, d, n*sizeof(Scalar), cudaMemcpyDeviceToDevice)); }
      }
      cost_new = best_cost;
    }

    if (cost_new >= cost) {
      if (verbose) std::printf("  OCA-CurvatureSwitch: no improving step found at k=%d (cost=%.6e)\n", k, cost);
      break;
    }
    lam_pt = std::max(lam_pt * 0.5, lam_pt0);
    if (used_exact) ++n_exact_used; else ++n_minres_used;

    Retract(p, s, d_best, s_cand);
    std::swap(s.R, s_cand.R); std::swap(s.t, s_cand.t); std::swap(s.X, s_cand.X);
    cost = cost_new;

    std::vector<Scalar> h_d(n);
    CUDA_CHECK(cudaMemcpy(h_d.data(), d_best, n*sizeof(Scalar), cudaMemcpyDeviceToHost));
    Scalar step_norm = 0.0; for (auto v : h_d) step_norm += v*v; step_norm = std::sqrt(step_norm);

    log.iters.push_back(k+1); log.costs.push_back(cost);
    if (verbose) {
      if (used_exact) std::printf("  OCA-CurvatureSwitch it%4d cost=%.6e mode=%-9s lam_pt=%.3e |d|=%.3e |grad|/|grad0|=%.3e\n",
                                    k+1, cost, mode, lam_pt, step_norm, grad_norm/grad_norm0);
      else std::printf("  OCA-CurvatureSwitch it%4d cost=%.6e mode=%-9s best_depth=%d/%d lam_pt=%.3e |d|=%.3e |grad|/|grad0|=%.3e mu_min(S)~%.3e\n",
                        k+1, cost, mode, best_depth, m, lam_pt, step_norm, grad_norm/grad_norm0, mu_min_est);
    }
    if (step_norm < tol && grad_norm < 1e-8 * grad_norm0) break;
  }
  if (verbose) std::printf("  OCA-CurvatureSwitch: exact-PD used %d/%d iterations, MINRES used %d/%d\n",
                            n_exact_used, (int)log.iters.size()-1, n_minres_used, (int)log.iters.size()-1);

  cublasDestroy(blas);
  cusolverDnDestroy(handle);
  cudaFree(Hcc); cudaFree(Hpp); cudaFree(obs_Hcp); cudaFree(grad_c); cudaFree(grad_p);
  cudaFree(App_inv); cudaFree(S); cudaFree(S_chol); cudaFree(bc); cudaFree(bc_corr); cudaFree(xc); cudaFree(xp);
  cudaFree(d); cudaFree(d_best); cudaFree(Q); cudaFree(w); cudaFree(y_dev); cudaFree(ok_flags);
  cudaFree(s_cand.R); cudaFree(s_cand.t); cudaFree(s_cand.X);
  return log;
}

// Stream-parallel version of SolveOCASchurSparseGNMultiLambda: the n_candidate
// lambda evaluations are INDEPENDENT (no data dependency between them within
// an outer iteration -- only the shared Hcc/Hpp/obs_Hcp/grad, computed once,
// feeds all of them), so instead of running them sequentially on one stream
// (the ~5x overhead measured earlier), each candidate gets its own CUDA
// stream + cuSOLVER handle + full set of scratch buffers, and all n_candidate
// factorizations + growing recursions are LAUNCHED without synchronizing
// between them -- true concurrent execution on the GPU (not just concurrent
// *issue*), limited only by how much of the device a single candidate's work
// already occupies. Two simplifications vs the sequential version, both
// specific to Gauss-Newton: (1) the per-candidate PD checks are skipped
// entirely -- Hpp+lam*I and its Schur complement S are mathematically
// guaranteed PD for lam>0 with a PSD Gauss-Newton Hessian, unlike the
// true-Hessian variants that genuinely need the check -- replaced by a single
// batched devInfo readback after all candidates are launched, so a real
// failure (should never happen) is still caught, just without a per-candidate
// blocking round-trip that would have serialized the streams; (2) the
// host-side negation used elsewhere in this file (round-trips the full
// solution vector through host memory to flip its sign) is replaced by
// KernelNegateInPlace, an on-device kernel -- ANY host round-trip
// (cudaMemcpy, not cudaMemcpyAsync) blocks the whole device regardless of
// which stream issued the preceding work, so removing it is required for
// the streams to actually run concurrently, not just look like they might.
RunLog SolveOCASchurSparseGNMultiLambdaParallel(const DeviceProblem& p, DeviceState& s, Scalar lam0, Scalar tol,
                                                 int max_iter, bool verbose, int n_candidates = 5,
                                                 Scalar decade_span = 1.0, int max_escalations = 25) {
  int ncam = p.ncam, npt = p.npt, n_c = 6*ncam, n_p = 3*npt, n = n_c + n_p;
  Scalar *Hcc, *Hpp, *obs_Hcp, *grad_c, *grad_p;
  CUDA_CHECK(cudaMalloc(&Hcc, 36*(size_t)ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&Hpp, 9*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&obs_Hcp, 18*(size_t)p.nobs*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&grad_c, 6*(size_t)ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&grad_p, 3*(size_t)npt*sizeof(Scalar)));

  // per-candidate: own stream, own cuSOLVER handle bound to that stream, own
  // full set of scratch buffers (App_inv/S/the growing-recursion vectors/d),
  // and a shared (but per-candidate-indexed) Cholesky devInfo/workspace.
  std::vector<cudaStream_t> stream(n_candidates);
  std::vector<cusolverDnHandle_t> solver(n_candidates);
  std::vector<Scalar*> App_inv(n_candidates), S(n_candidates), bc_corr(n_candidates), bc_prime(n_candidates),
      xc(n_candidates), xp(n_candidates), gc_prev(n_candidates), gp_prev(n_candidates),
      bp_j(n_candidates), bc_j(n_candidates), d(n_candidates), cho_work(n_candidates);
  std::vector<int*> ok_flags(n_candidates);   // per-candidate: KernelInvertAppBlocks writes it, but we never read it (PD guaranteed for GN, checked via d_info instead) -- still one-per-candidate to avoid concurrent writes to shared memory across streams
  std::vector<int> cho_lwork(n_candidates);
  int* d_info_all;  // one contiguous array, size n_candidates -- ONE batched readback after sync, not N blocking ones
  CUDA_CHECK(cudaMalloc(&d_info_all, n_candidates*sizeof(int)));

  for (int i = 0; i < n_candidates; ++i) {
    CUDA_CHECK(cudaStreamCreate(&stream[i]));
    cusolverDnCreate(&solver[i]);
    cusolverDnSetStream(solver[i], stream[i]);
    CUDA_CHECK(cudaMalloc(&App_inv[i], 9*(size_t)npt*sizeof(Scalar)));
    CUDA_CHECK(cudaMalloc(&S[i], (size_t)n_c*n_c*sizeof(Scalar)));
    CUDA_CHECK(cudaMalloc(&bc_corr[i], n_c*sizeof(Scalar)));
    CUDA_CHECK(cudaMalloc(&bc_prime[i], n_c*sizeof(Scalar)));
    CUDA_CHECK(cudaMalloc(&xc[i], n_c*sizeof(Scalar)));
    CUDA_CHECK(cudaMalloc(&xp[i], n_p*sizeof(Scalar)));
    CUDA_CHECK(cudaMalloc(&gc_prev[i], n_c*sizeof(Scalar)));
    CUDA_CHECK(cudaMalloc(&gp_prev[i], n_p*sizeof(Scalar)));
    CUDA_CHECK(cudaMalloc(&bp_j[i], n_p*sizeof(Scalar)));
    CUDA_CHECK(cudaMalloc(&bc_j[i], n_c*sizeof(Scalar)));
    CUDA_CHECK(cudaMalloc(&d[i], n*sizeof(Scalar)));
    CUDA_CHECK(cudaMalloc(&ok_flags[i], npt*sizeof(int)));
    CUSOLVER_CHECK(cusolverDnDpotrf_bufferSize(solver[i], CUBLAS_FILL_MODE_LOWER, n_c, nullptr, n_c, &cho_lwork[i]));
    CUDA_CHECK(cudaMalloc(&cho_work[i], cho_lwork[i]*sizeof(Scalar)));
  }

  Scalar* d_best; CUDA_CHECK(cudaMalloc(&d_best, n*sizeof(Scalar)));
  DeviceState s_new; AllocState(s_new, ncam, npt);

  Scalar cost = ComputeCost(p, s);
  RunLog log; log.iters.push_back(0); log.costs.push_back(cost);
  Scalar lam_center = lam0;
  Scalar grad_norm0 = -1.0;   // captured at k=0 -- see the grad-norm convergence check below (same fix as the sequential version, ported after the same failure mode on ladybug-598)

  // Launches candidate i's ENTIRE factorize+growing-recursion+negate sequence
  // on stream[i], with NO synchronization inside -- returns immediately after
  // issuing the work, letting the caller launch the next candidate's work
  // before this one has actually finished on the GPU.
  auto launch_candidate = [&](int i, int k, Scalar lam_val) {
    cudaStream_t st = stream[i];
    KernelInvertAppBlocks<<<GridSize(npt),256,0,st>>>(Hpp, lam_val, App_inv[i], ok_flags[i], npt);
    CUDA_CHECK(cudaMemsetAsync(S[i], 0, (size_t)n_c*n_c*sizeof(Scalar), st));
    KernelBuildAccFull<<<GridSize(ncam),256,0,st>>>(Hcc, lam_val, S[i], ncam, n_c);
    KernelFormSSparse<<<GridSize(npt),256,0,st>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                                   App_inv[i], npt, n_c, S[i]);
    CUSOLVER_CHECK(cusolverDnDpotrf(solver[i], CUBLAS_FILL_MODE_LOWER, n_c, S[i], n_c,
                                     cho_work[i], cho_lwork[i], d_info_all + i));

    CUDA_CHECK(cudaMemsetAsync(gc_prev[i], 0, n_c*sizeof(Scalar), st));
    for (int j = 0; j <= k; ++j) {
      CUDA_CHECK(cudaMemcpyAsync(bp_j[i], grad_p, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice, st));
      CUDA_CHECK(cudaMemcpyAsync(bc_j[i], grad_c, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice, st));
      if (j > 0) {
        KernelAxpy<<<GridSize(n_p),256,0,st>>>(bp_j[i], gp_prev[i], lam_val, n_p);
        KernelAxpy<<<GridSize(n_c),256,0,st>>>(bc_j[i], gc_prev[i], lam_val, n_c);
      }
      CUDA_CHECK(cudaMemsetAsync(bc_corr[i], 0, n_c*sizeof(Scalar), st));
      KernelRHSCorrectionSparse<<<GridSize(npt),256,0,st>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                                             App_inv[i], bp_j[i], npt, bc_corr[i]);
      KernelSubtractVec<<<GridSize(n_c),256,0,st>>>(bc_prime[i], bc_j[i], bc_corr[i], n_c);
      CUDA_CHECK(cudaMemcpyAsync(xc[i], bc_prime[i], n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice, st));
      CUSOLVER_CHECK(cusolverDnDpotrs(solver[i], CUBLAS_FILL_MODE_LOWER, n_c, 1, S[i], n_c, xc[i], n_c, d_info_all + i));
      KernelBackSubstituteSparse<<<GridSize(npt),256,0,st>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                                              App_inv[i], bp_j[i], xc[i], npt, xp[i]);
      CUDA_CHECK(cudaMemcpyAsync(gc_prev[i], xc[i], n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice, st));
      CUDA_CHECK(cudaMemcpyAsync(gp_prev[i], xp[i], n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice, st));
    }
    CUDA_CHECK(cudaMemcpyAsync(d[i], gc_prev[i], n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice, st));
    CUDA_CHECK(cudaMemcpyAsync(d[i]+n_c, gp_prev[i], n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice, st));
    KernelNegateInPlace<<<GridSize(n),256,0,st>>>(d[i], n);
  };

  for (int k = 0; k < max_iter; ++k) {
    CUDA_CHECK(cudaMemset(Hcc, 0, 36*(size_t)ncam*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(Hpp, 0, 9*(size_t)npt*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(grad_c, 0, 6*(size_t)ncam*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(grad_p, 0, 3*(size_t)npt*sizeof(Scalar)));
    KernelAssembleSchurSparseGN<<<GridSize(p.nobs),256>>>(
        p.cam_idx, p.pt_idx, p.uv, s.R, s.t, s.X, p.f, p.k1, p.k2, p.nobs,
        Hcc, Hpp, obs_Hcp, grad_c, grad_p);
    CUDA_CHECK(cudaDeviceSynchronize());  // shared inputs must be complete before any candidate stream reads them

    Scalar grad_norm;
    { std::vector<Scalar> h_grad_full(n);
      CUDA_CHECK(cudaMemcpy(h_grad_full.data(), grad_c, n_c*sizeof(Scalar), cudaMemcpyDeviceToHost));
      CUDA_CHECK(cudaMemcpy(h_grad_full.data()+n_c, grad_p, n_p*sizeof(Scalar), cudaMemcpyDeviceToHost));
      Scalar s2 = 0.0; for (auto v : h_grad_full) s2 += v*v;
      grad_norm = std::sqrt(s2);
    }
    if (grad_norm0 < 0.0) grad_norm0 = std::max(grad_norm, (Scalar)1e-300);

    Scalar cost_current = cost, cost_best = std::numeric_limits<Scalar>::infinity(), lam_best = lam_center;
    int n_esc = 0;
    for (;; ++n_esc) {
      std::vector<Scalar> lam_val(n_candidates);
      for (int i = 0; i < n_candidates; ++i) {
        Scalar frac = n_candidates > 1 ? (Scalar)i / (n_candidates - 1) : 0.5;
        Scalar exponent = -decade_span + 2.0 * decade_span * frac;
        lam_val[i] = lam_center * std::pow((Scalar)10.0, exponent);
        launch_candidate(i, k, lam_val[i]);   // issued, not waited on -- next i starts immediately
      }
      CUDA_CHECK(cudaDeviceSynchronize());    // ONE sync point for all n_candidates, not one per candidate

      std::vector<int> h_info(n_candidates);
      CUDA_CHECK(cudaMemcpy(h_info.data(), d_info_all, n_candidates*sizeof(int), cudaMemcpyDeviceToHost));
      for (int i = 0; i < n_candidates; ++i) {
        if (h_info[i] != 0) {
          std::fprintf(stderr, "OCA-GN-ML-parallel: candidate %d (lam=%.4g) not PD at k=%d -- should never "
                                "happen for GN, indicates lam<=0 or a real bug\n", i, lam_val[i], k);
          std::exit(EXIT_FAILURE);
        }
      }

      cost_best = std::numeric_limits<Scalar>::infinity();
      for (int i = 0; i < n_candidates; ++i) {
        Retract(p, s, d[i], s_new);
        Scalar c = ComputeCost(p, s_new);
        if (c < cost_best) { cost_best = c; lam_best = lam_val[i]; CUDA_CHECK(cudaMemcpy(d_best, d[i], n*sizeof(Scalar), cudaMemcpyDeviceToDevice)); }
      }
      if (cost_best < cost_current || n_esc >= max_escalations) break;
      lam_center *= 10.0;
    }

    if (cost_best >= cost_current) {
      if (verbose) std::printf("  OCA-GN-ML-par: converged / no improving lambda found at k=%d (cost=%.6e)\n", k, cost);
      break;
    }
    lam_center = std::max(lam_best * 0.5, lam0 * 1e-8);

    Retract(p, s, d_best, s_new);
    std::swap(s.R, s_new.R); std::swap(s.t, s_new.t); std::swap(s.X, s_new.X);
    cost = cost_best;

    std::vector<Scalar> h_d(n);
    CUDA_CHECK(cudaMemcpy(h_d.data(), d_best, n*sizeof(Scalar), cudaMemcpyDeviceToHost));
    Scalar step_norm = 0.0; for (auto v : h_d) step_norm += v*v; step_norm = std::sqrt(step_norm);

    log.iters.push_back(k+1); log.costs.push_back(cost);
    if (verbose) std::printf("  OCA-GN-ML-par it%4d cost=%.6e |d|=%.3e lam_best=%.3e n_esc=%d |grad|/|grad0|=%.3e\n",
                              k+1, cost, step_norm, lam_best, n_esc, grad_norm/grad_norm0);
    if (step_norm < tol && grad_norm < 1e-8 * grad_norm0) break;
  }

  for (int i = 0; i < n_candidates; ++i) {
    cusolverDnDestroy(solver[i]); cudaStreamDestroy(stream[i]);
    cudaFree(App_inv[i]); cudaFree(S[i]); cudaFree(bc_corr[i]); cudaFree(bc_prime[i]);
    cudaFree(xc[i]); cudaFree(xp[i]); cudaFree(gc_prev[i]); cudaFree(gp_prev[i]);
    cudaFree(bp_j[i]); cudaFree(bc_j[i]); cudaFree(d[i]); cudaFree(cho_work[i]); cudaFree(ok_flags[i]);
  }
  cudaFree(Hcc); cudaFree(Hpp); cudaFree(obs_Hcp); cudaFree(grad_c); cudaFree(grad_p);
  cudaFree(d_info_all); cudaFree(d_best);
  cudaFree(s_new.R); cudaFree(s_new.t); cudaFree(s_new.X);
  return log;
}

RunLog SolveOCAAdaptiveSchurSparse(const DeviceProblem& p, DeviceState& s, Scalar lam0, Scalar lam1,
                                    Scalar tol, int max_iter, bool verbose) {
  int ncam = p.ncam, npt = p.npt, n_c = 6*ncam, n_p = 3*npt, n = n_c + n_p;
  Scalar *Hcc, *Hpp, *obs_Hcp, *grad_c, *grad_p, *App_inv, *S;
  Scalar *bc_corr, *bc_prime, *xc, *xp, *g_k_c, *g_k_p, *g_c_c, *g_c_p, *bp_j, *bc_j, *d;
  int* ok_flags;
  CUDA_CHECK(cudaMalloc(&Hcc, 36*(size_t)ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&Hpp, 9*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&obs_Hcp, 18*(size_t)p.nobs*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&grad_c, 6*(size_t)ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&grad_p, 3*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&App_inv, 9*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&S, (size_t)n_c*n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bc_corr, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bc_prime, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&xc, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&xp, n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&g_k_c, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&g_k_p, n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&g_c_c, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&g_c_p, n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bp_j, n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bc_j, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&d, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&ok_flags, npt*sizeof(int)));
  DeviceState s_new; AllocState(s_new, ncam, npt);
  DeviceState s_tmp; AllocState(s_tmp, ncam, npt);

  cusolverDnHandle_t handle; cusolverDnCreate(&handle);
  CholeskyWorkspace ws; ws.Init(handle, n_c);

  // returns ok; writes the k+1-step inner recursion result into (out_c,out_p)
  auto inner_solve = [&](Scalar lam_val, int k, Scalar* out_c, Scalar* out_p) -> bool {
    CUDA_CHECK(cudaMemset(S, 0, (size_t)n_c*n_c*sizeof(Scalar)));
    KernelBuildAccFull<<<GridSize(ncam),256>>>(Hcc, lam_val, S, ncam, n_c);
    KernelFormSSparse<<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                              App_inv, npt, n_c, S);
    // App_inv was computed at the CALLER's lam_val (see below) -- recompute here for this specific lam_val
    { std::vector<int> h_ok(npt);
      CUDA_CHECK(cudaMemcpy(h_ok.data(), ok_flags, npt*sizeof(int), cudaMemcpyDeviceToHost));
      for (int v : h_ok) if (!v) return false;
    }
    if (!CholeskyFactor(ws, S)) return false;
    CUDA_CHECK(cudaMemset(g_k_c, 0, n_c*sizeof(Scalar)));  // gc_prev = 0 for j=0
    for (int j = 0; j <= k; ++j) {
      CUDA_CHECK(cudaMemcpy(bp_j, grad_p, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      CUDA_CHECK(cudaMemcpy(bc_j, grad_c, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      if (j > 0) {
        KernelAxpy<<<GridSize(n_p),256>>>(bp_j, out_p, lam_val, n_p);
        KernelAxpy<<<GridSize(n_c),256>>>(bc_j, out_c, lam_val, n_c);
      }
      CUDA_CHECK(cudaMemset(bc_corr, 0, n_c*sizeof(Scalar)));
      KernelRHSCorrectionSparse<<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                                         App_inv, bp_j, npt, bc_corr);
      KernelSubtractVec<<<GridSize(n_c),256>>>(bc_prime, bc_j, bc_corr, n_c);
      CUDA_CHECK(cudaMemcpy(out_c, bc_prime, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      CholeskySolveVec(ws, S, out_c);
      KernelBackSubstituteSparse<<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                                          App_inv, bp_j, out_c, npt, out_p);
    }
    return true;
  };
  auto invert_app_for_lam = [&](Scalar lam_val) -> bool {
    KernelInvertAppBlocks<<<GridSize(npt),256>>>(Hpp, lam_val, App_inv, ok_flags, npt);
    std::vector<int> h_ok(npt);
    CUDA_CHECK(cudaMemcpy(h_ok.data(), ok_flags, npt*sizeof(int), cudaMemcpyDeviceToHost));
    for (int v : h_ok) if (!v) return false;
    return true;
  };

  Scalar cost = ComputeCost(p, s);
  RunLog log; log.iters.push_back(0); log.costs.push_back(cost);
  Scalar lam_prev = lam0;

  for (int k = 0; k < max_iter; ++k) {
    CUDA_CHECK(cudaMemset(Hcc, 0, 36*(size_t)ncam*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(Hpp, 0, 9*(size_t)npt*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(grad_c, 0, 6*(size_t)ncam*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(grad_p, 0, 3*(size_t)npt*sizeof(Scalar)));
    KernelAssembleSchurSparse<<<GridSize(p.nobs),256>>>(
        p.cam_idx, p.pt_idx, p.uv, s.R, s.t, s.X, p.f, p.k1, p.k2, p.nobs,
        Hcc, Hpp, obs_Hcp, grad_c, grad_p);

    Scalar lam_k;
    if (k <= 1) {
      lam_k = (k == 0) ? lam0 : lam1;
      if (!invert_app_for_lam(lam_k) || !inner_solve(lam_k, k, g_k_c, g_k_p)) {
        std::fprintf(stderr, "OCA-Schur-sparse-adaptive: (R+H) indefinite at k=%d with fixed lam=%.4g\n", k, lam_k);
        std::exit(EXIT_FAILURE);
      }
    } else {
      // Robustness fix (not in the literal Algorithm 3 pseudocode -- see
      // reference_oca_schur_sparse.py's matching fix for the full rationale):
      // Algorithm 3 has no step-rejection gate, so an accepted worse step can
      // leave the Hessian more indefinite than lam_prev covers; the paper's
      // bisection only ever searches DOWNWARD from lam_prev and has no way to
      // recover from that. Escalate lam upward until PD is restored, then
      // bisect downward from THAT -- a no-op whenever lam_prev already works
      // (verified to reproduce the exact original trajectory on the toy
      // problem, where this never triggers).
      Scalar lam_start = lam_prev;
      bool ok0 = invert_app_for_lam(lam_start) && inner_solve(lam_start, k, g_k_c, g_k_p);
      if (!ok0) {
        for (int esc = 0; esc < 30 && !ok0; ++esc) {
          lam_start *= 2.0;
          ok0 = invert_app_for_lam(lam_start) && inner_solve(lam_start, k, g_k_c, g_k_p);
        }
        if (!ok0) {
          std::fprintf(stderr, "OCA-Schur-sparse-adaptive: (R+H) indefinite at k=%d even after "
                                "escalating lam up to %.4g\n", k, lam_start);
          std::exit(EXIT_FAILURE);
        }
      }
      lam_k = lam_start;
      CUDA_CHECK(cudaMemcpy(d, g_k_c, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      CUDA_CHECK(cudaMemcpy(d+n_c, g_k_p, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      { std::vector<Scalar> tmp(n); CUDA_CHECK(cudaMemcpy(tmp.data(), d, n*sizeof(Scalar), cudaMemcpyDeviceToHost));
        for (auto& v : tmp) v = -v; CUDA_CHECK(cudaMemcpy(d, tmp.data(), n*sizeof(Scalar), cudaMemcpyHostToDevice)); }
      DeviceState s_step; AllocState(s_step, ncam, npt);
      Retract(p, s, d, s_step);
      Scalar cost1 = ComputeCost(p, s_step);
      cudaFree(s_step.R); cudaFree(s_step.t); cudaFree(s_step.X);

      Scalar a = 0.0, b = lam_start, c = b;
      while ((b - a) > 0.1) {
        c = (a + b) / 2.0;
        bool ok_c = invert_app_for_lam(c) && inner_solve(c, k, g_c_c, g_c_p);
        Scalar cost2 = std::numeric_limits<Scalar>::infinity();
        if (ok_c) {
          CUDA_CHECK(cudaMemcpy(d, g_c_c, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
          CUDA_CHECK(cudaMemcpy(d+n_c, g_c_p, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));
          std::vector<Scalar> tmp(n); CUDA_CHECK(cudaMemcpy(tmp.data(), d, n*sizeof(Scalar), cudaMemcpyDeviceToHost));
          for (auto& v : tmp) v = -v; CUDA_CHECK(cudaMemcpy(d, tmp.data(), n*sizeof(Scalar), cudaMemcpyHostToDevice));
          DeviceState s_step2; AllocState(s_step2, ncam, npt);
          Retract(p, s, d, s_step2);
          cost2 = ComputeCost(p, s_step2);
          cudaFree(s_step2.R); cudaFree(s_step2.t); cudaFree(s_step2.X);
        }
        if (!ok_c) { a = c; continue; }
        if (cost1 > cost2) {
          b = c; cost1 = cost2;
          CUDA_CHECK(cudaMemcpy(g_k_c, g_c_c, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
          CUDA_CHECK(cudaMemcpy(g_k_p, g_c_p, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));
        } else if (cost1 < cost2) {
          a = c; cost1 = cost2;
          CUDA_CHECK(cudaMemcpy(g_k_c, g_c_c, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
          CUDA_CHECK(cudaMemcpy(g_k_p, g_c_p, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));
        } else break;
      }
      if ((b - a) <= 0.1) lam_k = c;
    }

    // Step-rejection gate (not in the literal Algorithm 1/2/3 pseudocode --
    // see reference_oca_schur_sparse.py's matching fix for the full
    // rationale). Distinct from the lam-escalation fix above (which only
    // handles "no candidate lam is PD"): this handles "a PD candidate exists
    // but doesn't actually reduce cost" -- real BAL data can make the
    // bisection's best candidate still worse than the pre-step cost (seen on
    // venice-52: 1.6M -> 8.4B -> 1.9e20 over two unrejected iterations). If
    // the chosen step doesn't improve cost, grow lam and retry. A no-op
    // whenever the chosen step already improves cost (verified: no change on
    // the toy problem, where this never triggers).
    Scalar cost_new;
    for (int attempt = 0;; ++attempt) {
      CUDA_CHECK(cudaMemcpy(d, g_k_c, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      CUDA_CHECK(cudaMemcpy(d+n_c, g_k_p, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      { std::vector<Scalar> tmp(n); CUDA_CHECK(cudaMemcpy(tmp.data(), d, n*sizeof(Scalar), cudaMemcpyDeviceToHost));
        for (auto& v : tmp) v = -v; CUDA_CHECK(cudaMemcpy(d, tmp.data(), n*sizeof(Scalar), cudaMemcpyHostToDevice)); }
      Retract(p, s, d, s_new);
      cost_new = ComputeCost(p, s_new);
      if (cost_new <= cost || attempt >= 20) break;
      lam_k *= 10.0;
      bool ok_retry = invert_app_for_lam(lam_k) && inner_solve(lam_k, k, g_k_c, g_k_p);
      if (!ok_retry) {
        for (int esc = 0; esc < 30 && !ok_retry; ++esc) {
          lam_k *= 2.0;
          ok_retry = invert_app_for_lam(lam_k) && inner_solve(lam_k, k, g_k_c, g_k_p);
        }
        if (!ok_retry) {
          std::fprintf(stderr, "OCA-Schur-sparse-adaptive: (R+H) indefinite at k=%d even after "
                                "growing lam to %.4g during step-rejection retry\n", k, lam_k);
          std::exit(EXIT_FAILURE);
        }
      }
    }

    std::swap(s.R, s_new.R); std::swap(s.t, s_new.t); std::swap(s.X, s_new.X);
    cost = cost_new;
    lam_prev = lam_k;

    std::vector<Scalar> h_d(n);
    CUDA_CHECK(cudaMemcpy(h_d.data(), d, n*sizeof(Scalar), cudaMemcpyDeviceToHost));
    Scalar step_norm = 0.0; for (auto v : h_d) step_norm += v*v; step_norm = std::sqrt(step_norm);

    log.iters.push_back(k+1); log.costs.push_back(cost);
    if (verbose) std::printf("  OCA-Schur-sparse-adapt it%4d cost=%.6e lam=%.3e |d|=%.3e\n", k+1, cost, lam_k, step_norm);
    if (step_norm < tol) break;
  }

  cusolverDnDestroy(handle);
  cudaFree(Hcc); cudaFree(Hpp); cudaFree(obs_Hcp); cudaFree(grad_c); cudaFree(grad_p);
  cudaFree(App_inv); cudaFree(S); cudaFree(bc_corr); cudaFree(bc_prime); cudaFree(xc); cudaFree(xp);
  cudaFree(g_k_c); cudaFree(g_k_p); cudaFree(g_c_c); cudaFree(g_c_p); cudaFree(bp_j); cudaFree(bc_j);
  cudaFree(d); cudaFree(ok_flags);
  cudaFree(s_new.R); cudaFree(s_new.t); cudaFree(s_new.X);
  cudaFree(s_tmp.R); cudaFree(s_tmp.t); cudaFree(s_tmp.X);
  return log;
}

// ============================================================== Algorithm 1: LM via sparse per-point Schur (Phase 4c)
// LM's Gauss-Newton Hessian (J^T J, Eq.2) has the exact same block-sparsity as
// OCA's true Hessian, so the same sparse-Schur machinery applies -- the only
// differences from SolveOCASchurSparse are: (1) assembly uses
// KernelAssembleSchurSparseGN (drops the residual-curvature term), (2) a
// single Schur solve per outer iteration (no growing inner recursion -- LM
// has no analogue of OCA's g_0..g_k), (3) mu is adapted via the trust-region
// ratio xi (Eq.3-4) instead of being fixed or bisected, and (4) the step is
// ALWAYS accepted (matches Algorithm 1 exactly, same as the dense SolveLM
// above -- no rejection gate).
RunLog SolveLMSchurSparse(const DeviceProblem& p, DeviceState& s, Scalar mu0, Scalar tol, int max_iter, bool verbose,
                           Scalar grad_tol_rel = 1e-8) {
  int ncam = p.ncam, npt = p.npt, n_c = 6*ncam, n_p = 3*npt, n = n_c + n_p;
  Scalar *Hcc, *Hpp, *obs_Hcp, *grad_c, *grad_p, *App_inv, *S;
  Scalar *bc_corr, *bc_prime, *xc, *xp, *d, *jd_sum;
  int* ok_flags;
  CUDA_CHECK(cudaMalloc(&Hcc, 36*(size_t)ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&Hpp, 9*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&obs_Hcp, 18*(size_t)p.nobs*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&grad_c, 6*(size_t)ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&grad_p, 3*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&App_inv, 9*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&S, (size_t)n_c*n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bc_corr, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bc_prime, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&xc, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&xp, n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&d, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&jd_sum, sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&ok_flags, npt*sizeof(int)));
  DeviceState s_new; AllocState(s_new, ncam, npt);

  cusolverDnHandle_t handle; cusolverDnCreate(&handle);
  CholeskyWorkspace ws; ws.Init(handle, n_c);

  Scalar mu = mu0;
  Scalar cost = ComputeCost(p, s);
  RunLog log; log.iters.push_back(0); log.costs.push_back(cost);
  Scalar grad_norm0 = -1.0;  // captured at k=0, used to scale the gradient-norm convergence check

  for (int k = 0; k < max_iter; ++k) {
    CUDA_CHECK(cudaMemset(Hcc, 0, 36*(size_t)ncam*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(Hpp, 0, 9*(size_t)npt*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(grad_c, 0, 6*(size_t)ncam*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(grad_p, 0, 3*(size_t)npt*sizeof(Scalar)));
    KernelAssembleSchurSparseGN<<<GridSize(p.nobs),256>>>(
        p.cam_idx, p.pt_idx, p.uv, s.R, s.t, s.X, p.f, p.k1, p.k2, p.nobs,
        Hcc, Hpp, obs_Hcp, grad_c, grad_p);

    // Gradient-norm convergence signal (independent of mu): a step forced tiny by an
    // artificially huge mu (see below) has step_norm~0 even when the true gradient is
    // still large -- ladybug-598 showed this exactly (mu escalated to ~1e14 to
    // numerically stabilize one poorly-scaled block, forcing a ~2e-7 step that
    // satisfied step_norm<tol after a SINGLE outer iteration, while the achievable
    // cost was still ~23x higher than what per-block-damped OCA reached from the same
    // start). step_norm alone is a well-known-insufficient stopping criterion in
    // exactly this situation (a classic pitfall, not specific to this codebase) --
    // gradient norm isn't affected by mu at all, so it's the correct cross-check.
    // Scaled by the INITIAL gradient norm (captured once, at k=0) rather than an
    // absolute threshold, since raw gradient magnitude varies hugely across datasets
    // (toy synthetic vs. real BAL scale/units).
    Scalar grad_norm;
    { std::vector<Scalar> h_grad_full(n);
      CUDA_CHECK(cudaMemcpy(h_grad_full.data(), grad_c, n_c*sizeof(Scalar), cudaMemcpyDeviceToHost));
      CUDA_CHECK(cudaMemcpy(h_grad_full.data()+n_c, grad_p, n_p*sizeof(Scalar), cudaMemcpyDeviceToHost));
      Scalar s2 = 0.0; for (auto v : h_grad_full) s2 += v*v;
      grad_norm = std::sqrt(s2);
    }
    if (grad_norm0 < 0.0) grad_norm0 = std::max(grad_norm, (Scalar)1e-300);

    // Step-rejection gate (not in the literal Algorithm 1 pseudocode, which
    // ALWAYS accepts x_{k+1}=x_k+d_k -- see reference_oca_schur_sparse.py's
    // matching OCA fix for the full rationale; applied here too since venice-52
    // showed literal LM oscillating by orders of magnitude and eventually
    // crashing, the same root cause OCA-adaptive had, for a fair comparison).
    // GN's H_gn=J^T J is always PSD, so mu*I>0 keeps (Hpp+mu*I) and S positive
    // definite in EXACT arithmetic -- but venice-89 showed that when mu shrinks
    // small enough (a long run of improving steps), floating-point round-off in
    // forming S can push it to fail Cholesky in practice despite being
    // theoretically PD. Treat that the same as a rejected step (grow mu, retry)
    // rather than crashing -- it's a numerical-precision issue, not a sign the
    // step was actually bad.
    Scalar cost_new, xi = 0.0, step_norm = 0.0;
    for (int attempt = 0;; ++attempt) {
      KernelInvertAppBlocks<<<GridSize(npt),256>>>(Hpp, mu, App_inv, ok_flags, npt);
      bool pd_ok = true;
      { std::vector<int> h_ok(npt);
        CUDA_CHECK(cudaMemcpy(h_ok.data(), ok_flags, npt*sizeof(int), cudaMemcpyDeviceToHost));
        for (int v : h_ok) if (!v) pd_ok = false;
      }
      if (pd_ok) {
        CUDA_CHECK(cudaMemset(S, 0, (size_t)n_c*n_c*sizeof(Scalar)));
        KernelBuildAccFull<<<GridSize(ncam),256>>>(Hcc, mu, S, ncam, n_c);
        KernelFormSSparse<<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                                  App_inv, npt, n_c, S);
        pd_ok = CholeskyFactor(ws, S);
      }
      if (!pd_ok) {
        if (attempt >= 30) {
          std::fprintf(stderr, "LM-Schur-sparse: (Hpp+mu*I)/S not PD at k=%d even after growing mu to %.4g\n", k, mu);
          std::exit(EXIT_FAILURE);
        }
        mu *= 10.0;
        continue;
      }
      CUDA_CHECK(cudaMemset(bc_corr, 0, n_c*sizeof(Scalar)));
      KernelRHSCorrectionSparse<<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                                         App_inv, grad_p, npt, bc_corr);
      KernelSubtractVec<<<GridSize(n_c),256>>>(bc_prime, grad_c, bc_corr, n_c);
      CUDA_CHECK(cudaMemcpy(xc, bc_prime, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      CholeskySolveVec(ws, S, xc);
      KernelBackSubstituteSparse<<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                                          App_inv, grad_p, xc, npt, xp);
      CUDA_CHECK(cudaMemcpy(d, xc, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      CUDA_CHECK(cudaMemcpy(d+n_c, xp, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      { std::vector<Scalar> tmp(n);
        CUDA_CHECK(cudaMemcpy(tmp.data(), d, n*sizeof(Scalar), cudaMemcpyDeviceToHost));
        for (auto& v : tmp) v = -v;
        CUDA_CHECK(cudaMemcpy(d, tmp.data(), n*sizeof(Scalar), cudaMemcpyHostToDevice));
      }

      Retract(p, s, d, s_new);
      cost_new = ComputeCost(p, s_new);

      // predicted decrease: -(grad.d + 0.5*d^T H_gn d), d^T H_gn d = ||J d||^2 via KernelJdSquaredSum
      CUDA_CHECK(cudaMemset(jd_sum, 0, sizeof(Scalar)));
      KernelJdSquaredSum<<<GridSize(p.nobs),256>>>(p.cam_idx, p.pt_idx, p.uv, s.R, s.t, s.X, p.f, p.k1, p.k2,
                                                    d, p.nobs, ncam, jd_sum);
      Scalar quad; CUDA_CHECK(cudaMemcpy(&quad, jd_sum, sizeof(Scalar), cudaMemcpyDeviceToHost));
      std::vector<Scalar> h_grad(n), h_d(n);
      CUDA_CHECK(cudaMemcpy(h_grad.data(), grad_c, n_c*sizeof(Scalar), cudaMemcpyDeviceToHost));
      CUDA_CHECK(cudaMemcpy(h_grad.data()+n_c, grad_p, n_p*sizeof(Scalar), cudaMemcpyDeviceToHost));
      CUDA_CHECK(cudaMemcpy(h_d.data(), d, n*sizeof(Scalar), cudaMemcpyDeviceToHost));
      Scalar grad_dot_d = 0.0; for (int i = 0; i < n; ++i) grad_dot_d += h_grad[i]*h_d[i];
      Scalar pred_decrease = -(grad_dot_d + 0.5*quad);
      Scalar actual_decrease = cost - cost_new;
      xi = (std::fabs(pred_decrease) > 1e-300) ? actual_decrease/pred_decrease : 0.0;
      step_norm = 0.0; for (auto v : h_d) step_norm += v*v; step_norm = std::sqrt(step_norm);

      if (cost_new <= cost || attempt >= 20) break;
      mu *= 10.0;  // reject: this step made things worse, grow mu and retry
    }

    std::swap(s.R, s_new.R); std::swap(s.t, s_new.t); std::swap(s.X, s_new.X);
    cost = cost_new;
    if (xi < 0.25) mu *= 10.0; else if (xi > 0.75) mu *= 0.1;

    log.iters.push_back(k+1); log.costs.push_back(cost);
    if (verbose) std::printf("  LM-Schur-sparse it%4d cost=%.6e mu=%.3e xi=%.3f |d|=%.3e |grad|/|grad0|=%.3e |grad|=%.6e\n",
                              k+1, cost, mu, xi, step_norm, grad_norm/grad_norm0, grad_norm);
    if (step_norm < tol && grad_norm < grad_tol_rel * grad_norm0) break;
  }

  cusolverDnDestroy(handle);
  cudaFree(Hcc); cudaFree(Hpp); cudaFree(obs_Hcp); cudaFree(grad_c); cudaFree(grad_p);
  cudaFree(App_inv); cudaFree(S); cudaFree(bc_corr); cudaFree(bc_prime); cudaFree(xc); cudaFree(xp);
  cudaFree(d); cudaFree(jd_sum); cudaFree(ok_flags);
  cudaFree(s_new.R); cudaFree(s_new.t); cudaFree(s_new.X);
  return log;
}

// ============================================================== Task: Anderson Acceleration wrapping the outer LM/GN step (numpy-validated
// first: on ladybug-49, AA(m=2) reached the exact known global optimum in
// 60 iterations vs plain LM-GN's 16,540; on ladybug-598, AA(m=2) reached
// 302,959 vs plain's 571,197 at a matched 60-iteration budget -- both a
// dramatically bigger win than outer Nesterov's 1-2%, at roughly the same
// per-iteration cost, since AA needs FEWER iterations to reach a given
// quality rather than making each iteration cheaper).
//
// Applied at the OUTER level, matching the established "acceleration goes
// outside OCA's recursion, not inside it" finding (Section 7) -- this wraps
// SolveLMSchurSparse's own plain damped-GN step (identical assembly,
// xi-ratio mu adaptation, and reject/retry-on-worse-cost loop, all
// unchanged) with standard Type-I Anderson Acceleration (Walker & Ni 2011,
// successive-differences form): maintain the last `window` (Dx,Df) pairs
// (Dx = the ACTUALLY applied step, Df = consecutive difference of the plain
// step itself), solve the small unconstrained least-squares
// gamma=argmin||f_k-DF@gamma||^2 (ridge-regularized), form the candidate
// d_aa = f_k - DX@gamma, and accept it ONLY if its true retracted cost beats
// the plain step's -- exactly the same true-cost accept/fallback contract
// as the outer-Nesterov work. mu adaptation is driven by the PLAIN step's
// xi ratio regardless of whether AA's candidate is the one actually
// applied, matching the numpy prototype's validated design.
RunLog SolveLMSchurSparseAA(const DeviceProblem& p, DeviceState& s, Scalar mu0, Scalar tol, int max_iter,
                             bool verbose, int window = 2, Scalar reg = 1e-10, Scalar grad_tol_rel = 1e-8) {
  int ncam = p.ncam, npt = p.npt, n_c = 6*ncam, n_p = 3*npt, n = n_c + n_p;
  Scalar *Hcc, *Hpp, *obs_Hcp, *grad_c, *grad_p, *App_inv, *S;
  Scalar *bc_corr, *bc_prime, *xc, *xp, *d, *jd_sum, *d_aa_dev;
  int* ok_flags;
  CUDA_CHECK(cudaMalloc(&Hcc, 36*(size_t)ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&Hpp, 9*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&obs_Hcp, 18*(size_t)p.nobs*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&grad_c, 6*(size_t)ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&grad_p, 3*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&App_inv, 9*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&S, (size_t)n_c*n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bc_corr, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&bc_prime, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&xc, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&xp, n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&d, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&jd_sum, sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&d_aa_dev, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&ok_flags, npt*sizeof(int)));
  DeviceState s_new; AllocState(s_new, ncam, npt);
  DeviceState s_aa; AllocState(s_aa, ncam, npt);

  cusolverDnHandle_t handle; cusolverDnCreate(&handle);
  CholeskyWorkspace ws; ws.Init(handle, n_c);

  Scalar mu = mu0;
  Scalar cost = ComputeCost(p, s);
  RunLog log; log.iters.push_back(0); log.costs.push_back(cost);
  Scalar grad_norm0 = -1.0;

  std::vector<std::vector<Scalar>> Dx_hist, Df_hist;  // each entry: host vector of length n
  std::vector<Scalar> f_prev;                          // empty until the first plain step is known
  int n_aa_accepted = 0;

  for (int k = 0; k < max_iter; ++k) {
    CUDA_CHECK(cudaMemset(Hcc, 0, 36*(size_t)ncam*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(Hpp, 0, 9*(size_t)npt*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(grad_c, 0, 6*(size_t)ncam*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(grad_p, 0, 3*(size_t)npt*sizeof(Scalar)));
    KernelAssembleSchurSparseGN<<<GridSize(p.nobs),256>>>(
        p.cam_idx, p.pt_idx, p.uv, s.R, s.t, s.X, p.f, p.k1, p.k2, p.nobs,
        Hcc, Hpp, obs_Hcp, grad_c, grad_p);

    Scalar grad_norm;
    { std::vector<Scalar> h_grad_full(n);
      CUDA_CHECK(cudaMemcpy(h_grad_full.data(), grad_c, n_c*sizeof(Scalar), cudaMemcpyDeviceToHost));
      CUDA_CHECK(cudaMemcpy(h_grad_full.data()+n_c, grad_p, n_p*sizeof(Scalar), cudaMemcpyDeviceToHost));
      Scalar s2 = 0.0; for (auto v : h_grad_full) s2 += v*v;
      grad_norm = std::sqrt(s2);
    }
    if (grad_norm0 < 0.0) grad_norm0 = std::max(grad_norm, (Scalar)1e-300);

    // ---- plain damped-GN step, identical to SolveLMSchurSparse (reject/retry on worse cost) ----
    Scalar cost_new, xi = 0.0;
    std::vector<Scalar> h_d(n);
    for (int attempt = 0;; ++attempt) {
      KernelInvertAppBlocks<<<GridSize(npt),256>>>(Hpp, mu, App_inv, ok_flags, npt);
      bool pd_ok = true;
      { std::vector<int> h_ok(npt);
        CUDA_CHECK(cudaMemcpy(h_ok.data(), ok_flags, npt*sizeof(int), cudaMemcpyDeviceToHost));
        for (int v : h_ok) if (!v) pd_ok = false;
      }
      if (pd_ok) {
        CUDA_CHECK(cudaMemset(S, 0, (size_t)n_c*n_c*sizeof(Scalar)));
        KernelBuildAccFull<<<GridSize(ncam),256>>>(Hcc, mu, S, ncam, n_c);
        KernelFormSSparse<<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                                  App_inv, npt, n_c, S);
        pd_ok = CholeskyFactor(ws, S);
      }
      if (!pd_ok) {
        if (attempt >= 30) {
          std::fprintf(stderr, "LM-Schur-sparse-AA: (Hpp+mu*I)/S not PD at k=%d even after growing mu to %.4g\n", k, mu);
          std::exit(EXIT_FAILURE);
        }
        mu *= 10.0;
        continue;
      }
      CUDA_CHECK(cudaMemset(bc_corr, 0, n_c*sizeof(Scalar)));
      KernelRHSCorrectionSparse<<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                                         App_inv, grad_p, npt, bc_corr);
      KernelSubtractVec<<<GridSize(n_c),256>>>(bc_prime, grad_c, bc_corr, n_c);
      CUDA_CHECK(cudaMemcpy(xc, bc_prime, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      CholeskySolveVec(ws, S, xc);
      KernelBackSubstituteSparse<<<GridSize(npt),256>>>(obs_Hcp, p.cam_idx, p.point_obs_offsets, p.point_obs_list,
                                                          App_inv, grad_p, xc, npt, xp);
      CUDA_CHECK(cudaMemcpy(d, xc, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      CUDA_CHECK(cudaMemcpy(d+n_c, xp, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));
      { std::vector<Scalar> tmp(n);
        CUDA_CHECK(cudaMemcpy(tmp.data(), d, n*sizeof(Scalar), cudaMemcpyDeviceToHost));
        for (auto& v : tmp) v = -v;
        CUDA_CHECK(cudaMemcpy(d, tmp.data(), n*sizeof(Scalar), cudaMemcpyHostToDevice));
      }

      Retract(p, s, d, s_new);
      cost_new = ComputeCost(p, s_new);

      CUDA_CHECK(cudaMemset(jd_sum, 0, sizeof(Scalar)));
      KernelJdSquaredSum<<<GridSize(p.nobs),256>>>(p.cam_idx, p.pt_idx, p.uv, s.R, s.t, s.X, p.f, p.k1, p.k2,
                                                    d, p.nobs, ncam, jd_sum);
      Scalar quad; CUDA_CHECK(cudaMemcpy(&quad, jd_sum, sizeof(Scalar), cudaMemcpyDeviceToHost));
      std::vector<Scalar> h_grad(n);
      CUDA_CHECK(cudaMemcpy(h_grad.data(), grad_c, n_c*sizeof(Scalar), cudaMemcpyDeviceToHost));
      CUDA_CHECK(cudaMemcpy(h_grad.data()+n_c, grad_p, n_p*sizeof(Scalar), cudaMemcpyDeviceToHost));
      CUDA_CHECK(cudaMemcpy(h_d.data(), d, n*sizeof(Scalar), cudaMemcpyDeviceToHost));
      Scalar grad_dot_d = 0.0; for (int i = 0; i < n; ++i) grad_dot_d += h_grad[i]*h_d[i];
      Scalar pred_decrease = -(grad_dot_d + 0.5*quad);
      Scalar actual_decrease = cost - cost_new;
      xi = (std::fabs(pred_decrease) > 1e-300) ? actual_decrease/pred_decrease : 0.0;

      if (cost_new <= cost || attempt >= 20) break;
      mu *= 10.0;
    }

    // ---- Anderson Acceleration: try to do better than the plain step using history ----
    std::vector<Scalar> applied = h_d;
    Scalar cost_final = cost_new;
    bool accepted_aa = false;
    bool used_s_aa = false;
    if (!Dx_hist.empty()) {
      int mcur = (int)Dx_hist.size();
      std::vector<std::vector<Scalar>> G(mcur, std::vector<Scalar>(mcur, 0.0));
      std::vector<Scalar> rhs(mcur, 0.0);
      for (int i = 0; i < mcur; ++i) {
        for (int j = 0; j < mcur; ++j) {
          Scalar dot = 0.0; for (int t = 0; t < n; ++t) dot += Df_hist[i][t]*Df_hist[j][t];
          G[i][j] = dot + (i == j ? reg : (Scalar)0.0);
        }
        Scalar dot = 0.0; for (int t = 0; t < n; ++t) dot += Df_hist[i][t]*h_d[t];
        rhs[i] = dot;
      }
      std::vector<Scalar> gamma = SolveSmallSPD(G, rhs);
      std::vector<Scalar> d_aa(n);
      for (int t = 0; t < n; ++t) {
        Scalar corr = 0.0; for (int i = 0; i < mcur; ++i) corr += gamma[i]*Dx_hist[i][t];
        d_aa[t] = h_d[t] - corr;
      }
      CUDA_CHECK(cudaMemcpy(d_aa_dev, d_aa.data(), n*sizeof(Scalar), cudaMemcpyHostToDevice));
      Retract(p, s, d_aa_dev, s_aa);
      Scalar cost_aa = ComputeCost(p, s_aa);
      if (cost_aa < cost_final) {
        applied = d_aa; cost_final = cost_aa; accepted_aa = true; used_s_aa = true;
      }
    }

    if (!f_prev.empty()) {
      std::vector<Scalar> df(n);
      for (int t = 0; t < n; ++t) df[t] = h_d[t] - f_prev[t];
      Dx_hist.push_back(applied);
      Df_hist.push_back(df);
      if ((int)Dx_hist.size() > window) { Dx_hist.erase(Dx_hist.begin()); Df_hist.erase(Df_hist.begin()); }
    }
    f_prev = h_d;

    if (used_s_aa) { std::swap(s.R, s_aa.R); std::swap(s.t, s_aa.t); std::swap(s.X, s_aa.X); }
    else { std::swap(s.R, s_new.R); std::swap(s.t, s_new.t); std::swap(s.X, s_new.X); }
    cost = cost_final;
    if (xi < 0.25) mu *= 10.0; else if (xi > 0.75) mu *= 0.1;
    n_aa_accepted += (int)accepted_aa;

    Scalar step_norm = 0.0; for (auto v : applied) step_norm += v*v; step_norm = std::sqrt(step_norm);
    log.iters.push_back(k+1); log.costs.push_back(cost);
    if (verbose) std::printf("  LM-Schur-sparse-AA it%4d cost=%.6e mu=%.3e xi=%.3f |d|=%.3e |grad|/|grad0|=%.3e %s\n",
                              k+1, cost, mu, xi, step_norm, grad_norm/grad_norm0, accepted_aa ? "[AA]" : "");
    if (step_norm < tol && grad_norm < grad_tol_rel * grad_norm0) break;
  }
  if (verbose) std::printf("  LM-Schur-sparse-AA: AA accepted %d/%d iterations\n", n_aa_accepted, (int)log.iters.size()-1);

  cusolverDnDestroy(handle);
  cudaFree(Hcc); cudaFree(Hpp); cudaFree(obs_Hcp); cudaFree(grad_c); cudaFree(grad_p);
  cudaFree(App_inv); cudaFree(S); cudaFree(bc_corr); cudaFree(bc_prime); cudaFree(xc); cudaFree(xp);
  cudaFree(d); cudaFree(jd_sum); cudaFree(d_aa_dev); cudaFree(ok_flags);
  cudaFree(s_new.R); cudaFree(s_new.t); cudaFree(s_new.X);
  cudaFree(s_aa.R); cudaFree(s_aa.t); cudaFree(s_aa.X);
  return log;
}

// ============================================================== Algorithm 2: DABA-style decoupled OCA (Phase 5)
// No cuSOLVER/cuBLAS needed anywhere -- unlike the Schur version, there is no
// coupled linear system to factorize, only independent per-block inversions
// and matvecs (see the kernel definitions above for the full rationale).
RunLog SolveOCADabaStyle(const DeviceProblem& p, DeviceState& s, Scalar lam, Scalar factor,
                          Scalar tol, int max_iter, bool verbose) {
  int ncam = p.ncam, npt = p.npt, n_c = 6*ncam, n_p = 3*npt, n = n_c + n_p;
  Scalar *Hcc, *Hpp, *obs_Hcp_unused, *grad_c, *grad_p, *Hcc_inv, *Hpp_inv, *gc, *gp, *d;
  int *ok_c, *ok_p;
  CUDA_CHECK(cudaMalloc(&Hcc, 36*(size_t)ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&Hpp, 9*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&obs_Hcp_unused, 18*(size_t)p.nobs*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&grad_c, 6*(size_t)ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&grad_p, 3*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&Hcc_inv, 36*(size_t)ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&Hpp_inv, 9*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&gc, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&gp, n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&d, n*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&ok_c, ncam*sizeof(int)));
  CUDA_CHECK(cudaMalloc(&ok_p, npt*sizeof(int)));
  DeviceState s_new; AllocState(s_new, ncam, npt);

  Scalar cost = ComputeCost(p, s);
  RunLog log; log.iters.push_back(0); log.costs.push_back(cost);

  for (int k = 0; k < max_iter; ++k) {
    CUDA_CHECK(cudaMemset(Hcc, 0, 36*(size_t)ncam*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(Hpp, 0, 9*(size_t)npt*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(grad_c, 0, 6*(size_t)ncam*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(grad_p, 0, 3*(size_t)npt*sizeof(Scalar)));
    KernelAssembleSchurSparse<<<GridSize(p.nobs),256>>>(
        p.cam_idx, p.pt_idx, p.uv, s.R, s.t, s.X, p.f, p.k1, p.k2, p.nobs,
        Hcc, Hpp, obs_Hcp_unused, grad_c, grad_p);  // obs_Hcp_unused: cross term computed but never used -- decoupled by construction

    KernelInvertCamBlocks<<<GridSize(ncam),256>>>(Hcc, lam, factor, Hcc_inv, ok_c, ncam);
    KernelInvertPtBlocksFactored<<<GridSize(npt),256>>>(Hpp, lam, factor, Hpp_inv, ok_p, npt);
    { std::vector<int> h_ok(std::max(ncam,npt));
      bool all_ok = true;
      h_ok.resize(ncam); CUDA_CHECK(cudaMemcpy(h_ok.data(), ok_c, ncam*sizeof(int), cudaMemcpyDeviceToHost));
      for (int v : h_ok) if (!v) all_ok = false;
      h_ok.resize(npt); CUDA_CHECK(cudaMemcpy(h_ok.data(), ok_p, npt*sizeof(int), cudaMemcpyDeviceToHost));
      for (int v : h_ok) if (!v) all_ok = false;
      if (!all_ok) {
        std::fprintf(stderr, "OCA-DABA-style: (lam*I+H_diag) not PD at outer iter k=%d (lam=%.4g, factor=%.4g)\n", k, lam, factor);
        std::exit(EXIT_FAILURE);
      }
    }

    KernelBlockApply6<<<GridSize(ncam),256>>>(Hcc_inv, grad_c, nullptr, lam, ncam, gc);  // g_0 camera part
    KernelBlockApply3<<<GridSize(npt),256>>>(Hpp_inv, grad_p, nullptr, lam, npt, gp);    // g_0 point part
    for (int j = 1; j <= k; ++j) {
      KernelBlockApply6<<<GridSize(ncam),256>>>(Hcc_inv, grad_c, gc, lam, ncam, gc);  // in-place: safe (see kernel doc)
      KernelBlockApply3<<<GridSize(npt),256>>>(Hpp_inv, grad_p, gp, lam, npt, gp);
    }
    CUDA_CHECK(cudaMemcpy(d, gc, n_c*sizeof(Scalar), cudaMemcpyDeviceToDevice));
    CUDA_CHECK(cudaMemcpy(d+n_c, gp, n_p*sizeof(Scalar), cudaMemcpyDeviceToDevice));
    { std::vector<Scalar> tmp(n);
      CUDA_CHECK(cudaMemcpy(tmp.data(), d, n*sizeof(Scalar), cudaMemcpyDeviceToHost));
      for (auto& v : tmp) v = -v;
      CUDA_CHECK(cudaMemcpy(d, tmp.data(), n*sizeof(Scalar), cudaMemcpyHostToDevice));
    }

    Retract(p, s, d, s_new);
    std::swap(s.R, s_new.R); std::swap(s.t, s_new.t); std::swap(s.X, s_new.X);
    cost = ComputeCost(p, s);

    std::vector<Scalar> h_d(n);
    CUDA_CHECK(cudaMemcpy(h_d.data(), d, n*sizeof(Scalar), cudaMemcpyDeviceToHost));
    Scalar step_norm = 0.0; for (auto v : h_d) step_norm += v*v; step_norm = std::sqrt(step_norm);

    log.iters.push_back(k+1); log.costs.push_back(cost);
    if (verbose) std::printf("  OCA-DABA-style it%4d cost=%.6e inner_steps=%d |d|=%.3e\n", k+1, cost, k+1, step_norm);
    if (step_norm < tol) break;
  }

  cudaFree(Hcc); cudaFree(Hpp); cudaFree(obs_Hcp_unused); cudaFree(grad_c); cudaFree(grad_p);
  cudaFree(Hcc_inv); cudaFree(Hpp_inv); cudaFree(gc); cudaFree(gp); cudaFree(d);
  cudaFree(ok_c); cudaFree(ok_p);
  cudaFree(s_new.R); cudaFree(s_new.t); cudaFree(s_new.X);
  return log;
}

// ============================================================== DABA-style OCA + per-block multi-lambda (Phase 6)
RunLog SolveOCADabaMultiLambda(const DeviceProblem& p, DeviceState& s, Scalar factor, int n_lambda,
                                Scalar decade_lo, Scalar decade_hi, Scalar lam_floor, Scalar lam_ceil,
                                Scalar base_lam_cam0, Scalar base_lam_pt0,
                                Scalar tol, int max_iter, bool verbose) {
  int ncam = p.ncam, npt = p.npt, n_c = 6*ncam, n_p = 3*npt, n = n_c + n_p;
  Scalar *Hcc, *Hpp, *obs_Hcp_unused, *grad_c, *grad_p;
  Scalar *base_lam_cam, *base_lam_pt, *lam_mult;
  Scalar *dC_grid, *dX_grid, *lam_grid_cam, *lam_grid_pt;
  Scalar *cam_cost_cand, *pt_cost_cand, *chosen_lam_cam, *chosen_lam_pt;
  Scalar *Hcc_inv, *Hpp_inv, *gcj, *gpj;
  Scalar *cam_cost_now, *pt_cost_now, *cam_cost_final, *pt_cost_final;
  Scalar *d_cam, *d_pt, *neg_gcj, *neg_gpj;
  int *ok_c, *ok_p;
  CUDA_CHECK(cudaMalloc(&Hcc, 36*(size_t)ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&Hpp, 9*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&obs_Hcp_unused, 18*(size_t)p.nobs*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&grad_c, 6*(size_t)ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&grad_p, 3*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&base_lam_cam, ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&base_lam_pt, npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&lam_mult, n_lambda*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&dC_grid, 6*(size_t)ncam*n_lambda*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&dX_grid, 3*(size_t)npt*n_lambda*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&lam_grid_cam, (size_t)ncam*n_lambda*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&lam_grid_pt, (size_t)npt*n_lambda*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&cam_cost_cand, (size_t)ncam*n_lambda*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&pt_cost_cand, (size_t)npt*n_lambda*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&chosen_lam_cam, ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&chosen_lam_pt, npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&Hcc_inv, 36*(size_t)ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&Hpp_inv, 9*(size_t)npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&gcj, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&gpj, n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&cam_cost_now, ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&pt_cost_now, npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&cam_cost_final, ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&pt_cost_final, npt*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&d_cam, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&d_pt, n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&neg_gcj, n_c*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&neg_gpj, n_p*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&ok_c, ncam*sizeof(int)));
  CUDA_CHECK(cudaMalloc(&ok_p, npt*sizeof(int)));
  DeviceState s_new; AllocState(s_new, ncam, npt);

  { std::vector<Scalar> h_base_c(ncam, base_lam_cam0), h_base_p(npt, base_lam_pt0);
    CUDA_CHECK(cudaMemcpy(base_lam_cam, h_base_c.data(), ncam*sizeof(Scalar), cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemcpy(base_lam_pt, h_base_p.data(), npt*sizeof(Scalar), cudaMemcpyHostToDevice));
    std::vector<Scalar> h_mult(n_lambda);
    for (int i = 0; i < n_lambda; ++i) {
      Scalar frac = n_lambda > 1 ? (Scalar)i/(n_lambda-1) : 0.0;
      h_mult[i] = std::pow(10.0, decade_lo + frac*(decade_hi-decade_lo));
    }
    CUDA_CHECK(cudaMemcpy(lam_mult, h_mult.data(), n_lambda*sizeof(Scalar), cudaMemcpyHostToDevice));
  }

  Scalar cost = ComputeCost(p, s);
  RunLog log; log.iters.push_back(0); log.costs.push_back(cost);

  for (int k = 0; k < max_iter; ++k) {
    CUDA_CHECK(cudaMemset(Hcc, 0, 36*(size_t)ncam*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(Hpp, 0, 9*(size_t)npt*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(grad_c, 0, 6*(size_t)ncam*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(grad_p, 0, 3*(size_t)npt*sizeof(Scalar)));
    KernelAssembleSchurSparse<<<GridSize(p.nobs),256>>>(
        p.cam_idx, p.pt_idx, p.uv, s.R, s.t, s.X, p.f, p.k1, p.k2, p.nobs,
        Hcc, Hpp, obs_Hcp_unused, grad_c, grad_p);

    // ---- per-block candidate grid + true-cost selection (DABA's own mechanism, k=0 step) ----
    KernelCamCandidateSolve<<<GridSize(ncam),256>>>(Hcc, grad_c, base_lam_cam, factor, lam_mult, n_lambda, ncam, dC_grid, lam_grid_cam);
    KernelPtCandidateSolve<<<GridSize(npt),256>>>(Hpp, grad_p, base_lam_pt, factor, lam_mult, n_lambda, npt, dX_grid, lam_grid_pt);
    CUDA_CHECK(cudaMemset(cam_cost_cand, 0, (size_t)ncam*n_lambda*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(pt_cost_cand, 0, (size_t)npt*n_lambda*sizeof(Scalar)));
    KernelCamCandidateCost<<<GridSize(p.nobs),256>>>(p.cam_idx, p.pt_idx, p.uv, s.R, s.t, s.X, p.f, p.k1, p.k2,
                                                       dC_grid, n_lambda, p.nobs, cam_cost_cand);
    KernelPtCandidateCost<<<GridSize(p.nobs),256>>>(p.cam_idx, p.pt_idx, p.uv, s.R, s.t, s.X, p.f, p.k1, p.k2,
                                                      dX_grid, n_lambda, p.nobs, pt_cost_cand);
    KernelSelectLam<<<GridSize(ncam),256>>>(cam_cost_cand, lam_grid_cam, n_lambda, ncam, chosen_lam_cam);
    KernelSelectLam<<<GridSize(npt),256>>>(pt_cost_cand, lam_grid_pt, n_lambda, npt, chosen_lam_pt);

    // ---- OCA's recursion (j=1..k) using each block's selected lambda for this outer iteration ----
    KernelInvertCamBlocksVarLam<<<GridSize(ncam),256>>>(Hcc, chosen_lam_cam, factor, Hcc_inv, ok_c, ncam);
    KernelInvertPtBlocksVarLamFactored<<<GridSize(npt),256>>>(Hpp, chosen_lam_pt, factor, Hpp_inv, ok_p, npt);
    KernelBlockApply6VarLam<<<GridSize(ncam),256>>>(Hcc_inv, grad_c, nullptr, chosen_lam_cam, ncam, gcj);
    KernelBlockApply3VarLam<<<GridSize(npt),256>>>(Hpp_inv, grad_p, nullptr, chosen_lam_pt, npt, gpj);
    for (int j = 1; j <= k; ++j) {
      KernelBlockApply6VarLam<<<GridSize(ncam),256>>>(Hcc_inv, grad_c, gcj, chosen_lam_cam, ncam, gcj);
      KernelBlockApply3VarLam<<<GridSize(npt),256>>>(Hpp_inv, grad_p, gpj, chosen_lam_pt, npt, gpj);
    }

    // ---- final accept/reject on the step ACTUALLY applied (g_k) ----
    CUDA_CHECK(cudaMemset(cam_cost_now, 0, ncam*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(pt_cost_now, 0, npt*sizeof(Scalar)));
    KernelPerBlockCostNow<<<GridSize(p.nobs),256>>>(p.cam_idx, p.pt_idx, p.uv, s.R, s.t, s.X, p.f, p.k1, p.k2,
                                                      p.nobs, cam_cost_now, pt_cost_now);
    CUDA_CHECK(cudaMemset(cam_cost_final, 0, ncam*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(pt_cost_final, 0, npt*sizeof(Scalar)));
    // KernelCamCandidateCost/KernelPtCandidateCost treat their dC/dX argument as the
    // retraction direction directly -- the actual step is -g_k (matches
    // KernelAcceptUpdateCam's own dneg=-gcj convention), so negate before evaluating.
    CUDA_CHECK(cudaMemset(neg_gcj, 0, n_c*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(neg_gpj, 0, n_p*sizeof(Scalar)));
    KernelAxpy<<<GridSize(n_c),256>>>(neg_gcj, gcj, -1.0, n_c);
    KernelAxpy<<<GridSize(n_p),256>>>(neg_gpj, gpj, -1.0, n_p);
    KernelCamCandidateCost<<<GridSize(p.nobs),256>>>(p.cam_idx, p.pt_idx, p.uv, s.R, s.t, s.X, p.f, p.k1, p.k2,
                                                       neg_gcj, 1, p.nobs, cam_cost_final);
    KernelPtCandidateCost<<<GridSize(p.nobs),256>>>(p.cam_idx, p.pt_idx, p.uv, s.R, s.t, s.X, p.f, p.k1, p.k2,
                                                      neg_gpj, 1, p.nobs, pt_cost_final);

    KernelAcceptUpdateCam<<<GridSize(ncam),256>>>(cam_cost_final, cam_cost_now, gcj, chosen_lam_cam,
                                                    lam_floor, lam_ceil, ncam, s.R, s.t, s_new.R, s_new.t, base_lam_cam, d_cam);
    KernelAcceptUpdatePt<<<GridSize(npt),256>>>(pt_cost_final, pt_cost_now, gpj, chosen_lam_pt,
                                                  lam_floor, lam_ceil, npt, s.X, s_new.X, base_lam_pt, d_pt);
    std::swap(s.R, s_new.R); std::swap(s.t, s_new.t); std::swap(s.X, s_new.X);
    cost = ComputeCost(p, s);

    std::vector<Scalar> h_dc(n_c), h_dp(n_p);
    CUDA_CHECK(cudaMemcpy(h_dc.data(), d_cam, n_c*sizeof(Scalar), cudaMemcpyDeviceToHost));
    CUDA_CHECK(cudaMemcpy(h_dp.data(), d_pt, n_p*sizeof(Scalar), cudaMemcpyDeviceToHost));
    Scalar step_norm = 0.0; for (auto v : h_dc) step_norm += v*v; for (auto v : h_dp) step_norm += v*v;
    step_norm = std::sqrt(step_norm);

    log.iters.push_back(k+1); log.costs.push_back(cost);
    if (verbose) std::printf("  OCA-DABA-multilambda it%4d cost=%.6e |d|=%.3e\n", k+1, cost, step_norm);
    if (step_norm < tol) break;
  }

  cudaFree(Hcc); cudaFree(Hpp); cudaFree(obs_Hcp_unused); cudaFree(grad_c); cudaFree(grad_p);
  cudaFree(base_lam_cam); cudaFree(base_lam_pt); cudaFree(lam_mult);
  cudaFree(dC_grid); cudaFree(dX_grid); cudaFree(lam_grid_cam); cudaFree(lam_grid_pt);
  cudaFree(cam_cost_cand); cudaFree(pt_cost_cand); cudaFree(chosen_lam_cam); cudaFree(chosen_lam_pt);
  cudaFree(Hcc_inv); cudaFree(Hpp_inv); cudaFree(gcj); cudaFree(gpj);
  cudaFree(cam_cost_now); cudaFree(pt_cost_now); cudaFree(cam_cost_final); cudaFree(pt_cost_final);
  cudaFree(d_cam); cudaFree(d_pt); cudaFree(neg_gcj); cudaFree(neg_gpj); cudaFree(ok_c); cudaFree(ok_p);
  cudaFree(s_new.R); cudaFree(s_new.t); cudaFree(s_new.X);
  return log;
}

// ============================================================== main
#endif  // !OCA_CORE_LIBRARY (legacy research solvers)

#ifndef OCA_CORE_LIBRARY
void PrintUsage(const char* prog) {
  std::fprintf(stderr,
      "Usage: %s --problem PATH --algo lm|oca|oca_adaptive [--lam L] [--lam0 L0] [--lam1 L1] "
      "[--mu0 M] [--tol T] [--max_iter N] [--quiet]\n", prog);
}
#endif  // !OCA_CORE_LIBRARY

// ---------------------------------------------------------------- s2.5/s2.6 driver
struct MFStats { long matvecs=0; long negcurv=0; long cand_evals=0;
                 long menu_gated=0; long menu_full=0;
                 long doomed_probe=0; long doomed_wrong=0; };

// ---- OCA_LEARN_POLICY: learned candidate-set controller (agent_rev/learn,
// Exp 5-7). Chooses WHICH menu candidates get true-cost scoring; never
// touches how a candidate is scored (selection-perturbation law). Two linear
// heads exported by train34.py: a decisiveness logistic over 14 state
// features and a per-shift utility ridge over 8 rank + 14 state features.
// Feature order here MUST match menus.py FEATS / train34.py SFEATS.
// Modes (OCA_LEARN_MODE): fixed2 | top1 | top2 | ada | ada2.
//   fixed2 : score {center, center+1} (trivial 2-eval baseline arm)
//   top1/2 : score the k best candidates by the utility head
//   ada    : flat menus (p_decisive < thr) score shift 0 only, else full menu
//   ada2   : flat -> shift 0, decisive -> top-2 by utility
struct LearnPolicy {
  bool on=false; int mode=0;              // 1=top1 2=top2 3=ada 4=ada2 5=fixed2
  double dec_thr=0.5;
  static constexpr int NS=14, NR=22;      // state dims; rank dims (8+14)
  double dmu[NS]={0},dsd[NS]={0},dw[NS]={0},db=0;
  double rmu[NR]={0},rsd[NR]={0},rw[NR]={0},rb=0;
  long n_flat=0,n_dec=0,n_menus=0;        // telemetry
  // Optional GBT forest for the utility head (OCA_LEARN_FOREST): plain
  // threshold rules exported by train34.py, evaluated on the RAW 22-dim
  // rank feature vector (no standardization). pred = init + lr*sum(trees).
  struct FNode { int feat,left,right; double thr,val; };
  std::vector<FNode> fnodes; std::vector<int> froot;
  double f_init=0.0,f_lr=0.1; bool forest_on=false;
  double ForestU(const double* f) const {
    double s=f_init;
    for(size_t t=0;t<froot.size();++t){
      int i=froot[t];
      while(fnodes[i].feat>=0)
        i = (f[fnodes[i].feat]<=fnodes[i].thr) ? fnodes[i].left : fnodes[i].right;
      s += f_lr*fnodes[i].val;
    }
    return s;
  }
  static double Sig(double z){ return 1.0/(1.0+std::exp(-z)); }
  double DecP(const double* f) const {
    double z=db;
    for(int i=0;i<NS;++i) z+=dw[i]*((f[i]-dmu[i])/(dsd[i]!=0?dsd[i]:1.0));
    return Sig(z);
  }
  double RankU(const double* f) const {
    double z=rb;
    for(int i=0;i<NR;++i) z+=rw[i]*((f[i]-rmu[i])/(rsd[i]!=0?rsd[i]:1.0));
    return z;                             // lower = better (log10 badness)
  }
  static bool ReadVec(FILE* fp,const char* key,double* v,int n){
    char k[64];
    if(std::fscanf(fp,"%63s",k)!=1||std::strcmp(k,key)!=0) return false;
    for(int i=0;i<n;++i) if(std::fscanf(fp,"%lf",v+i)!=1) return false;
    return true;
  }
};
static LearnPolicy g_lp;
static void LoadLearnPolicy(){
  static bool done=false; if(done) return; done=true;
  const char* mp=getenv("OCA_LEARN_POLICY");
  const char* mm=getenv("OCA_LEARN_MODE");
  if(!mm) return;
  if     (!std::strcmp(mm,"top1"))   g_lp.mode=1;
  else if(!std::strcmp(mm,"top2"))   g_lp.mode=2;
  else if(!std::strcmp(mm,"ada"))    g_lp.mode=3;
  else if(!std::strcmp(mm,"ada2"))   g_lp.mode=4;
  else if(!std::strcmp(mm,"fixed2")) g_lp.mode=5;
  else if(!std::strcmp(mm,"force"))  g_lp.mode=6;   // Exp 10 branched rollouts
  else if(!std::strcmp(mm,"shi1"))   g_lp.mode=7;   // streak: {L-1} probe
  else if(!std::strcmp(mm,"shi2"))   g_lp.mode=8;   // streak: {L-2,L-1} probe
  else if(!std::strcmp(mm,"shi2fx")) g_lp.mode=9;   // streak probe + clean fixed2
  else if(!std::strcmp(mm,"qh"))     g_lp.mode=10;  // horizon-Q prior (rlq study)
  else { std::fprintf(stderr,"[learn] unknown OCA_LEARN_MODE=%s\n",mm); return; }
  if(const char* e=getenv("OCA_LEARN_DEC_THR")) g_lp.dec_thr=std::atof(e);
  // Optional forest utility head (threshold rules; see LearnPolicy::ForestU).
  // Used by the linear-policy modes when present, and REQUIRED by mode qh
  // (which carries no linear-policy file at all -- its forest was trained on
  // H-outer branched-rollout returns, not one-step cost; rlq study).
  auto load_forest=[&](){
    const char* fp2=getenv("OCA_LEARN_FOREST");
    if(!fp2) return;
    FILE* ff=std::fopen(fp2,"r");
    if(!ff){ std::fprintf(stderr,"[learn] cannot open forest %s\n",fp2); return; }
    int nf=0,nt=0; double init=0,lr=0;
    if(std::fscanf(ff,"forest %d %d %lf %lf",&nf,&nt,&init,&lr)==4 &&
       nf==LearnPolicy::NR && nt>0 && nt<=4096){
      g_lp.f_init=init; g_lp.f_lr=lr;
      bool fok=true;
      for(int t=0;t<nt&&fok;++t){
        int nn=0;
        if(std::fscanf(ff," tree %d",&nn)!=1 || nn<=0 || nn>65535){ fok=false; break; }
        const int base=(int)g_lp.fnodes.size();
        g_lp.froot.push_back(base);
        for(int i=0;i<nn;++i){
          LearnPolicy::FNode nd{};
          if(std::fscanf(ff," %d %lf %d %d %lf",
                         &nd.feat,&nd.thr,&nd.left,&nd.right,&nd.val)!=5){ fok=false; break; }
          if(nd.feat>=0){ nd.left+=base; nd.right+=base;
            if(nd.feat>=LearnPolicy::NR){ fok=false; break; } }
          g_lp.fnodes.push_back(nd);
        }
      }
      if(fok){ g_lp.forest_on=true;
        std::fprintf(stderr,"[learn] forest loaded (%s: %d trees, %zu nodes)\n",
                     fp2,nt,g_lp.fnodes.size()); }
      else { g_lp.fnodes.clear(); g_lp.froot.clear();
        std::fprintf(stderr,"[learn] forest file %s malformed, OFF\n",fp2); }
    } else std::fprintf(stderr,"[learn] forest header bad in %s\n",fp2);
    std::fclose(ff);
  };
  if(g_lp.mode==10){
    load_forest();
    if(g_lp.forest_on) g_lp.on=true;
    else std::fprintf(stderr,"[learn] mode qh requires a valid OCA_LEARN_FOREST; OFF\n");
    return;
  }
  if(g_lp.mode>=5){ g_lp.on=true; return; }  // modes 5-9 need no weights
  if(!mp){ std::fprintf(stderr,"[learn] OCA_LEARN_MODE without OCA_LEARN_POLICY\n"); return; }
  FILE* fp=std::fopen(mp,"r");
  if(!fp){ std::fprintf(stderr,"[learn] cannot open %s\n",mp); return; }
  // skip comment + feature-name lines by keyed reads
  char line[4096];
  // format: '# ...' then dec_feats <names...> etc. Read line-wise, key-wise.
  bool ok=true; int got=0;
  while(std::fgets(line,sizeof line,fp)){
    char key[64]; int off=0;
    if(std::sscanf(line,"%63s%n",key,&off)!=1) continue;
    auto rd=[&](double* v,int n){ const char* p=line+off; char* end;
      for(int i=0;i<n;++i){ v[i]=std::strtod(p,&end); if(end==p){return false;} p=end; }
      return true; };
    if(!std::strcmp(key,"dec_mu")) ok&=rd(g_lp.dmu,LearnPolicy::NS),++got;
    else if(!std::strcmp(key,"dec_sd")) ok&=rd(g_lp.dsd,LearnPolicy::NS),++got;
    else if(!std::strcmp(key,"dec_w"))  ok&=rd(g_lp.dw ,LearnPolicy::NS),++got;
    else if(!std::strcmp(key,"dec_b"))  ok&=rd(&g_lp.db,1),++got;
    else if(!std::strcmp(key,"rank_mu"))ok&=rd(g_lp.rmu,LearnPolicy::NR),++got;
    else if(!std::strcmp(key,"rank_sd"))ok&=rd(g_lp.rsd,LearnPolicy::NR),++got;
    else if(!std::strcmp(key,"rank_w")) ok&=rd(g_lp.rw ,LearnPolicy::NR),++got;
    else if(!std::strcmp(key,"rank_b")) ok&=rd(&g_lp.rb,1),++got;
    else if(!std::strcmp(key,"dec_thr")&&!getenv("OCA_LEARN_DEC_THR"))
      rd(&g_lp.dec_thr,1);   // file-provided threshold; env wins
  }
  std::fclose(fp);
  if(ok&&got>=8){ g_lp.on=true;
    std::fprintf(stderr,"[learn] policy loaded (%s, mode %d, thr %.2f)\n",mp,g_lp.mode,g_lp.dec_thr); }
  else std::fprintf(stderr,"[learn] policy file %s incomplete (got %d/8), OFF\n",mp,got);
  load_forest();
}
// ROUND 10: CD templates the camera-block dimension. CD=6 reproduces round 9
// exactly (s.intr null, intrinsics read from the immutable problem arrays).
// CD=9 runs with s.intr non-null; k2mask=0 holds k2 fixed (Caspar-matched
// f+k1 refinement), k2mask=1 frees all three intrinsics.
// ROUND 12: the OPENCV_FISHEYE + rig path lives in its own header and reuses
// the generic MF kernels above; nothing below this include is modified by it.
#include "oca_rigfisheye.cuh"

template <int CD>
RunLog SolveMFreeShiftedCG(const DeviceProblem& p, DeviceState& s, Scalar lam0, int max_iter,
                           bool verbose, Scalar tau_pt, std::vector<int> ckpts, int n_shifts,
                           bool use_equil, Scalar ew_eta_max, bool use_alpha,
                           const std::string& jsonpath, bool mf_fp32 = false, Scalar k2mask = 1.0,
                           Scalar equil_floor = 0.0, Scalar intr_damp = 1.0,
                           int max_inner_retry = 8, bool tau_persist = true,
                           // Early stopping. Both default to DISABLED so the CLI's
                           // fixed-iteration behaviour stays bit-identical; the core
                           // library turns them on. Without these the solver always
                           // pays max_iter, which makes it uncompetitive on the small
                           // problems that incremental mapping is made of.
                           Scalar func_tolerance = 0.0,
                           int max_consecutive_failures = 0,
                           // IRLS robust kernel: 0 = L2 (bit-compat default).
                           // rk_scale2 is delta^2/c^2, or nu*sigma0^2 for the
                           // student-t (0 = auto-init from the residual median).
                           int rk = 0, Scalar rk_scale2 = 0.0, Scalar rk_nu = 4.0,
                           // Fast-opening mode: prune the candidate menu at
                           // intermediate CG checkpoints and cap CG depth
                           // while no step has been rejected yet. Shrinks the
                           // window where a single-damping solver leads, at a
                           // small but REAL end-residual cost -- see
                           // OPENING_ACCEL.md. Off by default.
                           bool fast_opening = false,
                           int fast_opening_depth = 32,
                           // REVIEW 2026-09-02: warm-start feedback for the
                           // mapper (Result::final_lambda). The rig path has
                           // always had this; the BAL path returned 0.0.
                           Scalar* final_lambda_out = nullptr) {
  int ncam=p.ncam, npt=p.npt, n_p=3*npt, nobs=p.nobs;
  // ROUND 11: with shared intrinsics the CG runs in the REDUCED camera space
  // [6*ncam poses | 3*ncalib calibrations]; the assembly kernels keep writing
  // the FULL 9-per-camera space. n_cf is the full width, n_c the reduced one.
  // Unshared (or CD==6) leaves n_c == n_cf, i.e. the pre-round-11 behaviour.
  const int n_cf=CD*ncam;
  // Triggered by the PRESENCE of a map, not by ncalib<ncam: an identity map
  // must exercise this path too, so the bijective case is a real regression
  // gate against the unshared one rather than silently bypassing it.
  // REVIEW: OCA_FORCE_UNSHARED=1 runs the unshared 9-per-camera path even when
  // calibration groups exist. With ONE group per camera the two formulations are
  // mathematically equivalent, so this makes the GPU exercise exactly the
  // structure the CPU prototype validated (needed to establish parity for the
  // block-congruence preconditioner).
  static const bool force_unshared = getenv("OCA_FORCE_UNSHARED")!=nullptr;
  const bool shared_intr = (!force_unshared && CD==9 && p.calib_of_cam!=nullptr && p.ncalib>0);
  const int ncalib = shared_intr ? p.ncalib : ncam;
  int n_c = shared_intr ? (6*ncam+3*ncalib) : n_cf;
  int n=n_cf+n_p;
  bool prof = (getenv("OCA_PROFILE")!=nullptr);
  auto now = [](){ return std::chrono::steady_clock::now(); };
  // REVIEW 2026-09-01: every pointer nullptr-initialised so the cleanup block
  // can free unconditionally (cudaFree(nullptr) is a no-op). The fp32 branch
  // leaves the fp64 gradient arrays unallocated and vice versa.
  Scalar *Hcc=nullptr,*Cdiag=nullptr,*Gp=nullptr,*Gc=nullptr,*Bo=nullptr,*bc=nullptr,
         *bp=nullptr,*Rf=nullptr,*tacc=nullptr,*uu=nullptr,*w=nullptr,*bprime=nullptr,
         *corr=nullptr,*E=nullptr,*dk=nullptr;
  Scalar *Bk=nullptr,*bscr=nullptr;   // REVIEW: block-congruence factor + scratch
  float *Gp32=nullptr,*Gc32=nullptr,*Bo32=nullptr;   // ROUND 9: --mf-fp32 storage
  Scalar *xc_un=nullptr,*xpv=nullptr,*dfull=nullptr,
         *d_best=nullptr,*r_=nullptr,*pv_=nullptr,*Ap_=nullptr;
  Scalar *pp1=nullptr,*pp2=nullptr,*pp3=nullptr,*pp4=nullptr;  // OCA_POLY_CONG scratch
  Scalar *R0f=nullptr;   // GAP-4090 F5: tau-independent point-factor cache
  Scalar *XCU=nullptr,*TACC=nullptr;   // GAP-4090 F2: multi-RHS scoring buffers
  int* okf;
  auto M=[&](void**q,size_t b){CUDA_CHECK(cudaMalloc(q,b));};
  M((void**)&Hcc,(size_t)CD*CD*ncam*sizeof(Scalar));M((void**)&Cdiag,3ul*npt*sizeof(Scalar));
  static const bool block_eq = getenv("OCA_BLOCKEQ")!=nullptr;
  // OCA_PRECOND_SWITCH=<eps> (+ OCA_PRECOND_SWITCH_K, default 3): the
  // diag-opening -> block-grind SCHEDULER. Basin selection happens in the
  // opening, where the block congruence can steer into catastrophically worse
  // basins (final-4585 +78%, ladybug-1197 +26% vs diag); block's 6-9x cheaper
  // Krylov matters in the grind, where it is quality-neutral (bit-identical on
  // 22/22 warm replays). So: open with the DIAGONAL preconditioner, and flip
  // to block permanently once relative progress has flattened (< eps for K
  // consecutive outers -- the same signal family as OCA_FTOL and the menu
  // gate). Unset = no scheduling, bit-compat.
  static const double psw_eps = [](){
    const char* e=getenv("OCA_PRECOND_SWITCH"); return e?std::atof(e):0.0; }();
  static const int psw_k = [](){
    const char* e=getenv("OCA_PRECOND_SWITCH_K"); return e?std::atoi(e):3; }();
  // OCA_PRECOND_SWITCH_LAM=<v>: LAMBDA-triggered variant -- switch diag->block
  // once lam_cam has decayed to <= v. lambda is the solver's own nonlinearity
  // estimate: basin selection happens while lambda is large (damped short
  // steps steer), and once lambda is far below the spectrum the steps are
  // near-Newton within an already-chosen basin, where block is measured
  // quality-neutral. Fires earlier than the flatness streak (venice-52:
  // lambda floors by ~outer 9 while the streak fired at 43), recovering more
  // of block's wall. Both triggers may be set; whichever fires first wins.
  static const double psw_lam = [](){
    const char* e=getenv("OCA_PRECOND_SWITCH_LAM"); return e?std::atof(e):0.0; }();
  const bool psw = psw_eps>0.0 || psw_lam>0.0;
  // block_on: the preconditioner actually used THIS outer. With the scheduler
  // it starts false (diag opening) and flips once; otherwise it equals the
  // static flag. Buffers are allocated if block can EVER be on.
  bool block_on = block_eq && !psw;
  int psw_streak=0; bool psw_switched=false;
  if(block_eq){ M((void**)&Bk,(size_t)CD*CD*ncam*sizeof(Scalar));
                M((void**)&bscr,(size_t)n_cf*sizeof(Scalar)); }
  if(mf_fp32){ M((void**)&Gp32,(size_t)3*CD*nobs*sizeof(float));M((void**)&Gc32,(size_t)3*CD*nobs*sizeof(float));
               M((void**)&Bo32,6ul*nobs*sizeof(float)); }
  else       { M((void**)&Gp,(size_t)3*CD*nobs*sizeof(Scalar));M((void**)&Gc,(size_t)3*CD*nobs*sizeof(Scalar));
               M((void**)&Bo,6ul*nobs*sizeof(Scalar)); }
  M((void**)&bc,(size_t)n_cf*sizeof(Scalar));M((void**)&bp,(size_t)n_p*sizeof(Scalar));
  M((void**)&Rf,6ul*npt*sizeof(Scalar));M((void**)&tacc,(size_t)n_p*sizeof(Scalar));
  M((void**)&uu,(size_t)n_p*sizeof(Scalar));M((void**)&w,(size_t)n_cf*sizeof(Scalar));
  M((void**)&bprime,(size_t)n_c*sizeof(Scalar));M((void**)&corr,(size_t)n_cf*sizeof(Scalar));
  M((void**)&E,(size_t)n_c*sizeof(Scalar));M((void**)&dk,(size_t)n_cf*sizeof(Scalar));
  M((void**)&xc_un,(size_t)n_cf*sizeof(Scalar));M((void**)&xpv,(size_t)n_p*sizeof(Scalar));
  M((void**)&dfull,(size_t)n*sizeof(Scalar));M((void**)&d_best,(size_t)n*sizeof(Scalar));
  M((void**)&r_,(size_t)n_c*sizeof(Scalar));M((void**)&pv_,(size_t)n_c*sizeof(Scalar));
  static const bool tau_split = [](){ const char* e=getenv("OCA_TAU_SPLIT");
    return e ? atoi(e)!=0 : true; }();
  if(tau_split) M((void**)&R0f,6ul*npt*sizeof(Scalar));
  static const bool multi_rhs = getenv("OCA_MULTI_RHS")!=nullptr;
  if(multi_rhs){ M((void**)&XCU,(size_t)n_shifts*n_cf*sizeof(Scalar));
                 M((void**)&TACC,(size_t)n_shifts*n_p*sizeof(Scalar)); }
  if(getenv("OCA_POLY_CONG")){
    M((void**)&pp1,(size_t)n_c*sizeof(Scalar));M((void**)&pp2,(size_t)n_c*sizeof(Scalar));
    M((void**)&pp3,(size_t)n_c*sizeof(Scalar));M((void**)&pp4,(size_t)n_c*sizeof(Scalar)); }
  M((void**)&Ap_,(size_t)n_c*sizeof(Scalar));M((void**)&okf,npt*sizeof(int));
  Scalar *r2acc=nullptr,*obscnt=nullptr;   // ROUND 10: intrinsics damping accumulators
  if(CD==9&&intr_damp>0.0){ M((void**)&r2acc,ncam*sizeof(Scalar)); M((void**)&obscnt,ncam*sizeof(Scalar)); }
  // OCA_NSHIFTS=<n>: override the multi-shift menu width (default = caller's
  // n_shifts, i.e. 5). n=1 collapses to a single shift at lam_cam, which is the
  // control arm for "does the menu pay for itself at all". grid_down already
  // self-clamps to L-1, so L=1 is a well-formed single-shift solve.
  static const int nshifts_env = [](){
    const char* e = getenv("OCA_NSHIFTS"); return e ? std::atoi(e) : 0; }();
  int L = nshifts_env > 0 ? nshifts_env : n_shifts;
  std::vector<Scalar*> xs(L),ps(L);
  for(int l=0;l<L;++l){ M((void**)&xs[l],(size_t)n_c*sizeof(Scalar)); M((void**)&ps[l],(size_t)n_c*sizeof(Scalar)); }
  DeviceState s_new; AllocState(s_new,ncam,npt,CD==9);
  // ROUND 11 scratch: one full-width vector for the broadcast operand and one
  // for the operator's full-width output. Allocated only when sharing is on.
  Scalar *bcast_in=nullptr,*bcast_out=nullptr;
  if(shared_intr){ M((void**)&bcast_in,(size_t)n_cf*sizeof(Scalar));
                   M((void**)&bcast_out,(size_t)n_cf*sizeof(Scalar)); }
  // Reduced-space block factors: 6x6 per camera + 3x3 per calibration group.
  Scalar *Bp=nullptr,*Bg=nullptr;
  const bool block_red_alloc = block_eq && shared_intr && CD==9;
  if(block_red_alloc){ M((void**)&Bp,(size_t)36*ncam*sizeof(Scalar));
                 M((void**)&Bg,(size_t)9*ncalib*sizeof(Scalar)); }
  // Evaluated per outer via block_on (scheduler-aware).
  auto BlockRedOn=[&](){ return block_on && shared_intr && CD==9; };
  // B : reduced -> full.
  auto Broadcast=[&](const Scalar* vr,Scalar* vfull){
    MFCalibBroadcast<<<GridSize(ncam),256>>>(vr,p.calib_of_cam,ncam,ncalib,vfull); };
  // B^T : full -> reduced. Zeroes the calibration section first, since the
  // group entries accumulate.
  auto Reduce=[&](const Scalar* vfull,Scalar* vr){
    CUDA_CHECK(cudaMemset(vr+6*ncam,0,(size_t)3*ncalib*sizeof(Scalar)));
    MFCalibReduce<<<GridSize(ncam),256>>>(vfull,p.calib_of_cam,ncam,ncalib,vr); };

  // Apply L^-1 (mode 0) or L^-T (mode 1) of the reduced-space block factor:
  // 6x6 per camera on the pose section, 3x3 per group on the calibration tail.
  auto BlockSolveRed=[&](const Scalar* in,int mode,Scalar* out){
    MFBlockSolve<6><<<GridSize(ncam),256>>>(Bp,in,ncam,mode,out);
    MFBlockSolve<3><<<GridSize(ncalib),256>>>(Bg,in+6*ncam,ncalib,mode,out+6*ncam);
  };
  auto DoRetract=[&](const Scalar* d,const DeviceState& out){
    if constexpr (CD==9) RetractDof9(p,s,d,out); else Retract(p,s,d,out); };
  cublasHandle_t blas; cublasCreate(&blas);
  // ---- robust kernel state -------------------------------------------------
  // rk_a2 is the effective squared scale. Fixed for huber/cauchy; for the
  // student-t it is re-estimated by EM once per ASSEMBLY (so it is frozen
  // across a candidate menu and across inner retries -- one consistent
  // objective per outer, which is what candidate scoring requires).
  Scalar rk_a2 = rk_scale2;
  Scalar* rk_sv = nullptr;            // per-obs |r|^2, student-t only
  if(rk==3) M((void**)&rk_sv,(size_t)nobs*sizeof(Scalar));
  auto RobustUpdateScale=[&](){
    if(rk!=3) return;
    KernelResidSq<<<GridSize(nobs),256>>>(p.cam_idx,p.pt_idx,p.uv,s.R,s.t,s.X,
        INTR_F(p,s),INTR_K1(p,s),INTR_K2(p,s),nobs,rk_sv);
    if(!(rk_a2>0.0)){
      // auto-init: median(|r|^2) ~ 1.386 sigma^2 for an isotropic 2-D normal.
      std::vector<Scalar> h(nobs);
      CUDA_CHECK(cudaMemcpy(h.data(),rk_sv,(size_t)nobs*sizeof(Scalar),cudaMemcpyDeviceToHost));
      std::nth_element(h.begin(),h.begin()+h.size()/2,h.end());
      const Scalar med=h[h.size()/2];
      rk_a2 = rk_nu*std::max(med/(Scalar)1.386,(Scalar)1e-8);
    }
    Scalar sig2 = rk_a2/rk_nu;
    Scalar* d_acc; CUDA_CHECK(cudaMalloc(&d_acc,sizeof(Scalar)));
    for(int em=0; em<3; ++em){
      CUDA_CHECK(cudaMemset(d_acc,0,sizeof(Scalar)));
      KernelTEMSum<<<GridSize(nobs),256>>>(rk_sv,nobs,rk_nu,sig2,d_acc);
      Scalar num; CUDA_CHECK(cudaMemcpy(&num,d_acc,sizeof(Scalar),cudaMemcpyDeviceToHost));
      sig2 = std::max(num/(2.0*(Scalar)nobs),(Scalar)1e-10);
    }
    CUDA_CHECK(cudaFree(d_acc));
    rk_a2 = rk_nu*sig2;
  };
  RobustUpdateScale();   // the initial cost below already needs a valid scale
  Scalar cost=ComputeCost(p,s,rk,rk_a2);
  int cheir0=CountCheiralityViolations(p,s);
  RunLog log; log.iters.push_back(0); log.costs.push_back(cost);
  // OCA_LAM_FLOOR=<exp>: override the damping floor's decade offset below lam0.
  // Default 8 reproduces the historical lam0*1e-8 exactly (bit-compat).
  static const double lam_floor_dec = [](){
    const char* e = getenv("OCA_LAM_FLOOR"); return e ? std::atof(e) : 8.0; }();
  // OCA_LAM0=<v>: override the caller's initial lambda (research knob for the
  // final-4585 opening-policy investigation). Unset = caller's value, bit-compat.
  static const double lam0_env = [](){
    const char* e = getenv("OCA_LAM0"); return e ? std::atof(e) : 0.0; }();
  if(lam0_env>0.0) lam0=(Scalar)lam0_env;
  Scalar lam_cam=lam0, lam_floor=lam0*std::pow((Scalar)10.0,(Scalar)(-lam_floor_dec));
  MFStats st; Scalar prev_bnorm=-1.0;
  int n_accept=0,n_reject=0,rej_streak=0;
  bool tau_lam_off=false;   // OCA_TAU_LAM_AUTO latch (see the tau floor below)
  int clean_streak=0;       // OCA_PRUNE_REARM: consecutive uncontested accepts
  Scalar tau_lam_floor_cur=std::numeric_limits<Scalar>::infinity();  // ratchet state
  int last_win_sh=0;   // OCA_CAND_PRUNE: previous outer's winning shift
  Scalar last_rel=1.0; // relative progress of the last ACCEPTED outer
  // Early-stopping state (inert unless the caller enables the tolerances).
  int stuck=0; bool converged=false; Scalar prev_cost=cost;
  // OCA_FTOL persistent-flatness stop (see the accept branch). Default off.
  static const double ftol_env = [](){
    const char* e=getenv("OCA_FTOL"); return e?std::atof(e):0.0; }();
  static const int ftol_k_env = [](){
    const char* e=getenv("OCA_FTOL_K"); return e?std::atoi(e):5; }();
  int ftol_streak=0;
  // OCA_STOP_WINDOW=<n>: outers to look back over before honouring a
  // consecutive-failure stop. 0 = legacy behaviour (bit-compat default).
  static const int stop_window = [](){
    const char* e = getenv("OCA_STOP_WINDOW"); return e ? std::atoi(e) : 0; }();
  // AUDIT 2026-08-22: lambda at the START of the current reject streak, so an
  // accept won by the tau ratchet can unwind the lambda escalation it did not
  // need. See the accept branch below.
  Scalar lam_pre_streak=lam0;
  // AUDIT 2026-08-23: persistent point damping. The tau ratchet used to reset
  // to the CLI value after every accept, so a scene whose usable tau is far
  // above it re-derived that fact through 2-3 rejected solves on EVERY outer
  // iteration (dubrovnik-142: 150 rejects/61 accepts, 55%+ of solve attempts
  // wasted; final-4585: 31 rejected solves before even crossing the baseline's
  // cost). tau_base moves geometrically halfway toward any tau that wins a
  // contested accept and decays x0.5 (floored at the CLI value) on clean
  // accepts, so it can both lock in (d-142 wants 3e-1, 100x the default) and
  // track a moving target (f-4585, where no static tau works). CD=6 untouched.
  // V2 (2026-08-23): warm-started ladder. V1 (raise the base itself) failed its
  // gate -- elevated first-attempt tau degraded accepted-step quality on both
  // patients. V2 keeps EVERY first attempt at the CLI tau (identical step
  // quality to the shipped policy) and only short-circuits the rediscovery:
  // on the first rejection the ladder jumps straight to the last tau that won
  // a contested accept (tau_win, decayed x0.5 per clean accept so stale
  // memory fades) instead of climbing from base by decades.
  // OCA_TAU_PT=<v>: override the caller's point-damping tau (research knob for
  // the final-4585 opening ablation). Unset = caller's value, bit-compat.
  static const double tau_pt_env = [](){
    const char* e = getenv("OCA_TAU_PT"); return e ? std::atof(e) : 0.0; }();
  if(tau_pt_env>0.0) tau_pt=(Scalar)tau_pt_env;
  // OCA_TAU_V3=<D>: adaptive retry-ladder floor, D decades below the last
  // winning tau (see the tau_eff block). Requires tau_win tracking, which is
  // enabled below whenever V3 is on, independent of --tau-persist.
  static const int tau_v3_dec = [](){
    const char* e=getenv("OCA_TAU_V3"); return e?std::atoi(e):0; }();
  Scalar tau_base=tau_pt, tau_used=tau_pt, tau_win=0.0;
  double t_asm=0,t_fac=0,t_mv=0,t_cand=0;
  // OCA_PROF_SCORE=1: sub-phase breakdown of the candidate-scoring path.
  static const bool prof_score = getenv("OCA_PROF_SCORE")!=nullptr;
  double ts_unscale=0,ts_pass1=0,ts_copy=0,ts_retract=0,ts_cost=0; long ts_n=0;
  // OCA_SCORE_STRIDE=<S>: subsampled candidate scoring (see KernelCostStride).
  // All candidates scored on obs k%S==0; the WINNER is re-scored on full data
  // before the accept decision, so trajectory semantics stay exact.
  // 1/unset = off, bit-compat.
  // OCA_JIT_J=1: on-the-fly Jacobian matvec (tier-1 Caspar-codegen adaptation;
  // see MFPass1JIT). dof9 + unshared only in this first cut. Default off.
  static const bool jit_j = getenv("OCA_JIT_J")!=nullptr;
  const bool jit_on = jit_j && CD==9 && !shared_intr;
  static const int score_stride_env = [](){
    const char* e = getenv("OCA_SCORE_STRIDE"); int v=e?std::atoi(e):1; return v<1?1:v; }();
  // PHASE-GATED: subsampled scoring only helps while candidate spreads are
  // large (the opening; spreads 10-400%). In the grind, true candidate
  // differences are ~1e-5 relative -- below the subset estimate's resolution
  // -- and subsampling picks noise: measured on venice, stride-10 everywhere gave
  // 86% of subset winners rejected on full rescore, +11% final, 5x wall.
  // score_stride is therefore per-outer: env stride while the last accepted
  // relative improvement exceeds 1e-3, full scoring once the grind begins.
  int score_stride = score_stride_env;
  std::vector<std::string> jrows;
  std::chrono::steady_clock::time_point t0;
  // ---- OCA_LEARN_LOG=<path>: opt-in JSONL for the learned-damping study ----
  // (agent_rev/learn Exp 1). One "c" record per scored menu candidate, one
  // "al" record per alpha-grid evaluation, one "a" record per attempt
  // (accepted outer or inner retry), plus one "hdr" record. Everything is
  // guarded by learn_f so the flag-off path is unchanged (a single getenv +
  // fopen at solver entry). Logged runs add one Dnrm2 (blocking) per menu
  // candidate for the step-norm feature: NEVER use a logged run for
  // wall-clock claims.
  FILE* learn_f=nullptr;
  { const char* e=getenv("OCA_LEARN_LOG"); if(e&&*e) learn_f=std::fopen(e,"w"); }
  long learn_att_id=0;
  LoadLearnPolicy();   // OCA_LEARN_POLICY / OCA_LEARN_MODE (no-op when unset)
  if(learn_f){
    const int gd_env=[](){ const char* e=getenv("OCA_GRID_DOWN");
      return e?std::atoi(e):0; }();
    std::fprintf(learn_f,"{\"t\":\"hdr\",\"ncam\":%d,\"npt\":%d,\"nobs\":%d,"
      "\"L\":%d,\"cd\":%d,\"grid_down\":%d,\"lam0\":%.6e,\"tau_pt\":%.6e,"
      "\"cost0\":%.10e,\"ckpts\":[",
      ncam,npt,nobs,L,CD,std::min(std::max(gd_env,0),L-1),
      (double)lam_cam,(double)tau_pt,(double)cost);
    for(size_t i=0;i<ckpts.size();++i)
      std::fprintf(learn_f,"%s%d",i?",":"",ckpts[i]);
    std::fprintf(learn_f,"]}\n");
  }

  MemMark("mfree_shifted_cg solver allocations");
  CsvOpen("mfree_shifted_cg", g_csv_problem.c_str()); CsvRow(0, (double)cost);
  // ---- OCA_RI_OPEN=<n>: RESECTION-INTERSECTION OPENING PHASE ---------------
  // Haensch/Drude/Hellwich 2016 (ISPRS III-3:43) measure first-order
  // alternation (cameras given points, points given cameras) descending
  // FASTEST in the early iterations, and stalling later -- the exact
  // complement of our diagnosed profile on final-4585 ("our finisher wins,
  // our opening loses", warm-starting from Caspar descends 4.2% below it).
  // An RI sweep here costs one assembly + two block solves (~25 ms at 29M
  // obs) against ~550 ms for a full outer, cannot storm (no retries, no CG,
  // no menu), and runs entirely BEFORE the first candidate menu, so it
  // cannot perturb any selection input -- it only moves the point the main
  // solver starts from. Each sweep is accepted only if the TRUE cost drops;
  // the first non-improving sweep ends the phase (that is the documented
  // stall, and it is the signal to hand over to the real solver).
  static const int ri_open = [](){ const char* e=getenv("OCA_RI_OPEN");
    return e? std::atoi(e) : 0; }();
  // OCA_RI_AT=<k>: run the RI sweeps AFTER outer k instead of before outer 0.
  // Motivation (2026-09-04): the RI dose-response shows the basin is committed
  // by ~3 greedy sweeps AT THE START -- and the branched rollouts show the
  // greedy/horizon disagreement vanishes after ~5 outers. So greedy
  // alternation is destructive only while the basin is still being chosen;
  // once the champion has settled it, RI cannot commit anything it has not
  // already committed, and Haensch's stall property makes it a cheap polish
  // step (~0.28 s/sweep vs ~0.5-15 s per champion outer). This tests the
  // inverted schedule the opening experiment could not.
  static const int ri_at = [](){ const char* e=getenv("OCA_RI_AT");
    return e? std::atoi(e) : -1; }();
  // RunRIPhase: the sweeps, callable either before outer 0 (OCA_RI_OPEN) or
  // after outer OCA_RI_AT. Returns the number of accepted sweeps.
  auto RunRIPhase=[&](int nsweeps)->int{
    Scalar* RIb=nullptr; Scalar* RId=nullptr;
    M((void**)&RIb,(size_t)CD*CD*ncam*sizeof(Scalar));
    M((void**)&RId,(size_t)n*sizeof(Scalar));
    Scalar ri_lam = lam_cam, ri_tau = std::max(tau_base,(Scalar)1e-6);
    int ri_done=0;
    const int ri_open = nsweeps;
    for(int it=0; it<ri_open; ++it){
      CUDA_CHECK(cudaMemset(Hcc,0,(size_t)CD*CD*ncam*sizeof(Scalar)));
      CUDA_CHECK(cudaMemset(Cdiag,0,3ul*npt*sizeof(Scalar)));
      CUDA_CHECK(cudaMemset(bc,0,(size_t)n_cf*sizeof(Scalar)));
      CUDA_CHECK(cudaMemset(bp,0,(size_t)n_p*sizeof(Scalar)));
      if(mf_fp32) MFAssemble<CD,float><<<GridSize(nobs),256>>>(p.cam_idx,p.pt_idx,p.uv,s.R,s.t,s.X,
          INTR_F(p,s),INTR_K1(p,s),INTR_K2(p,s),
          p.obs2pslot,p.obs2cslot,nobs,Hcc,Cdiag,Gp32,Gc32,Bo32,bc,bp,k2mask,r2acc,obscnt,rk,rk_a2);
      else        MFAssemble<CD,Scalar><<<GridSize(nobs),256>>>(p.cam_idx,p.pt_idx,p.uv,s.R,s.t,s.X,
          INTR_F(p,s),INTR_K1(p,s),INTR_K2(p,s),
          p.obs2pslot,p.obs2cslot,nobs,Hcc,Cdiag,Gp,Gc,Bo,bc,bp,k2mask,r2acc,obscnt,rk,rk_a2);
      // RESECTION half: per-camera damped block solve H_cc dx_c = b_c with the
      // point coupling dropped, points held FIXED. Accepted on true cost.
      CUDA_CHECK(cudaMemcpy(RIb,Hcc,(size_t)CD*CD*ncam*sizeof(Scalar),cudaMemcpyDeviceToDevice));
      MFBlockDampDiag<CD><<<GridSize(ncam),256>>>(RIb,ncam,ri_lam);
      MFBlockChol<CD><<<GridSize(ncam),256>>>(RIb,ncam,(Scalar)1e-10,nullptr);
      MFBlockSolve<CD><<<GridSize(ncam),256>>>(RIb,bc,ncam,0,w);
      CUDA_CHECK(cudaMemset(RId,0,(size_t)n*sizeof(Scalar)));
      MFBlockSolve<CD><<<GridSize(ncam),256>>>(RIb,w,ncam,1,RId);
      KernelNegateInPlace<<<GridSize(n),256>>>(RId,n);
      DoRetract(RId,s_new);
      Scalar c_res = ComputeCost(p,s_new,rk,rk_a2);
      bool any=false;
      if(std::isfinite((double)c_res) && c_res < cost){
        CopyState(s,s_new,ncam,npt); cost=c_res; any=true;
        ri_lam=std::max(ri_lam*(Scalar)0.5,lam_floor);
      } else ri_lam*=10.0;
      // INTERSECTION half: re-linearize at the (possibly updated) cameras and
      // solve (V+tau D) dx_p = b_p per point, cameras held FIXED. This is the
      // half that must NOT reuse the resection linearization -- that was the
      // first design's flaw (simultaneous updates = block-Jacobi, rejected on
      // every sweep of final-4585 because both halves overshoot together).
      if(any){
        CUDA_CHECK(cudaMemset(Cdiag,0,3ul*npt*sizeof(Scalar)));
        CUDA_CHECK(cudaMemset(Hcc,0,(size_t)CD*CD*ncam*sizeof(Scalar)));
        CUDA_CHECK(cudaMemset(bc,0,(size_t)n_cf*sizeof(Scalar)));
        CUDA_CHECK(cudaMemset(bp,0,(size_t)n_p*sizeof(Scalar)));
        if(mf_fp32) MFAssemble<CD,float><<<GridSize(nobs),256>>>(p.cam_idx,p.pt_idx,p.uv,s.R,s.t,s.X,
            INTR_F(p,s),INTR_K1(p,s),INTR_K2(p,s),
            p.obs2pslot,p.obs2cslot,nobs,Hcc,Cdiag,Gp32,Gc32,Bo32,bc,bp,k2mask,r2acc,obscnt,rk,rk_a2);
        else        MFAssemble<CD,Scalar><<<GridSize(nobs),256>>>(p.cam_idx,p.pt_idx,p.uv,s.R,s.t,s.X,
            INTR_F(p,s),INTR_K1(p,s),INTR_K2(p,s),
            p.obs2pslot,p.obs2cslot,nobs,Hcc,Cdiag,Gp,Gc,Bo,bc,bp,k2mask,r2acc,obscnt,rk,rk_a2);
      }
      if(mf_fp32) MFPointFactor<float><<<GridSize(npt),256>>>(Bo32,Cdiag,p.point_obs_offsets,p.point_obs_list,ri_tau,npt,Rf,okf);
      else        MFPointFactor<Scalar><<<GridSize(npt),256>>>(Bo,Cdiag,p.point_obs_offsets,p.point_obs_list,ri_tau,npt,Rf,okf);
      CUDA_CHECK(cudaMemset(RId,0,(size_t)n*sizeof(Scalar)));
      MFVinvApply<<<GridSize(npt),256>>>(Rf,bp,npt,RId+n_cf);
      KernelNegateInPlace<<<GridSize(n),256>>>(RId,n);
      DoRetract(RId,s_new);
      const Scalar c_int = ComputeCost(p,s_new,rk,rk_a2);
      if(std::isfinite((double)c_int) && c_int < cost){
        CopyState(s,s_new,ncam,npt); cost=c_int; any=true;
        ri_tau=std::max(ri_tau*(Scalar)0.5,(Scalar)1e-12);
      } else ri_tau*=10.0;
      if(any){
        ++ri_done;
        log.costs.push_back((double)cost); CsvRow((int)log.costs.size()-1,(double)cost);
        if(verbose) std::printf("  [ri-open] sweep %d cost=%.6e lam=%.2e tau=%.2e\n",
                                it+1,(double)cost,(double)ri_lam,(double)ri_tau);
      } else {
        if(verbose) std::printf("  [ri-open] sweep %d stalled (lam=%.2e tau=%.2e)\n",
                                it+1,(double)ri_lam,(double)ri_tau);
        break;   // documented RI stall: hand over to the main solver
      }
    }
    // OCA_RI_LAM=1: hand the RI phase's damping state to the main solver.
    // Without it the solver restarts at lam0 (measured on final-4585: RI ends
    // at lam=7.8e-2, the solver reopens at 1e2 and burns a 5-deep retry
    // ladder before its first accept). The menu can re-select from here.
    static const bool ri_lam_handover = getenv("OCA_RI_LAM")!=nullptr;
    if(ri_lam_handover && ri_done>0){
      lam_cam=std::max(ri_lam,lam_floor); lam_pre_streak=lam_cam;
      if(CD==9 && tau_persist) tau_win=ri_tau;
      if(verbose) std::printf("  [ri-open] handover lam=%.3e tau=%.3e\n",
                              (double)lam_cam,(double)ri_tau);
    }
    if(verbose) std::printf("  [ri-open] %d accepted sweeps, cost -> %.6e\n",ri_done,(double)cost);
    cudaFree(RIb); cudaFree(RId);
    return ri_done;
  };
  if(ri_open>0 && ri_at<0) RunRIPhase(ri_open);
  // AUDIT 2026-08-22: inner LM retry. A rejected step leaves the state -- and
  // therefore the entire assembly (Hcc, Gp/Gc/Bo, bc, bp, and the intrinsics
  // damping) -- bit-for-bit unchanged; only lam and tau_eff move. The original
  // loop nevertheless spent a whole outer iteration and a full re-assembly on
  // every reject, so final-4585 --dof9 burned 35 of its 61 iterations without
  // advancing the state. Retrying inside the outer step reuses the assembly
  // and stops rejects consuming the iteration budget. CD=6 keeps round-9
  // behaviour exactly (max_inner_retry is forced to 0 at the call site).
  bool need_assembly=true; int retries=0;
  bool pf_obs_dirty=true;   // GAP-4090 F5: R0f stale whenever assembly reran
  for(int k=0;k<max_iter;){
   if(need_assembly){
    if (g_bal_ptr && std::find(g_dump_iters.begin(), g_dump_iters.end(), k) != g_dump_iters.end())
      DumpBalState(g_dump_prefix + "_it" + std::to_string(k) + ".txt", *g_bal_ptr, s, ncam, npt);
    if(prof){cudaDeviceSynchronize();t0=now();}
    CUDA_CHECK(cudaMemset(Hcc,0,(size_t)CD*CD*ncam*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(Cdiag,0,3ul*npt*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(bc,0,(size_t)n_cf*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(bp,0,(size_t)n_p*sizeof(Scalar)));
    if(r2acc){ CUDA_CHECK(cudaMemset(r2acc,0,ncam*sizeof(Scalar)));
               CUDA_CHECK(cudaMemset(obscnt,0,ncam*sizeof(Scalar))); }
    // Student-t: refresh the scale from the CURRENT state, then freeze it for
    // this outer. Matches the CPU port, which drives the update from Assemble
    // and therefore skips it on assembly-reusing inner retries.
    RobustUpdateScale();
    if(mf_fp32) MFAssemble<CD,float><<<GridSize(nobs),256>>>(p.cam_idx,p.pt_idx,p.uv,s.R,s.t,s.X,
        INTR_F(p,s),INTR_K1(p,s),INTR_K2(p,s),
        p.obs2pslot,p.obs2cslot,nobs,Hcc,Cdiag,Gp32,Gc32,Bo32,bc,bp,k2mask,r2acc,obscnt,rk,rk_a2);
    else        MFAssemble<CD,Scalar><<<GridSize(nobs),256>>>(p.cam_idx,p.pt_idx,p.uv,s.R,s.t,s.X,
        INTR_F(p,s),INTR_K1(p,s),INTR_K2(p,s),
        p.obs2pslot,p.obs2cslot,nobs,Hcc,Cdiag,Gp,Gc,Bo,bc,bp,k2mask,r2acc,obscnt,rk,rk_a2);
    if(r2acc) KernelDampIntr9<<<GridSize(ncam),256>>>(Hcc,INTR_F(p,s),r2acc,obscnt,ncam,intr_damp,k2mask);
    pf_obs_dirty=true;   // Bo/Cdiag just rebuilt
    if(prof){cudaDeviceSynchronize();t_asm+=std::chrono::duration<double>(now()-t0).count();}
   }  // end if(need_assembly)
    if(prof){cudaDeviceSynchronize();t0=now();}
    // ROUND 10 (CD==9 only): ratchet the point damping with CONSECUTIVE
    // rejects. The reject loop multiplies lam_cam by 10, but lam_cam only
    // enters the CAMERA system -- the point back-substitution V^-1 b_p is
    // damped by the FIXED tau_pt, so a state where that step is toxic
    // (measured on final-4585 --dof9: a candidate with |x_c|=1.8e-3 and the
    // pure point relaxation evaluating 2000x worse than the current cost)
    // could never be escaped: lambda -> inf zeroed only half the step, and
    // the run sat at 113 consecutive null rejects. Escalating tau by 10x per
    // consecutive reject AFTER the first restores the classic LM limit (whole
    // step -> 0 => eventual acceptance) while leaving isolated rejects -- the
    // normal texture of a healthy run -- completely untouched: coupling tau
    // to lam_cam itself overdamped healthy scenes (final-3068 went 1.71M ->
    // 4.78M because tau stayed elevated while lam decayed back down after
    // every transient reject streak). CD=6 keeps round-9 behaviour exactly.
    // AUDIT 2026-08-22: escalate from the FIRST reject, not the second. lam
    // damps only the camera block and tau only the point block, so a reject
    // that escalates lam alone leaves the point relaxation -- the toxic half
    // on this scene -- untouched, and the streak runs until tau finally moves.
    if(score_stride_env>1)
      score_stride = (last_rel > (Scalar)1e-3) ? score_stride_env : 1;
    // OCA_LEARN_LOG: snapshot the attempt's pre-action state (lam/streak/cost
    // move inside the accept branch below, so they must be captured here).
    const Scalar learn_lam_att=lam_cam, learn_cost_att=cost;
    const int learn_streak_att=rej_streak;
    const long learn_ev0=st.cand_evals, learn_mg0=st.menu_gated,
               learn_mv0=st.matvecs;
    std::chrono::steady_clock::time_point learn_t0;
    if(learn_f) learn_t0=now();
    Scalar tau_eff = tau_base;
    if(CD==9 && rej_streak>0){
      tau_eff = tau_base*std::pow((Scalar)10.0,(Scalar)std::min(rej_streak,12));
      if(tau_persist && tau_win>tau_eff)
        tau_eff = tau_win*std::pow((Scalar)10.0,(Scalar)(rej_streak-1));
      // OCA_TAU_V3=<D>: V3 ADAPTIVE LADDER FLOOR. Engineered around both prior
      // failure modes: V1 (raising the base degraded first-attempt step
      // quality) -- the FIRST attempt stays at tau_base, untouched; V2
      // (tau_persist jumps retries straight to the winning tau, removing the
      // low-tau re-probes that ARE the descent mechanism on final-4585:
      // measured 7,007 outers / 99% rejects / stuck at 1.15e7 without them).
      // V3 keeps the full probe LADDER but starts it from a floor trailing
      // the last winning tau by D decades: retries still probe D rungs below
      // the winner (re-probes preserved), but skip the deep decades that never
      // win (final-4585's storm spends most of its 2,645 outers climbing from
      // 1e-7 toward ~1e-4 again and again). Floor fades with tau_win's 0.5x
      // decay on clean accepts, so a scene that stops needing it drifts back.
      // Unset/0 = off, bit-compat.
      if(tau_v3_dec>0 && tau_win>0.0){
        const Scalar lo = tau_win*std::pow((Scalar)10.0,(Scalar)(-tau_v3_dec));
        const Scalar base_eff = std::max(tau_base, lo);
        Scalar cand = base_eff*std::pow((Scalar)10.0,(Scalar)std::min(rej_streak,12));
        if(cand>tau_eff) tau_eff=cand;
      }
    }
    // OCA_TAU_LAM=<c>: UNIFORM DAMPING FLOOR (basin study 2026-09). Caspar-f64
    // damps every block -- points included -- with ONE relative Marquardt
    // multiplier that decays smoothly from 1.0, while our tau_pt is a static
    // 1e-7: at the first accepted outer the cameras carry lam ~ 1e0..1e5
    // (relative, equilibrated space) while the point half-step is essentially
    // an UNDAMPED Newton jump. On thin-track scenes (ladybug: 48% of points
    // have 2 observations) that jump commits the basin in the first few
    // outers; the factor ablation (agent_rev/basin) shows the tau floor is
    // the ONLY single factor that moves the ladybug endpoint. This flag
    // couples the point damping to the camera damping: every attempt uses
    // tau_eff >= c * lam_cam, so the point block sees the same decaying
    // trust region as the cameras (c=1 == Caspar's uniform diag). Both
    // lam_cam and tau are RELATIVE dampings (lam is an additive shift in the
    // equilibrated camera space, tau multiplies diag(V)), so c is
    // dimensionless. Reject escalations (lam x10) lift the point damping
    // automatically; the existing streak ratchet still applies on top via
    // the max. Unset/0 = off, bit-compat.
    // OCA_TAU_LAM_K=<k>: WINDOWED coupling -- apply the uniform floor only
    // while fewer than k outers have been ACCEPTED. The cross-restart study
    // (agent_rev/basin §2) shows the ladybug-class basin is irreversibly
    // committed in accepted outers 1-3; the uniform floor is only needed
    // there. Left on permanently (k=0 = unlimited), the coupling re-creates
    // the final-4585 reject storm it was meant to prevent: tau collapses to
    // the floor WITH lambda after every recentre, re-probing the toxic point
    // relaxation (measured: 4,667 rejects / 600 outers, endpoint +55% vs
    // champion). With k set, outer k+1 onward is EXACTLY the shipped
    // asymmetric policy. k=10 covers every measured commitment window.
    static const double tau_lam_c = [](){
      const char* e=getenv("OCA_TAU_LAM"); return e?std::atof(e):0.0; }();
    static const int tau_lam_k = [](){
      const char* e=getenv("OCA_TAU_LAM_K"); return e?std::atoi(e):0; }();
    // OCA_TAU_LAM_AUTO=<r>: RUNTIME DISCRIMINATOR (2026-09-05). The uniform
    // floor helps almost everywhere but is catastrophic on the final-4585
    // class (+55%), and the basin study measured and REFUTED every a-priori
    // separator it tried (obs/pt, 2-obs fraction, init cost/obs, pt/cam,
    // obs/cam, outer-1 signature): that class is identifiable only by
    // BEHAVIOUR. Its behavioural signature is unproductive damping -- the
    // coupling re-probes a toxic point relaxation, so rejects pile up per
    // accepted outer (4,667 rejects / 600 outers there, vs a handful on the
    // ladybug class where the floor pays). So: keep the floor while it is
    // productive, and retire it PERMANENTLY once the observed reject-to-
    // accept ratio exceeds r (checked only after a warm-up of
    // OCA_TAU_LAM_AUTO_MIN accepts, default 3, so the commitment window
    // 1-3 is always covered). Latching is deliberate: re-enabling would
    // re-enter the storm. r<=0 disables the discriminator.
    static const double tau_lam_auto = [](){
      const char* e=getenv("OCA_TAU_LAM_AUTO"); return e?std::atof(e):0.0; }();
    static const int tau_lam_auto_min = [](){
      const char* e=getenv("OCA_TAU_LAM_AUTO_MIN"); return e?std::atoi(e):3; }();
    if(tau_lam_c>0.0 && tau_lam_auto>0.0 && !tau_lam_off &&
       n_accept>=tau_lam_auto_min &&
       (double)n_reject > tau_lam_auto*(double)n_accept){
      tau_lam_off=true;
      if(verbose) std::printf("  [tau-lam] auto-off at outer %d "
                              "(rejects %d / accepts %d > %.2f)\n",
                              k,n_reject,n_accept,tau_lam_auto);
    }
    // OCA_TAU_LAM_RATCHET=1 (2026-09-05): MONOTONE floor. Diagnosis of the
    // final-4585 regression: with the plain coupling, tau collapses back DOWN
    // together with lambda after every recentre, so the toxic point
    // relaxation is re-probed again and again (4,667 rejects). The ladybug
    // class, by contrast, only needs the floor to be HIGH EARLY -- once the
    // basin is chosen (outers 1-3) it does not care. A floor that never rises
    // back after it has decayed, i.e. tau_floor = min(tau_floor, c*lam),
    // therefore gives the ladybugs their early uniform damping while making
    // the final-4585 storm unreachable, because the floor cannot follow
    // lambda back up. This tests whether the two regimes' requirements are
    // genuinely incompatible or only appear so under a lambda-tracking floor.
    static const bool tau_lam_ratchet = getenv("OCA_TAU_LAM_RATCHET")!=nullptr;
    // OCA_TAU_LAM_ANNEAL=<gamma>: c_k = c*gamma^n_accept -- a one-parameter
    // family interpolating smoothly between K=1 (gamma->0) and K=inf
    // (gamma=1), so the dose-response can be measured instead of comparing
    // two endpoints of a discrete window.
    static const double tau_lam_anneal = [](){
      const char* e=getenv("OCA_TAU_LAM_ANNEAL"); return e?std::atof(e):0.0; }();
    // OCA_TAU_LAM_MAXOBS=<m>: apply the floor ONLY to points with <= m
    // observations (thin tracks). 0 = every point (legacy global floor).
    static const int tau_lam_maxobs = [](){
      const char* e=getenv("OCA_TAU_LAM_MAXOBS"); return e?std::atoi(e):0; }();
    // OCA_TAU_LAM_COND=<t>: gate the per-point floor on the CONDITIONING of
    // the undamped point block (min/max of the R0f diagonal) instead of the
    // track length. Takes precedence over MAXOBS when set.
    static const double tau_lam_cond = [](){
      const char* e=getenv("OCA_TAU_LAM_COND"); return e?std::atof(e):0.0; }();
    Scalar tau_floor_now = 0.0;
    if(tau_lam_c>0.0 && !tau_lam_off && (tau_lam_k<=0 || n_accept<tau_lam_k)){
      Scalar tl=(Scalar)tau_lam_c*lam_cam;
      if(tau_lam_anneal>0.0)
        tl *= (Scalar)std::pow(tau_lam_anneal,(double)n_accept);
      if(tau_lam_ratchet){
        if(tl>tau_lam_floor_cur) tl=tau_lam_floor_cur;   // never rise again
        tau_lam_floor_cur=tl;
      }
      tau_floor_now = tl;
      // With per-point selection the floor is applied inside the factor
      // kernel (thin tracks only); globally it just raises tau_eff.
      if(tau_lam_maxobs<=0 && tau_lam_cond<=0.0 && tl>tau_eff) tau_eff=tl;
    }
    tau_used = tau_eff;
    if(tau_split){
      if(pf_obs_dirty){
        if(mf_fp32) MFPointFactorObs<float><<<GridSize(npt),256>>>(Bo32,p.point_obs_offsets,p.point_obs_list,npt,R0f);
        else        MFPointFactorObs<Scalar><<<GridSize(npt),256>>>(Bo,p.point_obs_offsets,p.point_obs_list,npt,R0f);
        pf_obs_dirty=false;
      }
      if((tau_lam_maxobs>0 || tau_lam_cond>0.0) && tau_floor_now>tau_eff)
        MFPointFactorTauSel<<<GridSize(npt),256>>>(Cdiag,R0f,p.point_obs_offsets,
            tau_eff,tau_floor_now,tau_lam_maxobs,(Scalar)tau_lam_cond,npt,Rf,okf);
      else
        MFPointFactorTau<<<GridSize(npt),256>>>(Cdiag,R0f,tau_eff,npt,Rf,okf);
    }
    else if(mf_fp32) MFPointFactor<float><<<GridSize(npt),256>>>(Bo32,Cdiag,p.point_obs_offsets,p.point_obs_list,tau_eff,npt,Rf,okf);
    else        MFPointFactor<Scalar><<<GridSize(npt),256>>>(Bo,Cdiag,p.point_obs_offsets,p.point_obs_list,tau_eff,npt,Rf,okf);
    // b' = b_c - H_cp V^-1 b_p
    MFVinvApply<<<GridSize(npt),256>>>(Rf,bp,npt,uu);
    // OCA_RHO_PT=1 (math review 2026-09-02, finding 1): preds[l] accumulates
    // only the CAMERA-Schur-space quadratic decrease. The full-space model
    // decrease of the eliminated step additionally contains the CONSTANT
    // point-block term 1/2 * b_p^T (V+tau D)^-1 b_p -- identical for every
    // candidate (so selection is unaffected) but missing from rho's
    // denominator, inflating rho -> Nielsen under-damps -> feeds reject
    // storms. uu = V^-1 b_p is already computed on this line; the fix is one
    // Ddot per attempt. Selection-facing via the lambda trajectory: needs the
    // full trajectory-validation protocol, hence opt-in.
    static const bool rho_pt_fix = getenv("OCA_RHO_PT")!=nullptr;
    Scalar pred_pt = 0.0;
    if(rho_pt_fix){ Scalar v=0; cublasDdot(blas,n_p,bp,1,uu,1,&v); pred_pt=0.5*v; }
    CUDA_CHECK(cudaMemset(corr,0,(size_t)n_cf*sizeof(Scalar)));
    if(mf_fp32) MFRhsPrime<CD,float><<<GridSize(nobs),256>>>(Gp32,p.mf_scam,p.mf_spt,uu,nobs,corr);
    else        MFRhsPrime<CD,Scalar><<<GridSize(nobs),256>>>(Gp,p.mf_scam,p.mf_spt,uu,nobs,corr);
    // bc and corr live in the full space; the reduced rhs is B^T (bc - corr).
    if(shared_intr){
      CUDA_CHECK(cudaMemcpy(bcast_out,bc,(size_t)n_cf*sizeof(Scalar),cudaMemcpyDeviceToDevice));
      { const Scalar m1=-1.0; cublasDaxpy(blas,n_cf,&m1,corr,1,bcast_out,1); }
      Reduce(bcast_out,bprime);
    } else {
      CUDA_CHECK(cudaMemcpy(bprime,bc,(size_t)n_cf*sizeof(Scalar),cudaMemcpyDeviceToDevice));
      { const Scalar m1=-1.0; cublasDaxpy(blas,n_cf,&m1,corr,1,bprime,1); }
    }
    if(use_equil){
      // GAP-4090 F3 (2026-09-03): when the BLOCK congruence is active this
      // outer, the Jacobi vector E is never read -- KvS and Score both go
      // through BlockSolve, and the Bk build reads Gc/Gp+Rf+Hcc, not dk/E.
      // MFDiagK is a full 27-double/obs fragment stream plus 9 Vinv solves
      // per obs (~13-20 ms of the 39 ms pf+rhs at 29M obs), paid per attempt
      // including every retry. Skipping it on block outers is bit-identical.
      // With the scheduler, diag opening outers still build E as before.
      // OCA_F3_OFF=1 restores the old always-build for A/B.
      static const bool f3_off = getenv("OCA_F3_OFF")!=nullptr;
      const bool e_dead = !f3_off && ((block_on && !shared_intr) || BlockRedOn());
      if(!e_dead){
      CUDA_CHECK(cudaMemset(dk,0,(size_t)n_cf*sizeof(Scalar)));
      if(mf_fp32) MFDiagK<CD,float><<<GridSize(nobs),256>>>(Gp32,p.mf_spt,p.mf_scam,Rf,nobs,dk);
      else        MFDiagK<CD,Scalar><<<GridSize(nobs),256>>>(Gp,p.mf_spt,p.mf_scam,Rf,nobs,dk);
      MFDiagHcc<CD><<<GridSize(ncam),256>>>(Hcc,ncam,dk);
      // Equilibrate the diagonal the CG actually sees: B^T diag(S) B when the
      // intrinsics are shared, diag(S) otherwise.
      const Scalar* dk_eq=dk;
      if(shared_intr){ Reduce(dk,bcast_in); dk_eq=bcast_in; }
      if(equil_floor>0.0&&!shared_intr)
        MFMakeEquilBlocked<CD><<<GridSize(ncam),256>>>(dk,ncam,equil_floor,E);
      else
        MFMakeEquil<<<GridSize(n_c),256>>>(dk_eq,n_c,E);
      }
      if(block_on && !shared_intr){
        CUDA_CHECK(cudaMemset(Bk,0,(size_t)CD*CD*ncam*sizeof(Scalar)));
        // OCA_BLOCK_CM=1: atomics-free camera-major build (deterministic).
        static const bool block_cm = [](){
          const char* e=getenv("OCA_BLOCK_CM"); return e&&atoi(e)!=0; }();
        if(block_cm){
          if(mf_fp32) MFBlockSchurCM<CD,float><<<ncam,32>>>(Gc32,p.mf_cspt,p.mf_coff,Rf,nobs,Bk);
          else        MFBlockSchurCM<CD,Scalar><<<ncam,32>>>(Gc,p.mf_cspt,p.mf_coff,Rf,nobs,Bk);
        } else {
          if(mf_fp32) MFBlockSchur<CD,float><<<GridSize(nobs),256>>>(Gp32,p.mf_spt,p.mf_scam,Rf,nobs,Bk);
          else        MFBlockSchur<CD,Scalar><<<GridSize(nobs),256>>>(Gp,p.mf_spt,p.mf_scam,Rf,nobs,Bk);
        }
        MFBlockAddHcc<CD><<<GridSize(ncam),256>>>(Hcc,ncam,Bk);
        { static int* d_nf=nullptr; static bool once=false;
          if(!d_nf) CUDA_CHECK(cudaMalloc((void**)&d_nf,sizeof(int)));
          CUDA_CHECK(cudaMemset(d_nf,0,sizeof(int)));
          MFBlockChol<CD><<<GridSize(ncam),256>>>(Bk,ncam,(Scalar)1e-10,d_nf);
          if(!once){ int h=0; CUDA_CHECK(cudaMemcpy(&h,d_nf,sizeof(int),cudaMemcpyDeviceToHost));
            std::printf("  [blockeq] cholesky fallbacks: %d of %d cameras\n",h,ncam); once=true; } }
        CUDA_CHECK(cudaMemcpy(bscr,bprime,(size_t)n_c*sizeof(Scalar),cudaMemcpyDeviceToDevice));
        MFBlockSolve<CD><<<GridSize(ncam),256>>>(Bk,bscr,ncam,0,bprime);
      } else if(BlockRedOn()){
        // Same build, then split into the reduced space before factoring.
        CUDA_CHECK(cudaMemset(Bk,0,(size_t)CD*CD*ncam*sizeof(Scalar)));
        static const bool block_cm_r = [](){
          const char* e=getenv("OCA_BLOCK_CM"); return e&&atoi(e)!=0; }();
        if(block_cm_r){
          if(mf_fp32) MFBlockSchurCM<CD,float><<<ncam,32>>>(Gc32,p.mf_cspt,p.mf_coff,Rf,nobs,Bk);
          else        MFBlockSchurCM<CD,Scalar><<<ncam,32>>>(Gc,p.mf_cspt,p.mf_coff,Rf,nobs,Bk);
        } else {
          if(mf_fp32) MFBlockSchur<CD,float><<<GridSize(nobs),256>>>(Gp32,p.mf_spt,p.mf_scam,Rf,nobs,Bk);
          else        MFBlockSchur<CD,Scalar><<<GridSize(nobs),256>>>(Gp,p.mf_spt,p.mf_scam,Rf,nobs,Bk);
        }
        MFBlockAddHcc<CD><<<GridSize(ncam),256>>>(Hcc,ncam,Bk);
        CUDA_CHECK(cudaMemset(Bg,0,(size_t)9*ncalib*sizeof(Scalar)));
        MFBlockRedSplit<CD><<<GridSize(ncam),256>>>(Bk,p.calib_of_cam,ncam,Bp,Bg);
        { static int* d_nf=nullptr; static bool once_r=false;
          if(!d_nf) CUDA_CHECK(cudaMalloc((void**)&d_nf,sizeof(int)));
          CUDA_CHECK(cudaMemset(d_nf,0,sizeof(int)));
          MFBlockChol<6><<<GridSize(ncam),256>>>(Bp,ncam,(Scalar)1e-10,d_nf);
          MFBlockChol<3><<<GridSize(ncalib),256>>>(Bg,ncalib,(Scalar)1e-10,d_nf);
          if(!once_r){ int h=0; CUDA_CHECK(cudaMemcpy(&h,d_nf,sizeof(int),cudaMemcpyDeviceToHost));
            std::printf("  [blockeq-red] %d cams + %d calib groups, cholesky fallbacks: %d\n",
                        ncam,ncalib,h); once_r=true; } }
        CUDA_CHECK(cudaMemcpy(bscr,bprime,(size_t)n_c*sizeof(Scalar),cudaMemcpyDeviceToDevice));
        BlockSolveRed(bscr,0,bprime);
      } else
      MFScaleVec<<<GridSize(n_c),256>>>(bprime,E,n_c);
    }
    if(prof){cudaDeviceSynchronize();t_fac+=std::chrono::duration<double>(now()-t0).count();}

    // ---- operator ----
    auto Kv=[&](const Scalar* vin,Scalar* vout){
      // With shared intrinsics this evaluates B^T S B: the inner kernels are
      // untouched and still see a full 9-per-camera vector.
      const Scalar* vf=vin; Scalar* wf=vout;
      if(shared_intr){ Broadcast(vin,bcast_in); vf=bcast_in; wf=bcast_out; }
      CUDA_CHECK(cudaMemset(tacc,0,(size_t)n_p*sizeof(Scalar)));
      if(jit_on){
        if constexpr (CD==9) {
        MFPass1JIT<9><<<GridSize(nobs),256>>>(p.cam_idx,p.pt_idx,p.uv,s.R,s.t,s.X,
            INTR_F(p,s),INTR_K1(p,s),INTR_K2(p,s),vf,nobs,k2mask,rk,rk_a2,tacc);
        MFVinvApply<<<GridSize(npt),256>>>(Rf,tacc,npt,uu);
        MFHccMulJIT<9><<<GridSize(ncam),256>>>(Hcc,vf,ncam,wf);
        MFPass2JIT<9><<<GridSize(nobs),256>>>(p.cam_idx,p.pt_idx,p.uv,s.R,s.t,s.X,
            INTR_F(p,s),INTR_K1(p,s),INTR_K2(p,s),uu,nobs,k2mask,rk,rk_a2,wf);
        }
      } else if(mf_fp32){ MFPass1<CD,float><<<GridSize(nobs),256>>>(Gp32,p.mf_scam,p.mf_spt,vf,nobs,tacc);
                   MFVinvApply<<<GridSize(npt),256>>>(Rf,tacc,npt,uu);
                   MFPass2<CD,float><<<ncam,256>>>(Gc32,p.mf_cspt,p.mf_coff,uu,Hcc,vf,nobs,wf); }
      else       { MFPass1<CD,Scalar><<<GridSize(nobs),256>>>(Gp,p.mf_scam,p.mf_spt,vf,nobs,tacc);
                   MFVinvApply<<<GridSize(npt),256>>>(Rf,tacc,npt,uu);
                   MFPass2<CD,Scalar><<<ncam,256>>>(Gc,p.mf_cspt,p.mf_coff,uu,Hcc,vf,nobs,wf); }
      if(shared_intr) Reduce(wf,vout);
      ++st.matvecs;
    };
    // Equilibrated bare operator S_hat = E S E (diag path building block).
    auto SvE=[&](const Scalar* vin,Scalar* vout){
      CUDA_CHECK(cudaMemcpy(w,vin,(size_t)n_c*sizeof(Scalar),cudaMemcpyDeviceToDevice));
      MFScaleVec<<<GridSize(n_c),256>>>(w,E,n_c);
      Kv(w,vout);
      MFScaleVec<<<GridSize(n_c),256>>>(vout,E,n_c);
    };
    // OCA_POLY_CONG=<d> (math review 2026-09-02, proposal 7): polynomial
    // CONGRUENCE p(S_hat)*S_hat*p(S_hat) + sigma*I. Unlike ordinary
    // polynomial preconditioning, the two-sided congruence keeps the damping
    // as sigma*I in the transformed space, so the whole multi-shift menu
    // survives one Krylov sweep -- the same property the block congruence
    // has, but with NO factor build and no per-camera Cholesky (the block
    // arm's basin lottery lives in that factor). p is a least-squares fit of
    // t^(-1/2) on [lam_max*rho_lo, lam_max] at log-spaced nodes, refit each
    // outer from an 8-step power-iteration lam_max. Costs 2d+1 S-matvecs per
    // CG iteration and d per candidate lift; pays iff CG depth shrinks by
    // more than that factor. Unshared+equil+diag path only; off = 0.
    static const int poly_d = [](){ const char* e=getenv("OCA_POLY_CONG");
      int v=e?std::atoi(e):0; return std::min(std::max(v,0),2); }();
    const bool poly_on = poly_d>0 && use_equil && !shared_intr && !block_eq;
    static Scalar poly_c[3]={0,0,0};
    auto PolyApply=[&](const Scalar* vin,Scalar* vout){
      // vout = c0*vin + c1*S_hat*vin (+ c2*S_hat^2*vin), scratch: xpv? no --
      // uses w internally via SvE, so dedicated scratch pp1/pp2.
      SvE(vin,pp1);
      if(poly_d>=2) SvE(pp1,pp2);
      CUDA_CHECK(cudaMemcpy(vout,vin,(size_t)n_c*sizeof(Scalar),cudaMemcpyDeviceToDevice));
      { Scalar c0=poly_c[0]; cublasDscal(blas,n_c,&c0,vout,1); }
      { Scalar c1=poly_c[1]; cublasDaxpy(blas,n_c,&c1,pp1,1,vout,1); }
      if(poly_d>=2){ Scalar c2=poly_c[2]; cublasDaxpy(blas,n_c,&c2,pp2,1,vout,1); }
    };
    auto KvS=[&](const Scalar* vin,Scalar* vout){
      if(!use_equil){ Kv(vin,vout); return; }
      if(poly_on){ PolyApply(vin,pp3); SvE(pp3,pp4); PolyApply(pp4,vout); return; }
      if(block_on && !shared_intr){
        MFBlockSolve<CD><<<GridSize(ncam),256>>>(Bk,vin,ncam,1,w);   // L^-T
        Kv(w,vout);
        CUDA_CHECK(cudaMemcpy(bscr,vout,(size_t)n_c*sizeof(Scalar),cudaMemcpyDeviceToDevice));
        MFBlockSolve<CD><<<GridSize(ncam),256>>>(Bk,bscr,ncam,0,vout); // L^-1
        return;
      }
      if(BlockRedOn()){
        BlockSolveRed(vin,1,w);                                        // L^-T
        Kv(w,vout);
        CUDA_CHECK(cudaMemcpy(bscr,vout,(size_t)n_c*sizeof(Scalar),cudaMemcpyDeviceToDevice));
        BlockSolveRed(bscr,0,vout);                                    // L^-1
        return;
      }
      CUDA_CHECK(cudaMemcpy(w,vin,(size_t)n_c*sizeof(Scalar),cudaMemcpyDeviceToDevice));
      MFScaleVec<<<GridSize(n_c),256>>>(w,E,n_c);
      Kv(w,vout);
      MFScaleVec<<<GridSize(n_c),256>>>(vout,E,n_c);
    };
    if(poly_on){
      // 8-step power iteration on S_hat for lam_max, seeded from bprime.
      CUDA_CHECK(cudaMemcpy(pp2,bprime,(size_t)n_c*sizeof(Scalar),cudaMemcpyDeviceToDevice));
      Scalar lmax=1.0;
      for(int it=0;it<8;++it){
        SvE(pp2,pp1);
        cublasDnrm2(blas,n_c,pp1,1,&lmax);
        if(!(lmax>0.0)){ lmax=1.0; break; }
        Scalar inv=1.0/lmax; cublasDscal(blas,n_c,&inv,pp1,1);
        std::swap(pp1,pp2);
      }
      // LS fit of p(t)=c0+c1*t(+c2*t^2) to t^(-1/2), 32 log nodes on
      // [lmax*1e-4, lmax]; tiny normal equations solved on the host.
      { const int NN=32, m=poly_d+1; double A[3][3]={{0}},b3[3]={0};
        for(int i=0;i<NN;++i){
          double t=lmax*std::pow(1e-4,1.0-(double)i/(NN-1));
          double f=1.0/std::sqrt(t), ph[3]={1.0,t,t*t};
          for(int a=0;a<m;++a){ b3[a]+=ph[a]*f;
            for(int c=0;c<m;++c) A[a][c]+=ph[a]*ph[c]; } }
        for(int c=0;c<m;++c){ double piv=A[c][c];        // Gauss, no pivoting
          for(int r=c+1;r<m;++r){ double f2=A[r][c]/piv;
            for(int c2=c;c2<m;++c2) A[r][c2]-=f2*A[c][c2]; b3[r]-=f2*b3[c]; } }
        for(int r=m-1;r>=0;--r){ double s2=b3[r];
          for(int c=r+1;c<m;++c) s2-=A[r][c]*poly_c[c];
          poly_c[r]=s2/A[r][r]; }
        for(int a=m;a<3;++a) poly_c[a]=0.0; }
      // Transform the rhs into the congruent space: b_tilde = p(S_hat) b'.
      PolyApply(bprime,pp3);
      CUDA_CHECK(cudaMemcpy(bprime,pp3,(size_t)n_c*sizeof(Scalar),cudaMemcpyDeviceToDevice));
    }
    // ---- candidate scoring by TRUE nonlinear cost (existing rule, unchanged) ----
    Scalar best_cost=cost; int best_sh=-1,best_ck=-1; bool have=false;
    bool doomed_probe_failed=false;   // OCA_DOOMED neutrality accounting
    std::vector<Scalar> cbest_sh(L,std::numeric_limits<Scalar>::infinity());
    // OCA_RHO_LAMBDA: running model reduction per shift, from CG scalars alone
    // (phi drops 0.5*alpha_i*|r_i|^2 per step; |r^sigma|^2 = zeta^2 |r|^2).
    // Validated in the CPU port (mfree_cpu.h): rho-gated lambda control gives
    // a strictly better transient (venice-52: 9.6% lower cost at 20 iters,
    // 0.43% at 60) and converges to the same basin.
    static const bool rho_mode = getenv("OCA_RHO_LAMBDA")!=nullptr;
    // OCA_RHO_SHIFT: under rho mode, anchor the Nielsen update at the WINNING
    // shift's damping sigma_win = lam*10^(best_sh-grid_down) instead of the
    // pre-streak lambda. The accepted step solved (S+sigma_win)x=b, so
    // sigma_win is the damping the trust region actually used; discarding it
    // pins lambda at the floor and every outer re-pays a reject/escalation
    // search (326 rejects measured on final-4585 under plain rho). Validated
    // in the CPU port: venice-52 cost at it3 drops 1.23e6 -> 5.11e5.
    // Value = max decades lambda may drop per accepted outer (1 or 2);
    // any value enables the flag. The full-menu drop (2) wins openings but
    // reproduced the tau-storm collapse on final-3068 (23 accepts/157
    // rejects, final +26%): one accept dropped lambda into the region where
    // the point relaxation is toxic. See the accept branch.
    static const int rho_shift_down = [](){
      const char* e = getenv("OCA_RHO_SHIFT");
      return e ? std::max(1, std::atoi(e)) : 0; }();
    static const bool rho_shift = rho_shift_down > 0;
    // OCA_ALPHA_RHO: re-enable the alpha grid under rho mode with an
    // alpha-aware prediction pred(s) = s*b'd - s^2*(b'd - pred1) (exact for
    // the Schur-space quadratic under uniform scaling; one extra dot per
    // winning candidate). Validated in the CPU port: recovers the alpha-off
    // regression on ladybug-49/dubrovnik-88 (-0.5% final at 60 iters).
    static const bool alpha_rho = getenv("OCA_ALPHA_RHO")!=nullptr;
    // OCA_CAND_PRUNE: the per-outer fixed cost is dominated by candidate
    // evaluations (measured: outer wall tracks eval count almost linearly;
    // a 128-deep sweep fires 5 checkpoints x 5 shifts + 8 alpha = 33 evals
    // and costs 0.26-0.66 s while a shallow outer costs 0.04 s). At an
    // INTERMEDIATE checkpoint score only shift 0 and the previous outer's
    // winner, and score the full menu once at the depth CG actually stops at.
    // Justification from the 23-set archive: 82.5% of accepted winners are
    // shift 0, 87.5% sit at the deepest fired checkpoint, and only 2.1% of
    // winners are at an intermediate checkpoint with a shift that is neither
    // 0 nor the previous winner -- i.e. this prunes 2.1% of decisions.
    static const bool cand_prune = getenv("OCA_CAND_PRUNE")!=nullptr;
    // OCA_ALPHA_CROSS: the alpha grid is {0.7,1,1.4}^2 minus (1,1) = 8 extra
    // cost evaluations on EVERY outer, which dominates the cheap ones (8 of
    // 13 evals on dubrovnik-135's steady-state outers). Score only the 4
    // "cross" combos that move one block at a time; because the grid
    // compounds on the live best step, two cross wins in one outer compose
    // into a corner, so the reachable set is not as reduced as 4/8 suggests.
    static const bool alpha_cross = getenv("OCA_ALPHA_CROSS")!=nullptr;
    // OCA_CKPT_OPEN=<d>: cap the CG depth ladder at d while the solve is still
    // in its cold phase (last accepted step moved cost by >1e-3 relative).
    // Rationale (measured, dubrovnik-135): early outers that run CG to depth
    // 61-128 cost 0.15-0.26 s each and are KRYLOV-dominated (88 ms of a 138 ms
    // outer), while Caspar completes ~15 cheap iterations in the same time.
    // Trading one deep sweep for several shallow outers is the opening
    // trade; the full {8..128} ladder returns for the grind phase, so the
    // endgame is unchanged.
    static const int ckpt_open = [](){
      const char* e = getenv("OCA_CKPT_OPEN"); return e ? std::atoi(e) : 0; }();
    // How long "the opening" lasts. A first attempt used last_rel > 1e-3,
    // which on venice-52 stays true for most of the solve -- the cap then
    // applied to the whole run and moved the endpoint (+0.9%). The opening is
    // the >10%-per-outer regime: ~3-6 outers, which is exactly the window
    // Caspar leads. Overridable for experiments.
    // Default 0 = no relative-progress gate: the accelerators stay on until
    // the first REJECTED step, which is the configuration that actually
    // delivers (-20% / -31% of the lead window on dubrovnik-135 /
    // venice-1672). A 0.1 gate was measured to remove the benefit entirely
    // (-6% / +4%) while the reject guard alone already protects the
    // reject-prone scenes. Overridable for experiments.
    static const Scalar open_rel = [](){
      const char* e = getenv("OCA_OPEN_REL"); return e ? (Scalar)atof(e) : (Scalar)0.0; }();
    std::vector<Scalar> preds(L,0.0);
    Scalar pred_best=0.0;
    Scalar bpd_best=0.0;   // b'^T x of the winning candidate (scaled space)
    // OCA_LEARN_LOG: the shift menu is declared below the Score lambdas, so
    // candidate records reach it through this pointer (set after the fill;
    // stays valid across the negcurv reseed, which edits shifts in place).
    const Scalar* learn_shift_ptr=nullptr;
    // OCA_LEARN_POLICY mirrors for values declared below the lambdas
    // (assigned before the CG loop, i.e. before any ScoreAll fires).
    double lp_nb=0.0, lp_eta=0.0;

    CUDA_CHECK(cudaMemset(d_best,0,(size_t)n*sizeof(Scalar)));
    // GAP-4090 F2 refactor: Lift writes the un-equilibrated camera step into
    // xc_un; ScoreTail consumes a given (xcu,tacc) pair. Score composes them
    // exactly as before; the multi-RHS path shares one MFPass1Multi stream
    // across the menu and then runs the identical tail per candidate.
    auto Lift=[&](const Scalar* x_scaled){
      // Undo the equilibration in the space the CG worked in, then lift to the
      // full 9-per-camera layout the retraction and MFPass1 expect. Poses in a
      // calibration group therefore receive the SAME intrinsics delta.
      if(shared_intr){
        if(BlockRedOn() && use_equil){
          BlockSolveRed(x_scaled,1,bcast_out);        // L^-T, in reduced space
        } else {
          CUDA_CHECK(cudaMemcpy(bcast_out,x_scaled,(size_t)n_c*sizeof(Scalar),cudaMemcpyDeviceToDevice));
          if(use_equil) MFScaleVec<<<GridSize(n_c),256>>>(bcast_out,E,n_c);
        }
        Broadcast(bcast_out,xc_un);
      } else {
        if(block_on && !shared_intr && use_equil){
          MFBlockSolve<CD><<<GridSize(ncam),256>>>(Bk,x_scaled,ncam,1,xc_un);
        } else if(poly_on){
          // Lift the congruent-space iterate: x_hat = p(S_hat) y, then E.
          PolyApply(x_scaled,pp3);
          CUDA_CHECK(cudaMemcpy(xc_un,pp3,(size_t)n_cf*sizeof(Scalar),cudaMemcpyDeviceToDevice));
          MFScaleVec<<<GridSize(n_cf),256>>>(xc_un,E,n_cf);
        } else {
          CUDA_CHECK(cudaMemcpy(xc_un,x_scaled,(size_t)n_cf*sizeof(Scalar),cudaMemcpyDeviceToDevice));
          if(use_equil) MFScaleVec<<<GridSize(n_cf),256>>>(xc_un,E,n_cf);
        }
      }
    };
    auto _ps=[&](double& acc,auto&& fn){ if(prof_score){cudaDeviceSynchronize();auto q=now();fn();cudaDeviceSynchronize();acc+=std::chrono::duration<double>(now()-q).count();} else fn(); };
    auto ScoreTail=[&](const Scalar* x_scaled,const Scalar* xcu,Scalar* tac,int sh,int ck,
                       std::chrono::steady_clock::time_point q0){
      _ps(ts_pass1,[&]{
      MFBackSub<<<GridSize(npt),256>>>(Rf,bp,tac,npt,xpv); });
      _ps(ts_copy,[&]{
      CUDA_CHECK(cudaMemcpy(dfull,xcu,(size_t)n_cf*sizeof(Scalar),cudaMemcpyDeviceToDevice));
      CUDA_CHECK(cudaMemcpy(dfull+n_cf,xpv,(size_t)n_p*sizeof(Scalar),cudaMemcpyDeviceToDevice));
      KernelNegateInPlace<<<GridSize(n),256>>>(dfull,n); });
      _ps(ts_retract,[&]{ DoRetract(dfull,s_new); });
      Scalar c=0;
      _ps(ts_cost,[&]{ c = score_stride>1 ? ComputeCostStride(p,s_new,score_stride,rk,rk_a2)
                                          : ComputeCost(p,s_new,rk,rk_a2); });
      if(prof_score) ++ts_n;
      if(getenv("MF_DEBUG")){ Scalar nx,np2;
        cublasDnrm2(blas,n_cf,xcu,1,&nx); cublasDnrm2(blas,n_p,xpv,1,&np2);
        std::printf("      [dbg] shift=%d ckpt=%d  |x_c|=%.6e |x_p|=%.6e  cand_cost=%.10e  (cur=%.10e)%s\n",
                    sh,ck,(double)nx,(double)np2,(double)c,(double)cost, std::isfinite((double)c)?"":"  <-- NON-FINITE"); }
      ++st.cand_evals;
      if(prof){cudaDeviceSynchronize();t_cand+=std::chrono::duration<double>(now()-q0).count();}
      if(learn_f){
        // One record per scored (shift, depth) candidate. xn = |x| in the CG's
        // (scaled) space -- available BEFORE scoring, so it is a legal feature
        // for a deployed controller; pred is the zeta-recurrence model
        // decrease at score time (also pre-scoring information).
        Scalar xn=0; cublasDnrm2(blas,n_c,x_scaled,1,&xn);
        std::fprintf(learn_f,"{\"t\":\"c\",\"o\":%d,\"a\":%ld,\"sh\":%d,"
          "\"ck\":%d,\"sig\":%.6e,\"pred\":%.10e,\"cost\":%.10e,\"xn\":%.6e,"
          "\"fin\":%d}\n",
          k,learn_att_id,sh,ck,
          (learn_shift_ptr&&sh>=0&&sh<L)?(double)learn_shift_ptr[sh]:-1.0,
          (sh>=0&&sh<L)?(double)preds[sh]:0.0,(double)c,(double)xn,
          std::isfinite((double)c)?1:0);
      }
      if(sh>=0 && sh<L && c<cbest_sh[sh]) cbest_sh[sh]=c;
      // ORDER-INDEPENDENT tie-break. With a strict `<` the winner of an exact
      // tie is whichever shift happened to be scored FIRST, so any change to
      // scoring order silently changes best_sh -> the lambda update -> the
      // whole trajectory. Measured: final-3068 moved +1.77% from reordering
      // alone, with the menu gate never once firing. Preferring the lowest
      // shift index on a tie reproduces what the canonical order 0..L-1 did
      // implicitly, and makes the result independent of evaluation order.
      if(c<best_cost || (have && c==best_cost && sh>=0 && sh<best_sh)){
        best_cost=c; best_sh=sh; best_ck=ck; have=true;
        if(rho_mode && sh>=0 && sh<L) pred_best=preds[sh];
        if(rho_mode && alpha_rho){
          Scalar bd=0; cublasDdot(blas,n_c,bprime,1,x_scaled,1,&bd);
          bpd_best=bd; }
        // REVIEW 2026-09-02 (code review F: winner copy): dfull is rebuilt
        // from scratch at every Score, so swapping the pointers records the
        // winner without the O(n) D2D copy. Numerically identical.
        std::swap(d_best,dfull); }
    };
    auto Score=[&](const Scalar* x_scaled,int sh,int ck){
      std::chrono::steady_clock::time_point q0; if(prof){cudaDeviceSynchronize();q0=now();}
      Lift(x_scaled);
      _ps(ts_pass1,[&]{
      CUDA_CHECK(cudaMemset(tacc,0,(size_t)n_p*sizeof(Scalar)));
      if(score_stride>1){
        if(mf_fp32) MFPass1Stride<CD,float><<<GridSize(nobs),256>>>(Gp32,p.mf_scam,p.mf_spt,xc_un,nobs,score_stride,tacc);
        else        MFPass1Stride<CD,Scalar><<<GridSize(nobs),256>>>(Gp,p.mf_scam,p.mf_spt,xc_un,nobs,score_stride,tacc);
      } else {
        if(mf_fp32) MFPass1<CD,float><<<GridSize(nobs),256>>>(Gp32,p.mf_scam,p.mf_spt,xc_un,nobs,tacc);
        else        MFPass1<CD,Scalar><<<GridSize(nobs),256>>>(Gp,p.mf_scam,p.mf_spt,xc_un,nobs,tacc);
      } });
      ScoreTail(x_scaled,xc_un,tacc,sh,ck,q0);
    };
    // OCA_MENU_GATE=<tol>: skip scoring a DEGENERATE menu (see ScoreAll below
    // for the mechanism -- it gates on the zeta-recurrence PREDICTIONS, not on
    // step norms; two earlier proxy designs are documented and refuted there).
    // Measured (venice-52, MF_DEBUG): once lambda falls far below the spectrum
    // of S the shifted systems stop differing -- candidate costs agree to
    // ~1e-8 while the menu still pays five residual passes. Degeneracy is
    // PER-CHECKPOINT: shallow checkpoints collapse while deep checkpoints in
    // the same outer still discriminate 4x. Validated tolerance: 1e-2
    // (1e-3 regressed ladybug-1197 +60% wall). 0 (default) = off, bit-compat.
    static const double menu_gate = [](){
      const char* e = getenv("OCA_MENU_GATE"); return e ? std::atof(e) : 0.0; }();

    // OCA_SHIFT_PRUNE=<tol> (math review 2026-09-02, proposal 3): the zeta
    // recurrence already yields each shift's EXACT shifted-residual norm for
    // free (|zeta_l|*sqrt(rr)). Once shift l's system has converged below
    // tol*|b'|, its iterate is frozen to CG accuracy -- scoring it again at
    // later checkpoints re-evaluates a near-identical candidate at full
    // 2-pass cost. Score once after convergence (sdone), then skip. Uses
    // exact per-shift information, NOT a subsample/proxy of the cost -- the
    // refuted designs perturbed the scores themselves; this only removes
    // duplicate menu entries. Shift 0 (the seed) is never pruned. Off = 0.
    static const double shift_prune = [](){
      const char* e=getenv("OCA_SHIFT_PRUNE"); return e?std::atof(e):0.0; }();
    std::vector<char> sconv(L,0), sdone(L,0);
    auto ScoreAll=[&](int depth){
      // Gate on the MODEL predictions, not on scored costs. preds[l] is the
      // accumulated quadratic-model decrease 1/2*sum(al*zeta^2*rr) per shift,
      // maintained by the zeta recurrence at every CG iteration -- free, and
      // available BEFORE any candidate is scored. When the shifted systems
      // have collapsed (lambda far below the spectrum) the predictions
      // coincide; when the menu is live they differ by construction.
      // This dominates the two earlier designs, both refuted by measurement:
      //  - step-norm proxy: steps differ (2.2%) while costs agree (1e-8) --
      //    the cost surface is flat over distinct steps; norms cannot see it.
      //  - score-extremes-first: correct detection, but REORDERING evaluation
      //    perturbs chaotic trajectories through residual order couplings
      //    (best_ck ties, last_win_sh pruning) even with an order-independent
      //    tie-break: +380% wall on insta360-3086 with the gate never firing.
      // Here the canonical order 0..L-1 is preserved unconditionally, so a
      // non-flat menu takes EXACTLY the ungated path -- the idle case is a
      // true no-op, not a perturbation.
      // rlq study (2026-09): OCA_LEARN_MODE=force must BYPASS the analytic
      // menu gate on the fork outer. Historically the gate ran first, so on a
      // FLAT menu a "forced" branch silently scored shift 0 -- all branches
      // then took the same action and their divergence at H measured only
      // run-to-run noise, not the action. The winner INDEX drives the lambda
      // recentre even on equal-cost menus, so a real fork must score the
      // forced shift unconditionally. Only mode=force (opt-in rollout
      // instrumentation) is affected; every other path is untouched.
      if(g_lp.on && g_lp.mode==6 && L>1 && rho_mode){
        static const int fsh0=[](){ const char* e=getenv("OCA_FORCE_SH");
          return e?std::atoi(e):-1; }();
        if(k==0 && fsh0>=0){
          const int l=std::min(fsh0,L-1);
          Score(xs[l],l,depth); return;
        }
      }
      if(menu_gate>0.0 && L>1 && rho_mode){
        double p0=(double)preds[0], lo=p0, hi=p0; bool fin=std::isfinite(p0);
        for(int l=1;l<L && fin;++l){
          double v=(double)preds[l];
          if(!std::isfinite(v)) fin=false;
          else { lo=std::min(lo,v); hi=std::max(hi,v); }
        }
        if(fin && (hi-lo)<=menu_gate*std::max(std::fabs(hi),1e-300)){
          Score(xs[0],0,depth); ++st.menu_gated; return;
        }
      }
      // ---- OCA_LEARN_POLICY hook (Exp 5-7): choose the candidate SET.
      // Runs AFTER the analytic menu gate (the gate is free and validated;
      // the policy handles the menus the gate did not flatten). Scoring of
      // any chosen candidate is the unchanged exact path, in canonical
      // 0..L-1 order (reordering evaluation is a refuted perturbation).
      if(g_lp.on && L>1 && L<=16 && rho_mode){
        static const int lp_gd_env=[](){ const char* e=getenv("OCA_GRID_DOWN");
          return e?std::atoi(e):0; }();
        const int gd=std::min(std::max(lp_gd_env,0),L-1);
        ++g_lp.n_menus;
        if(g_lp.mode==5){                     // fixed2: {center, center+1}
          const int a=gd, b=std::min(gd+1,L-1);
          Score(xs[a],a,depth);
          if(b!=a) Score(xs[b],b,depth);
          return;
        }
        if(g_lp.mode==6){                     // force (Exp 10 branched rollouts):
          // outer 0 scores ONLY the forced shift; later outers run normally.
          static const int fsh=[](){ const char* e=getenv("OCA_FORCE_SH");
            return e?std::atoi(e):-1; }();
          if(k==0 && fsh>=0){
            const int l=std::min(fsh,L-1);
            Score(xs[l],l,depth); return;
          }
          // fall through to the normal (gated/full) path
        }
        if(g_lp.mode>=7){                     // streak probes (trivial arms):
          // during a reject streak the attempt fails ~90% of the time and
          // contested winners sit at the TOP shifts (final-3068: 85% at
          // L-2/L-1) -- score a thin high-damping probe, keep the full path
          // on clean attempts. One-integer rule; the baseline any learned
          // reject-regime policy must beat.
          if(rej_streak>0){
            ++g_lp.n_flat;
            if(g_lp.mode>=8 && L>=2) Score(xs[L-2],L-2,depth);
            Score(xs[L-1],L-1,depth);
            return;
          }
          if(g_lp.mode==9){                   // clean attempts: fixed2
            const int a=gd, b=std::min(gd+1,L-1);
            Score(xs[a],a,depth);
            if(b!=a) Score(xs[b],b,depth);
            return;
          }
          // clean attempt (modes 7/8): fall through to the gated/full path
        }
        // OCA_LEARN_MODE=qh (rlq study): horizon-Q prior. Same features, same
        // forest walker, same deployment point and same top-k mechanics as the
        // refuted one-step top1/top2 arms -- the ONLY change is the label the
        // forest was trained on: the H-outer branched-rollout return instead
        // of the one-step candidate cost. OCA_QH_K = candidates scored (1 or
        // 2, default 2). OCA_QH_OUTERS >= 0 phase-gates the prior: it applies
        // only while outer < OCA_QH_OUTERS or during a reject streak (exactly
        // the regimes where one-step and horizon labels disagree); elsewhere
        // this block is skipped and the normal gated/full path runs.
        static const int qh_k=[](){ const char* e=getenv("OCA_QH_K");
          const int v=e?std::atoi(e):2; return std::min(std::max(v,1),2); }();
        static const int qh_outers=[](){ const char* e=getenv("OCA_QH_OUTERS");
          return e?std::atoi(e):-1; }();
        const bool qh_active = g_lp.mode==10 &&
          !(qh_outers>=0 && k>=qh_outers && rej_streak==0);
        if(g_lp.mode<5 || qh_active){
        double xnp[16]; bool xok=true;
        for(int l=0;l<L;++l){ Scalar v=0; cublasDnrm2(blas,n_c,xs[l],1,&v);
          xnp[l]=(double)v; if(!std::isfinite(xnp[l])) xok=false; }
        double phi=-1e300, plo=1e300; bool pfin=true;
        for(int l=0;l<L;++l){ double v=(double)preds[l];
          if(!std::isfinite(v)){ pfin=false; break; }
          phi=std::max(phi,v); plo=std::min(plo,v); }
        if(pfin && xok){
          auto slog=[](double x){ return std::log10(std::max(std::fabs(x),1e-300)); };
          double xhi=xnp[0],xlo=xnp[0];
          for(int l=1;l<L;++l){ xhi=std::max(xhi,xnp[l]); xlo=std::min(xlo,xnp[l]); }
          double sfe[LearnPolicy::NS];
          sfe[0]=slog((phi-plo)/std::max(std::fabs(phi),1e-300));
          sfe[1]=slog((xhi-xlo)/std::max(xhi,1e-300));
          sfe[2]=slog((double)lam_cam);
          sfe[3]=slog((double)tau_eff);
          sfe[4]=std::min(rej_streak,5);
          sfe[5]=std::min(retries,8);
          sfe[6]=slog(lp_nb);
          sfe[7]=lp_eta;
          sfe[8]=std::log2((double)std::max(depth,1));
          sfe[9]=slog(std::max((double)last_rel,1e-12));
          sfe[10]=last_win_sh-gd;
          sfe[11]=(double)n_reject/(double)(n_accept+n_reject+1);
          sfe[12]=slog((double)cost/(double)nobs);
          sfe[13]=slog((double)nobs);
          const int mode=g_lp.mode;
          bool handled=false;
          if(mode==3||mode==4){
            const double p=g_lp.DecP(sfe);
            if(p<g_lp.dec_thr){ ++g_lp.n_flat;
              Score(xs[0],0,depth); return; }  // flat: mirror the gate fallback
            ++g_lp.n_dec;
            // mode 3 decisive: fall through to the full-menu path below
          }
          if(mode==1||mode==2||mode==4||mode==10){
            double u[16]; const double lc0=slog((double)cost);
            for(int l=0;l<L;++l){
              double f[LearnPolicy::NR];
              const double rel=l-gd;
              f[0]=rel; f[1]=rel*rel;
              f[2]=slog((double)preds[l])-lc0;
              f[3]=slog(xnp[l])-slog(xnp[gd]);
              f[4]=rel*sfe[9]; f[5]=rel*sfe[2]; f[6]=rel*sfe[4]; f[7]=rel*sfe[11];
              for(int i=0;i<LearnPolicy::NS;++i) f[8+i]=sfe[i];
              u[l]=g_lp.forest_on ? g_lp.ForestU(f) : g_lp.RankU(f);
            }
            const int k=(mode==1)?1:((mode==10)?qh_k:2);
            int sel0=-1,sel1=-1;
            for(int j=0;j<k;++j){ int bi=-1; double bu=1e300;
              for(int l=0;l<L;++l){ if(l==sel0||l==sel1) continue;
                if(u[l]<bu){ bu=u[l]; bi=l; } }
              if(j==0) sel0=bi; else sel1=bi; }
            for(int l=0;l<L;++l)
              if(l==sel0||l==sel1) Score(xs[l],l,depth);
            // OCA_QH_FB=1 (rlq bench finding): the horizon prior deliberately
            // picks immediately-non-improving candidates, and when NONE of
            // its top-k beats cost0 the attempt used to fall to the reject
            // path -- a full retry sweep at lam x10, which inflated wall
            // 2-3.4x on accept-heavy scenes (insta360: 288 rejects vs the
            // champion's 9). The fallback scores the REMAINING shifts in
            // canonical order instead: the true-cost accept gate is
            // untouched, the prior only loses its eval savings on exactly
            // the attempts where it was wrong. Off by default.
            static const bool qh_fb = getenv("OCA_QH_FB")!=nullptr;
            if(mode==10 && qh_fb && (!have || !(best_cost<cost))){
              for(int l=0;l<L;++l)
                if(l!=sel0&&l!=sel1) Score(xs[l],l,depth);
            }
            handled=true;
          }
          if(handled) return;
        }
        }  // g_lp.mode!=6
      }
      ++st.menu_full;
      if(multi_rhs && score_stride<=1){
        // GAP-4090 F2: one Gp stream for the whole menu, then the identical
        // per-candidate tail in canonical order 0..L-1.
        int act[16]; int na=0;
        for(int l=0;l<L;++l){
          if(shift_prune>0.0 && l>0 && sconv[l] && sdone[l]) continue;
          act[na++]=l;
        }
        for(int a=0;a<na;++a){
          Lift(xs[act[a]]);
          CUDA_CHECK(cudaMemcpy(XCU+(size_t)a*n_cf,xc_un,(size_t)n_cf*sizeof(Scalar),cudaMemcpyDeviceToDevice));
        }
        _ps(ts_pass1,[&]{
        CUDA_CHECK(cudaMemset(TACC,0,(size_t)na*n_p*sizeof(Scalar)));
        if(mf_fp32) MFPass1Multi<CD,float><<<GridSize(nobs),256>>>(Gp32,p.mf_scam,p.mf_spt,XCU,n_cf,na,nobs,TACC,n_p);
        else        MFPass1Multi<CD,Scalar><<<GridSize(nobs),256>>>(Gp,p.mf_scam,p.mf_spt,XCU,n_cf,na,nobs,TACC,n_p); });
        for(int a=0;a<na;++a){
          int l=act[a];
          std::chrono::steady_clock::time_point q0; if(prof){cudaDeviceSynchronize();q0=now();}
          ScoreTail(xs[l],XCU+(size_t)a*n_cf,TACC+(size_t)a*n_p,l,depth,q0);
          if(sconv[l]) sdone[l]=1;
        }
        return;
      }
      for(int l=0;l<L;++l){
        if(shift_prune>0.0 && l>0 && sconv[l] && sdone[l]) continue;
        Score(xs[l],l,depth);
        if(sconv[l]) sdone[l]=1;
      }
    };
    // ---- multi-shift CG.  seed = SMALLEST shift (required for stability). ----
    // OCA_GRID_DOWN=d shifts the menu two-sided: lam*10^(l-d), l=0..L-1, so d
    // decades sit BELOW the center. Rationale (measured, final-4585 dof9): the
    // legacy one-sided grid can only RAISE damping through the menu; lowering
    // happens solely via x0.5-per-accept, costing one full outer (~1.4s of
    // assembly+candidates) per halving -- an 8-outer crawl on cold starts --
    // even though shifted CG prices any shift at ~zero extra matvecs. With d>0
    // the accept recentres lam on the winning shift, so a cold lam=10 can drop
    // decades in one outer. d=0 (default) is bit-identical legacy behaviour.
    static const int grid_down_env = [](){
      const char* e = getenv("OCA_GRID_DOWN");
      return e ? std::atoi(e) : 0; }();
    const int grid_down = std::min(std::max(grid_down_env, 0), L-1);
    std::vector<Scalar> shifts(L);
    for(int l=0;l<L;++l) shifts[l]=lam_cam*std::pow(10.0,(double)(l-grid_down));
    learn_shift_ptr=shifts.data();   // OCA_LEARN_LOG (no-op when logging off)
    // OCA_NEGCURV_RESEED=1 (math review 2026-09-02, proposal 2): negative
    // curvature at the SEED shift aborts the whole sweep even though the
    // direction has positive curvature at larger shifts (p^T(A+sigma)p grows
    // linearly in sigma). Instead of surrendering the outer to the retry
    // ladder, raise the entire menu to the smallest decade that restores SPD
    // at the offending direction and redo the sweep ONCE (assembly, point
    // factor and rhs are all reused; only matvecs are repaid). Off = legacy.
    static const bool negcurv_reseed = getenv("OCA_NEGCURV_RESEED")!=nullptr;
    int sweep_attempt=0; Scalar nc_pAp=0, nc_pp=0;
    sweep_restart:
    for(int l=0;l<L;++l){ CUDA_CHECK(cudaMemset(xs[l],0,(size_t)n_c*sizeof(Scalar)));
      CUDA_CHECK(cudaMemcpy(ps[l],bprime,(size_t)n_c*sizeof(Scalar),cudaMemcpyDeviceToDevice)); }
    std::vector<Scalar> zeta(L,1.0),zprev(L,1.0),znext(L,1.0),als(L,0.0),bes(L,0.0);
    CUDA_CHECK(cudaMemset(xs[0],0,(size_t)n_c*sizeof(Scalar)));
    CUDA_CHECK(cudaMemcpy(r_,bprime,(size_t)n_c*sizeof(Scalar),cudaMemcpyDeviceToDevice));
    CUDA_CHECK(cudaMemcpy(pv_,bprime,(size_t)n_c*sizeof(Scalar),cudaMemcpyDeviceToDevice));
    Scalar nb; cublasDnrm2(blas,n_c,bprime,1,&nb);
    if(getenv("MF_DEBUG")){ Scalar nbc,nbp; cublasDnrm2(blas,n_cf,bc,1,&nbc); cublasDnrm2(blas,n_p,bp,1,&nbp);
      std::printf("    [dbg] |b_c|=%.6e |b_p|=%.6e |b'|=%.6e  lam=%.3e\n",(double)nbc,(double)nbp,(double)nb,(double)lam_cam); }
    Scalar rr; cublasDdot(blas,n_c,r_,1,r_,1,&rr);
    // s2.7 Eisenstat-Walker forcing sequence
    Scalar eta = ew_eta_max;
    if(prev_bnorm>0.0){ Scalar q=(nb*nb)/(prev_bnorm*prev_bnorm); eta=std::min(ew_eta_max,(Scalar)0.9*q); }
    prev_bnorm=nb;
    lp_nb=(double)nb; lp_eta=(double)eta;   // OCA_LEARN_POLICY feature mirrors
    int maxck = ckpts.empty()?64:*std::max_element(ckpts.begin(),ckpts.end());
    // The opening accelerators are a bet that the cheap path ranks candidates
    // as well as the full menu. A REJECTED step is direct evidence the bet
    // failed on this scene, so any reject disarms them for the rest of the
    // solve: final-3068 (37 rejects) and final-4585 (190) both regressed
    // (+14.9% / +2.0% final) while the accelerators stayed on, and both are
    // protected by this guard.
    // The option turns both mechanisms on; the individual env flags remain
    // for experiment reproduction and override it.
    const bool prune_en = cand_prune || fast_opening;
    const int  cap_en   = (ckpt_open>0) ? ckpt_open
                                        : (fast_opening ? fast_opening_depth : 0);
    // OCA_PRUNE_REARM=<k> (2026-09-06): make the opening accelerator TWO-WAY.
    // The legacy gate is one-way -- `n_reject==0` disarms it permanently at
    // the first reject, so a scene with one early transient reject pays the
    // full menu for the rest of the solve. But the menu's value is now
    // measured to be concentrated exactly in the reject/storm regime (L=1 is
    // equal-or-better at ~2x less wall on healthy scenes, and +35% worse on
    // final-3068), so the right policy is: cheap while healthy, full during
    // storms, cheap AGAIN once k consecutive clean accepts show the storm has
    // passed. k<=0 keeps the legacy one-way behaviour (bit-compat).
    static const int prune_rearm = [](){ const char* e=getenv("OCA_PRUNE_REARM");
      return e?std::atoi(e):0; }();
    const bool accel = ((n_reject==0) ||
                        (prune_rearm>0 && clean_streak>=prune_rearm))
                       && (last_rel > open_rel);
    // REVIEW: OCA_PRUNE_ALWAYS=1 lifts the opening-only guard so candidate
    // pruning runs for the WHOLE solve (Caspar evaluates exactly one candidate
    // per outer; MFREE evaluates ~11, measured 18% of wall on venice-1778).
    // The full L-shift menu still fires at the final stop, so the damping menu
    // is preserved -- only the intermediate checkpoint scans are thinned.
    static const bool prune_always = getenv("OCA_PRUNE_ALWAYS")!=nullptr;
    const bool prune_now = prune_en && (accel || prune_always);
    // REVIEW: OCA_CKPT_MAX=<d> caps the CG depth ladder GLOBALLY (not just in
    // the opening like OCA_CKPT_OPEN), to test the trade between matvec cost
    // and step quality. Caspar's fixed ~19 PCG iterations are the reference
    // point; the default ladder runs to 128.
    static const int ckpt_max_env = [](){ const char* e=getenv("OCA_CKPT_MAX");
      return e? std::atoi(e) : 0; }();
    std::vector<int> ckpts_eff = ckpts;
    if(ckpt_max_env>0){
      ckpts_eff.clear();
      for(int c : ckpts) if(c<=ckpt_max_env) ckpts_eff.push_back(c);
      if(ckpts_eff.empty()) ckpts_eff.push_back(ckpt_max_env);
      maxck = std::min(maxck, ckpt_max_env);   // cap the CG SWEEP too, not just scoring
    }
    if(cap_en>0 && accel){
      ckpts_eff.clear();
      for(int c : ckpts) if(c<=cap_en) ckpts_eff.push_back(c);
      if(ckpts_eff.empty()) ckpts_eff.push_back(cap_en);
      maxck = std::min(maxck, cap_en);
    }
    // cgrl study (2026-09): OCA_STREAK_CKPT=<d> -- STREAK-CONDITIONED CG depth
    // cap. An attempt entering with rej_streak>0 fails with P=0.75-0.96 (the
    // shi2 finding), and when it does accept, the winner sits at checkpoint
    // <=8 in 91-94% of 1,176 logged streak accepts (20-scene corpus, gate +
    // nogate; capping the menu at depth 8 offline flips 11/1176 = 0.9% and
    // has median regret 0.0000 of the attempt's gain). Yet streak attempts
    // carry 59-74% of ALL matvecs and evals on reject-prone scenes -- deep
    // sweeps on near-certainly-doomed attempts, kept alive by the seed shift
    // lam/100 whose ill-conditioning blocks the Eisenstat-Walker break (the
    // pathological case: trafalgar-257 retries run the full 128-deep sweep).
    // While rej_streak>0, cap the ladder and the sweep at d. Same one-integer
    // regime variable as the shi2 eval rule and the tau ladder; clean
    // attempts are untouched, so reject-free trajectories are bit-identical.
    // NOTE this caps DEPTH, not shifts: down-shift winners (96% of
    // dubrovnik-356's streak accepts -- which refuted the "one-sided menu in
    // streaks" variant offline) remain reachable. Unset/0 = off, bit-compat.
    static const int streak_ckpt_env = [](){ const char* e=getenv("OCA_STREAK_CKPT");
      return e? std::atoi(e) : 0; }();
    if(streak_ckpt_env>0 && rej_streak>0){
      std::vector<int> cf2;
      for(int c : ckpts_eff) if(c<=streak_ckpt_env) cf2.push_back(c);
      if(cf2.empty()) cf2.push_back(streak_ckpt_env);
      ckpts_eff.swap(cf2);
      maxck = std::min(maxck, streak_ckpt_env);
      static bool sc_once=false;
      if(!sc_once){ std::printf("  [streak-ckpt] active: cap=%d (first fire: outer %d, streak %d)\n",
                                streak_ckpt_env, k, rej_streak); sc_once=true; }
    }
    Scalar al_prev=1.0,be_prev=0.0; size_t ci_=0; int cg_it=0; bool trunc=false;
    int last_ck_fired=-1; bool cg_broke=false;
    if(prof){cudaDeviceSynchronize();t0=now();}
    for(cg_it=0; cg_it<maxck; ++cg_it){
      KvS(pv_,Ap_);
      { const Scalar sh=shifts[0]; cublasDaxpy(blas,n_c,&sh,pv_,1,Ap_,1); }
      Scalar pAp,pp; cublasDdot(blas,n_c,pv_,1,Ap_,1,&pAp); cublasDdot(blas,n_c,pv_,1,pv_,1,&pp);
      if(!(pAp>1e-14*pp)){ ++st.negcurv; trunc=true; nc_pAp=pAp; nc_pp=pp; break; }   // Steihaug-Toint
      Scalar al=rr/pAp;
      if(rho_mode) preds[0]+=0.5*al*rr;
      cublasDaxpy(blas,n_c,&al,pv_,1,xs[0],1);
      Scalar mal=-al; cublasDaxpy(blas,n_c,&mal,Ap_,1,r_,1);
      Scalar rr_new; cublasDdot(blas,n_c,r_,1,r_,1,&rr_new);
      Scalar be=rr_new/rr;
      static const bool menu_fuse = getenv("OCA_MENU_FUSE")!=nullptr && L<=MSMAX;
      for(int l=1;l<L;++l){
        Scalar sg=shifts[l]-shifts[0];
        Scalar den=al*be_prev*(zprev[l]-zeta[l])+zprev[l]*al_prev*(1.0+sg*al);
        znext[l]=(den!=0.0)?(zeta[l]*zprev[l]*al_prev)/den:0.0;
        if(!std::isfinite(znext[l])) znext[l]=0.0;
        als[l]=al*znext[l]/zeta[l]; bes[l]=be*(znext[l]/zeta[l])*(znext[l]/zeta[l]);
        if(rho_mode) preds[l]+=0.5*als[l]*zeta[l]*zeta[l]*rr;
        if(!menu_fuse) cublasDaxpy(blas,n_c,&als[l],ps[l],1,xs[l],1);
      }
      if(menu_fuse){
        MSArgs ma{};
        for(int l=1;l<L;++l){ ma.xs[l-1]=xs[l]; ma.ps[l-1]=ps[l];
          ma.als[l-1]=als[l]; ma.bes[l-1]=bes[l]; ma.znext[l-1]=znext[l]; }
        const int tot=(L-1)*n_c;
        MFMenuXUpdate<<<GridSize(tot),256>>>(ma,L-1,n_c);
        MFMenuPUpdate<<<GridSize(tot),256>>>(ma,r_,L-1,n_c);
      }
      for(int l=1;l<L;++l){
        if(!menu_fuse){
          cublasDscal(blas,n_c,&bes[l],ps[l],1);
          cublasDaxpy(blas,n_c,&znext[l],r_,1,ps[l],1);
        }
        zprev[l]=zeta[l]; zeta[l]=znext[l];
        if(shift_prune>0.0 && std::fabs((double)zeta[l])*std::sqrt((double)rr_new)
                                <= shift_prune*(double)nb) sconv[l]=1;
      }
      al_prev=al; be_prev=be;
      cublasDscal(blas,n_c,&be,pv_,1);
      { const Scalar one=1.0; cublasDaxpy(blas,n_c,&one,r_,1,pv_,1); }
      rr=rr_new;
      if(prof){cudaDeviceSynchronize();t_mv+=std::chrono::duration<double>(now()-t0).count();}
      while(ci_<ckpts_eff.size() && cg_it+1==ckpts_eff[ci_]){
        // OCA_DOOMED=<mode>: DOOMED-ATTEMPT PROBE (2026-09-06). On storm
        // scenes 79% of candidate evaluations land on attempts where NOTHING
        // is accepted, and evaluation is ~45% of wall there -- roughly a
        // third of storm wall is spent scoring steps that are all rejected.
        // For an SPD system the CG iterate norms grow monotonically, so the
        // MOST CONSERVATIVE candidate is (largest sigma, shallowest depth):
        // the shortest step, hence the likeliest accept. Score it first at
        // the first checkpoint of a RETRY; if even that fails to beat the
        // current cost, the attempt is almost certainly doomed and the
        // remaining candidates are skipped.
        //   mode 1 = count only (log how often skipping would have been
        //            trajectory-neutral, i.e. no later candidate was
        //            accepted anyway) -- measure BEFORE switching on.
        //   mode 2 = act on it.
        // Candidate-SET change only; scoring inputs untouched.
        static const int doomed_mode = [](){ const char* e=getenv("OCA_DOOMED");
          return e?std::atoi(e):0; }();
        bool doomed_skip=false;
        if(doomed_mode>0 && rej_streak>0 && ci_==0 && L>1){
          const Scalar cost_before=best_cost; const bool had=have;
          Score(xs[L-1],L-1,cg_it+1);           // most conservative candidate
          const bool probe_failed = !(have && best_cost<cost);
          if(probe_failed){
            ++st.doomed_probe; doomed_probe_failed=true;
            if(doomed_mode>=2) doomed_skip=true;
          }
          (void)cost_before; (void)had;
        }
        if(doomed_skip){
          last_ck_fired = cg_it+1; ci_=ckpts_eff.size();   // abandon this attempt
          break;
        }
        if(prune_now){
          Score(xs[0],0,cg_it+1);
          if(last_win_sh>0 && last_win_sh<L) Score(xs[last_win_sh],last_win_sh,cg_it+1);
        } else {
          ScoreAll(cg_it+1);
        }
        last_ck_fired = cg_it+1;
        ++ci_;
      }
      if(prof){cudaDeviceSynchronize();t0=now();}
      if(sqrt(rr_new)<=eta*nb){ cg_broke=true; break; }    // s2.7
    }
    if(trunc && negcurv_reseed && sweep_attempt==0 && L>1){
      int kup=0;
      for(int k=1;k<L;++k)
        if(nc_pAp + shifts[0]*(std::pow((Scalar)10.0,(Scalar)k)-(Scalar)1.0)*nc_pp
             > (Scalar)1e-14*nc_pp){ kup=k; break; }
      if(kup>0){
        ++sweep_attempt;
        for(int l=0;l<L;++l) shifts[l]*=std::pow((Scalar)10.0,(Scalar)kup);
        std::fill(preds.begin(),preds.end(),(Scalar)0.0);
        std::fill(sconv.begin(),sconv.end(),0);
        std::fill(sdone.begin(),sdone.end(),0);
        if(verbose) std::printf("    [negcurv-reseed] menu raised %d decade(s), sweep restarted\n",kup);
        goto sweep_restart;
      }
    }
    if(trunc){ ScoreAll(cg_it); }
    else if(ci_==0){ ScoreAll(cg_it); }
    else if(prune_now){
      // Guarantee one FULL shift menu at the depth CG actually stopped at:
      // that is where 87.5% of winners live. If the last checkpoint coincides
      // with that state, only the shifts held back there still need scoring.
      const int depth = cg_broke ? (cg_it+1) : maxck;
      if(last_ck_fired==depth){
        for(int l=0;l<L;++l)
          if(l!=0 && l!=last_win_sh) Score(xs[l],l,depth);
      } else {
        ScoreAll(depth);
      }
    }

    // ---- existing alpha grid, unchanged ----
    int alpha_win=0;
    if(have && use_alpha && (!rho_mode || alpha_rho)){
      const Scalar as[3]={0.7,1.0,1.4};
      Scalar base=best_cost;
      // Under rho mode the winning combo must carry a matching prediction:
      // for a step whose camera half is scaled by cumulative s, the
      // Schur-space quadratic gives pred(s) = s*b'd - s^2*(b'd - pred1).
      // s compounds across winning combos exactly like the step itself.
      const Scalar bpd0=bpd_best, pred1=pred_best;
      Scalar s_cum=1.0;
      for(int a1=0;a1<3;++a1) for(int a2=0;a2<3;++a2){
        if(as[a1]==1.0&&as[a2]==1.0) continue;
        // cross = move one block at a time; corners remain reachable by
        // composition because the grid compounds on the live best step.
        if(alpha_cross && as[a1]!=1.0 && as[a2]!=1.0) continue;
        MFAlphaScale<<<GridSize(n),256>>>(dfull,d_best,as[a1],as[a2],n_cf,n);
        DoRetract(dfull,s_new);
        Scalar c=ComputeCost(p,s_new,rk,rk_a2);
        if(learn_f)
          std::fprintf(learn_f,"{\"t\":\"al\",\"o\":%d,\"a\":%ld,\"a1\":%.2f,"
            "\"a2\":%.2f,\"cost\":%.10e}\n",
            k,learn_att_id,(double)as[a1],(double)as[a2],(double)c);
        if(c<best_cost){ best_cost=c; alpha_win=1;
          if(rho_mode){
            s_cum*=as[a1];
            pred_best=s_cum*bpd0-s_cum*s_cum*(bpd0-pred1); }
          std::swap(d_best,dfull); }   // REVIEW 2026-09-02: same swap as in Score
      }
      (void)base;
    }
    // Subsampled scoring: re-score the WINNER on the full data so the accept
    // decision, rho, ftol and the logged trajectory all use true cost.
    if(score_stride>1 && have){
      DoRetract(d_best,s_new);
      best_cost=ComputeCost(p,s_new,rk,rk_a2);
    }
    // ---- accept / reject (existing rule) ----
    bool accepted=false;
    double learn_rho=std::numeric_limits<double>::quiet_NaN(),
           learn_fac=std::numeric_limits<double>::quiet_NaN(),
           learn_predfull=0.0;   // OCA_LEARN_LOG capture (accept branch only)
    if(have && best_cost<cost){
      // OCA_DOOMED accounting: the probe said "doomed" yet a later candidate
      // WAS accepted -> skipping would NOT have been trajectory-neutral here.
      if(doomed_probe_failed) ++st.doomed_wrong;
      // OCA_PRUNE_REARM bookkeeping: an accept that needed no retries is a
      // "clean" outer; any contested accept restarts the count.
      if(rej_streak==0) ++clean_streak; else clean_streak=0;
      const Scalar cost_pre_accept = cost;
      DoRetract(d_best,s_new); CopyState(s,s_new,ncam,npt);
      cost=best_cost;
      // AUDIT 2026-08-22: lambda ratchet. A reject multiplies lam by 10 and an
      // accept only halves it, so any scene that rejects at all drifts upward
      // forever: measured on final-4585 --dof9, a 3-reject/1-accept cycle nets
      // lam x500, carrying lam 3.9e-2 -> 4.8e34 by iter 61 with cg_it pinned to
      // 0 and the last 53 iterations buying 1.3%. The accept that ends such a
      // streak is won by the CD=9 tau ratchet above, NOT by the lambda
      // escalation, so unwind the escalation instead of banking it. CD=6 keeps
      // round-9 behaviour exactly.
      // OCA_LM_CLASSIC=1: keep the classic decay from the ACCEPTED lambda even
      // after a reject streak (diagnostic switch for the unwind-oscillation
      // investigation on dubrovnik-142 / final-4585).
      static const bool lm_classic = getenv("OCA_LM_CLASSIC")!=nullptr;
      if(rho_mode){
        // Trust-region update (Ceres-style): a step that underperforms its
        // quadratic model RAISES lambda even though it is accepted; a step
        // that matches it decays lambda smoothly. Fixes the accepted-step
        // overshoot zig-zag (gradient bouncing 4e3->5e4->1.6e4 measured on
        // venice-52 under the unconditional x0.5 decay).
        const Scalar act = cost_pre_accept - cost;
        const Scalar pred_full = pred_best + pred_pt;   // OCA_RHO_PT: pred_pt=0 when off
        const Scalar rho = (pred_full>1e-300) ? act/pred_full : 1.0;
        const Scalar f3 = 2.0*rho - 1.0;
        Scalar fac = 1.0 - f3*f3*f3;
        if(fac < (Scalar)(1.0/3.0)) fac = (Scalar)(1.0/3.0);
        if(rho < 0.25) fac = 2.0;
        static const Scalar fix_decay = [](){ const char* e=getenv("OCA_FIX_DECAY");
          return e? (Scalar)atof(e) : (Scalar)0.0; }();
        if(fix_decay > 0.0) fac = fix_decay;
        // rho is only a trustworthy signal in the near-quadratic regime; on a
        // cold nonlinear problem every candidate underperforms its model and
        // TR raises starve the descent (final-4585: lambda ran to inf, cost
        // frozen 2x above greedy). While the accepted step still moves cost by
        // >1e-4 relative, decay at least as fast as greedy; Nielsen governs
        // only the grind phase. And the reject x10s are an intra-outer search
        // device, not information about the accepted step: apply fac to the
        // PRE-STREAK lambda exactly like the legacy unwind above, else reject
        // storms bank permanently (that was the lam=inf mechanism).
        const Scalar rel = act / std::max(cost_pre_accept, (Scalar)1e-300);
        if(rel > (Scalar)1e-4) fac = std::min(fac, (Scalar)0.5);
        if(learn_f){ learn_rho=(double)rho; learn_fac=(double)fac;
                     learn_predfull=(double)pred_full; }
        // OCA_STREAK_GM=1 (math review 2026-09-02, proposal 4): rebasing a
        // contested accept all the way back to the PRE-streak lambda drops
        // below the accept boundary the streak just found, inviting the next
        // reject streak -- a derivable sawtooth limit cycle matching the
        // final-4585 storm signature. The geometric mean of the pre-streak
        // lambda and the escalated lambda that actually won keeps half the
        // streak's information (in log space) without banking the full x10^k.
        static const bool streak_gm = getenv("OCA_STREAK_GM")!=nullptr;
        Scalar base = (CD==9 && rej_streak>0 && !lm_classic)
                        ? (streak_gm ? std::sqrt(lam_pre_streak*lam_cam)
                                     : lam_pre_streak)
                        : lam_cam;
        // OCA_RHO_SHIFT: the accepted step was solved at sigma_win; make
        // that the anchor Nielsen updates from, so the menu's damping
        // information survives into the next outer.
        if(rho_shift && best_sh>=0 && rej_streak==0){
          // Anchor only on CLEAN accepts. A contested accept's lam carries
          // the reject streak's x10 escalations, which are a joint
          // (lambda,tau) search device, not damping information -- banking
          // them froze the final-4585 grind at an elevated lambda (48
          // outers buying 0.3%, final +1.9% worse). Clean accepts keep the
          // full downward anchor (the opening win) with the upward move
          // clamped to +1 decade.
          const int rel_sh = std::max(std::min(best_sh-grid_down, 1),
                                      -rho_shift_down);
          base = lam_cam*std::pow((Scalar)10.0,(Scalar)rel_sh);
        }
        lam_cam = std::min(std::max(base*fac, lam_floor), (Scalar)1e8);
      }
      else if(grid_down>0 && best_sh>=0){
        // Two-sided grid: the winning candidate names its own damping, so
        // recentre there -- but rate-limit the DOWNWARD move to one decade per
        // outer. Unclamped recentring reproduced the fixed-low-lambda failure
        // on ladybug-1723 (down-shift wins one candidate battle, drags lam too
        // low, then pays reject-escalations climbing back: 1.8s -> 3.4s). One
        // decade per accept still compresses the cold crawl ~3x vs x0.5
        // halving while capping any overshoot at one cheap correction.
        // Simple recentre: the winning candidate names its own damping. Two
        // guarded variants were tried and both made things worse in a
        // different way (rate-limit: final-4585 43.8s/0.7063; 2x-margin gate:
        // final-4585 24.5s/0.7558 -- each reshapes the trajectory under
        // func_tolerance and moves where the stop fires). Keep the policy
        // simple; the known cost is ladybug-1723 (1.8s -> 3.4s), which is why
        // this stays opt-in via OCA_GRID_DOWN rather than default.
        lam_cam=std::max(lam_cam*std::pow((Scalar)10.0,(Scalar)(best_sh-grid_down)),lam_floor);
        if(best_sh==grid_down) lam_cam=std::max(lam_cam*(Scalar)0.5,lam_floor);
      }
      else if(CD==9 && rej_streak>0 && !lm_classic)
                                lam_cam=std::max(lam_pre_streak*0.5,lam_floor);
      else                      lam_cam=std::max(lam_cam*0.5,lam_floor);
      if(CD==9 && (tau_persist || tau_v3_dec>0)){
        if(rej_streak>0) tau_win=tau_used;          // remember what won
        else             tau_win*=(Scalar)0.5;      // fade when not needed
      }
      if(best_sh>=0) last_win_sh=best_sh;
      last_rel=(cost_pre_accept-best_cost)/std::max(cost_pre_accept,(Scalar)1e-300);
      accepted=true; ++n_accept; rej_streak=0;
    } else {
      if(rej_streak==0) lam_pre_streak=lam_cam;
      // OCA_RETRY_SPAN=1 (2026-09-06): ESCALATE BY THE MENU SPAN, not x10.
      // A rejected attempt did not merely show that lambda is too small -- it
      // scored the WHOLE menu, so it proved that damping up to
      // lam*10^(L-1-grid_down) is insufficient. Escalating x10 therefore
      // re-tests four of the five shifts the previous attempt already
      // rejected, buying exactly ONE new decade per retry while re-paying the
      // point factor and the full scoring pass. That redundancy is the
      // measured cost driver: final-4585 runs ~8 rejects per accept and its
      // per-outer cost is 10.5x Caspar's, the ratio tracking reject count
      // across the whole benchmark. Jumping straight past the refuted range
      // should reach the accepting damping in ~1-2 retries instead of ~8.
      // The menu still spans grid_down decades BELOW the new centre, so a
      // moderate overshoot is recoverable within the next attempt's own menu.
      // OCA_RETRY_SPAN=<k>: use the span jump only from the k-th reject of a
      // streak onward (k=1 = always). Measured: always-on cuts rejects 1.5-8x
      // and wall with it, but overshoots on LOW-reject scenes -- venice-52
      // (32 rejects total) lost 5.7% because a single, possibly marginal
      // reject triggered a three-decade jump. A first reject is weak evidence
      // (the menu may have been nearly acceptable); a second is strong (the
      // whole neighbourhood has now been refuted twice). k=2 keeps the x10
      // step for the first reject and skips the refuted range thereafter.
      static const int retry_span = [](){ const char* e=getenv("OCA_RETRY_SPAN");
        return e?std::atoi(e):0; }();
      const bool span_now = retry_span>0 && (rej_streak+1)>=retry_span;
      const double esc = span_now
          ? std::pow(10.0,(double)std::max(1,L-1-grid_down)+1.0) : 10.0;
      lam_cam*=(Scalar)esc; ++n_reject; ++rej_streak;
    }
    // OCA_LEARN_LOG: one record per attempt, after the accept/reject decision
    // and the lambda/tau updates (lam=pre-action damping, lam1=post-update).
    if(learn_f){
      std::fprintf(learn_f,"{\"t\":\"a\",\"o\":%d,\"a\":%ld,\"retry\":%d,"
        "\"streak\":%d,\"lam\":%.6e,\"tau\":%.6e,\"nb\":%.6e,\"eta\":%.4e,"
        "\"cost0\":%.10e,\"cg\":%d,\"brk\":%d,\"tr\":%d,\"gated\":%ld,"
        "\"ev\":%ld,\"mv\":%ld,\"bsh\":%d,\"bck\":%d,\"aw\":%d,"
        "\"bcost\":%.10e,\"acc\":%d,\"rho\":%.6e,\"fac\":%.4f,"
        "\"pred\":%.10e,\"predpt\":%.10e,\"lam1\":%.6e,\"tauwin\":%.6e,"
        "\"dt\":%.4f,\"preds\":[",
        k,learn_att_id,retries,learn_streak_att,(double)learn_lam_att,
        (double)tau_eff,(double)nb,(double)eta,(double)learn_cost_att,
        cg_it,cg_broke?1:0,trunc?1:0,st.menu_gated-learn_mg0,
        st.cand_evals-learn_ev0,st.matvecs-learn_mv0,best_sh,best_ck,
        alpha_win,(double)best_cost,accepted?1:0,learn_rho,learn_fac,
        learn_predfull,(double)pred_pt,(double)lam_cam,(double)tau_win,
        std::chrono::duration<double>(now()-learn_t0).count());
      for(int l=0;l<L;++l)
        std::fprintf(learn_f,"%s%.10e",l?",":"",(double)preds[l]);
      std::fprintf(learn_f,"]}\n");
      ++learn_att_id;
    }
    // AUDIT 2026-08-22: retry this outer step rather than spending it. The
    // state is unchanged, so the next attempt skips assembly entirely and only
    // redoes the point factor / rhs / equilibration / CG at the escalated
    // lam and tau_eff. Give up after max_inner_retry attempts so a genuinely
    // stuck state still advances k and the run terminates.
    if(!accepted && retries<max_inner_retry){
      ++retries; need_assembly=false;
      if(verbose)
        std::printf("  MFCG it %3d  retry %d/%d  lam=%.3e tau_eff=%.3e  (assembly reused)\n",
                    k+1,retries,max_inner_retry,(double)lam_cam,(double)tau_eff);
      continue;
    }
    retries=0; need_assembly=true;
    log.iters.push_back(k+1); log.costs.push_back(cost);
    CsvRow(k+1, (double)cost);
    // Two independent reasons to stop early.
    //  (1) An accepted step that barely moved the cost -- Ceres' function_tolerance.
    //  (2) LM exhausted its retries without finding an improving step, repeatedly.
    //      This is the case that matters on an already-converged input, where every
    //      step is rejected and (1) never fires because cost never changes.
    // Both stopping rules ask "has the solve flattened?". Asking it of a
    // SINGLE outer makes the answer decidable by 1e-7 differences, which GPU
    // atomics supply for free: six identical final-3068 runs stopped at 8,
    // 14, 23, 56, 60 and 60 outers, so a user gets a random amount of
    // optimisation. OCA_STOP_WINDOW=<n> asks it of the last n outers instead.
    auto FlatOverWindow=[&](){
      if(stop_window<=0) return true;          // legacy: single-outer test
      const size_t have=log.costs.size();
      if(have<2) return false;
      const size_t back=std::min<size_t>(stop_window, have-1);
      const Scalar ref=log.costs[have-1-back];
      return (ref<=0) || ((ref-cost) < func_tolerance*ref);
    };
    if(accepted){
      stuck=0;
      if(func_tolerance>0 && prev_cost>0 &&
         (prev_cost-cost) < func_tolerance*prev_cost && FlatOverWindow()){
        converged=true;
        if(verbose) std::printf("  MFCG: converged (relative cost decrease < %.2e)\n",
                                (double)func_tolerance);
      }
      // Preconditioner scheduler trigger: same flatness signal as OCA_FTOL,
      // but flips the preconditioner instead of stopping. Fires once; the
      // factor for the next outer is built under the new metric.
      if(psw_lam>0.0 && !psw_switched && block_eq && lam_cam<=psw_lam){
        block_on=true; psw_switched=true;
        if(verbose) std::printf("  MFCG: PRECOND SWITCH diag->block at outer %d (lam %.2e <= %.1e)\n",
                                k+1,(double)lam_cam,psw_lam);
      }
      if(psw_eps>0.0 && !psw_switched && block_eq && prev_cost>0){
        psw_streak = ((prev_cost-cost) < psw_eps*prev_cost) ? psw_streak+1 : 0;
        if(psw_streak>=psw_k){
          block_on=true; psw_switched=true;
          if(verbose) std::printf("  MFCG: PRECOND SWITCH diag->block at outer %d (cost %.6e)\n",
                                  k+1,(double)cost);
        }
      }
      // OCA_FTOL=<eps> / OCA_FTOL_K=<k>: PERSISTENT relative-decrease stop.
      // Fires after k consecutive outers (accepted or not) whose best-so-far
      // relative improvement is below eps. Chosen offline against 27 recorded
      // trajectories (23 BAL + 4 monocular Fuchsberg): eps=5e-5, k=5 cuts
      // 42-57% of solve wall on the mono problems while the stop-point cost
      // STILL beats Caspar's final on 3 of 4 (the 4th ties within 0.04%), and
      // is inert on BAL (0% median wall saved, worst quality loss 0.052%).
      // Persistence k matters: single-accept ftol (above) is fooled by the
      // two-phase trajectories where a flat patch precedes a second descent.
      // Default off = bit-compatible.
      if(!converged && ftol_env>0 && prev_cost>0){
        ftol_streak = ((prev_cost-cost) < ftol_env*prev_cost) ? ftol_streak+1 : 0;
        if(ftol_streak>=ftol_k_env){
          converged=true;
          if(verbose) std::printf("  MFCG: converged (OCA_FTOL: %d outers < %.1e rel)\n",
                                  ftol_k_env,(double)ftol_env);
        }
      }
      prev_cost=cost;
    } else if(psw_eps>0.0 && !psw_switched && block_eq && ++psw_streak>=psw_k){
      block_on=true; psw_switched=true;
      if(verbose) std::printf("  MFCG: PRECOND SWITCH diag->block at outer %d (reject-flat)\n",k+1);
      if(ftol_env>0) ++ftol_streak;   // keep the stop rule's view of flatness
    } else if(ftol_env>0 && ++ftol_streak>=ftol_k_env && prev_cost>0){
      // Rejected outers improve nothing by definition; they count toward the
      // streak, matching the offline simulation (which saw only best-so-far).
      converged=true;
      if(verbose) std::printf("  MFCG: converged (OCA_FTOL: %d flat/rejected outers)\n",
                              ftol_k_env);
    } else if(max_consecutive_failures>0 && ++stuck>=max_consecutive_failures){
      // OCA_STOP_WINDOW: the bare failure counter is decidable by 1e-7
      // differences. A transient patch of fully-rejected outers is normal on
      // reject-prone scenes, and GPU atomics make it appear or not run to
      // run: measured on final-3068, six identical runs stopped at 8, 14, 23,
      // 56, 60 and 60 outers, i.e. a user gets a random amount of
      // optimisation. Requiring the streak AND genuinely flat progress over a
      // longer window keeps the rule's purpose -- terminate on an
      // already-converged input, where cost never moves at all -- while
      // refusing to fire on a scene that is still descending between rejects.
      if(FlatOverWindow()){
        converged=true;
        if(verbose) std::printf("  MFCG: converged (%d consecutive outer iterations "
                                "with no improving step)\n",stuck);
      } else {
        stuck=0;   // still descending over the window: keep going
      }
    }
    if(converged){ ++k; break; }
    if(verbose)
      std::printf("  MFCG it %3d cost=%.6e lam=%.3e tau=%.2e cg_it=%d shift=%d ckpt=%d alpha=%d %s mv=%ld\n",
                  k+1,(double)cost,(double)lam_cam,(double)tau_win,cg_it,best_sh,best_ck,alpha_win,
                  accepted?"acc":"REJ",st.matvecs);
    { char buf[512];
      std::snprintf(buf,sizeof buf,
        "{\"outer\":%d,\"cost\":%.10f,\"lam_cam\":%.6e,\"cg_iters\":%d,\"eta\":%.4e,"
        "\"sel_shift\":%d,\"sel_ckpt\":%d,\"alpha_win\":%d,\"accepted\":%d,"
        "\"matvecs_cum\":%ld,\"negcurv_cum\":%ld,\"cand_evals_cum\":%ld}",
        k+1,(double)cost,(double)lam_cam,cg_it,(double)eta,best_sh,best_ck,alpha_win,
        accepted?1:0,st.matvecs,st.negcurv,st.cand_evals);
      jrows.push_back(buf); }
    ++k;   // AUDIT 2026-08-22: advanced here, not in the for-header, so an
           // inner retry above can `continue` without spending an iteration.
    // OCA_RETRI=<k>: RE-TRIANGULATION REPAIR every k accepted outers (and
    // once at the end). Closed-form DLT reset of each point from its current
    // cameras, accepted per point only if that point's own reprojection cost
    // improves -- a projection back onto the feasible set, not a search step.
    // Tests the prediction that a fling is recoverable by geometry but not by
    // a Newton step. Cost: one O(nobs) kernel, no extra assembly.
    static const int retri_every = [](){ const char* e=getenv("OCA_RETRI");
      return e?std::atoi(e):0; }();
    if(retri_every>0 && accepted && (n_accept%retri_every)==0){
      static int* d_nfix=nullptr;
      if(!d_nfix) CUDA_CHECK(cudaMalloc((void**)&d_nfix,sizeof(int)));
      CUDA_CHECK(cudaMemset(d_nfix,0,sizeof(int)));
      const Scalar c_pre = cost;
      KernelRetriangulate<<<GridSize(npt),256>>>(p.cam_idx,p.pt_idx,p.uv,
          p.point_obs_offsets,p.point_obs_list,s.R,s.t,
          INTR_F(p,s),INTR_K1(p,s),INTR_K2(p,s),s.X,npt,d_nfix);
      const Scalar c_post = ComputeCost(p,s,rk,rk_a2);
      int hfix=0; CUDA_CHECK(cudaMemcpy(&hfix,d_nfix,sizeof(int),cudaMemcpyDeviceToHost));
      // Per-point gating cannot raise any point's own cost, but the global
      // objective is the sum of exactly those terms, so it cannot rise
      // either; guard anyway and report.
      if(std::isfinite((double)c_post) && c_post<=cost){
        cost=c_post; need_assembly=true;
        if(verbose && hfix>0)
          std::printf("  [retri] outer %d: %d points reset, cost %.6e -> %.6e (%+.3f%%)\n",
                      k,hfix,(double)c_pre,(double)cost,
                      100.0*((double)cost-(double)c_pre)/(double)c_pre);
      }
    }
    // OCA_RI_AT=<k>: LATE resection-intersection. Fires once, after outer k,
    // when the basin is already committed (rollouts: greedy/horizon
    // disagreement vanishes past ~5 outers). RI keeps its own true-cost
    // accept gates, so it can only lower the cost it is handed; the question
    // this tests is whether cheap alternation still finds descent the damped
    // Newton step has stopped finding -- and whether the state it leaves
    // helps or hurts the outers that follow.
    if(ri_at>=0 && ri_open>0 && k==ri_at+1){
      const Scalar c_pre=cost;
      const int done=RunRIPhase(ri_open);
      need_assembly=true;   // RI moved the state; the cached assembly is stale
      if(verbose) std::printf("  [ri-late] after outer %d: %d sweeps, %.6e -> %.6e (%+.2f%%)\n",
                              k,done,(double)c_pre,(double)cost,
                              100.0*((double)cost-(double)c_pre)/(double)c_pre);
    }
  }
  int cheir1=CountCheiralityViolations(p,s);
  if(prof_score && ts_n>0)
    std::printf("  [SCORE] n=%ld pass1+backsub=%.1fms copy+neg=%.1fms retract=%.1fms cost=%.1fms  (per eval)\n",
                ts_n, 1e3*ts_pass1/ts_n, 1e3*ts_copy/ts_n, 1e3*ts_retract/ts_n, 1e3*ts_cost/ts_n);
  if(st.menu_gated+st.menu_full>0)
    std::printf("  MFCG menu gate: %ld of %ld menus flat (%.1f%%), interior scorings skipped %ld\n",
                st.menu_gated, st.menu_gated+st.menu_full,
                100.0*st.menu_gated/(double)(st.menu_gated+st.menu_full),
                st.menu_gated*3);
  if(g_lp.on)
    std::printf("  MFCG learn-policy: mode %d, %ld menus (%ld flat / %ld decisive)\n",
                g_lp.mode, g_lp.n_menus, g_lp.n_flat, g_lp.n_dec);
  if(st.doomed_probe>0)
    std::printf("  MFCG doomed-probe: fired %ld, of which %ld attempts were "
                "accepted anyway (%.1f%% NOT neutral)\n",
                st.doomed_probe, st.doomed_wrong,
                100.0*st.doomed_wrong/(double)st.doomed_probe);
  std::printf("  MFCG: accepts=%d rejects=%d total_matvecs=%ld negcurv=%ld cand_evals=%ld "
              "mean_cg_per_outer=%.1f\n",
              n_accept,n_reject,st.matvecs,st.negcurv,st.cand_evals,
              (double)st.matvecs/std::max<int>(1,(int)log.costs.size()-1));
  if(prof) std::printf("  [PROFILE] assembly=%.3fs pointfactor+rhs=%.3fs krylov=%.3fs candidates=%.3fs\n",
                       t_asm,t_fac,t_mv,t_cand);
  if(!jsonpath.empty()){
    FILE* jf=std::fopen(jsonpath.c_str(),"w");
    if(jf){ std::fprintf(jf,"{\"dataset_ncam\":%d,\"nobs\":%d,\"n_c\":%d,\"shifts\":%d,"
              "\"checkpoints\":[",ncam,nobs,n_c,L);
      for(size_t i=0;i<ckpts.size();++i) std::fprintf(jf,"%s%d",i?",":"",ckpts[i]);
      std::fprintf(jf,"],\"equil\":%d,\"iters\":[\n",use_equil?1:0);
      for(size_t i=0;i<jrows.size();++i) std::fprintf(jf,"  %s%s\n",jrows[i].c_str(),i+1<jrows.size()?",":"");
      std::fprintf(jf,"],\"cheirality_start\":%d,\"cheirality_end\":%d}\n",cheir0,cheir1);
      std::fclose(jf); std::fprintf(stderr,"[R9] wrote %s\n",jsonpath.c_str()); }
  }
  // REVIEW 2026-09-01: this block used to free only 9 of ~39 per-call device
  // buffers. Standalone benchmarks never noticed (one solve per process), but
  // the MAPPER calls this function once per global BA -- ~47 times on the
  // muell sequence -- leaking 100-300MB per call on a 16GB card. Free
  // everything; all pointers are nullptr-initialised so unallocated branches
  // (fp32 vs fp64, block_eq off, shared_intr off) are safe no-ops.
  cudaFree(dfull);cudaFree(d_best);cudaFree(r_);cudaFree(pv_);cudaFree(Ap_);cudaFree(okf);
  cudaFree(r2acc);cudaFree(obscnt);cudaFree(rk_sv);
  cudaFree(pp1);cudaFree(pp2);cudaFree(pp3);cudaFree(pp4);cudaFree(R0f);
  cudaFree(XCU);cudaFree(TACC);
  cudaFree(Hcc);cudaFree(Cdiag);cudaFree(Gp);cudaFree(Gc);cudaFree(Bo);
  cudaFree(Gp32);cudaFree(Gc32);cudaFree(Bo32);
  cudaFree(bc);cudaFree(bp);cudaFree(Rf);cudaFree(tacc);cudaFree(uu);cudaFree(w);
  cudaFree(bprime);cudaFree(corr);cudaFree(E);cudaFree(dk);
  cudaFree(Bk);cudaFree(bscr);cudaFree(Bp);cudaFree(Bg);
  cudaFree(xc_un);cudaFree(xpv);
  cudaFree(bcast_in);cudaFree(bcast_out);
  for(int l=0;l<L;++l){ cudaFree(xs[l]); cudaFree(ps[l]); }
  cudaFree(s_new.R);cudaFree(s_new.t);cudaFree(s_new.X);cudaFree(s_new.intr);
  cublasDestroy(blas);
  CsvClose();
  if(learn_f){ std::fclose(learn_f);
    std::fprintf(stderr,"[learn] wrote %s (%ld attempts)\n",
                 getenv("OCA_LEARN_LOG"),learn_att_id); }
  if(final_lambda_out) *final_lambda_out = lam_cam;
  return log;
}

#ifndef OCA_CORE_LIBRARY
static int OcaCliMain(int argc, char** argv) {
  std::string problem_path, algo = "lm";
  Scalar lam = 1.0, lam0 = 10.0, lam1 = 10.0, mu0 = 1.0, tol = 1e-6, factor = 2.0;
  int max_iter = 500;
  int n_lambda = 6;
  Scalar decade_lo = -2.0, decade_hi = 2.0, lam_floor = 1e-9, lam_ceil = 1e12;
  Scalar base_lam_cam0 = 1.0, base_lam_pt0 = 1.0;
  int num_devices = 1;
  bool verbose = true, use_momentum = true;
  Scalar gamma_cap = 1.0, gamma_fixed = -1.0;
  int aa_window = 2;
  int j_max = 32;
  bool fp32_cholesky = false;
  bool subspace_min = false;
  // Round-2 flags (BA_Round2_Research_Directions.pdf priority action table)
  bool r2_relpt = false, r2_marquardt_pt = false, r2_jacobi = false, r2_audit = false;
  bool r2_aitken = false, r2_alpha = false, r2_oracle = false, r2_cheap_first = true;
  Scalar r2_tau_pt = 1e-7, r2_eps_rel = 1e-9;
  bool r2_fp32 = false; int r2_n_ir = 2; Scalar r2_ir_tol = 1e-10;
  bool r2_adaptive = false; Scalar r2_kappa = 1e4; Scalar r2_theta = 1.0;
  std::string dump_residuals;
  std::string dump_true_cost;
  bool build_edge_csr = false;
  bool r2_span_min = false;
  std::vector<int> depths_cli = {0,1,2,4,8};
  // A1: squared-Chebyshev spectral filter (MM-derived, gain 1-q(t)^2 in [0,1] for any t+,
  // any k -- see r6/math for the derivation and r6/cuda/cheb_validate.py for the host-side
  // numerical validation). Off by default; never touches champion behaviour unless enabled.
  bool r2_cheb = false;
  Scalar r2_cheb_tplus = 0.99;
  std::vector<int> r2_cheb_kmenu = {4, 6};
  std::vector<int> r2_hybrid_rmenu = {0, 0};  // paired by index with cheb_kmenu; 0 => pure sqCheb
  bool r2_cheir_gate = false;
  bool r2_fp32_jac = false;
  std::string dump_prefix; std::vector<int> dump_iters;
  std::vector<int> mf_ckpts={8,16,32,64,128}; int mf_shifts=5;
  std::string mf_precond="equil", mf_json; Scalar mf_eta=0.5; bool mf_alpha=true;
  bool mf_fp32=false;
  // ROUND 10: 9-DOF camera flags (mfree_shifted_cg only).
  //   --dof9    : free f and k1 per camera (Caspar's SIMPLE_RADIAL merged block)
  //   --free_k2 : with --dof9, also free k2 (full 9-DOF, Ceres-on-BAL convention)
  //   --zero_k2 : zero every k2 at load, so the objective matches the harness's
  //               COLMAP_BAL_SIMPLE_RADIAL model exactly (measured |k2/k1|~2e-7)
  bool dof9=false, free_k2=false, zero_k2=false;
  Scalar equil_floor=-1.0;  // <0 = unset: dof9 defaults to 1e-12, 6-DOF to 0 (bit-compat)
  Scalar intr_damp=1.0;     // weight of the absolute intrinsics damping (0 disables)
  // AUDIT 2026-08-22: max LM retries inside one outer iteration (dof9 only).
  // 0 = round-9 behaviour, where every reject spends an outer iteration.
  int lm_inner_retry=8;
  // AUDIT 2026-08-23: tau-memory experiment, DEFAULT OFF after failing its
  // gates. Two variants (persistent base; warm-started ladder) were both worse
  // than the shipped reset-to-base policy on the problems they targeted
  // (d-142: 1.89s/608k -> 2.31s/684k -> never/718k; f-4585: 28.5s/10.34M ->
  // 44.2s/10.85M -> 39.4s/10.96M). The ladder's rejected attempts are a joint
  // (lambda,tau) search; short-circuiting tau alone degrades accepted steps.
  // Kept behind --tau-persist 1 for future investigation.
  int tau_persist=0;
  for (int i = 1; i < argc; ++i) {
    std::string a = argv[i];
    auto next = [&]() { return std::string(argv[++i]); };
    if (a == "--problem") problem_path = next();
    else if (a == "--algo") algo = next();
    else if (a == "--lam") lam = std::stod(next());
    else if (a == "--lam0") lam0 = std::stod(next());
    else if (a == "--lam1") lam1 = std::stod(next());
    else if (a == "--mu0") mu0 = std::stod(next());
    else if (a == "--tol") tol = std::stod(next());
    else if (a == "--factor") factor = std::stod(next());
    else if (a == "--n_lambda") n_lambda = std::stoi(next());
    else if (a == "--decade_lo") decade_lo = std::stod(next());
    else if (a == "--decade_hi") decade_hi = std::stod(next());
    else if (a == "--lam_floor") lam_floor = std::stod(next());
    else if (a == "--lam_ceil") lam_ceil = std::stod(next());
    else if (a == "--base_lam_cam0") base_lam_cam0 = std::stod(next());
    else if (a == "--base_lam_pt0") base_lam_pt0 = std::stod(next());
    else if (a == "--num_devices") num_devices = std::stoi(next());
    else if (a == "--no_momentum") use_momentum = false;
    else if (a == "--gamma_cap") gamma_cap = std::stod(next());
    else if (a == "--gamma_fixed") gamma_fixed = std::stod(next());
    else if (a == "--aa_window") aa_window = std::stoi(next());
    else if (a == "--j_max") j_max = std::stoi(next());
    else if (a == "--fp32_cholesky") fp32_cholesky = true;
    else if (a == "--subspace_min") subspace_min = true;
    else if (a == "--relpt") r2_relpt = true;
    else if (a == "--tau_pt") r2_tau_pt = std::stod(next());
    else if (a == "--marquardt_pt") r2_marquardt_pt = true;
    else if (a == "--jacobi") r2_jacobi = true;
    else if (a == "--audit") r2_audit = true;
    else if (a == "--aitken") r2_aitken = true;
    else if (a == "--alpha_grid") r2_alpha = true;
    else if (a == "--oracle") r2_oracle = true;
    else if (a == "--no_cheap_first") r2_cheap_first = false;
    else if (a == "--eps_rel") r2_eps_rel = std::stod(next());
    else if (a == "--dump_residuals") dump_residuals = next();
    else if (a == "--dump_true_cost") dump_true_cost = next();
    else if (a == "--fp32_refine") r2_fp32 = true;
    else if (a == "--adaptive_pt") r2_adaptive = true;
    else if (a == "--edge_csr") build_edge_csr = true;
    else if (a == "--span_min") r2_span_min = true;
    else if (a == "--cheb_filter") r2_cheb = true;
    else if (a == "--cheb_tplus") r2_cheb_tplus = std::stod(next());
    else if (a == "--cheb_k_menu") {
      r2_cheb_kmenu.clear();
      std::string s2 = next(); std::stringstream ss(s2); std::string tok;
      while (std::getline(ss, tok, ',')) r2_cheb_kmenu.push_back(std::stoi(tok));
    }
    else if (a == "--hybrid_r_menu") {
      r2_hybrid_rmenu.clear();
      std::string s2 = next(); std::stringstream ss(s2); std::string tok;
      while (std::getline(ss, tok, ',')) r2_hybrid_rmenu.push_back(std::stoi(tok));
    }
    else if (a == "--cheir_gate") r2_cheir_gate = true;
    else if (a == "--fp32_jac") r2_fp32_jac = true;
    else if (a == "--dump_bal") dump_prefix = next();
    else if (a == "--csv") g_csv_path = next();
    else if (a == "--cg-checkpoints") { mf_ckpts.clear(); std::string v=next(); size_t q=0; while(q<v.size()){ size_t c=v.find(',',q); if(c==std::string::npos)c=v.size(); mf_ckpts.push_back(std::stoi(v.substr(q,c-q))); q=c+1; } std::sort(mf_ckpts.begin(),mf_ckpts.end()); }
    else if (a == "--seed-shift") { /* seed = incumbent lam_cam; kept for CLI parity */ lam0 = std::stod(next()); }
    else if (a == "--precond") mf_precond = next();
    else if (a == "--mf-shifts") mf_shifts = std::stoi(next());
    else if (a == "--ew-eta-max") mf_eta = std::stod(next());
    else if (a == "--mf-json") mf_json = next();
    else if (a == "--mf-no-alpha") mf_alpha = false;
    else if (a == "--mf-fp32") mf_fp32 = true;
    else if (a == "--dump_at") { std::string v = next(); size_t q=0; while(q<v.size()){ size_t c=v.find(',',q); if(c==std::string::npos)c=v.size(); dump_iters.push_back(std::stoi(v.substr(q,c-q))); q=c+1; } }
    else if (a == "--kappa") r2_kappa = std::stod(next());
    else if (a == "--theta") r2_theta = std::stod(next());
    else if (a == "--n_ir") r2_n_ir = std::stoi(next());
    else if (a == "--ir_tol") r2_ir_tol = std::stod(next());
    else if (a == "--depths") {
      depths_cli.clear();
      std::string s2 = next(); std::stringstream ss(s2); std::string tok;
      while (std::getline(ss, tok, ',')) depths_cli.push_back(std::stoi(tok));
    }
    else if (a == "--max_iter") max_iter = std::stoi(next());
    else if (a == "--dof9") dof9 = true;
    else if (a == "--free_k2") free_k2 = true;
    else if (a == "--zero_k2") zero_k2 = true;
    else if (a == "--equil-floor") equil_floor = std::stod(next());
    else if (a == "--intr-damp") intr_damp = std::stod(next());
    else if (a == "--lm-inner-retry") lm_inner_retry = std::stoi(next());
    else if (a == "--tau-persist") tau_persist = std::stoi(next());
    else if (a == "--quiet") verbose = false;
    else { PrintUsage(argv[0]); return 1; }
  }
  if (problem_path.empty()) { PrintUsage(argv[0]); return 1; }
  if (dof9 && algo != "mfree_shifted_cg") {
    std::fprintf(stderr, "--dof9 is only implemented for --algo mfree_shifted_cg\n");
    return 1;
  }

  BalData bal = LoadBal(problem_path);
  if (zero_k2) {  // ROUND 10: match the harness's SIMPLE_RADIAL model exactly
    for (int c = 0; c < bal.ncam; ++c) bal.cams[9*c+8] = 0.0;
    std::fprintf(stderr, "[R10] --zero_k2: all k2 set to 0 at load\n");
  }
  int ncam = bal.ncam, npt = bal.npt, nobs = bal.nobs;
  int n = 6 * ncam + 3 * npt;
  std::fprintf(stderr, "Loaded %s: ncam=%d npt=%d nobs=%d n=%d\n", problem_path.c_str(), ncam, npt, nobs, n);

  DeviceProblem p; p.ncam = ncam; p.npt = npt; p.nobs = nobs; p.n = n;
  CUDA_CHECK(cudaMalloc(&p.cam_idx, nobs*sizeof(int)));
  CUDA_CHECK(cudaMalloc(&p.pt_idx, nobs*sizeof(int)));
  CUDA_CHECK(cudaMalloc(&p.uv, 2*nobs*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&p.f, ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&p.k1, ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&p.k2, ncam*sizeof(Scalar)));
  CUDA_CHECK(cudaMemcpy(p.cam_idx, bal.cam_idx.data(), nobs*sizeof(int), cudaMemcpyHostToDevice));
  CUDA_CHECK(cudaMemcpy(p.pt_idx, bal.pt_idx.data(), nobs*sizeof(int), cudaMemcpyHostToDevice));
  CUDA_CHECK(cudaMemcpy(p.uv, bal.uv.data(), 2*nobs*sizeof(Scalar), cudaMemcpyHostToDevice));
    g_dump_prefix = dump_prefix; g_dump_iters = dump_iters;
    g_csv_problem = problem_path;
    MemMark("context + problem data (baseline)");
    if (!dump_prefix.empty()) g_bal_ptr = &bal;
  if (algo == "oca_schur_sparse" || algo == "oca_adaptive_schur_sparse" || algo == "lm_schur_sparse" ||
      algo == "oca_schur_sparse_gn" || algo == "oca_schur_sparse_gn_multilambda" ||
      algo == "oca_schur_sparse_gn_lmadaptive" || algo == "oca_schur_sparse_gn_multilambda_parallel" ||
      algo == "oca_partitioned" || algo == "oca_partitioned_nesterov" || algo == "oca_joint_lambda_depth" ||
      algo == "lm_schur_sparse_aa" || algo == "oca_minres_true" || algo == "oca_joint_lambda_campt_depth" ||
      algo == "oca_curvature_switch" || algo == "oca_joint_lambda_campt_depth_aa" ||
      algo == "oca_joint_lambda_campt_depth_curv" || algo == "oca_joint_lambda_campt_depth_nesterov" ||
      algo == "oca_joint_lambda_campt_depth_submom" || algo == "oca_round2" ||
      algo == "mfree_shifted_cg") {
    // CSR-style point->observation index (topology only, built once): point p's
    // observations are point_obs_list[offsets[p]:offsets[p+1]] -- same
    // construction as reference_oca_schur_sparse.py's build_point_obs_index.
    std::vector<int> offsets;
    std::vector<int> order =
        BuildPointObsCSR(p, bal.pt_idx.data(), npt, nobs, &offsets);
    if (algo == "mfree_shifted_cg") {
      BuildMFreeIndex(p, bal.cam_idx.data(), bal.pt_idx.data(), order, ncam, nobs);
    }
    if (build_edge_csr && algo == "oca_round2") {
      // Round-4 Q1: persistent edge-CSR over the camera co-visibility graph (unique camera pair
      // -> its shared observation-index pairs), for KernelFormSEdges. Two-pass CSR construction,
      // O(sum_p D_p^2) done ONCE here rather than once per (candidate, outer iteration) as the
      // atomic-scatter formation does today.
      auto tb0 = std::chrono::steady_clock::now();
      std::unordered_map<int64_t,int> edge_id;
      edge_id.reserve(1u<<18);
      std::vector<int> h_ci, h_cj, counts;
      long long total_pairs = 0;
      auto get_edge = [&](int cd, int ce) -> int {
        int lo = std::min(cd,ce), hi = std::max(cd,ce);
        int64_t key = (int64_t)lo*ncam + hi;
        auto it = edge_id.find(key);
        if (it != edge_id.end()) return it->second;
        int id = (int)h_ci.size();
        edge_id.emplace(key, id);
        h_ci.push_back(lo); h_cj.push_back(hi); counts.push_back(0);
        return id;
      };
      for (int pp = 0; pp < npt; ++pp) {
        int s0 = offsets[pp], s1 = offsets[pp+1];
        for (int di = s0; di < s1; ++di) {
          int cd = bal.cam_idx[order[di]];
          for (int ei = di+1; ei < s1; ++ei) {
            int ce = bal.cam_idx[order[ei]];
            if (cd == ce) continue;               // same camera can't observe a point twice
            counts[get_edge(cd, ce)]++; ++total_pairs;
          }
        }
      }
      int n_edges = (int)h_ci.size();
      std::vector<int> h_offsets(n_edges+1, 0);
      for (int e = 0; e < n_edges; ++e) h_offsets[e+1] = h_offsets[e] + counts[e];
      std::vector<int> cursor = h_offsets;
      std::vector<int> h_obs_d(total_pairs), h_obs_e(total_pairs);
      for (int pp = 0; pp < npt; ++pp) {
        int s0 = offsets[pp], s1 = offsets[pp+1];
        for (int di = s0; di < s1; ++di) {
          int od = order[di], cd = bal.cam_idx[od];
          for (int ei = di+1; ei < s1; ++ei) {
            int oe = order[ei], ce = bal.cam_idx[oe];
            if (cd == ce) continue;
            int lo = std::min(cd,ce), hi = std::max(cd,ce);
            int id = edge_id[(int64_t)lo*ncam + hi];
            int c = cursor[id]++;
            if (cd == lo) { h_obs_d[c] = od; h_obs_e[c] = oe; }
            else          { h_obs_d[c] = oe; h_obs_e[c] = od; }
          }
        }
      }
      p.n_edges = n_edges;
      CUDA_CHECK(cudaMalloc(&p.edge_ci, n_edges*sizeof(int)));
      CUDA_CHECK(cudaMalloc(&p.edge_cj, n_edges*sizeof(int)));
      CUDA_CHECK(cudaMalloc(&p.edge_offsets, (n_edges+1)*sizeof(int)));
      CUDA_CHECK(cudaMalloc(&p.edge_obs_d, std::max(total_pairs,1LL)*sizeof(int)));
      CUDA_CHECK(cudaMalloc(&p.edge_obs_e, std::max(total_pairs,1LL)*sizeof(int)));
      CUDA_CHECK(cudaMemcpy(p.edge_ci, h_ci.data(), n_edges*sizeof(int), cudaMemcpyHostToDevice));
      CUDA_CHECK(cudaMemcpy(p.edge_cj, h_cj.data(), n_edges*sizeof(int), cudaMemcpyHostToDevice));
      CUDA_CHECK(cudaMemcpy(p.edge_offsets, h_offsets.data(), (n_edges+1)*sizeof(int), cudaMemcpyHostToDevice));
      if (total_pairs > 0) {
        CUDA_CHECK(cudaMemcpy(p.edge_obs_d, h_obs_d.data(), total_pairs*sizeof(int), cudaMemcpyHostToDevice));
        CUDA_CHECK(cudaMemcpy(p.edge_obs_e, h_obs_e.data(), total_pairs*sizeof(int), cudaMemcpyHostToDevice));
      }
      auto tb1 = std::chrono::steady_clock::now();
      std::fprintf(stderr, "edge-CSR build: n_edges=%d total_pairs=%lld (%.2fs)\n",
                   n_edges, total_pairs, std::chrono::duration<double>(tb1-tb0).count());
    }
  }
  { std::vector<Scalar> f(ncam), k1(ncam), k2(ncam), omega(3*ncam), t(3*ncam);
    for (int c = 0; c < ncam; ++c) {
      omega[3*c]=bal.cams[9*c]; omega[3*c+1]=bal.cams[9*c+1]; omega[3*c+2]=bal.cams[9*c+2];
      t[3*c]=bal.cams[9*c+3]; t[3*c+1]=bal.cams[9*c+4]; t[3*c+2]=bal.cams[9*c+5];
      f[c]=bal.cams[9*c+6]; k1[c]=bal.cams[9*c+7]; k2[c]=bal.cams[9*c+8];
    }
    CUDA_CHECK(cudaMemcpy(p.f, f.data(), ncam*sizeof(Scalar), cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemcpy(p.k1, k1.data(), ncam*sizeof(Scalar), cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemcpy(p.k2, k2.data(), ncam*sizeof(Scalar), cudaMemcpyHostToDevice));

    DeviceState s; AllocState(s, ncam, npt, dof9);
    Scalar* d_omega; CUDA_CHECK(cudaMalloc(&d_omega, 3*ncam*sizeof(Scalar)));
    CUDA_CHECK(cudaMemcpy(d_omega, omega.data(), 3*ncam*sizeof(Scalar), cudaMemcpyHostToDevice));
    KernelExpSO3All<<<GridSize(ncam),256>>>(d_omega, s.R, ncam);
    CUDA_CHECK(cudaMemcpy(s.t, t.data(), 3*ncam*sizeof(Scalar), cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemcpy(s.X, bal.pts.data(), 3*npt*sizeof(Scalar), cudaMemcpyHostToDevice));
    cudaFree(d_omega);
    if (dof9) {  // ROUND 10: state-owned intrinsics [f|k1|k2], initialised from the input
      CUDA_CHECK(cudaMemcpy(s.intr,          f.data(),  ncam*sizeof(Scalar), cudaMemcpyHostToDevice));
      CUDA_CHECK(cudaMemcpy(s.intr + ncam,   k1.data(), ncam*sizeof(Scalar), cudaMemcpyHostToDevice));
      CUDA_CHECK(cudaMemcpy(s.intr + 2*ncam, k2.data(), ncam*sizeof(Scalar), cudaMemcpyHostToDevice));
      std::fprintf(stderr, "[R10] --dof9: refining f,k1%s per camera (%d cameras)\n",
                   free_k2 ? ",k2" : "", ncam);
    }

    Diagnostics diag_init = ComputeDiagnostics(p, s);

    CUDA_CHECK(cudaDeviceSynchronize());  // flush lazy CUDA/cuSOLVER context init before timing
    auto t0 = std::chrono::steady_clock::now();
    RunLog log;
    if (algo == "lm") log = SolveLM(p, s, mu0, tol, max_iter, verbose);
    else if (algo == "oca") log = SolveOCA(p, s, lam, tol, max_iter, verbose);
    else if (algo == "oca_adaptive") log = SolveOCAAdaptive(p, s, lam0, lam1, tol, max_iter, verbose);
    else if (algo == "oca_schur") log = SolveOCASchur(p, s, lam, tol, max_iter, verbose);
    else if (algo == "oca_adaptive_schur") log = SolveOCAAdaptiveSchur(p, s, lam0, lam1, tol, max_iter, verbose);
    else if (algo == "oca_schur_sparse") log = SolveOCASchurSparse(p, s, lam, tol, max_iter, verbose);
    else if (algo == "oca_adaptive_schur_sparse") log = SolveOCAAdaptiveSchurSparse(p, s, lam0, lam1, tol, max_iter, verbose);
    else if (algo == "lm_schur_sparse") log = SolveLMSchurSparse(p, s, mu0, tol, max_iter, verbose);
    else if (algo == "oca_daba_style") log = SolveOCADabaStyle(p, s, lam, factor, tol, max_iter, verbose);
    else if (algo == "oca_daba_multilambda") log = SolveOCADabaMultiLambda(p, s, factor, n_lambda, decade_lo, decade_hi,
                                                                            lam_floor, lam_ceil, base_lam_cam0, base_lam_pt0,
                                                                            tol, max_iter, verbose);
    else if (algo == "oca_schur_sparse_gn") log = SolveOCASchurSparseGN(p, s, lam, tol, max_iter, verbose);
    else if (algo == "oca_schur_sparse_gn_lmadaptive") log = SolveOCASchurSparseGNLMAdaptive(p, s, mu0, tol, max_iter, verbose);
    else if (algo == "oca_schur_sparse_gn_multilambda") log = SolveOCASchurSparseGNMultiLambda(
        p, s, lam, tol, max_iter, verbose, n_lambda, decade_hi, /*max_escalations=*/25);
    else if (algo == "oca_schur_sparse_gn_multilambda_parallel") log = SolveOCASchurSparseGNMultiLambdaParallel(
        p, s, lam, tol, max_iter, verbose, n_lambda, decade_hi, /*max_escalations=*/25);
    else if (algo == "oca_partitioned") {
      std::vector<int> device_of_cam, device_of_pt;
      BuildContiguousPartition(ncam, npt, num_devices, bal.cam_idx, bal.pt_idx, device_of_cam, device_of_pt);
      log = SolveOCASchurPartitioned(p, s, device_of_cam, device_of_pt, factor, lam, tol, max_iter, verbose);
    }
    else if (algo == "oca_partitioned_nesterov") {
      std::vector<int> device_of_cam, device_of_pt;
      BuildContiguousPartition(ncam, npt, num_devices, bal.cam_idx, bal.pt_idx, device_of_cam, device_of_pt);
      log = SolveOCAPartitionedNesterov(p, s, device_of_cam, device_of_pt, factor, lam, tol, max_iter, verbose,
                                         use_momentum, /*max_escalations=*/25, gamma_cap, gamma_fixed);
    }
    else if (algo == "oca_joint_lambda_depth") log = SolveOCAJointLambdaDepth(
        p, s, lam, tol, max_iter, verbose, n_lambda, decade_hi, /*max_escalations=*/25, depths_cli, fp32_cholesky, subspace_min);
    else if (algo == "lm_schur_sparse_aa") log = SolveLMSchurSparseAA(p, s, mu0, tol, max_iter, verbose, aa_window);
    else if (algo == "oca_minres_true") log = SolveOCAMinresSchurSparse(p, s, lam, j_max, tol, max_iter, verbose);
    else if (algo == "oca_joint_lambda_campt_depth") log = SolveOCAJointLambdaCamPtDepth(
        p, s, lam, tol, max_iter, verbose, n_lambda, n_lambda, decade_hi, /*max_escalations=*/25, depths_cli, subspace_min);
    else if (algo == "oca_curvature_switch") log = SolveOCACurvatureSwitch(p, s, lam, j_max, tol, max_iter, verbose);
    else if (algo == "oca_joint_lambda_campt_depth_aa") log = SolveOCAJointLambdaCamPtDepthAA(
        p, s, lam, tol, max_iter, verbose, n_lambda, n_lambda, decade_hi, /*max_escalations=*/25, depths_cli, subspace_min, aa_window);
    else if (algo == "oca_joint_lambda_campt_depth_curv") log = SolveOCAJointLambdaCamPtDepthCurv(
        p, s, lam, tol, max_iter, verbose, n_lambda, n_lambda, decade_hi, /*max_escalations=*/25, depths_cli, subspace_min);
    else if (algo == "oca_joint_lambda_campt_depth_nesterov") log = SolveOCAJointLambdaCamPtDepthNesterov(
        p, s, lam, tol, max_iter, verbose, n_lambda, n_lambda, decade_hi, /*max_escalations=*/25, depths_cli, subspace_min, use_momentum, gamma_cap);
    else if (algo == "oca_joint_lambda_campt_depth_submom") log = SolveOCAJointLambdaCamPtDepthSubspaceMomentum(
        p, s, lam, tol, max_iter, verbose, n_lambda, n_lambda, decade_hi, /*max_escalations=*/25, depths_cli, aa_window);
    else if (algo == "mfree_shifted_cg") log = dof9
      ? SolveMFreeShiftedCG<9>(
        p, s, lam0, max_iter, verbose, r2_tau_pt, mf_ckpts, mf_shifts,
        mf_precond == "equil", mf_eta, mf_alpha, mf_json, mf_fp32, free_k2 ? 1.0 : 0.0,
        // AUDIT 2026-08-22: default was 1e-12. Measured to collapse the Krylov
        // solve at CD=9 (final-3068: 1.1 matvecs/outer, 16/61 accepts, cost
        // 4.65M -> 28.3 matvecs/outer, 61/61 accepts, cost 1.71M with 0), and
        // it did not help final-4585, the scene it was added for. Default 0;
        // --equil-floor still available to re-enable it.
        equil_floor < 0.0 ? 0.0 : equil_floor, intr_damp, lm_inner_retry, tau_persist!=0)
      : SolveMFreeShiftedCG<6>(
        p, s, lam0, max_iter, verbose, r2_tau_pt, mf_ckpts, mf_shifts,
        mf_precond == "equil", mf_eta, mf_alpha, mf_json, mf_fp32, 1.0,
        // AUDIT 2026-08-22: 0 pins CD=6 to round-9 behaviour (every reject
        // spends an outer iteration), keeping the regression trace comparable.
        equil_floor < 0.0 ? 0.0 : equil_floor, 1.0, /*max_inner_retry=*/0);
    else if (algo == "oca_round2") log = SolveOCARound2(
        p, s, lam, tol, max_iter, verbose, n_lambda, n_lambda, decade_hi, /*max_escalations=*/25, depths_cli,
        r2_relpt, r2_tau_pt, r2_marquardt_pt, r2_jacobi, r2_audit, r2_aitken, r2_alpha, r2_oracle,
        r2_cheap_first, r2_eps_rel, r2_fp32, r2_n_ir, r2_ir_tol, r2_adaptive, r2_kappa, r2_theta,
        build_edge_csr, r2_span_min, r2_cheb, r2_cheb_tplus, r2_cheb_kmenu, r2_hybrid_rmenu, r2_cheir_gate, r2_fp32_jac);
    else { PrintUsage(argv[0]); return 1; }
    CUDA_CHECK(cudaDeviceSynchronize());
    auto t1 = std::chrono::steady_clock::now();
    double solve_seconds = std::chrono::duration<double>(t1 - t0).count();

    Diagnostics diag_final = ComputeDiagnostics(p, s);

    // Per-observation residual dump: writes sqrt(rx^2+ry^2) in pixels for every observation at the
    // final state, so the cost distribution can be analysed offline (a single observation's cost
    // contribution is 0.5*err^2). Used to test whether a dataset's high cost-per-observation is
    // outlier-driven rather than solver behaviour.
    if (!dump_residuals.empty()) {
      Scalar *reproj_err; int *obs_ch, *pt_ch;
      CUDA_CHECK(cudaMalloc(&reproj_err, p.nobs*sizeof(Scalar)));
      CUDA_CHECK(cudaMalloc(&obs_ch, p.nobs*sizeof(int)));
      CUDA_CHECK(cudaMalloc(&pt_ch, p.npt*sizeof(int)));
      CUDA_CHECK(cudaMemset(pt_ch, 0, p.npt*sizeof(int)));
      KernelDiagnostics<<<GridSize(p.nobs),256>>>(p.cam_idx, p.pt_idx, p.uv, s.R, s.t, s.X, p.f, p.k1, p.k2,
                                                    p.nobs, reproj_err, obs_ch, pt_ch);
      std::vector<Scalar> h_err(p.nobs);
      std::vector<int> h_ch(p.nobs);
      CUDA_CHECK(cudaMemcpy(h_err.data(), reproj_err, p.nobs*sizeof(Scalar), cudaMemcpyDeviceToHost));
      CUDA_CHECK(cudaMemcpy(h_ch.data(), obs_ch, p.nobs*sizeof(int), cudaMemcpyDeviceToHost));
      cudaFree(reproj_err); cudaFree(obs_ch); cudaFree(pt_ch);
      std::FILE* fp = std::fopen(dump_residuals.c_str(), "w");
      std::fprintf(fp, "err_px,cheirality\n");
      for (int o = 0; o < p.nobs; ++o) std::fprintf(fp, "%.8g,%d\n", h_err[o], h_ch[o]);
      std::fclose(fp);
      std::fprintf(stderr, "wrote %d per-observation residuals to %s\n", p.nobs, dump_residuals.c_str());
    }

    // Per-observation TRUE cost dump (unconditional on cheirality, unlike --dump_residuals'
    // sentinel -1 for flipped observations) -- sum over all rows reproduces the reported
    // final_cost exactly, so this is safe to partition into arbitrary subsets offline (e.g.
    // "clean in both of two solvers' final states") for analyses like CONTEXT S8.1's blind spot.
    if (!dump_true_cost.empty()) {
      Scalar *cost_arr; int *obs_ch;
      CUDA_CHECK(cudaMalloc(&cost_arr, p.nobs*sizeof(Scalar)));
      CUDA_CHECK(cudaMalloc(&obs_ch, p.nobs*sizeof(int)));
      KernelTrueResidualDump<<<GridSize(p.nobs),256>>>(p.cam_idx, p.pt_idx, p.uv, s.R, s.t, s.X,
                                                       INTR_F(p,s), INTR_K1(p,s), INTR_K2(p,s),
                                                         p.nobs, cost_arr, obs_ch);
      std::vector<Scalar> h_cost(p.nobs);
      std::vector<int> h_ch(p.nobs);
      CUDA_CHECK(cudaMemcpy(h_cost.data(), cost_arr, p.nobs*sizeof(Scalar), cudaMemcpyDeviceToHost));
      CUDA_CHECK(cudaMemcpy(h_ch.data(), obs_ch, p.nobs*sizeof(int), cudaMemcpyDeviceToHost));
      cudaFree(cost_arr); cudaFree(obs_ch);
      std::FILE* fp = std::fopen(dump_true_cost.c_str(), "w");
      std::fprintf(fp, "cost_contrib,cheirality\n");
      double check_sum = 0.0;
      for (int o = 0; o < p.nobs; ++o) { std::fprintf(fp, "%.10g,%d\n", h_cost[o], h_ch[o]); check_sum += h_cost[o]; }
      std::fclose(fp);
      std::fprintf(stderr, "wrote %d true per-observation cost contributions to %s (sum=%.6f, should match final_cost above)\n",
                   p.nobs, dump_true_cost.c_str(), check_sum);
    }

    std::printf("RESULT algo=%s iters=%d final_cost=%.10f solve_seconds=%.6f\n",
                algo.c_str(), log.iters.back(), log.costs.back(), solve_seconds);
    std::printf("DIAGNOSTICS median_reproj_err_px %.6f -> %.6f | cheirality_violations(obs) %d -> %d | "
                "cheirality_violations(pts, of %d) %d -> %d\n",
                diag_init.median_reproj_err_px, diag_final.median_reproj_err_px,
                diag_init.num_obs_cheirality_violations, diag_final.num_obs_cheirality_violations,
                p.npt, diag_init.num_pt_cheirality_violations, diag_final.num_pt_cheirality_violations);
  }
  return 0;
}

int main(int argc, char** argv) {
  try {
    return OcaCliMain(argc, argv);
  } catch (const std::exception& e) {
    std::fprintf(stderr, "%s\n", e.what());
    return EXIT_FAILURE;
  }
}
#endif  // OCA_CORE_LIBRARY

// ============================================================================
// Embeddable core API (oca_core.h).
//
// Deliberately in this translation unit rather than a separate file: the CLI
// above and the COLMAP backend must run the SAME kernels and the SAME LM
// policy. Round 10 found four defects in that policy; a forked copy would have
// to rediscover each one. See BA_RESEARCH_HISTORY/round10/STATUS.md.
// ============================================================================
#include "oca_core.h"

namespace oca {

bool IsAvailable() {
  int n = 0;
  return cudaGetDeviceCount(&n) == cudaSuccess && n > 0;
}

std::string VersionString() {
  return "oca matrix-free multi-shift (round 10, fp64 state, Scalar=double)";
}

namespace {

// Owns every device allocation for one Solve() so a throw unwinds cleanly.
struct DeviceArena {
  std::vector<void*> blocks;
  void* Alloc(size_t bytes) {
    void* q = nullptr;
    CUDA_CHECK(cudaMalloc(&q, bytes));
    blocks.push_back(q);
    return q;
  }
  ~DeviceArena() {
    for (void* q : blocks) cudaFree(q);
  }
};

// oca_cuda's --mf-eta / --mf-alpha defaults. Pinned here rather than exposed:
// the two wrappers must descend identically, and a COLMAP caller has no basis
// on which to tune them.
constexpr Scalar kCliEtaMax = 0.5;
constexpr bool kCliUseAlpha = true;

const char* CheckProblem(const Problem& pr, const State* st) {
  if (st == nullptr) return "state must not be null";
  if (pr.num_cameras <= 0) return "num_cameras must be positive";
  if (pr.num_points <= 0) return "num_points must be positive";
  if (pr.num_observations <= 0) return "num_observations must be positive";
  if (!pr.camera_index || !pr.point_index || !pr.observations)
    return "problem arrays must not be null";
  if (!st->rotations || !st->translations || !st->points)
    return "state pose/point arrays must not be null";
  if (!st->focal || !st->k1 || !st->k2)
    return "state intrinsics arrays must not be null (read even at 6 DoF)";
  for (int o = 0; o < pr.num_observations; ++o) {
    if (pr.camera_index[o] < 0 || pr.camera_index[o] >= pr.num_cameras)
      return "camera_index out of range";
    if (pr.point_index[o] < 0 || pr.point_index[o] >= pr.num_points)
      return "point_index out of range";
  }
  if (pr.calibration_index != nullptr) {
    if (pr.num_calibrations <= 0 || pr.num_calibrations > pr.num_cameras)
      return "num_calibrations must be in [1, num_cameras]";
    // Every camera in a group must start from the same intrinsics, or the
    // shared value the solver converges to would depend on which camera the
    // caller happened to read back.
    std::vector<int> first(pr.num_calibrations, -1);
    for (int c = 0; c < pr.num_cameras; ++c) {
      const int g = pr.calibration_index[c];
      if (g < 0 || g >= pr.num_calibrations)
        return "calibration_index out of range";
      if (first[g] < 0) { first[g] = c; continue; }
      const int f0 = first[g];
      if (st->focal[c] != st->focal[f0] || st->k1[c] != st->k1[f0] ||
          st->k2[c] != st->k2[f0])
        return "cameras sharing a calibration_index must start from identical "
               "focal/k1/k2";
    }
  }
  return nullptr;
}

}  // namespace

// OCA_PROFILE also breaks down the pre-solve setup, which the crossing
// analysis hides (it normalises to each solver's first logged iteration) but
// the user still pays: measured 0.48-0.74 s between the wrapper's "BA
// options" line and MFREE's first outer, vs Caspar's 0.06-0.08 s.
#define OCA_SETUP_MARK(tag)                                                    \
  if (setup_prof) {                                                            \
    cudaDeviceSynchronize();                                                   \
    const double _e = std::chrono::duration<double>(                           \
                          std::chrono::steady_clock::now() - _tsetup).count(); \
    std::printf("  [SETUP] %-28s %7.1f ms\n", tag, 1e3 * (_e - _tprev));       \
    _tprev = _e;                                                               \
  }

Result Solve(const Problem& pr, const Options& opt, State* st) {
  const bool setup_prof = getenv("OCA_PROFILE") != nullptr;
  const auto _tsetup = std::chrono::steady_clock::now();
  double _tprev = 0.0;
  Result res;
  if (const char* bad = CheckProblem(pr, st)) {
    res.message = bad;
    return res;
  }
  if (!IsAvailable()) {
    res.message = "no CUDA device available";
    return res;
  }

  const int ncam = pr.num_cameras, npt = pr.num_points, nobs = pr.num_observations;

  try {
    if (opt.gpu_index >= 0) CUDA_CHECK(cudaSetDevice(opt.gpu_index));

    DeviceArena arena;
    DeviceProblem p;
    p.ncam = ncam; p.npt = npt; p.nobs = nobs;
    p.n = 6 * ncam + 3 * npt;
    p.cam_idx = static_cast<int*>(arena.Alloc(nobs * sizeof(int)));
    p.pt_idx  = static_cast<int*>(arena.Alloc(nobs * sizeof(int)));
    p.uv      = static_cast<Scalar*>(arena.Alloc(2 * nobs * sizeof(Scalar)));
    p.f       = static_cast<Scalar*>(arena.Alloc(ncam * sizeof(Scalar)));
    p.k1      = static_cast<Scalar*>(arena.Alloc(ncam * sizeof(Scalar)));
    p.k2      = static_cast<Scalar*>(arena.Alloc(ncam * sizeof(Scalar)));
    CUDA_CHECK(cudaMemcpy(p.cam_idx, pr.camera_index, nobs * sizeof(int),
                          cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemcpy(p.pt_idx, pr.point_index, nobs * sizeof(int),
                          cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemcpy(p.uv, pr.observations, 2 * nobs * sizeof(Scalar),
                          cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemcpy(p.f, st->focal, ncam * sizeof(Scalar), cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemcpy(p.k1, st->k1, ncam * sizeof(Scalar), cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemcpy(p.k2, st->k2, ncam * sizeof(Scalar), cudaMemcpyHostToDevice));

    // Exactly the indexing the CLI builds -- shared helpers, not a copy.
    const std::vector<int> order =
        BuildPointObsCSR(p, pr.point_index, npt, nobs);
    BuildMFreeIndex(p, pr.camera_index, pr.point_index, order, ncam, nobs);
    for (void* q : {static_cast<void*>(p.point_obs_offsets),
                    static_cast<void*>(p.point_obs_list),
                    static_cast<void*>(p.obs2pslot),
                    static_cast<void*>(p.obs2cslot),
                    static_cast<void*>(p.mf_scam),
                    static_cast<void*>(p.mf_spt),
                    static_cast<void*>(p.mf_coff),
                    static_cast<void*>(p.mf_cspt)}) {
      arena.blocks.push_back(q);
    }

    if (pr.calibration_index != nullptr) {
      p.ncalib = pr.num_calibrations;
      p.calib_of_cam = static_cast<int*>(arena.Alloc(ncam * sizeof(int)));
      CUDA_CHECK(cudaMemcpy(p.calib_of_cam, pr.calibration_index,
                            ncam * sizeof(int), cudaMemcpyHostToDevice));
    }

    const bool dof9 = opt.refine_intrinsics;
    DeviceState s;
    s.R = static_cast<Scalar*>(arena.Alloc(9 * ncam * sizeof(Scalar)));
    s.t = static_cast<Scalar*>(arena.Alloc(3 * ncam * sizeof(Scalar)));
    s.X = static_cast<Scalar*>(arena.Alloc(3 * npt * sizeof(Scalar)));
    if (dof9) {
      s.intr = static_cast<Scalar*>(arena.Alloc(3 * ncam * sizeof(Scalar)));
      s.ncam_for_intr = ncam;
    }
    // Rotations arrive as matrices, so unlike the CLI (which reads angle-axis
    // from BAL and runs KernelExpSO3All) there is nothing to exponentiate.
    CUDA_CHECK(cudaMemcpy(s.R, st->rotations, 9 * ncam * sizeof(Scalar),
                          cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemcpy(s.t, st->translations, 3 * ncam * sizeof(Scalar),
                          cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemcpy(s.X, st->points, 3 * npt * sizeof(Scalar),
                          cudaMemcpyHostToDevice));
    if (dof9) {
      CUDA_CHECK(cudaMemcpy(s.intr, st->focal, ncam * sizeof(Scalar),
                            cudaMemcpyHostToDevice));
      CUDA_CHECK(cudaMemcpy(s.intr + ncam, st->k1, ncam * sizeof(Scalar),
                            cudaMemcpyHostToDevice));
      CUDA_CHECK(cudaMemcpy(s.intr + 2 * ncam, st->k2, ncam * sizeof(Scalar),
                            cudaMemcpyHostToDevice));
    }

    OCA_SETUP_MARK("upload + index build");
    const Diagnostics diag0 = ComputeDiagnostics(p, s);
    OCA_SETUP_MARK("initial diagnostics");
    res.initial_cost = ComputeCost(p, s);
    res.initial_median_error_px = diag0.median_reproj_err_px;
    OCA_SETUP_MARK("initial cost");

    std::vector<int> ckpts = opt.cg_checkpoints;
    if (ckpts.empty()) ckpts.push_back(opt.max_iterations);

    Scalar final_lam_bal = 0.0;
    RunLog log =
        dof9 ? SolveMFreeShiftedCG<9>(
                   p, s, opt.initial_lambda, opt.max_iterations, opt.verbose,
                   opt.point_damping, ckpts, opt.num_shifts, opt.equilibrate,
                   /*ew_eta_max=*/kCliEtaMax, /*use_alpha=*/kCliUseAlpha,
                   /*jsonpath=*/"",
                   opt.use_fp32_fragments, opt.refine_k2 ? 1.0 : 0.0,
                   /*equil_floor=*/0.0, /*intr_damp=*/1.0,
                   opt.max_inner_retries, /*tau_persist=*/false,
                   opt.func_tolerance, opt.max_consecutive_failures,
                   opt.robust_kernel, opt.robust_scale2, opt.robust_nu,
                   opt.fast_opening, opt.fast_opening_depth, &final_lam_bal)
             : SolveMFreeShiftedCG<6>(
                   p, s, opt.initial_lambda, opt.max_iterations, opt.verbose,
                   opt.point_damping, ckpts, opt.num_shifts, opt.equilibrate,
                   /*ew_eta_max=*/kCliEtaMax, /*use_alpha=*/kCliUseAlpha,
                   /*jsonpath=*/"",
                   opt.use_fp32_fragments, /*k2mask=*/1.0,
                   /*equil_floor=*/0.0, /*intr_damp=*/1.0,
                   // Was hardcoded 0, silently disabling the inner-retry
                   // (lambda+tau escalation) ladder on the fixed-intrinsics
                   // path only. On final-4585 -- which the round10 history
                   // shows NEEDS retries (3-reject/1-accept pattern) -- that
                   // starved the solver completely: 0 accepted steps, output
                   // identical to input, while the dof9 path solved it fine.
                   opt.max_inner_retries, /*tau_persist=*/false,
                   opt.func_tolerance, opt.max_consecutive_failures,
                   opt.robust_kernel, opt.robust_scale2, opt.robust_nu,
                   opt.fast_opening, opt.fast_opening_depth, &final_lam_bal);
    CUDA_CHECK(cudaDeviceSynchronize());

    // Write the solution back through the caller's arrays.
    CUDA_CHECK(cudaMemcpy(st->rotations, s.R, 9 * ncam * sizeof(Scalar),
                          cudaMemcpyDeviceToHost));
    CUDA_CHECK(cudaMemcpy(st->translations, s.t, 3 * ncam * sizeof(Scalar),
                          cudaMemcpyDeviceToHost));
    CUDA_CHECK(cudaMemcpy(st->points, s.X, 3 * npt * sizeof(Scalar),
                          cudaMemcpyDeviceToHost));
    if (dof9) {
      CUDA_CHECK(cudaMemcpy(st->focal, s.intr, ncam * sizeof(Scalar),
                            cudaMemcpyDeviceToHost));
      CUDA_CHECK(cudaMemcpy(st->k1, s.intr + ncam, ncam * sizeof(Scalar),
                            cudaMemcpyDeviceToHost));
      if (opt.refine_k2) {
        CUDA_CHECK(cudaMemcpy(st->k2, s.intr + 2 * ncam, ncam * sizeof(Scalar),
                              cudaMemcpyDeviceToHost));
      }
    }

    const Diagnostics diag1 = ComputeDiagnostics(p, s);
    res.final_cost = ComputeCost(p, s);
    // Under a robust kernel the reported endpoints must be the ROBUST
    // objective the solver actually minimized (the bare ComputeCost calls
    // around this block are L2). The solver's own log already carries it.
    if (opt.robust_kernel && !log.costs.empty()) {
      res.initial_cost = log.costs.front();
      res.final_cost = log.costs.back();
    }
    res.final_median_error_px = diag1.median_reproj_err_px;
    res.final_lambda = (double)final_lam_bal;
    res.cost_per_iteration.assign(log.costs.begin(), log.costs.end());
    // costs[0] is the initial cost, so the accepted-step count is one less.
    res.iterations = std::max<int>(0, static_cast<int>(log.costs.size()) - 1);
    res.success = true;
    return res;
  } catch (const std::exception& e) {
    res.success = false;
    res.message = e.what();
    return res;
  }
}

Result SolveRigFisheye(const RigFisheyeProblem& pr,
                       const RigFisheyeOptions& opt,
                       RigFisheyeState* st) {
  using namespace rigfisheye;
  Result res;
  if (pr.num_images<=0||pr.num_frames<=0||pr.num_sensors<=0||
      pr.num_calibrations<=0||pr.num_points<=0||pr.num_observations<=0){
    res.message="rigfisheye: empty problem"; return res; }
  for (const void* q : {static_cast<const void*>(pr.frame_of_image),
                        static_cast<const void*>(pr.sensor_of_image),
                        static_cast<const void*>(pr.calibration_of_image),
                        static_cast<const void*>(pr.camera_index),
                        static_cast<const void*>(pr.point_index),
                        static_cast<const void*>(pr.observations)})
    if (q==nullptr){ res.message="rigfisheye: null problem pointer"; return res; }
  if (!st||!st->frame_rotations||!st->frame_translations||!st->sensor_rotations||
      !st->sensor_translations||!st->intrinsics||!st->points){
    res.message="rigfisheye: null state pointer"; return res; }
  if (!IsAvailable()){ res.message="no CUDA device available"; return res; }
  const int ncam=pr.num_images, npt=pr.num_points, nobs=pr.num_observations;
  try {
    if (opt.gpu_index>=0) CUDA_CHECK(cudaSetDevice(opt.gpu_index));
    DeviceArena arena;
    RFDeviceProblem p;
    p.ncam=ncam; p.nframes=pr.num_frames; p.nsensors=pr.num_sensors;
    p.ncalib=pr.num_calibrations; p.npt=npt; p.nobs=nobs;
    auto UpI=[&](const int* h,size_t n){ int* d=(int*)arena.Alloc(n*sizeof(int));
      CUDA_CHECK(cudaMemcpy(d,h,n*sizeof(int),cudaMemcpyHostToDevice)); return d; };
    auto UpS=[&](const double* h,size_t n){ Scalar* d=(Scalar*)arena.Alloc(n*sizeof(Scalar));
      CUDA_CHECK(cudaMemcpy(d,h,n*sizeof(Scalar),cudaMemcpyHostToDevice)); return d; };
    p.cam_idx=UpI(pr.camera_index,nobs); p.pt_idx=UpI(pr.point_index,nobs);
    p.frame_of_cam=UpI(pr.frame_of_image,ncam);
    p.sensor_of_cam=UpI(pr.sensor_of_image,ncam);
    p.calib_of_cam=UpI(pr.calibration_of_image,ncam);
    p.uv=UpS(pr.observations,2ul*nobs);
    // Free-sensor maps. Sensor slot 0 is by construction the shared identity
    // for reference sensors and is never freed.
    {
      std::vector<int> slot_of_sensor(pr.num_sensors,-1);
      int nf=0;
      if (opt.refine_sensor_from_rig)
        for (int q2=1;q2<pr.num_sensors;++q2) slot_of_sensor[q2]=nf++;
      std::vector<int> free_of_cam(ncam,-1);
      for (int q2=0;q2<ncam;++q2)
        free_of_cam[q2]=slot_of_sensor[pr.sensor_of_image[q2]];
      p.nfree_sensors=nf;
      p.free_sensor_of_cam=UpI(free_of_cam.data(),ncam);
      p.free_slot_of_sensor=UpI(slot_of_sensor.data(),pr.num_sensors);
    }
    Scalar hmask[RF_NI]={opt.refine_focal?1.0:0.0,opt.refine_focal?1.0:0.0,
                         opt.refine_principal_point?1.0:0.0,opt.refine_principal_point?1.0:0.0,
                         opt.refine_distortion?1.0:0.0,opt.refine_distortion?1.0:0.0,
                         opt.refine_distortion?1.0:0.0,opt.refine_distortion?1.0:0.0};
    p.imask=(Scalar*)arena.Alloc(RF_NI*sizeof(Scalar));
    CUDA_CHECK(cudaMemcpy(p.imask,hmask,RF_NI*sizeof(Scalar),cudaMemcpyHostToDevice));
    // CSR + slot maps through the shared helpers, via a scratch DeviceProblem.
    DeviceProblem q; q.ncam=ncam; q.npt=npt; q.nobs=nobs;
    const std::vector<int> order=BuildPointObsCSR(q,pr.point_index,npt,nobs);
    BuildMFreeIndex(q,pr.camera_index,pr.point_index,order,ncam,nobs);
    for (void* b : {static_cast<void*>(q.point_obs_offsets),
                    static_cast<void*>(q.point_obs_list),
                    static_cast<void*>(q.obs2pslot),
                    static_cast<void*>(q.obs2cslot),
                    static_cast<void*>(q.mf_scam),
                    static_cast<void*>(q.mf_spt),
                    static_cast<void*>(q.mf_coff),
                    static_cast<void*>(q.mf_cspt)})
      arena.blocks.push_back(b);
    p.point_obs_offsets=q.point_obs_offsets; p.point_obs_list=q.point_obs_list;
    p.obs2pslot=q.obs2pslot; p.obs2cslot=q.obs2cslot;
    p.mf_scam=q.mf_scam; p.mf_spt=q.mf_spt; p.mf_coff=q.mf_coff; p.mf_cspt=q.mf_cspt;

    RFDeviceState s; RFAlloc(s,p.nframes,p.nsensors,p.ncalib,ncam,npt);
    struct RFGuard { RFDeviceState* s; ~RFGuard(){ RFFree(*s); } } guard{&s};
    auto Up=[&](Scalar* d,const double* h,size_t n){
      CUDA_CHECK(cudaMemcpy(d,h,n*sizeof(Scalar),cudaMemcpyHostToDevice)); };
    Up(s.Rf,st->frame_rotations,9ul*p.nframes);
    Up(s.tf,st->frame_translations,3ul*p.nframes);
    Up(s.Rs,st->sensor_rotations,9ul*p.nsensors);
    Up(s.ts,st->sensor_translations,3ul*p.nsensors);
    Up(s.intr,st->intrinsics,(size_t)RF_NI*p.ncalib);
    Up(s.X,st->points,3ul*npt);

    // Same checkpoint/shift defaults as oca::Solve's Options.
    std::vector<int> ckpts={8,16,32,64,128};
    Scalar final_lam=0.0;
    RunLog log=SolveRigFisheye(p,s,(Scalar)opt.initial_lambda,opt.max_iterations,
        opt.verbose,(Scalar)opt.point_damping,ckpts,/*n_shifts=*/5,
        /*use_equil=*/true,kCliEtaMax,kCliUseAlpha,opt.use_fp32_fragments,
        opt.max_inner_retries,(Scalar)opt.func_tolerance,
        opt.max_consecutive_failures,opt.gauge_frame,&final_lam,
        opt.robust_kernel,(Scalar)opt.robust_scale2,(Scalar)opt.robust_nu);
    res.final_lambda=(double)final_lam;

    auto Down=[&](double* h,const Scalar* d,size_t n){
      CUDA_CHECK(cudaMemcpy(h,d,n*sizeof(Scalar),cudaMemcpyDeviceToHost)); };
    Down(st->frame_rotations,s.Rf,9ul*p.nframes);
    Down(st->frame_translations,s.tf,3ul*p.nframes);
    Down(st->sensor_rotations,s.Rs,9ul*p.nsensors);
    Down(st->sensor_translations,s.ts,3ul*p.nsensors);
    Down(st->intrinsics,s.intr,(size_t)RF_NI*p.ncalib);
    Down(st->points,s.X,3ul*npt);

    res.initial_cost=log.costs.front(); res.final_cost=log.costs.back();
    res.cost_per_iteration.assign(log.costs.begin(),log.costs.end());
    res.iterations=std::max<int>(0,(int)log.costs.size()-1);
    res.success=true;
  } catch (const std::exception& e) {
    res.success=false; res.message=e.what();
  }
  return res;
}

}  // namespace oca
