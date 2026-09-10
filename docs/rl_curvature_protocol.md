# Curvature-informed damping: registered pilot, 2026-09-10

This is finite direct policy search on complete episodes, not SAC/PPO or a
trained neural network. No production defaults change. The frozen trajectory
study incumbent is the parent. Artifacts and exported states go under
`/tmp/prism-rl-curvature`; small durable results are copied into the repository.

## Information and causal timing

The current full-step model already computes slope `g^T d` and GN curvature
`d^T J^T J d`. Record their ratio `alpha_quad = -slope / curvature` for a
finite descent model with positive curvature. It is a directional quadratic
minimizer, not a certificate that an extrapolated nonlinear step will improve.
The prior step's ratio supplies a persistence check. Actual/model agreement
rho remains a separate signal about nonlinear model error.

Record existing PCG alpha, beta and pAp/pp host scalars. For one fixed SPD
operator/preconditioner, the associated Lanczos tridiagonal has diagonal
`1/alpha_i + beta_(i-1)/alpha_(i-1)` (first entry `1/alpha_0`), and off-diagonal
`sqrt(beta_(i-1))/alpha_(i-1)`. Its eigenvalues approximate the explored spectrum
of the preconditioned damped Schur system. They are not eigenvalues of the
undamped full Hessian, nor certified extremal bounds on unobserved directions.
Reset at every CG solve/retry. Mark depth < 4 and invalid recurrences unusable.
Do not subtract lambda to infer the undamped spectrum: eliminating damped
points makes the Schur operator depend nonlinearly on lambda.

These features require no additional GPU reduction, matrix product, or
observation pass. CPU summaries and policy overhead are included in target
timing. Features from a completed outer inform the NEXT damping decision;
the opening lambda remains unchanged. Failed outers permanently disable
interventions after rejection, repair, rho outside [.25,1.5], or progress <1e-7.

## Matched policy classes

Each action is -1, 0 or +1 decade relative to the incumbent's proposed lambda,
with at most two nonzero actions and an idle boundary between actions.
Lambda floors, true-objective acceptance, radius and rescue remain incumbent
rules. This bounds interventions; it does not guarantee baseline speed.

Four candidates per feature class: down-only or mixed up/down, crossed with
lenient `(rho=.75, alpha=1.5)` or strict `(rho=.95, alpha=3)` gates.

Without curvature: decrease when rho passes and CG fraction <=.25; increase
when CG fraction >=.99. With curvature: decrease when rho passes and
alpha_quad passes, with prior alpha_quad >1 if available; increase only at
CG cap with valid Ritz condition estimate >=100 and alpha_quad <= gate.
Mixed policies give increase priority. Both classes collect identical
curvature telemetry during training, so ablation compares access to features.
Baseline is also a selection option. The pre-specified deterministic rule is
the lenient mixed curvature controller, with no data-dependent tuning.

Training: ladybug-598, dubrovnik-356, venice-89; initial lambdas .1 and 10;
N=3, rotating order; 600 outers, 4 native seconds. Fixed targets, inherited
unchanged from the last study, are respectively `180411.357852*1.01`,
`724127.912566*1.01`, `303286.305616*1.01`. Nine arms give 162 episodes.
Select each feature class using mean log time relative to matched baseline;
misses get a 4*cap training penalty, never a reported target crossing. Also
report leave-one-family-out selection. Freeze policies before transfer. Carry
the best nonbaseline policy per class to transfer for diagnosis even if
baseline wins training selection; report that distinction explicitly.

Transfer: trafalgar-126 target 105579.58394455544 / cap 4s, final-1936 target
5125687.352261469 / cap 8s, muell-gba146 target 1946488.746262194 / cap 12s,
at lambda .1, plus muell at lambda 10. Largest test: final-13682 target
27591576.557625167 / cap 20s, lambda .1. N=3 for five arms: incumbent,
previous cap-2 feedback, selected non-curvature policy, selected curvature
policy, deterministic curvature rule. Identical selected policies may share
one measured arm with explicit aliasing; never count duplicates as samples.
All are full target-terminated solves. Transfer timing disables JSON logging;
separate labeled diagnostic runs may log decisions. Existing Caspar results
are historical context only; this pilot does not rerun Caspar.

## Validation and decision

Before training, verify PCG-to-Ritz reconstruction against an independent
small dense preconditioned eigensystem, masks/reset, action cooldown/budget
and failed-outer fallback. N=3 old-binary/new-off/collection-only compatibility
on ladybug-49, equal work counts and costs within 1e-7 GPU repeatability.
Check recorded slope/curvature reconstruct the incumbent prediction.
Every benchmark endpoint is audited on original observations in CPU FP64.
Report medians and min-max, hit counts, costs, outers, rejects and matvecs.
No promotion from training wins alone: require all transfer targets, positive
family-held-out evidence, at least 10% geometric mean transfer speedup and
no task >5% slower. Tiny differences are not substantive improvements.
Total native solver budget 660 seconds; stop failed exploration at the cap
and disclose missing tests rather than invent results.
