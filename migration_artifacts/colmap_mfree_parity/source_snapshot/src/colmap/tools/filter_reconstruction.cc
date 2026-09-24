// Filters out images whose registered pose is a wild outlier relative to the
// scene's point cloud (e.g. a degenerate/corrupted registration from an
// incremental-mapper run), and writes a new, valid Reconstruction containing
// only the well-posed images and the 3D points still observed by at least two
// of them. Not a general-purpose robustness tool -- built specifically to
// clean a real dataset (insta360x4_test) before running bundle-adjustment
// solver comparisons on it, where a handful of images had projection centers
// around 1e11-1e12 while the scene's own points spanned roughly [-35, 100] in
// each axis.
//
// Optional stride subsampling (4th arg): after pose-outlier filtering, keep
// only every Nth remaining image (sorted by name, so evenly spread across a
// video-derived sequence rather than a contiguous chunk) -- added because the
// full 3005-image/~19M-residual problem exhausted this environment's ~29GB
// cgroup memory ceiling running colmap_ba_compare (confirmed via live RSS
// sampling: >16GB and still climbing at 21 minutes in, process silently
// killed with no flushed output). Subsampling brings residual count down to
// something comparable to the venice-1778 problem (~5M residuals) that ran
// successfully earlier in this investigation.
#include "colmap/scene/reconstruction.h"

#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <unordered_set>
#include <vector>

using namespace colmap;

namespace {

double Median(std::vector<double> v) {
  std::nth_element(v.begin(), v.begin() + v.size() / 2, v.end());
  return v[v.size() / 2];
}

}  // namespace

int main(int argc, char** argv) {
  if (argc < 3) {
    std::fprintf(stderr,
                  "Usage: %s <input_model_dir> <output_model_dir> "
                  "[max_dist_from_median=1000] [stride=1]\n",
                  argv[0]);
    return EXIT_FAILURE;
  }
  const std::string in_path = argv[1];
  const std::string out_path = argv[2];
  const double max_dist = argc > 3 ? std::atof(argv[3]) : 1000.0;
  const int stride = argc > 4 ? std::atoi(argv[4]) : 1;

  Reconstruction recon;
  recon.Read(in_path);

  std::vector<double> xs, ys, zs;
  xs.reserve(recon.Points3D().size());
  ys.reserve(recon.Points3D().size());
  zs.reserve(recon.Points3D().size());
  for (const auto& [point3D_id, point3D] : recon.Points3D()) {
    xs.push_back(point3D.xyz.x());
    ys.push_back(point3D.xyz.y());
    zs.push_back(point3D.xyz.z());
  }
  const Eigen::Vector3d center(Median(xs), Median(ys), Median(zs));

  std::unordered_set<image_t> good_images;
  std::vector<image_t> bad_images;
  for (const image_t image_id : recon.RegImageIds()) {
    const Image& image = recon.Image(image_id);
    const double d = (image.ProjectionCenter() - center).norm();
    if (std::isfinite(d) && d <= max_dist) {
      good_images.insert(image_id);
    } else {
      bad_images.push_back(image_id);
    }
  }

  std::printf(
      "center (median of points3D) = (%.4f, %.4f, %.4f)\n"
      "registered images: %zu total, %zu good (dist <= %.1f), %zu bad\n",
      center.x(), center.y(), center.z(), recon.RegImageIds().size(),
      good_images.size(), max_dist, bad_images.size());
  for (const image_t id : bad_images) {
    const Image& image = recon.Image(id);
    const Eigen::Vector3d c = image.ProjectionCenter();
    std::printf("  dropped image %u '%s' center=(%.3e, %.3e, %.3e)\n", id,
                image.Name().c_str(), c.x(), c.y(), c.z());
  }

  if (stride > 1) {
    std::vector<image_t> good_sorted(good_images.begin(), good_images.end());
    std::sort(good_sorted.begin(), good_sorted.end(),
              [&recon](image_t a, image_t b) {
                return recon.Image(a).Name() < recon.Image(b).Name();
              });
    std::unordered_set<image_t> strided;
    for (size_t i = 0; i < good_sorted.size(); i += stride) {
      strided.insert(good_sorted[i]);
    }
    std::printf("stride=%d: %zu good images -> %zu kept\n", stride,
                good_images.size(), strided.size());
    good_images = std::move(strided);
  }

  // Decide which points3D survive: track filtered down to only good images
  // must still have >= 2 observations (COLMAP's own minimum for a valid
  // triangulated point).
  std::unordered_set<point3D_t> kept_point3D_ids;
  for (const auto& [point3D_id, point3D] : recon.Points3D()) {
    size_t good_count = 0;
    for (const auto& el : point3D.track.Elements()) {
      if (good_images.count(el.image_id)) ++good_count;
    }
    if (good_count >= 2) kept_point3D_ids.insert(point3D_id);
  }

  Reconstruction out;
  for (const auto& [camera_id, camera] : recon.Cameras()) {
    out.AddCameraWithTrivialRig(camera);
  }

  // Add every good image first, with all Points2D but no point3D
  // associations yet -- AddPoint3D below re-establishes them at matching
  // indices (Points2D are copied as-is, not reordered/removed, so original
  // point2D_idx values in each point3D's track remain valid).
  for (const image_t image_id : good_images) {
    Image image_copy = recon.Image(image_id);
    image_copy.ResetCameraPtr();
    image_copy.ResetFramePtr();
    for (point2D_t idx = 0; idx < image_copy.NumPoints2D(); ++idx) {
      image_copy.ResetPoint3DForPoint2D(idx);
    }
    const Rigid3d cam_from_world = recon.Image(image_id).CamFromWorld();
    out.AddImageWithTrivialFrame(std::move(image_copy), cam_from_world);
  }

  size_t num_points_written = 0;
  size_t num_obs_written = 0;
  for (const auto& [point3D_id, point3D] : recon.Points3D()) {
    if (!kept_point3D_ids.count(point3D_id)) continue;
    Track filtered_track;
    for (const auto& el : point3D.track.Elements()) {
      if (good_images.count(el.image_id)) {
        filtered_track.AddElement(el.image_id, el.point2D_idx);
      }
    }
    num_obs_written += filtered_track.Length();
    Point3D new_point3D;
    new_point3D.xyz = point3D.xyz;
    new_point3D.color = point3D.color;
    new_point3D.error = point3D.error;
    new_point3D.track = std::move(filtered_track);
    out.AddPoint3D(point3D_id, std::move(new_point3D));
    ++num_points_written;
  }

  std::printf(
      "writing filtered model: %zu images, %zu points3D, %zu obs -> %s\n",
      good_images.size(), num_points_written, num_obs_written,
      out_path.c_str());
  std::filesystem::create_directories(out_path);
  out.Write(out_path);
  return EXIT_SUCCESS;
}
