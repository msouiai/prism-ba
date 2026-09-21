// Copyright (c) 2026. Matrix-free multi-shift bundle adjustment -- library API.
//
// This is the ONLY entry point intended for embedding. It exposes the solver
// core (kernels + SolveMFreeShiftedCG) with no CLI, no file IO, and no
// dependency on the BAL format, so the research CLI (oca_cuda) and the COLMAP
// backend can share one implementation instead of forking it.
//
// The header is plain C++ with no CUDA types, so callers need no nvcc.
//
// Projection convention (inherited from BAL, and what the kernels implement):
//     P = R * X + t
//     x = -P.x / P.z ,  y = -P.y / P.z          <-- camera looks down -z
//     r2 = x*x + y*y ,  d = 1 + k1*r2 + k2*r2*r2
//     u = f*d*x ,       v = f*d*y
// The principal point is fixed at the origin: a caller whose model has one
// must subtract it from the observations before calling and add it back after.

#pragma once

#include <string>
#include <vector>

namespace oca {

// Observations and topology. Not owned; must outlive the Solve() call.
struct Problem {
  int num_cameras = 0;
  int num_points = 0;
  int num_observations = 0;

  const int* camera_index = nullptr;  // [num_observations]
  const int* point_index = nullptr;   // [num_observations]
  // [2*num_observations], interleaved (u,v), principal point already removed.
  const double* observations = nullptr;

  // OPTIONAL shared intrinsics. calibration_index[c] is the calibration group
  // of camera c, in [0, num_calibrations). Cameras in one group are
  // constrained to a SINGLE (f, k1, k2) throughout the solve: the constraint
  // is imposed exactly, by solving in the reduced space, not by averaging
  // afterwards. Leave null (or set num_calibrations == num_cameras with the
  // identity map) to give every camera its own intrinsics.
  //
  // When set, State's per-camera intrinsics arrays MUST already agree within
  // each group on entry -- Solve() rejects the problem otherwise -- and are
  // guaranteed to still agree on exit.
  const int* calibration_index = nullptr;  // [num_cameras]
  int num_calibrations = 0;
};

// The optimization variables. Read on entry, overwritten with the solution.
// Every array is caller-owned; Solve() writes in place.
struct State {
  double* rotations = nullptr;     // [9*num_cameras] row-major 3x3
  double* translations = nullptr;  // [3*num_cameras]
  double* points = nullptr;        // [3*num_points]
  // Intrinsics are always read. They are only written when
  // Options::refine_intrinsics is true (and k2 only when refine_k2 is true).
  double* focal = nullptr;  // [num_cameras]
  double* k1 = nullptr;     // [num_cameras]
  double* k2 = nullptr;     // [num_cameras]
};

struct Options {
  int max_iterations = 60;

  // false -> 6-DoF camera block (pose only), the round-9 path.
  // true  -> 9-DoF (pose + f + k1), requires per-camera intrinsics.
  bool refine_intrinsics = false;
  // Only meaningful with refine_intrinsics. Most callers want false: k2 is
  // outside COLMAP's SIMPLE_RADIAL and outside Caspar's model.
  bool refine_k2 = false;

  // Damping of the eliminated point block. This is the one parameter that
  // still needs per-scene initialization -- see round10/STATUS.md.
  double point_damping = 3e-3;
  // Initial camera-block damping. 10.0 is the CLI default (oca_cuda --lam0);
  // keep them equal so both wrappers descend identically.
  double initial_lambda = 10.0;

  // Truncated-CG iterates offered to the candidate menu each outer iteration.
  std::vector<int> cg_checkpoints = {8, 16, 32, 64, 128};
  // Damping values solved simultaneously by the multi-shift recurrence.
  int num_shifts = 5;

  // Store Jacobian fragments in fp32. Halves the dominant allocation; on the
  // measured suite the final cost agrees to ~1e-5 relative.
  bool use_fp32_fragments = false;

  // Max in-place LM retries per outer iteration; a rejected step leaves the
  // assembly untouched so a retry reuses it. 0 restores round-9 behaviour.
  // Forced to 0 when refine_intrinsics is false.
  int max_inner_retries = 8;

  // Early stopping. max_iterations alone is a poor budget: on an already-good
  // input the solver otherwise spends every iteration failing to improve. These
  // are on by default here (the CLI keeps its fixed-iteration behaviour).
  //
  //   func_tolerance            stop after an ACCEPTED step whose relative cost
  //                             decrease is below this (Ceres function_tolerance).
  //   max_consecutive_failures  stop after this many outer iterations in a row
  //                             that found no improving step. This is the one
  //                             that fires on a converged input, where the cost
  //                             never moves so func_tolerance never triggers.
  //
  // Set either to 0 to disable it.
  double func_tolerance = 1e-6;
  int max_consecutive_failures = 3;

  // Jacobi block equilibration of the camera block. Load-bearing at 9 DoF.
  bool equilibrate = true;

  int gpu_index = -1;  // -1 selects the current/default device.
  bool verbose = false;

  // ---- IRLS robust kernel (0 = L2, the default; bit-compat when 0) ----
  // The weight sqrt(rho'(|r|^2)) scales each observation's residual AND its
  // Jacobian rows at assembly, which turns the whole two-block machinery into
  // the weighted Gauss-Newton system; the multi-shift recurrence is untouched.
  //   1 huber  (robust_scale2 = delta^2, px^2)
  //   2 cauchy (robust_scale2 = c^2, px^2)
  //   3 student-t: same weight FORM as cauchy with a2 = nu*sigma^2, but sigma
  //     is re-estimated by EM from the current residuals once per assembly
  //     (frozen within an outer iteration so candidate scoring stays one
  //     consistent objective). robust_scale2 = nu*sigma0^2, or 0 to auto-init
  //     from the residual median. This is the variant with no scale to tune.
  //   4 soft-L1 (Ceres SoftLOneLoss): rho = 2a^2(sqrt(1+s/a^2)-1),
  //     robust_scale2 = a^2, px^2. The loss COLMAP's mapper uses for its
  //     local bundle adjustments (a = 1 px).
  int robust_kernel = 0;
  double robust_scale2 = 0.0;
  double robust_nu = 4.0;      // student-t degrees of freedom

  // ---- Fast-opening mode (off by default) --------------------------------
  // Cuts per-outer fixed cost while the solve is still in its opening: score
  // only the most promising shifts at intermediate CG checkpoints, and cap CG
  // depth. Disarms permanently at the first rejected step, which protects the
  // reject-prone scenes. Measured (N=3-4 runs per config): the window where a
  // single-damping baseline leads shrinks 20-31%, at a reproducible
  // end-residual cost of +0.08% to +0.44%. Enable when time-to-first-good-
  // answer matters more than the last half percent.
  bool fast_opening = false;
  int fast_opening_depth = 32;
};

struct Result {
  bool success = false;
  int iterations = 0;
  double initial_cost = 0.0;
  double final_cost = 0.0;
  // Cost after each accepted outer iteration, including the initial value.
  std::vector<double> cost_per_iteration;
  // Camera damping at exit. Feeding this (times a safety factor) back into the
  // next Solve()'s initial_lambda removes the cold-start stall: measured on the
  // Fuchsberg mapping, 45% of global-BA calls wasted their budget re-learning
  // lambda from the default 10.0 before early stopping cut them off.
  double final_lambda = 0.0;
  // Median reprojection error in pixels, before and after.
  double initial_median_error_px = 0.0;
  double final_median_error_px = 0.0;
  std::string message;
};

// True when a usable CUDA device is present. Safe to call without one.
bool IsAvailable();

// Human-readable description of the build (CUDA arch, fp mode). For logs.
std::string VersionString();

// Runs bundle adjustment in place. Returns Result::success=false with a
// populated message on bad input or CUDA failure; never throws, never exits.
Result Solve(const Problem& problem, const Options& options, State* state);

// ============================================================================
// Round 12: OPENCV_FISHEYE + rig problems.
//
// Model: each image's pose is sensor_from_rig(sensor) o rig_from_world(frame),
// COLMAP's +z convention throughout (no BAL sign flip anywhere: rotations,
// translations, and observations are passed exactly as COLMAP stores them).
// Intrinsics per calibration group: [fx fy cx cy k1 k2 k3 k4], the
// OPENCV_FISHEYE parameter order.
//
// v1 limits, enforced by Solve:
//   * sensor_from_rig refinement is optional (refine_sensor_from_rig); a
//     trivial rig is nsensors==1 with the identity, degenerating to plain
//     fisheye BA with frames==images.
//   * the refine mask applies to all calibration groups alike.
//   * every observation must satisfy Pz>0 at the initial state (COLMAP's own
//     projectable-depth guard; fisheye masks keep theta < 90 deg in practice).
// ============================================================================
struct RigFisheyeProblem {
  int num_images = 0;        // one pose per image after composition
  int num_frames = 0;        // rig_from_world blocks (the optimized poses)
  int num_sensors = 0;       // sensor_from_rig blocks (held constant)
  int num_calibrations = 0;  // intrinsics groups (== distinct cameras)
  int num_points = 0;
  int num_observations = 0;
  const int* frame_of_image = nullptr;    // [num_images]
  const int* sensor_of_image = nullptr;   // [num_images]
  const int* calibration_of_image = nullptr;  // [num_images]
  const int* camera_index = nullptr;      // [num_observations] -> image
  const int* point_index = nullptr;       // [num_observations]
  const double* observations = nullptr;   // [2*num_observations], raw pixels
  // Optional constancy flags (nullptr = everything free). They give the rig
  // path the same vocabulary as a Ceres problem with constant parameter
  // blocks, which COLMAP's local bundle adjustment relies on: out-of-bundle
  // poses held fixed, sensor_from_rig fixed unless every frame of the rig is
  // present, intrinsics fixed per camera, and every point whose track is not
  // fully inside the problem fixed. A constant frame / sensor / calibration
  // keeps its parameters exactly: its columns are removed from the linear
  // solve (mask on b' and on the operator output) and its step is zero. A
  // constant point is not eliminated (its V^-1 is zero), so its observations
  // constrain the cameras through Hcc and the gradient but the point itself
  // never moves -- exactly Ceres' constant point block.
  const unsigned char* frame_constant = nullptr;        // [num_frames]
  const unsigned char* sensor_constant = nullptr;       // [num_sensors]
  const unsigned char* calibration_constant = nullptr;  // [num_calibrations]
  const unsigned char* point_constant = nullptr;        // [num_points]
  // Optional projection model per calibration group (nullptr = every group
  // OPENCV_FISHEYE). RIG_MODEL_PINHOLE selects the pinhole + polynomial radial
  // chain on the same intrinsics vector: fx fy cx cy k1 k2 (k3 k4 ignored),
  // i.e. COLMAP's SIMPLE_PINHOLE / PINHOLE / SIMPLE_RADIAL / RADIAL. OR in
  // RIG_MODEL_TIED_FOCAL for the SIMPLE_* models (one focal length: fy is
  // kept equal to fx throughout the solve). Behind-camera points (Pz <= 0)
  // poison the cost of a pinhole group, they are never silently dropped.
  const int* calibration_model = nullptr;               // [num_calibrations]
  // Optional per-parameter freeze on top of the refine_* options, 8 entries
  // per calibration group in intrinsics order, 1 = free (nullptr = all free).
  // The wrapper uses it to pin the parameters a model does not have (k2 of
  // SIMPLE_RADIAL, all k of PINHOLE, ...).
  const unsigned char* calibration_param_mask = nullptr; // [8*num_calibrations]
};
constexpr int RIG_MODEL_FISHEYE = 0;
constexpr int RIG_MODEL_PINHOLE = 1;
constexpr int RIG_MODEL_TIED_FOCAL = 2;

struct RigFisheyeState {
  double* frame_rotations = nullptr;     // [9*num_frames], row-major
  double* frame_translations = nullptr;  // [3*num_frames]
  double* sensor_rotations = nullptr;    // [9*num_sensors] (constant)
  double* sensor_translations = nullptr; // [3*num_sensors] (constant)
  double* intrinsics = nullptr;          // [8*num_calibrations] fx fy cx cy k1..k4
  double* points = nullptr;              // [3*num_points]
};

struct RigFisheyeOptions {
  int max_iterations = 60;
  double point_damping = 3e-3;
  double initial_lambda = 10.0;
  bool use_fp32_fragments = false;  // mandatory in practice above ~15M obs
  int max_inner_retries = 8;
  // Column masks on the intrinsics tangent; a false entry freezes those
  // parameters exactly (zeroed gradient columns, zero delta).
  bool refine_focal = true;             // fx, fy
  bool refine_principal_point = true;   // cx, cy
  bool refine_distortion = true;        // k1..k4
  // Refine non-reference sensor_from_rig poses (first-order tangent columns,
  // exact exp retraction). Reference sensors are always the identity. When
  // false, all sensor poses are held constant (the round-12 v1 behaviour).
  bool refine_sensor_from_rig = false;
  double func_tolerance = 1e-6;
  int max_consecutive_failures = 3;
  // Index of a frame to hold fixed (gauge fix), or -1 for none. Pins six of the
  // seven gauge DOF; scale is the seventh and needs gauge_scale_frame below.
  int gauge_frame = -1;
  // Index of a second, well-separated frame whose translation update is zeroed
  // along gauge_scale_axis (0=x, 1=y, 2=z), fixing the distance to gauge_frame
  // and hence scale. -1 leaves scale free.
  //
  // Leaving it free is not harmless for incremental mapping: with only
  // gauge_frame pinned, consecutive Fuchsberg mapper snapshots differed by scale
  // factors of 0.519/0.761/0.833/0.913 while agreeing on shape to <0.1% of
  // extent. The drift damps out as the map grows, so it does not run away, but
  // over the full sequence it cost 18.1% of the reference's 3D points (vs 5.5%
  // with the pin) -- invisible in the cost, which is scale-invariant.
  int gauge_scale_frame = -1;
  int gauge_scale_axis = 0;
  int gpu_index = -1;
  bool verbose = false;

  // ---- IRLS robust kernel (0 = L2, the default; bit-compat when 0) --------
  // Same contract as Options above. Rig-specific note: the far-field /
  // behind-camera mask still decides which observations exist at all; the
  // robust weight only reshapes the ACTIVE ones, and inactive observations
  // are excluded from the student-t scale estimate rather than counted as
  // zero residuals.
  int robust_kernel = 0;
  double robust_scale2 = 0.0;
  double robust_nu = 4.0;
};

Result SolveRigFisheye(const RigFisheyeProblem& problem,
                       const RigFisheyeOptions& options,
                       RigFisheyeState* state);

}  // namespace oca
