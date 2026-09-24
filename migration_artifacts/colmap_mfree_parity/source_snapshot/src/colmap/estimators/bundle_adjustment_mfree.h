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

#pragma once

#include "colmap/estimators/bundle_adjustment.h"

#include <memory>
#include <vector>

namespace colmap {

// Options for the matrix-free multi-shift GPU bundle adjustment backend.
//
// The solver's linear core never forms or factorizes the Schur complement: a
// matrix-free operator evaluates Schur-vector products from Jacobian
// fragments, and a multi-shift conjugate gradient recurrence solves an entire
// Levenberg-Marquardt damping grid in one pass.
//
// SUPPORTED SUBSET. The backend refuses, rather than silently approximates,
// anything it cannot represent exactly:
//   * Camera models OPENCV_FISHEYE, SIMPLE_PINHOLE, PINHOLE, SIMPLE_RADIAL
//     and RADIAL, mixed freely within one problem. All of them go through the
//     rig solver (one projection model per camera on a shared intrinsics
//     layout), which speaks Ceres' constant-block vocabulary: out-of-bundle
//     poses and points held, per-camera intrinsics freezes, sensor_from_rig
//     constant or refined, gauge from the constant blocks (THREE_POINTS) or
//     a pinned frame + scale when nothing is constant. The mapper's local
//     bundle adjustment therefore solves the same problem as with Ceres.
//   * Focal length, principal point and distortion are refined per
//     refine_focal_length / refine_principal_point / refine_extra_params;
//     SIMPLE_* models keep their single focal length exactly.
//   * Shared cameras ARE supported: each distinct COLMAP camera becomes one
//     calibration group and every pose in a group shares its intrinsics
//     exactly (solved in the reduced space, not averaged afterwards).
//   * Losses: trivial, Huber, Cauchy, soft-L1 (what the mapper asks for).
// The legacy pinhole core (f, k1, k2; principal point fixed; no constant
// blocks; only in-bundle observations) remains reachable with
// COLMAP_MFREE_LEGACY_PINHOLE=1 for comparison only -- in a mapping run it
// lets every local window float and tears the map.
struct MFreeBundleAdjustmentOptions {
  // Fixed number of outer LM iterations. The solver has no tolerance-based
  // stopping rule yet, so this is the whole budget.
  int max_num_iterations = 60;

  // Damping of the eliminated point block. The one parameter that still needs
  // per-scene initialization; 3e-3 is the value used across the BAL suite.
  double point_damping = 3e-3;

  // Initial damping of the camera block.
  double initial_lambda = 10.0;

  // Store Jacobian fragments in fp32 (accumulation stays fp64). Halves both
  // Schur-matvec streams, which are memory-roofline bound (measured 185 of
  // 224 GB/s on an RTX 2000 Ada), so this is the only lever that moves them.
  //
  // Default is true as of 2026-09-14. Gated on the Fuchsberg rig dumps at N=3,
  // ms per matvec, quality identical to ~1e-5 relative: 1.5M obs -23%, 4.5M
  // -32%, 20.8M within the fp64 arm's own spread -- a large win up to a few
  // million observations, and neither a win nor a loss above that, because by
  // then the per-point stages dominate and they do not shrink with fragment
  // precision. The BAL panel agrees (-21..-33% from dubrovnik-88 up, -2% on
  // the smallest scene). No measured configuration loses. Set false to revert.
  bool use_fp32_fragments = true;

  // Max in-place LM retries per outer iteration. A rejected step leaves the
  // Hessian assembly untouched, so a retry reuses it instead of spending an
  // outer iteration. 0 restores the naive behaviour.
  int max_inner_retries = 8;

  // Refine focal length and k1. Shared COLMAP cameras are handled as
  // calibration groups, so this applies whether or not cameras are shared.
  bool refine_intrinsics = true;

  // Early stopping. Without it the solver always pays max_num_iterations,
  // which is what made it uncompetitive on the small, frequent bundle
  // adjustments that incremental mapping consists of. Measured on a 50-image
  // problem: 60 -> 15 iterations at identical final quality.
  //
  //   func_tolerance            stop after an accepted step whose relative
  //                             cost decrease falls below this.
  //   max_consecutive_failures  stop after this many outer iterations in a row
  //                             with no improving step. This is the criterion
  //                             that fires on an already-converged input,
  //                             where the cost never moves and so
  //                             func_tolerance never triggers.
  //
  // Set either to 0 to disable it and restore the fixed-iteration behaviour.
  double func_tolerance = 1e-6;
  int max_consecutive_failures = 3;

  // CUDA device to use. -1 selects the current/default device.
  // ---- Native robust kernel (IRLS), applied inside the solver ------------
  // 0 = L2 (default). 1 = Huber, 2 = Cauchy, 3 = Student's t. The weight
  // sqrt(rho'(|r|^2)) scales each observation's residual and Jacobian rows at
  // assembly, so the solver minimizes the robust objective directly rather
  // than relying on outlier culling between solves.
  //
  // robust_scale_px is delta (Huber) or c (Cauchy) in pixels. For Student's t
  // it is sigma0, and 0 means "estimate the scale from the data" -- the t
  // kernel re-estimates sigma by EM once per outer iteration, which is the
  // reason to prefer it: there is no scale to tune per scene.
  int robust_kernel = 0;
  double robust_scale_px = 0.0;
  double robust_nu = 4.0;   // Student's t degrees of freedom

  // ---- Fast-opening mode (off by default) --------------------------------
  // Trades a small amount of final accuracy for a faster opening: prunes the
  // candidate menu at intermediate CG checkpoints and caps CG depth until the
  // first rejected step. Measured over repeated runs: 20-31% less time before
  // the solver overtakes a single-damping baseline, at +0.08% to +0.44% final
  // cost. Enable for latency-sensitive callers; leave off when the last half
  // percent matters.
  bool fast_opening = false;
  int fast_opening_depth = 32;

  int gpu_index = -1;

  bool print_progress = false;
};

// Reports what the backend actually did, including the parts of the request it
// could not honour.
struct MFreeBundleAdjustmentSummary : public BundleAdjustmentSummary {
  int iteration_count = 0;
  double initial_cost = 0.0;
  double final_cost = 0.0;
  double initial_median_reproj_error_px = 0.0;
  double final_median_reproj_error_px = 0.0;
  bool refined_intrinsics = false;
  // Distinct calibration groups (== distinct COLMAP cameras in the problem).
  int num_calibrations = 0;
  int num_cameras = 0;
  int num_points = 0;
  int num_observations = 0;
  std::string message;

  std::string BriefReport() const override;
};

// Returns true when COLMAP was built with the backend and a CUDA device is
// present. Safe to call otherwise.
bool IsMFreeBundleAdjustmentAvailable();

std::unique_ptr<BundleAdjuster> CreateDefaultMFreeBundleAdjuster(
    const BundleAdjustmentOptions& options,
    const BundleAdjustmentConfig& config,
    Reconstruction& reconstruction);

}  // namespace colmap
