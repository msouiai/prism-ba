# Brief 0 independent witness analysis

The registered experiment is [PROTOCOL_00.md](../PROTOCOL_00.md). This package audits captured directions at fixed states. It performs no optimizer rollout, selection, or GPU computation.

```bash
OPENBLAS_NUM_THREADS=1 python research/eta2_research_20260912/analysis/audit_capture.py \
  --capture CAPTURE_DIRECTORY --bal ORIGINAL_BAL --output AUDIT.json
OPENBLAS_NUM_THREADS=1 python research/eta2_research_20260912/analysis/audit_normals.py \
  --capture CAPTURE_DIRECTORY --bal ORIGINAL_BAL --output NORMALS.json
```

`audit_capture(capture_dir, bal_path, output_path=...)` is also a Python API. Exact matrix states and native directions are memory mapped, observations are read once per capture, and Jacobian/scoring work is chunked. The default output is compact JSON. Optional per-point compressed archives have an explicit total 20 MiB per-capture bound; arms that cannot fit are marked skipped rather than silently exceeding it.

For each native direction, the audit independently computes the full original-observation SIMPLE_RADIAL objective, unregularized GN prediction, true decrease, rho, and the registered additive model-error decomposition. Cost differences are accumulated from per-observation differences of squared residuals before global reduction. Signed and absolute errors, positive and negative contributions, track-length and parallax bins, top-200 absolute point-error concentration, flings and cheirality are retained. Tracks with fewer than two observations or undefined camera rays have a separate undefined-parallax bin.

The scene radius is `max_i ||C_i-mean(C)||2`, with `C_i=-R_i^T t_i` from the initial witness. It is distinct from the solver's scaled-camera trust radius. Maximum parallax is the largest angle between the initial world rays `X_j-C_i`, with no absolute-dot folding. Pairwise work is O(sum track-length squared), but temporary pair matrices are blocked to 256x256. Projection horizons and invalid values remain visible; no observation is dropped.

CPU/native agreement uses the fixed heuristic budget `1e-8 + 5e-10 * max(1,scale)`. Prediction scale is the sum of absolute linear terms plus the nonnegative quadratic term, so a small prediction produced by cancellation does not cause a misleading relative-error test. True-decrease agreement uses initial plus candidate cost as its scale. This is not an interval-arithmetic error bound. Original budget violations remain recorded even when far too small to change a nonlinear sign conclusion.

`audit_normals.py` separately computes the actual direction's point and full normal-equation residuals, using saved point damping diagonals, camera scaling and native intrinsic regularization. It reports the point RHS components, block Frobenius-norm backward errors, Dp-whitened residuals relative to the full scaled gradient, and stable-Jacobian versus assembled-normal residual differences. The ten worst points by absolute residual and ten by backward error receive extended-precision checks, both with FP64 rows held fixed and with geometry/Jacobians also reevaluated in `numpy.longdouble` (63 stored mantissa bits on this host).

**Certification labels matter.** The native CSV's `certified=1` certifies the reduced camera residual of the source reference solve. For `exact_clip` it remains a certificate for the source unclipped solve. It does not certify the clipped direction, full normal equations, the true nonlinear Hessian, or nonlinear usefulness. Reports call these *references with certified reduced residual*, and retain independent point/full accuracy separately. Captured files retain their literal original names.

Implementation validation includes deterministic synthetic decomposition, bin conservation, dense-versus-blocked parallax, covariance/point-equation checks, and rejection of an uncertified source in the mechanism screen. The native toy audit passed cost/prediction agreement to normalized discrepancies below `4.7e-16`; its unclipped reference point-equation relative residual was `1.39e-15`. See [verification.json](verification.json), [toy audit](results/toy-audit.json), and [toy normal audit](results/toy-normals.json).

See [FINDINGS.md](FINDINGS.md) and [ledger.csv](ledger.csv) for the nine captured states. These are mechanism diagnostics, not time-to-target/hit-rate results.
