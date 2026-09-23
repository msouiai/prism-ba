// Unit test: the CPU/OpenMP port of the matrix-free multi-shift solver
// (mfree_cpu.h) against the GPU champion (oca::Solve).
//
// Gates, in order of increasing strictness about what "same algorithm" means:
//   T1  initial cost parity      -- same objective evaluated by both sides
//   T2  Jacobian finite-diff     -- the CPU derivatives validated independently
//   T3  trajectory parity        -- per-accepted-iteration costs track the
//                                   GPU's (early iterations tightly; later ones
//                                   loosely, since fp-noise in candidate
//                                   tie-breaks can legitimately fork the path)
//   T4  endpoint parity          -- final cost and iteration count agree
//
// Both solvers receive byte-identical inputs and identical options (the GPU
// core hardcodes n_shifts=5 and equilibration on; the CPU port mirrors that).
// Exit 0 = all gates pass. Usage:  mfree_cpu_test [bal.txt] [max_iters]
#include "mfree_cpu.h"
#include "oca_core.h"

#include <unistd.h>

#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <random>
#include <string>
#include <vector>

namespace {

struct Bal {
  int ncam = 0, npt = 0, nobs = 0;
  std::vector<int> cam, pt;
  std::vector<double> uv;
  std::vector<double> R, t, f, k1, k2, X;  // rotations already as matrices
};

bool LoadBal(const std::string& path, Bal* b) {
  std::ifstream in(path);
  if (!in) return false;
  in >> b->ncam >> b->npt >> b->nobs;
  b->cam.resize(b->nobs); b->pt.resize(b->nobs); b->uv.resize(2*(size_t)b->nobs);
  for (int i = 0; i < b->nobs; ++i)
    in >> b->cam[i] >> b->pt[i] >> b->uv[2*i] >> b->uv[2*i+1];
  b->R.resize(9*(size_t)b->ncam); b->t.resize(3*(size_t)b->ncam);
  b->f.resize(b->ncam); b->k1.resize(b->ncam); b->k2.resize(b->ncam);
  for (int c = 0; c < b->ncam; ++c) {
    double w[3], tt[3], fo, q1, q2;
    in >> w[0] >> w[1] >> w[2] >> tt[0] >> tt[1] >> tt[2] >> fo >> q1 >> q2;
    oca_cpu::ExpSO3(w, &b->R[9*c]);
    for (int i = 0; i < 3; ++i) b->t[3*c+i] = tt[i];
    b->f[c] = fo; b->k1[c] = q1; b->k2[c] = q2;
  }
  b->X.resize(3*(size_t)b->npt);
  for (int q = 0; q < b->npt; ++q) in >> b->X[3*q] >> b->X[3*q+1] >> b->X[3*q+2];
  return (bool)in;
}

int fails = 0;
void Check(bool ok, const char* what, double got, double tol) {
  std::printf("  %-46s %-4s (%.3e, tol %.1e)\n", what, ok ? "PASS" : "FAIL", got, tol);
  if (!ok) ++fails;
}

}  // namespace

// Write a solver endpoint back out in BAL format, so GPU and CPU results can
// be scored by the same external tooling (inlier-L2 on a known clean subset,
// which is the only fair way to compare robust kernels against each other).
void WriteBal(const std::string& path, const Bal& b,
              const std::vector<double>& R, const std::vector<double>& t,
              const std::vector<double>& X, const std::vector<double>& f,
              const std::vector<double>& k1, const std::vector<double>& k2) {
  FILE* fh = fopen(path.c_str(), "w");
  if (!fh) return;
  fprintf(fh, "%d %d %d\n", b.ncam, b.npt, b.nobs);
  for (int i = 0; i < b.nobs; ++i)
    fprintf(fh, "%d %d %.17g %.17g\n", b.cam[i], b.pt[i], b.uv[2*i], b.uv[2*i+1]);
  for (int c = 0; c < b.ncam; ++c) {
    const double* Rc = &R[9*c];
    const double tr = Rc[0] + Rc[4] + Rc[8];
    const double ct = std::max(-1.0, std::min(1.0, (tr - 1.0)*0.5));
    const double th = std::acos(ct);
    double w[3] = {0, 0, 0};
    if (th >= 1e-10) {
      const double s2 = 2.0*std::sin(th);
      w[0] = th*(Rc[7]-Rc[5])/s2; w[1] = th*(Rc[2]-Rc[6])/s2; w[2] = th*(Rc[3]-Rc[1])/s2;
    }
    fprintf(fh, "%.17g\n%.17g\n%.17g\n%.17g\n%.17g\n%.17g\n%.17g\n%.17g\n%.17g\n",
            w[0], w[1], w[2], t[3*c], t[3*c+1], t[3*c+2], f[c], k1[c], k2[c]);
  }
  for (int q = 0; q < b.npt; ++q)
    fprintf(fh, "%.17g\n%.17g\n%.17g\n", X[3*q], X[3*q+1], X[3*q+2]);
  fclose(fh);
  std::printf("dumped state to %s\n", path.c_str());
}

int main(int argc, char** argv) {
  // libgomp's default active (spinning) wait policy costs 46x at 64 threads
  // on this solver's many small regions (measured on venice-52: 210s active vs
  // 4.6s passive at nt=64). libgomp parses the variable in its ELF constructor
  // -- BEFORE main -- so setenv here is too late (measured: no effect); the
  // only reliable in-binary fix is to set it and re-exec ourselves once.
  if (!getenv("OMP_WAIT_POLICY")) {
    setenv("OMP_WAIT_POLICY", "passive", 1);
    execv("/proc/self/exe", argv);   // returns only on failure; then proceed
  }
  const std::string path = argc > 1 ? argv[1]
      : "/workspace/bundle_adjustment/daba_cuda/ladybug-49.txt";
  const int max_iters = argc > 2 ? std::atoi(argv[2]) : 20;

  Bal b;
  std::vector<int> fish_model;        // non-empty => FIXED-intrinsics mode
  std::vector<double> fish_par;       // 8 per camera
  const bool is_fish = path.size() > 9 &&
      path.compare(path.size() - 9, 9, ".fish.txt") == 0;
  if (is_fish) {
    // .fish.txt: "ncam npt nobs" / nobs x "ci pi u v" (RAW pixels) /
    // ncam x "model p0..p7 w0 w1 w2 t0 t1 t2" (COLMAP convention, log-map w) /
    // npt x "x y z". Intrinsics state is dummy (f=1,k=0) and frozen.
    FILE* fp = fopen(path.c_str(), "r");
    if (!fp) { std::printf("cannot read %s\n", path.c_str()); return 1; }
    if (fscanf(fp, "%d %d %d", &b.ncam, &b.npt, &b.nobs) != 3) return 1;
    b.cam.resize(b.nobs); b.pt.resize(b.nobs); b.uv.resize(2*(size_t)b.nobs);
    for (int i = 0; i < b.nobs; ++i)
      if (fscanf(fp, "%d %d %lf %lf", &b.cam[i], &b.pt[i], &b.uv[2*i],
                 &b.uv[2*i+1]) != 4) return 1;
    b.R.resize(9*(size_t)b.ncam); b.t.resize(3*(size_t)b.ncam);
    b.f.assign(b.ncam, 1.0); b.k1.assign(b.ncam, 0.0); b.k2.assign(b.ncam, 0.0);
    fish_model.resize(b.ncam); fish_par.resize(8*(size_t)b.ncam);
    for (int c = 0; c < b.ncam; ++c) {
      double w[3];
      if (fscanf(fp, "%d", &fish_model[c]) != 1) return 1;
      for (int j = 0; j < 8; ++j)
        if (fscanf(fp, "%lf", &fish_par[8*c+j]) != 1) return 1;
      for (int j = 0; j < 3; ++j) if (fscanf(fp, "%lf", &w[j]) != 1) return 1;
      for (int j = 0; j < 3; ++j)
        if (fscanf(fp, "%lf", &b.t[3*c+j]) != 1) return 1;
      oca_cpu::ExpSO3(w, &b.R[9*c]);
    }
    b.X.resize(3*(size_t)b.npt);
    for (size_t i = 0; i < b.X.size(); ++i)
      if (fscanf(fp, "%lf", &b.X[i]) != 1) return 1;
    fclose(fp);
  } else if (!LoadBal(path, &b)) {
    std::printf("cannot read %s\n", path.c_str()); return 1;
  }
  std::printf("loaded %s: %d cams, %d pts, %d obs%s\n", path.c_str(), b.ncam,
              b.npt, b.nobs, is_fish ? " (FIXED-intrinsics models)" : "");

  oca_cpu::Problem cp;
  cp.num_cameras = b.ncam; cp.num_points = b.npt; cp.num_observations = b.nobs;
  cp.camera_index = b.cam.data(); cp.point_index = b.pt.data();
  cp.observations = b.uv.data();
  if (is_fish) { cp.cam_model = fish_model.data(); cp.cam_params = fish_par.data(); }

  // ---------------- T2: finite-difference Jacobian (CPU, self-contained) ----
  if (is_fish) {
    // FD gate for the FIXED-model path: pose (w,t) and point columns; the
    // intrinsics columns are frozen by construction.
    std::mt19937 rng(11);
    std::uniform_int_distribution<int> pick(0, b.nobs - 1);
    double worst = 0.0;
    for (int trial = 0; trial < 60; ++trial) {
      const int o = pick(rng);
      const int c = b.cam[o], q = b.pt[o];
      double res[2], gcm[2][9], gpm[2][3];
      oca_cpu::ResidualAndJacobianFixed(&b.R[9*c], &b.t[3*c], &b.X[3*q],
                                        fish_model[c], &fish_par[8*c],
                                        &b.uv[2*o], res, gcm, gpm);
      for (int j = 0; j < 12; ++j) {
        if (j >= 6 && j < 9) continue;  // frozen intrinsics columns
        const double eps = 1e-7;
        double rp[2], rm[2], g2[2][9], g3[2][3];
        double Rp[9], Rm[9], tp[3], tm[3], Xp[3], Xm[3];
        std::memcpy(Rp, &b.R[9*c], sizeof Rp); std::memcpy(Rm, Rp, sizeof Rm);
        std::memcpy(tp, &b.t[3*c], sizeof tp); std::memcpy(tm, tp, sizeof tm);
        std::memcpy(Xp, &b.X[3*q], sizeof Xp); std::memcpy(Xm, Xp, sizeof Xm);
        if (j < 3) {
          double w[3] = {0, 0, 0}, dR[9], Rt[9];
          w[j] = eps;  oca_cpu::ExpSO3(w, dR); oca_cpu::Mat3Mul(dR, &b.R[9*c], Rt);
          std::memcpy(Rp, Rt, sizeof Rp);
          w[j] = -eps; oca_cpu::ExpSO3(w, dR); oca_cpu::Mat3Mul(dR, &b.R[9*c], Rt);
          std::memcpy(Rm, Rt, sizeof Rm);
        } else if (j < 6) { tp[j-3] += eps; tm[j-3] -= eps; }
        else              { Xp[j-9] += eps; Xm[j-9] -= eps; }
        oca_cpu::ResidualAndJacobianFixed(Rp, tp, Xp, fish_model[c],
                                          &fish_par[8*c], &b.uv[2*o], rp, g2, g3);
        oca_cpu::ResidualAndJacobianFixed(Rm, tm, Xm, fish_model[c],
                                          &fish_par[8*c], &b.uv[2*o], rm, g2, g3);
        for (int rrow = 0; rrow < 2; ++rrow) {
          const double fd = (rp[rrow] - rm[rrow]) / (2*eps);
          const double an = (j < 9) ? gcm[rrow][j] : gpm[rrow][j-9];
          double row_scale = 1e-30;
          for (int jj = 0; jj < 9; ++jj) row_scale = std::max(row_scale, std::fabs(gcm[rrow][jj]));
          for (int jj = 0; jj < 3; ++jj) row_scale = std::max(row_scale, std::fabs(gpm[rrow][jj]));
          const double scale = std::max({std::fabs(fd), std::fabs(an), 1e-4*row_scale});
          const double rel = std::fabs(fd - an)/scale;
          if (rel > worst) {
            worst = rel;
            if (rel > 1e-4)
              std::printf("    [T2f] obs %d col %d row %d: fd=%.8e an=%.8e\n",
                          o, j, rrow, fd, an);
          }
        }
      }
    }
    Check(worst < 1e-4, "T2f fixed-model Jacobian vs central differences", worst, 1e-4);
  } else {
    std::mt19937 rng(11);
    std::uniform_int_distribution<int> pick(0, b.nobs - 1);
    double worst = 0.0;
    for (int trial = 0; trial < 60; ++trial) {
      const int o = pick(rng);
      const int c = b.cam[o], q = b.pt[o];
      double res[2], gcm[2][9], gpm[2][3];
      oca_cpu::ResidualAndJacobian(&b.R[9*c], &b.t[3*c], &b.X[3*q],
                                   b.f[c], b.k1[c], b.k2[c], 1.0,
                                   &b.uv[2*o], res, gcm, gpm);
      // perturb each of the 12 coordinates through the same retraction the
      // solver uses (exp for w, additive otherwise) and central-difference.
      for (int j = 0; j < 12; ++j) {
        const double eps = (j == 6) ? 1e-2 : 1e-7;   // f is O(1e3)
        double rp[2], rm[2], g2[2][9], g3[2][3];
        double Rp[9], Rm[9], tp[3], tm[3], Xp[3], Xm[3];
        double fp = b.f[c], fm = b.f[c], k1p = b.k1[c], k1m = b.k1[c],
               k2p = b.k2[c], k2m = b.k2[c];
        std::memcpy(Rp, &b.R[9*c], sizeof Rp); std::memcpy(Rm, Rp, sizeof Rm);
        std::memcpy(tp, &b.t[3*c], sizeof tp); std::memcpy(tm, tp, sizeof tm);
        std::memcpy(Xp, &b.X[3*q], sizeof Xp); std::memcpy(Xm, Xp, sizeof Xm);
        if (j < 3) {                       // rotation: R <- exp(+-eps e_j) R
          double w[3] = {0, 0, 0}, dR[9], Rt[9];
          w[j] = eps;  oca_cpu::ExpSO3(w, dR); oca_cpu::Mat3Mul(dR, &b.R[9*c], Rt);
          std::memcpy(Rp, Rt, sizeof Rp);
          w[j] = -eps; oca_cpu::ExpSO3(w, dR); oca_cpu::Mat3Mul(dR, &b.R[9*c], Rt);
          std::memcpy(Rm, Rt, sizeof Rm);
        } else if (j < 6)  { tp[j-3] += eps; tm[j-3] -= eps; }
        else if (j == 6)   { fp += eps; fm -= eps; }
        else if (j == 7)   { k1p += eps; k1m -= eps; }
        else if (j == 8)   { k2p += eps; k2m -= eps; }
        else               { Xp[j-9] += eps; Xm[j-9] -= eps; }
        oca_cpu::ResidualAndJacobian(Rp, tp, Xp, fp, k1p, k2p, 1.0, &b.uv[2*o], rp, g2, g3);
        oca_cpu::ResidualAndJacobian(Rm, tm, Xm, fm, k1m, k2m, 1.0, &b.uv[2*o], rm, g2, g3);
        for (int rrow = 0; rrow < 2; ++rrow) {
          const double fd = (rp[rrow] - rm[rrow]) / (2*eps);
          const double an = (j < 9) ? gcm[rrow][j] : gpm[rrow][j-9];
          // Central differences on O(1e2) residuals resolve ~1e-7 absolute at
          // eps=1e-7; comparing entries below that floor measures FD noise,
          // not the Jacobian. Scale the tolerance to the row's magnitude.
          double row_scale = 1e-30;
          for (int jj = 0; jj < 9; ++jj) row_scale = std::max(row_scale, std::fabs(gcm[rrow][jj]));
          for (int jj = 0; jj < 3; ++jj) row_scale = std::max(row_scale, std::fabs(gpm[rrow][jj]));
          const double scale = std::max({std::fabs(fd), std::fabs(an), 1e-4*row_scale});
          const double rel = std::fabs(fd - an)/scale;
          if (rel > worst) {
            worst = rel;
            if (rel > 1e-4)
              std::printf("    [T2] obs %d col %d row %d: fd=%.8e an=%.8e\n",
                          o, j, rrow, fd, an);
          }
        }
      }
    }
    Check(worst < 1e-4, "T2 Jacobian vs central differences", worst, 1e-4);
  }

  // ---------------- shared options -----------------------------------------
  oca::Options go;      oca_cpu::Options co;
  go.max_iterations = co.max_iterations = max_iters;
  go.refine_intrinsics = true; go.refine_k2 = co.refine_k2 = true;
  go.func_tolerance = co.func_tolerance = 0.0;          // fixed-length runs:
  go.max_consecutive_failures = co.max_consecutive_failures = 0;  // trajectory
  go.verbose = co.verbose = getenv("MF_VERBOSE") != nullptr;      // comparison
  // MF_KERNEL applies to BOTH legs in the parity path, so the GPU robust
  // kernel is gated against the validated CPU one on the same problem.
  if (const char* e = getenv("MF_KERNEL")) {
    std::string s2 = e;
    auto set = [&](int k, double a2, double nu) {
      go.robust_kernel = co.robust_kernel = k;
      go.robust_scale2 = co.robust_scale2 = a2;
      go.robust_nu = co.robust_nu = nu;
    };
    if (s2.rfind("huber:", 0) == 0) { double d = atof(s2.c_str()+6); set(1, d*d, 4.0); }
    else if (s2.rfind("cauchy:", 0) == 0) { double c = atof(s2.c_str()+7); set(2, c*c, 4.0); }
    else if (s2.rfind("studentt:", 0) == 0) {
      const double nu = atof(s2.c_str()+9);
      const char* colon = strchr(s2.c_str()+9, ':');
      const double sg = colon ? atof(colon+1) : 0.0;
      set(3, sg > 0 ? nu*sg*sg : 0.0, nu);
    }
  }

  // MF_CPU_ONLY=1: skip the GPU reference and parity gates entirely -- pure
  // CPU benchmark mode for the algorithm-vs-algorithm comparison with CPU
  // Ceres. Prints the same per-iteration lines (MF_VERBOSE) for crossings.
  if (getenv("MF_CPU_ONLY")) {
    std::vector<double> Rc2 = b.R, tc2 = b.t, Xc2 = b.X, fc2 = b.f, k1c2 = b.k1, k2c2 = b.k2;
    oca_cpu::State cs2;
    cs2.rotations = Rc2.data(); cs2.translations = tc2.data(); cs2.points = Xc2.data();
    cs2.focal = fc2.data(); cs2.k1 = k1c2.data(); cs2.k2 = k2c2.data();
    oca_cpu::Options co2 = co;
    if (const char* e = getenv("MF_FUNC_TOL")) co2.func_tolerance = atof(e);
    if (const char* e = getenv("MF_MAX_FAIL")) co2.max_consecutive_failures = atoi(e);
    if (const char* e = getenv("MF_ETA")) co2.ew_eta_max = atof(e);
    if (const char* e = getenv("MF_TAU")) co2.point_damping = atof(e);
    if (const char* e = getenv("MF_INTR_DAMP")) co2.intr_damp = atof(e);
    if (const char* e = getenv("MF_LAM_FLOOR")) co2.lam_floor_rel = atof(e);
    if (getenv("MF_TAU_TRACK")) co2.tau_track_lambda = true;
    if (getenv("MF_NO_ALPHA")) co2.use_alpha = false;
    if (getenv("MF_CONSERVATIVE")) co2.conservative_select = true;
    if (getenv("MF_RHO")) co2.rho_lambda = true;
    if (const char* e = getenv("MF_INNER")) {
      std::string s2 = e;
      co2.inner_solver = (s2 == "poba") ? 1 : (s2 == "lsmr") ? 3 : (s2 == "rk") ? 4 : 0;
    }
    if (const char* e = getenv("MF_SKETCH_P0")) co2.sketch_p0 = atof(e);
    if (const char* e = getenv("MF_SKETCH_GROWTH")) co2.sketch_growth = atof(e);
    if (getenv("MF_SHARED_INTR")) co2.shared_intr = true;
    if (const char* e = getenv("MF_KERNEL")) {
      std::string s2 = e;
      if (s2.rfind("huber:", 0) == 0) { co2.robust_kernel = 1; double dd = atof(s2.c_str()+6); co2.robust_scale2 = dd*dd; }
      else if (s2.rfind("cauchy:", 0) == 0) { co2.robust_kernel = 2; double cc = atof(s2.c_str()+7); co2.robust_scale2 = cc*cc; }
      else if (s2.rfind("studentt:", 0) == 0) {  // studentt:<nu>[:<sigma0>], sigma0 px (0/absent = auto)
        co2.robust_kernel = 3; co2.robust_nu = atof(s2.c_str()+9);
        const char* colon = strchr(s2.c_str()+9, ':');
        double sg = colon ? atof(colon+1) : 0.0;
        co2.robust_scale2 = sg > 0 ? co2.robust_nu*sg*sg : 0.0;
      }
    }
    if (const char* e = getenv("MF_CKPT_MAX")) {   // {8,16,...,N} doubling ladder
      co2.cg_checkpoints.clear();
      for (int v = 8; v <= atoi(e); v *= 2) co2.cg_checkpoints.push_back(v);
    }
    const auto t0b = std::chrono::steady_clock::now();
    const oca_cpu::Result r2 = oca_cpu::Solve(cp, co2, &cs2);
    const double sec = std::chrono::duration<double>(std::chrono::steady_clock::now()-t0b).count();
    std::printf("CPU-ONLY: %d iters, %.2fs, cost %.6e -> %.6e (matvecs %ld)\n",
                r2.iterations, sec, r2.initial_cost, r2.final_cost, r2.total_matvecs);
    // MF_DUMP_BAL=path: write the FINAL state as a BAL file, so the endpoint
    // can be handed to another solver (the escape test: is this a genuine
    // local minimum, or a point only MFREE's step cannot leave?).
    if (const char* dump = getenv("MF_DUMP_BAL")) {
      FILE* f = fopen(dump, "w");
      fprintf(f, "%d %d %d\n", b.ncam, b.npt, b.nobs);
      for (int i = 0; i < b.nobs; ++i)
        fprintf(f, "%d %d %.17g %.17g\n", b.cam[i], b.pt[i], b.uv[2*i], b.uv[2*i+1]);
      for (int c = 0; c < b.ncam; ++c) {
        // rotation matrix -> angle-axis (log map)
        const double* R = &Rc2[9*c];
        double tr = R[0]+R[4]+R[8];
        double ct = std::max(-1.0, std::min(1.0, (tr-1.0)*0.5));
        double th = std::acos(ct);
        double w[3];
        if (th < 1e-10) { w[0]=w[1]=w[2]=0.0; }
        else {
          double s2 = 2.0*std::sin(th);
          w[0] = th*(R[7]-R[5])/s2; w[1] = th*(R[2]-R[6])/s2; w[2] = th*(R[3]-R[1])/s2;
        }
        fprintf(f, "%.17g\n%.17g\n%.17g\n%.17g\n%.17g\n%.17g\n%.17g\n%.17g\n%.17g\n",
                w[0], w[1], w[2], tc2[3*c], tc2[3*c+1], tc2[3*c+2],
                fc2[c], k1c2[c], k2c2[c]);
      }
      for (int q = 0; q < b.npt; ++q)
        fprintf(f, "%.17g\n%.17g\n%.17g\n", Xc2[3*q], Xc2[3*q+1], Xc2[3*q+2]);
      fclose(f);
      std::printf("dumped final state to %s\n", dump);
    }
    return 0;
  }

  // ---------------- GPU reference ------------------------------------------
  std::vector<double> Rg = b.R, tg = b.t, Xg = b.X, fg = b.f, k1g = b.k1, k2g = b.k2;
  oca::Problem gp;
  gp.num_cameras = b.ncam; gp.num_points = b.npt; gp.num_observations = b.nobs;
  gp.camera_index = b.cam.data(); gp.point_index = b.pt.data();
  gp.observations = b.uv.data();
  oca::State gs;
  gs.rotations = Rg.data(); gs.translations = tg.data(); gs.points = Xg.data();
  gs.focal = fg.data(); gs.k1 = k1g.data(); gs.k2 = k2g.data();
  const auto tg0 = std::chrono::steady_clock::now();
  const oca::Result gr = oca::Solve(gp, go, &gs);
  const double gpu_s = std::chrono::duration<double>(std::chrono::steady_clock::now()-tg0).count();
  if (!gr.success) { std::printf("GPU solve failed: %s\n", gr.message.c_str()); return 1; }
  if (const char* dump = getenv("MF_DUMP_BAL_GPU"))
    WriteBal(dump, b, Rg, tg, Xg, fg, k1g, k2g);

  // ---------------- CPU port ------------------------------------------------
  std::vector<double> Rc = b.R, tc = b.t, Xc = b.X, fc = b.f, k1c = b.k1, k2c = b.k2;
  oca_cpu::State cs;
  cs.rotations = Rc.data(); cs.translations = tc.data(); cs.points = Xc.data();
  cs.focal = fc.data(); cs.k1 = k1c.data(); cs.k2 = k2c.data();
  const auto tc0 = std::chrono::steady_clock::now();
  const oca_cpu::Result cr = oca_cpu::Solve(cp, co, &cs);
  const double cpu_s = std::chrono::duration<double>(std::chrono::steady_clock::now()-tc0).count();

  // ---------------- T1: initial cost ---------------------------------------
  const double d0 = std::fabs(gr.initial_cost - cr.initial_cost) /
                    std::max(gr.initial_cost, 1e-30);
  Check(d0 < 1e-10, "T1 initial cost GPU vs CPU", d0, 1e-10);

  // ---------------- T3: trajectory -----------------------------------------
  // Iterations 0-1 are DETERMINISTIC parity: every formula in the pipeline
  // feeds them, so they must match at machine precision. Beyond that the two
  // runs are the same algorithm under different fp summation orders (GPU
  // atomics vs CPU deterministic reduction); a ~1e-15 state difference gets
  // amplified until one near-tied candidate/Eisenstat-Walker decision flips
  // (observed: it3, cg depth 1 vs 0), after which the paths RE-CONVERGE.
  // The gates encode that mechanism: bit-parity early, re-convergence late.
  const size_t n = std::min(gr.cost_per_iteration.size(), cr.cost_per_iteration.size());
  double worst_early = 0.0, worst_all = 0.0, last_rel = 0.0;
  for (size_t i = 0; i < n; ++i) {
    const double g = gr.cost_per_iteration[i], c = cr.cost_per_iteration[i];
    const double rel = std::fabs(g - c)/std::max(g, 1e-30);
    if (i <= 1) worst_early = std::max(worst_early, rel);
    worst_all = std::max(worst_all, rel);
    if (i + 1 == n) last_rel = rel;
    if (getenv("MF_VERBOSE"))
      std::printf("    it %2zu  gpu %.10e  cpu %.10e  rel %.2e\n", i, g, c, rel);
  }
  Check(worst_early < 1e-12, "T3a bit-parity, iterations 0-1", worst_early, 1e-12);
  Check(worst_all < 0.15, "T3b transient divergence bounded", worst_all, 0.15);
  // 2e-2, not tighter: on final-4585 (39 rejects, f spanning 325..1.5e10)
  // every reject/retry is a decision a 1e-15 state difference can flip, and
  // the two runs legitimately end ~1.3% apart -- the CPU LOWER. Iteration-0/1
  // bit-parity (T3a) is what certifies algorithmic identity; the endpoint
  // gates only bound the chaos.
  Check(last_rel < 2e-2 && last_rel <= worst_all + 1e-30,
        "T3c paths re-converge (last common iter)", last_rel, 2e-2);

  // ---------------- T4: endpoints ------------------------------------------
  const double df = std::fabs(gr.final_cost - cr.final_cost)/std::max(gr.final_cost, 1e-30);
  Check(df < 2e-2, "T4a final cost", df, 2e-2);
  Check(std::abs(gr.iterations - cr.iterations) <= 2, "T4b iteration count (+-2)",
        std::abs(gr.iterations - cr.iterations), 2);

  std::printf("\nGPU: %d iters, %.2fs, cost %.6e -> %.6e\n",
              gr.iterations, gpu_s, gr.initial_cost, gr.final_cost);
  std::printf("CPU: %d iters, %.2fs, cost %.6e -> %.6e  (matvecs %ld, cand %ld, %d acc/%d rej)\n",
              cr.iterations, cpu_s, cr.initial_cost, cr.final_cost,
              cr.total_matvecs, cr.cand_evals, cr.accepts, cr.rejects);
  std::printf("%s\n", fails == 0 ? "ALL PASS" : "FAILURES");
  return fails == 0 ? 0 : 1;
}
