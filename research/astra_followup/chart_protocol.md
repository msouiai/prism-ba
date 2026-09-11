# Track A2: matched-tangent projective point paths

Registered before solver outcomes, 2026-09-11. This is a CPU mechanism test,
not a change to Eta2 or a GPU/Caspar speed comparison.

Use ordinary LM's original Euclidean tangent, damping, prediction, camera
retraction and rho/lambda rule. Replace only the finite point retraction by
X + alpha*dX/(1-alpha*h). Anchored control: h=(X-C_anchor)'dX/||X-C_anchor||^2,
where the first observing camera's parent center is frozen during the trial.
Mean-view candidate: h=mean_i(R_i[2,:]/z_i)'dX. Neither changes the objective,
point degrees of freedom, observations or physical damping. Point0 remains
Euclidean to preserve its fixed z gauge. At denominator <0.25 or nonfinite,
fall back per point to XYZ, reporting counts. Full depth and objective tests
remain mandatory. There is one full-scale candidate, matching ordinary LM;
this is not an additional trial menu. Chart vectors refresh on accepted state
changes only and remain fixed during retries.

First verify first-order equality, explicit anchored chart equivalence, exact
fixed-camera pinhole denominator identity, gauge and parent immutability.
The identity does not assert cancellation of moving-camera or radial-distortion
curvature. Linearized chart endpoints must equal XYZ to roundoff; they are an
algebra control, not a redundant timed arm.

Frozen comparison: XYZ, anchored, mean-view. Ten new seeds 200..209 in each
of low-parallax depth error (baseline multiplier 0.08), moderate-parallax depth
error (multiplier1), and rotation-dominated initialization. Use the existing
six-camera/80-point generator with its unchanged observation noise. The first
two families use parallax_case; the third synthetic(mode='rotation').
Target Ftruth+1e-4*(F0-Ftruth), frozen before any comparison. Truth is a feasible
reference, not an optimum. N=3 rotated arm order; cap80 attempts/2 seconds.
Charge all chart construction, reductions, fallbacks and objective evaluations.
Report acceptance/rejection, target misses, final cost and one globally aligned
point/camera error. No per-region alignment or truth feature in the solver.

Promotion gate: >=1.10x median paired time to target in the low-parallax cohort,
no extra misses or geometry failures. A geometry failure is point NRMSE>0.2,
camera NRMSE>0.2 or median rotation error>5deg, frozen here before evaluation;
also report continuous errors so this threshold cannot hide deterioration.
Compare mean-view directly against anchored control: a tie supports known
inverse-depth geometry, not a novel selection advantage. If the synthetic gate
passes, run the unchanged three packed real development probes at their prior
tau1e-3 targets, N=3. Otherwise stop this implementation at the mechanism test.

Budget <=15 CPU minutes, one BLAS/OpenMP thread, serial timings. Preserve all
results including regressions; no new data or native port for a failed screen.
