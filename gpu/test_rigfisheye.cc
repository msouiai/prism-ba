// Gate for oca::SolveRigFisheye: synthetic dual-fisheye rig, exact
// observations, perturbed state. With zero observation noise the ground truth
// is exactly recoverable, so the test demands a large cost reduction and
// near-zero final cost -- any convention error (rig composition order,
// +z sign, intrinsics layout) fails loudly rather than "converging" to a
// slightly wrong optimum.
//
// Second half: constant blocks, the vocabulary COLMAP's local bundle
// adjustment speaks (out-of-bundle frames, sensor_from_rig, per-camera
// intrinsics and long-track points held). Held blocks start at the truth and
// must come back bit-identical; the free blocks start perturbed and must still
// recover exactly, with no gauge pin at all -- the constant blocks fix it.
//
// Layout mirrors the Insta360 X4 capture this path exists for: sensor 0 is
// the identity (reference lens), sensor 1 is a 180-degree yaw with a small
// baseline; each frame contributes one image per sensor.
#include "oca_core.h"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <random>
#include <vector>

namespace {

void Rz180(double* R) {  // 180-degree yaw: diag(-1,-1,1)
  for (int i = 0; i < 9; ++i) R[i] = 0.0;
  R[0] = -1.0; R[4] = -1.0; R[8] = 1.0;
}
void Rident(double* R) {
  for (int i = 0; i < 9; ++i) R[i] = 0.0;
  R[0] = R[4] = R[8] = 1.0;
}
void RotZYX(double a, double b, double c, double* R) {
  double ca = std::cos(a), sa = std::sin(a), cb = std::cos(b), sb = std::sin(b),
         cc = std::cos(c), sc = std::sin(c);
  R[0] = ca * cb; R[1] = ca * sb * sc - sa * cc; R[2] = ca * sb * cc + sa * sc;
  R[3] = sa * cb; R[4] = sa * sb * sc + ca * cc; R[5] = sa * sb * cc - ca * sc;
  R[6] = -sb;     R[7] = cb * sc;                R[8] = cb * cc;
}
void MatMul(const double* A, const double* B, double* C) {
  for (int r = 0; r < 3; ++r)
    for (int c = 0; c < 3; ++c)
      C[3*r+c] = A[3*r]*B[c] + A[3*r+1]*B[3+c] + A[3*r+2]*B[6+c];
}

bool Project(const double* Rc, const double* tc, const double* X,
             const double* in, double* u, double* v) {
  double P[3];
  for (int r = 0; r < 3; ++r)
    P[r] = Rc[3*r]*X[0] + Rc[3*r+1]*X[1] + Rc[3*r+2]*X[2] + tc[r];
  if (P[2] < 0.05) return false;
  double nu = P[0]/P[2], nv = P[1]/P[2];
  double r = std::sqrt(nu*nu + nv*nv + 1e-32);
  double th = std::atan(r);
  if (th > 1.45) return false;  // stay inside the fisheye mask (~83 deg)
  double s = th/r, th2 = th*th;
  double d = 1 + th2*(in[4] + th2*(in[5] + th2*(in[6] + th2*in[7])));
  *u = in[0]*d*s*nu + in[2];
  *v = in[1]*d*s*nv + in[3];
  return true;
}

}  // namespace

int main() {
  if (!oca::IsAvailable()) { std::printf("SKIP: no CUDA device\n"); return 0; }
  const int kFrames = 12, kSensors = 2, kCalib = 2, kPoints = 400;
  std::mt19937 rng(7);
  std::uniform_real_distribution<double> U(-1.0, 1.0);

  // Ground truth ---------------------------------------------------------
  std::vector<double> Rs(9*kSensors), ts(3*kSensors, 0.0);
  Rident(&Rs[0]); Rz180(&Rs[9]);
  ts[3] = 0.02;  // 2 cm baseline on the back lens

  std::vector<double> Rf(9*kFrames), tf(3*kFrames);
  for (int f = 0; f < kFrames; ++f) {
    RotZYX(0.15*U(rng), 0.15*U(rng), 0.15*U(rng), &Rf[9*f]);
    tf[3*f]   = 0.4*f + 0.2*U(rng);
    tf[3*f+1] = 0.2*U(rng);
    tf[3*f+2] = 0.2*U(rng);
  }
  // Fuchsberg-like intrinsics, slightly different per lens.
  std::vector<double> intr = {533.0, 533.7, 961.1, 963.5, 0.081, -0.032, 0.012, -0.003,
                              533.9, 534.7, 959.8, 961.5, 0.082, -0.033, 0.012, -0.003};
  // Points surrounding the trajectory in all directions, so BOTH lenses see.
  std::vector<double> X(3*kPoints);
  for (int i = 0; i < kPoints; ++i) {
    double az = 3.14159265 * U(rng), el = 1.2 * U(rng), rad = 3.0 + 2.0*U(rng);
    X[3*i]   = 0.4*kFrames*0.5 + rad*std::cos(el)*std::cos(az);
    X[3*i+1] = rad*std::cos(el)*std::sin(az);
    X[3*i+2] = rad*std::sin(el);
  }

  // Exact observations ----------------------------------------------------
  std::vector<int> frame_of, sensor_of, calib_of;
  std::vector<int> obs_cam, obs_pt;
  std::vector<double> obs_uv;
  int ncam = 0;
  std::vector<double> Rc(9), tc(3);
  for (int f = 0; f < kFrames; ++f)
    for (int s = 0; s < kSensors; ++s) {
      MatMul(&Rs[9*s], &Rf[9*f], Rc.data());
      for (int r = 0; r < 3; ++r)
        tc[r] = Rs[9*s+3*r]*tf[3*f] + Rs[9*s+3*r+1]*tf[3*f+1] + Rs[9*s+3*r+2]*tf[3*f+2] + ts[3*s+r];
      int nvis = 0;
      for (int i = 0; i < kPoints; ++i) {
        double u, v;
        if (!Project(Rc.data(), tc.data(), &X[3*i], &intr[8*s], &u, &v)) continue;
        obs_cam.push_back(ncam); obs_pt.push_back(i);
        obs_uv.push_back(u); obs_uv.push_back(v); ++nvis;
      }
      frame_of.push_back(f); sensor_of.push_back(s); calib_of.push_back(s);
      ++ncam;
      if (nvis < 20) { std::printf("FAIL: sensor %d frame %d sees only %d pts\n", s, f, nvis); return 1; }
    }
  const int nobs = (int)obs_pt.size();
  std::printf("synthetic rig: %d frames x %d sensors = %d images, %d pts, %d obs\n",
              kFrames, kSensors, ncam, kPoints, nobs);

  // Perturb everything the solver may move ---------------------------------
  std::vector<double> Rf_n = Rf, tf_n = tf, X_n = X, intr_n = intr;
  for (int f = 0; f < kFrames; ++f) {
    double dR[9], tmp[9];
    RotZYX(0.02*U(rng), 0.02*U(rng), 0.02*U(rng), dR);
    MatMul(dR, &Rf[9*f], tmp);
    for (int i = 0; i < 9; ++i) Rf_n[9*f+i] = tmp[i];
    for (int r = 0; r < 3; ++r) tf_n[3*f+r] += 0.03*U(rng);
  }
  for (int i = 0; i < 3*kPoints; ++i) X_n[i] += 0.05*U(rng);
  for (int g = 0; g < kCalib; ++g) {
    intr_n[8*g]   += 5.0*U(rng); intr_n[8*g+1] += 5.0*U(rng);
    intr_n[8*g+2] += 3.0*U(rng); intr_n[8*g+3] += 3.0*U(rng);
    intr_n[8*g+4] += 0.01*U(rng);
  }

  oca::RigFisheyeProblem prob;
  prob.num_images = ncam; prob.num_frames = kFrames; prob.num_sensors = kSensors;
  prob.num_calibrations = kCalib; prob.num_points = kPoints; prob.num_observations = nobs;
  prob.frame_of_image = frame_of.data(); prob.sensor_of_image = sensor_of.data();
  prob.calibration_of_image = calib_of.data();
  prob.camera_index = obs_cam.data(); prob.point_index = obs_pt.data();
  prob.observations = obs_uv.data();

  // Perturb the back lens's sensor_from_rig too: 1.5 degrees of yaw error and
  // a wrong baseline (the Insta360 starting condition: the rig config guesses
  // 180 deg / zero baseline, and BA must find the truth).
  std::vector<double> Rs_n = Rs, ts_n = ts;
  {
    double dR[9], tmp[9];
    RotZYX(0.025, 0.01, -0.015, dR);
    MatMul(dR, &Rs[9], tmp);
    for (int i = 0; i < 9; ++i) Rs_n[9 + i] = tmp[i];
    ts_n[3] = 0.0; ts_n[4] = 0.01; ts_n[5] = -0.01;  // baseline zeroed + junk
  }

  oca::RigFisheyeState st;
  st.frame_rotations = Rf_n.data(); st.frame_translations = tf_n.data();
  st.sensor_rotations = Rs_n.data(); st.sensor_translations = ts_n.data();
  st.intrinsics = intr_n.data(); st.points = X_n.data();

  oca::RigFisheyeOptions opt;
  opt.max_iterations = 60;
  opt.refine_sensor_from_rig = true;
  opt.verbose = getenv("RF_VERBOSE") != nullptr;

  oca::Result res = oca::SolveRigFisheye(prob, opt, &st);
  if (!res.success) { std::printf("FAIL: %s\n", res.message.c_str()); return 1; }
  double drop = res.initial_cost / std::max(res.final_cost, 1e-300);
  std::printf("cost %.6e -> %.6e  (x%.1e reduction, %d iterations)\n",
              res.initial_cost, res.final_cost, drop, res.iterations);
  std::printf("lens0 fx: true %.3f  recovered %.3f\n", intr[0], intr_n[0]);
  std::printf("lens0 cx: true %.3f  recovered %.3f\n", intr[2], intr_n[2]);
  std::printf("lens1 k1: true %.5f  recovered %.5f\n", intr[12], intr_n[12]);
  std::printf("sensor baseline: true (%.4f %.4f %.4f)  recovered (%.4f %.4f %.4f)\n",
              ts[3], ts[4], ts[5], ts_n[3], ts_n[4], ts_n[5]);
  // Exact data: demand near-total recovery, not a soft "it went down".
  bool ok = res.final_cost < 1e-6 * res.initial_cost &&
            std::abs(intr_n[0] - intr[0]) < 0.5 &&
            std::abs(intr_n[2] - intr[2]) < 0.5 &&
            std::abs(intr_n[12] - intr[12]) < 1e-3 &&
            std::abs(ts_n[3] - ts[3]) < 2e-3 &&
            std::abs(ts_n[4] - ts[4]) < 2e-3 &&
            std::abs(ts_n[5] - ts[5]) < 2e-3;
  std::printf("%s\n", ok ? "PASS" : "FAIL");
  if (!ok) return 1;

  // Constant blocks ---------------------------------------------------------
  // Three configurations, each solved without gauge_frame: the constant
  // blocks alone must fix the gauge, as in a mapper local BA.
  //   A  frames 0..3 constant (an out-of-bundle neighbourhood), sensor
  //      constant, lens 1 constant, every third point constant;
  //   B  only points constant (one in three), everything else free;
  //   C  only frames 0 and 1 constant -- two constant frames fix the gauge.
  struct Config { const char* name; bool frames, sensor, calib, points; };
  const Config configs[] = {{"A frames+sensor+lens1+points", true, true, true, true},
                            {"B points only", false, false, false, true},
                            {"C two frames only", true, false, false, false}};
  for (const Config& cfg : configs) {
    std::vector<unsigned char> fc(kFrames, 0), sc(kSensors, 0), cc(kCalib, 0),
        pc(kPoints, 0);
    const int n_const_frames = cfg.name[0] == 'C' ? 2 : 4;
    if (cfg.frames) for (int f = 0; f < n_const_frames; ++f) fc[f] = 1;
    if (cfg.sensor) sc[1] = 1;
    if (cfg.calib) cc[1] = 1;
    if (cfg.points) for (int i = 0; i < kPoints; i += 3) pc[i] = 1;

    // Truth in the held blocks, the earlier perturbation in the free ones.
    std::vector<double> Rf_c = Rf_n, tf_c = tf_n, X_c = X_n, intr_c = intr_n;
    std::vector<double> Rs_c = Rs_n, ts_c = ts_n;
    for (int f = 0; f < kFrames; ++f)
      if (fc[f]) {
        for (int i = 0; i < 9; ++i) Rf_c[9*f+i] = Rf[9*f+i];
        for (int r = 0; r < 3; ++r) tf_c[3*f+r] = tf[3*f+r];
      }
    if (sc[1]) { Rs_c = Rs; ts_c = ts; }
    if (cc[1]) for (int j = 0; j < 8; ++j) intr_c[8+j] = intr[8+j];
    for (int i = 0; i < kPoints; ++i)
      if (pc[i]) for (int r = 0; r < 3; ++r) X_c[3*i+r] = X[3*i+r];
    const std::vector<double> Rf_0 = Rf_c, tf_0 = tf_c, X_0 = X_c, intr_0 = intr_c,
        Rs_0 = Rs_c, ts_0 = ts_c;

    oca::RigFisheyeProblem pc_prob = prob;
    pc_prob.frame_constant = cfg.frames ? fc.data() : nullptr;
    pc_prob.sensor_constant = cfg.sensor ? sc.data() : nullptr;
    pc_prob.calibration_constant = cfg.calib ? cc.data() : nullptr;
    pc_prob.point_constant = cfg.points ? pc.data() : nullptr;
    oca::RigFisheyeState sc_state;
    sc_state.frame_rotations = Rf_c.data(); sc_state.frame_translations = tf_c.data();
    sc_state.sensor_rotations = Rs_c.data(); sc_state.sensor_translations = ts_c.data();
    sc_state.intrinsics = intr_c.data(); sc_state.points = X_c.data();
    oca::RigFisheyeOptions copt = opt;
    copt.gauge_frame = -1;
    copt.gauge_scale_frame = -1;

    oca::Result cres = oca::SolveRigFisheye(pc_prob, copt, &sc_state);
    if (!cres.success) { std::printf("FAIL [%s]: %s\n", cfg.name, cres.message.c_str()); return 1; }
    std::printf("[%s] cost %.6e -> %.6e (%d iterations)\n", cfg.name,
                cres.initial_cost, cres.final_cost, cres.iterations);

    // Held blocks: bit-identical. Free blocks: recovered.
    bool held = true;
    for (int f = 0; f < kFrames; ++f)
      if (fc[f]) {
        for (int i = 0; i < 9; ++i) held &= Rf_c[9*f+i] == Rf_0[9*f+i];
        for (int r = 0; r < 3; ++r) held &= tf_c[3*f+r] == tf_0[3*f+r];
      }
    if (sc[1]) { held &= Rs_c == Rs_0; held &= ts_c == ts_0; }
    if (cc[1]) for (int j = 0; j < 8; ++j) held &= intr_c[8+j] == intr_0[8+j];
    for (int i = 0; i < kPoints; ++i)
      if (pc[i]) for (int r = 0; r < 3; ++r) held &= X_c[3*i+r] == X_0[3*i+r];
    // Points are checked only where the data determines them: seen from at
    // least two frames (0.4 apart). Roughly half of the synthetic points sit
    // behind the lenses and are never observed (they simply keep their
    // perturbation), and a point seen from one frame alone is constrained by
    // the 2 cm rig baseline only -- the first half of this gate never looked
    // at per-point recovery for the same reason.
    double max_t = 0.0, max_x = 0.0;
    int n_checked = 0, n_unobserved = 0;
    for (int f = 0; f < kFrames; ++f)
      for (int r = 0; r < 3; ++r) max_t = std::max(max_t, std::abs(tf_c[3*f+r] - tf[3*f+r]));
    {
      std::vector<int> first_frame(kPoints, -1), n_frames(kPoints, 0);
      for (int o = 0; o < nobs; ++o) {
        const int i = obs_pt[o], f = frame_of[obs_cam[o]];
        if (first_frame[i] < 0) { first_frame[i] = f; n_frames[i] = 1; }
        else if (first_frame[i] != f) n_frames[i] = 2;
      }
      for (int i = 0; i < kPoints; ++i) {
        if (n_frames[i] == 0) ++n_unobserved;
        if (n_frames[i] < 2) continue;
        ++n_checked;
        for (int r = 0; r < 3; ++r) max_x = std::max(max_x, std::abs(X_c[3*i+r] - X[3*i+r]));
      }
    }
    const bool cok = held && cres.final_cost < 1e-6 * cres.initial_cost &&
                     max_t < 2e-3 && max_x < 5e-3 && n_checked >= 100 &&
                     std::abs(intr_c[0] - intr[0]) < 0.5 &&
                     std::abs(intr_c[12] - intr[12]) < 1e-3 &&
                     std::abs(ts_c[3] - ts[3]) < 2e-3;
    std::printf("[%s] held blocks unchanged: %s; max |dt| %.2e, max |dX| %.2e over %d "
                "multi-frame points (%d unobserved), lens0 fx %.3f, lens1 k1 %.5f, "
                "baseline x %.4f -> %s\n",
                cfg.name, held ? "yes" : "NO", max_t, max_x, n_checked, n_unobserved,
                intr_c[0], intr_c[12], ts_c[3], cok ? "PASS" : "FAIL");
    if (!cok) return 1;
  }
  std::printf("PASS (constant blocks)\n");

  // Pinhole family -----------------------------------------------------------
  // A SIMPLE_RADIAL camera without a rig (frame == image, sensor 0 identity),
  // the Muellcontainer layout. calibration_model selects the x/z projection
  // with a tied focal length; k2 is masked off through calibration_param_mask
  // and k3/k4 by the model. Two constant frames fix the gauge. Exact data
  // again: f, cx, k1 and the free poses must come back, fy must equal fx and
  // the masked parameters must not move.
  {
    const int kPF = 16, kPP = 500;
    std::vector<double> pRf(9*kPF), ptf(3*kPF);
    for (int f = 0; f < kPF; ++f) {
      RotZYX(0.3*U(rng), 0.3*U(rng), 0.3*U(rng), &pRf[9*f]);
      ptf[3*f] = 0.3*f + 0.1*U(rng); ptf[3*f+1] = 0.1*U(rng); ptf[3*f+2] = 0.1*U(rng);
    }
    // Points 2..12 m in front of the cameras, spread across a 75-deg cone.
    std::vector<double> pX(3*kPP);
    for (int i = 0; i < kPP; ++i) {
      const double z = 2.0 + 10.0*(0.5 + 0.5*U(rng));
      pX[3*i] = 0.3*kPF*0.5 + 0.55*z*U(rng); pX[3*i+1] = 0.55*z*U(rng); pX[3*i+2] = z;
    }
    // [fx fy cx cy k1 k2 k3 k4]: SIMPLE_RADIAL 1296/960/540/0.0153 (Frank's camera).
    std::vector<double> pin = {1296.0, 1296.0, 960.0, 540.0, 0.0153, 0.0, 0.0, 0.0};
    std::vector<int> pframe_of, psensor_of, pcalib_of, pobs_cam, pobs_pt;
    std::vector<double> pobs_uv;
    std::vector<double> pRs = {1,0,0, 0,1,0, 0,0,1}, pts = {0,0,0};
    for (int f = 0; f < kPF; ++f) {
      int nvis = 0;
      for (int i = 0; i < kPP; ++i) {
        double P[3];
        for (int r = 0; r < 3; ++r)
          P[r] = pRf[9*f+3*r]*pX[3*i] + pRf[9*f+3*r+1]*pX[3*i+1] + pRf[9*f+3*r+2]*pX[3*i+2] + ptf[3*f+r];
        if (P[2] < 0.5) continue;
        const double x = P[0]/P[2], y = P[1]/P[2], r2 = x*x + y*y;
        if (r2 > 0.6) continue;
        const double d = 1.0 + pin[4]*r2;
        pobs_cam.push_back(f); pobs_pt.push_back(i);
        pobs_uv.push_back(pin[0]*d*x + pin[2]); pobs_uv.push_back(pin[1]*d*y + pin[3]);
        ++nvis;
      }
      pframe_of.push_back(f); psensor_of.push_back(0); pcalib_of.push_back(0);
      if (nvis < 30) { std::printf("FAIL: pinhole frame %d sees only %d pts\n", f, nvis); return 1; }
    }
    const int pnobs = (int)pobs_pt.size();
    std::printf("synthetic pinhole: %d images, %d pts, %d obs\n", kPF, kPP, pnobs);

    std::vector<double> Rf_p = pRf, tf_p = ptf, X_p = pX, in_p = pin;
    std::vector<unsigned char> fc(kPF, 0); fc[0] = fc[1] = 1;
    for (int f = 2; f < kPF; ++f) {
      double dR[9], tmp[9];
      RotZYX(0.01*U(rng), 0.01*U(rng), 0.01*U(rng), dR);
      MatMul(dR, &pRf[9*f], tmp);
      for (int i = 0; i < 9; ++i) Rf_p[9*f+i] = tmp[i];
      for (int r = 0; r < 3; ++r) tf_p[3*f+r] += 0.02*U(rng);
    }
    for (int i = 0; i < 3*kPP; ++i) X_p[i] += 0.03*U(rng);
    in_p[0] = in_p[1] = pin[0] + 8.0; in_p[2] += 4.0; in_p[3] -= 3.0; in_p[4] = 0.0;

    const int model = oca::RIG_MODEL_PINHOLE | oca::RIG_MODEL_TIED_FOCAL;
    const unsigned char pmask[8] = {1, 1, 1, 1, 1, 0, 0, 0};
    oca::RigFisheyeProblem pp;
    pp.num_images = kPF; pp.num_frames = kPF; pp.num_sensors = 1;
    pp.num_calibrations = 1; pp.num_points = kPP; pp.num_observations = pnobs;
    pp.frame_of_image = pframe_of.data(); pp.sensor_of_image = psensor_of.data();
    pp.calibration_of_image = pcalib_of.data();
    pp.camera_index = pobs_cam.data(); pp.point_index = pobs_pt.data();
    pp.observations = pobs_uv.data();
    pp.frame_constant = fc.data();
    pp.calibration_model = &model;
    pp.calibration_param_mask = pmask;
    oca::RigFisheyeState ps;
    ps.frame_rotations = Rf_p.data(); ps.frame_translations = tf_p.data();
    ps.sensor_rotations = pRs.data(); ps.sensor_translations = pts.data();
    ps.intrinsics = in_p.data(); ps.points = X_p.data();
    oca::RigFisheyeOptions popt;
    popt.max_iterations = 100;
    popt.verbose = getenv("RF_VERBOSE") != nullptr;
    oca::Result pres = oca::SolveRigFisheye(pp, popt, &ps);
    if (!pres.success) { std::printf("FAIL [pinhole]: %s\n", pres.message.c_str()); return 1; }
    double max_t = 0.0;
    for (int f = 0; f < kPF; ++f)
      for (int r = 0; r < 3; ++r) max_t = std::max(max_t, std::abs(tf_p[3*f+r] - ptf[3*f+r]));
    const bool pok = pres.final_cost < 1e-6 * pres.initial_cost &&
                     std::abs(in_p[0] - pin[0]) < 0.3 && in_p[1] == in_p[0] &&
                     std::abs(in_p[2] - pin[2]) < 0.3 && std::abs(in_p[3] - pin[3]) < 0.3 &&
                     std::abs(in_p[4] - pin[4]) < 1e-4 &&
                     in_p[5] == 0.0 && in_p[6] == 0.0 && in_p[7] == 0.0 && max_t < 2e-3;
    std::printf("[pinhole SIMPLE_RADIAL] cost %.6e -> %.6e (%d its), f %.3f (fy %.3f) cx %.3f cy %.3f "
                "k1 %.5f k2..k4 %g %g %g, max |dt| %.2e -> %s\n",
                pres.initial_cost, pres.final_cost, pres.iterations, in_p[0], in_p[1], in_p[2],
                in_p[3], in_p[4], in_p[5], in_p[6], in_p[7], max_t, pok ? "PASS" : "FAIL");
    if (!pok) return 1;
  }
  return 0;
}
