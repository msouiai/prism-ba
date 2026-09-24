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

#include "colmap/estimators/bundle_adjustment_mfree.h"

#include "colmap/estimators/bundle_adjustment_ceres.h"

#include <cstring>
#include <cstdlib>

#include "colmap/scene/projection.h"
#include "colmap/util/logging.h"
#include "colmap/util/misc.h"

#include <algorithm>
#include <cmath>
#include <sstream>
#include <atomic>
#include <map>
#include <unordered_map>

#ifdef MFREE_ENABLED
#include "oca_core.h"
#endif

namespace colmap {
namespace {

// COLMAP_MFREE_KERNEL=huber:<px> | cauchy:<px> | studentt:<nu>[:<sigma0_px>]
// Env route for the native robust kernel. The mapper does not register the
// BundleAdjustmentMFree.* CLI options (only --Mapper.ba_global_backend), so
// without this there is no way to select the kernel for an end-to-end mapping
// run. Applies to both the pinhole/radial and the rig/fisheye solve paths.
// Returns false (L2) when unset, which is the default everywhere.
bool RobustKernelFromEnv(int* kernel, double* scale_px, double* nu) {
  const char* e = std::getenv("COLMAP_MFREE_KERNEL");
  if (e == nullptr) return false;
  const std::string k = e;
  if (k.rfind("huber:", 0) == 0) {
    *kernel = 1; *scale_px = std::atof(k.c_str() + 6); return true;
  }
  if (k.rfind("cauchy:", 0) == 0) {
    *kernel = 2; *scale_px = std::atof(k.c_str() + 7); return true;
  }
  if (k.rfind("studentt:", 0) == 0) {
    *kernel = 3;
    *nu = std::atof(k.c_str() + 9);
    const char* colon = std::strchr(k.c_str() + 9, ':');
    *scale_px = colon ? std::atof(colon + 1) : 0.0;
    return true;
  }
  LOG(WARNING) << "Ignoring unrecognised COLMAP_MFREE_KERNEL=" << k;
  return false;
}

// The loss the caller asked for. Precedence: COLMAP_MFREE_KERNEL, then an
// explicit BundleAdjustmentMFree.robust_kernel, then the Ceres loss carried in
// the shared options. The last one is what makes the mapper's local bundle
// adjustment the same objective under both backends: it requests SOFT_L1 at
// 1 px (bundle_adjustment_ceres.cc CreateLossFunction) and the global one
// TRIVIAL. Until 2026-09-18 the MFREE backend ignored that and ran every local
// BA as plain L2, so freshly triangulated outliers -- which the mapper only
// filters AFTER the local BA -- pulled on the new frame with full weight.
void SelectRobustKernel(const BundleAdjustmentOptions& options,
                        const MFreeBundleAdjustmentOptions& opts,
                        int* kernel, double* scale_px, double* nu) {
  *kernel = opts.robust_kernel;
  *scale_px = opts.robust_scale_px;
  *nu = opts.robust_nu;
  if (RobustKernelFromEnv(kernel, scale_px, nu)) return;
  if (*kernel != 0 || !options.ceres) return;
  using LossType = CeresBundleAdjustmentOptions::LossFunctionType;
  switch (options.ceres->loss_function_type) {
    case LossType::TRIVIAL:
      break;
    case LossType::SOFT_L1:
      *kernel = 4;
      *scale_px = options.ceres->loss_function_scale;
      break;
    case LossType::CAUCHY:
      *kernel = 2;
      *scale_px = options.ceres->loss_function_scale;
      break;
    case LossType::HUBER:
      *kernel = 1;
      *scale_px = options.ceres->loss_function_scale;
      break;
  }
}

// Camera models the rig path solves, all on the solver's 8-slot intrinsics
// vector [fx fy cx cy k1 k2 k3 k4]. OPENCV_FISHEYE maps one-to-one; the
// pinhole family is embedded with its missing parameters pinned at zero (and
// masked out of the solve) and, for the SIMPLE_* models, fy tied to fx.
bool RigPathSupports(CameraModelId id) {
  switch (id) {
    case CameraModelId::kOpenCVFisheye:
    case CameraModelId::kSimplePinhole:
    case CameraModelId::kPinhole:
    case CameraModelId::kSimpleRadial:
    case CameraModelId::kRadial:
      return true;
    default:
      return false;
  }
}

// Fills intr[8], the solver model bits and the free-parameter mask of a
// camera. Callers check RigPathSupports first.
void RigIntrinsicsOf(const Camera& cam, double* intr, int* model,
                     unsigned char* mask) {
  std::fill(intr, intr + 8, 0.0);
  std::fill(mask, mask + 8, 1);
  const auto& q = cam.params;
  switch (cam.model_id) {
    case CameraModelId::kOpenCVFisheye:
      *model = oca::RIG_MODEL_FISHEYE;
      for (int j = 0; j < 8; ++j) intr[j] = q[j];
      return;
    case CameraModelId::kSimplePinhole:  // f cx cy
      *model = oca::RIG_MODEL_PINHOLE | oca::RIG_MODEL_TIED_FOCAL;
      intr[0] = intr[1] = q[0]; intr[2] = q[1]; intr[3] = q[2];
      mask[4] = mask[5] = 0;
      return;
    case CameraModelId::kPinhole:  // fx fy cx cy
      *model = oca::RIG_MODEL_PINHOLE;
      intr[0] = q[0]; intr[1] = q[1]; intr[2] = q[2]; intr[3] = q[3];
      mask[4] = mask[5] = 0;
      return;
    case CameraModelId::kSimpleRadial:  // f cx cy k
      *model = oca::RIG_MODEL_PINHOLE | oca::RIG_MODEL_TIED_FOCAL;
      intr[0] = intr[1] = q[0]; intr[2] = q[1]; intr[3] = q[2]; intr[4] = q[3];
      mask[5] = 0;
      return;
    case CameraModelId::kRadial:  // f cx cy k1 k2
      *model = oca::RIG_MODEL_PINHOLE | oca::RIG_MODEL_TIED_FOCAL;
      intr[0] = intr[1] = q[0]; intr[2] = q[1]; intr[3] = q[2];
      intr[4] = q[3]; intr[5] = q[4];
      return;
    default:
      LOG(FATAL) << "RigIntrinsicsOf: unsupported camera model";
  }
}

void RigIntrinsicsWriteBack(const double* intr, Camera& cam) {
  auto& q = cam.params;
  switch (cam.model_id) {
    case CameraModelId::kOpenCVFisheye:
      for (int j = 0; j < 8; ++j) q[j] = intr[j];
      return;
    case CameraModelId::kSimplePinhole:
      q[0] = intr[0]; q[1] = intr[2]; q[2] = intr[3];
      return;
    case CameraModelId::kPinhole:
      q[0] = intr[0]; q[1] = intr[1]; q[2] = intr[2]; q[3] = intr[3];
      return;
    case CameraModelId::kSimpleRadial:
      q[0] = intr[0]; q[1] = intr[2]; q[2] = intr[3]; q[3] = intr[4];
      return;
    case CameraModelId::kRadial:
      q[0] = intr[0]; q[1] = intr[2]; q[2] = intr[3]; q[3] = intr[4];
      q[4] = intr[5];
      return;
    default:
      LOG(FATAL) << "RigIntrinsicsWriteBack: unsupported camera model";
  }
}

// Median reprojection error (px) of a rig state, evaluated on the host with
// the solver's own projection (OPENCV_FISHEYE: theta = atan2(rho, Pz) and the
// theta polynomial; pinhole family: x/z with the r^2 polynomial; intrinsics
// [fx fy cx cy k1..k4] either way). The solver reports cost only;
// this is the number a person reads to judge whether BA worked. Observations
// whose ray is behind or at the camera plane carry no error, as in COLMAP's
// cost functor. Large problems are strided down to ~1M samples: the median of
// that subset is indistinguishable from the full one and keeps this to a few
// tens of milliseconds per call on the full Fuchsberg model.
double RigMedianReprojErrorPx(int nobs, const int* cam_of_obs,
                              const int* pt_of_obs, const double* uv,
                              const int* frame_of, const int* sensor_of,
                              const int* calib_of, const int* calib_model,
                              const double* Rf,
                              const double* tf, const double* Rs,
                              const double* ts, const double* intr,
                              const double* X) {
  if (nobs <= 0) return 0.0;
  const int stride = std::max(1, nobs / 1'000'000);
  std::vector<double> err;
  err.reserve(static_cast<size_t>(nobs / stride) + 1);
  for (int o = 0; o < nobs; o += stride) {
    const int c = cam_of_obs[o];
    const double* R1 = Rf + 9 * frame_of[c];
    const double* t1 = tf + 3 * frame_of[c];
    const double* R2 = Rs + 9 * sensor_of[c];
    const double* t2 = ts + 3 * sensor_of[c];
    const double* in = intr + 8 * calib_of[c];
    const double* Xp = X + 3 * pt_of_obs[o];
    double Q[3], P[3];
    for (int i = 0; i < 3; ++i)
      Q[i] = R1[3 * i] * Xp[0] + R1[3 * i + 1] * Xp[1] +
             R1[3 * i + 2] * Xp[2] + t1[i];
    for (int i = 0; i < 3; ++i)
      P[i] = R2[3 * i] * Q[0] + R2[3 * i + 1] * Q[1] + R2[3 * i + 2] * Q[2] +
             t2[i];
    if (!(P[2] > 1e-12)) continue;
    if (calib_model[calib_of[c]] & oca::RIG_MODEL_PINHOLE) {
      const double x = P[0] / P[2], y = P[1] / P[2], r2 = x * x + y * y;
      const double d = 1.0 + r2 * (in[4] + r2 * in[5]);
      const double rx = in[0] * d * x + in[2] - uv[2 * o];
      const double ry = in[1] * d * y + in[3] - uv[2 * o + 1];
      err.push_back(std::sqrt(rx * rx + ry * ry));
      continue;
    }
    const double rho = std::sqrt(P[0] * P[0] + P[1] * P[1] + 1e-32);
    const double th = std::atan2(rho, P[2]), th2 = th * th;
    const double d =
        1.0 + th2 * (in[4] + th2 * (in[5] + th2 * (in[6] + th2 * in[7])));
    const double s = th / rho;
    const double rx = in[0] * d * s * P[0] + in[2] - uv[2 * o];
    const double ry = in[1] * d * s * P[1] + in[3] - uv[2 * o + 1];
    err.push_back(std::sqrt(rx * rx + ry * ry));
  }
  if (err.empty()) return 0.0;
  const size_t mid = err.size() / 2;
  std::nth_element(err.begin(), err.begin() + mid, err.end());
  return err[mid];
}

}  // namespace

namespace {

// COLMAP projects along +z; the solver inherits BAL's -z convention. The two
// are related by D = diag(1, -1, -1), which is its own inverse:
//     P_soj = D * P_col  =>  x_solver = x_colmap,  y_solver = -y_colmap
// so observations take (u - cx, -(v - cy)) and poses take D * [R | t].
constexpr double kFlip[3] = {1.0, -1.0, -1.0};

// The solver's intrinsics are exactly (f, k1, k2) with the principal point
// fixed. Anything else has no exact embedding, so we refuse it rather than
// silently fit a different objective than the caller asked for.
struct IntrinsicsMap {
  bool supported = false;
  double f = 0.0, cx = 0.0, cy = 0.0, k1 = 0.0, k2 = 0.0;
  // Index of f / k1 / k2 in Camera::params, or -1 when the model has none.
  int f_idx = -1, k1_idx = -1, k2_idx = -1;
  const char* reason = "";
};

IntrinsicsMap MapIntrinsics(const Camera& camera) {
  IntrinsicsMap m;
  const std::vector<double>& p = camera.params;
  switch (camera.model_id) {
    case CameraModelId::kSimplePinhole:  // f, cx, cy
      m.f = p[0]; m.cx = p[1]; m.cy = p[2];
      m.f_idx = 0;
      break;
    case CameraModelId::kPinhole:  // fx, fy, cx, cy
      if (p[0] != p[1]) {
        m.reason = "PINHOLE with fx != fy has no (f, k1, k2) embedding";
        return m;
      }
      m.f = p[0]; m.cx = p[2]; m.cy = p[3];
      m.f_idx = 0;
      break;
    case CameraModelId::kSimpleRadial:  // f, cx, cy, k1
      m.f = p[0]; m.cx = p[1]; m.cy = p[2]; m.k1 = p[3];
      m.f_idx = 0; m.k1_idx = 3;
      break;
    case CameraModelId::kRadial:  // f, cx, cy, k1, k2
      m.f = p[0]; m.cx = p[1]; m.cy = p[2]; m.k1 = p[3]; m.k2 = p[4];
      m.f_idx = 0; m.k1_idx = 3; m.k2_idx = 4;
      break;
    default:
      m.reason = "camera model is not one of SIMPLE_PINHOLE, PINHOLE, "
                 "SIMPLE_RADIAL, RADIAL";
      return m;
  }
  m.supported = true;
  return m;
}

}  // namespace

std::string MFreeBundleAdjustmentSummary::BriefReport() const {
  std::ostringstream s;
  s << "Matrix-free multi-shift bundle adjustment\n"
    << "  cameras / points / observations : " << num_cameras << " / "
    << num_points << " / " << num_observations << "\n"
    << "  iterations                      : " << iteration_count << "\n"
    << "  cost                            : " << initial_cost << " -> "
    << final_cost << "\n"
    << "  median reprojection error (px)  : "
    << initial_median_reproj_error_px << " -> "
    << final_median_reproj_error_px << "\n"
    << "  calibration groups              : " << num_calibrations << "\n"
    << "  intrinsics                      : "
    << (refined_intrinsics ? "refined (f, k1), shared within each group"
                           : "held constant");
  if (!message.empty()) s << "\n  note                            : " << message;
  return s.str();
}

#ifdef MFREE_ENABLED

bool IsMFreeBundleAdjustmentAvailable() { return oca::IsAvailable(); }

namespace {

class MFreeBundleAdjuster : public BundleAdjuster {
 public:
  MFreeBundleAdjuster(const BundleAdjustmentOptions& options,
                      const BundleAdjustmentConfig& config,
                      Reconstruction& reconstruction)
      : BundleAdjuster(options, config),
        reconstruction_(reconstruction),
        opts_(*THROW_CHECK_NOTNULL(options.mfree)) {}

  std::shared_ptr<BundleAdjustmentSummary> Solve() override {
    auto summary = std::make_shared<MFreeBundleAdjustmentSummary>();
    summary->termination_type = BundleAdjustmentTerminationType::FAILURE;

    if (!oca::IsAvailable()) {
      summary->message = "no CUDA device available";
      LOG(WARNING) << summary->message;
      return summary;
    }

    // Every problem whose cameras the rig path knows (OPENCV_FISHEYE and the
    // pinhole family, mixed freely, with or without rigs) goes to the
    // round-12 rig path: it is the only one with Ceres' constant-block
    // vocabulary (out-of-bundle poses and points, per-camera intrinsics),
    // which the mapper's local BA depends on. The legacy pinhole core below
    // has none of that -- on the Muellcontainer run it let every local window
    // float freely and the map tore (26 deg bend at frame ~350) -- so it is
    // kept only as the fallback for models the rig path does not embed.
    {
      bool all_rig = true;
      for (const image_t image_id : config_.Images()) {
        const Image& image = reconstruction_.Image(image_id);
        if (!RigPathSupports(image.CameraPtr()->model_id)) {
          all_rig = false;
          break;
        }
      }
      const char* force = std::getenv("COLMAP_MFREE_LEGACY_PINHOLE");
      if (all_rig && !config_.Images().empty() && !(force && atoi(force))) {
        return SolveRigFisheye(std::move(summary));
      }
    }
    if (!Build(summary.get())) return summary;

    oca::Problem problem;
    problem.num_cameras = static_cast<int>(num_poses_);
    problem.num_points = static_cast<int>(num_points_);
    problem.num_observations = static_cast<int>(obs_camera_.size());
    problem.camera_index = obs_camera_.data();
    problem.point_index = obs_point_.data();
    problem.observations = obs_uv_.data();
    problem.calibration_index = calib_index_.data();
    problem.num_calibrations = static_cast<int>(calib_of_camera_.size());

    oca::State state;
    state.rotations = rotations_.data();
    state.translations = translations_.data();
    state.points = points_.data();
    state.focal = focal_.data();
    state.k1 = k1_.data();
    state.k2 = k2_.data();

    oca::Options o;
    o.max_iterations = opts_.max_num_iterations;
    o.refine_intrinsics = refine_intrinsics_;
    o.refine_k2 = refine_intrinsics_ && any_k2_free_;
    o.point_damping = opts_.point_damping;
    o.initial_lambda = opts_.initial_lambda;
    o.use_fp32_fragments = opts_.use_fp32_fragments;
    o.max_inner_retries = opts_.max_inner_retries;
    o.func_tolerance = opts_.func_tolerance;
    o.max_consecutive_failures = opts_.max_consecutive_failures;
    o.gpu_index = opts_.gpu_index;
    o.verbose = opts_.print_progress;
    int rk;
    double rk_px, rk_nu;
    SelectRobustKernel(options_, opts_, &rk, &rk_px, &rk_nu);
    o.robust_kernel = rk;
    o.robust_nu = rk_nu;
    // Huber/Cauchy take a fixed squared scale; the t kernel takes nu*sigma0^2
    // and treats 0 as "auto-init from the residual median".
    o.robust_scale2 = (rk == 3) ? rk_nu * rk_px * rk_px : rk_px * rk_px;
    o.fast_opening = opts_.fast_opening || std::getenv("COLMAP_MFREE_FAST_OPENING");
    o.fast_opening_depth = opts_.fast_opening_depth;

    const oca::Result r = oca::Solve(problem, o, &state);
    if (!r.success) {
      summary->message = r.message;
      LOG(WARNING) << "MFREE bundle adjustment failed: " << r.message;
      return summary;
    }

    WriteBack();

    summary->termination_type = BundleAdjustmentTerminationType::CONVERGENCE;
    summary->num_residuals = 2 * static_cast<int>(obs_camera_.size());
    summary->iteration_count = r.iterations;
    summary->initial_cost = r.initial_cost;
    summary->final_cost = r.final_cost;
    summary->initial_median_reproj_error_px = r.initial_median_error_px;
    summary->final_median_reproj_error_px = r.final_median_error_px;
    summary->refined_intrinsics = refine_intrinsics_;
    summary->num_calibrations = static_cast<int>(calib_of_camera_.size());
    summary->num_cameras = static_cast<int>(num_poses_);
    summary->num_points = static_cast<int>(num_points_);
    summary->num_observations = static_cast<int>(obs_camera_.size());
    if (!refine_intrinsics_ && !intrinsics_note_.empty()) {
      summary->message = intrinsics_note_;
    }
    if (options_.print_summary) LOG(INFO) << summary->BriefReport();
    return summary;
  }

 private:
  // ---------------------------------------------------------------------
  // Round 12: OPENCV_FISHEYE + rig path. One pose block per FRAME
  // (rig_from_world), sensor_from_rig held constant, intrinsics per COLMAP
  // camera as an 8-wide calibration group [fx fy cx cy k1 k2 k3 k4].
  // ---------------------------------------------------------------------
  std::shared_ptr<BundleAdjustmentSummary> SolveRigFisheye(
      std::shared_ptr<MFreeBundleAdjustmentSummary> summary) {
    // This path builds the SAME problem the Ceres backend builds from a
    // config (bundle_adjustment_ceres.cc: FillImages / AddPointToProblem /
    // ParameterizePoints), which matters most for the mapper's local bundle
    // adjustment. Until 2026-09-18 it refused constant poses and constant
    // points and otherwise took every point seen by the bundle's images as
    // variable, fitted to the in-bundle observations only. In a local BA of
    // ~10 frames that re-fits every long-track point of the neighbourhood to a
    // fraction of its track, thousands of times over a mapping run; Ceres
    // holds such points constant (track longer than its observations in the
    // problem) and adds the out-of-bundle observations of the variable points
    // with their poses constant. The rig extrinsics were likewise refined in
    // every local BA although the mapper marks them constant unless all frames
    // of the rig are present. All of that is now honoured:
    //   * constant rig_from_world  -> the frame's six columns are masked;
    //   * constant sensor_from_rig -> that sensor gets no free slot;
    //   * constant intrinsics      -> per camera, its eight columns masked;
    //   * out-of-bundle images of variable points enter as constant frames
    //     carrying the composed cam_from_world with the identity sensor;
    //   * constant points          -> config's constant points, everything
    //     when refine_points3D is off, and every point whose track is longer
    //     than its observations in the problem.
    const bool refine_frames = options_.refine_rig_from_world;

    // Index frames, sensors, and calibration groups over the image set.
    std::unordered_map<frame_t, int> frame_slot;
    std::map<std::pair<rig_t, sensor_t>, int> sensor_slot;
    std::vector<std::pair<rig_t, sensor_t>> sensor_keys;  // slot -> identity
    std::unordered_map<camera_t, int> calib_slot;
    std::vector<int> frame_of, sensor_of, calib_of;
    std::vector<double> Rf, tf, Rs, ts, intr;
    std::vector<image_t> ordered_images;
    std::vector<frame_t> frame_ids;
    std::vector<unsigned char> frame_const;
    std::vector<camera_t> calib_ids;
    std::vector<int> calib_model;            // per calibration group
    std::vector<unsigned char> calib_mask;   // 8 per calibration group
    auto push_calib = [&](const Camera& cam) {
      intr.resize(intr.size() + 8);
      calib_mask.resize(calib_mask.size() + 8);
      int model = 0;
      RigIntrinsicsOf(cam, &intr[intr.size() - 8], &model,
                      &calib_mask[calib_mask.size() - 8]);
      calib_model.push_back(model);
    };
    // Slot 0: the shared identity for every rig reference sensor.
    Rs.assign({1, 0, 0, 0, 1, 0, 0, 0, 1});
    ts.assign({0, 0, 0});

    auto push_pose = [](const Rigid3d& pose, std::vector<double>* R,
                        std::vector<double>* t) {
      const Eigen::Matrix3d m = pose.rotation().toRotationMatrix();
      for (int r = 0; r < 3; ++r)
        for (int c = 0; c < 3; ++c) R->push_back(m(r, c));
      for (int r = 0; r < 3; ++r) t->push_back(pose.translation()(r));
    };

    std::vector<image_t> sorted_ids(config_.Images().begin(),
                                    config_.Images().end());
    std::sort(sorted_ids.begin(), sorted_ids.end());  // determinism

    for (const image_t image_id : sorted_ids) {
      const Image& image = reconstruction_.Image(image_id);
      const Frame& frame = *image.FramePtr();
      auto fit = frame_slot.find(frame.FrameId());
      if (fit == frame_slot.end()) {
        fit = frame_slot.emplace(frame.FrameId(),
                                 static_cast<int>(frame_ids.size())).first;
        frame_ids.push_back(frame.FrameId());
        frame_const.push_back(
            (!refine_frames ||
             config_.HasConstantRigFromWorldPose(frame.FrameId()))
                ? 1
                : 0);
        push_pose(frame.RigFromWorld(), &Rf, &tf);
      }
      int s_slot = 0;
      const sensor_t sensor_id = image.CameraPtr()->SensorId();
      if (!frame.RigPtr()->IsRefSensor(sensor_id)) {
        const auto key = std::make_pair(frame.RigId(), sensor_id);
        auto sit = sensor_slot.find(key);
        if (sit == sensor_slot.end()) {
          sit = sensor_slot.emplace(key,
                                    static_cast<int>(Rs.size() / 9)).first;
          sensor_keys.push_back(key);
          push_pose(frame.RigPtr()->SensorFromRig(sensor_id), &Rs, &ts);
        }
        s_slot = sit->second;
      }
      auto cit = calib_slot.find(image.CameraId());
      if (cit == calib_slot.end()) {
        const Camera& cam = *image.CameraPtr();
        cit = calib_slot.emplace(image.CameraId(),
                                 static_cast<int>(calib_ids.size())).first;
        calib_ids.push_back(image.CameraId());
        push_calib(cam);
      }
      frame_of.push_back(fit->second);
      sensor_of.push_back(s_slot);
      calib_of.push_back(cit->second);
      ordered_images.push_back(image_id);
    }
    const size_t num_bundle_frames = frame_ids.size();

    // Sensors: constant when the config says so (the mapper's local BA holds
    // sensor_from_rig unless every frame of the rig is in the bundle).
    std::vector<unsigned char> sensor_const(1 + sensor_keys.size(), 0);
    for (size_t sl = 0; sl < sensor_keys.size(); ++sl)
      if (config_.HasConstantSensorFromRigPose(sensor_keys[sl].second))
        sensor_const[sl + 1] = 1;

    // Observations and points, raw pixels (the fisheye path never bakes the
    // principal point into the observations -- cx, cy are free columns).
    std::unordered_map<point3D_t, int> point_slot;
    std::vector<point3D_t> point_ids;
    std::vector<double> points;
    std::vector<size_t> point_num_obs;  // observations in the problem
    std::vector<int> obs_cam, obs_pt;
    std::vector<double> obs_uv;
    auto point_slot_of = [&](point3D_t point3D_id) -> int {
      auto it = point_slot.find(point3D_id);
      if (it == point_slot.end()) {
        const Point3D& point3D = reconstruction_.Point3D(point3D_id);
        it = point_slot.emplace(point3D_id,
                                static_cast<int>(point_ids.size())).first;
        point_ids.push_back(point3D_id);
        point_num_obs.push_back(0);
        points.push_back(point3D.xyz(0));
        points.push_back(point3D.xyz(1));
        points.push_back(point3D.xyz(2));
      }
      return it->second;
    };
    auto track_too_short = [&](const Point3D& point3D) {
      return options_.min_track_length > 0 &&
             static_cast<int>(point3D.track.Length()) <
                 options_.min_track_length;
    };
    for (size_t i = 0; i < ordered_images.size(); ++i) {
      const Image& image = reconstruction_.Image(ordered_images[i]);
      for (const Point2D& point2D : image.Points2D()) {
        if (!point2D.HasPoint3D() ||
            config_.IsIgnoredPoint(point2D.point3D_id)) {
          continue;
        }
        const Point3D& point3D = reconstruction_.Point3D(point2D.point3D_id);
        if (track_too_short(point3D)) continue;
        const int ps = point_slot_of(point2D.point3D_id);
        ++point_num_obs[ps];
        obs_cam.push_back(static_cast<int>(i));
        obs_pt.push_back(ps);
        obs_uv.push_back(point2D.xy(0));
        obs_uv.push_back(point2D.xy(1));
      }
    }

    // Variable points: the rest of their tracks, observed from images outside
    // the bundle, enters with those poses constant (Ceres: AddPointToProblem
    // with ReprojErrorConstantPoseCostFunctor). Each such image becomes a
    // constant frame holding its composed cam_from_world with the identity
    // sensor; its camera's intrinsics are held unless the camera also has an
    // image in the bundle (Ceres: parameterized_camera_ids_).
    std::unordered_map<image_t, int> extra_image_slot;
    std::vector<camera_t> extra_only_cameras;
    {
      std::vector<point3D_t> var_points(config_.VariablePoints().begin(),
                                        config_.VariablePoints().end());
      std::sort(var_points.begin(), var_points.end());
      for (const point3D_t point3D_id : var_points) {
        if (config_.IsIgnoredPoint(point3D_id)) continue;
        const Point3D& point3D = reconstruction_.Point3D(point3D_id);
        if (track_too_short(point3D)) continue;
        const int ps = point_slot_of(point3D_id);
        if (point_num_obs[ps] == point3D.track.Length()) continue;
        for (const TrackElement& el : point3D.track.Elements()) {
          if (config_.HasImage(el.image_id)) continue;
          const Image& image = reconstruction_.Image(el.image_id);
          auto xit = extra_image_slot.find(el.image_id);
          if (xit == extra_image_slot.end()) {
            const int cam_slot = static_cast<int>(ordered_images.size());
            xit = extra_image_slot.emplace(el.image_id, cam_slot).first;
            const int f_slot = static_cast<int>(frame_ids.size());
            frame_ids.push_back(kInvalidFrameId);  // not written back
            frame_const.push_back(1);
            push_pose(image.CamFromWorld(), &Rf, &tf);
            auto cit = calib_slot.find(image.CameraId());
            if (cit == calib_slot.end()) {
              const Camera& cam = *image.CameraPtr();
              cit = calib_slot.emplace(image.CameraId(),
                                       static_cast<int>(calib_ids.size()))
                        .first;
              calib_ids.push_back(image.CameraId());
              extra_only_cameras.push_back(image.CameraId());
              push_calib(cam);
            }
            frame_of.push_back(f_slot);
            sensor_of.push_back(0);
            calib_of.push_back(cit->second);
            ordered_images.push_back(el.image_id);
          }
          const Point2D& point2D = image.Point2D(el.point2D_idx);
          ++point_num_obs[ps];
          obs_cam.push_back(xit->second);
          obs_pt.push_back(ps);
          obs_uv.push_back(point2D.xy(0));
          obs_uv.push_back(point2D.xy(1));
        }
      }
    }
    if (obs_cam.empty()) {
      summary->message = "no observations in the bundle adjustment problem";
      LOG(WARNING) << "MFREE: " << summary->message;
      return summary;
    }

    // Intrinsics: per camera, as the config says; cameras that only appear
    // through out-of-bundle observations are held (Ceres does the same).
    std::vector<unsigned char> calib_const(calib_ids.size(), 0);
    for (size_t g = 0; g < calib_ids.size(); ++g)
      if (config_.HasConstantCamIntrinsics(calib_ids[g])) calib_const[g] = 1;
    for (const camera_t cam_id : extra_only_cameras)
      calib_const[calib_slot.at(cam_id)] = 1;
    const bool intr_constant =
        std::all_of(calib_const.begin(), calib_const.end(),
                    [](unsigned char c) { return c != 0; });

    // Constant points (Ceres: ParameterizePoints).
    std::vector<unsigned char> point_const(point_ids.size(), 0);
    size_t num_const_points = 0;
    for (size_t q = 0; q < point_ids.size(); ++q) {
      const Point3D& point3D = reconstruction_.Point3D(point_ids[q]);
      if (!options_.refine_points3D ||
          point3D.track.Length() > point_num_obs[q] ||
          config_.HasConstantPoint(point_ids[q])) {
        point_const[q] = 1;
        ++num_const_points;
      }
    }

    // Gauge. Mirrors the Ceres path. THREE_POINTS: three linearly independent
    // constant points fix it; when the problem holds fewer, three more become
    // constant (FixGaugeWithThreePoints). TWO_CAMS_FROM_WORLD: two constant
    // frames fix it; otherwise one frame is pinned (six DOF) plus one
    // translation coordinate of the farthest frame (scale). Before 2026-09-18
    // the rig path always pinned a frame, which in a local BA -- an
    // over-determined problem whose neighbourhood is constant -- froze one
    // in-bundle frame that should have moved.
    //
    // History: gauge fixing on this path used to be absent entirely
    // (gauge_frame_slot_ stayed -1); every BA ran with all seven gauge DOF
    // free and consecutive Fuchsberg mapper snapshots differed by scale
    // factors of 0.519/0.761/0.833/0.913 while agreeing on shape to <0.1% of
    // extent -- invisible in the cost, which is scale-invariant.
    gauge_image_id_ = kInvalidImageId;
    gauge_frame_slot_ = -1;
    gauge_scale_frame_slot_ = -1;
    gauge_scale_axis_ = 0;
    size_t num_const_frames = 0;  // bundle frames only
    for (size_t f = 0; f < num_bundle_frames; ++f) num_const_frames += frame_const[f];
    bool need_gauge = config_.FixedGauge() != BundleAdjustmentGauge::UNSPECIFIED &&
                      refine_frames;
    size_t num_gauge_points = 0;
    if (need_gauge &&
        config_.FixedGauge() == BundleAdjustmentGauge::THREE_POINTS) {
      // Same test as Ceres' FixedGaugeWithThreePoints: rank of the matrix of
      // point coordinates, so the three cannot be collinear through the origin.
      Eigen::Matrix3d fixed = Eigen::Matrix3d::Zero();
      Eigen::Index nfixed = 0;
      auto maybe_add = [&](const Eigen::Vector3d& x) {
        if (nfixed >= 3) return false;
        fixed.col(nfixed) = x;
        if (fixed.colPivHouseholderQr().rank() > nfixed) {
          ++nfixed;
          return true;
        }
        fixed.col(nfixed).setZero();
        return false;
      };
      for (size_t q = 0; q < point_ids.size() && nfixed < 3; ++q)
        if (point_const[q])
          maybe_add(Eigen::Map<const Eigen::Vector3d>(&points[3 * q]));
      for (size_t q = 0; q < point_ids.size() && nfixed < 3; ++q) {
        if (point_const[q]) continue;
        if (maybe_add(Eigen::Map<const Eigen::Vector3d>(&points[3 * q]))) {
          point_const[q] = 1;
          ++num_const_points;
          ++num_gauge_points;
        }
      }
      if (nfixed >= 3) {
        need_gauge = false;
      } else {
        LOG(WARNING) << "MFREE: failed to fix the gauge with three points ("
                     << nfixed << " found); pinning a frame instead.";
      }
    }
    if (need_gauge && num_const_frames >= 2) need_gauge = false;
    if (need_gauge) {
      // Anchor: the first constant frame if there is one, else the frame of
      // the lowest-id reference-sensor image (pinned).
      int anchor_slot = -1;
      for (size_t f = 0; f < frame_ids.size() && anchor_slot < 0; ++f)
        if (frame_const[f]) anchor_slot = static_cast<int>(f);
      if (anchor_slot < 0) {
        for (const image_t id : sorted_ids) {
          const Image& image = reconstruction_.Image(id);
          if (image.IsRefInFrame()) {
            gauge_image_id_ = id;
            anchor_slot = frame_slot.at(image.FrameId());
            gauge_frame_slot_ = anchor_slot;
            break;
          }
        }
      }
      if (anchor_slot < 0) {
        LOG(WARNING) << "MFREE: no reference-sensor image found; gauge left "
                        "unfixed (result may drift by a similarity).";
      } else {
        // Scale: freeze the largest baseline component of the farthest
        // variable reference-sensor frame.
        const Eigen::Vector3d anchor_c =
            -Eigen::Map<const Eigen::Matrix<double, 3, 3, Eigen::RowMajor>>(
                 &Rf[9 * anchor_slot])
                 .transpose() *
            Eigen::Vector3d(tf[3 * anchor_slot], tf[3 * anchor_slot + 1],
                            tf[3 * anchor_slot + 2]);
        double best = -1.0;
        int best_slot = -1;
        Eigen::Vector3d best_delta = Eigen::Vector3d::Zero();
        for (const image_t id : sorted_ids) {
          const Image& other = reconstruction_.Image(id);
          if (!other.IsRefInFrame()) continue;
          const int fs = frame_slot.at(other.FrameId());
          if (fs == anchor_slot || frame_const[fs]) continue;
          const Eigen::Vector3d delta = other.ProjectionCenter() - anchor_c;
          const double d2 = delta.squaredNorm();
          if (d2 > best) {
            best = d2;
            best_slot = fs;
            best_delta = delta;
          }
        }
        if (best_slot >= 0 && best > 0.0) {
          gauge_scale_frame_slot_ = best_slot;
          best_delta.cwiseAbs().maxCoeff(&gauge_scale_axis_);
        } else if (num_const_frames == 0) {
          LOG(WARNING) << "MFREE: only one frame in this problem; scale left "
                          "free (result may drift by a scale factor).";
        }
      }
    }

    oca::RigFisheyeProblem problem;
    problem.num_images = static_cast<int>(ordered_images.size());
    problem.num_frames = static_cast<int>(frame_ids.size());
    problem.num_sensors = static_cast<int>(Rs.size() / 9);
    problem.num_calibrations = static_cast<int>(calib_ids.size());
    problem.num_points = static_cast<int>(point_ids.size());
    problem.num_observations = static_cast<int>(obs_cam.size());
    problem.frame_of_image = frame_of.data();
    problem.sensor_of_image = sensor_of.data();
    problem.calibration_of_image = calib_of.data();
    problem.camera_index = obs_cam.data();
    problem.point_index = obs_pt.data();
    problem.observations = obs_uv.data();
    auto any_set = [](const std::vector<unsigned char>& v) {
      return std::any_of(v.begin(), v.end(),
                         [](unsigned char c) { return c != 0; });
    };
    if (any_set(frame_const)) problem.frame_constant = frame_const.data();
    if (any_set(sensor_const)) problem.sensor_constant = sensor_const.data();
    if (any_set(calib_const) && !intr_constant)
      problem.calibration_constant = calib_const.data();
    if (num_const_points > 0) problem.point_constant = point_const.data();
    problem.calibration_model = calib_model.data();
    problem.calibration_param_mask = calib_mask.data();

    oca::RigFisheyeState state;
    state.frame_rotations = Rf.data();
    state.frame_translations = tf.data();
    state.sensor_rotations = Rs.data();
    state.sensor_translations = ts.data();
    state.intrinsics = intr.data();
    state.points = points.data();

    oca::RigFisheyeOptions o;
    o.max_iterations = opts_.max_num_iterations;
    o.point_damping = opts_.point_damping;
    o.initial_lambda = opts_.initial_lambda;
    // Warm-start the damping from the previous solve in this process. Without
    // this every mapper GBA relearns lambda from 10.0 and early stopping cuts
    // it off first: on the Fuchsberg mapping, 45% of the 212 global solves
    // spent their whole budget in that rediscovery (<=10 accepted steps).
    // The x8 factor backs off toward caution, since the model grew between
    // calls; the clamp keeps the start inside the shift grid's usable range.
    {
      const double warm = warm_lambda_.load();
      if (warm > 0.0) {
        o.initial_lambda =
            std::clamp(warm * 8.0, 1e-6, opts_.initial_lambda);
      }
    }
    o.use_fp32_fragments = opts_.use_fp32_fragments ||
                           problem.num_observations > 15'000'000;
    int rk;
    double rk_px, rk_nu;
    SelectRobustKernel(options_, opts_, &rk, &rk_px, &rk_nu);
    o.robust_kernel = rk;
    o.robust_nu = rk_nu;
    o.robust_scale2 = (rk == 3) ? rk_nu * rk_px * rk_px : rk_px * rk_px;
    o.max_inner_retries = opts_.max_inner_retries;
    const bool refine = opts_.refine_intrinsics && !intr_constant;
    o.refine_focal = refine && options_.refine_focal_length;
    o.refine_principal_point = refine && options_.refine_principal_point;
    o.refine_distortion = refine && options_.refine_extra_params;
    // Per-sensor constancy travels in problem.sensor_constant; this switch is
    // the global one (off -> no sensor gets a free slot at all).
    const bool all_sensors_const =
        !sensor_keys.empty() &&
        std::all_of(sensor_const.begin() + 1, sensor_const.end(),
                    [](unsigned char c) { return c != 0; });
    o.refine_sensor_from_rig =
        options_.refine_sensor_from_rig && !all_sensors_const;
    o.gauge_frame = gauge_frame_slot_;
    o.gauge_scale_frame = gauge_scale_frame_slot_;
    o.gauge_scale_axis = gauge_scale_axis_;
    o.func_tolerance = opts_.func_tolerance;
    o.max_consecutive_failures = opts_.max_consecutive_failures;
    o.gpu_index = opts_.gpu_index;
    o.verbose = opts_.print_progress;

    auto median_px = [&]() {
      return RigMedianReprojErrorPx(
          problem.num_observations, obs_cam.data(), obs_pt.data(),
          obs_uv.data(), frame_of.data(), sensor_of.data(), calib_of.data(),
          calib_model.data(), Rf.data(), tf.data(), Rs.data(), ts.data(),
          intr.data(),
          points.data());
    };
    const double initial_median_px = median_px();
    const oca::Result r = oca::SolveRigFisheye(problem, o, &state);
    if (r.success && r.final_lambda > 0.0) warm_lambda_.store(r.final_lambda);
    if (!r.success) {
      summary->message = r.message;
      LOG(WARNING) << "MFREE rig/fisheye bundle adjustment failed: "
                   << r.message;
      return summary;
    }

    // Write back what was free: bundle frames, refined sensors, refined
    // calibration groups, variable points. The synthetic frames of the
    // out-of-bundle observations (frame_ids[f] == kInvalidFrameId) and every
    // constant block are left exactly as they were in the reconstruction.
    if (o.refine_sensor_from_rig) {
      for (size_t sl = 0; sl < sensor_keys.size(); ++sl) {
        const size_t idx = sl + 1;  // slot 0 is the shared ref-sensor identity
        if (sensor_const[idx]) continue;
        Eigen::Matrix3d m;
        for (int rr = 0; rr < 3; ++rr)
          for (int cc = 0; cc < 3; ++cc) m(rr, cc) = Rs[9 * idx + 3 * rr + cc];
        reconstruction_.Rig(sensor_keys[sl].first)
            .SetSensorFromRig(sensor_keys[sl].second,
                              Rigid3d(Eigen::Quaterniond(m),
                                      Eigen::Vector3d(ts[3 * idx],
                                                      ts[3 * idx + 1],
                                                      ts[3 * idx + 2])));
      }
    }
    for (size_t f = 0; f < num_bundle_frames; ++f) {
      if (frame_const[f]) continue;
      Eigen::Matrix3d m;
      for (int rr = 0; rr < 3; ++rr)
        for (int cc = 0; cc < 3; ++cc) m(rr, cc) = Rf[9 * f + 3 * rr + cc];
      reconstruction_.Frame(frame_ids[f])
          .SetRigFromWorld(Rigid3d(Eigen::Quaterniond(m),
                                   Eigen::Vector3d(tf[3 * f], tf[3 * f + 1],
                                                   tf[3 * f + 2])));
    }
    if (!intr_constant) {
      for (size_t g = 0; g < calib_ids.size(); ++g) {
        if (calib_const[g]) continue;
        RigIntrinsicsWriteBack(&intr[8 * g],
                               reconstruction_.Camera(calib_ids[g]));
      }
    }
    for (size_t q = 0; q < point_ids.size(); ++q) {
      if (point_const[q]) continue;
      reconstruction_.Point3D(point_ids[q]).xyz =
          Eigen::Vector3d(points[3 * q], points[3 * q + 1], points[3 * q + 2]);
    }

    summary->termination_type = BundleAdjustmentTerminationType::CONVERGENCE;
    summary->num_residuals = 2 * problem.num_observations;
    summary->iteration_count = r.iterations;
    summary->initial_cost = r.initial_cost;
    summary->final_cost = r.final_cost;
    summary->initial_median_reproj_error_px = initial_median_px;
    summary->final_median_reproj_error_px = median_px();
    summary->refined_intrinsics =
        o.refine_focal || o.refine_principal_point || o.refine_distortion;
    summary->num_calibrations = problem.num_calibrations;
    summary->num_cameras = static_cast<int>(sorted_ids.size());
    summary->num_points = problem.num_points;
    summary->num_observations = problem.num_observations;
    // One line per solve describing the problem as built. The mapper does not
    // register BundleAdjustmentMFree.print_progress, hence the env switch.
    static const bool log_problem =
        std::getenv("COLMAP_MFREE_LOG_PROBLEM") != nullptr;
    if (opts_.print_progress || log_problem) {
      LOG(INFO) << StringPrintf(
          "MFREE rig BA: %zu bundle images (+%zu out-of-bundle), %zu frames "
          "(%zu constant), %zu sensors (%zu constant), %zu cameras (%zu "
          "constant), %zu points (%zu constant), %zu observations, gauge %s, "
          "loss %s | %d its, cost %.6g -> %.6g",
          sorted_ids.size(), extra_image_slot.size(), num_bundle_frames,
          num_const_frames, sensor_keys.size(),
          static_cast<size_t>(std::count(sensor_const.begin() + 1,
                                         sensor_const.end(), 1)),
          calib_ids.size(),
          static_cast<size_t>(
              std::count(calib_const.begin(), calib_const.end(), 1)),
          point_ids.size(), num_const_points, obs_cam.size(),
          gauge_frame_slot_ >= 0
              ? "pinned frame+scale"
              : (gauge_scale_frame_slot_ >= 0 ? "pinned scale only"
                                              : "fixed by constant blocks"),
          rk == 0 ? "L2"
                  : StringPrintf("%s %.2fpx",
                                 rk == 1   ? "huber"
                                 : rk == 2 ? "cauchy"
                                 : rk == 3 ? "student-t"
                                           : "soft-L1",
                                 rk_px)
                        .c_str(),
          r.iterations, r.initial_cost, r.final_cost);
    }
    if (options_.print_summary) LOG(INFO) << summary->BriefReport();
    return summary;
  }

  // Translates the reconstruction into the solver's flat arrays. Returns false
  // (with summary->message set) when the problem cannot be represented.
  bool Build(MFreeBundleAdjustmentSummary* summary) {
    // --- poses: one solver camera per image, trivial frames only ----------
    std::vector<image_t> image_ids(config_.Images().begin(),
                                   config_.Images().end());
    std::sort(image_ids.begin(), image_ids.end());  // determinism

    std::unordered_map<camera_t, int> images_per_camera;
    for (const image_t image_id : image_ids) {
      const Image& image = reconstruction_.Image(image_id);
      // Only the per-image test matters: refine_sensor_from_rig defaults to
      // true, so gating on the flag alone would reject every default-options
      // call, including the overwhelmingly common trivial-rig case where
      // sensor_from_rig is identity and never enters the problem.
      if (!image.IsRefInFrame()) {
        summary->message =
            "image " + std::to_string(image_id) +
            " is a non-reference sensor in a frame; the MFREE backend models "
            "one pose per image and supports trivial rigs only";
        LOG(WARNING) << "MFREE: " << summary->message;
        return false;
      }
      images_per_camera[image.CameraId()] += 1;
    }

    // A shared COLMAP camera becomes one CALIBRATION GROUP: the solver
    // constrains every pose in the group to a single (f, k1) exactly, by
    // solving in the reduced space. No averaging, no drift.
    //
    // The solver refines f and k1 together or not at all, so a request to
    // free exactly one of them cannot be honoured and is refused rather than
    // silently widened.
    if (options_.refine_focal_length != options_.refine_extra_params) {
      summary->message =
          "MFREE refines focal length and k1 jointly; refine_focal_length and "
          "refine_extra_params must be equal";
      LOG(WARNING) << "MFREE: " << summary->message;
      return false;
    }
    // Likewise there is no per-group freeze: all calibrations are variable or
    // all are constant.
    const size_t num_constant_intrinsics = std::count_if(
        images_per_camera.begin(), images_per_camera.end(),
        [this](const auto& kv) {
          return config_.HasConstantCamIntrinsics(kv.first);
        });
    if (num_constant_intrinsics != 0 &&
        num_constant_intrinsics != images_per_camera.size()) {
      summary->message =
          "MFREE cannot hold only some cameras' intrinsics constant; mark all "
          "or none";
      LOG(WARNING) << "MFREE: " << summary->message;
      return false;
    }
    refine_intrinsics_ = opts_.refine_intrinsics &&
                         options_.refine_focal_length &&
                         options_.refine_extra_params &&
                         num_constant_intrinsics == 0;
    if (!refine_intrinsics_) {
      intrinsics_note_ = "intrinsics held constant by request";
    }
    if (options_.refine_principal_point) {
      LOG(WARNING) << "MFREE: refine_principal_point is ignored; the solver "
                      "holds the principal point fixed.";
    }

    pose_of_image_.clear();
    calib_of_camera_.clear(); calib_index_.clear();
    rotations_.clear(); translations_.clear();
    focal_.clear(); k1_.clear(); k2_.clear();
    principal_point_.clear();
    any_k2_free_ = false;

    for (const image_t image_id : image_ids) {
      const Image& image = reconstruction_.Image(image_id);
      const Camera& camera = *image.CameraPtr();
      const IntrinsicsMap m = MapIntrinsics(camera);
      if (!m.supported) {
        summary->message = StringPrintf(
            "camera %d: %s", static_cast<int>(camera.camera_id), m.reason);
        LOG(WARNING) << "MFREE: " << summary->message;
        return false;
      }
      if (m.k2_idx >= 0 && options_.refine_extra_params) any_k2_free_ = true;

      const Rigid3d& cam_from_world = image.FramePtr()->RigFromWorld();
      const Eigen::Matrix3d R = cam_from_world.rotation().toRotationMatrix();
      const Eigen::Vector3d t = cam_from_world.translation();

      // One calibration slot per distinct COLMAP camera.
      auto cit = calib_of_camera_.find(camera.camera_id);
      if (cit == calib_of_camera_.end()) {
        cit = calib_of_camera_
                  .emplace(camera.camera_id,
                           static_cast<int>(calib_of_camera_.size()))
                  .first;
      }
      calib_index_.push_back(cit->second);
      pose_of_image_[image_id] = static_cast<int>(focal_.size());
      for (int i = 0; i < 3; ++i) {
        for (int j = 0; j < 3; ++j) rotations_.push_back(kFlip[i] * R(i, j));
      }
      for (int i = 0; i < 3; ++i) translations_.push_back(kFlip[i] * t(i));
      focal_.push_back(m.f);
      k1_.push_back(m.k1);
      k2_.push_back(m.k2);
      principal_point_.push_back({m.cx, m.cy});
    }
    num_poses_ = focal_.size();
    if (num_poses_ == 0) {
      summary->message = "no images in the bundle adjustment configuration";
      return false;
    }

    // --- points and observations -------------------------------------------
    // Constant points are not representable: the solver optimizes every point.
    // Rather than silently move them, treat them as an unsupported request.
    // Constant poses are NOT representable: the solver optimizes every camera
    // block. Accepting them and simply not writing those poses back would be
    // worse than refusing -- the points would have been optimized against
    // poses that then get reverted, leaving an inconsistent reconstruction.
    // This is what excludes local BA in the incremental pipeline, which fixes
    // the frames surrounding the local window (incremental_mapper.cc).
    if (!config_.ConstantRigFromWorldPoses().empty()) {
      summary->message =
          "constant rig-from-world poses are not supported by the MFREE "
          "backend; it optimizes every camera block";
      LOG(WARNING) << "MFREE: " << summary->message;
      return false;
    }
    if (!options_.refine_rig_from_world) {
      summary->message =
          "refine_rig_from_world=false is not supported by the MFREE backend";
      LOG(WARNING) << "MFREE: " << summary->message;
      return false;
    }
    // Gauge fixing. TWO_CAMS_FROM_WORLD is honoured on the rig path by pinning
    // one frame (the lowest-id image that is its frame's reference sensor,
    // matching Caspar's FixGaugeWithOneFrameFromWorld and Ceres's deterministic
    // sorted-id choice); scale is left as the one free gauge DOF, as in Caspar.
    // THREE_POINTS needs constant points, which this backend cannot express.
    gauge_image_id_ = kInvalidImageId;
    gauge_frame_slot_ = -1;
    if (config_.FixedGauge() == BundleAdjustmentGauge::TWO_CAMS_FROM_WORLD) {
      std::vector<image_t> sorted(config_.Images().begin(),
                                  config_.Images().end());
      std::sort(sorted.begin(), sorted.end());
      for (const image_t image_id : sorted) {
        if (reconstruction_.Image(image_id).IsRefInFrame()) {
          gauge_image_id_ = image_id;
          break;
        }
      }
      if (gauge_image_id_ == kInvalidImageId) {
        LOG(WARNING) << "MFREE: no reference-sensor image found; gauge left "
                        "unfixed (result may differ by a similarity).";
      }
    } else if (config_.FixedGauge() != BundleAdjustmentGauge::UNSPECIFIED) {
      LOG(WARNING) << "MFREE: only TWO_CAMS_FROM_WORLD gauge fixing is "
                      "implemented; the result may differ from the requested "
                      "gauge by a similarity transform.";
    }

    if (!config_.ConstantPoints().empty()) {
      summary->message =
          "constant 3D points are not supported by the MFREE backend";
      LOG(WARNING) << "MFREE: " << summary->message;
      return false;
    }
    if (!options_.refine_points3D) {
      summary->message =
          "refine_points3D=false is not supported by the MFREE backend";
      LOG(WARNING) << "MFREE: " << summary->message;
      return false;
    }

    point_slot_.clear();
    points_.clear();
    obs_camera_.clear(); obs_point_.clear(); obs_uv_.clear();

    for (const image_t image_id : image_ids) {
      const Image& image = reconstruction_.Image(image_id);
      const int pose = pose_of_image_.at(image_id);
      const auto& pp = principal_point_[pose];
      for (const Point2D& point2D : image.Points2D()) {
        if (!point2D.HasPoint3D() ||
            config_.IsIgnoredPoint(point2D.point3D_id)) {
          continue;
        }
        const Point3D& point3D = reconstruction_.Point3D(point2D.point3D_id);
        if (options_.min_track_length > 0 &&
            static_cast<int>(point3D.track.Length()) <
                options_.min_track_length) {
          continue;
        }
        auto it = point_slot_.find(point2D.point3D_id);
        if (it == point_slot_.end()) {
          it = point_slot_.emplace(point2D.point3D_id,
                                   static_cast<int>(points_.size() / 3)).first;
          points_.push_back(point3D.xyz(0));
          points_.push_back(point3D.xyz(1));
          points_.push_back(point3D.xyz(2));
        }
        obs_camera_.push_back(pose);
        obs_point_.push_back(it->second);
        obs_uv_.push_back(point2D.xy(0) - pp.first);
        obs_uv_.push_back(-(point2D.xy(1) - pp.second));  // -z convention
      }
    }
    num_points_ = points_.size() / 3;
    if (obs_camera_.empty() || num_points_ == 0) {
      summary->message = "no observations in the bundle adjustment problem";
      return false;
    }
    return true;
  }

  void WriteBack() {
    // 3D points. Omitting these silently discards most of the solve: the
    // solver reached 0.52 px internally while COLMAP still scored 31.9 px,
    // because the reconstruction kept its original noisy points.
    for (const auto& [point3D_id, slot] : point_slot_) {
      Point3D& point3D = reconstruction_.Point3D(point3D_id);
      point3D.xyz = Eigen::Vector3d(points_[3 * slot],
                                    points_[3 * slot + 1],
                                    points_[3 * slot + 2]);
    }

    for (const auto& [image_id, pose] : pose_of_image_) {
      Image& image = reconstruction_.Image(image_id);
      // Every pose was optimized (Build() refuses constant poses), so every
      // pose is written back. Skipping any here would revert it while leaving
      // the points that were fitted against it in place.
      Eigen::Matrix3d R;
      for (int i = 0; i < 3; ++i) {
        for (int j = 0; j < 3; ++j) R(i, j) = kFlip[i] * rotations_[9 * pose + 3 * i + j];
      }
      Eigen::Vector3d t;
      for (int i = 0; i < 3; ++i) t(i) = kFlip[i] * translations_[3 * pose + i];
      Rigid3d& cam_from_world = image.FramePtr()->RigFromWorld();
      // Re-orthonormalize: the retraction is Exp(dw)*R in fp64, but round-off
      // over 60 iterations still leaves R slightly off SO(3).
      cam_from_world.rotation() = Eigen::Quaterniond(R).normalized();
      cam_from_world.translation() = t;
    }

    if (!refine_intrinsics_) return;
    // Every pose in a calibration group carries the same refined value (the
    // solver enforces that exactly), so writing from any one member is well
    // defined. Write once per CAMERA rather than once per pose.
    std::unordered_map<camera_t, int> pose_for_camera;
    for (const auto& [image_id, pose] : pose_of_image_) {
      pose_for_camera.emplace(reconstruction_.Image(image_id).CameraId(), pose);
    }
    for (const auto& [camera_id, pose] : pose_for_camera) {
      Camera& camera = reconstruction_.Camera(camera_id);
      const IntrinsicsMap m = MapIntrinsics(camera);
      if (m.f_idx >= 0) {
        camera.params[m.f_idx] = focal_[pose];
        if (camera.model_id == CameraModelId::kPinhole) {
          camera.params[1] = focal_[pose];  // keep fx == fy
        }
      }
      if (m.k1_idx >= 0) camera.params[m.k1_idx] = k1_[pose];
      if (m.k2_idx >= 0 && any_k2_free_) camera.params[m.k2_idx] = k2_[pose];
    }
  }

  Reconstruction& reconstruction_;
  const MFreeBundleAdjustmentOptions& opts_;
  // Last successful solve's final camera damping, shared across all
  // adjuster instances in this process (the mapper constructs a fresh
  // adjuster per GBA call).
  static inline std::atomic<double> warm_lambda_{0.0};

  bool refine_intrinsics_ = false;
  image_t gauge_image_id_ = kInvalidImageId;
  frame_t gauge_scale_frame_id_ = kInvalidFrameId;
  int gauge_scale_frame_slot_ = -1;
  Eigen::Index gauge_scale_axis_ = 0;
  int gauge_frame_slot_ = -1;
  bool any_k2_free_ = false;
  std::string intrinsics_note_;

  size_t num_poses_ = 0, num_points_ = 0;
  std::unordered_map<image_t, int> pose_of_image_;
  // COLMAP camera_id -> calibration slot, and the per-pose slot array.
  std::unordered_map<camera_t, int> calib_of_camera_;
  std::vector<int> calib_index_;
  std::unordered_map<point3D_t, int> point_slot_;
  std::vector<std::pair<double, double>> principal_point_;

  std::vector<double> rotations_, translations_, points_;
  std::vector<double> focal_, k1_, k2_;
  std::vector<int> obs_camera_, obs_point_;
  std::vector<double> obs_uv_;
};

}  // namespace

std::unique_ptr<BundleAdjuster> CreateDefaultMFreeBundleAdjuster(
    const BundleAdjustmentOptions& options,
    const BundleAdjustmentConfig& config,
    Reconstruction& reconstruction) {
  return std::make_unique<MFreeBundleAdjuster>(options, config, reconstruction);
}

#else  // !MFREE_ENABLED

bool IsMFreeBundleAdjustmentAvailable() { return false; }

std::unique_ptr<BundleAdjuster> CreateDefaultMFreeBundleAdjuster(
    const BundleAdjustmentOptions&,
    const BundleAdjustmentConfig&,
    Reconstruction&) {
  LOG(FATAL_THROW) << "MFREE BA backend selected but COLMAP was built without "
                      "MFREE_ENABLED; rebuild with -DMFREE_ENABLED=ON.";
  return nullptr;
}

#endif  // MFREE_ENABLED

}  // namespace colmap
