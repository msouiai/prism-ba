# D4 protocol: monotone soft acceptance at the strict-rho boundary

Registered before deriving the binary or scoring an active run.

## Hypothesis

D2 shows that Final3068 is contracting through its early smooth map and then
branches at a discrete accept/reject decision.  The frozen strict rule rejects
an otherwise cost-decreasing step whenever `rho <= 0.1`, creating a finite
jump in both the state and controller.  Lowering the threshold accepts the
entire poorly modelled step and was unresolved in wave 4.  D4 instead makes
the committed state continuous at the boundary.

For a full proposal with positive true decrease and
`0 < rho <= rho_min = 0.1`, D4 replaces the step `d` by

`d_soft = alpha d`, where `alpha = rho / rho_min`.

It recomputes the full plain-L2 cost and the full quadratic prediction on
`d_soft`.  The scaled step is accepted exactly when its true cost decreases
and its prediction is positive.  The recomputed rho drives the unchanged
radius and lambda update.  Proposals above `rho_min`, proposals with
nonpositive rho, the point safeguard, clipping, PCG, damping, stopping and the
scored objective are untouched.  Thus the accepted state tends continuously
to the rejected state as `rho` tends to zero and to the original full step as
`rho` tends to `rho_min` from below.  Cost remains monotone.

The one registered active parameter is `rho_min=0.1`; there is no sweep and no
minimum alpha.  The derived-off path must match the deterministic control
exactly.  The implementation logs every activation, alpha, original and
scaled rho, original and scaled cost, and whether the scaled step commits.

## Gates

1. **Arithmetic/semantic audit.**  Unit tests check the scaling law and its
   endpoint continuity.  An active Final3068 run must fire at least once,
   every commit must lower the true cost, and the logged recomputed rho must
   equal `(old_cost-scaled_cost)/scaled_prediction` to floating-point
   tolerance.
2. **Paired Final3068 reliability.**  Use unseen PCG64 perturbation seeds
   `650000--650059` at field scale `epsilon=1e-10`.  The deterministic control
   and active arm consume byte-identical BAL files; arm order alternates.
   Target is `1744796.9841897595`, with 45 native seconds and 600 outers.
   Independently rescore every endpoint in FP64.
3. **Sequential rule.**  On discordant target outcomes test
   `q0=0.50` against `q1=0.70`, with `alpha=0.05`, `beta=0.10`, and at most 60
   total pairs.  The lower boundary rejects the registered 70% conditional
   benefit; it is not a claim of harm.

A production candidate requires the upper sequential boundary, at least one
actual soft commit, and a median active/control target-time ratio no larger
than 1.20 on double hits.  Only if all three pass do we run Venice52 at N=10
and the nine practical cells at N=3.  Failure stops D4 without tuning the
scaling law or adding a filter objective.

This is a deterministic robustness experiment on a controlled perturbation
shell.  It does not estimate ordinary deployment randomness.
