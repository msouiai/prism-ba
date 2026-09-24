// Perturbs an existing reconstruction's rig poses, 3D points, and camera
// intrinsics, so bundle adjustment backends can be compared on a REAL model
// with a genuine descent to perform. (An already-converged model separates
// nothing: every correct solver just stops. See round10/STATUS.md.)
//
//   perturb_model --input_path DIR --output_path DIR [options]
//
// Rig-aware on purpose: noise is applied to rig_from_world (frames), never to
// per-image poses, so a multi-sensor rig stays a rig and the perturbation is
// reachable by rig-aware solvers.

#include "colmap/scene/reconstruction.h"
#include "colmap/scene/synthetic.h"
#include "colmap/util/logging.h"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <random>
#include <string>

using namespace colmap;

namespace {
double ArgD(int argc, char** argv, const char* key, double def) {
  for (int i = 1; i + 1 < argc; ++i)
    if (std::strcmp(argv[i], key) == 0) return std::atof(argv[i + 1]);
  return def;
}
std::string ArgS(int argc, char** argv, const char* key, const char* def) {
  for (int i = 1; i + 1 < argc; ++i)
    if (std::strcmp(argv[i], key) == 0) return argv[i + 1];
  return def;
}
}  // namespace

int main(int argc, char** argv) {
  const std::string in = ArgS(argc, argv, "--input_path", "");
  const std::string out = ArgS(argc, argv, "--output_path", "");
  if (in.empty() || out.empty()) {
    std::fprintf(stderr,
        "usage: perturb_model --input_path DIR --output_path DIR\n"
        "  --rot_stddev X     rig rotation noise, degrees (default 0.2)\n"
        "  --trans_stddev X   rig translation noise (default 0.02)\n"
        "  --point_stddev X   3D point noise (default 0.02)\n"
        "  --focal_stddev X   fx,fy noise, pixels (default 2.0)\n"
        "  --pp_stddev X      cx,cy noise, pixels (default 2.0)\n"
        "  --k_stddev X       first distortion param noise (default 0.002)\n");
    return 1;
  }
  Reconstruction reconstruction;
  reconstruction.Read(in);
  std::printf("read %s: %d frames, %d cameras, %d points\n", in.c_str(),
              (int)reconstruction.NumFrames(), (int)reconstruction.NumCameras(),
              (int)reconstruction.NumPoints3D());

  SyntheticNoiseOptions n;
  n.rig_from_world_rotation_stddev = ArgD(argc, argv, "--rot_stddev", 0.2);
  n.rig_from_world_translation_stddev = ArgD(argc, argv, "--trans_stddev", 0.02);
  n.point3D_stddev = ArgD(argc, argv, "--point_stddev", 0.02);
  n.point2D_stddev = 0.0;  // observations stay untouched: same objective
  SynthesizeNoise(n, &reconstruction);

  std::mt19937 rng(42);
  std::normal_distribution<double> Nf(0.0, ArgD(argc, argv, "--focal_stddev", 2.0));
  std::normal_distribution<double> Np(0.0, ArgD(argc, argv, "--pp_stddev", 2.0));
  std::normal_distribution<double> Nk(0.0, ArgD(argc, argv, "--k_stddev", 0.002));
  for (const auto& [camera_id, _] : reconstruction.Cameras()) {
    Camera& camera = reconstruction.Camera(camera_id);
    for (const size_t idx : camera.FocalLengthIdxs()) camera.params[idx] += Nf(rng);
    for (const size_t idx : camera.PrincipalPointIdxs()) camera.params[idx] += Np(rng);
    const auto extra = camera.ExtraParamsIdxs();
    if (!extra.empty()) camera.params[extra[0]] += Nk(rng);
  }

  reconstruction.Write(out);
  std::printf("wrote perturbed model to %s\n", out.c_str());
  return 0;
}
