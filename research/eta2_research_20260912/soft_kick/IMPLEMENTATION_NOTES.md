# Brief 11 implementation details frozen before native data

[PROTOCOL_11](../PROTOCOL_11.md) authorizes the implementation. The source
hooks and derivations are in [FEASIBILITY.md](FEASIBILITY.md); choices left
open there are resolved here before testing.

* Confirmed FTOL means a reason-tagged original FTOL or function-tolerance
  stop that survives the existing backtrack-confirmation/rearm blocks. The
  champion requires no extra confirmation if no backtrack rescue occurred.
  Failure-count, target, budget and cap stops do not trigger a kick.
* The pending event is processed after fresh normals/factors/E are built,
  immediately before sweep initialization and before forcing history changes.
  Preserve current lambda, radius, numeric floor, previous residual norm,
  last relative decrease and backtrack state. Clear FTOL/failure streaks and
  update prev_cost only after an admitted kick. No future fine solve consumes
  a stale factor or state-dependent assembly.
* Reuse existing K8 geometry and coarse assembly kernels, without enabling
  their additive preconditioner. Rank cutoff is the existing 1e-10 convention.
  Build Mc from the actual PCG lower factors. Global gauge columns must be
  represented to max per-column relative error <=1e-8. Normalize their
  whitened columns before SVD and require rank seven at relative cutoff1e-10;
  insufficient rank skips the event. Require finite matrices, SPD Mc and
  projected symmetry <=1e-7, gauge leakage and projected eigen residual<=1e-8.
* Choose the lowest strictly positive finite restricted eigenvalue, without
  repair or floor. Report negative/zero values; they are not physical-saddle
  claims. Require the independently scored ray's original GN curvature>0.
* Sign uses full original g^T d: flip if negative; at exact zero choose the
  largest-magnitude full-direction coordinate positive. One sign, one ray.
  Amplitude sets the original GN predicted increase to the registered budget.
  The finite upper cost bound permits an unexpected true decrease as well
  as an uphill move. There is no old-radius clip or point-gradient term.
* One event only. Rejected/invalid kick honors the pending stop immediately.
  An admitted kick continues at the same next-outer index with fresh assembly.
  The event has distinct counters; common attempt timing covers assembly,
  numerical continues and probe work, while PCG-iteration counters stay zero
  for this probe. Whole-solve wall includes state snapshot/restoration.
* Retain the pre-kick full state, including intrinsics; before final export and
  diagnostics return it if its true full cost is better. Retain the temporary
  uphill curve and log any final restoration explicitly, without continuing
  optimization after restoration.

Runtime OCA_SOFT_KICK is off by default. Derived source must reverse exactly
to the pinned champion. No other module or frozen source is edited. GPU
correctness checks use /tmp/prism_gpu.lock; the timed grid belongs to parent.
