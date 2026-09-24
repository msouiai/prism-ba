# Prism novelty evaluation: frozen protocol (2026-09-07)

Scope authorized: Caspar-fp32; 2x2 shifts/backtracking ablation; shared versus
independent solves; joint-damping LM and Dogleg; mathematical and prior-art
analysis; held-out scenes, initialization perturbations, full largest-scene
budget, and second GPU if available. No changes to earlier measurement records.

Primary development scenes: venice-52, ladybug-1197, final-3068, final-4585.
Ablation: Config A + retry cache + multi-RHS + diagonal norm, with
A=1 shift/backtracking off, B=1/on (8), C=5/off, D=5/on (8).
One frozen binary, 600 outer cap on ALL four scenes, N=3 fresh repetitions,
cyclic run order by replicate, serialized GPU. A single shift is centered at
lambda because grid_down clamps to L-1=0. Report interaction and failures,
not just a winning arm. No default change based on these development data.

Evaluation scenes held out from this controller's local development:
ladybug-598, trafalgar-126, dubrovnik-173, venice-1672. They may have appeared
in historical repo studies; do not call them globally unseen. Same fixed arms,
N=3 each, 600 cap. Initialization stress: development Venice-52 and final-3068,
three predetermined seeds (17,29,43), rotation perturbation std 0.001 rad and
translation/point perturbation std 0.001 times robust point-cloud radius;
observations/intrinsics unchanged. These seeds are distinct initializations,
not timing repetitions; three fresh repetitions per seed/config.

Caspar: pinned COLMAP ed8080bcf42ef0e42d3f5d0cd21eeff0698dfde8 generated/f32.
Keep f64 controls separate. Primary budgets 200 and 2000, N=3, defaults.
FP32 initial quantization error is measured, not hidden by forcing a f64
initial-cost identity check. Final states evaluated in CPU fp64 against
original double observations; native float score never ranks solutions.
Only independently checked endpoints certify fp32 cost attainment. If adding
budget curves, use fixed budgets 8,32,128,512 (N=3), do not infer exact shared
trajectory crossings from separate capped runs. Native float traces are diagnostic.

Baselines: Ceres joint-damping LM and Dogleg, identical BAL SIMPLE_RADIAL
objective and all observations. Default plus a small declared development grid
for initial damping/linear tolerance where supported; freeze a single profile
per solver before evaluation scenes. Report CPU versus GPU hardware honestly.
Dogleg exact-factorization limitation is disclosed; do not silently substitute
an inexact algorithm and call it Ceres Dogleg.

Shared-solve audit: identical captured Schur operator/RHS/shifts, verify true
relative linear residual and candidate discrepancies. Compare multi-shift CG
against independent CG for the same target residuals, report achieved accuracy,
matvecs and synchronized GPU wall. This microbenchmark isolates amortization;
nonlinear ablation isolates candidate selection. Neither is a novelty proof.

Report all repeats, endpoint cost, solver/setup wall, residual evaluations,
rebuild retries, matvecs, stopping reasons and memory where measurable.
Primary quality targets: best attained fp64-verified endpoint over fixed arms
per instance times (1+epsilon), epsilon in {0.01,0.001,0.0001}; these are empirical
references, not optima. Also retain prior median-endpoint crossings. Timeouts,
resource failures and invalid objectives remain in records. N=3 ranges are
not tail claims. Freeze executable/data hashes and sanitize OCA environment.

One RTX 2000 Ada currently available. Second-GPU replication needs an existing
accessible machine from the user; no paid provisioning is authorized/inferred.

Baseline development grid clarification (before evaluation selection): Ceres
LM and traditional Dogleg each use initial trust-region radii {10000,1}, all
other installed Ceres 2.2 solver defaults except 8 CPU threads, the explicit
linear solver choice (ITERATIVE_SCHUR/SCHUR_JACOBI for LM, SuiteSparse
SPARSE_SCHUR for Dogleg) and 600 cap. Select each method's profile on Venice-52
and Ladybug-1197 only: minimize failures first, then geometric-mean endpoint
cost; if relative geometric-mean cost difference <=0.15%, choose lower
geometric-mean wall. Caspar fp32 default and historical paper profiles are
both retained on development scenes; freeze one profile by the same rule on
Venice/Ladybug at budget 2000, then use it on evaluation scenes. Original
Caspar default results remain separately reported, regardless of tuning.
This small grid is not claimed exhaustive or optimal tuning.
