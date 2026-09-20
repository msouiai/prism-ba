# Camera-space trust-region PRISM: first bounded screen

**The prototype is the provisional winner on both sampled scenes.** All three arms reach all six targets (two scenes × three repeats). This is promising evidence for the complete prototype, not yet proof that multiple shifts are the source of its advantage. Defaults and the frozen v7 binary remain unchanged.

| Scene | Single guarded | Fixed five guarded | Camera TR, five shifts | TR speedup vs single / five |
|---|---:|---:|---:|---:|
| trafalgar-126 | 1.755 s | 1.244 s | **0.679 s** | 2.58× / 1.83× |
| dubrovnik-88 | 1.199 s | 2.300 s | **1.041 s** | 1.15× / 2.21× |

Times are medians of three logging-free native target crossings, certified by independent CPU endpoint scoring. Existing medium targets are 104534.24152926281 (Trafalgar126) and 359003.9111293723 (Dubrovnik88), each with the common 1e-8 inward margin and four-second native cap. No new target calibration or parameter tuning followed outcomes. Caspar was not rerun; its earlier timing must not be presented as a fresh paired comparison.

TR ranges are **0.668–0.694 s on Trafalgar** and **0.770–1.080 s on Dubrovnik**. The latter overlaps the single-guarded range of 1.004–1.252 s and includes one slower paired repeat. The 15% median improvement on Dubrovnik needs replication. The selected two-scene sample is not a general performance result.

## What the prototype implements

The camera norm is measured in the existing diagonal-equilibrated coordinates: if the physical camera increment is d_c = E z, the constraint is ||z|| ≤ Δ. Point damping is fixed within a linearization and its rejection retries. It may change after an accepted step under the existing point-damping floor/ratchet policy. This is a camera-space constraint with point safeguards, not a joint camera-and-point trust region.

At the existing CG checkpoints, the five shifted iterates become candidate directions. Each candidate is radially clipped to the radius and ranked by the reduced, fixed-point-damping model decrease bᵀz − 0.5 zᵀS z. An explicit Cauchy direction is also included. These model values are evaluated directly with operator products; their cost is charged. This finite candidate set is an approximation: radial clipping of a shifted iterate does not generally solve the trust-region KKT equations or identify the exact boundary multiplier. The Cauchy candidate provides a reduced-model descent control, not a global convergence proof for the full safeguarded algorithm.

The initial radius is the norm of the central-shift candidate at the first scoring checkpoint. Only the best model candidate is passed to the ordinary nonlinear scoring and backtracking/point-safeguard path. The alpha grid is disabled for TR, since it can violate the radius. Existing scalar backtracking contracts the camera step, and point-only repair leaves its camera component unchanged.

After any repair, the prototype directly computes the full, unregularized GN prediction for the actual proposed step: −rᵀJd − 0.5||Jd||². It independently measures the actual scaled camera norm. Acceptance requires positive actual and predicted reduction, rho ≥ 0.1, and radius feasibility (1e-8 numerical tolerance). The radius contracts by 0.25 for rho < 0.25, expands by two for rho > 0.75 near the boundary (norm ≥ 0.8Δ), and otherwise stays fixed. A rejected or invalid proposal always causes contraction. Radius bounds are 1e-14 and 1e16. These are frozen engineering choices, not tuned optimal settings.

The next menu center is the selected candidate shift times (old radius / new radius)², clipped to the original damping bounds; a Cauchy winner uses the prior center. This is a heuristic way to position a finite menu, not an exact radius-to-multiplier conversion. On rejection, the center and point damping remain fixed while the radius contracts.

A bounded bank holds at most 64 scaled camera vectors with their linear/quadratic model coefficients. Rejection retries reconsider these saved directions at the smaller radius without new Krylov or candidate-model operator products; assembly/factors are reused where valid. An accepted state or forced reassembly invalidates the bank. The normal finite inner-retry limit is retained. The candidate bank is not a general reusable Lanczos basis and cannot synthesize arbitrary new shifted solutions.

**No BA rejection occurred in this screen**, including the two six-iteration sanity runs. Thus the observed gains are not evidence of saved retry work. Candidate-bank reuse and physical/scaled norm conversion pass a separate GPU component test, but the integrated rejection path still needs an activating BA case.

## Where work changed

Unprofiled medians. Matvec totals already include TR’s extra model-evaluation products. Full objective scores count menu + alpha + backtracking, including point-safeguard full-cost checks. They exclude the trackwise old/full comparisons inside the safeguard, initial scoring and the separate full-GN prediction passes.

| Scene | Arm | Accepted steps | Total matvecs | Model matvecs (subset) | Full objective scores | Full-GN prediction passes |
|---|---|---:|---:|---:|---:|---:|
| trafalgar-126 | single | 52 | 3753 | 0 | 583 | 0 |
| trafalgar-126 | five | 35 | 2408 | 0 | 601 | 0 |
| trafalgar-126 | tr | 14 | 1414 | 278 | 31 | 14 |
| dubrovnik-88 | single | 21 | 859 | 0 | 188 | 0 |
| dubrovnik-88 | five | 40 | 1543 | 0 | 622 | 0 |
| dubrovnik-88 | tr | 11 | 805 | 177 | 22 | 11 |

On Trafalgar, counted full objective scores fall from **601 to 31** versus fixed five; on Dubrovnik, **622 to 22**. This trades many nonlinear evaluations for cheaper reduced-model selection, while changing the trajectory and damping control. TR also takes fewer accepted steps on these targets. On Dubrovnik, point repair remains active in some runs (three repair wins in repeat one, none in repeats two/three); all repaired accepted steps pass the full-model and radius checks.

The prototype simultaneously changes candidate selection, alpha search, the acceptance test and damping/radius feedback. Consequently the speedup cannot be attributed to any one component, or to multishift itself, from this comparison. A **single-shift version of the same trust-region controller** is the next necessary ablation. Only after that should the fixed configuration move to a held-out medium/large problem.

## Verification and reproducibility

Two six-iteration real-BA sanity runs precede 18 target runs; all **20 exported endpoints pass independent CPU FP64 audits**, maximum relative discrepancy 9.89e-15. Every recorded accepted TR step has positive predicted reduction, sufficient rho and a feasible camera norm; the maximum norm/radius ratio is 1.0000000000000002. Binaries, original inputs, harness files and included headers are hashed before the experiment, and manifests are verified against the frozen plan.

Tests:

- 500 dense SPD shifted/clipped candidates: radius feasibility, monotone shifted-solution norms and directly checked quadratic prediction; maximum prediction error 1.09e-15. Acceptance and radius-update guards pass.
- GPU candidate-bank selection at four shrinking radii agrees with independent dense CPU selection to 8.36e-17 in vector norm, uses zero additional operator calls during reconsideration, and verifies physical-to-scaled camera norms.
- The existing GPU full-step model test passes 12 finite-difference mixed-block/mask cases, maximum relative error 3.81e-10.

Native measurement work: 25.137 s; sanity work: 0.640 s; total **25.777 s**, excluding separately recorded component tests and compilation. Native clocks include solver-local allocations and the candidate bank; input loading/upload, state export and independent CPU endpoint audits are outside those clocks. Process-wall times are retained separately. No extra BA runs were selected after seeing outcomes.

| Scene | Arm | Crossing range (s) | Median endpoint | Median process wall (s) |
|---|---|---:|---:|---:|
| trafalgar-126 | single | 1.173–1.955 | 104514.457275 | 2.307 |
| trafalgar-126 | five | 0.824–1.585 | 104522.538459 | 1.785 |
| trafalgar-126 | tr | 0.668–0.694 | 104446.186604 | 1.273 |
| dubrovnik-88 | single | 1.004–1.252 | 358719.443509 | 1.853 |
| dubrovnik-88 | five | 2.279–2.320 | 359000.639588 | 2.975 |
| dubrovnik-88 | tr | 0.770–1.080 | 358968.257247 | 1.717 |

All code is in the shared repository: [isolated source builder](../bench/build_camera_tr.py), [radius/model rules](../gpu/camera_tr_math.h), [GPU candidate bank](../gpu/camera_tr_diagnostic.cuh), [experiment runner](../bench/camera_tr_study.py), [auditor/summarizer](../bench/summarize_camera_tr.py), [dense tests](../bench/test_camera_tr_math.cc), [GPU tests](../gpu/test_camera_tr_bank.cu). The main solver source and normal build targets are unchanged.

Reproduce the isolated build using `/workspace/prism-camera-tr/source-before.cu` (the retained frozen source snapshot), `python3 bench/build_camera_tr.py`, then `python3 bench/camera_tr_study.py` and `python3 bench/summarize_camera_tr.py`. Existing completed runs are retained rather than overwritten. Full protocol, source patch, binary, test logs, manifests, traces, states and summaries are in `/workspace/prism-camera-tr`. Old paused jobs remain paused.
