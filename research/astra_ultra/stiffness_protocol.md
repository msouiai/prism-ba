# U2: residual-induced positive perspective stiffness

Registered before directional measurements. Follow the mechanics analogy only
if frozen-system measurements support it. Use all12synthetic screen inputs and
ordinary parents k=0,2,4, preserving actual lambda. They are pinhole, so the
following residual-Hessian decomposition is exact in the current retraction.

With a=Jq'r, e=[0,0,1], Kq=-(a e'+e a')/z, dq=G d, and
G=[-skew(RX), I, R], perspective residual curvature is sum dq'Kq dq.
Pose curvature is sum a'[omega cross(omega cross RX)+2omega cross Rdp].
Their sum equals r'r'' from the existing analytic full second derivative.
Validate this identity, the rank1 positive-eigenvalue factor and finite
differences. The original GN curvature is ||Jd||².

Fixed mechanism gate from adviser: severe positive-excess parents have
k_total/k_GN>=1. Require >=4 such parents across>=2synthetic families, and
median k_perspective/k_total>=0.5 there. Retain signed values/cancellation;
ratios>1 are not clipped. No selecting new noise levels or parents after seeing
the result. If gate fails, stop full trajectory screening; still evaluate one
augmented step at the registered parents to verify construction.

Implementation: b=-a/z, positive eigenvalue kappa=b_z+||b|| and eigenvector
v proportional to b+||b||e. Assemble one zero-residual pseudo-row
sqrt(kappa) v'G per observation. Add its normal blocks to the existing GN
matrix, keeping the original gradient and GN-derived damping D unchanged.
Gauge rows/columns are zeroed exactly as in ordinary LM. This is a positive
step penalty informed by curvature, not the exact Newton Hessian. Primary rho
uses original GN prediction; augmented prediction is diagnostic only.

If mechanism gate passes, compare ordinary LM, this penalty, a scalar
fractional-depth penalty matched in trace under D-whitening, and one extra
lambda×4 candidate, all with original objective/controller, N=3. At the first
stage only the actual stiffness and trace-control one-step diagnostics run.
No radial/intrinsic-curvature claims or native port follow from pinhole algebra.
Budget<10CPU minutes; no full-screen continuation after a failed mechanism gate.
