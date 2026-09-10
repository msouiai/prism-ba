# Schur preconditioner follow-up to Claude round 8

This isolated experiment starts from the published eta2 package at d3d42dc.
Original solver sources, frozen package, and production defaults are unchanged.
See RESULTS.md for measured outcomes and ARCHITECTURE.md for the single/five
question. No Caspar comparison is rerun here; Claude owns cross-validation.

Requirements: CUDA/nvcc, cuBLAS/cuSOLVER, Eigen3, an sm_89 GPU and BAL inputs.
Build scripts verify the frozen source and all 44 headers before patching copies.

```bash
python3 research/eta2_champion/build.py
python3 research/schur_preconditioner/build.py
python3 research/schur_preconditioner/run_fixed.py
python3 research/schur_preconditioner/build_solver.py
python3 research/schur_preconditioner/run_targets.py
python3 research/schur_preconditioner/run_targets.py --upgrade
python3 research/schur_preconditioner/summarize.py
python3 research/schur_preconditioner/summarize.py --upgrade
```

Runners accept `--data-root`, `--output`, and `--baseline`. Defaults are
/workspace/bal, /workspace/prism-schur-eta2, and the freshly built frozen package.
They take the local /tmp/prism_gpu.lock themselves. Capture files occupy about
904 MiB; retain them for exact fixed-state replay. Do not substitute states if
the registered outer is not reached. The standalone fixed executable takes the
capture directory as its sole argument. Summarizer uses the default output root.

Integrated research switch `OCA_PCG_GRAM`:
- absent/0: original fresh Hcc block PCG.
- 1: fresh Schur block Jacobi with forward-solve Gram construction.
- 2: begin every solve with Hcc; after eight iterations, if still unfinished,
  recompute the true residual and restart from the current x using Gram Schur
  blocks. Charge the extra product and construction; retain the total 128 cap.

These modes are restricted to the frozen fixed-eta2, compact2, unshared classical
LM path. Learned policies and replay are not supported by this extension.
The preconditioner does not change the matrix, RHS, damping, coordinate scaling,
linear tolerance, cost acceptance, or target definitions. It can change the
inexact direction and subsequent nonlinear trajectory; that is why the full
fixed-target gate is required even after a large fixed-system speedup.

The fixed benchmark compares Hcc, legacy Schur, and Gram Schur on identical
captured data, three repetitions with rotating arm order after one warm-up.
It checks unfactored block parity, Cholesky fallback counts, and the true linear
residual. Timed intervals include construction and residual verification. A cap
miss is not an equal-accuracy timing win. End-to-end runs alternate arms, N=3,
and retain the previously registered sustained-eta2 targets.

Schur Jacobi is established BA practice, documented in
[Ceres](https://ceres-solver.readthedocs.io/latest/nnls_solving.html#schur-jacobi).
The Gram identity and PCG restart are standard algebra. This is an implementation
and empirical-selection study, not a claim of a novel preconditioner.
