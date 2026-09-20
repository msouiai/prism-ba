# Point rescue transfer, simplification and fresh Caspar comparison

Study date: 2026-09-09. This follows the [solver novelty ablation](solver_novelty_ablation_results.md).

The zero/full whole-track safeguard transfers to classical LM and rescues a previously missed target on Final-4585. It does not by itself reproduce guarded TR's speed. A bounded nonlinear point-refinement alternative improves Trafalgar but is more expensive and still misses Final-4585. The experiments therefore narrow the attribution, rather than establish a new trust-region algorithm.

## Protocol and interventions

All internal arms share a frozen binary derived from the preceding ablation: identical optimized assembly/Schur kernels, Hcc block PCG, FP64 arithmetic and acceptance, and FP32 stored fragments. Nine camera coordinates are used, with k2 fixed at zero. Data, objective thresholds, inner caps and independent endpoint auditing are unchanged. Initial LM lambda is fixed at either 10 or 1e-4 across all scenes. No per-scene best-setting oracle is presented as one solver.

The new `OCA_LM_POINT_RESCUE` modes activate only when the single terminal LM proposal fails to reduce the objective. They keep the proposed camera state fixed:

* Mode 1 calls the identical `PrismPointSafeguard::Choose` implementation used by TR. Each whole track chooses its old or proposed 3D point. It adds no uniform line search to LM.
* Mode 2 computes one analytic point-only Gauss–Newton step starting at the proposed point. Each 3x3 system has fixed diagonal regularization `1e-6 * max(diag(Hp), 1e-3 * trace(Hp)/3)`, with a tiny floor for empty tracks. It evaluates scales 1, 1/2 and 1/4 and retains the best whole-track cost, including the unchanged starting point. Unseen and unusable tracks remain unchanged. This is a bounded conventional refinement used as failed-step rescue, not a full Ceres inner-iteration implementation or a sweep over every accepted proposal.

Both modes require negative original-objective directional derivative and a full nonlinear Armijo decrease. The resulting full camera/point step then passes LM's existing unregularized Gauss–Newton prediction and positive gain-ratio acceptance. Nielsen lambda updates remain unchanged. A provisional rescue counter can therefore differ from the final accepted-rescue count; the report records both. No claim is made that a rescued direction still solves the original damped linear system.

One warp processes each track. The refinement performs its small solve and trial evaluations without point-sized scratch arrays; each rescue helper has an eight-byte counter. All evaluation, synchronization, refinement and rescue work is included in native runtime. The LM implementation retains previously documented unnecessary fused diagonal work, so it is a matched-kernel baseline rather than an independently optimized LM implementation.

## Staged selection

The first screen runs plain LM and safeguarded LM at both fixed initial lambdas on Trafalgar-126, Final-1936 and Final-4585, once each. The second screen runs the two point-refinement settings on the same scenes. This is 18 runs with at most 4, 12 and 20 solver seconds per scene, respectively.

On Final-4585, plain LM misses 20 seconds at both settings. The cheap safeguard reaches the target in 5.643 seconds at lambda 10 and 10.690 seconds at lambda 1e-4. It performs 15/26 rescue calls, with 9/17 provisional wins, costing 0.781/1.354 seconds. The initial-lambda-10 safeguard is selected as the fixed LM safeguard candidate for confirmation.

Point refinement at initial lambda 1e-4 reaches Trafalgar in 0.140 seconds, versus 0.320 seconds for plain low-damping LM in the fresh screen. It reaches Final-1936 in 1.283 seconds with four accepted steps and no rejections, but this is not faster than plain low-damping LM's 1.220 seconds. Both refinement settings miss Final-4585: final costs are 7,807,029 and 9,103,657 against the 7,488,278 nominal target. Their rescue work consumes 8.905 and 6.562 seconds. The low-damping setting is retained in confirmation because it wins on Trafalgar, not because it wins across scenes.

Three fresh rotated repetitions compare full TR, TR without projection, LM plus the cheap safeguard at lambda 10, and LM plus bounded refinement at lambda 1e-4. The refinement misses remain in the comparison. Projection removal retains the radius controller, legacy CG/Cauchy candidate bank, point safeguard and backtracking. It does not turn TR into vanilla LM.

| Scene | Full TR | TR without projection | LM + safeguard, lambda 10 | LM + refinement, lambda 1e-4 |
|---|---:|---:|---:|---:|
| trafalgar-126 | 0.265s | 0.199s | 0.216s | 0.140s |
| final-1936 | 1.557s | 1.552s | 1.309s | 1.260s |
| final-4585 | 2.321s | 2.320s | 5.640s | miss (0/3 hits) |

All entries are medians of three fresh runs. Guarded TR without projection is selected for the Caspar pairs: it hits all nine targets, improves Trafalgar by about 25% relative to full TR, and preserves Final-1936 and Final-4585 timing. LM refinement wins the two smaller rows but misses Final-4585 in all three runs. LM with the safeguard reaches that target in a median 5.640 seconds, versus 2.320 seconds for the selected TR configuration (about 2.43x faster). This is a configuration comparison, not an isolated proof that radius control causes the entire gap.

The subsequent fresh Caspar FP32 comparison uses a single selected PRISM configuration across the three screening scenes and Final-13682, with three alternating-order repetitions. Native timing excludes data loading. PRISM includes solver-local setup; the frozen standalone Caspar backend excludes graph setup, so these are not full COLMAP pipeline timings. Caspar uses the established 0.1% tighter native target to accommodate FP32 rounding; every endpoint is independently audited against the original double-precision observations. That margin is empirical, not a numerical certificate. Misses are censored at the budget and are never converted into exact speedup ratios.

| Scene | Selected TR median (range), seconds | Caspar FP32 median (range), seconds | Hits: TR / Caspar |
|---|---:|---:|---:|
| trafalgar-126 | 0.217 (0.195–0.221) | miss at 4s | 3/3 / 0/3 |
| final-1936 | 1.554 (1.552–1.556) | 3.238 (3.233–3.243) | 3/3 / 3/3 |
| final-4585 | 2.324 (2.324–2.362) | miss at 20s | 3/3 / 0/3 |
| final-13682 | 6.896 (6.895–6.901) | 8.346 (7.797–8.349) | 3/3 / 3/3 |

Selected TR hits 12/12 targets; Caspar FP32 hits 6/12. On the two scenes where both hit, TR is about 2.08x faster on Final-1936 and 1.21x faster on Final-13682 (about 52% and 17% less time). The large-scene result preserves the preceding preconditioner gain; projection removal does not create a new large-scene speedup. The two Caspar misses are not just failures of its tighter native stopping margin: their independently audited endpoints also remain above the common objective thresholds.

## Validation, limitations and interpretation

The independent refinement check forms central-finite-difference Jacobians on synthetic tracks and compares the selected point step with a CPU dense 3x3 solve. Maximum step disagreement is 5.08e-11. Tests cover rotated cameras, nonzero radial coefficients, a 65-observation track, an unseen point and a nonfinite track. The first test compilation lacked the CUDA infinity constant include; the subsequent initial CPU reference used a dangling Eigen expression. Both test issues were corrected before refinement benchmarking. The production refinement kernel did not change as a result, and the corrected test passed. The earlier independent dense check remains the validation of the underlying LM path.

The benchmark harness verifies full endpoint costs on original-double observations, accepted-step conditions, coupled LM damping and consecutive Nielsen updates. It also checks the rescue's slope and Armijo conditions. State hashes, frozen binary/source/header hashes and input hashes are recorded. Repetitions sample timing variability on the same problems; they do not supply statistical certainty over a scene population or establish novelty.

The finite zero/full point menu minimizes a conditionally separable objective over that menu. It does not imply a global convergence theorem, faster subsequent iterates, or optimal continuous point refinement. Independent-set nonlinear point refinement has prior art, including [Ceres inner iterations](https://ceres-solver.readthedocs.io/latest/nnls_solving.html#inner-iterations). The result here concerns this particular inexpensive safeguard and its measured integration. The next attribution experiment, if warranted, would isolate independently controlled point damping and the radius policy while keeping point rescue fixed.

## Code and artifacts

New code: `gpu/point_refinement_candidate.cuh`, `bench/build_lm_point_rescue.py`, `bench/check_point_refinement.cu`, `bench/point_rescue_caspar.py`, and `bench/report_lm_point_rescue.py`. The existing `bench/solver_novelty_ablation.py` now supports an explicit binary, the rescue arms, low-damping suffixes and rescue acceptance checks.

Persistent report, frozen build, scripts, manifests, logs and result JSON files: `/workspace/prism-lm-point-rescue`. Full endpoint states are under `/tmp/prism-lm-point-rescue` because the workspace reached its storage quota in the preceding study. `endpoint_locations.json` records their exact paths; temporary storage must be retained if those endpoints are needed. No completed prior benchmark data was deleted to make space. The builder refuses an existing build directory; the frozen build contains the exact tested source and headers. Its additional `build.sh` accepts a fresh output-binary path for rebuilding from that snapshot. This convenience script was not separately rebuild-tested; the binary compiled by the recorded original command is the one used throughout the study.

Tested binary SHA256: `8170e2d9deedcc50eee7b08fcec19edf08794b3a5a838b801e6c12f43854717a`. `selected_config.json` records the fixed no-projection configuration. This is a frozen research candidate; repository production defaults are unchanged by this study.

Final verification: **78 timed runs, 65 target hits, 1070 accepted-step checks**, plus the independent refinement test. Maximum endpoint-audit relative error is 1.49e-13. Total native solve time is 356.97 seconds (about six minutes); data loading, state export, independent audits and compilation are additional wall time. All valid misses are retained. Frozen source/header/binary hashes and every recorded endpoint state hash were verified. The production source retains its pre-study hash, all 11 pre-existing paused jobs remain paused with matching process start times, and no GPU experiment remains running.
