# D0v3 complete champion-path reduction validation

Registered before D0v3 native execution.  All arms, scenes, targets,
repetitions and decision gates in `D0_PROTOCOL.md` remain fixed.

D0v2 fixed assembly, Schur products, objective/model reductions and all
source-level cuBLAS dot/norm reductions, but its path audit exposed two
remaining atomic sums used by the frozen champion:

1. `MFRhsDiagFused` formed the reduced RHS and Schur diagonal for scenes below
   the registered 128-camera preparation threshold;
2. `MFPass1` formed the point back-substitution input while scoring and
   committing the accepted single-shift proposal.

D0v3 routes the first through the existing camera-owned fixed reduction and
the second through the point-owned fixed reduction.  Disabled behavior still
delegates to the B6v7 path.  No nonlinear algorithm, preconditioner, stopping
rule, target, cap or statistical gate changes.  Earlier rows remain
localisation evidence and are not pooled with v3.
