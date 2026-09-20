// mfree_cpu.h — CPU/OpenMP port of the champion matrix-free multi-shift-CG
// bundle adjuster (SolveMFreeShiftedCG<9>, unshared intrinsics, fp64).
//
// PURPOSE: an algorithm-level comparison against CPU Ceres on the same
// hardware. Every GPU-vs-CPU number so far confounds algorithm with silicon;
// this removes the confound. It is a PORT, not a reimplementation: the LM
// policy (multi-shift grid incl. OCA_GRID_DOWN, zeta recurrence, checkpoint
// candidate menu, alpha grid, Eisenstat-Walker forcing, Steihaug truncation,
// inner retries with assembly reuse, tau ladder, lambda streak-unwind,
// early stopping) is cloned line-for-line from oca_cuda.cu so that, in exact
// arithmetic, the iterates are identical. The unit test
// (colmap/src/colmap/tools/mfree_cpu_test.cc) enforces trajectory parity
// against the GPU solver.
//
// SCOPE: BAL/pinhole-radial (f,k1,k2), CD=9 with refine_intrinsics=true.
// Shared-intrinsics reduction, CD=6, and fp32 fragments are NOT ported.
// Residual convention is BAL's: xp = -Px/Pz, dist = 1 + k1 r^2 + k2 r^4,
// residual = f*dist*xp - u, cost = 1/2 sum r^2  (matches KernelCost).
#pragma once

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <string>
#include <vector>

#ifdef _OPENMP
#include <omp.h>
#endif

namespace oca_cpu {

using Scalar = double;

struct Problem {
  int num_cameras = 0, num_points = 0, num_observations = 0;
  const int* camera_index = nullptr;
  const int* point_index = nullptr;
  const double* observations = nullptr;  // interleaved (u,v), pp removed
  // Optional FIXED per-camera projection models (Fuchsberg path). When set,
  // observations are RAW pixels, projections use COLMAP's +z convention, and
  // the f/k1/k2 state columns are frozen (zero Jacobian, masked retraction).
  // cam_model: 2=SIMPLE_RADIAL(f,cx,cy,k) 5=OPENCV_FISHEYE(fx,fy,cx,cy,k1..k4)
  const int* cam_model = nullptr;
  const double* cam_params = nullptr;  // [8*num_cameras]
};

struct State {  // same layout contract as oca::State
  double* rotations = nullptr;     // [9*ncam] row-major
  double* translations = nullptr;  // [3*ncam]
  double* points = nullptr;        // [3*npt]
  double* focal = nullptr;         // [ncam]
  double* k1 = nullptr;
  double* k2 = nullptr;
};

struct Options {
  int max_iterations = 60;
  double point_damping = 3e-3;
  double initial_lambda = 10.0;
  int max_inner_retries = 8;
  bool refine_k2 = true;
  double func_tolerance = 1e-6;
  int max_consecutive_failures = 3;
  std::vector<int> cg_checkpoints = {8, 16, 32, 64, 128};
  int num_shifts = 5;
  double ew_eta_max = 0.5;   // Eisenstat-Walker cap (GPU hardcodes 0.5)
  double intr_damp = 1.0;    // weight of the intrinsics prior (KernelDampIntr9)
  double lam_floor_rel = 1e-8;  // lam_floor = initial_lambda * this (GPU: 1e-8)
  // H7 experiment: let the point damping TRACK lam downward,
  // tau_k = min(point_damping, max(lam_k, tau_track_floor)), restoring the
  // joint (cam+point) damping decay of textbook LM while staying constant
  // across the shift menu inside each outer iteration (the shift-family
  // constraint is per-solve, not per-run).
  bool tau_track_lambda = false;
  double tau_track_floor = 1e-9;
  bool use_alpha = true;     // the 0.7/1.4 block-rescale grid
  // H2b probe: among IMPROVING candidates pick the smallest-step one instead
  // of the lowest-cost one (trust-region-flavoured selection vs greedy).
  bool conservative_select = false;
  // rho-gated lambda control (Ceres-style trust region): selection stays
  // greedy min-cost, but lambda updates from rho = actual/predicted reduction
  // of the CHOSEN candidate. pred comes free from CG scalars:
  // phi drops 0.5*alpha_i*|r_i|^2 per iteration, and |r_i^sigma|^2 =
  // zeta_i^2 |r_i|^2, so every shift's model reduction accumulates from
  // quantities the zeta recurrence already computes.
  bool rho_lambda = false;
  bool verbose = false;
  int num_threads = 0;  // 0 = omp default
  // IRLS robust kernel (adopted from the NLCG benchmark's finding: the
  // robustness win is the kernel's, not the optimizer's). cost = 0.5*rho(|r|^2)
  // and each observation's residual+Jacobian is scaled by sqrt(rho'(|r|^2)) at
  // assembly, which makes the whole two-block machinery the weighted-GN system.
  int robust_kernel = 0;      // 0 l2, 1 huber, 2 cauchy, 3 student-t (adaptive scale)
  double robust_scale2 = 0.0; // delta^2 (huber) or c^2 (cauchy) or nu*sigma0^2 (t; 0 = auto-init), px^2
  double robust_nu = 4.0;     // t kernel: degrees of freedom
  // ---- inner linear solver on the reduced camera system ----
  // 0 = multi-shift CG (default, the shipped solver)
  // 1 = PoBA-style power series: block-Jacobi preconditioned Richardson,
  //     run PER SHIFT (no shared-sweep economy; see benchmark notes)
  // 3 = LSMR on the exact rectangular factor of S (Golub-Kahan), with the
  //     WHOLE lambda menu from ONE bidiagonalization (damped-LSMR recurrences;
  //     the uniform camera damping after point elimination makes this exact)
  // 4 = randomized Kaczmarz row-action on the damped LS rows (single lambda,
  //     center shift only; robustness strawman)
  int inner_solver = 0;
  // Variable-dimension sketching (RandNLA): observation ROW-SAMPLING, redrawn
  // once per OUTER iteration (fixed within the sweep so the shift menu applies
  // to one consistent sketched operator; per-inner-step sketch-and-project is
  // structurally incompatible with shifted recurrences). p grows toward 1 as
  // LM converges: p_k = min(1, p0*growth^k). 0 = off. Unbiased via 1/sqrt(p).
  double sketch_p0 = 0.0;
  double sketch_growth = 1.6;
  // Tie f,k1,k2 across all cameras (single moving camera): candidate steps are
  // projected onto the shared-intrinsics subspace before scoring/retraction.
  bool shared_intr = false;
};

// rho and weight for the IRLS kernels (s = |r|^2)
inline double RobustRho(int k, double a2, double s) {
  if (k == 1) return s <= a2 ? s : 2.0*std::sqrt(a2*s) - a2;
  if (k == 2) return a2*std::log1p(s/a2);
  if (k == 3) return a2*std::log1p(s/a2);   // Student's t: Cauchy form, a2 = nu*sigma^2 (adaptive)
  return s;
}
inline double RobustW(int k, double a2, double s) {
  if (k == 1) return s <= a2 ? 1.0 : std::sqrt(a2/s);
  if (k == 2) return 1.0/(1.0 + s/a2);
  if (k == 3) return 1.0/(1.0 + s/a2);
  return 1.0;
}

struct Result {
  bool success = false;
  int iterations = 0;
  double initial_cost = 0.0, final_cost = 0.0;
  std::vector<double> cost_per_iteration;
  double final_lambda = 0.0;
  long total_matvecs = 0, cand_evals = 0;
  int accepts = 0, rejects = 0;
  std::string message;
};

// ---------------------------------------------------------------- small math
inline void ExpSO3(const Scalar* w, Scalar* R) {
  const Scalar t2 = w[0]*w[0] + w[1]*w[1] + w[2]*w[2];
  const Scalar t = std::sqrt(t2);
  Scalar a, b;
  if (t < 1e-8) { a = 1.0 - t2/6.0; b = 0.5 - t2/24.0; }
  else          { a = std::sin(t)/t; b = (1.0 - std::cos(t))/t2; }
  const Scalar wx = w[0], wy = w[1], wz = w[2];
  R[0] = 1 + b*(-wz*wz - wy*wy); R[1] = -a*wz + b*wx*wy; R[2] =  a*wy + b*wx*wz;
  R[3] =  a*wz + b*wx*wy; R[4] = 1 + b*(-wz*wz - wx*wx); R[5] = -a*wx + b*wy*wz;
  R[6] = -a*wy + b*wx*wz; R[7] =  a*wx + b*wy*wz; R[8] = 1 + b*(-wy*wy - wx*wx);
}
inline void Mat3Mul(const Scalar* A, const Scalar* B, Scalar* C) {
  for (int r = 0; r < 3; ++r)
    for (int c = 0; c < 3; ++c)
      C[3*r+c] = A[3*r]*B[c] + A[3*r+1]*B[3+c] + A[3*r+2]*B[6+c];
}
// 3x3 SPD Cholesky, lower L (6 packed: L00,L10,L11,L20,L21,L22). false if not PD.
inline bool Chol3(const Scalar A[6], Scalar L[6]) {
  // A packed sym: a00,a01,a11,a02,a12,a22
  const Scalar a00=A[0], a01=A[1], a11=A[2], a02=A[3], a12=A[4], a22=A[5];
  if (!(a00 > 0)) return false;
  const Scalar l00 = std::sqrt(a00);
  const Scalar l10 = a01/l00, l20 = a02/l00;
  const Scalar d1 = a11 - l10*l10;
  if (!(d1 > 0)) return false;
  const Scalar l11 = std::sqrt(d1);
  const Scalar l21 = (a12 - l20*l10)/l11;
  const Scalar d2 = a22 - l20*l20 - l21*l21;
  if (!(d2 > 0)) return false;
  L[0]=l00; L[1]=l10; L[2]=l11; L[3]=l20; L[4]=l21; L[5]=std::sqrt(d2);
  return true;
}
inline void CholSolve3(const Scalar L[6], const Scalar b[3], Scalar x[3]) {
  // forward L y = b
  const Scalar y0 = b[0]/L[0];
  const Scalar y1 = (b[1] - L[1]*y0)/L[2];
  const Scalar y2 = (b[2] - L[3]*y0 - L[4]*y1)/L[5];
  // back L^T x = y
  x[2] = y2/L[5];
  x[1] = (y1 - L[4]*x[2])/L[2];
  x[0] = (y0 - L[1]*x[1] - L[3]*x[2])/L[0];
}

// -------------------------------------------------- residual + 12-col Jacobian
// Column order matches the GPU layout: [w0 w1 w2 | t0 t1 t2 | f k1 k2] + [X0 X1 X2].
// Retraction is R <- exp(w) R with additive t, so P = exp(w)(R X) + t and
// dP/dw_k at w=0 is e_k x (R X): the cross product with the ROTATED point,
// before translation. FD-validated by the unit test.
inline void ResidualAndJacobian(const Scalar* R, const Scalar* t, const Scalar* X,
                                Scalar f, Scalar k1, Scalar k2, Scalar k2mask,
                                const Scalar* uv, Scalar res[2],
                                Scalar gc[2][9], Scalar gp[2][3]) {
  const Scalar RX0 = R[0]*X[0]+R[1]*X[1]+R[2]*X[2];
  const Scalar RX1 = R[3]*X[0]+R[4]*X[1]+R[5]*X[2];
  const Scalar RX2 = R[6]*X[0]+R[7]*X[1]+R[8]*X[2];
  const Scalar Px = RX0 + t[0], Py = RX1 + t[1], Pz = RX2 + t[2];
  const Scalar iz = 1.0/Pz;
  const Scalar xp = -Px*iz, yp = -Py*iz;
  const Scalar r2 = xp*xp + yp*yp;
  const Scalar dist = 1.0 + k1*r2 + k2*r2*r2;
  const Scalar g = k1 + 2.0*k2*r2;          // d(dist)/d(r2)
  res[0] = f*dist*xp - uv[0];
  res[1] = f*dist*yp - uv[1];
  // du/dxp etc.
  const Scalar du_dxp = f*(dist + 2.0*xp*xp*g);
  const Scalar du_dyp = f*(2.0*xp*yp*g);
  const Scalar dv_dxp = du_dyp;
  const Scalar dv_dyp = f*(dist + 2.0*yp*yp*g);
  // dxp/dP, dyp/dP
  const Scalar dxp_dP[3] = {-iz, 0.0,  Px*iz*iz};
  const Scalar dyp_dP[3] = {0.0, -iz,  Py*iz*iz};
  // dP/d(param): w_k -> e_k x RX; t -> I; X -> R columns.
  const Scalar dP_dw[3][3] = {  // column k = e_k x RX
    {0.0,   RX2, -RX1},   // row i, col k:  dP_i/dw_k = (e_k x RX)_i
    {-RX2,  0.0,  RX0},
    { RX1, -RX0,  0.0}};
  // dP_dw[i][k] = d P_i / d w_k = (e_k x RX)_i
  for (int k = 0; k < 3; ++k) {
    const Scalar dPx = dP_dw[0][k], dPy = dP_dw[1][k], dPz = dP_dw[2][k];
    const Scalar dxp = dxp_dP[0]*dPx + dxp_dP[2]*dPz;
    const Scalar dyp = dyp_dP[1]*dPy + dyp_dP[2]*dPz;
    gc[0][k] = du_dxp*dxp + du_dyp*dyp;
    gc[1][k] = dv_dxp*dxp + dv_dyp*dyp;
  }
  for (int k = 0; k < 3; ++k) {
    const Scalar dPx = (k==0), dPy = (k==1), dPz = (k==2);
    const Scalar dxp = dxp_dP[0]*dPx + dxp_dP[2]*dPz;
    const Scalar dyp = dyp_dP[1]*dPy + dyp_dP[2]*dPz;
    gc[0][3+k] = du_dxp*dxp + du_dyp*dyp;
    gc[1][3+k] = dv_dxp*dxp + dv_dyp*dyp;
  }
  gc[0][6] = dist*xp;        gc[1][6] = dist*yp;          // f
  gc[0][7] = f*r2*xp;        gc[1][7] = f*r2*yp;          // k1
  gc[0][8] = f*r2*r2*xp*k2mask; gc[1][8] = f*r2*r2*yp*k2mask;  // k2 (masked)
  for (int k = 0; k < 3; ++k) {   // dP/dX_k = R column k
    const Scalar dPx = R[k], dPy = R[3+k], dPz = R[6+k];
    const Scalar dxp = dxp_dP[0]*dPx + dxp_dP[2]*dPz;
    const Scalar dyp = dyp_dP[1]*dPy + dyp_dP[2]*dPz;
    gp[0][k] = du_dxp*dxp + du_dyp*dyp;
    gp[1][k] = dv_dxp*dxp + dv_dyp*dyp;
  }
}

// ---------------------------------------- FIXED-intrinsics models (Fuchsberg)
// COLMAP convention: P = R X + t with Pz > 0 in front, xp = +Px/Pz. Intrinsics
// columns gc[.][6..8] stay zero (frozen). SIMPLE_RADIAL and OPENCV_FISHEYE.
inline void FixedDistort(int model, const Scalar* par, Scalar xp, Scalar yp,
                         Scalar* u, Scalar* v,
                         Scalar* du_dxp, Scalar* du_dyp,
                         Scalar* dv_dxp, Scalar* dv_dyp) {
  if (model == 2) {  // SIMPLE_RADIAL: f,cx,cy,k
    const Scalar f = par[0], cx = par[1], cy = par[2], k = par[3];
    const Scalar r2 = xp*xp + yp*yp;
    const Scalar dist = 1.0 + k*r2;
    *u = f*dist*xp + cx; *v = f*dist*yp + cy;
    *du_dxp = f*(dist + 2.0*xp*xp*k); *du_dyp = f*(2.0*xp*yp*k);
    *dv_dxp = *du_dyp;                *dv_dyp = f*(dist + 2.0*yp*yp*k);
    return;
  }
  // OPENCV_FISHEYE: fx,fy,cx,cy,k1,k2,k3,k4. u = fx*s*xp+cx with
  // s = D(theta)/r, theta = atan(r), D = theta*(1+k1 t2+k2 t2^2+k3 t2^3+k4 t2^4).
  const Scalar fx = par[0], fy = par[1], cx = par[2], cy = par[3];
  const Scalar k1 = par[4], k2 = par[5], k3 = par[6], k4 = par[7];
  const Scalar r2 = xp*xp + yp*yp;
  if (r2 < 1e-16) {  // at the center s->1, ds/dr->0
    *u = fx*xp + cx; *v = fy*yp + cy;
    *du_dxp = fx; *du_dyp = 0.0; *dv_dxp = 0.0; *dv_dyp = fy;
    return;
  }
  const Scalar r = std::sqrt(r2);
  const Scalar th = std::atan(r), t2 = th*th;
  const Scalar D  = th*(1.0 + t2*(k1 + t2*(k2 + t2*(k3 + t2*k4))));
  const Scalar dD = 1.0 + t2*(3.0*k1 + t2*(5.0*k2 + t2*(7.0*k3 + t2*9.0*k4)));
  const Scalar s = D/r;
  const Scalar dth_dr = 1.0/(1.0 + r2);
  const Scalar ds_dr = (dD*dth_dr*r - D)/r2;    // d(D/r)/dr
  const Scalar a = ds_dr/r;                     // ds/dr * (1/r) for chain via xp,yp
  *u = fx*s*xp + cx; *v = fy*s*yp + cy;
  *du_dxp = fx*(s + xp*xp*a); *du_dyp = fx*(xp*yp*a);
  *dv_dxp = fy*(xp*yp*a);     *dv_dyp = fy*(s + yp*yp*a);
}

inline void ResidualAndJacobianFixed(const Scalar* R, const Scalar* t,
                                     const Scalar* X, int model,
                                     const Scalar* par, const Scalar* uv,
                                     Scalar res[2], Scalar gc[2][9],
                                     Scalar gp[2][3]) {
  const Scalar RX0 = R[0]*X[0]+R[1]*X[1]+R[2]*X[2];
  const Scalar RX1 = R[3]*X[0]+R[4]*X[1]+R[5]*X[2];
  const Scalar RX2 = R[6]*X[0]+R[7]*X[1]+R[8]*X[2];
  const Scalar Px = RX0 + t[0], Py = RX1 + t[1], Pz = RX2 + t[2];
  const Scalar iz = 1.0/Pz;
  const Scalar xp = Px*iz, yp = Py*iz;          // +z convention (no BAL flip)
  Scalar u, v, du_dxp, du_dyp, dv_dxp, dv_dyp;
  FixedDistort(model, par, xp, yp, &u, &v, &du_dxp, &du_dyp, &dv_dxp, &dv_dyp);
  res[0] = u - uv[0];
  res[1] = v - uv[1];
  const Scalar dxp_dP[3] = { iz, 0.0, -Px*iz*iz};
  const Scalar dyp_dP[3] = {0.0,  iz, -Py*iz*iz};
  const Scalar dP_dw[3][3] = {
    {0.0,   RX2, -RX1},
    {-RX2,  0.0,  RX0},
    { RX1, -RX0,  0.0}};
  for (int k = 0; k < 3; ++k) {
    const Scalar dPx = dP_dw[0][k], dPy = dP_dw[1][k], dPz = dP_dw[2][k];
    const Scalar dxp = dxp_dP[0]*dPx + dxp_dP[2]*dPz;
    const Scalar dyp = dyp_dP[1]*dPy + dyp_dP[2]*dPz;
    gc[0][k] = du_dxp*dxp + du_dyp*dyp;
    gc[1][k] = dv_dxp*dxp + dv_dyp*dyp;
  }
  for (int k = 0; k < 3; ++k) {
    const Scalar dPx = (k==0), dPy = (k==1), dPz = (k==2);
    const Scalar dxp = dxp_dP[0]*dPx + dxp_dP[2]*dPz;
    const Scalar dyp = dyp_dP[1]*dPy + dyp_dP[2]*dPz;
    gc[0][3+k] = du_dxp*dxp + du_dyp*dyp;
    gc[1][3+k] = dv_dxp*dxp + dv_dyp*dyp;
  }
  gc[0][6]=gc[0][7]=gc[0][8]=0.0;  // intrinsics frozen
  gc[1][6]=gc[1][7]=gc[1][8]=0.0;
  for (int k = 0; k < 3; ++k) {
    const Scalar dPx = R[k], dPy = R[3+k], dPz = R[6+k];
    const Scalar dxp = dxp_dP[0]*dPx + dxp_dP[2]*dPz;
    const Scalar dyp = dyp_dP[1]*dPy + dyp_dP[2]*dPz;
    gp[0][k] = du_dxp*dxp + du_dyp*dyp;
    gp[1][k] = dv_dxp*dxp + dv_dyp*dyp;
  }
}

// ------------------------------------------------------------------ the solver
class Solver {
 public:
  Solver(const Problem& p, const Options& o) : p_(p), o_(o) {
    ncam_ = p.num_cameras; npt_ = p.num_points; nobs_ = p.num_observations;
    n_c_ = 9*ncam_; n_p_ = 3*npt_; n_ = n_c_ + n_p_;
#ifdef _OPENMP
    nthreads_ = o_.num_threads > 0 ? o_.num_threads : omp_get_max_threads();
#else
    nthreads_ = 1;
#endif
    // point -> obs adjacency (for the point factor and diagnostics)
    pt_off_.assign(npt_+1, 0);
    for (int o2 = 0; o2 < nobs_; ++o2) pt_off_[p.point_index[o2]+1]++;
    for (int q = 0; q < npt_; ++q) pt_off_[q+1] += pt_off_[q];
    pt_list_.resize(nobs_);
    { std::vector<int> cur(pt_off_.begin(), pt_off_.end()-1);
      for (int o2 = 0; o2 < nobs_; ++o2) pt_list_[cur[p.point_index[o2]]++] = o2; }
    // cam -> obs adjacency (for the Hcc/Pass2-style camera-major loops)
    cam_off_.assign(ncam_+1, 0);
    for (int o2 = 0; o2 < nobs_; ++o2) cam_off_[p.camera_index[o2]+1]++;
    for (int c = 0; c < ncam_; ++c) cam_off_[c+1] += cam_off_[c];
    cam_list_.resize(nobs_);
    { std::vector<int> cur(cam_off_.begin(), cam_off_.end()-1);
      for (int o2 = 0; o2 < nobs_; ++o2) cam_list_[cur[p.camera_index[o2]]++] = o2; }
    res_.resize(2*(size_t)nobs_); gc_.resize(18*(size_t)nobs_); gp_.resize(6*(size_t)nobs_);
    tacc2_.resize(n_p_); uu2_.resize(n_p_); scaled_.resize(n_c_);
    Hcc_.resize(81*(size_t)ncam_); bc_.resize(n_c_); bp_.resize(n_p_);
    Vsym_.resize(6*(size_t)npt_); Cdiag_.resize(3*(size_t)npt_);
    Lp_.resize(6*(size_t)npt_); ok_.resize(npt_);
    r2acc_.resize(ncam_); obscnt_.resize(ncam_);
    qd_.resize(3*(size_t)npt_);
    cam_work_ = nobs_;   // camera-major loops sweep all obs via cam_list_
    pt_work_ = nobs_;    // point-major loops likewise
  }

  Scalar ComputeCost(const std::vector<Scalar>& R, const std::vector<Scalar>& t,
                     const std::vector<Scalar>& X, const std::vector<Scalar>& f,
                     const std::vector<Scalar>& k1, const std::vector<Scalar>& k2) const {
    Scalar total = 0.0;
#ifdef _OPENMP
#pragma omp parallel for reduction(+:total) schedule(static) num_threads(TF(nobs_))
#endif
    for (int o2 = 0; o2 < nobs_; ++o2) {
      const int c = p_.camera_index[o2], q = p_.point_index[o2];
      const Scalar* Rc = &R[9*c]; const Scalar* Xp = &X[3*q];
      const Scalar Px = Rc[0]*Xp[0]+Rc[1]*Xp[1]+Rc[2]*Xp[2] + t[3*c];
      const Scalar Py = Rc[3]*Xp[0]+Rc[4]*Xp[1]+Rc[5]*Xp[2] + t[3*c+1];
      const Scalar Pz = Rc[6]*Xp[0]+Rc[7]*Xp[1]+Rc[8]*Xp[2] + t[3*c+2];
      Scalar rx, ry;
      if (p_.cam_model) {
        const Scalar xp = Px/Pz, yp = Py/Pz;
        Scalar u, v, j0, j1, j2, j3;
        FixedDistort(p_.cam_model[c], &p_.cam_params[8*c], xp, yp,
                     &u, &v, &j0, &j1, &j2, &j3);
        rx = u - p_.observations[2*o2];
        ry = v - p_.observations[2*o2+1];
      } else {
        const Scalar xp = -Px/Pz, yp = -Py/Pz;
        const Scalar r2 = xp*xp + yp*yp;
        const Scalar dist = 1.0 + k1[c]*r2 + k2[c]*r2*r2;
        rx = f[c]*dist*xp - p_.observations[2*o2];
        ry = f[c]*dist*yp - p_.observations[2*o2+1];
      }
      total += 0.5*RobustRho(o_.robust_kernel, rk_a2_, rx*rx + ry*ry);
    }
    return total;
  }

  Result Solve(State* st) {
    Result out;
    rk_a2_ = o_.robust_scale2;   // t kernel: 0 = auto-init below
    // working copies of the state (retraction writes into "new", accept swaps)
    R_.assign(st->rotations, st->rotations + 9*(size_t)ncam_);
    t_.assign(st->translations, st->translations + 3*(size_t)ncam_);
    X_.assign(st->points, st->points + 3*(size_t)npt_);
    f_.assign(st->focal, st->focal + ncam_);
    k1v_.assign(st->k1, st->k1 + ncam_);
    k2v_.assign(st->k2, st->k2 + ncam_);
    Rn_ = R_; tn_ = t_; Xn_ = X_; fn_ = f_; k1n_ = k1v_; k2n_ = k2v_;
    // The initial ComputeCost below needs a valid t-kernel scale already
    // (rho(a2=0) is NaN), so the auto-init/EM pass runs here, not only at
    // assembly time.
    UpdateTScale();

    const Scalar k2mask = o_.refine_k2 ? 1.0 : 0.0;
    const int L = o_.num_shifts;
    static const int grid_down_env = [](){
      const char* e = getenv("OCA_GRID_DOWN"); return e ? std::atoi(e) : 0; }();
    const int grid_down = std::min(std::max(grid_down_env, 0), L-1);
    static const bool lm_classic = getenv("OCA_LM_CLASSIC") != nullptr;
    // OCA_RHO_SHIFT: under rho mode, anchor the Nielsen update at the WINNING
    // shift's damping sigma_win = lam*10^(best_sh-grid_down) instead of the
    // pre-streak lambda. The accepted step solved (S+sigma_win)x=b, so
    // sigma_win is the damping the trust region actually used; discarding it
    // pins lambda at the floor and every outer re-pays a reject/escalation
    // search (326 rejects measured on final-4585 under plain rho).
    static const int rho_shift_down = [](){
      const char* e = getenv("OCA_RHO_SHIFT");
      return e ? std::max(1, std::atoi(e)) : 0; }();
    static const bool rho_shift = rho_shift_down > 0;
    // OCA_ALPHA_RHO: re-enable the alpha grid under rho mode with an
    // alpha-aware prediction pred(s) = s*b'd - s^2*(b'd - pred1) (exact for
    // the Schur-space quadratic under uniform scaling; one extra dot).
    static const bool alpha_rho = getenv("OCA_ALPHA_RHO") != nullptr;
    // OCA_GRIND_ETA=<v>: once the last accepted step's relative progress
    // drops below 1e-4 (the same boundary the rho gate uses), cap the
    // Eisenstat-Walker forcing tolerance at v so CG runs deep. In the grind
    // phase EW's |b|-ratio is ~1, eta pins at eta_max=0.5, and CG stops after
    // 1-16 iterations -- while the outer's fixed cost (assembly + candidate
    // scoring) dwarfs a matvec, so shallow sweeps waste the outer.
    static const Scalar grind_eta = [](){
      const char* e = getenv("OCA_GRIND_ETA"); return e ? (Scalar)atof(e) : (Scalar)0.0; }();
    // OCA_TAU_GRIND=<floor_rel>: in the grind phase (last_rel < 1e-4) let
    // the point damping TRACK lam downward, floored at floor_rel x the CLI
    // tau: tau_k = min(tau_cli, max(lam, tau_cli*floor_rel)). Outside the
    // grind phase tau stays at the CLI value, so the opening is untouched.
    // Mechanism: lam decays to its floor but tau never moves, so the endgame
    // point relaxation carries a permanent bias -- measured on ladybug-49
    // (tau 3e-3 -> 3e-5 lowers the 60-iter final by 0.83%, the size of the
    // entire deficit to Caspar there). The reject ladder still escalates
    // from the tracked base, so a bad decay self-corrects within the outer.
    static const Scalar tau_grind = [](){
      const char* e = getenv("OCA_TAU_GRIND"); return e ? (Scalar)atof(e) : (Scalar)0.0; }();
    // OCA_LAZY_SCORE: at intermediate CG checkpoints score only shift 0 and
    // the previous outer's winning shift; the full L-shift scan runs only at
    // the final stop (EW break / truncation / max depth). 82% of accepted
    // winners are shift 0 (measured across the 23-set trace archive), so the
    // 5-shift scan at every checkpoint is mostly fixed-cost waste: on
    // final-4585 candidate evaluation is ~25 ms each and the early outers
    // fire up to 5 checkpoints.
    static const bool lazy_score = getenv("OCA_LAZY_SCORE") != nullptr;

    Scalar cost = ComputeCost(R_, t_, X_, f_, k1v_, k2v_);
    out.initial_cost = cost;
    out.cost_per_iteration.push_back(cost);
    Scalar lam_cam = o_.initial_lambda, lam_floor = o_.initial_lambda*o_.lam_floor_rel;
    Scalar lam_pre_streak = lam_cam;
    Scalar tau_base = o_.point_damping, tau_eff = tau_base;
    Scalar prev_bnorm = -1.0, prev_cost = cost;
    Scalar last_rel = 1.0;   // relative progress of the last ACCEPTED outer
    int last_win_sh = 0;     // OCA_LAZY_SCORE: previous outer's winning shift

    int rej_streak = 0, stuck = 0, retries = 0;
    bool converged = false, need_assembly = true;
    std::vector<int> ckpts = o_.cg_checkpoints;
    if (ckpts.empty()) ckpts.push_back(o_.max_iterations);
    const int maxck = *std::max_element(ckpts.begin(), ckpts.end());

    std::vector<Scalar> bprime(n_c_), E(n_c_), dk(n_c_);
    std::vector<Scalar> r(n_c_), pv(n_c_), Ap(n_c_), w(n_c_);
    std::vector<std::vector<Scalar>> xs(L, std::vector<Scalar>(n_c_)),
                                     ps(L, std::vector<Scalar>(n_c_));
    std::vector<Scalar> xc_un(n_c_), tacc(n_p_), uu(n_p_), xpv(n_p_);
    std::vector<Scalar> dfull(n_), d_best(n_);

    for (int k = 0; k < o_.max_iterations;) {
      prev_iter_cost_ = cost;
      outer_k_ = k;
      if (o_.sketch_p0 > 0.0)
        sk_p_ = std::min(1.0, o_.sketch_p0*std::pow(o_.sketch_growth, (double)k));
      if (need_assembly) Assemble(k2mask);
      // tau ladder (tau_persist=false in the core-API config being cloned)
      Scalar tau_base_k = tau_base;
      if (tau_grind > 0.0 && last_rel < 1e-4)
        tau_base_k = std::min(tau_base, std::max(lam_cam, tau_base*tau_grind));
      if (o_.tau_track_lambda)
        tau_base_k = std::min(tau_base, std::max(lam_cam, (Scalar)o_.tau_track_floor));
      tau_eff = tau_base_k;
      if (rej_streak > 0)
        tau_eff = tau_base_k*std::pow(10.0, (double)std::min(rej_streak, 12));
      if (!PointFactor(tau_eff)) { /* ok_ flags handled per point */ }
      // b' = bc - H_cp V^-1 bp ; equilibrate
      VinvApply(bp_.data(), uu.data());
      RhsPrime(uu.data(), bprime.data());
      BuildEquil(dk.data(), E.data());
      for (int i = 0; i < n_c_; ++i) bprime[i] *= E[i];

      // ---- candidates ----
      Scalar best_cost = cost; int best_sh = -1, best_ck = -1; bool have = false;
      best_sn_ = std::numeric_limits<Scalar>::infinity();
      std::vector<Scalar> cbest_sh(L, std::numeric_limits<Scalar>::infinity());
      std::vector<Scalar> preds(L, 0.0);           // running model reduction per shift
      std::fill(d_best.begin(), d_best.end(), 0.0);
      Scalar pred_best = 0.0;
      Scalar bpd_best = 0.0;                        // b'^T x of the winning candidate (scaled space)
      auto Score = [&](const std::vector<Scalar>& x_scaled, int sh, int ck){
        for (int i = 0; i < n_c_; ++i) xc_un[i] = x_scaled[i]*E[i];
        Pass1(xc_un.data(), tacc.data());
        BackSub(tacc.data(), xpv.data());        // xpv = V^-1 (bp - tacc)
        for (int i = 0; i < n_c_; ++i) dfull[i] = -xc_un[i];
        for (int i = 0; i < n_p_; ++i) dfull[n_c_+i] = -xpv[i];
        if (o_.shared_intr && !p_.cam_model) {
          // single-moving-camera projection: tie the intrinsics step across
          // cameras (feasible-set projection; scored at its true cost)
          for (int j = 6; j < 9; ++j) {
            Scalar m = 0; for (int c = 0; c < ncam_; ++c) m += dfull[9*c+j];
            m /= std::max(1, ncam_);
            for (int c = 0; c < ncam_; ++c) dfull[9*c+j] = m;
          }
        }
        Retract(dfull.data());
        const Scalar c = ComputeCost(Rn_, tn_, Xn_, fn_, k1n_, k2n_);
        if (getenv("MF_DEBUG")) {
          Scalar nx = 0, np2 = 0;
          for (int i = 0; i < n_c_; ++i) nx += xc_un[i]*xc_un[i];
          for (int i = 0; i < n_p_; ++i) np2 += xpv[i]*xpv[i];
          std::printf("      [dbg] shift=%d ckpt=%d  |x_c|=%.6e |x_p|=%.6e  cand_cost=%.10e  (cur=%.10e)%s\n",
                      sh, ck, std::sqrt(nx), std::sqrt(np2), c, cost,
                      std::isfinite(c) ? "" : "  <-- NON-FINITE");
        }
        ++out.cand_evals;
        if (sh >= 0 && sh < L && c < cbest_sh[sh]) cbest_sh[sh] = c;
        bool take;
        if (o_.conservative_select) {
          // improving at all? then prefer the shortest improving step so far.
          Scalar sn = 0; for (int i = 0; i < n_; ++i) sn += dfull[i]*dfull[i];
          take = (c < cost) && (!have || sn < best_sn_);
          if (take) best_sn_ = sn;
          if (c < best_cost) best_cost = std::min(best_cost, c);  // book-keeping
          if (take) best_cost = c;
        } else {
          take = (c < best_cost);
        }
        if (take) { best_cost = c; best_sh = sh; best_ck = ck; have = true;
                    d_best = dfull;
                    pred_best = (sh >= 0 && sh < L) ? preds[sh] : 0.0;
                    if (alpha_rho) {
                      Scalar bd = 0;
                      for (int i = 0; i < n_c_; ++i) bd += bprime[i]*x_scaled[i];
                      bpd_best = bd;
                    } }
      };

      // ---- inner linear solver on the reduced camera system ----
      std::vector<Scalar> shifts(L);
      for (int l = 0; l < L; ++l) shifts[l] = lam_cam*std::pow(10.0, (double)(l - grid_down));
      int cg_it = 0;
      if (o_.inner_solver == 1) {
        cg_it = InnerPoBA(shifts, bprime, E, ckpts, maxck, Score, xs);
      } else if (o_.inner_solver == 3) {
        cg_it = InnerLSMR(shifts, bprime, E, ckpts, maxck, Score, xs);
      } else if (o_.inner_solver == 4) {
        cg_it = InnerRK(shifts, bprime, E, ckpts, maxck, Score, dfull);
      } else {
      // ---- multi-shift CG, seed at the smallest shift ----
      for (int l = 0; l < L; ++l) { std::fill(xs[l].begin(), xs[l].end(), 0.0); ps[l] = bprime; }
      std::vector<Scalar> zeta(L,1.0), zprev(L,1.0), znext(L,1.0), als(L,0.0), bes(L,0.0);
      r = bprime; pv = bprime;
      Scalar nb = Nrm2(bprime), rr = Dot(r, r);
      if (getenv("MF_DEBUG")) {
        Scalar nbc = 0, nbp = 0;
        for (int i = 0; i < n_c_; ++i) nbc += bc_[i]*bc_[i];
        for (int i = 0; i < n_p_; ++i) nbp += bp_[i]*bp_[i];
        std::printf("    [dbg] |b_c|=%.6e |b_p|=%.6e |b'|=%.6e  lam=%.3e\n",
                    std::sqrt(nbc), std::sqrt(nbp), nb, lam_cam);
      }
      Scalar eta = o_.ew_eta_max;
      if (prev_bnorm > 0.0) eta = std::min(o_.ew_eta_max, 0.9*(nb*nb)/(prev_bnorm*prev_bnorm));
      prev_bnorm = nb;
      if (grind_eta > 0.0 && last_rel < 1e-4) eta = std::min(eta, grind_eta);
      Scalar al_prev = 1.0, be_prev = 0.0; size_t ci = 0; bool trunc = false;
      for (cg_it = 0; cg_it < maxck; ++cg_it) {
        KvS(pv.data(), Ap.data(), E.data());
        for (int i = 0; i < n_c_; ++i) Ap[i] += shifts[0]*pv[i];
        const Scalar pAp = Dot(pv, Ap), pp = Dot(pv, pv);
        if (!(pAp > 1e-14*pp)) { trunc = true; break; }        // Steihaug-Toint
        const Scalar al = rr/pAp;
        preds[0] += 0.5*al*rr;
        for (int i = 0; i < n_c_; ++i) xs[0][i] += al*pv[i];
        for (int i = 0; i < n_c_; ++i) r[i] -= al*Ap[i];
        const Scalar rr_new = Dot(r, r);
        const Scalar be = rr_new/rr;
        for (int l = 1; l < L; ++l) {
          const Scalar sg = shifts[l] - shifts[0];
          const Scalar den = al*be_prev*(zprev[l]-zeta[l]) + zprev[l]*al_prev*(1.0+sg*al);
          znext[l] = (den != 0.0) ? (zeta[l]*zprev[l]*al_prev)/den : 0.0;
          if (!std::isfinite(znext[l])) znext[l] = 0.0;
          als[l] = al*znext[l]/zeta[l];
          bes[l] = be*(znext[l]/zeta[l])*(znext[l]/zeta[l]);
          preds[l] += 0.5*als[l]*zeta[l]*zeta[l]*rr;
          for (int i = 0; i < n_c_; ++i) xs[l][i] += als[l]*ps[l][i];
        }
        for (int l = 1; l < L; ++l) {
          for (int i = 0; i < n_c_; ++i) ps[l][i] = bes[l]*ps[l][i] + znext[l]*r[i];
          zprev[l] = zeta[l]; zeta[l] = znext[l];
        }
        al_prev = al; be_prev = be;
        for (int i = 0; i < n_c_; ++i) pv[i] = r[i] + be*pv[i];
        rr = rr_new;
        while (ci < ckpts.size() && cg_it+1 == ckpts[ci]) {
          if (lazy_score) {
            Score(xs[0], 0, cg_it+1);
            if (last_win_sh > 0 && last_win_sh < L)
              Score(xs[last_win_sh], last_win_sh, cg_it+1);
          } else {
            for (int l = 0; l < L; ++l) Score(xs[l], l, cg_it+1);
          }
          ++ci;
        }
        if (std::sqrt(rr_new) <= eta*nb) break;               // Eisenstat-Walker
      }
      if (trunc)      for (int l = 0; l < L; ++l) Score(xs[l], l, cg_it);
      else if (ci==0) for (int l = 0; l < L; ++l) Score(xs[l], l, cg_it);
      }  // end inner_solver dispatch

      // ---- alpha grid: scales the LIVE d_best, so improvements compound
      // across combos (verbatim GPU behaviour -- a saved-copy variant is a
      // different algorithm and diverged 40% at venice-52 iteration 1).
      if (have && o_.use_alpha && (!o_.rho_lambda || alpha_rho)) {
        static const Scalar as[3] = {0.7, 1.0, 1.4};
        // Under rho mode the winning combo must carry a matching prediction:
        // for a step whose camera half is scaled by cumulative s, the
        // Schur-space quadratic gives pred(s) = s*b'd - s^2*(b'd - pred1).
        // s compounds across winning combos exactly like the step itself.
        const Scalar bpd0 = bpd_best, pred1 = pred_best;
        Scalar s_cum = 1.0;
        for (int a1 = 0; a1 < 3; ++a1) for (int a2 = 0; a2 < 3; ++a2) {
          if (as[a1] == 1.0 && as[a2] == 1.0) continue;
          for (int i = 0; i < n_c_; ++i) dfull[i] = d_best[i]*as[a1];
          for (int i = 0; i < n_p_; ++i) dfull[n_c_+i] = d_best[n_c_+i]*as[a2];
          Retract(dfull.data());
          const Scalar c = ComputeCost(Rn_, tn_, Xn_, fn_, k1n_, k2n_);
          if (c < best_cost) { best_cost = c; d_best = dfull;
            if (o_.rho_lambda) {
              s_cum *= as[a1];
              pred_best = s_cum*bpd0 - s_cum*s_cum*(bpd0 - pred1);
            } }
        }
      }

      // ---- accept / reject (grid-down recentre + CD9 streak unwind) ----
      bool accepted = false;
      if (have && best_cost < cost) {
        Retract(d_best.data());
        R_.swap(Rn_); t_.swap(tn_); X_.swap(Xn_); f_.swap(fn_); k1v_.swap(k1n_); k2v_.swap(k2n_);
        last_rel = (prev_iter_cost_ - best_cost)
                   / std::max(prev_iter_cost_, (Scalar)1e-300);
        if (best_sh >= 0) last_win_sh = best_sh;
        cost = best_cost;
        if (o_.rho_lambda) {
          const Scalar act = /* cost before this accept */ out.cost_per_iteration.size()
                             ? (prev_iter_cost_ - best_cost) : 0.0;
          const Scalar rho = (pred_best > 1e-300) ? act/pred_best : 1.0;
          // Ceres TR update: lam *= max(1/3, 1-(2rho-1)^3); poor rho RAISES lam
          const Scalar f3 = 2.0*rho - 1.0;
          Scalar fac = 1.0 - f3*f3*f3;
          if (fac < 1.0/3.0) fac = 1.0/3.0;
          if (rho < 0.25) fac = 2.0;
          // rho trustworthy only near the quadratic regime: while the accepted
          // step still moves cost >1e-4 relative, decay at least as fast as
          // greedy; Nielsen governs only the grind phase. Apply fac to the
          // PRE-STREAK lambda (the legacy unwind below), else reject x10s bank
          // permanently -- the lam=inf mechanism seen on final-4585.
          const Scalar rel = act / std::max(prev_iter_cost_, (Scalar)1e-300);
          if (rel > 1e-4) fac = std::min(fac, (Scalar)0.5);
          Scalar base = (rej_streak > 0 && !lm_classic) ? lam_pre_streak : lam_cam;
          // OCA_RHO_SHIFT: the accepted step was solved at sigma_win; make
          // that the anchor Nielsen updates from, so the menu's damping
          // information survives into the next outer.
          if (rho_shift && best_sh >= 0 && rej_streak == 0) {
            // Anchor only on CLEAN accepts. A contested accept's lam carries
            // the reject streak's x10 escalations, which are a joint
            // (lambda,tau) search device, not damping information -- banking
            // them froze the final-4585 grind at an elevated lambda (48
            // outers buying 0.3%, final +1.9% worse). Clean accepts keep the
            // full downward anchor (the opening win: venice-52 it3 cost
            // 1.23e6 -> 5.0e5) with the upward move clamped to +1 decade.
            const int rel_sh = std::max(std::min(best_sh - grid_down, 1),
                                        -rho_shift_down);
            base = lam_cam*std::pow((Scalar)10.0, (Scalar)rel_sh);
          }
          lam_cam = std::min(std::max(base*fac, lam_floor), (Scalar)1e8);
        } else if (grid_down > 0 && best_sh >= 0) {
          lam_cam = std::max(lam_cam*std::pow(10.0, (double)(best_sh-grid_down)), lam_floor);
          if (best_sh == grid_down) lam_cam = std::max(lam_cam*0.5, lam_floor);
        } else if (rej_streak > 0 && !lm_classic) {
          lam_cam = std::max(lam_pre_streak*0.5, lam_floor);
        } else {
          lam_cam = std::max(lam_cam*0.5, lam_floor);
        }
        accepted = true; ++out.accepts; rej_streak = 0;
      } else {
        if (rej_streak == 0) lam_pre_streak = lam_cam;
        lam_cam *= 10.0; ++out.rejects; ++rej_streak;
      }
      if (!accepted && retries < o_.max_inner_retries) {
        ++retries; need_assembly = false;
        if (o_.verbose)
          std::printf("  CPU it %3d  retry %d/%d  lam=%.3e tau_eff=%.3e\n",
                      k+1, retries, o_.max_inner_retries, lam_cam, tau_eff);
        continue;
      }
      retries = 0; need_assembly = true;
      out.cost_per_iteration.push_back(cost);
      if (accepted) {
        stuck = 0;
        if (o_.func_tolerance > 0 && prev_cost > 0 &&
            (prev_cost - cost) < o_.func_tolerance*prev_cost) converged = true;
        prev_cost = cost;
      } else if (o_.max_consecutive_failures > 0 && ++stuck >= o_.max_consecutive_failures) {
        converged = true;
      }
      if (o_.verbose)
        std::printf("  CPU it %3d cost=%.6e lam=%.3e cg_it=%d shift=%d ckpt=%d %s mv=%ld\n",
                    k+1, cost, lam_cam, cg_it, best_sh, best_ck,
                    accepted ? "acc" : "REJ", matvecs_);
      ++k;
      if (converged) break;
    }

    std::memcpy(st->rotations, R_.data(), 9*(size_t)ncam_*sizeof(double));
    std::memcpy(st->translations, t_.data(), 3*(size_t)ncam_*sizeof(double));
    std::memcpy(st->points, X_.data(), 3*(size_t)npt_*sizeof(double));
    std::memcpy(st->focal, f_.data(), ncam_*sizeof(double));
    std::memcpy(st->k1, k1v_.data(), ncam_*sizeof(double));
    std::memcpy(st->k2, k2v_.data(), ncam_*sizeof(double));
    out.final_cost = cost;
    out.total_matvecs = matvecs_;
    out.iterations = (int)out.cost_per_iteration.size() - 1;
    out.final_lambda = lam_cam;
    out.success = true;
    return out;
  }

 private:
  // full re-linearization at the current state
  // Student's t (kernel 3): EM scale update. With current state residuals
  // s_i = |r_i|^2 and Mahalanobis delta_i = s_i/sigma^2, the EM weights are
  // u_i = (nu+2)/(nu+delta_i) and the M-step is sigma^2 <- sum u_i s_i/(2N)
  // (bivariate). rk_a2_ = nu*sigma^2 then feeds the same Cauchy-form IRLS
  // weight the assembly already applies. One extra residual pass per outer.
  void UpdateTScale() {
    if (o_.robust_kernel != 3) return;
    const Scalar nu = (Scalar)o_.robust_nu;
    std::vector<Scalar> sv(nobs_);
#ifdef _OPENMP
#pragma omp parallel for schedule(static) num_threads(TF(nobs_))
#endif
    for (int o2 = 0; o2 < nobs_; ++o2) {
      const int c = p_.camera_index[o2], q = p_.point_index[o2];
      Scalar rx, ry;
      const Scalar* R = &R_[9*c];
      Scalar Px = R[0]*X_[3*q]+R[1]*X_[3*q+1]+R[2]*X_[3*q+2]+t_[3*c];
      Scalar Py = R[3]*X_[3*q]+R[4]*X_[3*q+1]+R[5]*X_[3*q+2]+t_[3*c+1];
      Scalar Pz = R[6]*X_[3*q]+R[7]*X_[3*q+1]+R[8]*X_[3*q+2]+t_[3*c+2];
      // Same convention as ComputeCost's BAL branch: Snavely -P/Pz.
      Scalar xp = -Px/Pz, yp = -Py/Pz, r2 = xp*xp+yp*yp;
      Scalar dist = 1.0 + k1v_[c]*r2 + k2v_[c]*r2*r2;
      rx = f_[c]*dist*xp - p_.observations[2*o2];
      ry = f_[c]*dist*yp - p_.observations[2*o2+1];
      sv[o2] = rx*rx + ry*ry;
    }
    if (rk_a2_ <= 0.0) {   // auto-init: median(s) ~ 1.386 sigma^2 for N(0,sigma^2 I2)
      std::vector<Scalar> tmp = sv;
      std::nth_element(tmp.begin(), tmp.begin()+tmp.size()/2, tmp.end());
      Scalar med = tmp[tmp.size()/2];
      rk_a2_ = nu*std::max(med/(Scalar)1.386, (Scalar)1e-8);
    }
    Scalar sig2 = rk_a2_/nu;
    for (int em = 0; em < 3; ++em) {   // a few EM sweeps per outer
      Scalar num = 0, cnt = 0;
      for (int i = 0; i < nobs_; ++i) {
        const Scalar u = (nu + 2.0)/(nu + sv[i]/sig2);
        num += u*sv[i]; cnt += 1.0;
      }
      sig2 = std::max(num/(2.0*cnt), (Scalar)1e-10);
    }
    rk_a2_ = nu*sig2;
  }

  void Assemble(Scalar k2mask) {
    UpdateTScale();
    std::fill(Hcc_.begin(), Hcc_.end(), 0.0);
    std::fill(bc_.begin(), bc_.end(), 0.0);
    std::fill(bp_.begin(), bp_.end(), 0.0);
    std::fill(Vsym_.begin(), Vsym_.end(), 0.0);
    std::fill(Cdiag_.begin(), Cdiag_.end(), 0.0);
    std::fill(r2acc_.begin(), r2acc_.end(), 0.0);
    std::fill(obscnt_.begin(), obscnt_.end(), 0.0);
    // per-obs Jacobians in parallel (each obs writes only its own slots)
#ifdef _OPENMP
#pragma omp parallel for schedule(static) num_threads(TF(nobs_))
#endif
    for (int o2 = 0; o2 < nobs_; ++o2) {
      const int c = p_.camera_index[o2], q = p_.point_index[o2];
      Scalar res[2], gcm[2][9], gpm[2][3];
      if (p_.cam_model)
        ResidualAndJacobianFixed(&R_[9*c], &t_[3*c], &X_[3*q], p_.cam_model[c],
                                 &p_.cam_params[8*c], &p_.observations[2*o2],
                                 res, gcm, gpm);
      else
        ResidualAndJacobian(&R_[9*c], &t_[3*c], &X_[3*q], f_[c], k1v_[c],
                            k2v_[c], k2mask, &p_.observations[2*o2], res, gcm,
                            gpm);
      if (o_.robust_kernel) {  // IRLS: sqrt-weight residual AND Jacobian rows
        const Scalar sw = std::sqrt(
            RobustW(o_.robust_kernel, rk_a2_, res[0]*res[0] + res[1]*res[1]));
        res[0] *= sw; res[1] *= sw;
        for (int rr2 = 0; rr2 < 2; ++rr2) {
          for (int j = 0; j < 9; ++j) gcm[rr2][j] *= sw;
          for (int j = 0; j < 3; ++j) gpm[rr2][j] *= sw;
        }
      }
      if (sk_p_ < 1.0) {  // RandNLA row-sampling sketch, fixed within the outer
        // deterministic per (outer, obs): same sketch across inner retries
        unsigned h = (unsigned)o2*2654435761u ^ (unsigned)(outer_k_*40503u + 0x9e37u);
        h ^= h >> 16; h *= 2246822519u; h ^= h >> 13;
        const double u01 = (h & 0xffffffu) * (1.0/16777216.0);
        const Scalar sk = (u01 < sk_p_) ? (Scalar)(1.0/std::sqrt(sk_p_)) : (Scalar)0.0;
        res[0] *= sk; res[1] *= sk;
        for (int rr2 = 0; rr2 < 2; ++rr2) {
          for (int j = 0; j < 9; ++j) gcm[rr2][j] *= sk;
          for (int j = 0; j < 3; ++j) gpm[rr2][j] *= sk;
        }
      }
      std::memcpy(&res_[2*(size_t)o2], res, 2*sizeof(Scalar));
      std::memcpy(&gc_[18*(size_t)o2], gcm, 18*sizeof(Scalar));
      std::memcpy(&gp_[6*(size_t)o2], gpm, 6*sizeof(Scalar));
    }
    // camera-major accumulation (deterministic: each camera owned by one task)
#ifdef _OPENMP
#pragma omp parallel for schedule(static) num_threads(TF(cam_work_))
#endif
    for (int c = 0; c < ncam_; ++c) {
      Scalar* H = &Hcc_[81*(size_t)c];
      Scalar* b = &bc_[9*c];
      for (int idx = cam_off_[c]; idx < cam_off_[c+1]; ++idx) {
        const int o2 = cam_list_[idx];
        const Scalar* g0 = &gc_[18*(size_t)o2];
        const Scalar* g1 = g0 + 9;
        const Scalar* rr = &res_[2*(size_t)o2];
        for (int i = 0; i < 9; ++i) {
          b[i] += g0[i]*rr[0] + g1[i]*rr[1];
          for (int j = 0; j < 9; ++j) H[9*i+j] += g0[i]*g0[j] + g1[i]*g1[j];
        }
        // rbar2 for the intrinsics prior: r2 recomputed from gc[7]/gc[6] is
        // fragile; recompute directly.
        const int qq = p_.point_index[o2];
        const Scalar* Rc = &R_[9*c]; const Scalar* Xp = &X_[3*qq];
        const Scalar Px = Rc[0]*Xp[0]+Rc[1]*Xp[1]+Rc[2]*Xp[2] + t_[3*c];
        const Scalar Py = Rc[3]*Xp[0]+Rc[4]*Xp[1]+Rc[5]*Xp[2] + t_[3*c+1];
        const Scalar Pz = Rc[6]*Xp[0]+Rc[7]*Xp[1]+Rc[8]*Xp[2] + t_[3*c+2];
        const Scalar xp = -Px/Pz, yp = -Py/Pz;
        r2acc_[c] += xp*xp + yp*yp; obscnt_[c] += 1.0;
      }
      // KernelDampIntr9, w=1
      if (obscnt_[c] > 0.0 && o_.intr_damp > 0.0) {
        Scalar rbar2 = r2acc_[c]/obscnt_[c]; if (!(rbar2 > 1e-12)) rbar2 = 1e-12;
        const Scalar sf = 0.5*std::fabs(f_[c]) + 1e-3;
        H[9*6+6] += o_.intr_damp/(sf*sf);
        H[9*7+7] += o_.intr_damp*rbar2*rbar2;
        if (k2mask > 0.0) H[9*8+8] += o_.intr_damp*rbar2*rbar2*rbar2*rbar2;
      }
    }
    // point-major accumulation
#ifdef _OPENMP
#pragma omp parallel for schedule(static) num_threads(TF(pt_work_))
#endif
    for (int q = 0; q < npt_; ++q) {
      Scalar* V = &Vsym_[6*(size_t)q];
      Scalar* cd = &Cdiag_[3*(size_t)q];
      Scalar* b = &bp_[3*q];
      for (int idx = pt_off_[q]; idx < pt_off_[q+1]; ++idx) {
        const int o2 = pt_list_[idx];
        const Scalar* g0 = &gp_[6*(size_t)o2];
        const Scalar* g1 = g0 + 3;
        const Scalar* rr = &res_[2*(size_t)o2];
        for (int i = 0; i < 3; ++i) b[i] += g0[i]*rr[0] + g1[i]*rr[1];
        // packed sym: a00,a01,a11,a02,a12,a22
        V[0] += g0[0]*g0[0] + g1[0]*g1[0];
        V[1] += g0[0]*g0[1] + g1[0]*g1[1];
        V[2] += g0[1]*g0[1] + g1[1]*g1[1];
        V[3] += g0[0]*g0[2] + g1[0]*g1[2];
        V[4] += g0[1]*g0[2] + g1[1]*g1[2];
        V[5] += g0[2]*g0[2] + g1[2]*g1[2];
      }
      cd[0] = V[0]; cd[1] = V[2]; cd[2] = V[5];
    }
  }

  // Augmented Givens QR, exactly as MFGivens/MFPointFactor: rotate each
  // observation's two gp ROWS plus the three damping rows sqrt(q_i) e_i into
  // an upper-triangular R (packed r00,r01,r02,r11,r12,r22), so V = R^T R with
  // kappa(R) = kappa(V)^(1/2). A Cholesky of the normal equations squares the
  // conditioning and DIVERGES from the GPU on venice-52 (measured: 40% at
  // iteration 1); the QR port restores bit-parity.
  static inline void Givens(Scalar* Rp, Scalar* v) {
    static const int ix[3][3] = {{0,1,2},{-1,3,4},{-1,-1,5}};
    for (int j = 0; j < 3; ++j) {
      const Scalar vj = v[j]; if (vj == 0.0) continue;
      const Scalar rjj = Rp[ix[j][j]];
      const Scalar rr = std::hypot(rjj, vj); if (rr == 0.0) continue;
      const Scalar cs = rjj/rr, sn = vj/rr; Rp[ix[j][j]] = rr;
      for (int k = j+1; k < 3; ++k) {
        const Scalar t1 = Rp[ix[j][k]], t2 = v[k];
        Rp[ix[j][k]] = cs*t1 + sn*t2; v[k] = -sn*t1 + cs*t2;
      }
      v[j] = 0.0;
    }
  }
  bool PointFactor(Scalar tau) {
#ifdef _OPENMP
#pragma omp parallel for schedule(static) num_threads(TF(pt_work_))
#endif
    for (int q = 0; q < npt_; ++q) {
      const Scalar* cd = &Cdiag_[3*(size_t)q];
      const Scalar tr = cd[0]+cd[1]+cd[2];
      Scalar fl = tau*tr/3.0; if (!(fl > 0.0)) fl = 1e-32;
      Scalar Rp[6] = {0,0,0,0,0,0};
      for (int idx = pt_off_[q]; idx < pt_off_[q+1]; ++idx) {
        const int o2 = pt_list_[idx];
        Scalar v0[3] = {gp_[6*(size_t)o2],   gp_[6*(size_t)o2+1], gp_[6*(size_t)o2+2]};
        Scalar v1[3] = {gp_[6*(size_t)o2+3], gp_[6*(size_t)o2+4], gp_[6*(size_t)o2+5]};
        Givens(Rp, v0); Givens(Rp, v1);
      }
      for (int i = 0; i < 3; ++i) {
        Scalar qd = tau*cd[i]; if (!(qd > 1e-3*fl)) qd = 1e-3*fl;
        qd_[3*(size_t)q + i] = qd;   // kept for LSMR's augmented point rows
        Scalar v[3] = {0,0,0}; v[i] = std::sqrt(qd); Givens(Rp, v);
      }
      ok_[q] = (Rp[0] > 0.0 && Rp[3] > 0.0 && Rp[5] > 0.0) ? 1 : 0;
      for (int i = 0; i < 6; ++i) Lp_[6*(size_t)q+i] = Rp[i];
    }
    return true;
  }
  // R^T R x = b via the two triangular solves (MFVinv verbatim).
  inline void Vinv(int q, const Scalar b[3], Scalar x[3]) const {
    if (!ok_[q]) { x[0] = x[1] = x[2] = 0.0; return; }
    const Scalar* Rp = &Lp_[6*(size_t)q];
    const Scalar y0 = b[0]/Rp[0];
    const Scalar y1 = (b[1] - Rp[1]*y0)/Rp[3];
    const Scalar y2 = (b[2] - Rp[2]*y0 - Rp[4]*y1)/Rp[5];
    x[2] = y2/Rp[5];
    x[1] = (y1 - Rp[4]*x[2])/Rp[3];
    x[0] = (y0 - Rp[1]*x[1] - Rp[2]*x[2])/Rp[0];
  }
  void VinvApply(const Scalar* vin, Scalar* vout) const {
#ifdef _OPENMP
#pragma omp parallel for schedule(static) num_threads(TF(pt_work_))
#endif
    for (int q = 0; q < npt_; ++q) Vinv(q, &vin[3*q], &vout[3*q]);
  }
  // corr[c] = sum_obs gc^T (gp * uu[pt]);  bprime = bc - corr
  void RhsPrime(const Scalar* uu_in, Scalar* bprime) const {
#ifdef _OPENMP
#pragma omp parallel for schedule(static) num_threads(TF(cam_work_))
#endif
    for (int c = 0; c < ncam_; ++c) {
      Scalar acc[9] = {0,0,0,0,0,0,0,0,0};
      for (int idx = cam_off_[c]; idx < cam_off_[c+1]; ++idx) {
        const int o2 = cam_list_[idx]; const int q = p_.point_index[o2];
        const Scalar* g0 = &gc_[18*(size_t)o2]; const Scalar* g1 = g0 + 9;
        const Scalar* h0 = &gp_[6*(size_t)o2]; const Scalar* h1 = h0 + 3;
        const Scalar* u3 = &uu_in[3*q];
        const Scalar y0 = h0[0]*u3[0]+h0[1]*u3[1]+h0[2]*u3[2];
        const Scalar y1 = h1[0]*u3[0]+h1[1]*u3[1]+h1[2]*u3[2];
        for (int i = 0; i < 9; ++i) acc[i] += g0[i]*y0 + g1[i]*y1;
      }
      for (int i = 0; i < 9; ++i) bprime[9*c+i] = bc_[9*c+i] - acc[i];
    }
  }
  // dk = diag(Hcc) + per-obs -( w_i^T V^-1 w_i ), w_i = gp^T gc[:,i]  (MFDiagK)
  void BuildEquil(Scalar* dk, Scalar* E) const {
#ifdef _OPENMP
#pragma omp parallel for schedule(static) num_threads(TF(cam_work_))
#endif
    for (int c = 0; c < ncam_; ++c) {
      for (int i = 0; i < 9; ++i) dk[9*c+i] = Hcc_[81*(size_t)c + 9*i + i];
      for (int idx = cam_off_[c]; idx < cam_off_[c+1]; ++idx) {
        const int o2 = cam_list_[idx]; const int q = p_.point_index[o2];
        if (!ok_[q]) continue;
        const Scalar* g0 = &gc_[18*(size_t)o2]; const Scalar* g1 = g0 + 9;
        const Scalar* h0 = &gp_[6*(size_t)o2]; const Scalar* h1 = h0 + 3;
        for (int i = 0; i < 9; ++i) {
          const Scalar wv[3] = {h0[0]*g0[i]+h1[0]*g1[i],
                                h0[1]*g0[i]+h1[1]*g1[i],
                                h0[2]*g0[i]+h1[2]*g1[i]};
          Scalar u3[3]; Vinv(q, wv, u3);
          dk[9*c+i] -= wv[0]*u3[0]+wv[1]*u3[1]+wv[2]*u3[2];
        }
      }
      for (int i = 0; i < 9; ++i) {
        const Scalar d = dk[9*c+i];
        E[9*c+i] = (d > 0.0) ? 1.0/std::sqrt(d) : 1.0;
      }
    }
  }
  // tacc[pt] = sum_obs gp^T (gc * v_cam)   (MFPass1)
  void Pass1(const Scalar* v, Scalar* tacc_out) const {
#ifdef _OPENMP
#pragma omp parallel for schedule(static) num_threads(TF(pt_work_))
#endif
    for (int q = 0; q < npt_; ++q) {
      Scalar acc[3] = {0,0,0};
      for (int idx = pt_off_[q]; idx < pt_off_[q+1]; ++idx) {
        const int o2 = pt_list_[idx]; const int c = p_.camera_index[o2];
        const Scalar* g0 = &gc_[18*(size_t)o2]; const Scalar* g1 = g0 + 9;
        const Scalar* h0 = &gp_[6*(size_t)o2]; const Scalar* h1 = h0 + 3;
        const Scalar* vc = &v[9*c];
        Scalar t0 = 0, t1 = 0;
        for (int i = 0; i < 9; ++i) { t0 += g0[i]*vc[i]; t1 += g1[i]*vc[i]; }
        acc[0] += h0[0]*t0 + h1[0]*t1;
        acc[1] += h0[1]*t0 + h1[1]*t1;
        acc[2] += h0[2]*t0 + h1[2]*t1;
      }
      tacc_out[3*q] = acc[0]; tacc_out[3*q+1] = acc[1]; tacc_out[3*q+2] = acc[2];
    }
  }
  // xpv = V^-1 (bp - tacc)   (MFBackSub)
  void BackSub(const Scalar* tacc_in, Scalar* xpv_out) const {
#ifdef _OPENMP
#pragma omp parallel for schedule(static) num_threads(TF(pt_work_))
#endif
    for (int q = 0; q < npt_; ++q) {
      const Scalar b3[3] = {bp_[3*q]-tacc_in[3*q], bp_[3*q+1]-tacc_in[3*q+1],
                            bp_[3*q+2]-tacc_in[3*q+2]};
      Vinv(q, b3, &xpv_out[3*q]);
    }
  }
  // K v = Hcc v - H_cp V^-1 H_pc v   (MFPass1 + Vinv + MFPass2)
  void Kv(const Scalar* v, Scalar* outv) {
    Pass1(v, tacc2_.data());
    VinvApply(tacc2_.data(), uu2_.data());
#ifdef _OPENMP
#pragma omp parallel for schedule(static) num_threads(TF(cam_work_))
#endif
    for (int c = 0; c < ncam_; ++c) {
      const Scalar* H = &Hcc_[81*(size_t)c];
      const Scalar* vc = &v[9*c];
      Scalar acc[9];
      for (int i = 0; i < 9; ++i) {
        Scalar s = 0;
        for (int j = 0; j < 9; ++j) s += H[9*i+j]*vc[j];
        acc[i] = s;
      }
      for (int idx = cam_off_[c]; idx < cam_off_[c+1]; ++idx) {
        const int o2 = cam_list_[idx]; const int q = p_.point_index[o2];
        const Scalar* g0 = &gc_[18*(size_t)o2]; const Scalar* g1 = g0 + 9;
        const Scalar* h0 = &gp_[6*(size_t)o2]; const Scalar* h1 = h0 + 3;
        const Scalar* u3 = &uu2_[3*q];
        const Scalar y0 = h0[0]*u3[0]+h0[1]*u3[1]+h0[2]*u3[2];
        const Scalar y1 = h1[0]*u3[0]+h1[1]*u3[1]+h1[2]*u3[2];
        for (int i = 0; i < 9; ++i) acc[i] -= g0[i]*y0 + g1[i]*y1;
      }
      for (int i = 0; i < 9; ++i) outv[9*c+i] = acc[i];
    }
    ++matvecs_;
  }
  void KvS(const Scalar* vin, Scalar* vout, const Scalar* E) {
    if ((int)scaled_.size() != n_c_) scaled_.resize(n_c_);
    for (int i = 0; i < n_c_; ++i) scaled_[i] = vin[i]*E[i];
    Kv(scaled_.data(), vout);
    for (int i = 0; i < n_c_; ++i) vout[i] *= E[i];
  }

  // ============== alternative inner solvers (benchmark paradigms) ============
  // PoBA-style power-series/Richardson with block-Jacobi preconditioner, run
  // PER SHIFT. The Neumann iterates live in the same Krylov space as the
  // shifts, so a shared-basis multi-shift variant exists on paper; the
  // practical form benchmarked here pays L separate sweeps.
  template <class ScoreFn>
  int InnerPoBA(const std::vector<Scalar>& shifts, const std::vector<Scalar>& b,
                const std::vector<Scalar>& E, const std::vector<int>& ckpts,
                int maxck, ScoreFn& Score, std::vector<std::vector<Scalar>>& xs) {
    const int L = (int)shifts.size();
    std::vector<Scalar> resid(n_c_), z(n_c_), M(81*(size_t)ncam_);
    int last_it = 0;
    for (int l = 0; l < L; ++l) {
      // M_c = E Hcc E + sigma I  (9x9), Cholesky in place
#ifdef _OPENMP
#pragma omp parallel for schedule(static) num_threads(TF(cam_work_))
#endif
      for (int c = 0; c < ncam_; ++c) {
        Scalar* Mc = &M[81*(size_t)c];
        const Scalar* H = &Hcc_[81*(size_t)c];
        const Scalar* Ec = &E[9*c];
        for (int i = 0; i < 9; ++i)
          for (int j = 0; j < 9; ++j)
            Mc[9*i+j] = Ec[i]*H[9*i+j]*Ec[j] + (i==j ? shifts[l] : 0.0);
        Chol9(Mc);
      }
      std::fill(xs[l].begin(), xs[l].end(), 0.0);
      size_t ci = 0;
      for (int it = 0; it < maxck; ++it) {
        KvS(xs[l].data(), resid.data(), E.data());
        for (int i = 0; i < n_c_; ++i) resid[i] = b[i] - (resid[i] + shifts[l]*xs[l][i]);
#ifdef _OPENMP
#pragma omp parallel for schedule(static) num_threads(TF(cam_work_))
#endif
        for (int c = 0; c < ncam_; ++c)
          Chol9Solve(&M[81*(size_t)c], &resid[9*c], &z[9*c]);
        Scalar zn = 0; for (int i = 0; i < n_c_; ++i) { xs[l][i] += z[i]; zn += z[i]*z[i]; }
        while (ci < ckpts.size() && it+1 == ckpts[ci]) { Score(xs[l], l, it+1); ++ci; }
        last_it = it+1;
        if (!(zn > 0) || !std::isfinite(zn)) break;   // diverged/stalled series
      }
      if (ci == 0) Score(xs[l], l, last_it);
    }
    return last_it;
  }

  // LSMR on the exact rectangular factor A of the reduced system: with
  // augmented rows [ (I-JpB Jp')Jc ; D^1/2 B Jp' Jc ; prior^1/2 ]E, B=(V+D)^-1,
  // A'A == E S E exactly (numerically gated below). ONE Golub-Kahan
  // bidiagonalization serves the WHOLE damping menu lambda_l = sqrt(shifts):
  // this is the multi-lambda fit the shifted-CG design already exploits.
  template <class ScoreFn>
  int InnerLSMR(const std::vector<Scalar>& shifts, const std::vector<Scalar>& b,
                const std::vector<Scalar>& E, const std::vector<int>& ckpts,
                int maxck, ScoreFn& Score, std::vector<std::vector<Scalar>>& xs) {
    const int L = (int)shifts.size();
    const size_t M = 2*(size_t)nobs_ + (size_t)n_p_ + 3*(size_t)ncam_;
    if (lsmr_u_.size() != M) { lsmr_u_.resize(M); lsmr_scr_.resize(M); }
    // prior sqrt (same formula as assembly's KernelDampIntr9)
    std::vector<Scalar> prs(3*(size_t)ncam_, 0.0);
    if (o_.intr_damp > 0.0 && !p_.cam_model)
      for (int c = 0; c < ncam_; ++c) {
        if (!(obscnt_[c] > 0)) continue;
        Scalar rb = r2acc_[c]/obscnt_[c]; if (!(rb > 1e-12)) rb = 1e-12;
        const Scalar sf = 0.5*std::fabs(f_[c]) + 1e-3;
        prs[3*c]   = std::sqrt(o_.intr_damp)/sf;
        prs[3*c+1] = std::sqrt(o_.intr_damp)*rb;
        prs[3*c+2] = (o_.refine_k2 ? std::sqrt(o_.intr_damp)*rb*rb : 0.0);
      }
    auto Aop = [&](const std::vector<Scalar>& vin, std::vector<Scalar>& uout){
      for (int i = 0; i < n_c_; ++i) scaled_[i] = vin[i]*E[i];
      Pass1(scaled_.data(), tacc2_.data());
      VinvApply(tacc2_.data(), uu2_.data());          // z = B Jp' Jc v
#ifdef _OPENMP
#pragma omp parallel for schedule(static) num_threads(TF((long)nobs_))
#endif
      for (int o2 = 0; o2 < nobs_; ++o2) {
        const int c = p_.camera_index[o2], q = p_.point_index[o2];
        const Scalar* g0 = &gc_[18*(size_t)o2]; const Scalar* g1 = g0 + 9;
        const Scalar* h0 = &gp_[6*(size_t)o2]; const Scalar* h1 = h0 + 3;
        const Scalar* vc = &scaled_[9*c]; const Scalar* z3 = &uu2_[3*q];
        Scalar t0 = 0, t1 = 0;
        for (int i = 0; i < 9; ++i) { t0 += g0[i]*vc[i]; t1 += g1[i]*vc[i]; }
        uout[2*(size_t)o2]   = t0 - (h0[0]*z3[0]+h0[1]*z3[1]+h0[2]*z3[2]);
        uout[2*(size_t)o2+1] = t1 - (h1[0]*z3[0]+h1[1]*z3[1]+h1[2]*z3[2]);
      }
      Scalar* upt = &uout[2*(size_t)nobs_];
#ifdef _OPENMP
#pragma omp parallel for schedule(static) num_threads(TF(pt_work_))
#endif
      for (int q = 0; q < npt_; ++q)
        for (int i = 0; i < 3; ++i)
          upt[3*(size_t)q+i] = std::sqrt(qd_[3*(size_t)q+i])*uu2_[3*q+i];
      Scalar* uin3 = &uout[2*(size_t)nobs_ + (size_t)n_p_];
      for (int c = 0; c < ncam_; ++c)
        for (int i = 0; i < 3; ++i)
          uin3[3*(size_t)c+i] = prs[3*c+i]*scaled_[9*c+6+i];
      ++matvecs_;
    };
    auto ATop = [&](const std::vector<Scalar>& uin, std::vector<Scalar>& vout){
      const Scalar* u1 = uin.data();
      const Scalar* u2 = &uin[2*(size_t)nobs_];
      const Scalar* u3 = &uin[2*(size_t)nobs_ + (size_t)n_p_];
#ifdef _OPENMP
#pragma omp parallel for schedule(static) num_threads(TF(pt_work_))
#endif
      for (int q = 0; q < npt_; ++q) {
        Scalar acc[3] = {0,0,0};
        for (int idx = pt_off_[q]; idx < pt_off_[q+1]; ++idx) {
          const int o2 = pt_list_[idx];
          const Scalar* h0 = &gp_[6*(size_t)o2]; const Scalar* h1 = h0 + 3;
          const Scalar a = u1[2*(size_t)o2], bb2 = u1[2*(size_t)o2+1];
          acc[0] += h0[0]*a + h1[0]*bb2;
          acc[1] += h0[1]*a + h1[1]*bb2;
          acc[2] += h0[2]*a + h1[2]*bb2;
        }
        for (int i = 0; i < 3; ++i)
          tacc2_[3*q+i] = acc[i] - std::sqrt(qd_[3*(size_t)q+i])*u2[3*(size_t)q+i];
      }
      VinvApply(tacc2_.data(), uu2_.data());          // z = B (Jp'u1 - D^1/2 u2)
#ifdef _OPENMP
#pragma omp parallel for schedule(static) num_threads(TF(cam_work_))
#endif
      for (int c = 0; c < ncam_; ++c) {
        Scalar acc[9] = {0,0,0,0,0,0,0,0,0};
        for (int idx = cam_off_[c]; idx < cam_off_[c+1]; ++idx) {
          const int o2 = cam_list_[idx]; const int q = p_.point_index[o2];
          const Scalar* g0 = &gc_[18*(size_t)o2]; const Scalar* g1 = g0 + 9;
          const Scalar* h0 = &gp_[6*(size_t)o2]; const Scalar* h1 = h0 + 3;
          const Scalar* z3 = &uu2_[3*q];
          const Scalar e0 = u1[2*(size_t)o2]   - (h0[0]*z3[0]+h0[1]*z3[1]+h0[2]*z3[2]);
          const Scalar e1 = u1[2*(size_t)o2+1] - (h1[0]*z3[0]+h1[1]*z3[1]+h1[2]*z3[2]);
          for (int i = 0; i < 9; ++i) acc[i] += g0[i]*e0 + g1[i]*e1;
        }
        for (int i = 0; i < 3; ++i) acc[6+i] += prs[3*c+i]*u3[3*(size_t)c+i];
        for (int i = 0; i < 9; ++i) vout[9*c+i] = acc[i]*E[9*c+i];
      }
    };
    // one-time exactness gate: A'A v must equal KvS(v) (no shift)
    static bool gated = false;
    if (!gated) {
      gated = true;
      std::vector<Scalar> v(n_c_), w1(n_c_), w2(n_c_);
      unsigned s = 12345;
      for (int i = 0; i < n_c_; ++i) { s = s*1664525u+1013904223u; v[i] = (Scalar)((s>>8)&0xffff)/65536.0 - 0.5; }
      Aop(v, lsmr_u_); ATop(lsmr_u_, w1);
      KvS(v.data(), w2.data(), E.data());
      Scalar num = 0, den = 0;
      for (int i = 0; i < n_c_; ++i) { num += (w1[i]-w2[i])*(w1[i]-w2[i]); den += w2[i]*w2[i]; }
      std::printf("  [LSMR gate] ||A'Av - Kv||/||Kv|| = %.3e\n", std::sqrt(num/std::max(den,(Scalar)1e-300)));
    }
    // Golub-Kahan shared across the damping menu; per-damp LSMR recurrences
    std::vector<Scalar> v(n_c_), vnext(n_c_);
    std::vector<Scalar>& u = lsmr_u_;
    Aop(std::vector<Scalar>(n_c_, 0.0), u);           // u = 0 (sizes)
    Scalar beta = Nrm2(b);
    if (!(beta > 0)) return 0;
    // u = [b;0;0] / beta   -- b lives in the row space only via A; LSMR solves
    // min||A x - u_rhs|| with u_rhs = "b" expressed in aug space. The reduced
    // rhs b' equals A' * [rhat;aug]; using LSMR on (A, b_aug) requires b in the
    // TALL space. Equivalent standard trick: solve A'A x = b via LSMR on the
    // least-squares system with rhs u0 satisfying A'u0 = b: NOT directly
    // available. Instead run CGLS-style: treat b as A'*r0 with r0 unknown --
    // use LSMR on normal-equation form: bidiagonalize with v1 = b/||b||
    // (CRAIG/LSMR-NE variant): v-space start, damping enters identically.
    for (int i = 0; i < n_c_; ++i) v[i] = b[i]/beta;
    Aop(v, u);
    Scalar alpha = Nrm2(u);
    if (alpha > 0) for (size_t i = 0; i < M; ++i) u[i] /= alpha;
    struct DS { Scalar alphabar, zetabar, rho, rhobar, cbar, sbar;
                std::vector<Scalar> h, hbar; };
    std::vector<DS> ds(L);
    for (int l = 0; l < L; ++l) {
      ds[l].alphabar = alpha; ds[l].zetabar = alpha*beta;
      ds[l].rho = 1; ds[l].rhobar = 1; ds[l].cbar = 1; ds[l].sbar = 0;
      ds[l].h = v; ds[l].hbar.assign(n_c_, 0.0);
      std::fill(xs[l].begin(), xs[l].end(), 0.0);
    }
    size_t ci = 0; int it = 0;
    for (it = 0; it < maxck; ++it) {
      // bidiag step: v_{k+1}: ATop(u) - alpha*v ; then u_{k+1} = A v - beta*u
      ATop(u, vnext);
      for (int i = 0; i < n_c_; ++i) vnext[i] -= alpha*v[i];
      Scalar beta2 = Nrm2(vnext);
      if (!(beta2 > 0)) { ++it; break; }
      for (int i = 0; i < n_c_; ++i) vnext[i] /= beta2;
      Aop(vnext, lsmr_scr_);
      for (size_t i = 0; i < M; ++i) lsmr_scr_[i] -= beta2*u[i];
      Scalar alpha2 = Nrm2FlatM(lsmr_scr_);
      if (alpha2 > 0) for (size_t i = 0; i < M; ++i) u[i] = lsmr_scr_[i]/alpha2;
      // NOTE index roles: in the v-start (normal-equations) variant the roles
      // of (alpha,beta) swap relative to textbook LSMR; the recurrences below
      // use the local bidiagonal entries directly.
      for (int l = 0; l < L; ++l) {
        DS& d = ds[l];
        const Scalar damp = std::sqrt(shifts[l]);
        const Scalar alphahat = std::sqrt(d.alphabar*d.alphabar + damp*damp);
        const Scalar rhoold = d.rho;
        d.rho = std::sqrt(alphahat*alphahat + beta2*beta2);
        const Scalar c2 = alphahat/d.rho, s2 = beta2/d.rho;
        const Scalar thetanew = s2*alpha2;
        d.alphabar = c2*alpha2;
        const Scalar rhobarold = d.rhobar;
        const Scalar thetabar = d.sbar*d.rho;
        d.rhobar = std::sqrt(d.cbar*d.rho*d.cbar*d.rho + thetanew*thetanew);
        d.cbar = d.cbar*d.rho/d.rhobar;
        d.sbar = thetanew/d.rhobar;
        const Scalar zeta = d.cbar*d.zetabar;
        d.zetabar = -d.sbar*d.zetabar;
        const Scalar hb = thetabar*d.rho/(rhoold*rhobarold);
        for (int i = 0; i < n_c_; ++i) {
          d.hbar[i] = d.h[i] - hb*d.hbar[i];
          xs[l][i] += (zeta/(d.rho*d.rhobar))*d.hbar[i];
          d.h[i] = vnext[i] - (thetanew/d.rho)*d.h[i];
        }
      }
      v.swap(vnext); alpha = alpha2;
      while (ci < ckpts.size() && it+1 == ckpts[ci]) {
        for (int l = 0; l < L; ++l) Score(xs[l], l, it+1);
        ++ci;
      }
    }
    if (ci == 0) for (int l = 0; l < L; ++l) Score(xs[l], l, it);
    return it;
  }

  // Randomized Kaczmarz row-action on the damped LS rows (center shift only;
  // rows are the raw obs rows [gc|gp] plus scalar damping rows). Solves in the
  // JOINT (cam+pt) space; candidate scoring recomputes points from the camera
  // part like every other inner solver, so RK's own point estimates are only
  // an internal device.
  template <class ScoreFn>
  int InnerRK(const std::vector<Scalar>& shifts, const std::vector<Scalar>& b,
              const std::vector<Scalar>& E, const std::vector<int>& ckpts,
              int maxck, ScoreFn& Score, std::vector<Scalar>& dscratch) {
    std::vector<Scalar> d(n_, 0.0), xscaled(n_c_);
    const Scalar lam = shifts.size() ? shifts[std::min<size_t>(2, shifts.size()-1)] : 1.0;
    unsigned rng = 777u;
    auto urand = [&](){ rng = rng*1664525u + 1013904223u; return (rng>>8) & 0xffffff; };
    const Scalar omega = 0.7;   // under-relaxation
    size_t ci = 0; int it = 0;
    const long sweep = std::max(1L, (long)nobs_);
    for (it = 0; it < maxck; ++it) {
      for (long s2 = 0; s2 < sweep; ++s2) {
        const int o2 = (int)(urand() % (unsigned)nobs_);
        const int c = p_.camera_index[o2], q = p_.point_index[o2];
        const Scalar* g0 = &gc_[18*(size_t)o2];
        const Scalar* h0 = &gp_[6*(size_t)o2];
        for (int row = 0; row < 2; ++row) {
          const Scalar* gr = g0 + 9*row; const Scalar* hr = h0 + 3*row;
          Scalar ax = 0, nrm = 0;
          for (int i = 0; i < 9; ++i) { ax += gr[i]*d[9*c+i]; nrm += gr[i]*gr[i]; }
          for (int i = 0; i < 3; ++i) { ax += hr[i]*d[9*ncam_+3*q+i]; nrm += hr[i]*hr[i]; }
          if (!(nrm > 1e-300)) continue;
          const Scalar corr = omega*((-res_[2*(size_t)o2+row]) - ax)/nrm;
          for (int i = 0; i < 9; ++i) d[9*c+i] += corr*gr[i];
          for (int i = 0; i < 3; ++i) d[9*ncam_+3*q+i] += corr*hr[i];
        }
        if ((s2 & 7) == 0) {   // damping rows at 1/8 rate: shrink toward 0
          const int j = (int)(urand() % (unsigned)n_);
          const Scalar qdj = (j < n_c_) ? lam : qd_[j - n_c_];
          (void)qdj; d[j] *= (Scalar)(1.0 - omega*0.05);
        }
      }
      while (ci < ckpts.size() && it+1 == ckpts[ci]) {
        // Score expects the EQUILIBRATED camera part with a MINUS convention
        // downstream (dfull = -xc_un): negate so the step direction matches.
        for (int i = 0; i < n_c_; ++i)
          xscaled[i] = (E[i] != 0.0) ? -d[i]/E[i] : 0.0;
        Score(xscaled, -1, it+1);
        ++ci;
      }
      matvecs_ += 2;   // a full RK sweep touches every row ~ 2 matvec-equivalents
    }
    if (ci == 0) {
      for (int i = 0; i < n_c_; ++i) xscaled[i] = (E[i] != 0.0) ? -d[i]/E[i] : 0.0;
      Score(xscaled, -1, it);
    }
    (void)dscratch; (void)b;
    return it;
  }

  static void Chol9(Scalar* A) {   // in-place lower Cholesky, 9x9 row-major
    for (int i = 0; i < 9; ++i) {
      for (int j = 0; j <= i; ++j) {
        Scalar s = A[9*i+j];
        for (int k2 = 0; k2 < j; ++k2) s -= A[9*i+k2]*A[9*j+k2];
        if (i == j) A[9*i+j] = std::sqrt(std::max(s, (Scalar)1e-300));
        else        A[9*i+j] = s/A[9*j+j];
      }
    }
  }
  static void Chol9Solve(const Scalar* Lm, const Scalar* bin, Scalar* x) {
    Scalar y[9];
    for (int i = 0; i < 9; ++i) {
      Scalar s = bin[i];
      for (int j = 0; j < i; ++j) s -= Lm[9*i+j]*y[j];
      y[i] = s/Lm[9*i+i];
    }
    for (int i = 8; i >= 0; --i) {
      Scalar s = y[i];
      for (int j = i+1; j < 9; ++j) s -= Lm[9*j+i]*x[j];
      x[i] = s/Lm[9*i+i];
    }
  }
  Scalar Nrm2FlatM(const std::vector<Scalar>& a) const {
    Scalar s = 0;
#ifdef _OPENMP
#pragma omp parallel for reduction(+:s) schedule(static) num_threads(TF((long)a.size()))
#endif
    for (long i = 0; i < (long)a.size(); ++i) s += a[i]*a[i];
    return std::sqrt(s);
  }
  // exp(dw) R, additive t/f/k1/k2/X  — 9-wide camera layout, then points
  void Retract(const Scalar* d) {
#ifdef _OPENMP
#pragma omp parallel for schedule(static) num_threads(TF(cam_work_))
#endif
    for (int c = 0; c < ncam_; ++c) {
      Scalar dR[9];
      ExpSO3(d + 9*c, dR);
      Mat3Mul(dR, &R_[9*c], &Rn_[9*c]);
      for (int i = 0; i < 3; ++i) tn_[3*c+i] = t_[3*c+i] + d[9*c+3+i];
      // frozen when a fixed projection model is attached (zero-gradient columns
      // stay ~0 anyway; the mask makes it exact)
      const Scalar ilive = p_.cam_model ? 0.0 : 1.0;
      fn_[c]  = f_[c]  + ilive*d[9*c+6];
      k1n_[c] = k1v_[c] + ilive*d[9*c+7];
      k2n_[c] = k2v_[c] + ilive*d[9*c+8];
    }
#ifdef _OPENMP
#pragma omp parallel for schedule(static) num_threads(TF(pt_work_))
#endif
    for (int q = 0; q < npt_; ++q)
      for (int i = 0; i < 3; ++i) Xn_[3*q+i] = X_[3*q+i] + d[9*ncam_+3*q+i];
  }
  // Threads scaled to the work: a 64-thread fork over a 49-camera loop costs
  // hundreds of times the loop body (measured: 5 iterations went 0.04s at 8
  // threads to 21.9s at 64 purely from fork/join+barrier overhead on tiny
  // regions). Grain 4096 keeps big obs sweeps fully parallel and runs small
  // per-camera/per-point loops serial.
  inline int TF(long work) const {
    const long by_grain = work / 4096;
    if (by_grain <= 1) return 1;
    return (int)std::min<long>(nthreads_, by_grain);
  }
  Scalar Dot(const std::vector<Scalar>& a, const std::vector<Scalar>& b) const {
    Scalar s = 0;
#ifdef _OPENMP
#pragma omp parallel for reduction(+:s) schedule(static) num_threads(TF((long)a.size()))
#endif
    for (int i = 0; i < (int)a.size(); ++i) s += a[i]*b[i];
    return s;
  }
  Scalar Nrm2(const std::vector<Scalar>& a) const { return std::sqrt(Dot(a, a)); }

 private:
  long matvecs_ = 0;

  const Problem& p_; const Options& o_;
  int ncam_, npt_, nobs_, n_c_, n_p_, n_, nthreads_;
  Scalar rk_a2_ = 0.0;   // effective robust a2 (mutable for the adaptive t kernel)
  long cam_work_ = 0, pt_work_ = 0;
  Scalar best_sn_ = 0;
  Scalar prev_iter_cost_ = 0;
  std::vector<int> pt_off_, pt_list_, cam_off_, cam_list_;
  std::vector<Scalar> res_, gc_, gp_;
  std::vector<Scalar> Hcc_, bc_, bp_, Vsym_, Cdiag_, Lp_;
  std::vector<int> ok_;
  std::vector<Scalar> r2acc_, obscnt_;
  std::vector<Scalar> R_, t_, X_, f_, k1v_, k2v_;
  std::vector<Scalar> Rn_, tn_, Xn_, fn_, k1n_, k2n_;
  std::vector<Scalar> tacc2_, uu2_, scaled_;
  std::vector<Scalar> qd_;          // augmented point-damping diag (3/pt)
  std::vector<Scalar> lsmr_u_, lsmr_scr_;   // GK tall-space work vectors
  double sk_p_ = 1.0;               // current sketch keep-probability
  int outer_k_ = 0;                 // outer index (sketch redraw seed)
};

inline Result Solve(const Problem& p, const Options& o, State* st) {
  Solver s(p, o);
  return s.Solve(st);
}

}  // namespace oca_cpu
