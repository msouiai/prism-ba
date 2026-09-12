# O4 fixed-camera ray constraint pre-test

Registered before calculating the new ray-constrained proposals. Inputs are
the archived hit/miss E4 accept-6 pre-states and their actual recorded joint
steps. The sensitivity trigger passed the healthy locality screen. The audit
targets point 250233; this is a mechanism pre-test, not a run-everywhere rule
selected using that point ID.

Hold the original proposed camera step fixed. Build the old anchor camera's
observed undistorted ray, using the inverse radial solution continuously
connected to the current predicted bearing. Retain its signed-depth branch.
First solve the exact scalar damped GN restriction at the old state, including
the affine displacement needed to put the point on that frozen ray and the
camera contribution to every observation. Use the recorded point damping and
diagonal floor. Evaluate the resulting point with the *updated* cameras and
the complete original pixel cost and model prediction. This is a restricted
back-substitution diagnostic; it does not recompute the camera Schur solution.

Separately audit how much any scalar solution on the same frozen ray could
improve the track: bounded log-depth search from 1e-4 to 1e4 times old depth,
with all local brackets in 129 fixed grid samples refined by bounded Brent.
Split intervals at every updated-camera pole. This search is a diagnostic
upper envelope of the scalar GN restriction, not the production method or a
certified global rational optimizer. Report constraint residuals at old and
updated cameras separately; do not assume the updated residual is zero.

Gate: the scalar GN restriction must remove at least 90% of this point's
hit/miss cost gap, keep both complete proposals acceptable, and retain the old
depth sign in both observing cameras. If it does not, do not build the native
frozen-anchor approximation. If it does, a separate registered native chart
implementation must recompute the joint camera/point solve before tail claims.
Fixed-step replay by itself cannot establish that the subsequent controller
branch or basin is repaired.
