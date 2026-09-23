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

#include "colmap/ui/bundle_adjustment_widget.h"

#include "colmap/controllers/bundle_adjustment.h"
#include "colmap/estimators/bundle_adjustment.h"
#include "colmap/estimators/bundle_adjustment_caspar.h"
#include "colmap/estimators/bundle_adjustment_mfree.h"
#include "colmap/estimators/bundle_adjustment_ceres.h"
#include "colmap/ui/main_window.h"
#include "colmap/util/controller_thread.h"

namespace colmap {

BundleAdjustmentWidget::BundleAdjustmentWidget(MainWindow* main_window,
                                               OptionManager* options)
    : OptionsWidget(main_window),
      main_window_(main_window),
      options_(options),
      reconstruction_(nullptr),
      thread_control_widget_(new ThreadControlWidget(this)) {
  setWindowFlags(Qt::Dialog);
  setWindowModality(Qt::ApplicationModal);
  setWindowTitle("Bundle adjustment");

  AddOptionInt(
      &options->bundle_adjustment->ceres->solver_options.max_num_iterations,
      "max_num_iterations");
  AddOptionInt(&options->bundle_adjustment->ceres->solver_options
                    .max_linear_solver_iterations,
               "max_linear_solver_iterations");

  AddOptionDoubleLog(
      &options->bundle_adjustment->ceres->solver_options.function_tolerance,
      "function_tolerance [10eX]",
      -1000,
      1000);
  AddOptionDoubleLog(
      &options->bundle_adjustment->ceres->solver_options.gradient_tolerance,
      "gradient_tolerance [10eX]",
      -1000,
      1000);
  AddOptionDoubleLog(
      &options->bundle_adjustment->ceres->solver_options.parameter_tolerance,
      "parameter_tolerance [10eX]",
      -1000,
      1000);

  AddOptionBool(&options->bundle_adjustment->refine_focal_length,
                "refine_focal_length");
  AddOptionBool(&options->bundle_adjustment->refine_principal_point,
                "refine_principal_point");
  AddOptionBool(&options->bundle_adjustment->refine_extra_params,
                "refine_extra_params");
  AddOptionBool(&options->bundle_adjustment->refine_rig_from_world,
                "refine_rig_from_world");
  AddOptionBool(&options->bundle_adjustment->refine_sensor_from_rig,
                "refine_sensor_from_rig");
  AddOptionBool(&options->bundle_adjustment->refine_points3D,
                "refine_points3D");

#if defined(CASPAR_ENABLED) || defined(MFREE_ENABLED)
  AddSection("Bundle Adjustment Backend");
  auto* backend_combo = new QComboBox(this);
  // Item index must equal the BundleAdjustmentBackend value, so every backend
  // is listed even when this build cannot run it; selecting an unavailable one
  // fails with the explicit "rebuild with -D..._ENABLED=ON" message.
  backend_combo->addItem("CERES");   // 0 == BundleAdjustmentBackend::CERES
  backend_combo->addItem("CASPAR");  // 1 == BundleAdjustmentBackend::CASPAR
  backend_combo->addItem("MFREE");   // 2 == BundleAdjustmentBackend::MFREE
  backend_combo->setCurrentIndex(
      static_cast<int>(options->bundle_adjustment->backend));
  connect(backend_combo,
          QOverload<int>::of(&QComboBox::currentIndexChanged),
          [options](int idx) {
            options->bundle_adjustment->backend =
                static_cast<BundleAdjustmentBackend>(idx);
          });
  AddWidgetRow("backend", backend_combo);

  AddSection("Caspar Options");
  AddOptionText(&options->bundle_adjustment->caspar->gpu_index,
                "gpu_index (-1 = auto)");

  AddSection("MFREE Options");
  AddOptionInt(&options->bundle_adjustment->mfree->max_num_iterations,
               "mfree max_num_iterations", 1, 10000);
  AddOptionDouble(&options->bundle_adjustment->mfree->point_damping,
                  "mfree point_damping", 1e-9, 1e3, 1e-4, 9);
  AddOptionBool(&options->bundle_adjustment->mfree->use_fp32_fragments,
                "mfree use_fp32_fragments");
  AddOptionInt(&options->bundle_adjustment->mfree->gpu_index,
               "mfree gpu_index (-1 = auto)", -1, 64);

  auto show_backend_options = [this, options](int idx) {
    const auto backend = static_cast<BundleAdjustmentBackend>(idx);
    auto set = [&](bool on, auto* opt) {
      if (on) {
        ShowOption(opt);
      } else {
        HideOption(opt);
      }
    };
    const bool is_caspar = backend == BundleAdjustmentBackend::CASPAR;
    const bool is_mfree = backend == BundleAdjustmentBackend::MFREE;
    set(is_caspar, &options->bundle_adjustment->caspar->gpu_index);
    set(is_mfree, &options->bundle_adjustment->mfree->max_num_iterations);
    set(is_mfree, &options->bundle_adjustment->mfree->point_damping);
    set(is_mfree, &options->bundle_adjustment->mfree->use_fp32_fragments);
    set(is_mfree, &options->bundle_adjustment->mfree->gpu_index);
  };
  show_backend_options(
      static_cast<int>(options->bundle_adjustment->backend));
  connect(backend_combo,
          QOverload<int>::of(&QComboBox::currentIndexChanged),
          show_backend_options);
#endif

  QPushButton* run_button = new QPushButton(tr("Run"), this);
  grid_layout_->addWidget(run_button, grid_layout_->rowCount(), 1);
  connect(
      run_button, &QPushButton::released, this, &BundleAdjustmentWidget::Run);

  render_action_ = new QAction(this);
  connect(render_action_,
          &QAction::triggered,
          this,
          &BundleAdjustmentWidget::Render,
          Qt::QueuedConnection);
}

void BundleAdjustmentWidget::Show(
    std::shared_ptr<Reconstruction> reconstruction) {
  reconstruction_ = std::move(reconstruction);
  show();
  raise();
}

void BundleAdjustmentWidget::Run() {
  THROW_CHECK_NOTNULL(reconstruction_);

  WriteOptions();

  auto thread = std::make_unique<ControllerThread<BundleAdjustmentController>>(
      std::make_shared<BundleAdjustmentController>(*options_, reconstruction_));
  thread->AddCallback(Thread::FINISHED_CALLBACK,
                      [this]() { render_action_->trigger(); });

  // Normalize scene for numerical stability and
  // to avoid large scale changes in viewer.
  reconstruction_->Normalize();

  thread_control_widget_->StartThread(
      "Bundle adjusting...", true, std::move(thread));
}

void BundleAdjustmentWidget::Render() { main_window_->RenderNow(); }

}  // namespace colmap
