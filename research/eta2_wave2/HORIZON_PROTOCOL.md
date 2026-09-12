# W6 conditional horizon pre-test

Registered before new candidate scores. Same plain objective, fixed camera
directions, no dropped observations. This tests step shaping, not a new score.

First replay Ladybug1197 capture0, point47270, the documented two-observation
point-Newton explosion. N3 repeated calculations, same original camera move.
Compare unchanged point-Newton, GN, Newton plus shadow-depth model, and exact
projective/distortion point-ray line search before its first positive depth pole.
Barrier weight mu=0.01*(2F/nobs) from the **full current problem**, a single
scene-independent rule; no dose tuning. Model barrier is -mu sum log(Yz/Yz0),
defined locally on each original signed-depth component, not log(Yz). Gradient
and PSD rank-one Hessian are included in the conditional point RHS and block,
including their camera-point mixed term. Pixel GN prediction and cost remain
the acceptance quantities. This conditional test is not a coupled-camera solve.

Ray search: exact projected pixels including distortion along the proposed
point direction, alpha in[0,min(1,0.99*first_positive_pole)], safeguarded bounded
scalar minimization with alpha0 and upper endpoint also evaluated. The camera
state is the prescribed proposed state. If the full step is outside the allowed
interval, there is no claim of dominance over a binary safeguard that permits
crossing the pole. All candidates still require global original-cost acceptance.

If the shadow barrier fails to prevent this documented explosion, stop that
fixed coefficient before a162-row chart screen. If it succeeds, repeat the
original conditional162 cells with the same rule and report all changes;
native extension requires improvement in two scene families, no >0.15%
primary-state loss, and positive pixel-model prediction/rho. No native claim
from a single repaired point. A poor fixed dose does not refute all barriers.

W6c: the W1 camera-outlier finding motivates a separate N3 fixed-state check,
all seven primary captures. At fixed OLD points compute each camera's maximum
alpha in[0,1] preserving its first-order signed depth ratio>=0.1. Re-complete
points afterward; explicitly count any actual joint depth-bound violations.
This is not a proof that the joint nonlinear candidate preserves depth.
Compare clipped baseline at the same state, never transfer the norm fraction
threshold directly into a claim of useful descent. No production camera bound
until this conditional mechanism passes the true-cost screen.
