# D18 protocol: sparse geometric-starvation prior

Registered 2026-09-13 before capturing or scoring a D18 system.  This combines
the categorical map's information-geometric starvation score with an
empirical-Bayes local Gaussian prior.  It targets the geometric Venice failure
that the count gate in D15 cannot see.

## Hypothesis

At the five archived Venice52 terminal states, camera 34 carries about
99.99956% of squared raw camera-step norm despite having 2,959 observations.
The exact posterior and the inverse smallest eigenvalue of its local scaled
Schur block both rank it first.  Wave 3's spectral floor failed because a fixed
threshold touched 47% of cameras.  D18 instead uses a top-one, step-attributed
gate and applies a prior to exactly one camera.  If global clipping is failing
only because that one geometrically unobservable camera consumes the radius,
the prior should retain the healthy-camera direction and make the proposed
step useful.

## Immutable gate

At an attempt, compute the ordinary Eta2 raw camera direction and the active
8x8 scaled Schur diagonal blocks.  Select a camera only if all conditions hold:

1. `||z_raw||/R > 100`;
2. one camera carries more than 99% of squared raw camera-step norm;
3. that same camera has the smallest local-block eigenvalue in the scene.

Ties use lowest camera id.  At most one camera is selected.  The gate is
state-based, has no controller memory, and is distinct from the count rule.

For the selected camera, add

`Delta = Q diag(max(0, dose*mu_ref - mu_k)) Q^T`,

where `mu_k,Q` are its active scaled Schur eigensystem and `mu_ref` is the
median largest active eigenvalue of all other cameras.  Add Delta consistently
to the operator and camera preconditioner, then resolve at unchanged lambda,
tau, radius and Eta2 forcing tolerance.  Point completion, clipping, full-model
prediction, safeguards and true-cost acceptance remain unchanged.

## Fixed-state dose screen

Use all five checksum-pinned Venice terminal states from D6 and the exact
captured FP32-fragment/FP64-accumulation Eta2 system at each state.  Reproduce
the archived raw direction and full-objective score before interpreting an
arm.  Test the finite, preregistered doses `0.1, 1, 10, 100`; `0` is control and
hard projection is a descriptive limiting control.  Three deterministic
linear repetitions must agree.

Select the smallest finite dose satisfying every condition:

- gate selects camera 34 in all five states and no other camera;
- raw/radius ratio is at most 10 in at least four of five states;
- ungated raw-direction norm is at least 95% of control in every state;
- true decrease improves by more than 0.15% in at least four of five states;
- rho does not decrease in any state.

If no dose passes, stop and retain Eta2.  Do not change the gate, quantile,
reference scale or dose family.

## Native gate if earned

Only after a fixed dose passes, derive a same-binary-off native arm and require
exact disabled compatibility.  Run Venice52 N=5 at target 243740.27, then
Final3068 N=5 and the nine practical cells N=3.  Promotion requires Venice at
least 3/5, no Final hit-rate loss, no practical endpoint loss above 0.15%, and
no disjoint time loss on five or more practical cells.  Every run reports
activations, cameras touched, raw/radius before and after, products and wall.

The full scored objective remains plain L2 SIMPLE_RADIAL with unshared
intrinsics and `k2=0`.  The frozen Eta2 champion remains the winner until all
native gates pass.
