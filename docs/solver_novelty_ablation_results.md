# Solver novelty ablation — 2026-09-09

The strongest evidence from this panel concerns the whole-track point safeguard, not the projected Krylov trust-region solve. Disabling the safeguard on Final-4585 changes a 2.32-second target hit with zero rejections into a 20-second miss with 138 rejections. Disabling the projected solver preserves the large-scene results and improves the smaller scenes. This identifies a useful component; it does not establish algorithmic novelty.

## Matched implementation and results

All four arms use the same compiled binary, optimized assembly and Schur kernels, camera-Hcc block PCG, FP64 arithmetic/state/acceptance, and FP32 stored fragments. Times below are solver-native seconds to the same independently audited objective threshold. They exclude input loading. Small/medium rows are medians of three rotated runs per arm; the two large rows are single runs. A miss means no qualifying target hit within the 20-second budget, not an infinite runtime.

| Scene | Full TR | Classical LM, initial lambda 10 | TR without point safeguard | TR without projected solve |
|---|---:|---:|---:|---:|
| Trafalgar-126 | 0.283 | 0.216 | 0.264 | **0.196** |
| Dubrovnik-88 | 0.204 | **0.169** | 0.203 | 0.186 |
| Final-1936 | 1.557 | **1.299** | 1.566 | 1.557 |
| Final-13682 | 6.900 | 9.663 | **6.727** | 6.906 |
| Final-4585 | **2.319** | miss | miss | 2.322 |

Bold marks the measured minimum in this table, not statistical significance or a universal winner. In particular, 2.319 versus 2.322 seconds is a practical tie. Full TR reaches all five targets; classical LM is faster on the three smaller scenes. Full TR is about 29% faster than this LM configuration on Final-13682. The smaller initial-damping sensitivity below must also be considered before interpreting that comparison.

Full TR on Final-4585 takes 8 accepted steps, zero rejected steps and 49 operator products, ending at cost 7,445,683.81. Without its point safeguard it takes 39 accepted and 138 rejected steps, ending at 7,939,829.70 after 20.192 seconds; the nominal target is 7,488,277.53. LM with initial lambda 10 takes 93 accepted and 19 rejected steps and ends at 18,194,238.54 after 20.136 seconds. Native budgets are checked between operations and can overshoot slightly; these remain misses.

On Final-13682 the safeguard wins one rescue and lowers the terminal cost to 25,586,388.96 versus 26,997,001.42 without it, but both cross this target on their eighth accepted step. Its extra work therefore does not improve time to this particular threshold.

The projected subproblem solve is never reached on the two full-TR large-scene trajectories: preconditioned inner solves stop before the first 16-step projection checkpoint. Their candidate banks contain the legacy CG and Cauchy proposals. Consequently these large-scene wins are not evidence for multi-shift or projected-Krylov acceleration. The no-projection arm retains that legacy bank, the radius controller, point safeguard and backtracking; it is not plain LM.

## Initial-damping sensitivity

A second, fixed LM configuration uses initial lambda 1e-4 on every scene. This is one run per scene, not a per-scene tuned baseline.

| Scene | LM, initial lambda 1e-4 |
|---|---:|
| Trafalgar-126 | 0.315 |
| Dubrovnik-88 | 0.116 |
| Final-1936 | 1.237 |
| Final-13682 | 7.450 |
| Final-4585 | miss at 20 seconds |

Initial damping materially changes the comparison. Full TR's Final-13682 advantage shrinks to **7.4% less time** against this configuration; the earlier 29% figure is not robust to this choice. Low-damping LM still misses Final-4585, ending at cost 15,165,634.49 with 86 accepted and 32 rejected steps. On Trafalgar the smaller initial lambda increases operator products to 689 and worsens runtime. Do not combine the best LM setting on each scene into a purported single fixed solver.

## Baseline definition and validation

The classical LM arm solves the coupled damped normal equations with camera damping lambda times diag(Hcc), and point damping lambda times the existing floored point diagonal. It uses one terminal PCG step, the full unregularized Gauss–Newton model for the gain ratio, positive-gain acceptance and Nielsen damping updates. It has no nonlinear checkpoint menu, line search or point safeguard. All arms use the same inner cap and existing inexact-PCG machinery. The LM path conservatively retains fused Schur-diagonal work that its camera scaling does not require; it is a matched-kernel baseline, not a separately optimized LM implementation.

An independent central-finite-difference Jacobian and dense damped solve on a five-camera, twenty-point synthetic BA problem validate one tightly solved LM step. Relative pixel-prediction disagreement is 2.04e-9; maximum point and translation errors are 4.15e-10 and 2.33e-9. The endpoint audit uses the original double-precision observations. Consecutive LM logs also validate coupled damping, Nielsen updates and rejection multipliers. Full-TR accepted-step checks validate positive model reduction, sufficient gain ratio and radius feasibility.

The seven-step smoke check reproduces the frozen full-TR endpoint to about 1.7e-11 relative objective error. Its target misses are intentional iteration-cap results, excluded from the timing table. An initial dense-check invocation used an unsupported CLI option and failed before solving; the corrected check is retained separately.

## Interpretation and next discriminating comparison

There is no universal winner on this small panel. The guarded radius-TR configuration remains the robust candidate across these five scenes, while removing projection is the leading simplification to confirm. Classical LM remains a strong baseline. Comparing LM with full TR changes coupled versus independently controlled point damping, the radius policy, and point rescue together; their speed difference cannot be assigned solely to radius control.

The point safeguard exploits exact conditional separability: for fixed proposed cameras, choosing each point from its old and proposed locations minimizes the objective over that finite Cartesian-product menu. This is a local candidate-selection fact, not a convergence or runtime theorem. Independent-set nonlinear refinement after a trust-region step already appears in [Ceres inner iterations](https://ceres-solver.readthedocs.io/latest/nnls_solving.html#inner-iterations). That prior art prevents treating independent point refinement alone as a novelty claim. LM itself also has a trust-region interpretation; our arm names distinguish implementations, not disjoint mathematical categories.

The next decisive control is **classical LM plus the identical point safeguard**, followed by a comparison with conventional nonlinear point inner iterations. If the benefit transfers, the defensible contribution centers on an inexpensive BA safeguard and its implementation, rather than a new TR algorithm. These additional experiments have not been run in this study.

No fresh Caspar run belongs to this ablation. Earlier Caspar timing results should not be substituted for the matched internal controls or read as evidence of novelty.

## Reproduction and artifacts

Scripts: `bench/build_solver_ablation.py`, `bench/solver_novelty_ablation.py`, `bench/check_classical_lm_dense.py`, `bench/report_solver_novelty.py`.

Artifact root: `/workspace/prism-tr-novelty-ablation`. The `build` directory contains frozen source, headers, compiler command and hash manifest. Tested binary SHA256: `3039b1c1d3c0051c7187a5d5b7ea7be1e20bbede2cf49c9ae9300615fb9ef9dc`. The builder derives from the frozen `prism-tr-preconditioner/pcg-v2` source and verifies its parent hashes. It refuses an existing build directory. The harness records per-run input and binary hashes, flags, commands, logs, endpoints, audits and misses. Its output argument must be a fresh directory.

The main tables come from `small/summary.json` and `large/summary.json`; smoke and dense validation live in `smoke` and `dense-check-v2`. Production defaults were not promoted, and pre-existing paused jobs remain paused.

The sensitivity results are split between `lm-sensitivity/results.json` (three scenes) and `lm-sensitivity-large-complete/results.json` (two scenes). A workspace disk-quota error interrupted the original large sensitivity output; an attempted restart also failed to write its protocol. Neither incomplete attempt is counted as an algorithmic miss or valid timing. The incomplete unaudited state was removed, and both large scenes were rerun successfully using `/tmp/prism-novelty-lm-sensitivity-large`. Their audited state files remain at that path to avoid filling the workspace again; commands, hashes, logs and results were copied into the artifact root, with exact state paths in `endpoint_locations.json`. These two endpoint files are on temporary storage. All other completed endpoints remain in the workspace.

`verification.json` records **49 timed runs, 46 target hits, 680 accepted-step checks, and maximum endpoint-audit relative error 8.63e-15**. The three valid misses are the two Final-4585 LM configurations and TR without its safeguard. Total native solve time for the completed timing panel is 128.09 seconds, excluding loading, audits, smoke/dense checks and quota-interrupted attempts. Five smoke endpoints and one dense endpoint provide six additional validation runs. Frozen source/header/binary hashes and the unchanged production source were checked; all eleven previously paused jobs were verified paused with matching process start times.
