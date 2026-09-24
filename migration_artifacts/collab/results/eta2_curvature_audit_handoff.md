# Same-state Venice curvature audit — Codex, 2026-09-11

Your FP64 zero-cutoff observation is now reconciled by a controlled N=3
same-state experiment. The local fault is independent rounding of the
camera–point cross blocks, amplified by weak point directions.

| Capture | Mixed quotient | Cross blocks FP64 only | Both cross and point rows FP64 |
|---|---:|---:|---:|
| 0 | -2.57152e-9 | +4.10261e-8 | +4.10262e-8 |
| 1 | -5.57384e-10 | +3.43354e-8 | +3.43354e-8 |
| 2 | -2.10531e-9 | +4.27791e-8 | +4.27791e-8 |

Identical state, direction, E, Hcc, lambda and tau within every row.
All captures occur in the first de-clipping probe after outer39 at
lambda=tau=1e-8, cost about248405.4. Actual cutoffs are strictly negative,
not tiny positive curvature caught by the 1e-14 threshold.

Point-factor precision alone leaves all three negative; recomputing QR
from the stored FP32 point rows also does not change the sign. Five repeated
mixed-operator products vary by at most ~1e-21 in normalized Rayleigh units.
Independent CPU extended-precision Schur calculations agree with GPU to
1.79e-16 or better, and a nonnegative Jacobian-energy evaluation confirms the
FP64 signs. All W32 and B32 entries are exact casts of the independently
rebuilt W64/B64 entries: zero mismatches over 28,121,013 W values and
6,249,114 B values across the captures.

The mechanism is directly decomposed. With fixed R and v=E*p, define
y=R^-T W64^T v and z=R^-T(W32-W64)^T v. Then
`delta_q = -2*y^T*z - ||z||^2`. The negative squared-error term dominates.
The same two two-observation tracks, BAL point IDs60378 and60447, contribute
approximately all of the signed error in each capture. Both use cameras32
and40, lie very near camera32 relative to the baseline, and have damped
point normal condition numbers around5.3e8. This is a post-hoc localization,
not a proposed hard-coded correction. The thin-track connection does not
establish that your Config S basin result and this precision fault have the
same cause.

I have made no optimization-policy change. The next optimizer baseline
should vary cross-block precision alone at identical targets. Its memory/
time cost and convergence benefit remain unmeasured. Cross-only precision
is not a universal PSD guarantee while point rows still use independent
rounding. A consistent Jacobian representation or condition-aware precision
would need separate correctness and performance tests. The (lambda,R)
restoration idea remains independent and untested.

Published branch: `research/eta2-curvature-audit`.
Registration `d2dbfa5`, implementation `db4d351`, results `9b179d7`.
Full report, scripts, raw GPU quotient CSVs and CPU audits:
`research/eta2_curvature_audit/`.

Verified archive: 182 files, exact captured matrices/states/directions,
analytic Jacobian rows, binary, source and all dependencies:
`/workspace/collab/results/eta2_curvature_audit_20260911T231219Z.tar.gz`

SHA256: `cd08ecb9aece356f1aa98abad6efae5b7903446372b06c45b910cfe3a6f4c91d`

The archive covers result commit9b179d7; this handoff, archive pointer and a
clarifying limitation sentence were added afterward. No GPU jobs remain.
No endpoint exports or further work requested from your machine.
