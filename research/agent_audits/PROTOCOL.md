# Agent-audit implementation protocol

Registered 2026-09-14 before building or running the candidate binaries.

## Scope and immutable control

The frozen source in `research/eta2_champion/` and the Wave-5 B6v7 candidate
remain unchanged.  All changes are generated derivatives and are disabled by
default.  The control is the existing B6v7 source/configuration.  The code-only
arm enables `OCA_W6_DETERMINISTIC=1`; the math-only arm enables
`OCA_AUDIT_LINEAR_EDGES=1`; the combined arm enables both.

## Code hypothesis: complete fixed-order reductions

Port the complete Wave-6 D0v3 reduction path as a selectable derivative.  The
hypothesis is scientific rather than a speed claim: N=5 identical executions
will have one accepted-cost hash, normalized decision hash, endpoint SHA256,
and work-count tuple.  Flag-off must follow the B6v7 path.  Cost, assembly,
Schur products, full-model sums, reduced RHS, accepted point steps, and
source-level dot/norm reductions must all use fixed owners/trees when enabled.

The lightweight gate is Ladybug49, N=5, at a fixed iteration cap.  Dubrovnik356
is the next gate if Ladybug passes and runtime permits.  Kill the candidate if
any numerical repeatability field differs, an independently rescored endpoint
fails the existing FP64 tolerance, or median wall regresses by more than 1%
after timing spread.  Existing Wave-6 D0v3 evidence may be cited as prior
validation, but new rows must be identified separately.

## Math hypothesis: robust forcing and exact-zero reduced solves

Under `OCA_AUDIT_LINEAR_EDGES=1`, compute the Eisenstat-Walker norm ratio as
`nb/prev_bnorm` before squaring when direct squaring would overflow/underflow,
reject nonfinite norms explicitly, and classify an exactly zero reduced RHS as
a zero-depth converged camera solve.  The normal point back-substitution and
candidate scoring remain active, because zero reduced camera RHS does not imply
zero point gradient or full-state stationarity.

CPU tests must cover ordinary-scale bit parity, overflow (`1e200/2e200`),
underflow (`1e-200/2e-200`), exact zero RHS, a nonzero control, and NaN/Inf.
The algebraic zero-RHS fixture is `U=2,V=1,W=1,lambda=1,Dc=Dp=1,gc=1,gp=2`:
the reduced camera RHS is zero while the exact joint damped step is
`dc=0, dp=-1`.  Kill the change if ordinary-scale forcing differs from the old
formula, nonfinite values are treated as convergence, or zero RHS is logged as
negative curvature or a positive CG depth.

## Integration gate

The combined build must pass all CPU tests and compile.  With both flags absent,
its generated source must be semantically identical to the control paths: new
branches may be present but cannot activate.  No source/configuration is
promoted, pushed, or merged by this experiment.
