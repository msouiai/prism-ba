# Rejection-triggered switching: fewer retries, no Ladybug recovery

2026-09-08. **Do not promote the new in-place switch.** It detects Ladybug1197's rejection problem and cuts rejection count substantially, but fails both quality targets. Paired from the start remains the Ladybug winner; fixed-five remains the practical incumbent on Dubrovnik173 and Venice52.

## Rule and implementation

Experimental `OCA_DEMAND_MENU=3` starts in fixed-five mode. After two consecutive rejected attempts, it permanently activates existing paired mode 2. The trigger contains no scene identifier. It uses the existing paired `Reject` update on the rejected attempt's camera lambda and point tau, clips to existing bounds, invalidates the factor cache, and proceeds from the current geometry. It does not restart or relax acceptance criteria.

The two-rejection threshold was selected from previous fixed-five traces: both Ladybug repeats first reached it at outer 2, eventually reaching streaks of eight; Dubrovnik and Venice had no rejected attempts. These scenes informed the design, so this is a development check, not held-out validation.

Code is in `gpu/oca_cuda.cu`. Mode 3 requires five slots, the original FP64 unshared diagonal full-scoring profile, original backtracking, point safeguard mode 1, and no other repair/model feedback. It allocates the paired fallback-step buffer at initialization so the transition can occur safely; the buffer is freed on exit even if switching never activates. Existing modes and defaults remain unchanged.

## Matched original-input results

All three arms use the same verified v6 binary and point repair. Original input files, default starting damping and original coupling restored. Two repeats, reversed order. Ladybug target366600 cap6; Dubrovnik target375358.1835212728 cap6; Venice target252000 cap4.

| Scene | Fixed-five | Paired from start | Rejection switch | Practical winner |
|---|---:|---:|---:|---|
| Ladybug1197 | Miss (0/2) | **2.318 s (2/2)** | Miss (0/2) | Paired |
| Dubrovnik173 | 2.388 s (2/2) | 4.882 s (2/2) | 2.358 s (2/2), inactive | Fixed-five behavior |
| Venice52 | **2.210 s (2/2)** | 2.602 s (2/2) | 2.264 s (2/2), inactive | Fixed-five |

Times are median native first-target crossings with CPU-audited exported endpoints. The inactive switch's 1.2% lower Dubrovnik time and 2.4% higher Venice time do not establish controller improvements: it made no policy transition there. Treat those as comparable fixed-five performance with small run/trajectory differences. All modes were opt-in research configurations and no default changed.

## Ladybug: rejection reduction is insufficient

| Metric, median | Fixed-five | Paired from start | Switch |
|---|---:|---:|---:|
| Outer rejections | 34 | 0 | 4 |
| Backtracking evaluations | 318 | 24.5 | 99 |
| Matrix-vector products | 2810 | 1017.5 | 3184.5 |
| Scored candidates | 1056.5 | 404.5 | 681 |
| Final CPU cost | 367066.40 | 366566.10 | 368268.89 |
| Native return time | 6.037 s | 2.332 s | 6.028 s |

Switching reduced rejections by 88% and backtracking evaluations by 69% relative to capped fixed-five, yet required more matrix-vector products and ended at worse cost. It remained about 0.46% above the target. This is not catastrophic quality deterioration, but it fails the intended time-to-target recovery. Counts compare capped or target-stopped full runs, not equal-length trajectories.

Both switch runs transitioned exactly once at outer2 after the second rejection. The trigger pair was lambda=0.1111111111111111, tau=0.01111111111111111. The next attempt correctly used lambda=1.111111111111111 and tau=0.1111111111111111, following the paired retry rule. No switches occurred in the four Dubrovnik/Venice candidate runs.

The opening diagnostic provides context. In the first repeat, fixed-five and the switch both reached cost about 2.039 million after two accepted steps, whereas paired from the start was at about 3.873 million. Despite its less aggressive early objective decrease, paired won the final target race. A switch at outer2 cannot undo those already accepted geometric steps. This supports investigating path dependence; it does not prove the run is trapped in an irrecoverable basin or identify the unique cause of failure.

## Build verification and validation

A source guard was added while the first compilation was running. Binary inspection found that the executable lacked that final guard despite the incremental build reporting up-to-date. The preliminary batch was stopped and retained, then a rebuild was forced after compilation ended. The final guard's presence was verified before freezing `prism-v6`; all final comparisons use that same binary. No preliminary results enter the table.

18 verified solves consumed **62.384 native solver seconds**. The discarded preliminary batch has 13 completed solver logs totaling 41.753 seconds (12 have result audits; one completed after its runner was stopped). Total logged native solver time was **104.136 seconds**, excluding compilation, startup, and CPU auditing. These preliminary files are retained for provenance, not counted as validated comparison evidence.

All 18 verified endpoint audits and monotonic-cost checks passed; maximum relative discrepancy 2.61e-12. Independently audited all six switch traces, both actual transitions, and both subsequent damping pairs. Both invalid-configuration guard tests passed. CUDA CLI and core library built, and changed-code whitespace checks passed. No sanitizer was run; no kernel or state-layout changes were introduced, although mode3 adds the existing fallback buffer to initially fixed-five runs. The standard post-rejection paired path invalidates the factor cache in both transitions.

Artifacts: `/workspace/prism-rejection-switch/` holds trigger-selection traces, frozen protocol/plans, verified and preliminary binaries/logs/states/results, guards, opening diagnostic, transition audits in `summary.json`, provenance, and completion. `verified/` is the final comparison; `screen/` is the excluded preliminary batch. Eleven earlier jobs remain paused. Nothing was pushed.

## Verdict and next experiment

Current practical winner ledger remains **fixed-five + point repair for Dubrovnik173/Venice52; paired + point repair for Ladybug1197**. The rejection detector distinguishes these development cases, but an in-place transition does not provide the desired universal configuration.

The next hypothesis worth a short test is a bounded early rollback/restart into paired mode when this trigger fires, charging all abandoned work to the same clock. That can test whether the early fixed-five trajectory is the obstacle, while retaining the best valid solution if the alternative fails. It needs explicit state/timing accounting; do not simply discard the opening time or claim that fewer rejections means faster BA. Until such evidence exists, leave this switching mode experimental and disabled by default.
