// End-to-end check of the MFREE COLMAP backend without gtest: synthesize a
// reconstruction, perturb it, run BA through the public factory, and report
// the median reprojection error before and after.
#include "colmap/estimators/bundle_adjustment.h"
#include "colmap/estimators/bundle_adjustment_mfree.h"
#include "colmap/scene/projection.h"
#include "colmap/scene/synthetic.h"
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <vector>

using namespace colmap;

static double MedianErr(const Reconstruction& r) {
  std::vector<double> e;
  for (const image_t id : r.RegImageIds()) {
    const Image& im = r.Image(id);
    for (const Point2D& p2 : im.Points2D()) {
      if (!p2.HasPoint3D()) continue;
      e.push_back(std::sqrt(CalculateSquaredReprojectionError(
          p2.xy, r.Point3D(p2.point3D_id).xyz, im.CamFromWorld(),
          *im.CameraPtr())));
    }
  }
  std::sort(e.begin(), e.end());
  return e.empty() ? -1 : e[e.size() / 2];
}

// Runs one backend on a COPY of the same perturbed reconstruction, so CERES
// and MFREE are compared on identical input rather than in sequence.
static void RunBackend(const char* label, Reconstruction rec,
                       BundleAdjustmentBackend backend, double tau,
                       bool refine_intr = true) {
  const double before = MedianErr(rec);
  BundleAdjustmentConfig cfg;
  for (const image_t id : rec.RegImageIds()) cfg.AddImage(id);
  BundleAdjustmentOptions opts;
  opts.backend = backend;
  opts.print_summary = false;
  opts.mfree->point_damping = tau;
  opts.mfree->refine_intrinsics = refine_intr;

  std::vector<double> p0 = rec.Camera(rec.Image(*rec.RegImageIds().begin()).CameraId()).params;
  auto sum = CreateDefaultBundleAdjuster(opts, cfg, rec)->Solve();
  std::vector<double> p1 = rec.Camera(rec.Image(*rec.RegImageIds().begin()).CameraId()).params;
  const auto* m = dynamic_cast<const MFreeBundleAdjustmentSummary*>(sum.get());
  const double after = MedianErr(rec);
  // The solver's OWN view of the error. If this disagrees with COLMAP's
  // `before`, the adapter is feeding it a different problem than COLMAP scores
  // -- a setup bug, not a convergence problem.
  const bool failed =
      sum->termination_type == BundleAdjustmentTerminationType::FAILURE;
  if (m != nullptr && !failed) {
    std::printf("  %-26s medA %8.4f -> %8.4f   [solver saw %8.4f -> %8.4f, "
                "cost %.4g -> %.4g, %d it]\n",
                label, before, after, m->initial_median_reproj_error_px,
                m->final_median_reproj_error_px, m->initial_cost, m->final_cost,
                m->iteration_count);
    std::printf("      cam0 params:");
    for (size_t i = 0; i < p0.size(); ++i)
      std::printf(" %.4g->%.4g", p0[i], p1[i]);
    std::printf("\n");
  } else if (m != nullptr) {
    std::printf("  %-26s REFUSED: %s\n", label,
                m->message.empty() ? "(no reason given)" : m->message.c_str());
  } else {
    std::printf("  %-26s medA %8.4f -> %8.4f   %s\n", label, before, after,
                sum->termination_type ==
                        BundleAdjustmentTerminationType::FAILURE
                    ? "FAILURE" : "");
  }
}

static void Run(const char* label, bool unique_cameras) {
  Reconstruction rec;
  SyntheticDatasetOptions o;
  if (unique_cameras) { o.num_rigs = 10; o.num_frames_per_rig = 1; }
  else                { o.num_rigs = 1;  o.num_frames_per_rig = 10; }
  o.num_cameras_per_rig = 1;
  o.num_points3D = 200;
  o.camera_model_id = CameraModelId::kSimpleRadial;
  SynthesizeDataset(o, &rec);

  SyntheticNoiseOptions n;
  n.point2D_stddev = 0.5; n.point3D_stddev = 0.1;
  n.rig_from_world_rotation_stddev = 0.5;
  n.rig_from_world_translation_stddev = 0.1;
  SynthesizeNoise(n, &rec);

  std::printf("\n== %s ==\n", label);
  RunBackend("CERES", rec, BundleAdjustmentBackend::CERES, 3e-3);
  RunBackend("MFREE intr=OFF", rec, BundleAdjustmentBackend::MFREE, 3e-3, false);
  RunBackend("MFREE intr=ON", rec, BundleAdjustmentBackend::MFREE, 3e-3, true);
}

// Optional: run on a real reconstruction on disk instead of synthetic data.
static void RunPath(const char* path) {
  Reconstruction rec;
  try {
    rec.Read(path);
  } catch (const std::exception& e) {
    std::printf("\n== %s ==\n  could not read: %s\n", path, e.what());
    return;
  }
  std::printf("\n== %s ==\n  %d images, %d cameras, %d points\n", path,
              static_cast<int>(rec.NumRegImages()),
              static_cast<int>(rec.NumCameras()),
              static_cast<int>(rec.NumPoints3D()));
  RunBackend("CERES", rec, BundleAdjustmentBackend::CERES, 3e-3);
  RunBackend("MFREE tau=3e-3", rec, BundleAdjustmentBackend::MFREE, 3e-3);
}

int main(int argc, char** argv) {
  std::printf("MFREE available: %s\n",
              IsMFreeBundleAdjustmentAvailable() ? "yes" : "no");
  if (argc > 1) {
    for (int i = 1; i < argc; ++i) RunPath(argv[i]);
    return 0;
  }
  Run("shared camera", false);
  Run("unique cameras", true);
  return 0;
}
