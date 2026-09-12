# D2 finite-time Lyapunov diagnostic

Registered before instrument validation or FTLE execution.

## Fixed binary and trajectories

The binary is the deterministic B6v7-derived measurement build recorded in
`d2-registration.json`.  The compact-dump option only serialises `R`, `t`,
`X`, and the three per-camera intrinsics before accepted outers 0--9; the
ordinary endpoint state supplies outer 10.  Before scoring D2, dump-off and
two dump-on executions must have identical endpoint-state, accepted-cost and
normalized decision hashes on both Venice-52 and Final3068 at `max_iter=10`.

The solver uses the frozen Eta2 champion flags, the four wave-5 optimized
overlays, `OCA_W6_DETERMINISTIC=1`, `lam0=0.1`, plain L2, unshared
SIMPLE_RADIAL intrinsics, and `k2=0`.  No target or wall stop is active.

## Perturbations

For each scene the unperturbed trajectory is run once.  Eight directions use
PCG64 seeds `620000` through `620007` at `epsilon=1e-12`.  The first four
directions are repeated at `epsilon=1e-10`, so the direction is identical and
only its magnitude changes.  `bal_perturb.py` supplies the preregistered field
normalisation in `D1_PROTOCOL.md`; observations remain byte-identical.

At each outer k, independently evaluate all FP64 reprojection residuals from
the compact states and report

`A_k = ||r(x'_k)-r(x_k)||_2 / ||r(x'_0)-r(x_0)||_2`.

The terminal exponent is `gamma10=log(A_10)/10`.  The pre-saturation exponent
used for the cross-dose check is fixed as `gamma5=log(A_5)/5` (no post-hoc
choice of an apparently linear interval).  Per attempt, compare the sequence
of `(accepted-outer, accept/reject)` decisions and record its first mismatch.

## Decision

Classify a scene/dose cohort by its medians:

- positive/sensitive if `median(A10)>1e3` and `median(gamma10)>0.5`;
- stable/switch-like if `median(A10)<10` and `median(gamma10)<0.1`;
- unresolved otherwise.

The two doses agree only if their classifications have the same direction
and their median `gamma5` values have the same sign and differ by at most 25%
relative to the larger absolute value.  Otherwise the verdict is numerical
scale ambiguity.  Positive FTLE sends later work to map changes or portfolios;
stable FTLE plus a discrete decision split sends it to soft/filter acceptance.
