# Early restart: recovery across the three development scenes

2026-09-08. **The bounded restart rule reaches all six targets across Ladybug1197, Dubrovnik173, and Venice52.** It recovers Ladybug where the in-place switch failed, while leaving fixed-five active on the other scenes. Paired from the start remains faster on Ladybug. This is a promising single rule on the development set, not a universal or held-out winner.

## Rule and scope

Start fixed-five with point safeguard mode 1. If two consecutive rejected attempts occur at outer index 0, 1, or 2, stop before changing the last accepted state and export it. Restart paired mode from the original BAL input once, using the remaining native solver budget. After that opening window, remain fixed-five rather than restarting on a later rejection. The external harness retains whichever independently CPU-audited endpoint has lower cost.

`OCA_DEMAND_MENU=3 OCA_SWITCH_RESTART=1` enables the stop request. The CLI emits `RESTART_REQUEST` and returns the retained state; the CLI alone does **not** orchestrate the second solve. `bench/early_restart_screen.py` implements the complete two-stage policy and best-state selection. Mode3 without this extra flag retains the previously tested in-place switch. Defaults remain unchanged.

The native target time for a restart is the entire first solver's return time plus the second solver's first-target crossing. The second-stage budget is the original cap minus the first-stage native solve time. All abandoned solver work is charged. Native clocks exclude input loading and export, so total process wall through completion is reported separately, including both solver launches, loads, exports, and harness bookkeeping. CPU audits occur after solving and are excluded from these clocks. This is not a strict process-wall deadline controller.

## Same-binary original-input comparison

All arms use frozen v7, original inputs, original coupling and starting damping, and point repair. Two repeats, reversed scene/arm order. Targets/caps unchanged: Ladybug366600/6s, Dubrovnik375358.1835212728/6s, Venice252000/4s.

| Scene | Fixed-five native crossing | Paired native crossing | Restart-rule native crossing | Restart target hits |
|---|---:|---:|---:|---:|
| Ladybug1197 | Miss (0/2) | **2.576 s** | 2.907 s | 2/2 |
| Dubrovnik173 | 2.426 s | 4.878 s | 2.114 s, inactive | 2/2 |
| Venice52 | 2.379 s | 2.588 s | 2.148 s, inactive | 2/2 |

Values are medians of two runs. Restart-rule results on Dubrovnik and Venice do not demonstrate a benefit from restarting: no restart fired. They follow the fixed-five path, with differences in trajectories/timing. For example, median matrix-vector counts differed between fixed-five and the inactive restart arm: 1114.5 versus 966.5 on Dubrovnik, 1906 versus 1712.5 on Venice. The measured lower times cannot be assigned causally to an inactive policy. Treat these cases as preservation of fixed-five behavior rather than a new algorithmic speedup over it.

Ladybug restart crossings were 2.865 and 2.950 seconds including abandoned work. Paired from the start took 2.490 and 2.662 seconds. Median discarded first-stage solve time was **0.298 seconds**. The restart policy takes about 12.8% more native time than paired from the start on this scene, but restores reliability compared with fixed-five and the in-place switch.

## Process wall time

| Scene | Fixed-five return wall | Paired return wall | Restart-rule return wall |
|---|---:|---:|---:|
| Ladybug1197 | 6.926 s, target missed | **3.384 s** | 4.512 s |
| Dubrovnik173 | 3.267 s | 5.718 s | 2.943 s, inactive |
| Venice52 | 3.036 s | 3.218 s | 2.820 s, inactive |

These clocks run through returned/exported endpoints, not the precise instant of target crossing. They expose the extra process/I/O cost of the Ladybug restart: about 1.13 seconds more than the paired control's wall time, versus about 0.33 seconds more native target time. Do not hide that overhead or compare the two clock definitions as if interchangeable.

## What changed relative to the failed in-place switch

Both Ladybug restarts trigger at outer2 after the second rejection, as specified. The first endpoint is preserved, and stage2 reloads the original problem rather than continuing from the altered geometry. The paired stage succeeds twice and its endpoint is selected twice. No restart occurs in the four Dubrovnik/Venice candidate runs.

Ladybug median total rejection counts were 36 fixed-five, 0 paired, and 2 for the restart pipeline, including the abandoned prefix. Median total matrix-vector counts were 2797.5, 1209.5, and 1369.5 respectively. The previous in-place switch reduced retries but continued with a trajectory that did not meet the target. This restart experiment supports the importance of the opening path; it does not prove a basin theorem or guarantee the same trigger generalizes.

## Validation and artifacts

18 pipelines used 20 solver stages, consuming **56.274 native solver seconds** and **71.649 seconds summed process wall**. All 20 endpoint audits and per-stage monotonicity checks passed; maximum relative endpoint discrepancy 7.09e-12. Initial objectives were checked against the same original input in both stages. Both restart triggers were checked against the exact first eligible rejected attempt, with no in-place switch event allowed. Both second-stage budgets and cumulative crossing times were independently verified, and all retained best-state files were checked against the lower-cost audited endpoint's hash. In these successful runs the fallback to stage1 was not needed.

The full combined internal trace intentionally resets to the original higher-cost state at stage2; only individual stages are monotone. The reported final state is selected from both endpoints, so the first valid endpoint is not discarded if the second stage fails to improve it. A production implementation would need equivalent retained-state and deadline accounting.

CUDA CLI and core library built; new binary markers were verified before freezing v7. The invalid restart-mode guard, Python compilation, and changed-code whitespace checks passed. No new kernels or state-layout changes were introduced, and no sanitizer was run. Eleven old jobs remain paused. Nothing was pushed.

Artifacts: `/workspace/prism-early-restart/` contains the protocol, plan, frozen binary/source, stage logs/manifests/CSV/JSONL/states, selected `.best.state` files, results, summary, guard test, provenance, and completion. Solver support is in `gpu/oca_cuda.cu`; orchestration and independent auditing are in `bench/early_restart_screen.py`.

## Current winner and next step

On a per-scene basis: **paired from the start wins Ladybug; fixed-five behavior remains preferable on Dubrovnik and Venice.** The early-restart policy is now a credible unified candidate for these three cases because it succeeds on all six target runs without scene-name selection. Paired from the start also succeeds on all six, but is slower on Dubrovnik in this comparison.

Do not change defaults yet: the trigger was developed using these scenes. Freeze this exact rule and test it on additional original-input scenes before optimizing away the process boundary. If it generalizes, an in-process restart may reduce reload/export overhead, but its full state reset and retained-best behavior must be validated rather than assumed.
