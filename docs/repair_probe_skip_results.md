# Ten steps: model-gated repair probes

2026-09-08. **Single shift + point repair remains the current winner on the main Dubrovnik173 test.** Model-gated probe skipping is implemented and validated, but the short screen does not demonstrate an end-to-end speed benefit. It remains opt-in and off by default.

## Completed steps

1. Froze protocol, original source copies, targets, and v3 baseline binary.
2. Repeated the tighter Dubrovnik173 comparison twice with v3.
3. Implemented `OCA_REPAIR_SKIP_PROBES=1`, requiring split repair.
4. Tested decision equivalence on 362235 host cases including nonfinite inputs, overflow-scale values, random cases, and adjacent values at the prediction floor.
5. Built and froze `/workspace/prism-probe-skip/prism-v4` for all new comparison arms.
6. Compared single, frozen paired, full-probe split, and skipped-probe split twice with reversed order on repeat 2.
7. Checked the original Dubrovnik356 and Venice52 development targets with full and skipped probes once each.
8. Audited CPU endpoints, actual split decisions, following damping pairs, and evaluated/skipped probe records.
9. Measured model/probe work and target times; inspected the development trajectory differences.
10. Saved provenance, updated the winner ledger, and retained unchanged defaults.

## Current winner and performance

All arms below include point safeguard mode 1. Dubrovnik173 target 375358.1835212728, cap 6 seconds. Times are medians of two native first-target crossings; exported endpoints are independently CPU-audited. Every run reached its target.

| Phase | Single + repair | Frozen paired | Full-probe split | Skipped-probe split | Winner |
|---|---:|---:|---:|---:|---|
| Original v3 repeat | 2.364 s | 4.720 s | 3.869 s | — | Single |
| Same v4 binary, all arms | 2.358 s | 3.737 s | 4.252 s | 4.319 s | Single |

The earlier single-run split advantage is not stable: v3 split repeats took 2.945 and 4.794 seconds; v4 frozen paired took 2.611 and 4.864 seconds. Single was much more consistent across these four fresh runs, 2.351–2.371 seconds. In the matched v4 screen, single was 1.83 times as fast as skipped-probe split.

Skipping reduced median model/probe time from 191.6 to 170.6 ms, about 11%, but median end-to-end time increased by 1.6%. This small timing regression is not a decisive failure; it simply does not establish a speedup. Matrix-vector counts also differed (1632.5 full versus 1681 skipped). Both split arms lowered point damping once per run and never lowered camera damping.

Across recent studies, there is still no universal configuration winner: frozen paired won the Ladybug1197/Trafalgar126 screen, while single + repair won Dubrovnik173. These are per-scene observations, not evidence for an implementable oracle that selects the best configuration after running them all. No new Caspar comparison was performed.

## Development checks, one run per arm

| Scene and target | Full probes | Skipped probes | Winner among these two |
|---|---:|---:|---|
| Dubrovnik356, 754100, cap 8 s | 1.617 s | 1.554 s | Skipped probes |
| Venice52, 252000, cap 4 s | 2.810 s | 3.943 s | Full probes |

Both targets were reached in every run. Dubrovnik356 had 139 matrix-vector products and 40 backtracking evaluations in both arms, six point-damping reductions, and no cost-trajectory difference above 1e-10 relative. It removed 18 of 26 probes; model/probe time fell from 161.3 to 145.0 ms. The 3.9% end-to-end improvement is encouraging but only one pair.

Venice52 trajectories diverged above 1e-10 relative at iteration 14, before either run's first split probe at outer 18. Their current costs already differed by about 2.63 at that first probe. Thus this comparison cannot isolate probe skipping as the cause of the slowdown. Skipped-probe Venice needed more solver work (3193 versus 2171 matrix-vector products) and more repair calls (9 versus 5). This is a material variability limitation, not grounds to claim equivalence of complete GPU trajectories.

## Implementation and mathematical guarantee

`PrismRepairDamping::ModelEligible` checks only the prerequisites already required by `Decide`: finite current cost, slope, curvature and prediction; slope below zero; curvature at least zero; and P = -g - h/2 above 64 epsilon max(1,current).

If one fails, `Decide` must return factor 1 for every possible trial cost. The optional optimization therefore skips that block's retraction and cost evaluation. Eligible blocks retain the original true-cost test. The accepted combined step and its nonlinear acceptance rule remain unchanged. No new kernels or buffers were added.

An unmeasured block cost is logged as the current cost sentinel, explicitly marked by `REPAIR_PROBES camera_evaluated=0` or `point_evaluated=0`; it must not be interpreted as a measured unchanged objective. `REPAIR_PROBES summary` records actual evaluated and skipped counts, parsed by the benchmark runner. Add actual evaluated probes to legacy `scored` counts, rather than assuming two per repair call when skipping is on. Separate debug capture probes are outside these controller counters and were disabled throughout this study.

On Dubrovnik173, skipping removed 114 of 124 possible block probes across the two new runs (91.9%). The model reduction still runs, so this is not a comparable reduction in runtime. Existing model/probe time was only about 4.5% of total split time; even eliminating that entire component could not close the large gap to single.

## Validation and artifacts

Eighteen benchmark solves consumed 61.375 native solver seconds. All endpoints and monotonic-cost checks passed, maximum CPU relative discrepancy 2.64e-15. Independently checked 218 split records, 210 following-iteration damping pairs, and 328 block probe decisions. Host gate checks passed; CUDA CLI and core library built; Python compilation and changed-code whitespace checks passed. The core smoke test passed on Venice52 with a one-second cap, separately from the 18 audited benchmark solves. An initial smoke-test invocation omitted its required BAL argument and failed; the corrected invocation passed. No sanitizer was run: the change branches around existing operations, and introduces no kernel or memory-layout changes.

Artifacts are under `/workspace/prism-probe-skip/`: frozen plans, protocol, binaries/source copies, manifests, logs, CSV/JSONL traces, exported states, `host-tests.log`, corrected core smoke log, `summary.json`, `all-audits.json`, `trajectory-diagnostic.json`, provenance, and completion. Eleven previous jobs remain paused. Nothing was pushed.

Code: `gpu/repair_damping.h`, `gpu/oca_cuda.cu`, `gpu/test_repair_probe_gate.cc`, and `bench/backtrack_investigation.py`. Reproduce the host test with `g++ -O2 -std=c++17 gpu/test_repair_probe_gate.cc -o /tmp/test_repair_probe_gate` then run that binary. Solver use requires `OCA_REPAIR_DAMPING=1 OCA_REPAIR_SPLIT=1 OCA_REPAIR_SKIP_PROBES=1` alongside the paired profile and its existing compatibility requirements.

## Verdict

Retain the mathematically safe probe optimization as an experimental option; do not promote it as a measured general speedup. Single + point repair is the current main-scene winner. The next substantial opportunity is reducing the additional Krylov and backtracking work in paired mode, which dominates the tens of milliseconds saved here. First capture an identical repaired state and compare the proposed next damping choices from that state, so controller effects can be separated from divergent trajectories before more end-to-end runs.
