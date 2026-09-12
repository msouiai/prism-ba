# Eta2 wave 5

This directory records the course-correction and linear-algebra experiments
requested after wave 4.  The frozen Eta2 champion is never edited.  Every
native intervention is a reversible overlay built from the source and headers
whose hashes are pinned in `research/eta2_champion/source_manifest.json`.

The order is deliberate:

1. replay the wave-4 E4 branch with targeted nonlinear two-view point repair;
2. profile the frozen champion by phase on the nine practical cells;
3. settle the adaptive robust opening and `rho_min=1e-3` with fresh N=10
   cohorts;
4. pursue Schur-Jacobi and later algebraic changes only where the measured
   phase ceiling justifies their cost.

Large endpoint states and diagnostic arrays are ignored here but are retained
losslessly with hashes and restoration metadata.  Compact protocols, code,
tables, and verdicts are committed.

Current decisions:

- A1 exact targeted two-view repair closes the recorded E4 point-level model
  error, but its native greedy use worsens Venice and does not improve the
  Final3068 hit rate.
- A2 adaptive robust-stage exit loses the wave-4 O5 signal; A4 `rho_min=1e-3`
  is unresolved on Final3068 and significantly worse on Venice.
- B0 assigns 53.19% of practical-panel native wall to Krylov work.
- B3's phase-switched Schur-Jacobi arm is rejected despite selected product
  savings: it is slower overall and loses tail reliability.  Nystrom is not
  pursued on that base.
- B1 factored Jacobian storage preserves products, outers, and endpoints.
  Version 2 recovers almost all of version 1's 3.85% panel loss, but remains
  0.34% slower on the panel and 3.28% slower on profiled Muell.  The production
  family is rejected; the representation is retained as a possible B2
  low-precision substrate.
- B4 exact dense Schur dispatch is rejected.  It is operator-equivalent to
  `3.53e-16`, yet Trafalgar target time is 1.49--2.77x slower.  On Venice52,
  Schur formation alone consumes 56.72 of 60.12 seconds and the exact step
  follows a worse clipped trajectory; FP64 Cholesky is only 0.84 seconds.
- B6 batched FP64 dot reductions plus fused PCG vector updates improve the
  practical-panel geometric mean by 3.62% with identical median product counts,
  but the fused arithmetic perturbs the Final3068 tail trajectory.  The
  combined arm is not promoted; a preregistered dots-only isolation follows.
- B6v2 dots-only batching is the current systems winner: 1.32% faster on the
  practical-panel geometric mean, identical work counts, 8/10 Final3068 hits
  in both arms, and no Venice endpoint movement.  It remains an overlay while
  exact-rounding vector fusion is tested for the remaining launch overhead.
- B6v3 exact-rounding vector fusion passes a 1,000,003-element bitwise audit
  but is rejected: 0.24% panel gain versus 1.44% for dots-only in the same
  three-arm cohort.  Its custom kernels help deep CG and do not pay reliably
  in the smallest cells.
- B5's Jacobian-consistent square-root Schur path is algebraically exact and
  reduces fragment storage, but is rejected after losing both tail cohorts.
  Backward stability does not preserve a basin-sensitive BA trajectory.
- B2's FP32 correction solves pass the frozen FP64 residual gate with zero
  fallbacks and make six of nine practical cells faster, but require
  1.07--4.40x more products and move median endpoints by as much as 0.519%.
  A loose forcing tolerance defines a set of valid directions rather than one
  direction, so ordinary iterative-refinement guarantees do not make this a
  transparent acceleration.  The arm is rejected before Muell and tail runs.
- B6v4 removes preparation work whose Schur-diagonal output is immediately
  discarded by the frozen classical-LM path.  Combined with dots-only batching
  it is 7.78% faster on the practical panel and 2.35% faster on Muell, with
  unchanged stable-cell work counts.  The N=30 Final3068 extension gives
  17/30 hits versus 18/30 for dots-only.  This combined arm is the strongest
  wave-5 research candidate; the intervals are still too wide for a formal
  reliability-equivalence claim.
- B6v5 preserves the old RHS atomic work and applies only three bitwise fusions.
  It is 1.79% faster on the panel but neutral on Muell, confirming that the
  discarded diagonal work is the source of B6v4's large-scene gain.
