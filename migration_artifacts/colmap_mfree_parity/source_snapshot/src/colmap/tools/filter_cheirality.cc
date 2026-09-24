// Drops points3D that fail cheirality (behind, or too close to the image
// plane of, any observing camera) from an already-perturbed reconstruction.
// Built because a small number of such points caused two different, dramatic
// failures on the insta360x4_test comparison: Ceres's non-robust TRIVIAL loss
// let them dominate the sum-of-squares objective, making the median
// reprojection error worse even while Ceres's own (non-robust) cost
// converged; DABA-MM's fixed-damping block solve (no LM-style adaptive
// re-damping) went to NaN outright from the huge Jacobian entries near
// depth=0. Removing these points before any solver runs gives all three a
// like-for-like, numerically sane problem instead of chasing perturbation
// magnitudes that dodge the issue by luck.
//
// Operates directly on an already-perturbed reconstruction (e.g.
// colmap_ba_compare's own perturbed_input/ output) rather than
// re-perturbing from scratch, so every solver still sees the exact same
// perturbed starting point used for the original (failed) comparison.
#include "colmap/scene/projection.h"
#include "colmap/scene/reconstruction.h"

#include <cstdio>
#include <cstdlib>
#include <unordered_set>
#include <vector>

using namespace colmap;

int main(int argc, char** argv) {
  if (argc < 3) {
    std::fprintf(stderr,
                  "Usage: %s <input_model_dir> <output_model_dir> "
                  "[min_depth=0.01]\n",
                  argv[0]);
    return EXIT_FAILURE;
  }
  const std::string in_path = argv[1];
  const std::string out_path = argv[2];
  const double min_depth = argc > 3 ? std::atof(argv[3]) : 0.01;

  Reconstruction recon;
  recon.Read(in_path);

  std::unordered_set<point3D_t> kept_point3D_ids;
  size_t num_checked = 0, num_dropped_negative = 0, num_dropped_shallow = 0;
  for (const auto& [point3D_id, point3D] : recon.Points3D()) {
    ++num_checked;
    bool ok = true;
    for (const auto& el : point3D.track.Elements()) {
      const Image& image = recon.Image(el.image_id);
      const Eigen::Matrix3x4d cam_from_world = image.CamFromWorld().ToMatrix();
      const Eigen::Vector3d point_cam =
          cam_from_world * point3D.xyz.homogeneous();
      if (point_cam.z() <= 0) {
        ++num_dropped_negative;
        ok = false;
        break;
      }
      if (point_cam.z() < min_depth) {
        ++num_dropped_shallow;
        ok = false;
        break;
      }
    }
    if (ok) kept_point3D_ids.insert(point3D_id);
  }

  Reconstruction out;
  for (const auto& [camera_id, camera] : recon.Cameras()) {
    out.AddCameraWithTrivialRig(camera);
  }
  for (const image_t image_id : recon.RegImageIds()) {
    Image image_copy = recon.Image(image_id);
    image_copy.ResetCameraPtr();
    image_copy.ResetFramePtr();
    for (point2D_t idx = 0; idx < image_copy.NumPoints2D(); ++idx) {
      image_copy.ResetPoint3DForPoint2D(idx);
    }
    const Rigid3d cam_from_world = recon.Image(image_id).CamFromWorld();
    out.AddImageWithTrivialFrame(std::move(image_copy), cam_from_world);
  }
  size_t num_points_written = 0, num_obs_written = 0;
  for (const auto& [point3D_id, point3D] : recon.Points3D()) {
    if (!kept_point3D_ids.count(point3D_id)) continue;
    // Track element image ids are all still present (we dropped no images),
    // so no re-filtering of the track itself is needed here, unlike
    // filter_reconstruction.cc's image-removal case.
    if (point3D.track.Length() < 2) continue;
    Point3D new_point3D;
    new_point3D.xyz = point3D.xyz;
    new_point3D.color = point3D.color;
    new_point3D.error = point3D.error;
    new_point3D.track = point3D.track;
    num_obs_written += new_point3D.track.Length();
    out.AddPoint3D(point3D_id, std::move(new_point3D));
    ++num_points_written;
  }

  std::printf(
      "cheirality filter (min_depth=%.4f): %zu points3D checked, "
      "%zu dropped (negative depth), %zu dropped (depth < min_depth), "
      "%zu kept, %zu obs -> %s\n",
      min_depth, num_checked, num_dropped_negative, num_dropped_shallow,
      num_points_written, num_obs_written, out_path.c_str());

  std::filesystem::create_directories(out_path);
  out.Write(out_path);
  return EXIT_SUCCESS;
}
