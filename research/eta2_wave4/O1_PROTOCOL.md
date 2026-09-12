# O1 registration: constrained object-space opening

Registered before O1 native scores. Frozen Eta2 and the common wave-4 targets,
N=5 tails / N=3 practical cells, 600 outers and 60-second native budget apply.
Arms: off, k=3, k=5, k=10 complete opening sweeps, then unchanged Eta2.
All setup, transfers, SVDs, QP solves and rejected sweeps count in native time.
The whole sweep is accepted only if the original full L2 decreases; otherwise
restore its input and end the opening. No radius, LM damping or rho update in
the opening. The final Eta2 stage starts with its original controller defaults.

This is an opening heuristic, not a pixel-L2 majorization algorithm or a global
BA method. Read literature/MATH_AND_PRIOR_ART.md: cost equality is not gradient
consistency, and object-space Procrustes BA has close prior art.

## Fixed choices

At each sweep form observed rays by inverting the camera's radial polynomial;
select the real root closest to the current normalized image direction and
verify forward projection. Signed BAL depths are preserved. Scalar weights
are squared pixel residual / squared perpendicular object residual. At joint
zero residual use f^2/Z^2, explicitly an approximation rather than a theorem.
Reject a nonfinite or unverified ray instead of silently changing observations.

One weighted OI Procrustes rotation update per camera at fixed translation,
followed by the exact two-variable pixel-L2 least-squares update in (f, f*k1)
at fixed geometry. Degenerate intrinsics systems retain their input. Rays are
updated to the new intrinsics; the sweep's scalar weights remain frozen.
Rotation updates that violate sign(Z_old)*Z_new >= 0.5*abs(Z_old) are reverted
per camera before the translation/point QP, ensuring its zero step is feasible.
This feasibility guard is an explicit deviation from unconstrained pose OI.

Joint translation/point QP: fixed R, intrinsics and weights, minimize weighted
object-space squared error with all signed depth constraints above. Use 3x3
blocks and a matrix-free GPU Schur product. Fix the first translation increment
to zero; constrain the farthest camera's baseline-parallel increment to zero
to fix scale. These four equalities remove the fixed-rotation gauge and prevent
the all-zero scale-collapse solution. Depth floor is relative to the sweep's
original state, including the rotation update already taken.

Primal active set starts with the feasible zero step. Solve the equality QP,
move to its first blocking constraint, add it, and repeat. Feasible optima
require the correct multiplier signs; remove a wrong-sign active constraint.
Point-local constraint elimination is exact, with the resulting small PSD
Schur correction, not a finite penalty. At most three independent active
depth normals per point are supported; dependent constraints, more than 32
active observations, or 64 active-set iterations terminate the opening as an
incomplete numerical/working-set attempt. These limits are engineering guards,
not evidence that the exact QP itself is ineffective.

Projected camera PCG: relative residual 1e-8, at most 1024 iterations, FP64
blocks/products; positive-semidefinite point pseudoinverse with relative
eigenvalue cutoff 1e-14 and explicit KKT/residual checks. No persistent floor
or added LM damping. If feasibility, stationarity or point range checks fail,
do not accept the putative optimum; restore the sweep and enter Eta2. Budget
expiry likewise records an incomplete opening and cannot certify a staged hit.

## Correctness and decision gates

Before BAL scores, compare the GPU Schur/equality solve and active-set result
to independently assembled dense tiny QPs, including a binding depth bound,
negative signed depths, point-local multiple constraints, gauge and a rank
failure. Check actual full-L2 export and original/off N=3 compatibility.
Log per sweep original and surrogate cost, full-L2 acceptance, active count,
PCG products, KKT and feasibility residuals, rotation reverts, and all failure
reasons. A local surrogate improvement is not a basin claim.

Run k=3/5/10 on both tails. Only an observed Final3068 hit-count gain over its
fresh off control earns the practical panel. Report opposite-tail losses too.
Kill promotion for panel losses on at least five cells with disjoint ranges
without a tail gain. N=5 is screening, not an established reliability rate.
O6 opens only if a valid O1 translation/point step changes the basin, not merely
if an incomplete opening perturbs a trajectory or incurs extra runtime.
