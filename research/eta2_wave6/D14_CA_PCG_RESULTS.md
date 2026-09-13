# D14 verdict: one-reduction PCG has no single-GPU crossover

## Verdict

The preconditioned Chronopoulos--Gear recurrence is numerically correct but is
rejected before a native Eta2 integration.  It cuts the measured scalar
reduction phases almost in half on the deep systems, yet produces no speedup on
the 128-update Muell capture and is 2.30% slower on the 41-update Muell
capture.  The one extra Schur product needed to fill/drain the recurrence costs
more than the saved host synchronization.  Shallow captures are 30.2% and
49.4% slower.

The fixed-system preregistration required at least a 5% gain on a hard system.
The best hard ratio is `1.0001`, so no nonlinear runs are allowed.  The frozen
Eta2 champion remains the scientific winner and the wave-5 B6v7 candidate
remains the systems winner.

## Fixed-system results

Each cell uses three warmups followed by ten arm-alternated pairs.  Products
include the explicit true-residual audit.  Times cover the resident-device
linear solve; loading and CPU construction of the common Hcc factor are
excluded from both arms.

| Capture | Standard hit | CG-CG hit | Standard products | CG-CG products | Reduction phases | Median ms standard -> CG-CG | Ratio |
|---|---:|---:|---:|---:|---:|---:|---:|
| Muell outer 11 | 0/10 | 0/10 | 129 | 129 | 259 -> 130 | 399.737 -> 399.780 | 1.0001x |
| Muell outer 12 | 10/10 | 10/10 | 42 | 43 | 85 -> 44 | 130.178 -> 133.168 | 1.0230x |
| Ladybug598 outer 8 | 10/10 | 10/10 | 3 | 4 | 7 -> 5 | 1.753 -> 2.283 | 1.3024x |
| Final1936 outer 0 | 10/10 | 10/10 | 2 | 3 | 5 -> 4 | 16.152 -> 24.138 | 1.4945x |

Muell outer 11 reaches the 128-update cap in both arms.  No pipeline-drain
product is computed at a cap, so product counts are equal and the timing ratio
directly measures the value of removing 129 scalar dependencies: it is below
measurement resolution.  Muell outer 12 converges in 41 updates in both arms;
there the required drain product makes the one-reduction form slower.

## Numerical audit

The dense random-SPD test compares both recurrences and direct Cholesky.  The
worst final relative error of Chronopoulos--Gear against the direct solution is
`5.73e-15`.  On captured BA systems:

- every reported hit passes an explicit `||b-Ax||/||b|| <= 0.5` check;
- no recurrence denominator or curvature check fails;
- paired solution differences have medians from zero to `2.42e-11`;
- Muell outer-12 true residuals agree to about `2e-13` absolute.

This rules out an algebra or convergence failure as the reason for the timing
result.

## Interpretation

Chronopoulos--Gear PCG was designed to reduce global communication on parallel
machines.  Eta2 runs on one GPU, where a Schur product streams all observation
fragments and dominates the scalar-return latency.  Wave-5 B6v2 already
captured the cheap part by returning independent dot pairs together.  D14
shows that removing the remaining dependency has essentially zero ceiling on
a product-dominated solve, while recurrence fill/drain is visible everywhere
else.

The result does not claim that communication-avoiding CG is generally slow.
It closes this recurrence for Eta2 on the measured single-GPU architecture.
Multi-GPU or distributed BA has a different communication/product ratio and
would require a separate experiment.

## Provenance

The method follows Algorithm 2 in Ghysels and Vanroose, *Hiding global
synchronization latency in the preconditioned Conjugate Gradient algorithm*,
Parallel Computing 40(7), 2014, DOI `10.1016/j.parco.2013.06.001`, which in
turn presents the Chronopoulos--Gear recurrence.  The protocol, source,
checksum-pinned build, dense audit, raw parsed rows and summaries are in
`D14_CA_PCG_PROTOCOL.md`, `d14_ca_pcg/`, `d14-fixed-results.json`, and
`d14-fixed-summary.json`.
