// =============================================================================
// Round 12: OPENCV_FISHEYE + rig solve path.
//
// This file is #included by oca_cuda.cu immediately before SolveMFreeShiftedCG
// and is the ONLY place the fisheye/rig machinery lives: the BAL kernels, the
// champion solve path, and the CLI are not modified. Everything here reuses
// the residual-agnostic matrix-free kernels (MFPass1/2, MFRhsPrime, MFDiagK,
// MFPointFactor, MFVinvApply, MFBackSub, MFDiagHcc, MFMakeEquil, MFScaleVec,
// MFAlphaScale) at CD=14 and swaps only what is residual- or rig-specific.
//
// Model
//   image pose      cam_from_world = sensor_from_rig(s) o rig_from_world(F)
//   camera tangent  [dw3 dt3 | dfx dfy dcx dcy dk1 dk2 dk3 dk4]   (14)
//   reduced space   [6*nframes frame tangents | 8*ncalib intrinsics]
//
// The rig is a tangent-space linear constraint: with the retraction
// R <- exp(dw) R, t <- t + dt applied to the FRAME, the induced image-pose
// tangent is dw_cam = R_S dw_frame, dt_cam = R_S dt_frame (exact, not first
// order), so B has 3x3 rotation blocks in the pose section and 0/1 indicator
// entries in the intrinsics section -- round 11's calibration-group
// architecture with rotations instead of indicators. All numerical kernels
// see the full 14-per-image space; CG runs in the reduced one.
//
// v1 limits (checked by the adapter, documented in oca_core.h):
//   * sensor_from_rig is HELD CONSTANT (refined upstream by the mapper).
//   * one intrinsics mask for all groups (refine flags are global).
//   * +z convention throughout (COLMAP native); cheirality is Pz>0.
// =============================================================================
#pragma once

#include "oca_rig_support.cuh"  // prism-ba: shared helpers of mfree_release/oca_cuda.cu
#include "fisheye_grad17_generated.cuh"
#include "fisheye_grad17_atan2_generated.cuh"
#include "pinhole_grad17_generated.cuh"

namespace rigfisheye {

constexpr int RF_CD = 14;   // camera tangent width per image
constexpr int RF_NI = 8;    // intrinsics per calibration group
// Projection model of a calibration group. Bit 0 selects the pinhole +
// polynomial-radial chain (PinholeResidualGrad17; COLMAP SIMPLE_PINHOLE,
// PINHOLE, SIMPLE_RADIAL, RADIAL on the same 8-slot intrinsics vector, k3/k4
// unused) instead of OPENCV_FISHEYE; bit 1 ties fy to fx (the SIMPLE_* models
// have one focal length): the dfy column is folded into dfx and the retraction
// copies fx into fy, so the two never drift apart during the solve.
constexpr int RF_MODEL_FISHEYE = 0;
constexpr int RF_MODEL_PINHOLE = 1;
constexpr int RF_MODEL_TIED_FOCAL = 2;
__device__ __forceinline__ int RFModelOf(const int* calib_model, int calib) {
  return calib_model ? calib_model[calib] : RF_MODEL_FISHEYE;
}

struct RFDeviceProblem {
  int ncam = 0, nframes = 0, nsensors = 0, ncalib = 0, npt = 0, nobs = 0;
  int *cam_idx = nullptr, *pt_idx = nullptr;          // per obs
  int *frame_of_cam = nullptr, *sensor_of_cam = nullptr, *calib_of_cam = nullptr;
  // Reduced-space slot of each image's sensor block, or -1 when that sensor is
  // held constant (always -1 for rig reference sensors). Sized ncam.
  int *free_sensor_of_cam = nullptr;
  int *free_slot_of_sensor = nullptr;   // per sensor: reduced slot or -1
  int nfree_sensors = 0;
  Scalar *uv = nullptr;                               // raw pixels, 2 per obs
  // CSR + slot maps, built with the shared helpers (BuildPointObsCSR etc.).
  int *point_obs_offsets = nullptr, *point_obs_list = nullptr;
  int *obs2pslot = nullptr, *obs2cslot = nullptr;
  int *mf_scam = nullptr, *mf_spt = nullptr, *mf_coff = nullptr, *mf_cspt = nullptr;
  // Intrinsics column masks, RF_NI per calibration group (refine options AND
  // the per-model unused-parameter mask, e.g. k3/k4 of a pinhole camera).
  Scalar *imask = nullptr;
  // Projection model per calibration group (RF_MODEL_* bits). nullptr = all
  // OPENCV_FISHEYE, the original contract of this file.
  int *calib_model = nullptr;
  // Constant points (1 = held), or nullptr. Their point factor is zeroed after
  // every factorisation, which every V^-1 consumer already treats as "no
  // elimination": the point stays where it is and constrains the cameras
  // through Hcc and the gradient only.
  unsigned char *pt_const = nullptr;
};

__global__ void RFZeroConstPointFactor(Scalar* __restrict__ Rf,
                                       const unsigned char* __restrict__ cst,
                                       int npt) {
  int p = blockIdx.x * blockDim.x + threadIdx.x; if (p >= npt) return;
  if (!cst[p]) return;
  for (int i = 0; i < 6; ++i) Rf[6 * p + i] = 0.0;
}

struct RFDeviceState {
  Scalar *Rf = nullptr, *tf = nullptr;    // frames: 9,3 per frame
  Scalar *Rs = nullptr, *ts = nullptr;    // sensors: 9,3 per sensor (constant)
  Scalar *intr = nullptr;                 // 8 per calibration group
  Scalar *X = nullptr;                    // 3 per point
  Scalar *Rc = nullptr, *tc = nullptr;    // composed image poses: 9,3 per image
};

inline void RFAlloc(RFDeviceState& s, int nframes, int nsensors, int ncalib,
                    int ncam, int npt) {
  CUDA_CHECK(cudaMalloc(&s.Rf, 9ul * nframes * sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&s.tf, 3ul * nframes * sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&s.Rs, 9ul * nsensors * sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&s.ts, 3ul * nsensors * sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&s.intr, (size_t)RF_NI * ncalib * sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&s.X, 3ul * npt * sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&s.Rc, 9ul * ncam * sizeof(Scalar)));
  CUDA_CHECK(cudaMalloc(&s.tc, 3ul * ncam * sizeof(Scalar)));
}
inline void RFFree(RFDeviceState& s) {
  for (Scalar* q : {s.Rf, s.tf, s.Rs, s.ts, s.intr, s.X, s.Rc, s.tc})
    if (q) cudaFree(q);
  s = RFDeviceState{};
}
inline void RFCopy(const RFDeviceState& dst, const RFDeviceState& src,
                   int nframes, int nsensors, int ncalib, int ncam, int npt) {
  auto cp = [](Scalar* d, const Scalar* s_, size_t n) {
    CUDA_CHECK(cudaMemcpy(d, s_, n * sizeof(Scalar), cudaMemcpyDeviceToDevice));
  };
  cp(dst.Rf, src.Rf, 9ul * nframes); cp(dst.tf, src.tf, 3ul * nframes);
  cp(dst.Rs, src.Rs, 9ul * nsensors); cp(dst.ts, src.ts, 3ul * nsensors);
  cp(dst.intr, src.intr, (size_t)RF_NI * ncalib);
  cp(dst.X, src.X, 3ul * npt);
  cp(dst.Rc, src.Rc, 9ul * ncam); cp(dst.tc, src.tc, 3ul * ncam);
}

// cam_from_world = sensor_from_rig o rig_from_world, per image.
__global__ void RFCompose(const Scalar* __restrict__ Rf, const Scalar* __restrict__ tf,
                          const Scalar* __restrict__ Rs, const Scalar* __restrict__ ts,
                          const int* __restrict__ frame_of_cam,
                          const int* __restrict__ sensor_of_cam,
                          int ncam, Scalar* __restrict__ Rc, Scalar* __restrict__ tc) {
  int i = blockIdx.x * blockDim.x + threadIdx.x; if (i >= ncam) return;
  const Scalar* A = Rs + 9 * sensor_of_cam[i];   // S.R
  const Scalar* B = Rf + 9 * frame_of_cam[i];    // F.R
  const Scalar* bt = tf + 3 * frame_of_cam[i];
  const Scalar* at = ts + 3 * sensor_of_cam[i];
  Scalar* C = Rc + 9 * i;
  for (int r = 0; r < 3; ++r)
    for (int c = 0; c < 3; ++c)
      C[3 * r + c] = A[3 * r] * B[c] + A[3 * r + 1] * B[3 + c] + A[3 * r + 2] * B[6 + c];
  for (int r = 0; r < 3; ++r)
    tc[3 * i + r] = A[3 * r] * bt[0] + A[3 * r + 1] * bt[1] + A[3 * r + 2] * bt[2] + at[r];
}

// Observations at or past the projection singularity contribute NOTHING --
// neither residual nor gradient. Real fisheye masks keep everything under
// ~89 degrees, but a converged model holds rim observations arbitrarily close
// to theta=90, and one flipped observation's 1/Pz otherwise dominates the
// whole cost (measured: a 0.005-degree pose perturbation of an 11k-image
// model pushed the SUM to ~1e150). Ceres survives the same states through
// finite mirrored projections + robust loss; this path drops the observation
// instead, which matches what the physical mask says about such rays: they
// carry no scene information. RFActive is the single definition of validity,
// shared by cost, gradient, and the inactive-count diagnostic.
__device__ __forceinline__ bool RFActive(Scalar Pz, Scalar nu, Scalar nv) {
  // Pz floor: absolute, in scene units; theta cap ~89.4 deg (tan ~ 95).
  return (Pz > 1e-6) && (nu * nu + nv * nv < 9000.0);
}
// EXPERIMENT (OCA_RF_CLAMP=1, default off = bit-compat): an inactive
// observation costs its residual with theta held at the cap and its azimuth
// taken from (Px,Py) directly -- finite, continuous at the boundary, valid for
// Pz<0 too. It still carries no gradient (RFAssemble's inactive branch is
// unchanged). Motivation, measured on Fuchsberg ref300: with a zero-cost mask
// the solver is REWARDED for pushing rim observations out of the domain, and
// with the early stop disabled it drives all 1.69M observations inactive and
// reports cost 0.
__constant__ int g_rf_clamp = 0;
constexpr Scalar RF_THETA_CAP = 1.5602564;   // atan(sqrt(9000))
// DEFAULT since 2026-09-19 (OCA_RF_ATAN2=0 restores the 1/Pz path): incidence-
// angle formulation theta = atan2(rho, Pz) (fisheye_grad17_atan2_generated.cuh).
// No 1/Pz anywhere, so the residual and its gradient are finite and smooth
// through the camera plane; the only guards left are the camera centre
// (|P| ~ 0, direction undefined) and a cap theta < g_rf_theta_max
// (OCA_RF_THETA_MAX_DEG, default 90 = exactly Ceres' Pz > 0 domain; the
// physical alternative is the lens FOV, ~100 deg for a 200 deg fisheye).
// Motivation, measured on Fuchsberg ref300: the 89.4 deg mask turns the
// objective into a step function for the ~18k observations per degree
// sitting on the rim, and LM accept/reject becomes noise-driven long before
// Ceres' cost is reached. On the full 5592-frame sequence the atan2 domain
// takes the deviation from the Ceres map from 1.31 % to 0.92 % of the extent
// at identical wall time, and the intrinsics land on Ceres' to the 4th digit.
__constant__ int g_rf_atan2 = 1;
__constant__ Scalar g_rf_theta_max = 1.5707963267948966;
// Activity from the camera-frame point: the one rule shared by cost, gradient
// and the inactive-count diagnostic (RFActive semantics when the smooth
// variant is off).
__device__ __forceinline__ bool RFActiveP(int model, Scalar Px, Scalar Py, Scalar Pz) {
  // Pinhole: every point in front of the camera is active. Points behind it
  // are not masked to zero cost (that would reward a step for pushing them
  // there, the 90-degree cliff of the fisheye branch); RFResidual poisons the
  // cost instead, so such a candidate is rejected like a non-finite one.
  if (model & RF_MODEL_PINHOLE) return Pz > 0.0;
  if (g_rf_atan2) {
    const Scalar rho2 = Px * Px + Py * Py;
    if (!(rho2 + Pz * Pz > 1e-24)) return false;
    return atan2(sqrt(rho2), Pz) < g_rf_theta_max;
  }
  return RFActive(Pz, Px / Pz, Py / Pz);
}
__device__ __forceinline__ bool RFResidual(
    const Scalar* Rc, const Scalar* tc, const Scalar* Xp, const Scalar* in, int model,
    Scalar u, Scalar v, Scalar* rx, Scalar* ry) {
  Scalar Px = Rc[0]*Xp[0] + Rc[1]*Xp[1] + Rc[2]*Xp[2] + tc[0];
  Scalar Py = Rc[3]*Xp[0] + Rc[4]*Xp[1] + Rc[5]*Xp[2] + tc[1];
  Scalar Pz = Rc[6]*Xp[0] + Rc[7]*Xp[1] + Rc[8]*Xp[2] + tc[2];
  // A non-finite camera-frame point (point or pose overflowed in a candidate
  // step) fails every activity test below and would be scored as a free,
  // zero-cost observation -- a candidate that sends points to inf/NaN then
  // wins by the residuals it deleted. Measured on Fuchsberg ref300 with the
  // tau ratchet run past 1e298: 540 well-conditioned points went NaN in one
  // accepted step and the reported cost dropped by their 6172 residuals.
  // Poison the cost instead: the candidate is rejected, no gradient is built.
  if (!(isfinite(Px) && isfinite(Py) && isfinite(Pz))) {
    *rx = INFINITY; *ry = 0.0; return false;
  }
  if (model & RF_MODEL_PINHOLE) {
    // Same arithmetic as PinholeResidualGrad17's residual.
    if (!(Pz > 0.0)) { *rx = INFINITY; *ry = 0.0; return false; }
    const Scalar x = Px / Pz, y = Py / Pz, r2 = x * x + y * y;
    const Scalar d = 1.0 + r2 * (in[4] + r2 * in[5]);
    *rx = in[0] * d * x + in[2] - u;
    *ry = in[1] * d * y + in[3] - v;
    return true;
  }
  if (g_rf_atan2) {
    // Same arithmetic as FisheyeResidualGrad17A's residual, so the cost the
    // LM step is judged on is the one the linearisation was built from.
    if (!RFActiveP(model, Px, Py, Pz)) { *rx = 0.0; *ry = 0.0; return false; }
    const Scalar rho = sqrt(Px * Px + Py * Py + 1e-32);
    const Scalar th = atan2(rho, Pz), s = th / rho, th2 = th * th;
    const Scalar d = 1.0 + th2 * (in[4] + th2 * (in[5] + th2 * (in[6] + th2 * in[7])));
    *rx = in[0] * d * s * Px + in[2] - u;
    *ry = in[1] * d * s * Py + in[3] - v;
    return true;
  }
  Scalar nu = Px / Pz, nv = Py / Pz;
  if (!RFActive(Pz, nu, nv)) {
    if (!g_rf_clamp) { *rx = 0.0; *ry = 0.0; return false; }
    const Scalar rho = sqrt(Px * Px + Py * Py);
    if (!(rho > 1e-30)) { *rx = in[2] - u; *ry = in[3] - v; return false; }
    const Scalar th = RF_THETA_CAP, th2 = th * th;
    const Scalar d = 1.0 + th2 * (in[4] + th2 * (in[5] + th2 * (in[6] + th2 * in[7])));
    *rx = in[0] * d * th * (Px / rho) + in[2] - u;
    *ry = in[1] * d * th * (Py / rho) + in[3] - v;
    return false;
  }
  Scalar r = sqrt(nu * nu + nv * nv + 1e-32);
  Scalar th = atan(r), s = th / r, th2 = th * th;
  Scalar d = 1.0 + th2 * (in[4] + th2 * (in[5] + th2 * (in[6] + th2 * in[7])));
  *rx = in[0] * d * s * nu + in[2] - u;
  *ry = in[1] * d * s * nv + in[3] - v;
  return true;
}

__global__ void RFCostKernel(const int* __restrict__ ci, const int* __restrict__ pi,
                             const Scalar* __restrict__ uv,
                             const Scalar* __restrict__ Rc, const Scalar* __restrict__ tc,
                             const Scalar* __restrict__ X,
                             const Scalar* __restrict__ intr,
                             const int* __restrict__ calib_of_cam,
                             const int* __restrict__ calib_model,
                             int nobs, Scalar* __restrict__ cost,
                             int rk = 0, Scalar rk_a2 = 0.0) {
  int o = blockIdx.x * blockDim.x + threadIdx.x; if (o >= nobs) return;
  int c = ci[o];
  Scalar rx, ry;
  // Inactive (far-field / behind-camera) observations return rx=ry=0 here, so
  // they contribute 0 under L2 and rho(0)=0 under every robust kernel too --
  // the mask semantics survive the reweighting untouched.
  RFResidual(Rc + 9 * c, tc + 3 * c, X + 3 * pi[o],
             intr + RF_NI * calib_of_cam[c], RFModelOf(calib_model, calib_of_cam[c]),
             uv[2 * o], uv[2 * o + 1], &rx, &ry);
  const Scalar ss = rx * rx + ry * ry;
  atomicAdd(cost, 0.5 * (rk ? OcaRho(rk, rk_a2, ss) : ss));
}
// Block-reduced variant (see KernelCostBlk in oca_cuda.cu): one partial per
// block, summed in fixed order by KernelCostFinal. The single-address atomic
// above costs ~1.6 ms per million observations per evaluation on Ada.
__global__ void RFCostKernelBlk(const int* __restrict__ ci, const int* __restrict__ pi,
                                const Scalar* __restrict__ uv,
                                const Scalar* __restrict__ Rc, const Scalar* __restrict__ tc,
                                const Scalar* __restrict__ X,
                                const Scalar* __restrict__ intr,
                                const int* __restrict__ calib_of_cam,
                                const int* __restrict__ calib_model,
                                int nobs, Scalar* __restrict__ part,
                                int rk, Scalar rk_a2) {
  __shared__ Scalar sh[256];
  int o = blockIdx.x * blockDim.x + threadIdx.x;
  Scalar val = 0.0;
  if (o < nobs) {
    int c = ci[o];
    Scalar rx, ry;
    RFResidual(Rc + 9 * c, tc + 3 * c, X + 3 * pi[o],
               intr + RF_NI * calib_of_cam[c], RFModelOf(calib_model, calib_of_cam[c]),
               uv[2 * o], uv[2 * o + 1], &rx, &ry);
    const Scalar ss = rx * rx + ry * ry;
    val = 0.5 * (rk ? OcaRho(rk, rk_a2, ss) : ss);
  }
  sh[threadIdx.x] = val; __syncthreads();
  for (int st = 128; st > 0; st >>= 1) { if (threadIdx.x < st) sh[threadIdx.x] += sh[threadIdx.x + st]; __syncthreads(); }
  if (threadIdx.x == 0) part[blockIdx.x] = sh[0];
}

// Per-observation |r|^2 for the student-t EM scale, reusing RFResidual so the
// scale is never estimated from a re-derived projection. INACTIVE
// observations are marked -1, not 0: they carry no scene information, and
// folding them in as zeros would drag sigma toward 0 and turn the kernel into
// a hard outlier filter (on gba_164 that is 27k of 4.6M observations).
__global__ void RFResidSqKernel(const int* __restrict__ ci, const int* __restrict__ pi,
                                const Scalar* __restrict__ uv,
                                const Scalar* __restrict__ Rc, const Scalar* __restrict__ tc,
                                const Scalar* __restrict__ X,
                                const Scalar* __restrict__ intr,
                                const int* __restrict__ calib_of_cam,
                                const int* __restrict__ calib_model,
                                int nobs, Scalar* __restrict__ s_out) {
  int o = blockIdx.x * blockDim.x + threadIdx.x; if (o >= nobs) return;
  int c = ci[o];
  Scalar rx, ry;
  const bool act = RFResidual(Rc + 9 * c, tc + 3 * c, X + 3 * pi[o],
                              intr + RF_NI * calib_of_cam[c],
                              RFModelOf(calib_model, calib_of_cam[c]),
                              uv[2 * o], uv[2 * o + 1], &rx, &ry);
  s_out[o] = act ? (rx * rx + ry * ry) : (Scalar)(-1.0);
}

// One EM M-step over the ACTIVE observations: acc[0] += u_i s_i, acc[1] += 1.
__global__ void RFTEMSum(const Scalar* __restrict__ sv, int nobs, Scalar nu,
                         Scalar sig2, Scalar* __restrict__ acc) {
  int o = blockIdx.x * blockDim.x + threadIdx.x; if (o >= nobs) return;
  const Scalar si = sv[o];
  if (si < 0.0) return;                       // inactive: excluded from the fit
  const Scalar u = (nu + 2.0)/(nu + si/sig2);
  atomicAdd(&acc[0], u*si);
  atomicAdd(&acc[1], (Scalar)1.0);
}

__global__ void RFCheirKernel(const int* __restrict__ ci, const int* __restrict__ pi,
                              const Scalar* __restrict__ Rc, const Scalar* __restrict__ tc,
                              const Scalar* __restrict__ X,
                              const int* __restrict__ calib_of_cam,
                              const int* __restrict__ calib_model, int nobs,
                              int* __restrict__ nviol) {
  int o = blockIdx.x * blockDim.x + threadIdx.x; if (o >= nobs) return;
  int c = ci[o]; const Scalar* R = Rc + 9 * c; const Scalar* Xp = X + 3 * pi[o];
  Scalar Px = R[0]*Xp[0] + R[1]*Xp[1] + R[2]*Xp[2] + tc[3 * c];
  Scalar Py = R[3]*Xp[0] + R[4]*Xp[1] + R[5]*Xp[2] + tc[3 * c + 1];
  Scalar Pz = R[6]*Xp[0] + R[7]*Xp[1] + R[8]*Xp[2] + tc[3 * c + 2];
  if (!RFActiveP(RFModelOf(calib_model, calib_of_cam[c]), Px, Py, Pz)) atomicAdd(nviol, 1);
}

// Fragment assembly: identical storage contract to MFAssemble<14,HT> so the
// generic MFPass1/2 / MFRhsPrime / MFDiagK / MFPointFactor consume it as-is.
template <class HT>
__global__ void RFAssemble(const int* __restrict__ ci, const int* __restrict__ pi,
    const Scalar* __restrict__ uv,
    const Scalar* __restrict__ Rc, const Scalar* __restrict__ tc,
    const Scalar* __restrict__ X,
    const Scalar* __restrict__ intr, const int* __restrict__ calib_of_cam,
    const int* __restrict__ calib_model,
    const Scalar* __restrict__ imask,
    const int* __restrict__ o2p, const int* __restrict__ o2c, int nobs,
    Scalar* __restrict__ Hcc, Scalar* __restrict__ Cdiag,
    HT* __restrict__ Gp, HT* __restrict__ Gc, HT* __restrict__ Bo,
    Scalar* __restrict__ bc, Scalar* __restrict__ bp,
    int rk = 0, Scalar rk_a2 = 0.0) {
  constexpr int CD = RF_CD;
  int o = blockIdx.x * blockDim.x + threadIdx.x; if (o >= nobs) return;
  int c = ci[o], p = pi[o];
  const Scalar* R = Rc + 9 * c; const Scalar* Xp = X + 3 * p;
  const int calib = calib_of_cam[c];
  const Scalar* in = intr + RF_NI * calib;
  const int model = RFModelOf(calib_model, calib);
  const Scalar* im = imask + RF_NI * calib;
  Scalar gx[CD + 3], gy[CD + 3], rx, ry;
  {
    Scalar Pz = R[6]*Xp[0] + R[7]*Xp[1] + R[8]*Xp[2] + tc[3*c+2];
    Scalar Px = R[0]*Xp[0] + R[1]*Xp[1] + R[2]*Xp[2] + tc[3*c];
    Scalar Py = R[3]*Xp[0] + R[4]*Xp[1] + R[5]*Xp[2] + tc[3*c+1];
    if (!RFActiveP(model, Px, Py, Pz)) {
      // Zero fragments: the slots must still be written (they are dense).
      int kp0 = o2p[o], kc0 = o2c[o];
      for (int i = 0; i < CD; ++i)
        for (int j = 0; j < 3; ++j) {
          Gp[(size_t)(3*i+j)*nobs + kp0] = (HT)0;
          Gc[(size_t)(3*i+j)*nobs + kc0] = (HT)0;
        }
      for (int j = 0; j < 6; ++j) Bo[6*o+j] = (HT)0;
      return;
    }
  }
  if (model & RF_MODEL_PINHOLE)
    PinholeResidualGrad17(R[0],R[1],R[2],R[3],R[4],R[5],R[6],R[7],R[8],
        tc[3*c],tc[3*c+1],tc[3*c+2],Xp[0],Xp[1],Xp[2],
        in[0],in[1],in[2],in[3],in[4],in[5],in[6],in[7],
        uv[2*o],uv[2*o+1],gx,gy,&rx,&ry);
  else if (g_rf_atan2)
    FisheyeResidualGrad17A(R[0],R[1],R[2],R[3],R[4],R[5],R[6],R[7],R[8],
        tc[3*c],tc[3*c+1],tc[3*c+2],Xp[0],Xp[1],Xp[2],
        in[0],in[1],in[2],in[3],in[4],in[5],in[6],in[7],
        uv[2*o],uv[2*o+1],gx,gy,&rx,&ry);
  else
    FisheyeResidualGrad17(R[0],R[1],R[2],R[3],R[4],R[5],R[6],R[7],R[8],
        tc[3*c],tc[3*c+1],tc[3*c+2],Xp[0],Xp[1],Xp[2],
        in[0],in[1],in[2],in[3],in[4],in[5],in[6],in[7],
        uv[2*o],uv[2*o+1],gx,gy,&rx,&ry);
  if (model & RF_MODEL_TIED_FOCAL) { gx[6] += gx[7]; gy[6] += gy[7]; gx[7] = 0.0; gy[7] = 0.0; }
  for (int j = 0; j < RF_NI; ++j) { gx[6 + j] *= im[j]; gy[6 + j] *= im[j]; }
  // IRLS: sqrt-weight the residual AND the Jacobian rows (same contract as the
  // CD=9 path). Only reached for ACTIVE observations -- the inactive branch
  // above already returned with zeroed fragments.
  if (rk) {
    const Scalar sw = sqrt(OcaRobustW(rk, rk_a2, rx*rx + ry*ry));
    rx *= sw; ry *= sw;
    for (int i = 0; i < CD + 3; ++i) { gx[i] *= sw; gy[i] *= sw; }
  }
  for (int i = 0; i < CD; ++i) atomicAdd(&bc[CD*c+i], rx*gx[i] + ry*gy[i]);
  for (int i = 0; i < 3; ++i)  atomicAdd(&bp[3*p+i], rx*gx[CD+i] + ry*gy[CD+i]);
  for (int i = 0; i < CD; ++i)
    for (int j = 0; j < CD; ++j)
      atomicAdd(&Hcc[(size_t)CD*CD*c + CD*i + j], gx[i]*gx[j] + gy[i]*gy[j]);
  for (int i = 0; i < 3; ++i)
    atomicAdd(&Cdiag[3*p+i], gx[CD+i]*gx[CD+i] + gy[CD+i]*gy[CD+i]);
  int kp = o2p[o], kc = o2c[o];
  for (int i = 0; i < CD; ++i)
    for (int j = 0; j < 3; ++j) {
      Scalar g = gx[i]*gx[CD+j] + gy[i]*gy[CD+j];
      Gp[(size_t)(3*i+j)*nobs + kp] = (HT)g;
      Gc[(size_t)(3*i+j)*nobs + kc] = (HT)g;
    }
  for (int j = 0; j < 3; ++j) { Bo[6*o+j] = (HT)gx[CD+j]; Bo[6*o+3+j] = (HT)gy[CD+j]; }
}

// B: reduced [6*nframes | 8*ncalib] -> full [14 per image].
// Sensor tangent -> image tangent, first order: dw_cam = ew,
// dt_cam = et - [v]x ew with v = t_cam - t_sensor (the rotated frame
// translation). v varies per image, so these blocks are computed on the fly
// from the composed state rather than stored.
__global__ void RFBroadcast(const Scalar* __restrict__ vr,
                            const Scalar* __restrict__ Rs,
                            const Scalar* __restrict__ ts,
                            const Scalar* __restrict__ tc,
                            const int* __restrict__ frame_of_cam,
                            const int* __restrict__ sensor_of_cam,
                            const int* __restrict__ free_sensor_of_cam,
                            const int* __restrict__ calib_of_cam,
                            int ncam, int nframes, int nfree,
                            Scalar* __restrict__ vf) {
  int i = blockIdx.x * blockDim.x + threadIdx.x; if (i >= ncam) return;
  const Scalar* A = Rs + 9 * sensor_of_cam[i];
  const Scalar* w = vr + 6 * frame_of_cam[i];
  Scalar* out = vf + RF_CD * i;
  for (int r = 0; r < 3; ++r) {
    out[r]     = A[3*r]*w[0] + A[3*r+1]*w[1] + A[3*r+2]*w[2];
    out[3 + r] = A[3*r]*w[3] + A[3*r+1]*w[4] + A[3*r+2]*w[5];
  }
  const int fs = free_sensor_of_cam[i];
  if (fs >= 0) {
    const Scalar* e = vr + 6 * nframes + 6 * fs;
    Scalar v0 = tc[3*i]   - ts[3*sensor_of_cam[i]];
    Scalar v1 = tc[3*i+1] - ts[3*sensor_of_cam[i]+1];
    Scalar v2 = tc[3*i+2] - ts[3*sensor_of_cam[i]+2];
    out[0] += e[0]; out[1] += e[1]; out[2] += e[2];
    // dt += et - v x ew
    out[3] += e[3] - (v1*e[2] - v2*e[1]);
    out[4] += e[4] - (v2*e[0] - v0*e[2]);
    out[5] += e[5] - (v0*e[1] - v1*e[0]);
  }
  const Scalar* g = vr + 6 * nframes + 6 * nfree + RF_NI * calib_of_cam[i];
  for (int j = 0; j < RF_NI; ++j) out[6 + j] = g[j];
}

// B^T: full -> reduced. Caller zeroes vr first (entries accumulate).
__global__ void RFReduce(const Scalar* __restrict__ vf,
                         const Scalar* __restrict__ Rs,
                         const Scalar* __restrict__ ts,
                         const Scalar* __restrict__ tc,
                         const int* __restrict__ frame_of_cam,
                         const int* __restrict__ sensor_of_cam,
                         const int* __restrict__ free_sensor_of_cam,
                         const int* __restrict__ calib_of_cam,
                         int ncam, int nframes, int nfree,
                         Scalar* __restrict__ vr) {
  int i = blockIdx.x * blockDim.x + threadIdx.x; if (i >= ncam) return;
  const Scalar* A = Rs + 9 * sensor_of_cam[i];
  const Scalar* in = vf + RF_CD * i;
  Scalar* w = vr + 6 * frame_of_cam[i];
  for (int r = 0; r < 3; ++r) {   // A^T in
    atomicAdd(&w[r],     A[r]*in[0] + A[3+r]*in[1] + A[6+r]*in[2]);
    atomicAdd(&w[3 + r], A[r]*in[3] + A[3+r]*in[4] + A[6+r]*in[5]);
  }
  const int fs = free_sensor_of_cam[i];
  if (fs >= 0) {
    Scalar* e = vr + 6 * nframes + 6 * fs;
    Scalar v0 = tc[3*i]   - ts[3*sensor_of_cam[i]];
    Scalar v1 = tc[3*i+1] - ts[3*sensor_of_cam[i]+1];
    Scalar v2 = tc[3*i+2] - ts[3*sensor_of_cam[i]+2];
    // B^T: ew row picks up dw + [v]x^T dt = dw + v x dt... ( -[v]x )^T = [v]x
    atomicAdd(&e[0], in[0] + (v1*in[5] - v2*in[4]));
    atomicAdd(&e[1], in[1] + (v2*in[3] - v0*in[5]));
    atomicAdd(&e[2], in[2] + (v0*in[4] - v1*in[3]));
    atomicAdd(&e[3], in[3]);
    atomicAdd(&e[4], in[4]);
    atomicAdd(&e[5], in[5]);
  }
  Scalar* g = vr + 6 * nframes + 6 * nfree + RF_NI * calib_of_cam[i];
  for (int j = 0; j < RF_NI; ++j) atomicAdd(&g[j], in[6 + j]);
}

// diag(B^T D B) for the preconditioner: pose entries need SQUARED rotation
// weights ((B^T D B)_kk = sum_m Rs[m][k]^2 D_m), intrinsics entries plain sums.
// A plain transpose-reduce of the diagonal would be wrong for the pose part.
__global__ void RFReduceDiag(const Scalar* __restrict__ df,
                             const Scalar* __restrict__ Rs,
                             const Scalar* __restrict__ ts,
                             const Scalar* __restrict__ tc,
                             const int* __restrict__ frame_of_cam,
                             const int* __restrict__ sensor_of_cam,
                             const int* __restrict__ free_sensor_of_cam,
                             const int* __restrict__ calib_of_cam,
                             int ncam, int nframes, int nfree,
                             Scalar* __restrict__ dr) {
  int i = blockIdx.x * blockDim.x + threadIdx.x; if (i >= ncam) return;
  const Scalar* A = Rs + 9 * sensor_of_cam[i];
  const Scalar* in = df + RF_CD * i;
  Scalar* w = dr + 6 * frame_of_cam[i];
  for (int k = 0; k < 3; ++k) {
    Scalar sw = A[k]*A[k]*in[0] + A[3+k]*A[3+k]*in[1] + A[6+k]*A[6+k]*in[2];
    Scalar st = A[k]*A[k]*in[3] + A[3+k]*A[3+k]*in[4] + A[6+k]*A[6+k]*in[5];
    atomicAdd(&w[k], sw); atomicAdd(&w[3 + k], st);
  }
  const int fs = free_sensor_of_cam[i];
  if (fs >= 0) {
    Scalar* e = dr + 6 * nframes + 6 * fs;
    Scalar v0 = tc[3*i]   - ts[3*sensor_of_cam[i]];
    Scalar v1 = tc[3*i+1] - ts[3*sensor_of_cam[i]+1];
    Scalar v2 = tc[3*i+2] - ts[3*sensor_of_cam[i]+2];
    // Column ew_k of B: 1 in dw_k plus the two skew entries in dt.
    atomicAdd(&e[0], in[0] + v2*v2*in[4] + v1*v1*in[5]);
    atomicAdd(&e[1], in[1] + v2*v2*in[3] + v0*v0*in[5]);
    atomicAdd(&e[2], in[2] + v1*v1*in[3] + v0*v0*in[4]);
    atomicAdd(&e[3], in[3]);
    atomicAdd(&e[4], in[4]);
    atomicAdd(&e[5], in[5]);
  }
  Scalar* g = dr + 6 * nframes + 6 * nfree + RF_NI * calib_of_cam[i];
  for (int j = 0; j < RF_NI; ++j) atomicAdd(&g[j], in[6 + j]);
}

// Retraction from the REDUCED delta (already negated): frames get
// R <- exp(dw) R, t <- t + dt; intrinsics groups add their 8 deltas.
__global__ void RFRetractFrames(const Scalar* __restrict__ Rf_old,
                                const Scalar* __restrict__ tf_old,
                                const Scalar* __restrict__ d, int nframes,
                                Scalar* __restrict__ Rf_new, Scalar* __restrict__ tf_new) {
  int fidx = blockIdx.x * blockDim.x + threadIdx.x; if (fidx >= nframes) return;
  const Scalar* dw = d + 6 * fidx;
  Scalar dR[9]; ExpSO3(dw, dR);
  const Scalar* R0 = Rf_old + 9 * fidx; Scalar* R1 = Rf_new + 9 * fidx;
  for (int r = 0; r < 3; ++r)
    for (int c = 0; c < 3; ++c)
      R1[3*r+c] = dR[3*r]*R0[c] + dR[3*r+1]*R0[3+c] + dR[3*r+2]*R0[6+c];
  for (int r = 0; r < 3; ++r) tf_new[3*fidx+r] = tf_old[3*fidx+r] + dw[3 + r];
}
// Gauge fix: zero one frame's 6 tangent components so the retraction leaves it
// exactly where it started. Applied to the reduced delta at the single choke
// point every candidate step passes through, so no step -- accepted, rejected,
// or alpha-scaled -- can move the gauge frame. Ceres fixes the gauge with
// TWO_CAMS_FROM_WORLD and Caspar with FixGaugeWithOneFrameFromWorld (one frame,
// scale left free); this matches Caspar's choice. Measured motivation: without
// it MFREE rotates the whole model 0.33 deg/call vs gauge-fixed Ceres's 0.064.
__global__ void RFPinGaugeFrame(Scalar* __restrict__ d, int gauge_frame) {
  int k = blockIdx.x * blockDim.x + threadIdx.x; if (k >= 6) return;
  d[6 * gauge_frame + k] = (Scalar)0;
}
// Pinning one frame fixes six of the seven gauge degrees of freedom. Scale is
// the seventh and it is NOT fixed: scaling the world about the pinned frame's
// centre leaves every ray -- and therefore every residual -- unchanged.
//
// That freedom is not harmless during incremental mapping. Measured on
// Fuchsberg (5592 rig frames, OPENCV_FISHEYE), consecutive mapper snapshots
// differed by scale factors of 0.519, 0.761, 0.833 and 0.913 while agreeing on
// shape to 0.04-0.08% of scene extent -- the map was not deforming between
// checkpoints, it was being rescaled. The drift is worst while the map is small
// and damps out as constraints accumulate (camera-centre extent fell 12.78 ->
// 10.63 by frame 1252, then recovered to 13.53 by the end), so it does not run
// away; what it costs is structure. Over the full sequence the unpinned run
// finished 18.1% short of the reference on 3D points and 25.3% of extent from it
// in shape, against 5.5% and 19.5% with this pin, and took 5h46m against 3h40m.
// Cost never shows any of it, because reprojection error is scale-invariant.
//
// A zero-baseline rig cannot supply the missing constraint either -- a
// back-to-back dual fisheye has both sensors at one centre -- so the seventh DOF
// has to be pinned explicitly. Zeroing one translation component of a second,
// well-separated frame does it: that frame may still rotate and slide in the
// other two axes, but it can no longer move along `axis` relative to the pinned
// frame, which fixes the distance between them and hence scale.
__global__ void RFPinGaugeScale(Scalar* __restrict__ d, int scale_frame,
                                int axis) {
  if (blockIdx.x * blockDim.x + threadIdx.x != 0) return;
  d[6 * scale_frame + 3 + axis] = (Scalar)0;
}
// Sensors: identity update for held sensors, exp(e) o S for free ones.
__global__ void RFRetractSensors(const Scalar* __restrict__ Rs_old,
                                 const Scalar* __restrict__ ts_old,
                                 const Scalar* __restrict__ d,
                                 const int* __restrict__ free_slot_of_sensor,
                                 int nsensors, int nframes,
                                 Scalar* __restrict__ Rs_new,
                                 Scalar* __restrict__ ts_new) {
  int sidx = blockIdx.x * blockDim.x + threadIdx.x; if (sidx >= nsensors) return;
  const Scalar* R0 = Rs_old + 9 * sidx; Scalar* R1 = Rs_new + 9 * sidx;
  const int fs = free_slot_of_sensor[sidx];
  if (fs < 0) {
    for (int j = 0; j < 9; ++j) R1[j] = R0[j];
    for (int j = 0; j < 3; ++j) ts_new[3*sidx+j] = ts_old[3*sidx+j];
    return;
  }
  const Scalar* e = d + 6 * nframes + 6 * fs;
  Scalar dR[9]; ExpSO3(e, dR);
  for (int r = 0; r < 3; ++r)
    for (int c = 0; c < 3; ++c)
      R1[3*r+c] = dR[3*r]*R0[c] + dR[3*r+1]*R0[3+c] + dR[3*r+2]*R0[6+c];
  for (int r = 0; r < 3; ++r) ts_new[3*sidx+r] = ts_old[3*sidx+r] + e[3 + r];
}

__global__ void RFRetractIntr(const Scalar* __restrict__ intr_old,
                              const Scalar* __restrict__ d, int nframes, int nfree,
                              int ncalib, const int* __restrict__ calib_model,
                              Scalar* __restrict__ intr_new) {
  int i = blockIdx.x * blockDim.x + threadIdx.x; if (i >= RF_NI * ncalib) return;
  // Tied focal length: fy follows fx (its own delta is 0 by the folded column).
  if (i % RF_NI == 1 && (RFModelOf(calib_model, i / RF_NI) & RF_MODEL_TIED_FOCAL)) {
    intr_new[i] = intr_old[i - 1] + d[6 * nframes + 6 * nfree + i - 1];
    return;
  }
  intr_new[i] = intr_old[i] + d[6 * nframes + 6 * nfree + i];
}
__global__ void RFRetractPoints(const Scalar* __restrict__ X_old,
                                const Scalar* __restrict__ d, int npt,
                                Scalar* __restrict__ X_new) {
  int i = blockIdx.x * blockDim.x + threadIdx.x; if (i >= 3 * npt) return;
  X_new[i] = X_old[i] + d[i];
}

inline Scalar RFComputeCost(const RFDeviceProblem& p, const RFDeviceState& s,
                            Scalar* dcost, int rk = 0, Scalar rk_a2 = 0.0) {
  // AUDIT 2026-09-14 (C3 polarity / C2 device-keying) -- see ComputeCost in
  // oca_cuda.cu for the full rationale; this is the same cache, same two bugs.
  static const bool legacy_atomic = [](){const char* e=getenv("OCA_COST_ATOMIC"); return e?atoi(e)!=0:false;}();
  if (!legacy_atomic) {
    MFCostScratch& sc = MFCostScratchForCurrentDevice();
    const int nb = GridSize(p.nobs);
    sc.ensure(nb);
    RFCostKernelBlk<<<nb, 256>>>(p.cam_idx, p.pt_idx, p.uv, s.Rc, s.tc,
                                 s.X, s.intr, p.calib_of_cam, p.calib_model, p.nobs, sc.part, rk, rk_a2);
    KernelCostFinal<<<1, 256>>>(sc.part, nb, dcost);
    Scalar h; CUDA_CHECK(cudaMemcpy(&h, dcost, sizeof(Scalar), cudaMemcpyDeviceToHost));
    return h;
  }
  CUDA_CHECK(cudaMemset(dcost, 0, sizeof(Scalar)));
  RFCostKernel<<<GridSize(p.nobs), 256>>>(p.cam_idx, p.pt_idx, p.uv, s.Rc, s.tc,
                                          s.X, s.intr, p.calib_of_cam, p.calib_model, p.nobs, dcost,
                                          rk, rk_a2);
  Scalar h; CUDA_CHECK(cudaMemcpy(&h, dcost, sizeof(Scalar), cudaMemcpyDeviceToHost));
  return h;
}

inline int RFCheirality(const RFDeviceProblem& p, const RFDeviceState& s, int* dviol) {
  CUDA_CHECK(cudaMemset(dviol, 0, sizeof(int)));
  RFCheirKernel<<<GridSize(p.nobs), 256>>>(p.cam_idx, p.pt_idx, s.Rc, s.tc, s.X,
                                           p.calib_of_cam, p.calib_model, p.nobs, dviol);
  int h; CUDA_CHECK(cudaMemcpy(&h, dviol, sizeof(int), cudaMemcpyDeviceToHost));
  return h;
}

// -----------------------------------------------------------------------------
// Host solve loop. Clone of SolveMFreeShiftedCG's LM policy (inner retries,
// tau ratchet with warm ladder, lambda unwind, Eisenstat-Walker, Steihaug
// truncation, checkpoint scoring, alpha grid, early stopping) with the rig
// broadcast/reduce always on and the fisheye kernels substituted. Divergences
// from the champion path are marked "RF:".
// -----------------------------------------------------------------------------
inline RunLog SolveRigFisheye(const RFDeviceProblem& p, RFDeviceState& s,
                              Scalar lam0, int max_iter, bool verbose,
                              Scalar tau_pt, std::vector<int> ckpts, int n_shifts,
                              bool use_equil, Scalar ew_eta_max, bool use_alpha,
                              bool mf_fp32,
                              int max_inner_retry, Scalar func_tolerance,
                              int max_consecutive_failures,
                              int gauge_frame = -1,
                              // Seventh gauge DOF: see RFPinGaugeScale. -1
                              // leaves scale free (the historical behaviour).
                              int gauge_scale_frame = -1,
                              int gauge_scale_axis = 0,
                              Scalar* final_lambda_out = nullptr,
                              // IRLS robust kernel: 0 = L2 (bit-compat default).
                              int rk = 0, Scalar rk_scale2 = 0.0,
                              Scalar rk_nu = 4.0,
                              // Reduced-space column mask (1 = free, 0 = held
                              // constant), sized 6*nframes+6*nfree+8*ncalib, or
                              // nullptr / empty for all free. Built by the host
                              // wrapper from the problem's constancy flags.
                              const std::vector<Scalar>* col_mask = nullptr) {
  constexpr int CD = RF_CD;
  const int ncam = p.ncam, npt = p.npt, nobs = p.nobs;
  const int nframes = p.nframes, ncalib = p.ncalib;
  const int n_p = 3 * npt;
  const int n_cf = CD * ncam;                       // full camera space
  const int nfree = p.nfree_sensors;
  const int n_c = 6 * nframes + 6 * nfree + RF_NI * ncalib;  // reduced space
  const int n_red = n_c + n_p;                      // RF: d_best lives here

  Scalar *Hcc,*Cdiag,*Gp=nullptr,*Gc=nullptr,*Bo=nullptr,*bc,*bp,*Rfac,*tacc,*uu,*w,*bprime,*corr,*E,*dk;
  float *Gp32=nullptr,*Gc32=nullptr,*Bo32=nullptr;
  Scalar *xc_un,*xr_un,*xpv,*dred,*d_best,*r_,*pv_,*Ap_,*bcast_in,*bcast_out,*dcost;
  int *okf,*dviol;
  // C7 (see MFDeviceScratch in oca_cuda.cu): same raw-allocate/free-at-the-tail
  // shape as SolveMFreeShiftedCG, same leak on a thrown CUDA_CHECK. Declared
  // before the guard so both outlive it. s_new was previously never released on
  // the success path either -- RFFree(s_new) was reached only if nothing threw.
  RFDeviceState s_new;
  cublasHandle_t blas=nullptr;
  MFDeviceScratch scratch;
  scratch.defer([&]{ RFFree(s_new); });
  scratch.defer([&]{ if(blas) cublasDestroy(blas); });
  auto M=[&](void**q,size_t b){scratch.alloc(q,b);};
  M((void**)&Hcc,(size_t)CD*CD*ncam*sizeof(Scalar)); M((void**)&Cdiag,3ul*npt*sizeof(Scalar));
  if(mf_fp32){ M((void**)&Gp32,(size_t)3*CD*nobs*sizeof(float)); M((void**)&Gc32,(size_t)3*CD*nobs*sizeof(float));
               M((void**)&Bo32,6ul*nobs*sizeof(float)); }
  else       { M((void**)&Gp,(size_t)3*CD*nobs*sizeof(Scalar)); M((void**)&Gc,(size_t)3*CD*nobs*sizeof(Scalar));
               M((void**)&Bo,6ul*nobs*sizeof(Scalar)); }
  M((void**)&bc,(size_t)n_cf*sizeof(Scalar)); M((void**)&bp,(size_t)n_p*sizeof(Scalar));
  M((void**)&Rfac,6ul*npt*sizeof(Scalar)); M((void**)&tacc,(size_t)n_p*sizeof(Scalar));
  // Rig port (2026-09-14) of the two BAL-path point-block optimisations, see
  // MSCG_ACCEL_RESEARCH.md: the tau-separated point factor (the undamped Givens
  // sweep is cached and only the three damping rows are re-applied when tau
  // moves) and the per-point V^-1 cache for the diagonal preconditioner. The rig
  // is the workload they should pay best on -- its reject rate is far higher
  // than BAL's (gba_230: 20 accepts, 22 rejects), and every reject re-factors at
  // a new tau with the assembly unchanged, which is exactly the split's case.
  // Same env flags as the BAL path so a run can be gated the same way.
  static const bool pf_split   = [](){const char* e=getenv("OCA_PF_SPLIT");   return e?atoi(e)!=0:true;}();
  static const bool diagk_vinv = [](){const char* e=getenv("OCA_DIAGK_VINV"); return e?atoi(e)!=0:true;}();
  Scalar *Rfac0=nullptr,*Svinv=nullptr;
  if(pf_split)   M((void**)&Rfac0,6ul*npt*sizeof(Scalar));
  if(diagk_vinv) M((void**)&Svinv,6ul*npt*sizeof(Scalar));
  bool r0_valid=false;   // invalidated whenever RFAssemble rewrites Bo
  M((void**)&uu,(size_t)n_p*sizeof(Scalar)); M((void**)&w,(size_t)n_c*sizeof(Scalar));
  M((void**)&bprime,(size_t)n_c*sizeof(Scalar)); M((void**)&corr,(size_t)n_cf*sizeof(Scalar));
  M((void**)&E,(size_t)n_c*sizeof(Scalar)); M((void**)&dk,(size_t)n_cf*sizeof(Scalar));
  M((void**)&xc_un,(size_t)n_cf*sizeof(Scalar)); M((void**)&xr_un,(size_t)n_c*sizeof(Scalar));
  M((void**)&xpv,(size_t)n_p*sizeof(Scalar));
  M((void**)&dred,(size_t)n_red*sizeof(Scalar)); M((void**)&d_best,(size_t)n_red*sizeof(Scalar));
  M((void**)&r_,(size_t)n_c*sizeof(Scalar)); M((void**)&pv_,(size_t)n_c*sizeof(Scalar));
  M((void**)&Ap_,(size_t)n_c*sizeof(Scalar)); M((void**)&okf,npt*sizeof(int));
  M((void**)&bcast_in,(size_t)n_cf*sizeof(Scalar)); M((void**)&bcast_out,(size_t)n_cf*sizeof(Scalar));
  M((void**)&dcost,sizeof(Scalar)); M((void**)&dviol,sizeof(int));
  int L=n_shifts;
  std::vector<Scalar*> xs(L),ps(L);
  for(int l=0;l<L;++l){ M((void**)&xs[l],(size_t)n_c*sizeof(Scalar)); M((void**)&ps[l],(size_t)n_c*sizeof(Scalar)); }
  RFAlloc(s_new,nframes,p.nsensors,ncalib,ncam,npt);
  // RFRetractSensors writes every sensor slot of s_new (identity update for
  // held sensors), so no seed copy is needed.

  // Gauge pin INSIDE the linear solve. RFPinGaugeFrame/RFPinGaugeScale zero
  // the pinned entries of the step after CG has solved the UNCONSTRAINED
  // system, which is not a gauge motion but a deformation: the cheapest way
  // for the unconstrained system to repair any mismatch of the gauge frame is
  // to move the gauge frame itself, so CG does exactly that, the pin then
  // drops that part, and everything else moves as if the gauge frame had
  // followed. The applied step is never the step the model evaluated.
  // Measured on Fuchsberg ref300 (OCA_RF_PROBE=1, 2026-09-18): along the
  // pinned CG step the true cost tracks eps*g'd to 4 digits, but the gauge
  // frame's own 6 gradient entries held 93% of |g| and 60-88% of the
  // unpinned g'd -- the frame had drifted out of the model because no step
  // could ever move it -- and the full step raised the cost by 1.1e4 against
  // a predicted decrease. Ceres removes the constant block's columns from
  // the Jacobian; the equivalent here is a mask on b' and on the operator
  // output, which keeps every CG iterate (r, p, x, all shifts) in the
  // constrained subspace exactly (their pinned entries are linear
  // combinations of exact zeros). OCA_RF_PINSOLVE=0 restores the old
  // post-solve pin for A/B.
  //
  // The same mask carries the problem's constant blocks (col_mask: frames,
  // sensors, calibration groups held by the caller), which are constraints of
  // the problem and therefore never subject to OCA_RF_PINSOLVE.
  static const int rf_pinsolve_env = [](){ const char* e=getenv("OCA_RF_PINSOLVE"); return e?atoi(e):1; }();
  Scalar* pmask=nullptr;
  const bool pin_frame = gauge_frame>=0 && gauge_frame<nframes;
  const bool pin_scale = gauge_scale_frame>=0 && gauge_scale_frame<nframes &&
                         gauge_scale_frame!=gauge_frame;
  int n_const_cols=0;
  if(col_mask && (int)col_mask->size()==n_c)
    for(Scalar m : *col_mask) if(!(m>0.0)) ++n_const_cols;
  const bool pin_solve = (rf_pinsolve_env && (pin_frame||pin_scale)) || n_const_cols>0;
  if(pin_solve){
    M((void**)&pmask,(size_t)n_c*sizeof(Scalar));
    std::vector<Scalar> hm((size_t)n_c,(Scalar)1);
    if(n_const_cols>0) for(int i=0;i<n_c;++i) hm[i]=((*col_mask)[i]>0.0)?(Scalar)1:(Scalar)0;
    if(rf_pinsolve_env && pin_frame) for(int k=0;k<6;++k) hm[6*gauge_frame+k]=(Scalar)0;
    if(rf_pinsolve_env && pin_scale) hm[6*gauge_scale_frame+3+gauge_scale_axis]=(Scalar)0;
    CUDA_CHECK(cudaMemcpy(pmask,hm.data(),(size_t)n_c*sizeof(Scalar),cudaMemcpyHostToDevice));
  }
  int n_const_pts=0;
  if(p.pt_const){
    std::vector<unsigned char> hc((size_t)npt);
    CUDA_CHECK(cudaMemcpy(hc.data(),p.pt_const,(size_t)npt,cudaMemcpyDeviceToHost));
    for(unsigned char c : hc) if(c) ++n_const_pts;
  }
  auto PinMask=[&](Scalar* v){ if(pin_solve) MFScaleVec<<<GridSize(n_c),256>>>(v,pmask,n_c); };

  // The sensor-block columns of B depend on the CURRENT composed state
  // (v_i = t_cam - t_sensor), so the closures read s.tc/s.ts live: after an
  // accepted step the linearization point moves with the state, as it must.
  auto Broadcast=[&](const Scalar* vr,Scalar* vf){
    RFBroadcast<<<GridSize(ncam),256>>>(vr,s.Rs,s.ts,s.tc,
        p.frame_of_cam,p.sensor_of_cam,p.free_sensor_of_cam,
        p.calib_of_cam,ncam,nframes,nfree,vf); };
  auto Reduce=[&](const Scalar* vf,Scalar* vr){
    CUDA_CHECK(cudaMemset(vr,0,(size_t)n_c*sizeof(Scalar)));
    RFReduce<<<GridSize(ncam),256>>>(vf,s.Rs,s.ts,s.tc,
        p.frame_of_cam,p.sensor_of_cam,p.free_sensor_of_cam,
        p.calib_of_cam,ncam,nframes,nfree,vr); };
  auto ReduceDiag=[&](const Scalar* df,Scalar* dr){
    CUDA_CHECK(cudaMemset(dr,0,(size_t)n_c*sizeof(Scalar)));
    RFReduceDiag<<<GridSize(ncam),256>>>(df,s.Rs,s.ts,s.tc,
        p.frame_of_cam,p.sensor_of_cam,p.free_sensor_of_cam,
        p.calib_of_cam,ncam,nframes,nfree,dr); };
  // RF: retraction consumes the REDUCED delta and recomposes image poses.
  auto DoRetract=[&](const Scalar* d,const RFDeviceState& out){
    if (gauge_frame >= 0 && gauge_frame < nframes)
      RFPinGaugeFrame<<<1,32>>>(const_cast<Scalar*>(d), gauge_frame);
    if (gauge_scale_frame >= 0 && gauge_scale_frame < nframes &&
        gauge_scale_frame != gauge_frame)
      RFPinGaugeScale<<<1,32>>>(const_cast<Scalar*>(d), gauge_scale_frame,
                                gauge_scale_axis);
    RFRetractFrames<<<GridSize(nframes),256>>>(s.Rf,s.tf,d,nframes,out.Rf,out.tf);
    RFRetractSensors<<<GridSize(p.nsensors),256>>>(s.Rs,s.ts,d,
        p.free_slot_of_sensor,p.nsensors,nframes,out.Rs,out.ts);
    RFRetractIntr<<<GridSize(RF_NI*ncalib),256>>>(s.intr,d,nframes,nfree,ncalib,p.calib_model,out.intr);
    RFRetractPoints<<<GridSize(3*npt),256>>>(s.X,d+n_c,npt,out.X);
    RFCompose<<<GridSize(ncam),256>>>(out.Rf,out.tf,out.Rs,out.ts,
                                      p.frame_of_cam,p.sensor_of_cam,ncam,out.Rc,out.tc);
  };

  cublasCreate(&blas);
  RFCompose<<<GridSize(ncam),256>>>(s.Rf,s.tf,s.Rs,s.ts,p.frame_of_cam,p.sensor_of_cam,
                                    ncam,s.Rc,s.tc);
  // ---- robust kernel state (see the CD=9 solver for the rationale) --------
  // The one rig-specific wrinkle is the far-field mask: only ACTIVE
  // observations may enter the scale estimate, so both the median auto-init
  // and the EM sums filter on the -1 sentinel written by RFResidSqKernel.
  Scalar rk_a2 = rk_scale2;
  Scalar* rk_sv = nullptr;
  Scalar* rk_acc = nullptr;
  if(rk==3){ M((void**)&rk_sv,(size_t)nobs*sizeof(Scalar));
             M((void**)&rk_acc,2*sizeof(Scalar)); }
  auto RobustUpdateScale=[&](){
    if(rk!=3) return;
    RFResidSqKernel<<<GridSize(nobs),256>>>(p.cam_idx,p.pt_idx,p.uv,s.Rc,s.tc,s.X,
        s.intr,p.calib_of_cam,p.calib_model,nobs,rk_sv);
    if(!(rk_a2>0.0)){
      std::vector<Scalar> h(nobs);
      CUDA_CHECK(cudaMemcpy(h.data(),rk_sv,(size_t)nobs*sizeof(Scalar),cudaMemcpyDeviceToHost));
      std::vector<Scalar> act; act.reserve(h.size());
      for(Scalar v : h) if(v>=0.0) act.push_back(v);
      if(act.empty()){ rk_a2 = rk_nu*(Scalar)1e-8; }
      else{
        std::nth_element(act.begin(),act.begin()+act.size()/2,act.end());
        const Scalar med=act[act.size()/2];
        rk_a2 = rk_nu*std::max(med/(Scalar)1.386,(Scalar)1e-8);
      }
    }
    Scalar sig2 = rk_a2/rk_nu;
    for(int em=0; em<3; ++em){
      CUDA_CHECK(cudaMemset(rk_acc,0,2*sizeof(Scalar)));
      RFTEMSum<<<GridSize(nobs),256>>>(rk_sv,nobs,rk_nu,sig2,rk_acc);
      Scalar hacc[2]; CUDA_CHECK(cudaMemcpy(hacc,rk_acc,2*sizeof(Scalar),cudaMemcpyDeviceToHost));
      if(!(hacc[1]>0.0)) break;
      sig2 = std::max(hacc[0]/(2.0*hacc[1]),(Scalar)1e-10);
    }
    rk_a2 = rk_nu*sig2;
  };
  // Experiment knobs (all default off = bit-compat). The device symbols must
  // be set before the first cost / cheirality evaluation below.
  static const Scalar rf_eta_env = [](){ const char* e=getenv("OCA_RF_ETA"); return e?(Scalar)atof(e):(Scalar)-1.0; }();
  static const int rf_maxck_env = [](){ const char* e=getenv("OCA_RF_MAXCK"); return e?atoi(e):0; }();
  static const int rf_mincg_env = [](){ const char* e=getenv("OCA_RF_MINCG"); return e?atoi(e):0; }();
  static const int rf_clamp_env = [](){ const char* e=getenv("OCA_RF_CLAMP"); return e?atoi(e):0; }();
  static const int rf_atan2_env = [](){ const char* e=getenv("OCA_RF_ATAN2"); return e?atoi(e):1; }();
  static const Scalar rf_thmax_env = [](){ const char* e=getenv("OCA_RF_THETA_MAX_DEG"); return e?(Scalar)atof(e):(Scalar)90.0; }();
  // OCA_RF_QTOL=<q>: Nash-Sofer / Ceres-style CG termination on the quadratic
  // model instead of the residual norm: stop after iteration k when
  // k*(Q_{k-1}-Q_k)/(Q_0-Q_k) < q (Ceres: eta=0.1, r_tolerance disabled,
  // "r_tolerance based termination is essentially useless in truncated Newton").
  static const Scalar rf_qtol_env = [](){ const char* e=getenv("OCA_RF_QTOL"); return e?(Scalar)atof(e):(Scalar)-1.0; }();
  static const int rf_lamwin_env = [](){ const char* e=getenv("OCA_RF_LAMWIN"); return e?atoi(e):0; }();
  static const Scalar rf_tau_cap_env = [](){ const char* e=getenv("OCA_RF_TAU_CAP"); return e?(Scalar)atof(e):(Scalar)-1.0; }();
  // EXPERIMENT (OCA_RF_CLEANCONV=1, default off = bit-compat): test
  // func_tolerance only on a step accepted at un-ratcheted damping. After a
  // rejection streak tau/lambda are inflated and the first accepted step is a
  // crumb whose relative decrease is < 1e-6 although the model is far from a
  // minimum (measured on the Fuchsberg GBA: "converged" at it 41 with tau 3e5,
  // a rerun then took 100 clean steps and 1.878e7 -> 1.772e7).
  static const int rf_cleanconv_env = [](){ const char* e=getenv("OCA_RF_CLEANCONV"); return e?atoi(e):0; }();
  const bool rf_knobs = (rf_eta_env>=0.0)||(rf_maxck_env>0)||(rf_mincg_env>0)||(rf_qtol_env>0.0)||(rf_lamwin_env>0);
  {
    const Scalar thmax = rf_thmax_env * (Scalar)(3.14159265358979323846 / 180.0);
    CUDA_CHECK(cudaMemcpyToSymbol(g_rf_clamp,&rf_clamp_env,sizeof(int)));
    CUDA_CHECK(cudaMemcpyToSymbol(g_rf_atan2,&rf_atan2_env,sizeof(int)));
    CUDA_CHECK(cudaMemcpyToSymbol(g_rf_theta_max,&thmax,sizeof(Scalar)));
  }
  if(verbose && (rf_knobs||rf_clamp_env||rf_atan2_env||rf_tau_cap_env>0.0))
    std::printf("  RF: experiment knobs eta=%g qtol=%g mincg=%d maxck=%d clamp=%d atan2=%d theta_max=%g deg lamwin=%d tau_cap=%g\n",
                (double)rf_eta_env,(double)rf_qtol_env,rf_mincg_env,rf_maxck_env,rf_clamp_env,
                rf_atan2_env,(double)rf_thmax_env,rf_lamwin_env,(double)rf_tau_cap_env);
  if(verbose)
    std::printf("  RF: gauge frame=%d scale frame=%d axis=%d pinned %s; constant: %d of %d columns, %d of %d points\n",
                gauge_frame,gauge_scale_frame,gauge_scale_axis,
                (rf_pinsolve_env&&(pin_frame||pin_scale))?"inside the linear solve":(pin_frame||pin_scale)?"after the solve (OCA_RF_PINSOLVE=0)":"nowhere",
                n_const_cols,n_c,n_const_pts,npt);
  RobustUpdateScale();
  Scalar cost=RFComputeCost(p,s,dcost,rk,rk_a2);
  int cheir0=RFCheirality(p,s,dviol);
  RunLog log; log.iters.push_back(0); log.costs.push_back(cost);
  Scalar lam_cam=lam0, lam_floor=lam0*1e-8;
  MFStats st; Scalar prev_bnorm=-1.0;
  int n_accept=0,n_reject=0,rej_streak=0;
  int stuck=0; bool converged=false; Scalar prev_cost=cost;
  bool clean_step=false; const char* stop_reason="maxit";
  Scalar lam_pre_streak=lam0;
  Scalar tau_base=tau_pt, tau_used=tau_pt, tau_win=0.0;
  CsvOpen("rigfisheye", g_csv_problem.c_str()); CsvRow(0,(double)cost);
  bool need_assembly=true; int retries=0;
  for(int k=0;k<max_iter;){
   if(need_assembly){
    r0_valid=false;   // Bo about to be rewritten: the cached undamped factor is stale
    CUDA_CHECK(cudaMemset(Hcc,0,(size_t)CD*CD*ncam*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(Cdiag,0,3ul*npt*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(bc,0,(size_t)n_cf*sizeof(Scalar)));
    CUDA_CHECK(cudaMemset(bp,0,(size_t)n_p*sizeof(Scalar)));
    RobustUpdateScale();   // frozen for this outer, incl. assembly-reusing retries
    if(mf_fp32) RFAssemble<float><<<GridSize(nobs),256>>>(p.cam_idx,p.pt_idx,p.uv,
        s.Rc,s.tc,s.X,s.intr,p.calib_of_cam,p.calib_model,p.imask,p.obs2pslot,p.obs2cslot,nobs,
        Hcc,Cdiag,Gp32,Gc32,Bo32,bc,bp,rk,rk_a2);
    else        RFAssemble<Scalar><<<GridSize(nobs),256>>>(p.cam_idx,p.pt_idx,p.uv,
        s.Rc,s.tc,s.X,s.intr,p.calib_of_cam,p.calib_model,p.imask,p.obs2pslot,p.obs2cslot,nobs,
        Hcc,Cdiag,Gp,Gc,Bo,bc,bp,rk,rk_a2);
   }
    // tau ratchet with warm ladder (always on here; this path always has
    // intrinsics in the camera block, the situation the ratchet exists for).
    // EXPERIMENT (OCA_RF_TAU_CAP=<x>, default off = bit-compat): ceiling on the
    // effective point damping. Measured on the full Fuchsberg map (11k images):
    // when every outer iteration's first attempt is rejected, the warm ladder
    // compounds across iterations (tau_win is set on every contested accept and
    // only halves on clean ones) and tau ran 3e-3 -> 3e61 in 27 iterations. At
    // tau >> 1 the points are frozen in the model, so the accepted steps are
    // camera-only crumbs and the coupled camera-point modes never move.
    Scalar tau_eff = tau_base;
    if(rej_streak>0){
      tau_eff = tau_base*std::pow((Scalar)10.0,(Scalar)std::min(rej_streak,12));
      if(tau_win>tau_eff) tau_eff = tau_win*std::pow((Scalar)10.0,(Scalar)(rej_streak-1));
    }
    // Hard ceiling: past ~1e12 the point step is already < 1e-12 of its
    // Gauss-Newton value (frozen), and beyond ~1e300 tau*Cdiag overflows in
    // the point factor and produces NaN point steps (see RFResidual).
    if(tau_eff>(Scalar)1e12) tau_eff = (Scalar)1e12;
    if(rf_tau_cap_env>0.0 && tau_eff>rf_tau_cap_env) tau_eff = rf_tau_cap_env;
    tau_used = tau_eff;
    if(pf_split){
      // R0 survives everything except a new assembly, so a reject retry -- which
      // moves only tau_eff -- runs the O(1) damping stage alone.
      if(!r0_valid){
        if(mf_fp32) MFPointFactorR0<float><<<GridSize(npt),256>>>(Bo32,p.point_obs_offsets,p.point_obs_list,npt,Rfac0);
        else        MFPointFactorR0<Scalar><<<GridSize(npt),256>>>(Bo,p.point_obs_offsets,p.point_obs_list,npt,Rfac0);
        r0_valid=true;
      }
      MFPointFactorDamp<<<GridSize(npt),256>>>(Rfac0,Cdiag,tau_eff,npt,Rfac,okf);
    }
    else if(mf_fp32) MFPointFactor<float><<<GridSize(npt),256>>>(Bo32,Cdiag,p.point_obs_offsets,p.point_obs_list,tau_eff,npt,Rfac,okf);
    else        MFPointFactor<Scalar><<<GridSize(npt),256>>>(Bo,Cdiag,p.point_obs_offsets,p.point_obs_list,tau_eff,npt,Rfac,okf);
    // Constant points: a zero factor is what MFVinvApply / MFBackSub /
    // MFPointVinv / MFDiagK all read as "do not eliminate" -- no Schur
    // correction from this point in b', in the operator, in the diagonal, and a
    // zero point step. Re-applied after every (re)factorisation, including the
    // O(1) tau-only refactor of a reject retry.
    if(p.pt_const) RFZeroConstPointFactor<<<GridSize(npt),256>>>(Rfac,p.pt_const,npt);
    MFVinvApply<<<GridSize(npt),256>>>(Rfac,bp,npt,uu);
    CUDA_CHECK(cudaMemset(corr,0,(size_t)n_cf*sizeof(Scalar)));
    if(mf_fp32) MFRhsPrime<CD,float><<<GridSize(nobs),256>>>(Gp32,p.mf_scam,p.mf_spt,uu,nobs,corr);
    else        MFRhsPrime<CD,Scalar><<<GridSize(nobs),256>>>(Gp,p.mf_scam,p.mf_spt,uu,nobs,corr);
    CUDA_CHECK(cudaMemcpy(bcast_out,bc,(size_t)n_cf*sizeof(Scalar),cudaMemcpyDeviceToDevice));
    { const Scalar m1=-1.0; cublasDaxpy(blas,n_cf,&m1,corr,1,bcast_out,1); }
    Reduce(bcast_out,bprime);
    PinMask(bprime);
    if(use_equil){
      CUDA_CHECK(cudaMemset(dk,0,(size_t)n_cf*sizeof(Scalar)));
      if(diagk_vinv){
        MFPointVinv<<<GridSize(npt),256>>>(Rfac,npt,Svinv);
        if(mf_fp32) MFDiagKS<CD,float><<<GridSize(nobs),256>>>(Gp32,p.mf_spt,p.mf_scam,Svinv,nobs,dk);
        else        MFDiagKS<CD,Scalar><<<GridSize(nobs),256>>>(Gp,p.mf_spt,p.mf_scam,Svinv,nobs,dk);
      }
      else if(mf_fp32) MFDiagK<CD,float><<<GridSize(nobs),256>>>(Gp32,p.mf_spt,p.mf_scam,Rfac,nobs,dk);
      else        MFDiagK<CD,Scalar><<<GridSize(nobs),256>>>(Gp,p.mf_spt,p.mf_scam,Rfac,nobs,dk);
      MFDiagHcc<CD><<<GridSize(ncam),256>>>(Hcc,ncam,dk);
      // RF: diag reduce needs the squared rotation weights, see RFReduceDiag.
      ReduceDiag(dk,xr_un);
      MFMakeEquil<<<GridSize(n_c),256>>>(xr_un,n_c,E);
      MFScaleVec<<<GridSize(n_c),256>>>(bprime,E,n_c);
    }
    auto Kv=[&](const Scalar* vin,Scalar* vout){
      Broadcast(vin,bcast_in);
      CUDA_CHECK(cudaMemset(tacc,0,(size_t)n_p*sizeof(Scalar)));
      if(mf_fp32){ MFPass1<CD,float><<<GridSize(nobs),256>>>(Gp32,p.mf_scam,p.mf_spt,bcast_in,nobs,tacc);
                   MFVinvApply<<<GridSize(npt),256>>>(Rfac,tacc,npt,uu);
                   MFPass2<CD,float><<<ncam,256>>>(Gc32,p.mf_cspt,p.mf_coff,uu,Hcc,bcast_in,nobs,bcast_out); }
      else       { MFPass1<CD,Scalar><<<GridSize(nobs),256>>>(Gp,p.mf_scam,p.mf_spt,bcast_in,nobs,tacc);
                   MFVinvApply<<<GridSize(npt),256>>>(Rfac,tacc,npt,uu);
                   MFPass2<CD,Scalar><<<ncam,256>>>(Gc,p.mf_cspt,p.mf_coff,uu,Hcc,bcast_in,nobs,bcast_out); }
      Reduce(bcast_out,vout);
      ++st.matvecs;
    };
    auto KvS=[&](const Scalar* vin,Scalar* vout){
      if(!use_equil){ Kv(vin,vout); PinMask(vout); return; }
      CUDA_CHECK(cudaMemcpy(w,vin,(size_t)n_c*sizeof(Scalar),cudaMemcpyDeviceToDevice));
      MFScaleVec<<<GridSize(n_c),256>>>(w,E,n_c);
      Kv(w,vout);
      MFScaleVec<<<GridSize(n_c),256>>>(vout,E,n_c);
      PinMask(vout);
    };
    Scalar best_cost=cost; int best_sh=-1,best_ck=-1; bool have=false;
    CUDA_CHECK(cudaMemset(d_best,0,(size_t)n_red*sizeof(Scalar)));
    // OCA_RHO_LAMBDA / OCA_GRID_DOWN: rho-gated lambda + two-sided shift menu,
    // ported from the CD9 solver (v3 semantics: Nielsen TR gated to the grind
    // phase, greedy-speed decay while relative progress is large, fac applied
    // to the pre-streak lambda, 1e8 ceiling). Off by default = bit-compat.
    static const bool rf_rho = getenv("OCA_RHO_LAMBDA")!=nullptr;
    static const int rf_gd_env = [](){ const char* e=getenv("OCA_GRID_DOWN"); return e?std::atoi(e):0; }();
    const int rf_gd = std::min(std::max(rf_gd_env,0),L-1);
    // OCA_RHO_SHIFT / OCA_ALPHA_RHO: same semantics as the CD9 solver (anchor
    // Nielsen at the winning shift's damping; alpha grid under rho with an
    // alpha-aware prediction). Off by default = bit-compat.
    static const int rf_rho_shift_down = [](){
      const char* e = getenv("OCA_RHO_SHIFT");
      return e ? std::max(1, std::atoi(e)) : 0; }();
    static const bool rf_rho_shift = rf_rho_shift_down > 0;
    static const bool rf_alpha_rho = getenv("OCA_ALPHA_RHO")!=nullptr;
    std::vector<Scalar> preds(L,0.0); Scalar pred_best=0.0;
    Scalar bpd_best=0.0;   // b'^T x of the winning candidate (scaled space)
    auto Score=[&](const Scalar* x_scaled,int sh,int ck){
      // Unscale in the reduced space, lift to full for the point relaxation,
      // but keep the REDUCED delta: the retraction wants frame tangents.
      CUDA_CHECK(cudaMemcpy(xr_un,x_scaled,(size_t)n_c*sizeof(Scalar),cudaMemcpyDeviceToDevice));
      if(use_equil) MFScaleVec<<<GridSize(n_c),256>>>(xr_un,E,n_c);
      Broadcast(xr_un,xc_un);
      CUDA_CHECK(cudaMemset(tacc,0,(size_t)n_p*sizeof(Scalar)));
      if(mf_fp32) MFPass1<CD,float><<<GridSize(nobs),256>>>(Gp32,p.mf_scam,p.mf_spt,xc_un,nobs,tacc);
      else        MFPass1<CD,Scalar><<<GridSize(nobs),256>>>(Gp,p.mf_scam,p.mf_spt,xc_un,nobs,tacc);
      MFBackSub<<<GridSize(npt),256>>>(Rfac,bp,tacc,npt,xpv);
      CUDA_CHECK(cudaMemcpy(dred,xr_un,(size_t)n_c*sizeof(Scalar),cudaMemcpyDeviceToDevice));
      CUDA_CHECK(cudaMemcpy(dred+n_c,xpv,(size_t)n_p*sizeof(Scalar),cudaMemcpyDeviceToDevice));
      KernelNegateInPlace<<<GridSize(n_red),256>>>(dred,n_red);
      DoRetract(dred,s_new);
      Scalar c=RFComputeCost(p,s_new,dcost,rk,rk_a2);
      ++st.cand_evals;
      if(c<best_cost){ best_cost=c; best_sh=sh; best_ck=ck; have=true;
        pred_best=(sh>=0&&sh<L)?preds[sh]:0.0;
        if(rf_rho && rf_alpha_rho){
          Scalar bd=0; cublasDdot(blas,n_c,bprime,1,x_scaled,1,&bd);
          bpd_best=bd; }
        CUDA_CHECK(cudaMemcpy(d_best,dred,(size_t)n_red*sizeof(Scalar),cudaMemcpyDeviceToDevice)); }
    };
    std::vector<Scalar> shifts(L);
    for(int l=0;l<L;++l) shifts[l]=lam_cam*std::pow(10.0,(double)(l-rf_gd));
    for(int l=0;l<L;++l){ CUDA_CHECK(cudaMemset(xs[l],0,(size_t)n_c*sizeof(Scalar)));
      CUDA_CHECK(cudaMemcpy(ps[l],bprime,(size_t)n_c*sizeof(Scalar),cudaMemcpyDeviceToDevice)); }
    std::vector<Scalar> zeta(L,1.0),zprev(L,1.0),znext(L,1.0),als(L,0.0),bes(L,0.0);
    CUDA_CHECK(cudaMemset(xs[0],0,(size_t)n_c*sizeof(Scalar)));
    CUDA_CHECK(cudaMemcpy(r_,bprime,(size_t)n_c*sizeof(Scalar),cudaMemcpyDeviceToDevice));
    CUDA_CHECK(cudaMemcpy(pv_,bprime,(size_t)n_c*sizeof(Scalar),cudaMemcpyDeviceToDevice));
    Scalar nb; cublasDnrm2(blas,n_c,bprime,1,&nb);
    Scalar rr; cublasDdot(blas,n_c,r_,1,r_,1,&rr);
    Scalar eta = ew_eta_max;
    if(prev_bnorm>0.0){ Scalar q=(nb*nb)/(prev_bnorm*prev_bnorm); eta=std::min(ew_eta_max,(Scalar)0.9*q); }
    prev_bnorm=nb;
    int maxck = ckpts.empty()?64:*std::max_element(ckpts.begin(),ckpts.end());
    // EXPERIMENT knobs (default off = bit-compat). Measured on Fuchsberg
    // ref300: the Eisenstat-Walker test is met after ONE CG iteration nearly
    // every outer (cg_it=0 in the trace), which makes each step a scaled
    // steepest-descent step; the shared-intrinsics block, coupled to every
    // pose and point, then barely moves (Ceres gains 6% of cost from the
    // intrinsics on the same problem, this path 0.26%).
    //   OCA_RF_ETA=<x>    fixed forcing term instead of min(eta_max, 0.9 q)
    //   OCA_RF_MINCG=<n>  never stop CG before n iterations
    //   OCA_RF_MAXCK=<n>  CG depth cap (default: last checkpoint, 128)
    if(rf_eta_env>=0.0) eta=rf_eta_env;
    if(rf_maxck_env>0)  maxck=rf_maxck_env;
    Scalar al_prev=1.0,be_prev=0.0; size_t ci_=0; int cg_it=0; bool trunc=false;
    int done_its=0, last_scored=-1;   // knobs: iterate count reached / last count scored
    Scalar q_tot=0.0;                  // knobs: model decrease of the shift-0 system so far
    for(cg_it=0; cg_it<maxck; ++cg_it){
      KvS(pv_,Ap_);
      { const Scalar sh=shifts[0]; cublasDaxpy(blas,n_c,&sh,pv_,1,Ap_,1); }
      Scalar pAp,pp; cublasDdot(blas,n_c,pv_,1,Ap_,1,&pAp); cublasDdot(blas,n_c,pv_,1,pv_,1,&pp);
      if(!(pAp>1e-14*pp)){ ++st.negcurv; trunc=true; break; }
      Scalar al=rr/pAp;
      if(rf_rho) preds[0]+=0.5*al*rr;
      const Scalar q_dec=0.5*al*rr; q_tot+=q_dec;
      cublasDaxpy(blas,n_c,&al,pv_,1,xs[0],1);
      Scalar mal=-al; cublasDaxpy(blas,n_c,&mal,Ap_,1,r_,1);
      Scalar rr_new; cublasDdot(blas,n_c,r_,1,r_,1,&rr_new);
      Scalar be=rr_new/rr;
      for(int l=1;l<L;++l){
        Scalar sg=shifts[l]-shifts[0];
        Scalar den=al*be_prev*(zprev[l]-zeta[l])+zprev[l]*al_prev*(1.0+sg*al);
        znext[l]=(den!=0.0)?(zeta[l]*zprev[l]*al_prev)/den:0.0;
        if(!std::isfinite(znext[l])) znext[l]=0.0;
        als[l]=al*znext[l]/zeta[l]; bes[l]=be*(znext[l]/zeta[l])*(znext[l]/zeta[l]);
        if(rf_rho) preds[l]+=0.5*als[l]*zeta[l]*zeta[l]*rr;
        cublasDaxpy(blas,n_c,&als[l],ps[l],1,xs[l],1);
      }
      for(int l=1;l<L;++l){
        cublasDscal(blas,n_c,&bes[l],ps[l],1);
        cublasDaxpy(blas,n_c,&znext[l],r_,1,ps[l],1);
        zprev[l]=zeta[l]; zeta[l]=znext[l];
      }
      al_prev=al; be_prev=be;
      cublasDscal(blas,n_c,&be,pv_,1);
      { const Scalar one=1.0; cublasDaxpy(blas,n_c,&one,r_,1,pv_,1); }
      rr=rr_new;
      done_its=cg_it+1;
      while(ci_<ckpts.size() && cg_it+1==ckpts[ci_]){
        for(int l=0;l<L;++l) Score(xs[l],l,cg_it+1);
        last_scored=cg_it+1;
        ++ci_;
      }
      if(rf_qtol_env>0.0){
        const Scalar zeta=(q_tot>0.0)?(Scalar)(cg_it+1)*q_dec/q_tot:0.0;
        if(zeta<rf_qtol_env && cg_it+1>=rf_mincg_env) break;
      } else if(sqrt(rr_new)<=eta*nb && cg_it+1>=rf_mincg_env) break;
    }
    if(trunc){ for(int l=0;l<L;++l) Score(xs[l],l,cg_it); }
    else if(ci_==0){ for(int l=0;l<L;++l) Score(xs[l],l,cg_it); }
    else if(rf_knobs && last_scored!=done_its){
      // knobs on: the final CG iterate is scored even when it is not a
      // checkpoint (with a deep CG it is usually the best candidate).
      for(int l=0;l<L;++l) Score(xs[l],l,done_its); }

    // EXPERIMENT (OCA_RF_PROBE=1, verbose): directional consistency probe.
    // Evaluates the TRUE cost along (a) the negative reduced gradient, (b) the
    // shift-0 CG iterate with its point back-substitution and (c) its camera
    // part alone, at step fractions 1e-8..1, against the first-order
    // prediction eps*g'd. Separates "the direction is not a descent direction"
    // (tiny steps go up: gradient / B operator / retraction inconsistent with
    // the cost) from "the step is too long" (tiny steps track the prediction,
    // the full step does not).
    static const int rf_probe_env = [](){ const char* e=getenv("OCA_RF_PROBE"); return e?atoi(e):0; }();
    if(rf_probe_env && verbose){
      static Scalar *gred=nullptr,*dprobe=nullptr,*dpin=nullptr,*dblk=nullptr;
      if(!gred){ CUDA_CHECK(cudaMalloc(&gred,(size_t)n_c*sizeof(Scalar)));
                 CUDA_CHECK(cudaMalloc(&dprobe,(size_t)n_red*sizeof(Scalar)));
                 CUDA_CHECK(cudaMalloc(&dpin,(size_t)n_red*sizeof(Scalar)));
                 CUDA_CHECK(cudaMalloc(&dblk,(size_t)n_red*sizeof(Scalar))); }
      Reduce(bc,gred);                                    // reduced gradient, unscaled
      // Block layout of the reduced+point vector.
      const int o_fr=0, n_fr=6*nframes, o_se=n_fr, n_se=6*nfree, o_in=n_fr+n_se, n_in=RF_NI*ncalib;
      // Adjointness of the B operator: <B v, w> must equal <v, B^T w>.
      {
        std::vector<Scalar> hv(n_c),hw(n_cf); unsigned long long sd=88172645463325252ull;
        auto rnd=[&](){ sd^=sd<<13; sd^=sd>>7; sd^=sd<<17; return (Scalar)((sd>>11)*(1.0/9007199254740992.0))-0.5; };
        for(auto& v:hv) v=rnd(); for(auto& v:hw) v=rnd();
        CUDA_CHECK(cudaMemcpy(xr_un,hv.data(),(size_t)n_c*sizeof(Scalar),cudaMemcpyHostToDevice));
        CUDA_CHECK(cudaMemcpy(bcast_out,hw.data(),(size_t)n_cf*sizeof(Scalar),cudaMemcpyHostToDevice));
        Broadcast(xr_un,xc_un); Reduce(bcast_out,w);
        Scalar a=0,b=0; cublasDdot(blas,n_cf,xc_un,1,bcast_out,1,&a); cublasDdot(blas,n_c,xr_un,1,w,1,&b);
        std::printf("  PROBE adjoint <Bv,w>=%.10e <v,B^Tw>=%.10e rel=%.2e  (gauge_frame=%d scale_frame=%d axis=%d nframes=%d nfree=%d ncalib=%d)\n",
                    (double)a,(double)b,(double)(fabs(a-b)/std::max(fabs(a),(Scalar)1e-300)),
                    gauge_frame,gauge_scale_frame,gauge_scale_axis,nframes,nfree,ncalib);
      }
      // Directional test on the direction AS APPLIED: pinned like DoRetract
      // pins it, with g'd split by block so a block whose gradient disagrees
      // with its retraction shows up on its own.
      auto Probe=[&](const char* name,const Scalar* dsrc,int neps){
        CUDA_CHECK(cudaMemcpy(dpin,dsrc,(size_t)n_red*sizeof(Scalar),cudaMemcpyDeviceToDevice));
        if(gauge_frame>=0&&gauge_frame<nframes) RFPinGaugeFrame<<<1,32>>>(dpin,gauge_frame);
        if(gauge_scale_frame>=0&&gauge_scale_frame<nframes&&gauge_scale_frame!=gauge_frame)
          RFPinGaugeScale<<<1,32>>>(dpin,gauge_scale_frame,gauge_scale_axis);
        Scalar gd_all=0,gd_fr=0,gd_se=0,gd_in=0,gd_p=0,gd_g=0,nrm_c=0,nrm_p=0;
        cublasDdot(blas,n_c,gred,1,dsrc,1,&gd_all);               // unpinned, for the gauge share
        cublasDdot(blas,n_fr,gred+o_fr,1,dpin+o_fr,1,&gd_fr);
        if(n_se) cublasDdot(blas,n_se,gred+o_se,1,dpin+o_se,1,&gd_se);
        cublasDdot(blas,n_in,gred+o_in,1,dpin+o_in,1,&gd_in);
        cublasDdot(blas,n_p,bp,1,dpin+n_c,1,&gd_p);
        if(gauge_frame>=0) cublasDdot(blas,6,gred+6*gauge_frame,1,dsrc+6*gauge_frame,1,&gd_g);
        cublasDnrm2(blas,n_c,dpin,1,&nrm_c); cublasDnrm2(blas,n_p,dpin+n_c,1,&nrm_p);
        const Scalar gd=gd_fr+gd_se+gd_in+gd_p;
        std::printf("  PROBE %-6s g'd(pinned)=%.4e [frames %.4e sensors %.4e intr %.4e pts %.4e] gauge-frame share of unpinned g'd=%.3f |d_c|=%.3e |d_p|=%.3e\n",
                    name,(double)gd,(double)gd_fr,(double)gd_se,(double)gd_in,(double)gd_p,
                    (double)(gd_g/(gd_all+gd_p)),(double)nrm_c,(double)nrm_p);
        const Scalar eps[9]={1e-8,1e-7,1e-6,1e-5,1e-4,1e-3,1e-2,1e-1,1.0};
        const int i0=(neps>=9)?0:(9-neps);
        for(int i=i0;i<9;++i){
          MFAlphaScale<<<GridSize(n_red),256>>>(dred,dpin,eps[i],eps[i],n_c,n_red);
          DoRetract(dred,s_new);
          const Scalar c=RFComputeCost(p,s_new,dcost,rk,rk_a2);
          const int nv=RFCheirality(p,s_new,dviol);
          const Scalar pred=eps[i]*gd;
          std::printf("    eps=%-6g dcost=%+.6e  1st-order=%+.6e  ratio=%+.4f  inactive=%d\n",
                      (double)eps[i],(double)(c-cost),(double)pred,(double)((c-cost)/pred),nv);
        }
      };
      // Restrict a direction to one block (zero everything else).
      auto BlockOf=[&](const Scalar* dsrc,int off,int len){
        CUDA_CHECK(cudaMemset(dblk,0,(size_t)n_red*sizeof(Scalar)));
        CUDA_CHECK(cudaMemcpy(dblk+off,dsrc+off,(size_t)len*sizeof(Scalar),cudaMemcpyDeviceToDevice));
        return (const Scalar*)dblk; };
      // (a) steepest descent, unit length: d = -[g_c ; g_p]/|g|
      CUDA_CHECK(cudaMemcpy(dprobe,gred,(size_t)n_c*sizeof(Scalar),cudaMemcpyDeviceToDevice));
      CUDA_CHECK(cudaMemcpy(dprobe+n_c,bp,(size_t)n_p*sizeof(Scalar),cudaMemcpyDeviceToDevice));
      { Scalar gn=0; cublasDnrm2(blas,n_red,dprobe,1,&gn); const Scalar sc=-1.0/std::max(gn,(Scalar)1e-300);
        cublasDscal(blas,n_red,&sc,dprobe,1); }
      Probe("SD/|g|",dprobe,9);
      // (b) shift-0 CG iterate, points by back-substitution (as in Score)
      CUDA_CHECK(cudaMemcpy(xr_un,xs[0],(size_t)n_c*sizeof(Scalar),cudaMemcpyDeviceToDevice));
      if(use_equil) MFScaleVec<<<GridSize(n_c),256>>>(xr_un,E,n_c);
      Broadcast(xr_un,xc_un);
      CUDA_CHECK(cudaMemset(tacc,0,(size_t)n_p*sizeof(Scalar)));
      if(mf_fp32) MFPass1<CD,float><<<GridSize(nobs),256>>>(Gp32,p.mf_scam,p.mf_spt,xc_un,nobs,tacc);
      else        MFPass1<CD,Scalar><<<GridSize(nobs),256>>>(Gp,p.mf_scam,p.mf_spt,xc_un,nobs,tacc);
      MFBackSub<<<GridSize(npt),256>>>(Rfac,bp,tacc,npt,xpv);
      CUDA_CHECK(cudaMemcpy(dprobe,xr_un,(size_t)n_c*sizeof(Scalar),cudaMemcpyDeviceToDevice));
      CUDA_CHECK(cudaMemcpy(dprobe+n_c,xpv,(size_t)n_p*sizeof(Scalar),cudaMemcpyDeviceToDevice));
      KernelNegateInPlace<<<GridSize(n_red),256>>>(dprobe,n_red);
      Probe("CG0",dprobe,9);
      // (c) the same step one block at a time: each ratio must -> 1 on its own.
      Probe("CG0:fr",BlockOf(dprobe,o_fr,n_fr),4);
      if(n_se) Probe("CG0:se",BlockOf(dprobe,o_se,n_se),4);
      Probe("CG0:in",BlockOf(dprobe,o_in,n_in),4);
      Probe("CG0:pt",BlockOf(dprobe,n_c,n_p),4);
    }

    int alpha_win=0;
    if(have && use_alpha && (!rf_rho || rf_alpha_rho)){
      const Scalar as[3]={0.7,1.0,1.4};
      // Under rho mode the winning combo must carry a matching prediction:
      // pred(s) = s*b'd - s^2*(b'd - pred1), s compounding across wins.
      const Scalar bpd0=bpd_best, pred1=pred_best;
      Scalar s_cum=1.0;
      for(int a1=0;a1<3;++a1) for(int a2=0;a2<3;++a2){
        if(as[a1]==1.0&&as[a2]==1.0) continue;
        MFAlphaScale<<<GridSize(n_red),256>>>(dred,d_best,as[a1],as[a2],n_c,n_red);
        DoRetract(dred,s_new);
        Scalar c=RFComputeCost(p,s_new,dcost,rk,rk_a2);
        if(c<best_cost){ best_cost=c; alpha_win=1;
          if(rf_rho){
            s_cum*=as[a1];
            pred_best=s_cum*bpd0-s_cum*s_cum*(bpd0-pred1); }
          CUDA_CHECK(cudaMemcpy(d_best,dred,(size_t)n_red*sizeof(Scalar),cudaMemcpyDeviceToDevice)); }
      }
    }
    bool accepted=false;
    if(have && best_cost<cost){
      const Scalar cost_pre_accept=cost;
      DoRetract(d_best,s_new);
      RFCopy(s,s_new,nframes,p.nsensors,ncalib,ncam,npt);
      cost=best_cost;
      if(rf_rho){
        const Scalar act=cost_pre_accept-cost;
        const Scalar rho=(pred_best>1e-300)?act/pred_best:1.0;
        const Scalar f3=2.0*rho-1.0;
        Scalar fac=1.0-f3*f3*f3;
        if(fac<(Scalar)(1.0/3.0)) fac=(Scalar)(1.0/3.0);
        if(rho<0.25) fac=2.0;
        const Scalar rel=act/std::max(cost_pre_accept,(Scalar)1e-300);
        if(rel>(Scalar)1e-4) fac=std::min(fac,(Scalar)0.5);
        Scalar base=(rej_streak>0)?lam_pre_streak:lam_cam;
        // OCA_RHO_SHIFT: anchor Nielsen at the winning shift's damping.
        if(rf_rho_shift && best_sh>=0 && rej_streak==0){
          // Clean accepts only; down free, up clamped (see oca_cuda.cu).
          const int rel_sh=std::max(std::min(best_sh-rf_gd,1),
                                    -rf_rho_shift_down);
          base=lam_cam*std::pow((Scalar)10.0,(Scalar)rel_sh);
        }
        lam_cam=std::min(std::max(base*fac,lam_floor),(Scalar)1e8);
      }
      else if(rf_lamwin_env && best_sh>=0){
        // OCA_RF_LAMWIN: the accepted step was solved at the winning shift's
        // damping sigma_win = lam*10^(best_sh-gd); recentre there and halve.
        // The legacy policy below halves lam regardless of which shift won
        // (and, after a reject streak, resets to the pre-streak lam), so lam
        // sits at the 1e-7 floor for the whole grind while every accept is
        // found at shift 4 or after several x10 escalations -- each of them
        // a full CG solve thrown away. Measured on ref300 (mf_pin trace, its
        // 36-50): 1-4 rejected solves per accepted 1-CG-iteration step.
        //   1: recentre on every accept (contested accepts bank the streak's
        //      escalations too, which the CD9 solver found can freeze a grind
        //      at an elevated lambda -- see the OCA_RHO_SHIFT comments there)
        //   2: clean accepts recentre; contested accepts take the larger of
        //      the legacy pre-streak/2 and sigma_win/20 (one decade less).
        const Scalar sig_win=shifts[best_sh];
        if(rej_streak==0 || rf_lamwin_env==1) lam_cam=std::max(sig_win*0.5,lam_floor);
        else lam_cam=std::max(std::max(lam_pre_streak*0.5,sig_win*0.05),lam_floor);
      }
      else if(rej_streak>0) lam_cam=std::max(lam_pre_streak*0.5,lam_floor);
      else             lam_cam=std::max(lam_cam*0.5,lam_floor);
      if(rej_streak>0) tau_win=tau_used;
      else             tau_win*=(Scalar)0.5;
      clean_step=(rej_streak==0);
      accepted=true; ++n_accept; rej_streak=0;
    } else {
      if(rej_streak==0) lam_pre_streak=lam_cam;
      lam_cam*=10.0; ++n_reject; ++rej_streak;
    }
    if(verbose)
      std::printf("  RF it %3d cost=%.6e lam=%.3e tau=%.2e cg_it=%d shift=%d ckpt=%d alpha=%d %s mv=%ld best=%.6e pred=%.3e\n",
                  k+1,(double)cost,(double)lam_cam,(double)tau_used,cg_it,best_sh,best_ck,alpha_win,
                  accepted?"acc":"REJ",st.matvecs,(double)best_cost,(double)pred_best);
    if(!accepted && retries<max_inner_retry){
      ++retries; need_assembly=false;
      continue;
    }
    retries=0; need_assembly=true;
    log.iters.push_back(k+1); log.costs.push_back(cost);
    CsvRow(k+1,(double)cost);
    if(accepted){
      stuck=0;
      if(func_tolerance>0 && prev_cost>0 && (clean_step || !rf_cleanconv_env) &&
         (prev_cost-cost) < func_tolerance*prev_cost){
        converged=true; stop_reason="ftol";
        if(verbose) std::printf("  RF: converged (relative cost decrease < %.2e)\n",
                                (double)func_tolerance);
      }
      prev_cost=cost;
    } else if(max_consecutive_failures>0 && ++stuck>=max_consecutive_failures){
      converged=true; stop_reason="stuck";
      if(verbose) std::printf("  RF: converged (%d consecutive outer iterations "
                              "with no improving step)\n",stuck);
    }
    if(converged){ ++k; break; }
    ++k;
  }
  if(final_lambda_out) *final_lambda_out = lam_cam;
  int cheir1=RFCheirality(p,s,dviol);
  std::printf("  RF: accepts=%d rejects=%d total_matvecs=%ld negcurv=%ld cand_evals=%ld "
              "inactive_obs %d -> %d stop=%s\n",
              n_accept,n_reject,st.matvecs,st.negcurv,st.cand_evals,cheir0,cheir1,stop_reason);
  // C7: released by ~MFDeviceScratch, on the throwing path as well.
  CsvClose();
  return log;
}

}  // namespace rigfisheye
