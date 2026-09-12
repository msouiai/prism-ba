# Wave 5 B5 protocol: Jacobian-consistent square-root Schur products

## Hypothesis

The frozen Eta2 operator is assembled from independently rounded ingredients:
`W = Jc^T Jp` is stored in FP32, while `Hcc`, gradients, and point diagonals
are accumulated from FP64 Jacobian rows.  Subtracting `Hcc*v - W*V^-1*W^T*v`
therefore need not be the Gram operator of any single Jacobian.  Storing one
rounded Jacobian and applying the Schur complement through projected residuals
should make curvature positive by construction and create the stable substrate
needed by B2 iterative refinement.  The 24-float Jacobian also replaces the
champion's 33 floats per observation (`W27 + Jp6`).

## Frozen comparison

- Source and flags: `research/eta2_champion/champion.json` and
  `source_manifest.json`.
- Scored objective and stopping rules are unchanged.
- B5 changes only the stored linearisation and its algebraic contractions.
- The active arm uses one FP32 `2 x 12` Jacobian per observation and FP64
  accumulation, point solves, CG recurrences, state, and acceptance.

## Registered sequence

1. Run one small audit on Ladybug49.  Compare the projected-residual action
   against the literal `Hcc*v - Jc^T Jp*u` action formed from the same stored
   Jacobian.  Also compare `v^T S v` against
   `||Jc*v-Jp*u||^2 + u^T Qp u + v^T Qin v`.  Require finite nonnegative
   curvature, relative action error below `1e-5`, and relative curvature
   identity error below `1e-8`.
2. Run a flag-off compatibility check against the frozen binary, N=3 on
   Ladybug49.  Require the ordinary floating-point trajectory tolerance used
   elsewhere in wave 5 (`<1e-10` relative endpoint difference).
3. If the audit passes, compare control and B5 at N=3 on the nine registered
   practical scene/target cells.  Report targets, crossings in both
   directions, wall ranges, endpoints, products, rejects, and geometric mean
   time ratio.
4. Profile Trafalgar138 and Muell, then run a separate Muell N=3 target cell.
5. Run N=5 on Final3068 and Venice52 only if steps 1-4 show no broad quality
   regression or prohibitive overhead.

## Kill and promotion criteria

- Kill for numerical failure if either audit threshold fails.
- Kill as a production B5 path if projected products cost more than 10% over
  the frozen path in FP64 arithmetic, or if time-to-target is worse on at
  least five of nine cells with disjoint ranges.
- Kill B2-on-B5 if endpoint quality changes by more than 0.15% on any stable
  cell or tail hit rate falls.
- B5 can remain a diagnostic/numerical asset even when its production timing
  gate fails.  B2 proceeds only if B5 is numerically sound and its measured
  overhead leaves a plausible low-precision speed ceiling.

