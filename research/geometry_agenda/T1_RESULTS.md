# T1: keep the diagnostic; do not promote a depth controller

The registered predictive gate failed. On 120 held-out synthetic proposals,
adding prospective fractional depth change raises AUC from 0.99870 to 0.99935,
below the required +0.05. The depth family rises from 0.99530 to 0.99765; the
rotation family has no failures and cannot establish discrimination. This is
a limited negative screen with little predictive headroom, not a refutation of
the projection identity or of depth-aware optimization in other regimes.

On 69 captured Eta2 proposals from three real BAL scenes, the leave-family-out
AUC changes are Dubrovnik88 0.811 to 0.795, Ladybug49 0.708 to 0.917 (only two
failures), and Venice52 0.820 to 0.769. Two of three folds worsen. Pooled scores
from separately calibrated folds must not conceal that inconsistency.

The algebra and instrumentation are useful. The exact pinhole identity agrees
to 2.22e-16 relative error, analytic chart derivatives agree with a finite-
difference step sweep to 1.65e-11, and decomposing perspective, pose-chart,
radial, and intrinsic defects reconstructs the total defect to 1.3e-14.
Independent CPU costs reproduce native trial costs within 2.2e-13 relative.
Generated instrumentation-off and original Eta2 N=3 endpoints differ by at
most 4.21e-7 relative. Instrumented endpoints remain within 8e-7 of the original
medians. This is numerical agreement, not bit identity or a timing result.

Fresh Schur residuals agree with recurrence residuals within 8.11e-13, but the
actual relative residuals range from 0.024 to 0.485 (median 0.305). Eta2 uses
intentionally loose forcing. Agreement does **not** establish an accurate
linear solve. Failed proposals have median nonlinear defect 1.943 versus 0.525
for passing proposals, while their median linear residual is actually smaller
(0.296 versus 0.351). T2 uses direct tiny solves to separate these mechanisms.

The prototype includes an optional depth penalty with camera–point cross
blocks. Schur, dense, and augmented least-squares checks pass near 1e-15.
No penalty controller, inverse-depth intervention, or GPU speed claim is
advanced because those interventions were conditional on the failed gate.
Eta2 remains the production incumbent.

## Closest prior art

Parallax BA changes both parameterization and its residual to an observation-ray
direction error in equations 9–10. It therefore cannot be treated as a same-
pixel-objective comparator without adapting the parameterization separately.
[Parallax BA, sections III-A–D](https://arxiv.org/html/1807.03556).

Square-root BA describes point elimination by QR/nullspace projection and its
equivalence to Schur elimination, including damping via augmented rows. It is
the relevant numerical reference for distinguishing solver accuracy from model
error; this experiment validates a tiny Cholesky/least-squares reference and
does not implement a production QR backend.
[Square Root BA, sections 4.1–4.4](https://arxiv.org/html/2103.01843).

## Reproduction and evidence

Run `check_geometry.py`, `check_reference.py`, `build_capture.py`,
`run_t1_capture.py`, `analyze_t1_capture.py`, `predict_depth.py`, and
`run_t1_synthetic.py` in this directory; use single-thread BLAS for CPU timings.
The source and original GPU binary hashes are in `registration.json`.
`T1_SYNTHETIC_PROTOCOL.md` predates the synthetic outcomes. JSON files with
the `t1_` prefix retain every captured/proposed outcome, including failures.
Native captures and logs are archived in the three `evidence/t1-*.tar.xz`
files. [The evidence manifest](evidence/manifest.json) records archive hashes
and hashes of every contained file. The original scratch copies remain in
`/tmp/prism-geometry-agenda/`.

The next decisive experiment is a cached curved correction under T2, compared
with the established LM-plus-geodesic baseline and additional relinearization.
