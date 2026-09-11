# T6 registration: bounded depth tubes

Two parallax settings: existing six-camera/80-point depth-initialization
generator, and camera-center baselines shortened to 0.1x. Regenerate truth
projections while preserving each observation's sampled noise; initial pose
errors remain unchanged. All starts must have valid projections; retain any
invalid case as an explicit failure instead of resampling. Development0–9,
held-out100–109, N=3 rotated order.

Depth direction is the lowest-eigenvalue eigenvector of each undamped point
GN block in common world-coordinate units at initialization. Freeze it and
the radius throughout each run. Test radius fractions 0.02 and 0.10 of each
point's minimum initial observed absolute depth. Use three bounded samples
alpha=-1,0,1 and weights1/4,1/2,1/4. Isotropic control uses center and +/-three
axes, weights1/2 and1/12, so its covariance trace equals the depth tube's.
Seven versus three evaluations are fully charged. No sample may cross the
camera plane: reject the whole trial, never delete or renormalize samples.

Arms: ordinary LM, depth.02, depth.10, isotropic.02, isotropic.10, and two
ordinary starts (original plus a fixed seed-dependent bounded log-depth
perturbation of +/-0.2; keep the original gauge and retain an invalid start as
a failed branch). Total cap1 second; multistart gets half per branch. Each
single run has12 opening attempts (6 at full radius,6 at half), then36 attempts
at radius0 on the identical original objective; ordinary gets48 ordinary
attempts. Reset lambda to0.1 at terminal refinement for all. All stage directions
and quadrature weights are constants when differentiating.

Freeze target=Ftruth+1e-4*(F0-Ftruth) per scene. Report original-objective curves,
time-to-target after entering radius0, final original cost, global geometry,
invalid sample rejection, overhead and sensitivity to radius/parallax. All arms
receive the same terminal refinement count/cap rule. A gain must survive this
refinement and beat equivalent multiple starts to justify further adaptation.
No adaptive smoothing schedule unless the simple registered one earns a win.
