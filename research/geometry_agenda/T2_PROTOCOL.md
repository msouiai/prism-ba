# T2 registration before comparative timings

CPU FP64 six-DOF reference, fixed intrinsics, same seven fixed gauge coordinates
and valid negative-depth domain as T1. Development seeds 0–9 and held-out seeds
100–109, both depth and rotation families. No tuning on held-out outputs.
Three timing repetitions, cyclically rotated arm order, single-thread BLAS.
Each arm has 80 attempts / 2 seconds maximum. Stop at the fixed target
`F(truth) + 1e-4*(F(initial)-F(truth))`; the generating state is a feasible
reference, not a global optimum. Include all solve/derivative/candidate work.

Arms: ordinary LM (fresh linearization after each accepted step); LM with
geodesic acceleration; one extra OCA recursion; a second lambda at lambda/3;
and a deterministic hybrid. All start lambda=0.1 and first evaluate the same
ordinary step. Hybrid uses the already evaluated full-step nonlinear defect:
if `||r_trial-r-Jv||/(||Jv||+epsilon)>0.25` or invalid, try geodesic acceleration;
otherwise try OCA recursion. This is an explicit, charged trial feature.

Geodesic correction uses the analytic second derivative and the exact same
point/Schur factors, `A*a=-J' r_vv`. Test curve t=1,0.5 only when
`t*||a||_M/(||v||_M+epsilon)<=0.75`; M fixes rotation units and uses the initial
scene radius for translation/point units throughout the run. OCA solves
`A*u=-g+D*v` with the same factors and changes spectral bias. A new lambda
always builds new factors. Every candidate starts from the immutable parent.

Accept finite valid states with positive GN prediction and rho>0.1, choosing
the lowest full original cost. If none passes, lambda *=4 and retain the
linearization; after acceptance halve lambda for rho>0.75, double for rho<0.25.
Floor 1e-8, ceiling 1e8. No post-hoc alternative acceptance definitions.
Log rejected and safeguard-skipped candidates, all counts and time breakdowns.
Single global similarity alignment measures point and camera error; no
per-cluster alignment. Report target misses and failures, not just common hits.

Promotion requires 1.10x median time-to-target against ordinary LM **and** the
same geodesic baseline, no extra misses/geometric failures (normalized point
RMSE>0.15), and consistency across both families. CPU results only gate a
matched GPU experiment. Merely adding geodesic acceleration is established
prior art and is not a novel contribution.
