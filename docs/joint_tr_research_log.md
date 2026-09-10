# Continuing TR research: joint geometry, solve depth and recurrence scoring

Live research record. The user requested continued autonomous work until there is a clear improving TR candidate. No method below is promoted merely for a local gain. The prior [four radius rollouts](adaptive_radius_results.md) remain intact.

## Joint camera/point TR candidate

Source/binary/artifacts: `/workspace/prism-joint-tr/`. Build: `bench/build_joint_tr.py`; model hook: `gpu/joint_subspace_tr.inc`.

Use the existing CG step to span two directions, `(dc,0)` and `(0,dp)`. A single full-observation GPU pass computes `gc,gp,cc,cp,pp`, the gradient and complete 2x2 unregularized GN model. The radius uses the restricted block-diagonal GN metric `cc*a²+pp*b² <= R²`, constraining both blocks. Whitening gives a 2x2 symmetric TR problem with unit diagonal and the normalized cross term. Solve it with the projected secular solver, allowing negative coefficients if the constrained quadratic chooses them. Maintain a joint radius between nonlinear iterations and test the current radius, followed selectively by an expanded or contracted radius. Retain the original candidate only if it is feasible, acceptable and better.

This is an exact TR subproblem in a two-dimensional subspace, not a full-space exact solution or a new convergence theorem. The original camera TR machinery generates seeds; joint feasibility controls acceptance when the joint model is available. Degenerate/no-candidate states retain the existing fallback. The independent full GN pass checks the selected step before commitment. Radius metrics may change with the nonlinear state.

3000 CPU projection/metric/KKT checks pass, including singular cancellation directions; maximum predicted-reduction discrepancy is 4.74e-15. The GPU subspace model passes 12 mixed-block/mask finite-difference tests with maximum error 4.80e-10. Logged selected-step predictions agree with independent full-GN evaluations within 1.85e-13 relative error.

Each study below uses fresh paired controls, frozen Trafalgar126 and Dubrovnik88 targets, N3, a four-second target budget, and no profiler or detailed candidate logging in timed runs. Different studies have different realized baseline trajectories/timings; assess comparisons within each study. All runs and failed approaches are retained.

| Study | Arm | Trafalgar median seconds | Dubrovnik median seconds |
|---|---|---:|---:|
| Joint geometry | TR-one, depth128 | 0.506 | 0.738 |
| Joint geometry | Joint TR, depth128 | 0.631 | 0.985 |
| Depth ablation | TR-one, depth128 | 0.449 | 0.861 |
| Depth ablation | TR-one, depth64 | 0.522 | 0.716 |
| Depth ablation | Joint TR, depth64 | 0.623 | 0.707 |
| Width/depth tradeoff | TR-one, depth128 | 0.505 | 0.732 |
| Width/depth tradeoff | TR-five, depth64 | 0.593 | 0.715 |
| Width/depth tradeoff | TR-five, depth32 | 1.427 | 0.776 |

Every timed target is reached. Joint geometry alone loses both scenes. Depth64 helps Dubrovnik but loses Trafalgar, with or without joint geometry. TR-five/depth64 splits the scenes, and depth32 loses both. A small subspace or a lower linear cap is not automatically sufficient: changed nonlinear trajectories can require more total matvecs.

The joint study has two extra seven-iteration diagnostic runs plus 12 timings (9.352 native seconds). Depth64 has 18 timings (11.672 native seconds). Width/depth has 18 timings (14.032 native seconds). Full raw manifests, costs, counts, timing ranges, and independent endpoint audits are in their respective folders. `bench/verify_joint_tr.py` performs the additional source/hash, CSV and joint-acceptance checks.

## Current next experiment: remove redundant operator evaluations

TR ranking currently computes `xᵀSx` using another Schur matvec for every saved CG candidate. The shifted residual identity gives

```
(S + sigma I)x = b - r_sigma
xᵀSx = bᵀx - sigma*||x||² - xᵀr_sigma
r_sigma = zeta_sigma * r_seed.
```

The candidate bank can obtain the quadratic coefficients using vector reductions and the stored recurrence residual. This identity is exact in exact arithmetic; finite-precision residual drift must be measured. Actual nonlinear cost and full GN acceptance remain independently evaluated. Cauchy construction keeps its explicit operator call.

`bench/build_tr_recurrence.py`, `gpu/tr_recurrence_score.inc` and `bench/tr_recurrence_study.py` implement an isolated experiment in `/workspace/prism-tr-recurrence/`. Four 16-iteration audits cover both scenes and widths1/5, compare every recurrence curvature against an explicit Schur application, and fail above 1e-7 relative discrepancy before proceeding to timings. Timing runs omit this audit overhead. The audits and fresh three-scene N5 confirmation passed. See [confirmed candidate and reproduction](tr_candidate_results.md): 14/15 paired wins, all three medians improve. This scoring optimization, rather than the slower joint variants, is the selected candidate.
