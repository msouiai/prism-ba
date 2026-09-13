# D13b protocol: periodic exact-residual replacement in Hcc-PCG

Registered 2026-09-13 after the always-on GMRES native rejection and before
building or running the native restart arm.

## Hypothesis and selection

D13's fixed screen selected periodic exact-residual restart at depth 8 among
the PCG policies.  It reaches the unchanged `eta=0.5` gate on Muell outer 11
in 22 products versus 54 for one restart at 8 and a 128-product miss for
uninterrupted PCG.  On outer 12 it ties one-shot restart at 15 products versus
42 uninterrupted.  Ladybug598 and Final1936 finish before depth 8, so the rule
is exactly inactive there.

Always-on GMRES then won the isolated systems but failed natively because its
different early directions changed the nonlinear path.  Periodic PCG restart
tests the narrower mechanism: retain PCG's energy-minimising directions in
eight-step segments, explicitly replace the residual at a segment boundary,
and discard only old conjugacy.  The matrix, RHS, Hcc preconditioner, forcing
threshold, nonlinear controller and scored objective remain unchanged.

The sole registered arm is `OCA_PCG_RESTART_DEPTH=8` plus
`OCA_PCG_RESTART_PERIODIC=1`.  Each replacement computes `r=b-Ax` with one
charged Schur product, applies the existing Hcc preconditioner, and starts a
new valid PCG recurrence from the current iterate.  It does not allocate a new
camera vector.  Unset flags must reproduce the frozen binary.

## Native evaluation

1. N=3 no-flag compatibility on Ladybug539 at the 1.01 target.
2. N=3 paired and arm-alternated trials on the nine practical target cells.
3. N=3 paired trials on Muell at `1946488.746262194` and Final1936 at
   `5125687.352261469`.
4. Only if the practical geometric-mean time ratio is at most 1.02, no cell
   loses more than 10% with disjoint ranges, and Muell is at least 1.10x
   faster, run N=5 Final3068 and Venice52 at their existing registered targets.

Report exact target crossings, hit rates in both directions, products,
outers, rejects, endpoint costs, number of residual replacements and the
fraction of solves touched.  A shallow solve must trigger zero replacements.
Cost differences below 0.15% are unresolved.

## Kill and claim boundary

Kill globally if any practical hit is lost, the practical geometric mean is
above 1.02, five or more cells are slower, or Muell gains less than 1.10x.
Kill on the tails if hit rate falls or successful-run median time rises more
than 20%.

Residual replacement and restarted PCG are established numerical-linear-
algebra techniques.  No novelty attaches to either.  A positive contribution
would require end-to-end evidence that a forcing-metric/CG-objective mismatch
creates a predictable GPU BA crossover; a negative result closes that route.
