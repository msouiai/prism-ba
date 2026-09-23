// Writes a small synthetic COLMAP model with REALISTIC observation noise, for
// benchmarking bundle adjustment backends against each other.
//
// The distinction that matters: perturbing only the poses and 3D points leaves
// the observations exact, so the true optimum is zero reprojection error and
// every correct solver reaches it -- a comparison on such a model measures
// nothing but correctness. Adding point2D noise gives the problem a genuine
// noise floor, so solvers separate on how close they get and how fast.
//
//   synthesize_ba_model --output_path DIR [options]

#include "colmap/scene/reconstruction.h"
#include "colmap/scene/synthetic.h"
#include "colmap/util/logging.h"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>

using namespace colmap;

namespace {

double ArgD(int argc, char** argv, const char* key, double def) {
  for (int i = 1; i + 1 < argc; ++i)
    if (std::strcmp(argv[i], key) == 0) return std::atof(argv[i + 1]);
  return def;
}
int ArgI(int argc, char** argv, const char* key, int def) {
  for (int i = 1; i + 1 < argc; ++i)
    if (std::strcmp(argv[i], key) == 0) return std::atoi(argv[i + 1]);
  return def;
}
std::string ArgS(int argc, char** argv, const char* key, const char* def) {
  for (int i = 1; i + 1 < argc; ++i)
    if (std::strcmp(argv[i], key) == 0) return argv[i + 1];
  return def;
}

}  // namespace

int main(int argc, char** argv) {
  const std::string out = ArgS(argc, argv, "--output_path", "");
  if (out.empty()) {
    std::fprintf(stderr,
        "usage: synthesize_ba_model --output_path DIR\n"
        "  --num_images N        (default 50)\n"
        "  --num_points N        (default 3000)\n"
        "  --track_length N      (default 10; -1 = every image sees every point)\n"
        "  --shared_camera 0|1   (default 1: one camera for all images, the\n"
        "                         layout COLMAP normally produces)\n"
        "  --point2D_stddev X    (default 0.5 px -- the noise FLOOR; set 0 for\n"
        "                         an exactly-recoverable problem)\n"
        "  --point3D_stddev X    (default 0.05)\n"
        "  --rot_stddev X        (default 0.5 deg)  --trans_stddev X (default 0.05)\n");
    return 1;
  }

  const int num_images = ArgI(argc, argv, "--num_images", 50);
  const bool shared = ArgI(argc, argv, "--shared_camera", 1) != 0;

  SyntheticDatasetOptions d;
  // One rig with many frames => all frames share a camera. Many rigs of one
  // frame => each image owns its camera.
  if (shared) {
    d.num_rigs = 1;
    d.num_frames_per_rig = num_images;
  } else {
    d.num_rigs = num_images;
    d.num_frames_per_rig = 1;
  }
  d.num_cameras_per_rig = 1;
  d.num_points3D = ArgI(argc, argv, "--num_points", 3000);
  d.track_length = ArgI(argc, argv, "--track_length", 10);
  // SIMPLE_RADIAL is inside the MFREE backend's supported set.
  d.camera_model_id = SimpleRadialCameraModel::model_id;

  Reconstruction reconstruction;
  SynthesizeDataset(d, &reconstruction);

  SyntheticNoiseOptions n;
  n.point2D_stddev = ArgD(argc, argv, "--point2D_stddev", 0.5);
  n.point3D_stddev = ArgD(argc, argv, "--point3D_stddev", 0.05);
  n.rig_from_world_rotation_stddev = ArgD(argc, argv, "--rot_stddev", 0.5);
  n.rig_from_world_translation_stddev = ArgD(argc, argv, "--trans_stddev", 0.05);
  SynthesizeNoise(n, &reconstruction);

  reconstruction.Write(out);
  std::printf("wrote %s: %d images, %d cameras, %d points, %d observations\n",
              out.c_str(),
              static_cast<int>(reconstruction.NumRegImages()),
              static_cast<int>(reconstruction.NumCameras()),
              static_cast<int>(reconstruction.NumPoints3D()),
              static_cast<int>(reconstruction.ComputeNumObservations()));
  std::printf("  observation noise floor: %.2f px\n", n.point2D_stddev);
  return 0;
}
