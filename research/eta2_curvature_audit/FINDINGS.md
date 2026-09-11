# Confirmed: rounded cross blocks create false negative curvature

All three captured Venice52 failures are negative directions of Eta2's
stored mixed-precision operator, but positive directions of the same-state
FP64 damped Gauss–Newton operator. Replacing **only the camera–point cross
blocks** with their FP64 values changes the sign in every capture. State,
direction, Hcc, camera scaling E, camera damping and point factors are held
fixed. Point-factor precision alone does not fix the sign.

This reconciles the local cutoff behavior with MFREE's reported zero-cutoff
FP64 trajectories. It does not prove a new solver reaches the Venice target,
is faster, or has better global convergence. No optimization policy changed.
The frozen Eta2 remains the performance champion pending a separate A/B test.

## Controlled comparison

Registration: `d2dbfa5`; diagnostic implementation: `db4d351`.
Three fresh runs reproduce the first de-clipping cutoff after 39 accepted
outers. Costs are about 248405.4, with lambda=tau=1e-8. All use the exact
registered BAL bytes and the previous de-clipping prototype's trajectory.
Comparisons within each capture use the identical accepted state and CG
search direction; comparisons across trajectories are not used for attribution.
The quantities below are p^T A p / p^T p in the original equilibrated
camera coordinates. The actual cutoff is a positive 1e-14.

| Capture | Completed CG iterations | Stored W32 / stored point factor | FP64 cross blocks only | FP64 point factor only | Both FP64 |
|---|---:|---:|---:|---:|---:|
| 0 | 17 | -2.571521825e-09 | 4.102612694e-08 | -2.582673149e-09 | 4.102618337e-08 |
| 1 | 23 | -5.573835268e-10 | 3.433541681e-08 | -5.609904073e-10 | 3.433542514e-08 |
| 2 | 15 | -2.105306815e-09 | 4.277910817e-08 | -2.108942563e-09 | 4.277910045e-08 |

The quotients are strictly negative, not small positive numbers accidentally
excluded by the cutoff. Repeating the same mixed GPU operator five times
per capture changes the quotient by at most **1.045e-21**. That variability
is far too small to explain the observed sign. Recomputing QR from the
same stored FP32 point rows also leaves the sign unchanged; the guarded
point-factor preparation is not the cause in these captures.

The independent CPU Schur calculation uses 64-significand-bit extended
precision accumulation and triangular solves on exported operands. Its
largest discrepancy from any GPU variant is **1.788e-16** in normalized
Rayleigh units. A second reference evaluates the full Jacobian residual
energy plus nonnegative damping terms, avoiding Schur subtraction entirely.

| Capture | CPU FP64-components Schur quotient | Nonnegative Jacobian energy |
|---|---:|---:|
| 0 | 4.102618334531e-08 | 4.102618325012e-08 |
| 1 | 3.433542515099e-08 | 3.433542582539e-08 |
| 2 | 4.277910049134e-08 | 4.277910092996e-08 |

All camera/point Jacobians in the reference are rebuilt from the exact
captured matrix state. Across **28,121,013 cross-block entries** and
**6,249,114 point-Jacobian entries**, the stored FP32 values equal casts of
the corresponding FP64 values with **zero mismatches**. This isolates
rounding from a changed linearization or indexing bug. Original Hcc and
Cdiag are held fixed; independent camera reassembly changes the same-vector
quotient by at most about 2e-15, far below the cross-rounding effect.
Exported states also pass independent CPU FP64 objective checks against the
original observation set. This is not a new derivative-validation test:
analytic Jacobian rows come from the existing routine.

## Why the sign changes

For v=E p and the fixed damped point block V=R^T R, the reduced quadratic is

    q = v^T U v - ||R^-T W^T v||^2 + lambda ||p||^2.

The camera block U is accumulated in FP64 from unrounded Jacobian rows,
while W is rounded independently to FP32. Such independent block rounding
does not preserve the positive semidefinite Gram-matrix structure. A
positive damping shift does not necessarily dominate the resulting error.

For a normalized direction, put y=R^-T W64^T v and
z=R^-T (W32-W64)^T v. The exact fixed-factor perturbation identity is

    q(W32)-q(W64) = -2 y^T z - ||z||^2.

The squared error term is always nonpositive and can be magnified by weak
point directions. Its dominance is measured here, not inferred from a
whole-trajectory endpoint difference:

| Capture | Linear error term | Negative squared-error term | Total cross-rounding error |
|---|---:|---:|---:|
| 0 | 1.882507923e-11 | -4.361647383e-08 | -4.359764875e-08 |
| 1 | -4.746731924e-11 | -3.484533315e-08 | -3.489280047e-08 |
| 2 | -1.674431390e-10 | -4.471697171e-08 | -4.488441485e-08 |

The CPU calculation checks this identity directly. Point elimination
amplifies the cross-block rounding enough to overwhelm positive FP64
curvature on these directions. The original nonlinear BA objective may
still have nonconvex behavior; the conclusion concerns these particular
**damped Gauss–Newton operators**, not an absence of nonlinear saddles.

## Localization: the same two fragile points

Post-hoc point-level decomposition identifies zero-based BAL points
**60378 and 60447** in all three captures. Each has two observations, in
cameras **32 and 40**. Together they account for approximately 100% of the
signed cross-rounding error; small contributions elsewhere can cancel and
make the signed fraction slightly exceed 100%.

Both points lie extremely close to camera32 relative to the camera32–40
baseline, with nearly antiparallel rays (about 179.2 degrees). Their damped
point normal condition numbers are approximately **5.2–5.3e8**, and their
largest point-Jacobian singular values are around **8e6–1.3e7**. These are
coordinates in the BAL model's arbitrary units, not metric distances.
The same ill-conditioned geometry amplifies precision error in all captures.

As an algebraic counterfactual, upgrading only these two points' cross blocks
would make each captured quotient positive. This follows from the additive
point terms already measured; it is **not a tested runtime policy** and must
not become a hard-coded point-ID rule. `localization.json` records the camera
IDs, singular values, ray geometry, and counterfactual quotient.

This connects the numerical failure to fragile tracks, but does not prove
that Config S's basin-selection gains, Eta2's radius collapse, and this
precision fault all share one cause. Those are different measured regimes.

## Consequence and next experiment

Do not loosen the curvature cutoff to hide the failure, or treat another
larger CG budget as an accuracy fix. The stored operator itself is
indefinite on the captured vectors. The fully consistent high-precision
model is positive there.

The next controlled optimization baseline should change cross-block
precision alone, preserving the current controller and target protocol.
That would measure the memory/time cost and whether removing false curvature
repairs improves target attainment. These diagnostics already show that
upgrading point QR alone is not the right fix on this phase.

A subsequent representation experiment could preserve Gram consistency by
forming the blocks from common rounded Jacobian rows, or use condition-aware
precision. Either requires its own correctness and performance gates; no
such implementation or speed benefit is claimed here. Restoring the
(lambda,R) controller pair remains another separately testable hypothesis.

## Evidence and limits

The three runs are controlled examples from one phase of one scene, not a
BAL-wide frequency estimate. GPU repeats and CPU references validate the
local operator diagnosis. The diagnostic exits at capture, so its runtime
and endpoint must not be used as optimization benchmarks.

- `results.json`: full GPU/CPU factorial comparisons and error decomposition.
- `rounding_identity.json`: exact cast correspondence for all stored entries.
- `localization.json`: post-hoc point-level geometry.
- `evidence/capture-*/`: metadata, manifests, raw GPU quotient CSVs, logs and audits.
- Verified archive: all exported arrays, exact states, source and binary;
  see `archive.json` once packaging completes.

The original solver and the preceding depth-rescue negative result remain
unchanged. [README.md](README.md) gives reproduction commands.
