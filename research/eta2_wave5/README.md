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
