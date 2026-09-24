# Second ten steps: upward recovery and line-search attribution

**Neither upward-recovery variant is a general improvement. The simpler guarded line search also has strong controller-dependent regressions. Leave all experimental policies off by default.** The earlier Dubrovnik gain was relative to the paired-demand controller; it did not beat the fixed five-shift baseline at the same target.

This follow-up completes steps 11–20 after [the first ten-step investigation](backtrack_schedule_results.md). It contains 26 short runs, 130.936 seconds of native solve time, 21/25 target hits, and 26 independent CPU objective audits. The other run is diagnostic. Maximum CPU/GPU objective discrepancy is `6.79e-12`. No additional large run was launched: the recorded smaller-scene gate failed. The previous Final-4585 target miss remains part of the verdict.

## Controlled attribution: the most informative result

One run per cell, same frozen binary, full FP64 objective. Here **paired demand is disabled in every cell**. The factors are shift count (1 or 5) and line search (original halving or mode-3 guarded interpolation). All other solver flags match. This controls the changes within each pair but is not enough repetition for a precise statistical speed estimate.

| Scene / target / cap | Single, original | Single, guarded | Five shifts, original | Five shifts, guarded |
|---|---:|---:|---:|---:|
| Ladybug-1197 / 366,600 / 6 s | 4.203 s | 2.856 s | Miss | Miss |
| Dubrovnik-356 / 754,100 / 8 s | 4.807 s | Miss | **1.668 s** | 2.736 s |

Times are first accepted target crossings, not solver-return times. Misses are not assigned speedup ratios. Their CPU-audited endpoints and native return times are:

- Ladybug five shifts, original: 366,957.79 at 6.112 s.
- Ladybug five shifts, guarded: 368,744.74 at 6.151 s.
- Dubrovnik single, guarded: 1,065,730.06 at 8.022 s.

The guarded line search made fixed five-shift Dubrovnik **64% slower** to this target in this run. The unchanged fixed five-shift baseline was also faster than the earlier paired-demand-plus-guard result (~2.615 s). Therefore the earlier **2.63×** claim is valid only for its explicitly matched paired-demand baseline; it is not a best-known-solver speedup or proof of multishift novelty.

On Ladybug with five shifts, guarded interpolation reduced rejected attempts **44→10** and backtracking probes **347→110**, yet both arms missed the target and guarded finished worse. It also increased matvecs **2,875→3,101**. Reducing rejection count alone is not the right objective. The `rejects` counter includes rejected inner attempts, not just distinct outer iterations.

## Accepted-step recovery experiment

Mode 4 extends mode 3: after an interpolated step succeeds, try the next larger dyadic scale. Keep it only if it is Armijo-valid and has lower full cost. Stop at failure, worse cost, an already tested neighbor, or the original eight-probe budget. A previous successful full step remains saved while probing. This introduces no GPU state buffer or matvec.

The always-upward screen used paired-demand mode 2, one run per cell:

| Scene | Original halving | Guarded (mode 3) | Upward (mode 4) |
|---|---:|---:|---:|
| Ladybug-1197 | 2.779 s | 2.883 s | 2.850 s |
| Dubrovnik-356 | 6.891 s | 2.623 s | **8.551 s** |
| Venice-52 | 3.071 s | 2.995 s | 2.705 s |

All used the existing targets 366,600 / 754,100 / 252,000 and hit within their caps. On Dubrovnik, 239 upward probes found 116 immediate objective improvements, but the solve needed 109 accepted iterations and 1,187 matvecs, versus 32 and 388 with mode 3. Greedily improving each accepted step did not preserve the better subsequent trajectory. This is evidence against the proposed universal repair, not proof that a specific local minimum or geometric mechanism caused the regression.

One recorded revision was permitted before further runs. Mode 5 only probes upward while progress is weak according to the **existing** demand-menu criterion, `relative_gain < max(10*ftol, 0.25*previous_gain)`. No new threshold was fitted. Its new same-binary screen was:

| Scene | Original halving | Weak-progress upward (mode 5) |
|---|---:|---:|
| Ladybug-1197 | 2.718 s | 2.801 s |
| Dubrovnik-356 | 6.896 s | 6.917 s |
| Venice-52 | 2.376 s | 3.534 s |

Every target hit, but the variant failed the pre-recorded large-run gate (all hits, no >10% regression, and >10% Dubrovnik improvement). Accordingly **no new Final-4585 run** was performed and no additional policy revision was tried.

## Harder quality checkpoint

Retaining mode 3 only for further diagnosis, paired-demand mode 2 was tested on the older, harder Dubrovnik target **723,500**, with a 16-second cap:

| Policy | Result | Final CPU cost | Native return |
|---|---|---:|---:|
| Original halving | Miss | 751,399.39 | 16.016 s |
| Guarded interpolation | Hit at **15.033 s** | **722,579.57** | 15.043 s |

This is one run per arm. It shows a useful deeper-quality benefit for this controller/scene, beyond the early 754,100 crossing. It does not establish an equal-quality speed ratio, because baseline never reached the harder target within the cap. It also does not reverse the prior large-scene failure or the fixed-menu ablation above.

## Steps and validation

11. Audited the prior large trajectories: first material cost divergence at iteration eight; the guarded run subsequently made less progress. Matching iteration numbers after that point do not identify matching linear systems.
12. Implemented the bounded upward check (mode 4), saving the earlier winner across additional trials.
13. Extended host tests across menu lengths 1–12, every starting index and modes 0–5; verified unique coverage and upward stopping at visited boundaries. AddressSanitizer and UBSan pass.
14. Ran the nine-cell original/guarded/upward screen on the three scenes above.
15. Recorded and tested the one weak-progress revision (mode 5) in six cells; it also failed the selection gate.
16. Skipped a new large run and used a short, traced Dubrovnik rollout to inspect the recovery behavior. Its 19 searches used 73 probes: 27 upward probes, 11 improvements, and 16 failed/worse upward probes where the earlier winner was retained. Parsed trace counts match solver counters, every scale is unique within a search, and no search exceeds eight probes. The exported endpoint passes its CPU audit. The trace run is excluded from timing comparisons.
17. Ran the harder paired-demand quality checkpoint, retaining the target miss.
18. Ran the eight-cell shift-count × line-search ablation with paired demand disabled.
19. Verified all exported objectives, monotonic accepted-cost traces, probe/rescue limits and frozen-source provenance; built CLI and core library; checked paused jobs by PID and start tick.
20. Recorded this report, raw artifacts and the decision. Defaults remain unchanged; broad benchmark jobs stay paused.

All native clocks include solver initialization and exclude state export/CPU audit; the summarizer also retains solver-return time, so first-crossing and cleanup costs are not conflated. Budget checks occur at solver boundaries and can overrun slightly. Screens are single repeats and the scenes were used during development. Do not select the best cell per scene and present it as one fixed configuration.

## Code and reproduction

- `gpu/backtrack_schedule.h`: finite-menu scheduling and upward-boundary check.
- `gpu/oca_cuda.cu`: full-cost winner retention and modes 4/5 integration; default remains mode 0.
- `bench/test_backtrack_schedule.cc`: host numerical/policy tests.
- `bench/backtrack_investigation.py PLAN.json`: run a retained manifest-driven stage.
- `bench/summarize_backtrack_followup.py /workspace/prism-backtrack-upward`: rebuild the summary.

`OCA_BACKTRACK_POLICY`: 0 original, 1 history, 2 unguarded quadratic, 3 guarded quadratic, 4 always upward after success, 5 upward only during weak progress. These are research switches, not recommended defaults. No Krylov reuse or bounded-cost screening was enabled.

Artifacts are under `/workspace/prism-backtrack-upward/`: before/after sources, two frozen binaries, protocols, revision/selection decisions, stage plans, raw logs/CSV/states/result JSON, trace analysis, build/test logs and summary. Earlier results remain separately frozen under `/workspace/prism-backtrack-ten/`. No new Caspar comparison or publication claim is made.

## Next recommendation

Stop adding more scale-search heuristics to this sequence. The evidence points to interactions with damping/controller trajectories, rather than a missing universally good backtracking order. A bounded next study should test **point-damping feedback from repeated small-step rescues**, keeping camera damping separate and rebuilding the changed point factors/operator correctly. That is a hypothesis, not an established fix. Give any resulting policy to both single- and five-shift baselines at equal quality before crediting a gain to multishift selection.
