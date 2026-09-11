# U1: joint virtual-ray retraction

Registered before comparisons. Follow Astra's finite joint-path construction.
The ordinary6DOF/fixed-intrinsics LM solve is unchanged. For each parent q=RX+t,
u=-q_xy/q_z, compute dq=omega cross RX+dt+R dX and du=P dq. Keep ordinary finite
trial cameras. Virtual normalized pixels are u*=u+alpha du, NOT observations.
Rows B=[I2,u*], A=(f/q_z_parent) B R_trial, and b=-(f/q_z_parent) B t_trial define
per-point finite ray intersections. Around Xlin=X+alpha dX solve
(sum A'A+lambda diag(Dp)) correction=sum A'(b-A Xlin). Dp is original GN scaling.
Keep point0 entirely XYZ; return XYZ per point on nonfinite/Cholesky failure.
No change of original objective, observations, gradient, camera step or gauge.

Controls: ordinary XYZ; old fixed-world-host radial inverse-depth path; moving
host radial inverse-depth path (actual trial host camera); virtual-ray with
mu=lambda; existing one-step observed-pixel polishing. Hosts are first observing
cameras. Moving-host q*=q+alpha dq/(1-alpha(q'dq)/(q'q)), transformed back through
actual trial host camera; denominator<0.25/nonfinite falls back per point.
The observation-polish control uses prior point_relaxation.polish(steps=1),
including its3 local trial scales and full checks. It is not tangent matched;
compute original GN prediction at its actual point displacement. Other paths
use the solved physical tangent prediction. All retain the original rho/lambda
controller. Every path's additional work is inside solve timing.

Algebra tests: alpha0, first-order tangent with moving cameras, unchanged gauge
and parent, moving-host equals old anchored when host motion is zero, and
virtual targets independent of measured pixels for a frozen geometry/tangent.
mu0 is diagnostic only, never a timed tuning arm; whiten its3x3 matrix by Dp and
fallback at min/max eigenvalue<=1e-10. Test finite alpha1 point and joint model
defects at frozen original/accepted2/4 parents without selecting a new policy.

Screen primary targets on all12synthetic cases from TEST_CONTRACT, five arms,
N=3 rotated order, max160 attempts/3seconds per run. The small total workload
makes N=3 cheap enough to run directly after algebra checks. Promotion requires
virtual-ray>=1.10x paired median speed vsXYZ and both anchored controls on at
least2of3families, no extra target misses, and no severe geometry deterioration
(point/camera NRMSE grows by>20% AND crosses0.2; median rotation grows by>20%
AND crosses5deg, relative to ordinary at the same target). Report comparisons
against observed polishing as prior-art attribution. A moving-host win matched
by virtual rays supports comotion, not novel multi-view integration.

If any candidate passes this fixed gate, register seeds510..515 plus the three
unchanged BAL development probes and deep targets before running them. Otherwise
stop timed expansion. Rough budget<15CPU minutes; no GPU port on this screen.
