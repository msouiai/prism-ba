# Wave 5 B2 protocol: FP32 inner PCG with FP64 residual refinement

## Dependency correction after B5

B5's fully consistent rounded system is mathematically clean but changed the
tail basin, so iterative refinement must not solve that changed system as the
outer problem.  B2 therefore retains the frozen Eta2 assembly, reduced RHS,
equilibration, point factor, FP64 matrix-free operator, and forcing threshold.
One separately stored consistent FP32 Jacobian is used only as an approximate
correction operator.  After every FP32 correction solve, the residual is
recomputed with the frozen FP64 Eta2 operator.  A correction is accepted only
when that high-precision residual meets the same Eisenstat--Walker threshold;
otherwise the ordinary frozen PCG is run as a fallback.

This preserves the high-precision linear system and avoids inheriting B5's
registered tail failure.  It does not claim bitwise trajectory identity: any
inexact solver may return a different vector inside the same residual ball.

## Registered algorithm

- Approximate operator: one FP32 `2 x 12` Jacobian, projected-residual Schur
  form, FP32 point solves, FP32 9x9 camera-block preconditioner, FP32 CG
  vectors/recurrences/reductions.
- Coordinate scaling and intrinsic regularizer values come from the frozen
  FP64 assembly and are rounded only as they enter the correction operator.
- Inner relative tolerance per correction is
  `min(0.1, max(0.5 * eta, 1e-3))`; maximum depth is the frozen attempt's
  current CG cap.
- At most two FP32 correction solves are allowed.  Each is followed by a full
  FP64 residual.  Failure to reach `1.01 * eta * ||b||` falls back to frozen
  PCG in the same attempt.  All low and high operator applications count as
  Schur products.
- Model decrease is evaluated from the retained FP64 system on the actual
  returned iterate.  Candidate scoring, clipping, retraction, true objective,
  acceptance, damping, and stopping remain unchanged.

## Registered sequence and gates

1. Flag-off compatibility, N=3 Ladybug539, relative median endpoint below
   `1e-10`.
2. One Ladybug49 audit: every successful correction must monotonically reduce
   the FP64 residual; no approximate curvature may be nonpositive; no more
   than two correction sweeps.
3. N=3 practical nine-cell panel.  Report target times, work, refinement
   sweeps/fallbacks, endpoints, and crossings in both directions.
4. Profile Trafalgar138 and Muell, then Muell N=3.
5. N=5 Final3068 and Venice52 if steps 1--4 pass numerical validity and leave
   a plausible speed ceiling.

Kill if any correction increases the FP64 residual, if more than two sweeps
are required, if fallbacks exceed 10% of attempts on calm cells, if Krylov
time does not improve on Muell, if any stable-cell endpoint moves by more than
0.15%, or if either tail hit rate falls.  Promotion additionally requires a
time-to-target improvement with disjoint ranges on at least one deep cell and
no five-of-nine broad timing loss.
