# Rescue, damping and radius attribution — 2026-09-09

This study follows [point rescue transfer](lm_point_rescue_results.md). It identifies a promising camera-radius controller with coupled camera/point damping. It improves the tested medium and large scenes relative to the previous guarded TR configuration, with a regression on Trafalgar. The evidence concerns an interaction between damping and control policies; it does not establish a novel trust-region algorithm.

## What is held fixed

All arms share one frozen binary, optimized assembly and Schur kernels, Hcc block PCG, FP64 arithmetic and state, and FP32 stored fragments. Data, independent original-double endpoint audits, target thresholds, PCG caps, and native budgets remain unchanged. Trafalgar-126 has a 4-second budget, Final-1936 12 seconds, and Final-4585/Final-13682 20 seconds. The original small-progress stopping rule is retained; a target miss can stop before its time budget.

The controlled LM-family comparisons keep Hcc diagonal camera coordinates, a single terminal PCG direction, full Gauss–Newton model evaluation, and the same rescue policy. They do not enable the existing TR candidate bank or projected Krylov solver. Comparisons with the previous full configuration additionally change its Schur-diagonal camera metric, candidate bank and initial damping. Consequently not all of the end-to-end speedup over that configuration can be attributed to radius control alone.

`OCA_ATTR_RESCUE` allows LM to use the actual existing uniform backtracking plus zero/full whole-track safeguard. This includes its three-accepted-step warmup and stop-confirmation/rearm rules. The preceding standalone LM safeguard instead operated on failed steps without that warmup; the matched policy replaces it, rather than stacking two rescue implementations. Every accepted rescue still passes the full model and LM gain-ratio check, with Nielsen updates applied to the actual rescued step.

## Rescue and point damping screens

One run per arm per scene; all times are seconds to the common audited threshold.

| Scene | LM + standalone safeguard, lambda 10 | LM + matched rescue, lambda 10 | LM + matched rescue, lambda 1e-4 |
|---|---:|---:|---:|
| Trafalgar-126 | 0.236 | 0.181 | 0.152 |
| Final-1936 | 1.278 | 1.298 | 1.220 |
| Final-4585 | 5.642 | 4.681 | 5.599 |

Matching rescue explains part of the preceding Final-4585 gap, but does not close it. The screen is not a significance claim for the small Final-1936 difference.

Source inspection found an important damping-scale difference: the previous TR configuration starts nominal lambda at 10, but `OCA_GRID_DOWN=2` and a single shift produce camera sigma=0.1 while initial point tau=10. Standard LM's initial lambda=10 applies to both blocks. These scalars also multiply different camera metrics, so matching their ratio does not make the two regularization matrices identical.

The next screen fixes initial camera lambda=0.1 and compares coupled tau=lambda against the existing ratcheted point policy:

    tau_k = max(1e-7 * 10^min(reject_streak,12), c * min_{i<=k} lambda_i),
    c in {1, 100}.

The minimum ranges over attempts, including rejections. The second term cannot rise when camera lambda rises; the first can increase with consecutive rejections. The formula is checked against every emitted LM attempt. Setting c=100 matches the previous TR configuration's initial scalar ratio. It does not reproduce that solver's different metric or retry-bank reuse behavior.

| Scene | Coupled damping | Ratcheted floor, c=1 | Ratcheted floor, c=100 |
|---|---:|---:|---:|
| Trafalgar-126 | 0.238 | 0.218 | 0.141 |
| Final-1936 | 0.976 | 0.977 | 1.313 |
| Final-4585 | miss | 7.917 | 4.842 |

The coupled Final-4585 run stops after 14.666 seconds at cost 9,694,345 because eight successive accepted outer iterations make less than 1e-5 relative progress. This is retained as a target miss, not reported as a run that consumed the full 20-second budget.

## Matched radius experiment

Both controller arms use gain ratio rho>0.1, identical rescue and the same point-damping policy. This separates the acceptance threshold from the controller switch. The scalar-damping control uses Nielsen updates; the camera-radius variant uses the following rules:

* Initialize R from the first terminal camera step norm in the same Hcc coordinates.
* Clip that terminal camera direction to R before point back-substitution. The point step is recomputed as `(C + tau Dp) dp = -gp - W^T dc`; it is not uniformly scaled with the camera step.
* Evaluate the full nonlinear objective and full unregularized model after any rescue. Check the final camera norm against R.
* Quarter R for rho<0.25; double it for rho>0.75 when the camera norm is at least 0.8R. Ensure a rejected attempt contracts R.
* Set the next camera lambda to `lambda * (R_old/R_new)^2`. For an accepted interior step with rho>=0.25, also permit a tenfold lambda decrease. Coupled point damping follows this lambda; the alternative floor follows the formula above.

This is a terminal-direction camera-radius heuristic, not an exact trust-region subproblem solve or a convergence theorem. The radius, clipping, and lambda transitions are independently checked from logs. Changing control changes future states and damping histories; these are policy comparisons rather than identical-state trajectory comparisons.

| Scene | Coupled + Nielsen | Coupled + radius | c=100 floor + Nielsen | c=100 floor + radius |
|---|---:|---:|---:|---:|
| Trafalgar-126 | 0.243 | 0.267 | 0.139 | 0.232 |
| Final-1936 | 0.977 | 0.856 | 1.303 | 0.980 |
| Final-4585 | miss | 2.102 | 4.848 | 12.472 |

Radius control helps Final-1936 under both damping policies, but its effect reverses on Final-4585. Coupling lets a rejected attempt raise point and camera damping together. In the c=100 radius run, the first three failed attempts at one outer iteration use camera lambdas 0.0025, 0.04 and 0.64 while point tau remains 0.25. This is a concrete difference in rejection response; it is a plausible explanation for the interaction, not a proof that it alone causes the timing gap.

## Confirmation and largest-scene check

Only the promising coupled-radius candidate is repeated against the previous guarded TR without projection. Both configurations use the new binary. Smaller-panel order rotates over three repetitions. The largest-scene screen is followed by two alternating pairs if it improves. No per-scene parameter tuning or additional Caspar runs are used.

| Scene | Previous guarded TR | Coupled-radius candidate | Time change |
|---|---:|---:|---:|
| trafalgar-126 | 0.198s | 0.271s | +36.8% |
| final-1936 | 1.551s | 0.870s | -43.9% |
| final-4585 | 2.317s | 2.096s | -9.5% |
| final-13682 | 6.920s | 4.268s | -38.3% |

All rows are three-run medians. Both configurations hit 12/12 confirmation targets. The coupled-radius candidate is the new leader on the three larger scenes in this panel; previous TR remains faster on Trafalgar. This is not a universal default recommendation. Final-13682 ranges are 6.899–6.939 seconds for previous TR and 4.264–4.284 seconds for the new candidate.

On the first Final-13682 run, the new candidate uses five accepted steps, zero rejections and 28 operator products, versus the previous configuration's eight steps and 43 products. No camera clipping or point safeguard fires on that new trajectory. Its largest-scene improvement therefore does not demonstrate a benefit from active radius clipping: changed damping placement and updates matter. A matched Nielsen control on the largest scene is included to check this attribution directly.

The matched coupled-damping Nielsen control reaches Final-13682 in **4.918 seconds** (one run), compared with the radius candidate's **4.268-second median**. Thus about 13% less time is associated with the controller in this matched comparison; the entire 38% improvement over previous TR cannot be assigned to radius control. No active radius clipping occurs in any of the three new largest-scene runs. The control result is a bounded attribution check, not a three-run estimate.

## Validation and artifacts

The unchanged coupled LM path passes the independent finite-difference dense check with relative pixel-prediction disagreement 2.04e-9 and maximum translation error 2.33e-9. A second dense check uses camera damping 0.1 and point damping 10. It agrees within relative pixel error 2.39e-8, point error 9.68e-9 and translation error 6.09e-7, within the declared 1e-7/1e-6 tolerances. These checks include finite-difference and stored-fragment errors; no bitwise identity is claimed.

All accepted-step model checks, point-damping formulas, radius bounds and controller transitions are checked by `bench/controller_attribution.py`. Endpoints are independently audited on the original double-precision observations. Native timing includes scoring and rescue; input loading, state export and audits are outside that scope. Repeating four selected scenes does not establish population-wide superiority or novelty.

Code: `bench/build_controller_attribution.py`, `bench/controller_attribution.py`, `bench/report_controller_attribution.py`. The builder patches the frozen preceding source and verifies parent hashes; it refuses an existing build directory. Production `gpu/oca_cuda.cu` is unchanged by this study. Frozen source, headers, tested binary, scripts, logs and result manifests are saved in `/workspace/prism-controller-attribution/artifacts.tar.gz`, with report, configuration and verification JSON alongside it. A quota failure during copying required the single-archive format. A reporting script truncated by the failed write was restored and checked; the original experiment source and results under `/tmp` were intact throughout. Endpoint states remain under `/tmp/prism-controller-attribution` due to the workspace quota; `endpoint_locations.json` records their paths. The temporary states must be retained if needed for later inspection.

Final verification: **58 timed runs, 56 target hits, 712 accepted-step checks**, and two independent dense checks. The two misses are the coupled initial-lambda-0.1 Nielsen controls on Final-4585, at the two acceptance thresholds. All 184 radius attempts were checked, including 62 pre-rescue camera clipping events. Maximum endpoint-audit relative error is 2.53e-14. Total native solve time is 157.66 seconds, excluding compilation/loading/export/audits. Frozen hashes and endpoint state hashes are verified, the production source retains its pre-study hash, and all eleven pre-existing paused jobs remain paused. No GPU experiments remain running.
