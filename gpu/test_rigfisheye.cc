// Gate for oca::SolveRigFisheye: synthetic dual-fisheye rig, exact
// observations, perturbed state. With zero observation noise the ground truth
// is exactly recoverable, so the test demands a large cost reduction and
// near-zero final cost -- any convention error (rig composition order,
// +z sign, intrinsics layout) fails loudly rather than "converging" to a
// slightly wrong optimum.
//
// Layout mirrors the Insta360 X4 capture this path exists for: sensor 0 is
// the identity (reference lens), sensor 1 is a 180-degree yaw with a small
// baseline; each frame contributes one image per sensor.
#include "oca_core.h"

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
  return ok ? 0 : 1;
}
