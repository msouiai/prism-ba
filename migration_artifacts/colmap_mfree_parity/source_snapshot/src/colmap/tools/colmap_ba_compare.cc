// Copyright (c), ETH Zurich and UNC Chapel Hill.
// All rights reserved.
//
// Redistribution and use in source and binary forms, with or without
// modification, are permitted provided that the following conditions are met:
//
//     * Redistributions of source code must retain the above copyright
//       notice, this list of conditions and the following disclaimer.
//
//     * Redistributions in binary form must reproduce the above copyright
//       notice, this list of conditions and the following disclaimer in the
//       documentation and/or other materials provided with the distribution.
//
//     * Neither the name of ETH Zurich and UNC Chapel Hill nor the names of
//       its contributors may be used to endorse or promote products derived
//       from this software without specific prior written permission.
//
// THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
// AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
// IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
// ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDERS OR CONTRIBUTORS BE
// LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
// CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
// SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
// INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
// CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
// ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
// POSSIBILITY OF SUCH DAMAGE.
//
// Loads a real COLMAP reconstruction, perturbs it (so there is actual
// optimization work to do -- the source reconstruction is already converged),
// then runs COLMAP's own BundleAdjuster (via CreateDefaultBundleAdjuster,
// COLMAP's real production entry point -- not a reimplementation) with
// backend=CERES and, if built with -DCASPAR_ENABLED=ON, backend=CASPAR, both
// starting from the identical perturbed state. Also writes that perturbed
// state to disk so it can be exported to BAL and run through the
// DABA-MM CUDA tool (../daba_cuda/daba_mm.cu) for a three-way comparison on
// the exact same problem.

#include "colmap/estimators/bundle_adjustment.h"
#include "colmap/estimators/bundle_adjustment_ceres.h"
#include "colmap/estimators/bundle_adjustment_mfree.h"
#include "colmap/geometry/pose.h"
#include "colmap/geometry/rigid3.h"
#include "colmap/scene/reconstruction.h"
#include "colmap/scene/synthetic.h"
#include "colmap/scene/track.h"
#include "colmap/sensor/models.h"
#include "colmap/util/logging.h"

#include <ceres/iteration_callback.h>

#include <algorithm>
#include <chrono>
#include <cstdio>
#include <filesystem>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <string>
#include <unordered_map>
#include <vector>

using namespace colmap;

namespace {
double ElapsedSeconds(std::chrono::steady_clock::time_point t0) {
  return std::chrono::duration<double>(std::chrono::steady_clock::now() - t0)
      .count();
}

// Reconstruction::ComputeMeanReprojectionError() is not robust to cheirality
// violations: CalculateSquaredReprojectionError() returns
// std::numeric_limits<double>::max() for any observation that fails the
// cheirality check (point behind the camera), so a single such point makes the
// naive mean meaningless (sqrt(DBL_MAX) =~ 1.34e154, dwarfing every other
// point). This is not a bug in the loader below -- raw/uncurated real BAL
// problems (unlike our synthetic or already-triangulated-by-COLMAP inputs) can
// genuinely contain points initialized behind a camera; Ceres' own cost
// functor isn't cheirality-gated and optimizes through them fine (that's why
// Ceres' own "Initial cost" stays sane even when this metric doesn't). Report
// the median instead, which one outlier can't blow up, plus how many points
// are affected so it's visible rather than silently swept in.
double ComputeMedianReprojectionError(const Reconstruction& reconstruction) {
  std::vector<double> errors;
  errors.reserve(reconstruction.NumPoints3D());
  for (const auto& [_, point3D] : reconstruction.Points3D()) {
    if (point3D.track.Length() > 0) errors.push_back(point3D.error);
  }
  if (errors.empty()) return 0.0;
  std::nth_element(errors.begin(), errors.begin() + errors.size() / 2,
                    errors.end());
  return errors[errors.size() / 2];
}

size_t CountCheiralityViolations(const Reconstruction& reconstruction) {
  size_t count = 0;
  for (const auto& [_, point3D] : reconstruction.Points3D()) {
    if (point3D.error > 1e100) ++count;
  }
  return count;
}

// COLMAP -> BAL export, same convention as multishift-bundle-adjustment's
// colmap_to_bal.py (re-derived here directly against the C++ Reconstruction
// API rather than pulling in pycolmap as a new dependency):
//   COLMAP: x_cam = R*x_world + t, camera looks down +z, pixel y down
//   BAL:    P = R*X + t, camera looks down -z, y up
//   => R_bal = diag(1,-1,-1) @ R_colmap, t_bal = diag(1,-1,-1) @ t_colmap
//   => u_bal = x_px - cx, v_bal = -(y_px - cy)
// RADIAL (f, cx, cy, k1, k2) -> BAL's (f, k1, k2) is an exact reproduction of
// that model (both use dist=1+k1*r^2+k2*r^4), not an approximation. SIMPLE_RADIAL
// (f, cx, cy, k) -> BAL's (f, k1=k, k2=0) is exact too (k2 genuinely absent from
// the source model, not dropped). PINHOLE (fx, fy, cx, cy) -> BAL's (f=fx,
// k1=0, k2=0) is exact only when fx==fy (checked below and warned if not, since
// BAL has no separate fx/fy) -- added so datasets undistorted from a camera
// model BAL/daba_mm can't represent natively (e.g. OPENCV_FISHEYE via
// undistort_reconstruction) can still be exported.
void WriteBal(const Reconstruction& reconstruction,
              const std::filesystem::path& path) {
  const Eigen::Matrix3d flip = Eigen::Vector3d(1, -1, -1).asDiagonal();

  std::vector<image_t> image_ids;
  for (const image_t image_id : reconstruction.RegImageIds()) {
    const Camera& camera = *reconstruction.Image(image_id).CameraPtr();
    if (camera.model_id != SimpleRadialCameraModel::model_id &&
        camera.model_id != RadialCameraModel::model_id &&
        camera.model_id != PinholeCameraModel::model_id) {
      std::fprintf(stderr,
                   "WriteBal: skipping BAL export -- image %u has camera "
                   "model %s, only RADIAL/SIMPLE_RADIAL/PINHOLE are supported\n",
                   image_id, CameraModelIdToName(camera.model_id).c_str());
      return;
    }
    if (camera.model_id == PinholeCameraModel::model_id) {
      const double fx = camera.params[0], fy = camera.params[1];
      if (std::abs(fx - fy) > 1e-3 * std::max(fx, fy)) {
        std::fprintf(stderr,
                     "WriteBal: warning -- camera %u is PINHOLE with "
                     "fx=%.6f != fy=%.6f, BAL has no separate fx/fy; using "
                     "fx and accepting the small approximation\n",
                     image_id, fx, fy);
      }
    }
    image_ids.push_back(image_id);
  }
  std::unordered_map<image_t, int> image_to_cam_idx;
  for (size_t i = 0; i < image_ids.size(); ++i) image_to_cam_idx[image_ids[i]] = (int)i;

  std::unordered_map<point3D_t, int> point_to_idx;
  std::vector<point3D_t> point_ids;
  for (const auto& [point3D_id, point3D] : reconstruction.Points3D()) {
    if (point3D.track.Length() == 0) continue;
    point_to_idx[point3D_id] = (int)point_ids.size();
    point_ids.push_back(point3D_id);
  }

  // (f, cx, cy, k1, k2) regardless of whether the source is RADIAL
  // (params = [f, cx, cy, k1, k2]), SIMPLE_RADIAL (params = [f, cx, cy, k1],
  // k2=0), or PINHOLE (params = [fx, fy, cx, cy], k1=k2=0, fx used per the
  // fx==fy check/warning above).
  auto FCxCyK = [](const Camera& camera) -> std::array<double, 5> {
    if (camera.model_id == PinholeCameraModel::model_id) {
      return {camera.params[0], camera.params[2], camera.params[3], 0.0, 0.0};
    }
    if (camera.model_id == RadialCameraModel::model_id) {
      return {camera.params[0], camera.params[1], camera.params[2],
              camera.params[3], camera.params[4]};
    }
    return {camera.params[0], camera.params[1], camera.params[2],
            camera.params[3], 0.0};
  };

  struct Obs { int cam_idx, pt_idx; double u, v; };
  std::vector<Obs> obs;
  for (const image_t image_id : image_ids) {
    const Image& image = reconstruction.Image(image_id);
    const Camera& camera = *image.CameraPtr();
    const auto [f, cx, cy, k1, k2] = FCxCyK(camera);
    (void)f; (void)k1; (void)k2;
    for (const auto& p2d : image.Points2D()) {
      if (!p2d.HasPoint3D()) continue;
      auto it = point_to_idx.find(p2d.point3D_id);
      if (it == point_to_idx.end()) continue;
      obs.push_back({image_to_cam_idx.at(image_id), it->second,
                      p2d.xy.x() - cx, -(p2d.xy.y() - cy)});
    }
  }

  std::ofstream fh(path);
  fh.precision(9);
  fh << image_ids.size() << " " << point_ids.size() << " " << obs.size() << "\n";
  for (const auto& o : obs) {
    fh << o.cam_idx << " " << o.pt_idx << " " << o.u << " " << o.v << "\n";
  }
  for (const image_t image_id : image_ids) {
    const Image& image = reconstruction.Image(image_id);
    const Camera& camera = *image.CameraPtr();
    const Rigid3d cam_from_world = image.CamFromWorld();
    const Eigen::Matrix3d R_bal = flip * cam_from_world.rotation().toRotationMatrix();
    const Eigen::Vector3d t_bal = flip * cam_from_world.translation();
    const Eigen::Vector3d aa = RotationMatrixToAngleAxis(R_bal);
    const auto [f, cx, cy, k1, k2] = FCxCyK(camera);
    (void)cx; (void)cy;
    fh << aa.x() << " " << aa.y() << " " << aa.z() << " " << t_bal.x() << " "
       << t_bal.y() << " " << t_bal.z() << " " << f << " "
       << k1 << " " << k2 << "\n";
  }
  for (const point3D_t point_id : point_ids) {
    const Eigen::Vector3d& xyz = reconstruction.Point3D(point_id).xyz;
    fh << xyz.x() << " " << xyz.y() << " " << xyz.z() << "\n";
  }
  std::printf("wrote BAL export to %s (%zu cams, %zu pts, %zu obs)\n",
              path.string().c_str(), image_ids.size(), point_ids.size(), obs.size());
}

// Loads a real (not synthetic) BAL-format problem as a COLMAP Reconstruction so it
// runs through the exact same CreateDefaultBundleAdjuster path as everything else in
// this tool. Inverse of WriteBal above -- same flip convention (BAL looks down -z,
// y up; COLMAP looks down +z, y down), 0-indexed cam_idx/pt_idx (Snavely/BAL
// convention, same as daba_mm.cu's own loader). Uses RadialCameraModel (f, cx, cy,
// k1, k2) -- COLMAP's two-parameter radial model, params-for-params identical to
// BAL's own distortion polynomial (dist = 1 + k1*r^2 + k2*r^4, verified against
// RadialCameraModel::Distortion in sensor/models.h) -- so k2 is no longer dropped.
// An earlier version of this function used SimpleRadialCameraModel (k1 only,
// k2 silently discarded); that was fine for venice-1778 (max|k2| ~5 orders of
// magnitude below max|k1| there) but not in general, and made Ceres/Caspar solve
// a strictly easier problem than every other solver in this investigation, which
// all use the full k1+k2 BAL model -- caught when an independently-built CUDA
// solver's own diagnostics (median reprojection error) didn't match this tool's,
// on the identical nominal input.
Reconstruction ReadBal(const std::filesystem::path& path) {
  std::ifstream fh(path);
  THROW_CHECK(fh.good()) << "failed to open " << path;

  int ncam = 0, npt = 0, nobs = 0;
  fh >> ncam >> npt >> nobs;

  if (std::getenv("COLMAP_BAL_SIMPLE_RADIAL"))
    std::printf("BAL loader: SIMPLE_RADIAL mapping (k2 dropped) -- Caspar-compatible\n");
  else
    std::printf("BAL loader: RADIAL mapping (exact k1+k2) -- Caspar will skip all images\n");
  std::vector<int> obs_cam(nobs), obs_pt(nobs);
  std::vector<double> obs_u(nobs), obs_v(nobs);
  for (int i = 0; i < nobs; ++i) {
    fh >> obs_cam[i] >> obs_pt[i] >> obs_u[i] >> obs_v[i];
  }
  std::vector<double> cam_params(9 * ncam);
  for (double& v : cam_params) fh >> v;
  std::vector<double> pts(3 * npt);
  for (double& v : pts) fh >> v;
  THROW_CHECK(!fh.fail() || fh.eof()) << "malformed BAL file " << path;

  const Eigen::Matrix3d flip = Eigen::Vector3d(1, -1, -1).asDiagonal();

  Reconstruction reconstruction;

  // Cameras (+ trivial rigs), one per BAL camera -- BAL has no shared intrinsics.
  for (int c = 0; c < ncam; ++c) {
    Camera camera;
    camera.camera_id = static_cast<camera_t>(c + 1);
    // RADIAL (f,cx,cy,k1,k2) is the exact BAL model and the default. But Caspar's
    // adapter implements only SimpleRadial/Pinhole, so it skips every image under
    // RADIAL. Env COLMAP_BAL_SIMPLE_RADIAL=1 opts into the SIMPLE_RADIAL (f,cx,cy,k1)
    // mapping, which Caspar CAN run, at the cost of dropping k2. Measured cost of
    // that approximation on venice-1672/1778 and final-3068/4585/13682:
    // median |k2/k1| ~ 2e-7, and the initial median reprojection error is identical
    // to 4 decimal places with and without k2. Opt-in and logged, never silent.
    const bool bal_simple_radial = std::getenv("COLMAP_BAL_SIMPLE_RADIAL") != nullptr;
    camera.model_id = bal_simple_radial ? SimpleRadialCameraModel::model_id
                                        : RadialCameraModel::model_id;
    camera.width = 2000;   // unused by BA itself; principal point is (0,0) below
    camera.height = 2000;  // to match BAL's own (already-centered) pixel convention
    if (bal_simple_radial) {
      camera.params = {cam_params[9 * c + 6], 0.0, 0.0, cam_params[9 * c + 7]};
    } else {
      camera.params = {cam_params[9 * c + 6], 0.0, 0.0,
                        cam_params[9 * c + 7], cam_params[9 * c + 8]};
    }
    reconstruction.AddCameraWithTrivialRig(camera);
  }

  // Bucket observations per image so each image's Points2D() can be built in one
  // shot before AddImageWithTrivialFrame -- AddPoint3D later dereferences Point2D
  // by reference into the already-inserted image, so points2D must exist first.
  std::vector<std::vector<int>> obs_of_image(ncam);
  for (int i = 0; i < nobs; ++i) obs_of_image[obs_cam[i]].push_back(i);
  std::vector<point2D_t> obs_point2D_idx(nobs);

  for (int c = 0; c < ncam; ++c) {
    std::vector<Eigen::Vector2d> points2D;
    points2D.reserve(obs_of_image[c].size());
    for (const int obs_i : obs_of_image[c]) {
      obs_point2D_idx[obs_i] = static_cast<point2D_t>(points2D.size());
      // Inverse of WriteBal: u_bal = x_px - cx, v_bal = -(y_px - cy), cx=cy=0 here.
      points2D.emplace_back(obs_u[obs_i], -obs_v[obs_i]);
    }

    Image image;
    image.SetImageId(static_cast<image_t>(c + 1));
    image.SetCameraId(static_cast<camera_t>(c + 1));
    image.SetName("bal_cam_" + std::to_string(c) + ".png");
    image.SetPoints2D(points2D);

    const Eigen::Vector3d angle_axis(cam_params[9 * c + 0], cam_params[9 * c + 1],
                                      cam_params[9 * c + 2]);
    const Eigen::Vector3d t_bal(cam_params[9 * c + 3], cam_params[9 * c + 4],
                                 cam_params[9 * c + 5]);
    const Eigen::Matrix3d R_colmap = flip * AngleAxisToRotationMatrix(angle_axis);
    const Eigen::Vector3d t_colmap = flip * t_bal;
    const Rigid3d cam_from_world(Eigen::Quaterniond(R_colmap), t_colmap);

    reconstruction.AddImageWithTrivialFrame(std::move(image), cam_from_world);
  }

  // Points3D with tracks built from the same observations, bucketed by point.
  std::vector<std::vector<int>> obs_of_point(npt);
  for (int i = 0; i < nobs; ++i) obs_of_point[obs_pt[i]].push_back(i);
  for (int p = 0; p < npt; ++p) {
    Track track;
    for (const int obs_i : obs_of_point[p]) {
      track.AddElement(static_cast<image_t>(obs_cam[obs_i] + 1),
                        obs_point2D_idx[obs_i]);
    }
    reconstruction.AddPoint3D(
        Eigen::Vector3d(pts[3 * p], pts[3 * p + 1], pts[3 * p + 2]),
        std::move(track));
  }

  std::printf(
      "loaded BAL %s: %d cams, %d points3D, %d obs (real data, RADIAL model, k1+k2 both kept)\n",
      path.string().c_str(), ncam, npt, nobs);
  return reconstruction;
}

// Logs (iteration, cost) pairs for a convergence plot -- Ceres's own
// print_summary output only gives Initial/Final cost, no per-iteration
// trace, unlike the champion CUDA solver's "it N cost=..." stdout lines.
// cost here is Ceres's internal objective value (half sum of squared
// residuals), not the pixel-space median reprojection error printed
// elsewhere in this file -- different units, only comparable to itself
// across iterations of the same run.
struct CostLogEntry {
  int iteration;
  double cost;
  double elapsed_seconds;
};

class CostLoggingCallback : public ceres::IterationCallback {
 public:
  CostLoggingCallback(std::vector<CostLogEntry>* log,
                       std::chrono::steady_clock::time_point start_time)
      : log_(log), start_time_(start_time) {}
  ceres::CallbackReturnType operator()(
      const ceres::IterationSummary& summary) override {
    // Ceres invokes this callback on every trial step, including rejected
    // ones (trust-region quality checks) -- step_is_successful filters to
    // only the accepted trajectory, matching how the champion CUDA solver's
    // own "it N cost=..." log only records its accepted steps. elapsed_seconds
    // is wall-clock from the same t0 RunBackend uses for its own reported
    // wall-clock figure, so a (elapsed_seconds, cost) plot is directly
    // comparable to another solver's own wall-clock-vs-cost trace.
    if (summary.step_is_successful) {
      const double elapsed =
          std::chrono::duration<double>(std::chrono::steady_clock::now() -
                                         start_time_)
              .count();
      log_->push_back({summary.iteration, summary.cost, elapsed});
    }
    return ceres::SOLVER_CONTINUE;
  }

 private:
  std::vector<CostLogEntry>* log_;
  std::chrono::steady_clock::time_point start_time_;
};

void RunBackend(const std::string& name, BundleAdjustmentBackend backend,
                 const Reconstruction& perturbed,
                 const std::filesystem::path& out_dir,
                 const bool prefer_gpu = false,
                 const double huber_delta = 0.0) {
  Reconstruction reconstruction = perturbed;  // fresh copy, same starting point
  BundleAdjustmentConfig config;
  for (const image_t image_id : reconstruction.RegImageIds()) {
    config.AddImage(image_id);
  }
  BundleAdjustmentOptions options;
  options.backend = backend;
  options.print_summary = true;
  // Fix intrinsics (f, k1, k2) -- COLMAP's defaults (refine_focal_length=true,
  // refine_extra_params=true) let Ceres optimize per-camera focal length and
  // both radial distortion coefficients as free parameters. Every other
  // solver this tool compares against (daba_mm.cu, the OCA-family CUDA
  // solvers) holds f/k1/k2 fixed and only ever adjusts camera pose and 3D
  // points -- a hard convention from the start of that whole investigation.
  // Leaving Ceres's defaults on means it solves a strictly less-constrained
  // problem (more free parameters that can absorb residual error), not the
  // same problem solved better -- caught when two structurally different
  // pose+points-only solvers (LM and a decoupled multi-lambda variant)
  // converged to near-identical reprojection error while Ceres reached a
  // meaningfully lower one: not a shared bug, just a different, easier
  // problem. refine_principal_point is already false by default, matching
  // BAL's fixed (already-centered) principal point convention.
  options.refine_focal_length = false;
  options.refine_extra_params = false;
  // ROUND 10: opt-in intrinsics refinement, for benchmarking against solvers
  // that also free the intrinsics (the oca --dof9 port). Both flags together
  // because CASPAR's merged focal_and_extra block requires them to agree
  // (bundle_adjustment_caspar.cc, IsFocalAndExtraVariable). For SIMPLE_RADIAL
  // this frees f and k1 per camera; principal point stays fixed either way.
  if (std::getenv("COLMAP_BA_REFINE_INTRINSICS")) {
    options.refine_focal_length = true;
    options.refine_extra_params = true;
    std::printf("BA options: REFINING intrinsics (f + extra params) per camera\n");
  }
  // CeresBundleAdjustmentOptions's constructor defaults max_num_iterations to
  // 100 (bundle_adjustment_ceres.cc) -- fine for well-conditioned problems,
  // but on ladybug-810 Ceres was still visibly plateaued (flat cost trace,
  // not yet converged) right at that cutoff, while every other solver this
  // tool compares against got a far larger iteration budget. Raised so a
  // "solver A didn't reach solver B's cost" result reflects genuine
  // convergence behavior, not one solver running out of allowed iterations
  // before the others did.
  options.ceres->solver_options.max_num_iterations = 1000;
  // Same fairness argument for MFREE. Its defaults (60 iterations,
  // max_consecutive_failures=3) are tuned for warm in-mapper calls where each
  // GBA starts near the optimum. On a cold BAL problem the first few steps
  // failing is ordinary LM behaviour, not grounds to quit -- measured on
  // final-4585, where the default stopped after 3 rejected steps with ZERO
  // accepted steps and returned the input unchanged (3.0731px -> 3.0731px)
  // while Caspar reached 1.3276px. Env-overridable so the effect of each
  // stopping rule can be measured rather than assumed.
  if (const char* e = std::getenv("COLMAP_MFREE_MAX_ITER"))
    options.mfree->max_num_iterations = std::atoi(e);
  if (const char* e = std::getenv("COLMAP_MFREE_MAX_FAILURES"))
    options.mfree->max_consecutive_failures = std::atoi(e);
  if (std::getenv("COLMAP_MFREE_VERBOSE"))
    options.mfree->print_progress = true;
  if (const char* e = std::getenv("COLMAP_MFREE_FUNC_TOL"))
    options.mfree->func_tolerance = std::atof(e);
  if (const char* e = std::getenv("COLMAP_MFREE_INITIAL_LAMBDA"))
    options.mfree->initial_lambda = std::atof(e);
  if (std::getenv("COLMAP_MFREE_FP32"))
    options.mfree->use_fp32_fragments = true;
  if (std::getenv("COLMAP_MFREE_FAST_OPENING"))
    options.mfree->fast_opening = true;
  if (const char* e = std::getenv("COLMAP_MFREE_FAST_OPENING_DEPTH"))
    options.mfree->fast_opening_depth = std::atoi(e);
  // COLMAP_MFREE_KERNEL=huber:<px> | cauchy:<px> | studentt:<nu>[:<sigma0_px>]
  if (const char* e = std::getenv("COLMAP_MFREE_KERNEL")) {
    const std::string k = e;
    if (k.rfind("huber:", 0) == 0) {
      options.mfree->robust_kernel = 1;
      options.mfree->robust_scale_px = std::atof(k.c_str() + 6);
    } else if (k.rfind("cauchy:", 0) == 0) {
      options.mfree->robust_kernel = 2;
      options.mfree->robust_scale_px = std::atof(k.c_str() + 7);
    } else if (k.rfind("studentt:", 0) == 0) {
      options.mfree->robust_kernel = 3;
      options.mfree->robust_nu = std::atof(k.c_str() + 9);
      const char* colon = std::strchr(k.c_str() + 9, ':');
      options.mfree->robust_scale_px = colon ? std::atof(colon + 1) : 0.0;
    }
  }
  if (prefer_gpu) {
    // Force GPU SPARSE Schur (cuDSS) explicitly, rather than letting
    // auto_select_solver_type pick for us. The prior version of this comment
    // ("for small inputs num_images stays under [min_num_images_gpu_solver]
    // anyway") was simply wrong: min_num_images_gpu_solver defaults to 50,
    // and venice-52 (52 images) and dubrovnik-88 (88 images) both cross it.
    // Worse, auto_select_solver_type picks DENSE_SCHUR (not sparse) for any
    // num_images <= max_num_images_direct_dense_gpu_solver (200 by default)
    // -- so those two datasets landed on Ceres's GPU *dense* Cholesky
    // (cuSolverDNDpotrf), which failed repeatedly with "leading minor of
    // order N is not positive definite" and never escaped across 100+
    // retries (measured directly). Forcing SPARSE_SCHUR sidesteps that
    // specific numerically-unstable path while still using the GPU uniformly
    // across every dataset above the hard min_num_images_gpu_solver=50 floor
    // -- so the champion (always GPU) and Ceres here are compared on the
    // same hardware, not GPU-vs-CPU.
    options.ceres->use_gpu = true;
    options.ceres->auto_select_solver_type = false;
    options.ceres->solver_options.linear_solver_type = ceres::SPARSE_SCHUR;
  }
  if (huber_delta > 0.0) {
    // Ceres only -- Caspar's ICasparModelAdapter has no robust-loss option in
    // this build (checked directly: no loss_function reference anywhere under
    // estimators/caspar/), so a CASPAR RunBackend call with huber_delta>0
    // silently still runs trivial/L2. Document this asymmetry at every call
    // site rather than pretending it's a fair comparison.
    options.ceres->loss_function_type =
        CeresBundleAdjustmentOptions::LossFunctionType::HUBER;
    options.ceres->loss_function_scale = huber_delta;
  }

  // ComputeMeanReprojectionError() only averages the cached Point3D::error
  // field -- it does not recompute it from current geometry, and BA does not
  // refresh that cache itself (its own internal cost, printed by
  // print_summary above, is the real number; UpdatePoint3DErrors() is what
  // syncs the cache to match). Without this, both calls below silently read
  // the same stale post-perturbation snapshot.
  //
  // Always use the median + cheirality-violation-safe path, not just for BAL
  // inputs: a real colmap_model_dir reconstruction (insta360x4_test) turned
  // out to also have pre-existing cheirality violations (15,500/261,233
  // points, ~5.9%, present even before synthetic perturbation) that the plain
  // mean silently blew up to ~1e155 via CalculateSquaredReprojectionError()'s
  // DBL_MAX sentinel -- while Ceres' own unaffected internal cost converged
  // normally (39.97px -> 0.62px), proving the data/solve were fine and only
  // this summary statistic was broken. "Only BAL data has this problem" was
  // the wrong assumption; the fix generalizes to any input.
  reconstruction.UpdatePoint3DErrors();
  const double err_before = ComputeMedianReprojectionError(reconstruction);
  const size_t violations_before = CountCheiralityViolations(reconstruction);

  // Ceres-only per-iteration cost trace for convergence plots -- Caspar's
  // BundleAdjustmentOptions has no Ceres solver_options to attach a callback
  // to, and this tool's own print_summary output for Caspar has no iteration
  // concept to log (it's a fixed number of PCG/GN steps internal to the
  // generated solver, not exposed here).
  std::vector<CostLogEntry> cost_log;
  const auto t0 = std::chrono::steady_clock::now();
  CostLoggingCallback cost_logger(&cost_log, t0);
  if (backend == BundleAdjustmentBackend::CERES) {
    options.ceres->solver_options.callbacks.push_back(&cost_logger);
    options.ceres->solver_options.update_state_every_iteration = false;
  }

  auto bundle_adjuster =
      CreateDefaultBundleAdjuster(options, config, reconstruction);
  const auto summary = bundle_adjuster->Solve();
  const double wall = ElapsedSeconds(t0);
  reconstruction.UpdatePoint3DErrors();
  const double err_after = ComputeMedianReprojectionError(reconstruction);
  const size_t violations_after = CountCheiralityViolations(reconstruction);

  std::printf(
      "\n== %s ==\n"
      "  usable solution: %s\n"
      "  num residuals:   %d\n"
      "  median reproj err: %.4fpx -> %.4fpx\n"
      "  cheirality violations: %zu -> %zu (of %zu points3D)\n"
      "  wall-clock:       %.3fs\n",
      name.c_str(), summary->IsSolutionUsable() ? "yes" : "no",
      summary->num_residuals, err_before,
      err_after, violations_before, violations_after,
      reconstruction.NumPoints3D(), wall);

  std::filesystem::create_directories(out_dir);
  reconstruction.Write(out_dir);

  if (!cost_log.empty()) {
    std::ofstream f(out_dir / "cost_per_iteration.csv");
    f << "iteration,cost,elapsed_seconds\n";
    for (const auto& e : cost_log) {
      f << e.iteration << "," << std::setprecision(17) << e.cost << ","
        << e.elapsed_seconds << "\n";
    }
    std::printf("wrote %zu-row cost trace to %s\n", cost_log.size(),
                (out_dir / "cost_per_iteration.csv").string().c_str());
  }
}
}  // namespace

int main(int argc, char** argv) {
  if (argc < 2) {
    std::fprintf(
        stderr,
        "Usage: %s <colmap_model_dir | --synthetic:NUM_FRAMES:NUM_POINTS | "
        "--bal:PATH | --noperturb:DIR> [out_dir=./compare_out] "
        "[trans_stddev=0.05] [rot_stddev_deg=2.0] [point_stddev=0.05] "
        "[huber_delta=0.0]\n"
        "\n"
        "  huber_delta > 0 switches Ceres from its default TrivialLoss to\n"
        "  HuberLoss(huber_delta) (delta in pixels). CASPAR has no robust-loss\n"
        "  option in this build and always runs TrivialLoss regardless of this\n"
        "  argument -- Ceres-vs-Caspar median reprojection error is only a fair\n"
        "  comparison at huber_delta=0 (the default).\n"
        "\n"
        "  --synthetic:F:P generates an F-frame, P-point SIMPLE_RADIAL\n"
        "  dataset via COLMAP's own SynthesizeDataset (same generator Caspar's\n"
        "  own unit tests use) instead of reading a model from disk -- Caspar\n"
        "  only supports SIMPLE_RADIAL/PINHOLE, so a real reconstruction using\n"
        "  a richer camera model (e.g. OPENCV) will make it skip every image.\n"
        "\n"
        "  --bal:PATH loads a real (not synthetic) BAL-format problem --\n"
        "  already-noisy real data, so no synthetic perturbation is applied;\n"
        "  it's run through the solvers exactly as loaded. trans/rot/point\n"
        "  stddev args are ignored in this mode.\n"
        "\n"
        "  --noperturb:DIR loads a colmap_model_dir reconstruction that is\n"
        "  already perturbed/prepared (e.g. a saved perturbed_input/ from a\n"
        "  prior run, possibly further edited -- filtered, points removed,\n"
        "  etc.) and runs the solvers on it exactly as loaded, no synthetic\n"
        "  noise applied. Unlike --bal, keeps the full COLMAP reconstruction\n"
        "  format (frames/rigs), so the source camera model is preserved for\n"
        "  Ceres/Caspar; --bal export inside this run still requires\n"
        "  SIMPLE_RADIAL/PINHOLE for daba_mm's benefit. trans/rot/point\n"
        "  stddev args are ignored in this mode.\n",
        argv[0]);
    return EXIT_FAILURE;
  }
  const std::string model_dir = argv[1];
  const std::filesystem::path out_root =
      argc > 2 ? argv[2] : "./compare_out";
  const double trans_stddev = argc > 3 ? std::atof(argv[3]) : 0.05;
  const double rot_stddev_deg = argc > 4 ? std::atof(argv[4]) : 2.0;
  const double point_stddev = argc > 5 ? std::atof(argv[5]) : 0.05;
  const double huber_delta = argc > 6 ? std::atof(argv[6]) : 0.0;

  Reconstruction reconstruction;
  const std::string kSyntheticPrefix = "--synthetic:";
  const std::string kBalPrefix = "--bal:";
  const std::string kNoPerturbPrefix = "--noperturb:";
  const bool is_bal_input = model_dir.rfind(kBalPrefix, 0) == 0;
  const bool is_noperturb_input = model_dir.rfind(kNoPerturbPrefix, 0) == 0;
  const bool skip_perturbation = is_bal_input || is_noperturb_input;
  if (model_dir.rfind(kSyntheticPrefix, 0) == 0) {
    const std::string rest = model_dir.substr(kSyntheticPrefix.size());
    const size_t colon = rest.find(':');
    const int num_frames = std::atoi(rest.substr(0, colon).c_str());
    const int num_points = std::atoi(rest.substr(colon + 1).c_str());
    SyntheticDatasetOptions synth_options;
    synth_options.num_rigs = 1;
    synth_options.num_cameras_per_rig = 1;
    synth_options.num_frames_per_rig = num_frames;
    synth_options.num_points3D = num_points;
    synth_options.track_length = 8;  // sparser than dense-default, more BAL-like
    synth_options.camera_model_id = SimpleRadialCameraModel::model_id;
    SynthesizeDataset(synth_options, &reconstruction);
    std::printf(
        "synthesized: %d frames, %d points3D, SIMPLE_RADIAL cameras "
        "(Ceres + Caspar compatible)\n",
        num_frames, num_points);
  } else if (is_bal_input) {
    reconstruction = ReadBal(model_dir.substr(kBalPrefix.size()));
  } else if (is_noperturb_input) {
    reconstruction.Read(model_dir.substr(kNoPerturbPrefix.size()));
    std::printf(
        "loaded (already perturbed/prepared, no further noise) %s: %zu "
        "images, %zu points3D\n",
        model_dir.c_str(), reconstruction.NumRegImages(),
        reconstruction.NumPoints3D());
  } else {
    reconstruction.Read(model_dir);
    std::printf("loaded %s: %zu images, %zu points3D\n", model_dir.c_str(),
                reconstruction.NumRegImages(), reconstruction.NumPoints3D());
  }

  // Median + cheirality-violation-safe path unconditionally, not just for BAL
  // inputs -- see the comment in RunBackend for why the plain mean isn't safe
  // for any real (non-synthetic) input, colmap_model_dir included.
  reconstruction.UpdatePoint3DErrors();  // cache doesn't self-refresh; see RunBackend
  {
    const size_t num_violations = CountCheiralityViolations(reconstruction);
    const char* context = skip_perturbation ? "starting (already prepared)"
                                             : "converged (source)";
    std::printf(
        "%s median reproj err: %.4fpx  (%zu/%zu points3D start behind a "
        "camera)\n",
        context, ComputeMedianReprojectionError(reconstruction),
        num_violations, reconstruction.NumPoints3D());
  }

  if (skip_perturbation) {
    // --bal input is already real/noisy; --noperturb input is an
    // already-perturbed-and-possibly-edited reconstruction from a prior run.
    // Neither should get a second round of synthetic noise on top.
    std::printf(
        "skipping synthetic noise injection: input is already "
        "perturbed/real data\n");
  } else {
    SyntheticNoiseOptions noise;
    noise.rig_from_world_translation_stddev = trans_stddev;
    noise.rig_from_world_rotation_stddev = rot_stddev_deg;
    noise.point3D_stddev = point_stddev;
    SynthesizeNoise(noise, &reconstruction);

    reconstruction.UpdatePoint3DErrors();
    const double err_perturbed = ComputeMedianReprojectionError(reconstruction);
    std::printf(
        "perturbed (trans_stddev=%.3fm rot_stddev=%.2fdeg point_stddev=%.3fm) "
        "median reproj err: %.4fpx\n",
        trans_stddev, rot_stddev_deg, point_stddev, err_perturbed);
  }

  // Save the perturbed starting point once, shared as the identical input to
  // every backend below (each RunBackend call takes its own copy).
  std::filesystem::create_directories(out_root / "perturbed_input");
  reconstruction.Write(out_root / "perturbed_input");
  std::printf("wrote perturbed starting reconstruction to %s\n",
              (out_root / "perturbed_input").string().c_str());
  WriteBal(reconstruction, out_root / "perturbed.bal.txt");

  // prefer_gpu=true unconditionally for --bal: inputs so Ceres runs on the
  // same hardware (GPU) as the champion CUDA solver it's being compared
  // against. RunBackend now forces GPU SPARSE Schur (cuDSS) specifically --
  // see the comment there for why (the GPU *dense* path failed repeatedly on
  // venice-52/dubrovnik-88, and plain CPU would make this a GPU-vs-CPU
  // comparison, not an algorithm comparison).
  // COLMAP_BA_ONLY=caspar|ceres restricts which backends run -- Ceres on the
  // largest BAL problems takes hours, so a Caspar-only timing needs this.
  const char* only_env = std::getenv("COLMAP_BA_ONLY");
  const std::string only = only_env ? only_env : "";
  if (only.empty() || only == "ceres") {
    // COLMAP_BA_CPU_CERES=1 runs Ceres on the CPU (auto-selected solver:
    // SuiteSparse SPARSE_SCHUR / ITERATIVE_SCHUR by problem size) instead of
    // the forced GPU sparse path. Exists for the algorithm-vs-algorithm
    // comparison against the CPU port of MFREE (mfree_cpu.h): both on the
    // same 64 cores, no silicon confound.
    const bool cpu_ceres = std::getenv("COLMAP_BA_CPU_CERES") != nullptr;
    RunBackend("CERES", BundleAdjustmentBackend::CERES, reconstruction,
               out_root / "ceres_result", /*prefer_gpu=*/!cpu_ceres, huber_delta);
  } else {
    std::printf("\n== CERES ==\n  skipped (COLMAP_BA_ONLY=%s)\n", only.c_str());
  }
#ifdef CASPAR_ENABLED
  // No huber_delta passed here -- Caspar has no robust-loss option in this
  // build (see the comment inside RunBackend), so it always runs trivial/L2
  // regardless. Passing huber_delta here would silently misrepresent that.
  if (!(only.empty() || only == "caspar")) {
    std::printf("\n== CASPAR ==\n  skipped (COLMAP_BA_ONLY=%s)\n", only.c_str());
  } else
  RunBackend("CASPAR", BundleAdjustmentBackend::CASPAR, reconstruction,
             out_root / "caspar_result", skip_perturbation);
#else
  std::printf(
      "\n== CASPAR ==\n  skipped: built without -DCASPAR_ENABLED=ON\n");
#endif

  // MFREE runs on the same perturbed reconstruction as the other two. Like
  // CASPAR it has no robust-loss option, so huber_delta is deliberately not
  // forwarded -- passing it would misreport which objective was minimised.
  // MFREE holds the principal point fixed on this (non-rig) path, so any
  // comparison here must leave refine_principal_point off for ALL backends
  // or the parameterisations differ silently.
  if (!(only.empty() || only == "mfree")) {
    std::printf("\n== MFREE ==\n  skipped (COLMAP_BA_ONLY=%s)\n", only.c_str());
  } else {
    RunBackend("MFREE", BundleAdjustmentBackend::MFREE, reconstruction,
               out_root / "mfree_result", skip_perturbation);
  }

  return EXIT_SUCCESS;
}
