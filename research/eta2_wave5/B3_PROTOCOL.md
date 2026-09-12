# B3 Schur-Jacobi activation protocol

Registered before native runs.

The frozen Eta2 profile assigns 53.19% of native panel wall to Krylov work.
An earlier fixed-system study already establishes the opportunity and the
hazard: on Muell outer 12, Schur-Jacobi reduced PCG from 41 to 3 iterations and
the linear solve from 131.2 to 24.4 ms, but always-on native use changed the
opening trajectory and made the registered Muell target 20.1% slower.  An
eight-iteration within-solve upgrade was 3.6% slower.  Those arms are not
repeated.

This experiment retains the champion's explicit 9x9 Hcc camera-block PCG
preconditioner during basin selection, then permanently changes those blocks
to the 9x9 Schur diagonal when the accepted camera damping reaches
`lambda <= 1e-3`.  The threshold is fixed from the source's documented
basin/grind boundary before this run.  The complete arm is:

```
OCA_W5_PCG_SCHUR_LAM=1e-3
```

The only source overlay sets the existing public `PrismPcg::schur` selector
once this threshold is crossed; all Schur-block construction and application
code already exists in the frozen source.  It does not change forcing or the
preconditioner formulas.  Disabled-mode compatibility is required first.

Protocol amendment before any valid active run: the first registered spelling
used `OCA_BLOCKEQ`, which is a separate congruence-coordinate preconditioner
and is explicitly incompatible with the champion's `OCA_PCG`.  Its smoke test
exited at the configuration guard before producing a solver result.  That
invalid registration is retained as `b3-registration-invalid-blockeq.json`.
The arm above is the intended Schur-Jacobi upgrade of the champion's existing
PCG and was registered after diagnosing that configuration error, before any
active outcome.

Run N=3 paired trials on the nine registered practical time-to-target cells
and the previously registered Muell target.  If the practical result or Muell
shows a speed opportunity without a quality failure, run N=5 on Venice52 and
Final3068 at their registered targets.  Report switch outer, target time,
products, outers, rejects, endpoint, and ranges.  A difference needs disjoint
ranges for a speed verdict.  Kill Schur-Jacobi as a production change if it
does not reduce total products by at least 30% on switched, Krylov-heavy cells,
or if build overhead erases that saving.  Proceed to randomized Nystrom only
if the Schur activation leaves a remaining Krylov opportunity that can
amortize its sketch; do not build Nystrom merely because a fixed matrix looks
favorable.
