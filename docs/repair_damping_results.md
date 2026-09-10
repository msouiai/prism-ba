# Repaired-step damping results — 2026-09-08

**The measured damping freeze is fixable, but model-agreement feedback is not a universal controller.** With point repair and bounded damping relaxation, paired demand reaches the same quality target 4.32x faster on Dubrovnik356 and 1.22x faster on Ladybug1197 than plain paired demand. A prospective Venice52 repeat misses its target; frozen point repair succeeds twice. Keep the new controller opt-in.

## What changed

`OCA_REPAIR_DAMPING=1|2|3` evaluates the full unregularized GN prediction of the **actual accepted repaired step**, including its selected point mask, before state mutation and after demand competition. Mode1 audits only. Mode2 halves the retained camera/point damping pair when valid rho>0.75. Mode3 also doubles the pair when rho<0.25. Invalid or numerically tiny predictions retain the pair. A small rounding band around thresholds also retains it.

The existing nonlinear acceptance check remains authoritative. Feedback is applied after the demand controller stores its winning pair; next-iteration factor reuse checks include the changed point damping. This implementation supports paired demand, original backtracking, FP64 CD9 unshared L2, with or without point repair. Other experimental model/point-feedback/replay paths are rejected by configuration guards. Unset/zero leaves this feedback off.

Prediction P=-g^T*d-0.5*||Jd||^2 is algebraically valid for an arbitrary mixed direction. Applying a multiplicative damping rule from its agreement ratio is an experimental policy, not an optimal two-parameter update or a convergence theorem. See [the mathematical analysis](repair_damping_math.md).

## Scope and validation

Completed 30 investigation steps with **31 short BA runs and 105.754292 seconds of native solver time**. No large scene and no external-solver rerun. GPU: RTX2000 Ada 16GB, CUDA12.8, architecture89. PRISM uses the existing compact-fragment/execution profile and target-state CPU auditing.

All 31 exported states passed the independent CPU raw-objective audit, maximum relative discrepancy **3.71e-12**. Accepted objective traces are monotonic. All **265 actual-step model records** and their pair updates passed independent arithmetic checks; **258 next-iteration records** confirm that the updated pair was used. The remaining model records have no subsequent recorded attempt, such as a target or budget endpoint. No invalid prediction occurred in these BA runs; invalid-path handling is covered by host tests.

The main screen has two repeats per cell in reversed scene/arm order. Targets were fixed before this round: Ladybug1197 cost366600/cap6s; Dubrovnik356 cost754100/cap8s. A hit requires a native crossing before the cap and an independently verified returned cost at or below target. Solver return times can slightly exceed their caps at existing check boundaries; late crossings are not counted as hits. CPU audits, process setup, compilation and kernel gates are outside the reported native BA time.

## Medium target results

Median time to the same quality; every numeric cell has2/2 hits.

| Paired-demand configuration | Ladybug1197 | Dubrovnik356 |
|---|---:|---:|
| Plain paired | 2.805s | 6.923s |
| Point repair, frozen damping | 2.553s | Miss, 0/2 |
| **Point repair + relaxation (mode2)** | **2.304s** | **1.604s** |
| Point repair + symmetric feedback (mode3) | 2.473s | 1.609s |
| Relaxation without point repair | 2.287s | 7.684s |

The selected mode2 crossings on Dubrovnik were1.6067s and 1.6015s. It reached cost about 747327, below target754100. On Ladybug, crossings were2.2765s and 2.3315s. This is a real online equal-quality comparison against paired demand, not a fixed-state gain extrapolation.

On Dubrovnik, repaired accepted steps had rho between0.778 and 0.997 in the first relaxation run. The pair was halved after all ten such accepts, escaping the previous freeze. In contrast, the no-point-repair controller saw rho between0.00497 and 0.449, never changed damping, and reproduced the plain solver's799 matvecs and 839 backtracking scores while paying extra prediction cost. Point repair and damping feedback are complementary here; neither ablation alone produces the result.

Ladybug shows a different balance: relaxation without point repair is about as fast as the combined method. With only two repeats and known floating-point trajectory variability, the small difference is not evidence for a reliable ranking. Symmetric feedback provides no compelling advantage: its Dubrovnik decisions are identical, and Ladybug is slower in this small screen. Mode2 was selected before prospective runs because it passed both medium targets without material regression and uses the simpler one-sided rule.

## Work and overhead

| Dubrovnik statistic, median | Plain paired | Repair + mode2 |
|---|---:|---:|
| Matvecs | 799 | 209 |
| Backtracking cost evaluations | 839 | 27 |
| Outer rejected iterations | 0 | 0 |
| Actual-step prediction calls | 0 | 10 |
| Prediction time | 0 | 0.107s |
| Point-selection/verification time | 0 | 0.086s |

Thus backtracking scores fall about 96.8% and matvecs about 73.8%. Outer rejections were already zero; the improvement comes from fewer shortened-step iterations and cost probes. The new prediction pass adds one persistent16-byte reduction allocation and uses the existing accepted-step vector; it does not allocate per-point or per-observation prediction buffers. Point repair has its separate existing8-byte counter.

Prediction and point repair together consume about 0.193s of the 1.622s median native return time, approximately 12%. Without point repair on Dubrovnik,68 model calls consume 0.731s and do not change the trajectory, explaining most of that ablation's slowdown. This quantifies a possible optimization target but does not demonstrate that all this time is removable.

## Prospective contradiction and bounded repeat

Venice52 target252000/cap4s and Dubrovnik88 target360000/cap3s were specified before the main screen. The selected controller was tested against plain and frozen-point paired demand. Venice's first result was close to the cap and worse than frozen point repair, so one reversed-order repeat was recorded before making a verdict.

| Prospective scene | Plain paired | Frozen point repair | Repair + mode2 |
|---|---:|---:|---:|
| Venice52, N2 | 3.636s, 2/2 hits | **2.695s, 2/2 hits** | **1/2 hits** |
| Dubrovnik88, N1 | 0.650s | 0.640s | 0.612s |

Venice mode2 first reaches the target at 3.915s, but the repeat returns cost 254289 after 4.057s and misses. Its four repaired-step agreement ratios in the missed run are 1.114,1.010,1.395 and 1.123: each satisfies the one-sided relaxation rule. Local agreement/realized decrease does not predict the quality of subsequent trajectories after changing both damping values. Symmetric mode3 would make the same decisions on these recorded ratios; it was not rerun speculatively.

Dubrovnik88 invokes neither point repair nor the new prediction, so its small timing differences cannot be credited to the controller. The old opt-out study already documented late trajectory variation from initially near-roundoff differences; this round does not claim deterministic performance or resolve that numerical sensitivity.

The Venice miss blocks universal promotion. No extra threshold was fitted to exclude this scene, no third controller was added, and no large run was launched.

## What the math tests establish—and do not

- 117 host checks cover valid/invalid predictions, exact threshold boundaries, cost scaling and audit behavior. The first boundary test failed due to floating-point threshold flips; a conservative64*epsilon ratio band fixed it before BA runs.
- 36 independent GPU finite-difference cases include zero/full/fractional point masks, camera scales and k2 masks. Maximum relative prediction/slope/curvature discrepancy is 4.68e-10. CUDA memory sanitizer reports zero errors.
- 1000 affine-residual cases verify the actual masked prediction against exact objective differences. Substituting the original unmasked prediction generally fails.
- An explicit nonlinear least-squares example has identical current residuals, gradient, GN matrix and full-step rho but opposite camera-only versus point-only errors. One ratio cannot identify two separate damping corrections.
- A scalar residual example has rho about 0.999 for a tiny descent step while its full step raises cost from 0.5 to 500000. High local agreement is not a certificate for a larger step or lower damping.
- CLI and embedding core build. Five runtime compatibility guards pass. The final summary checks both the proposed factor and the pair actually consumed by the following iteration.

These checks validate the prediction and integration. They do not transfer trust-region convergence guarantees to a masked step that is not an exact trust-region solution, or demonstrate publication-level novelty for agreement-based damping.

## Comparison with the strongest previous configurations and Caspar

The prior [point-safeguard screen](point_safeguard_results.md) measured Dubrovnik fixed single with point repair at 1.238s and fixed five with point repair at 1.422s. The new paired result 1.604s is still slower than both. These are historical cross-round comparisons on the same GPU/target, not fresh matched-arm timings. **This is a major repair to paired demand, not a new overall fastest Dubrovnik configuration.** It also does not demonstrate that multiple shifts beat one well-controlled shift.

The preceding [Caspar comparison](short_caspar_results.md) used these same medium targets. Native FP32 Caspar reached neither: Ladybug stopped at its damping limit with CPU raw cost about 484812, while Dubrovnik ended near1154072 at 8s. The new PRISM configuration reaches both targets, but Caspar was not rerun here and there is no finite measured equal-quality speedup ratio. The FP64/FP32 distinction and native-versus-CPU score discrepancy on Ladybug remain material limitations.

## Decision and next bounded investigation

Keep mode2 as an experimental paired-demand option. The diagnosis that rescued-step freezing harmed Dubrovnik is supported by repeatable online improvement and the no-point ablation. A universal joint-damping rule is not supported by Venice.

The next mathematically motivated diagnostic is to separate camera-only, point-only and interaction model errors at a small number of saved accepted states from Dubrovnik and Venice. With two additional true-cost probes F(dc,0) and F(0,dp), plus the already observed F(dc,dp), blockwise GN predictions expose which component or interaction accounts for model error along this direction. That supplies information absent from one scalar rho. It still would not identify a globally optimal damping pair or justify an immediate new default. Test those local diagnostics before another controller rollout.

## Reproduction

Artifacts: `/workspace/prism-repair-damping/`. `steps.json` records all 30 steps. Frozen `prism-v1`, matching source/header snapshots, plans, flags, binary/data hashes, logs, CSVs, raw JSONL traces, exported states, mathematical tests, model-update audits, selection and prospective-repeat rationale are retained.

```bash
cmake -S gpu -B /workspace/prism-repair-damping/build -DOCA_CUDA_ARCHITECTURES=89
cmake --build /workspace/prism-repair-damping/build --target oca_cuda oca_core test_repair_model -j2
python3 bench/repair_damping_study.py audit
python3 bench/repair_damping_study.py medium
python3 bench/backtrack_investigation.py /workspace/prism-repair-damping/medium-plan.json
python3 bench/backtrack_investigation.py /workspace/prism-repair-damping/prospective-plan.json
python3 bench/backtrack_investigation.py /workspace/prism-repair-damping/prospective-repeat-plan.json
python3 bench/summarize_repair_damping.py
```

Plan generators refuse overwrite; the runner skips completed results and preserves incomplete logs. Use a new root in saved plans for a fresh study. Legacy JSONL traces use lowercase `nan` for unavailable old rho fields; the analysis parser normalizes these tokens without changing the raw logs. The new repaired-model records are independently parsed and checked.

Source: `gpu/repair_damping.h`, integration in `gpu/oca_cuda.cu`, `gpu/test_repair_model.cu`, `bench/test_repair_damping.cc`, `bench/check_repair_damping_math.py`, study generator and summarizer above. No default changed or push performed; all 11 previously paused jobs remain paused.
