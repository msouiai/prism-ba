// Converts a Reconstruction's camera(s) to PINHOLE by geometrically
// undistorting every 2D observation (not image pixels -- bundle adjustment
// never touches raw pixel data, only keypoint coordinates + intrinsics + 3D
// points, so there is nothing to gain from actually warping the image files).
// Uses colmap::UndistortReconstruction, the same exact per-observation
// CamFromImg/ImgFromCam round-trip COLMAP's own production image-undistortion
// pipeline uses -- correct for any camera model, OPENCV_FISHEYE included, not
// an approximation.
//
// Built to make a real dual-fisheye dataset (insta360x4_test, OPENCV_FISHEYE)
// usable with tools that only support SIMPLE_RADIAL/PINHOLE (Caspar,
// daba_mm's BAL exporter): undistorting to PINHOLE first makes it a genuine,
// like-for-like bundle-adjustment problem for all solvers, at the cost of
// dropping observations whose viewing angle can't be represented in a finite
// pinhole image (expected and inherent for wide-FOV fisheye source data, not
// a bug -- see max_cam_point_norm below).
#include "colmap/image/undistortion.h"
#include "colmap/scene/reconstruction.h"

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <vector>

using namespace colmap;

int main(int argc, char** argv) {
  if (argc < 3) {
    std::fprintf(stderr,
                  "Usage: %s <input_model_dir> <output_model_dir> "
                  "[max_fov_deg_from_axis=75]\n",
                  argv[0]);
    return EXIT_FAILURE;
  }
  const std::string in_path = argv[1];
  const std::string out_path = argv[2];
  const double max_fov_deg = argc > 3 ? std::atof(argv[3]) : 75.0;

  Reconstruction recon;
  recon.Read(in_path);
  const size_t num_images_in = recon.RegImageIds().size();
  const size_t num_points_in = recon.Points3D().size();

  UndistortCameraOptions options;
  options.blank_pixels = 0.0;
  // tan(theta): points whose ray makes a larger angle with the optical axis
  // than this cannot be finitely represented in a pinhole image (theta->90
  // degrees => tan(theta)->infinity) -- capping this explicitly (rather than
  // leaving it at the -1/disabled default) keeps the derived pinhole
  // dimensions and focal length sane for wide-FOV fisheye input; see the
  // option's own comment in undistortion.h.
  options.max_cam_point_norm = std::tan(max_fov_deg * M_PI / 180.0);

  UndistortReconstruction(options, &recon);

  // Observations whose ray fell outside max_cam_point_norm (or otherwise
  // couldn't round-trip through the new pinhole camera) were marked NaN by
  // UndistortReconstruction rather than silently dropped -- remove them now.
  // Reconstruction::DeleteObservation cascades correctly (removes the whole
  // point3D if its track drops below 2 remaining observations).
  size_t num_obs_dropped = 0;
  for (const image_t image_id : recon.RegImageIds()) {
    Image& image = recon.Image(image_id);
    std::vector<point2D_t> to_delete;
    for (point2D_t idx = 0; idx < image.NumPoints2D(); ++idx) {
      const Point2D& p2d = image.Point2D(idx);
      if (p2d.HasPoint3D() && !p2d.xy.allFinite()) {
        to_delete.push_back(idx);
      }
    }
    for (const point2D_t idx : to_delete) {
      recon.DeleteObservation(image_id, idx);
      ++num_obs_dropped;
    }
  }

  std::printf(
      "undistorted to PINHOLE (max_fov_from_axis=%.1fdeg): "
      "%zu images (unchanged), %zu -> %zu points3D, %zu observations "
      "dropped (outside representable pinhole FOV)\n",
      max_fov_deg, num_images_in, num_points_in, recon.Points3D().size(),
      num_obs_dropped);
  for (const auto& [camera_id, camera] : recon.Cameras()) {
    std::printf("  camera %u: %s %zux%zu params=[", camera_id,
                CameraModelIdToName(camera.model_id).c_str(), camera.width,
                camera.height);
    for (size_t i = 0; i < camera.params.size(); ++i) {
      std::printf("%s%.3f", i ? ", " : "", camera.params[i]);
    }
    std::printf("]\n");
  }

  std::filesystem::create_directories(out_path);
  recon.Write(out_path);
  return EXIT_SUCCESS;
}
