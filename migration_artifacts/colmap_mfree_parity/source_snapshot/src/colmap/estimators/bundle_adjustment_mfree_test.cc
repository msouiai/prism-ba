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

#include "colmap/scene/projection.h"
#include "colmap/scene/reconstruction_matchers.h"
#include "colmap/scene/synthetic.h"
#include "colmap/sensor/models.h"
#include "colmap/util/testing.h"

#include <gtest/gtest.h>

namespace colmap {
namespace {

// The backend needs a GPU. Skip rather than fail on CPU-only machines.
#define SKIP_WITHOUT_GPU()                                       \
  if (!IsMFreeBundleAdjustmentAvailable()) {                     \
    GTEST_SKIP() << "no CUDA device available for MFREE";        \
  }

// Median reprojection error over all observations of a reconstruction.
double MedianReprojError(const Reconstruction& reconstruction) {
  std::vector<double> errors;
  for (const image_t image_id : reconstruction.RegImageIds()) {
    const Image& image = reconstruction.Image(image_id);
    const Camera& camera = *image.CameraPtr();
    for (const Point2D& point2D : image.Points2D()) {
      if (!point2D.HasPoint3D()) continue;
      const Point3D& point3D = reconstruction.Point3D(point2D.point3D_id);
      errors.push_back(std::sqrt(CalculateSquaredReprojectionError(
          point2D.xy, point3D.xyz, image.CamFromWorld(), camera)));
    }
  }
  EXPECT_FALSE(errors.empty());
  std::sort(errors.begin(), errors.end());
  return errors[errors.size() / 2];
}

BundleAdjustmentConfig ConfigForAllImages(const Reconstruction& r) {
  BundleAdjustmentConfig config;
  for (const image_t image_id : r.RegImageIds()) config.AddImage(image_id);
  return config;
}

// One camera per frame, so every image owns its intrinsics and the 9-DoF path
// is reachable. num_cameras_per_rig=1 with several rigs gives that.
Reconstruction SyntheticUniqueCameras(int num_frames, int num_points) {
  Reconstruction r;
  SyntheticDatasetOptions o;
  o.num_rigs = num_frames;
  o.num_cameras_per_rig = 1;
  o.num_frames_per_rig = 1;
  o.num_points3D = num_points;
  o.camera_model_id = CameraModelId::kSimpleRadial;
  SynthesizeDataset(o, &r);
  return r;
}

// One rig with many frames sharing a single camera: the common COLMAP layout
// that the solver's per-pose intrinsics block cannot refine.
Reconstruction SyntheticSharedCamera(int num_frames, int num_points) {
  Reconstruction r;
  SyntheticDatasetOptions o;
  o.num_rigs = 1;
  o.num_cameras_per_rig = 1;
  o.num_frames_per_rig = num_frames;
  o.num_points3D = num_points;
  o.camera_model_id = CameraModelId::kSimpleRadial;
  SynthesizeDataset(o, &r);
  return r;
}

void AddNoise(Reconstruction* r) {
  SyntheticNoiseOptions n;
  n.point2D_stddev = 0.5;
  n.point3D_stddev = 0.1;
  n.rig_from_world_rotation_stddev = 0.5;
  n.rig_from_world_translation_stddev = 0.1;
  SynthesizeNoise(n, r);
}

TEST(MFreeBundleAdjuster, ReducesReprojectionErrorWithSharedCamera) {
  SKIP_WITHOUT_GPU();
  Reconstruction reconstruction = SyntheticSharedCamera(10, 200);
  AddNoise(&reconstruction);
  const double before = MedianReprojError(reconstruction);

  BundleAdjustmentOptions options;
  options.backend = BundleAdjustmentBackend::MFREE;
  const BundleAdjustmentConfig config = ConfigForAllImages(reconstruction);
  const auto summary =
      CreateDefaultMFreeBundleAdjuster(options, config, reconstruction)
          ->Solve();

  ASSERT_NE(summary->termination_type,
            BundleAdjustmentTerminationType::FAILURE);
  EXPECT_LT(MedianReprojError(reconstruction), before);

  // A shared camera is one calibration group, and IS refined.
  const auto* s = dynamic_cast<const MFreeBundleAdjustmentSummary*>(
      summary.get());
  ASSERT_NE(s, nullptr);
  EXPECT_TRUE(s->refined_intrinsics);
  EXPECT_EQ(s->num_calibrations, 1);
}

TEST(MFreeBundleAdjuster, RefinesSharedCameraAsOneCalibration) {
  SKIP_WITHOUT_GPU();
  Reconstruction reconstruction = SyntheticSharedCamera(10, 200);
  AddNoise(&reconstruction);
  const camera_t camera_id =
      reconstruction.Image(*reconstruction.RegImageIds().begin()).CameraId();
  const std::vector<double> orig = reconstruction.Camera(camera_id).params;

  BundleAdjustmentOptions options;
  options.backend = BundleAdjustmentBackend::MFREE;
  const BundleAdjustmentConfig config = ConfigForAllImages(reconstruction);
  CreateDefaultMFreeBundleAdjuster(options, config, reconstruction)->Solve();

  // One camera, one refined value -- the 10 poses sharing it cannot have
  // drifted into 10 different cameras, because the solver constrains them in
  // the reduced space rather than averaging afterwards.
  EXPECT_EQ(reconstruction.NumCameras(), 1);
  EXPECT_NE(reconstruction.Camera(camera_id).params, orig);
  // The principal point is never refined.
  EXPECT_EQ(reconstruction.Camera(camera_id).params[1], orig[1]);
  EXPECT_EQ(reconstruction.Camera(camera_id).params[2], orig[2]);
}

TEST(MFreeBundleAdjuster, HoldsIntrinsicsWhenAllMarkedConstant) {
  SKIP_WITHOUT_GPU();
  Reconstruction reconstruction = SyntheticSharedCamera(10, 200);
  AddNoise(&reconstruction);
  const camera_t camera_id =
      reconstruction.Image(*reconstruction.RegImageIds().begin()).CameraId();
  const std::vector<double> orig = reconstruction.Camera(camera_id).params;

  BundleAdjustmentOptions options;
  options.backend = BundleAdjustmentBackend::MFREE;
  BundleAdjustmentConfig config = ConfigForAllImages(reconstruction);
  config.SetConstantCamIntrinsics(camera_id);
  const auto summary =
      CreateDefaultMFreeBundleAdjuster(options, config, reconstruction)
          ->Solve();

  ASSERT_NE(summary->termination_type,
            BundleAdjustmentTerminationType::FAILURE);
  EXPECT_EQ(reconstruction.Camera(camera_id).params, orig);
}

// f and k1 are refined jointly or not at all; a request to free exactly one
// cannot be honoured and must be refused rather than silently widened.
TEST(MFreeBundleAdjuster, RejectsPartialIntrinsicsRefinement) {
  SKIP_WITHOUT_GPU();
  Reconstruction reconstruction = SyntheticSharedCamera(5, 100);
  AddNoise(&reconstruction);

  BundleAdjustmentOptions options;
  options.backend = BundleAdjustmentBackend::MFREE;
  options.refine_focal_length = true;
  options.refine_extra_params = false;
  const BundleAdjustmentConfig config = ConfigForAllImages(reconstruction);
  const auto summary =
      CreateDefaultMFreeBundleAdjuster(options, config, reconstruction)
          ->Solve();
  EXPECT_EQ(summary->termination_type,
            BundleAdjustmentTerminationType::FAILURE);
}

TEST(MFreeBundleAdjuster, RefinesIntrinsicsWhenCamerasAreUnique) {
  SKIP_WITHOUT_GPU();
  Reconstruction reconstruction = SyntheticUniqueCameras(10, 200);
  AddNoise(&reconstruction);
  const double before = MedianReprojError(reconstruction);

  BundleAdjustmentOptions options;
  options.backend = BundleAdjustmentBackend::MFREE;
  const BundleAdjustmentConfig config = ConfigForAllImages(reconstruction);
  const auto summary =
      CreateDefaultMFreeBundleAdjuster(options, config, reconstruction)
          ->Solve();

  ASSERT_NE(summary->termination_type,
            BundleAdjustmentTerminationType::FAILURE);
  EXPECT_LT(MedianReprojError(reconstruction), before);

  const auto* s = dynamic_cast<const MFreeBundleAdjustmentSummary*>(
      summary.get());
  ASSERT_NE(s, nullptr);
  EXPECT_TRUE(s->refined_intrinsics);
}

TEST(MFreeBundleAdjuster, RejectsUnsupportedCameraModel) {
  SKIP_WITHOUT_GPU();
  Reconstruction reconstruction;
  SyntheticDatasetOptions o;
  o.num_rigs = 1;
  o.num_cameras_per_rig = 1;
  o.num_frames_per_rig = 5;
  o.num_points3D = 100;
  o.camera_model_id = CameraModelId::kOpenCV;  // has no (f, k1, k2) embedding
  SynthesizeDataset(o, &reconstruction);

  BundleAdjustmentOptions options;
  options.backend = BundleAdjustmentBackend::MFREE;
  const BundleAdjustmentConfig config = ConfigForAllImages(reconstruction);
  const auto summary =
      CreateDefaultMFreeBundleAdjuster(options, config, reconstruction)
          ->Solve();

  // Refusing is the contract: an approximate fit would silently optimize a
  // different objective than the caller asked for.
  EXPECT_EQ(summary->termination_type,
            BundleAdjustmentTerminationType::FAILURE);
}

TEST(MFreeBundleAdjuster, RefusesNonTrivialRigWithoutAborting) {
  SKIP_WITHOUT_GPU();
  Reconstruction reconstruction;
  SyntheticDatasetOptions o;
  o.num_rigs = 1;
  o.num_cameras_per_rig = 2;  // second sensor is not the frame reference
  o.num_frames_per_rig = 5;
  o.num_points3D = 100;
  o.camera_model_id = CameraModelId::kSimpleRadial;
  SynthesizeDataset(o, &reconstruction);

  BundleAdjustmentOptions options;
  options.backend = BundleAdjustmentBackend::MFREE;
  const BundleAdjustmentConfig config = ConfigForAllImages(reconstruction);
  // Refuse, but do NOT abort: a backend that cannot represent the problem must
  // let the caller fall back to another one, not kill the process.
  const auto summary =
      CreateDefaultMFreeBundleAdjuster(options, config, reconstruction)
          ->Solve();
  EXPECT_EQ(summary->termination_type,
            BundleAdjustmentTerminationType::FAILURE);
}

// refine_sensor_from_rig defaults to true, so a trivial-rig problem built from
// default options must still run: gating on the flag rather than on the actual
// rig structure would reject essentially every caller.
TEST(MFreeBundleAdjuster, DefaultOptionsRunOnTrivialRig) {
  SKIP_WITHOUT_GPU();
  Reconstruction reconstruction = SyntheticSharedCamera(5, 100);
  AddNoise(&reconstruction);

  BundleAdjustmentOptions options;
  options.backend = BundleAdjustmentBackend::MFREE;
  ASSERT_TRUE(options.refine_sensor_from_rig);
  const BundleAdjustmentConfig config = ConfigForAllImages(reconstruction);
  const auto summary =
      CreateDefaultMFreeBundleAdjuster(options, config, reconstruction)
          ->Solve();
  EXPECT_NE(summary->termination_type,
            BundleAdjustmentTerminationType::FAILURE);
}

TEST(MFreeBundleAdjuster, RejectsConstantRigFromWorldPose) {
  SKIP_WITHOUT_GPU();
  Reconstruction reconstruction = SyntheticSharedCamera(10, 200);
  AddNoise(&reconstruction);

  BundleAdjustmentOptions options;
  options.backend = BundleAdjustmentBackend::MFREE;
  BundleAdjustmentConfig config = ConfigForAllImages(reconstruction);
  config.SetConstantRigFromWorldPose(
      reconstruction.Image(*reconstruction.RegImageIds().begin()).FrameId());

  // Refusing is required for correctness: the solver optimizes every camera
  // block, so honouring the request by reverting that pose afterwards would
  // leave points fitted against a pose that no longer exists.
  const auto summary =
      CreateDefaultMFreeBundleAdjuster(options, config, reconstruction)
          ->Solve();
  EXPECT_EQ(summary->termination_type,
            BundleAdjustmentTerminationType::FAILURE);
}

}  // namespace
}  // namespace colmap
