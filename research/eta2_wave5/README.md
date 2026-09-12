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
- B1 factored Jacobian storage preserves products, outers, and endpoints, but
  version 1 is 3.85% slower on the panel because reconstruction raises register
  pressure and Krylov time.  One preregistered algebraic contraction follow-up
  is in progress before the family is closed.
