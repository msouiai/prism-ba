# Camera/point error decomposition and split damping — 2026-09-08

**Separate, standalone-descent-gated damping is a promising compromise on the two contrasting development scenes.** The optimized split policy reaches both quality targets in both repeats: Dubrovnik356 in 1.61s and Venice52 in 2.84s. Fixed single with point repair remains faster on Dubrovnik but misses Venice; frozen paired point repair is faster on Venice but misses Dubrovnik. This is a small development result, not proof of a universal best policy.

## Diagnostic finding

Four short instrumented runs captured 12 actual accepted repaired steps: first, second and fourth repair calls from Dubrovnik356 and Venice52, each under frozen and jointly relaxing paired damping. Each capture contains the exact state, selected direction (including its point mask), five projected GN coefficients, camera-only and point-only true costs, combined accepted cost, and the current damping pair.

| Signature over six captured steps per scene | Dubrovnik356 | Venice52 |
|---|---:|---:|
| Camera-only positive predicted decrease | 0/6 | 1/6 |
| Point-only positive predicted decrease | 6/6 | 3/6 |
| Camera-only eligible for relaxation | 0/6 | 1/6 |
| Point-only eligible for relaxation | 6/6 | 2/6 |
| Model cancellation factor range | 1.46–2.13 | 1.00–223.65 |

For Dubrovnik, the isolated point step decreases true cost with rho 0.933–0.994 across all six captures. Its isolated camera step predicts an increase. On Venice's first repaired step, **neither isolated block predicts descent**; their combination is essential. Camera–point interaction and cancellation explain why treating a good combined ratio as permission to relax both components is questionable.

The decomposition is exact at the sampled endpoints:

    E_camera = F10 - F00 - q10
    E_point = F01 - F00 - q01
    E_interaction = F11 - F10 - F01 + F00 - cp
    E_total = E_camera + E_point + E_interaction.

Here q is the projected GN change and cp its mixed coefficient. Conditional block ratios, holding the other proposed block in place, remain near one for many steps in both scenes and do not provide a useful discriminator by themselves. They both contain interaction error, so that error cannot be assigned uniquely to either damping variable. See [the derivation and limitations](repair_block_error_math.md).

## Tested policy

After the combined repaired step has been chosen for acceptance, evaluate the isolated camera and point trials. Halve a component's retained damping only if that isolated trial:

1. actually decreases the current true objective;
2. has a positive, numerically resolved GN predicted decrease;
3. achieves rho>0.75, outside the existing rounding band.

Otherwise retain that component. There are no upward updates. The isolated trials are never committed; combined-step acceptance is unchanged. This is a conservative eligibility rule, **not** an assertion that the interaction error belongs to one block or that lowering damping must improve the next step.

Implementation: `OCA_REPAIR_SPLIT=1` with `OCA_REPAIR_DAMPING=1`, paired demand and point safeguard1. The combined model remains audit-only while the separate decisions control the pair. Both flags are off by default.

On Dubrovnik, each tested split rollout relaxes point damping six times and never relaxes camera damping through this repair-specific rule. Ordinary unrescued acceptances retain their existing behavior. On Venice, the optimized runs relax both components only once through the new rule, retaining damping at the first strongly coupled repair. This differs from the previous joint controller's four successive halvings.

## Short time-to-quality results

Targets: Dubrovnik356 cost 754100/cap8s; Venice52 cost 252000/cap4s. Two repeats per cell; initial matched screen reverses scene and arm order in the second repeat. All baselines include point safeguard1.

| Configuration | Dubrovnik356 | Venice52 |
|---|---:|---:|
| Fixed single + point repair | **1.259s**, 2/2 | Miss, 0/2 |
| Paired + point repair, frozen pair | Miss, 0/2 | **2.685s**, 2/2 |
| Split policy, initial implementation | 1.724s, 2/2 | 3.179s, 2/2 |
| **Split policy, reused model** | **1.608s**, 2/2 | **2.840s**, 2/2 |

The optimized candidate was run in a separate four-run N2 follow-up; the displayed baseline timings are retained from the immediately preceding matched v2 screen, not fresh v3 baseline reruns. Per-run evidence is retained. Its Dubrovnik crossings are 1.648s and 1.568s; Venice crossings are 3.016s and 2.665s. These variations limit how precisely small timing differences can be interpreted.

The optimized policy is about 28% slower than fixed single on Dubrovnik and about 6% slower than frozen paired on Venice, while reaching both targets. The first implementation already reached both targets twice, so the consistency result does not depend on the later optimization. The previous [joint-feedback experiment](repair_damping_results.md) missed one Venice repeat; that comparison is historical and is not a new matched joint-policy run.

Both scenes informed the hypothesis through their captured states. These are **development scenes**, not held-out generalization evidence. No large-scene run was launched and no solver default was changed.

## Removing duplicate model work

The split decision already computes gc,gp,cc,cp,pp. The combined prediction can reuse

    slope = gc + gp
    curvature = cc + 2*cp + pp
    prediction = -slope - 0.5*curvature.

This removes the separate direct-model kernel and its 16-byte allocation on the split path, leaving the 40-byte coefficient reduction. The twelve saved predictions agree with the separate direct computation to 9.84e-14 relative. True-cost probes, masks, damping thresholds and per-block decisions remain unchanged.

Dubrovnik prediction/diagnostic overhead falls from 0.298s to 0.158s. Native target time falls from 1.724s to 1.608s in the follow-up. Venice's larger elapsed-time variation cannot be attributed solely to this small kernel saving: its trajectory and matvec count also vary.

| Optimized split work, median | Dubrovnik356 | Venice52 |
|---|---:|---:|
| Matvecs | 139 | 2195 |
| Backtracking candidate scores | 40 | 18 |
| Additional isolated-block scores | 26 | 11 |
| Split model/diagnostic time | 0.158s | 0.019s |
| Point safeguard time | 0.111s | 0.016s |

The extra block scores are **not** included in the legacy `scored` counter. Including them, total nonlinear scores are 169 and 579.5 respectively. Native runtimes include all of this work. Outer rejected iterations are zero in the matched screen: the method changes progress per accepted iteration and the amount of backtracking, not a previously nonzero outer rejection count.

## Validation and budget

- 20 short solves total: four instrumented capture runs, twelve matched screen runs, four optimized candidate runs. Total native solver time **58.951132s**, including capture instrumentation/I/O; those capture times are not performance comparisons.
- All 20 returned states pass the independent CPU raw-objective audit; maximum relative discrepancy3.51e-15. Accepted cost traces are monotonic.
- 48 independent CPU captured-cost checks pass, maximum relative discrepancy5.30e-14. Sixty projected coefficient checks have maximum normalized error 4.98e-12.
- All 74 split decision records and damping updates pass independent arithmetic checks. Seventy following-iteration records confirm the actual new lambda/tau pair was consumed; terminal records have no next attempt to inspect.
- The existing decision helper and numerical kernels are reused. CLI and embedding core compile. Capture requires a valid repair mode; split feedback requires combined audit mode. Both runtime guards pass. Python analysis scripts compile.
- Existing point/model finite-difference and memory-check evidence is documented in the preceding reports; this turn does not claim a newly run memory-sanitizer gate.

The next useful check is a short scene not used to derive this rule, before promoting it or expanding to large problems. The current result supports the mechanism on these two conflicting scenes while preserving the strongest per-scene baselines.

## Files and reproduction

Artifacts: `/workspace/prism-block-error/`. `prism-v1` freezes the capture implementation; `prism-v2` the first split implementation; `prism-v3` the reused-model implementation. Matching source snapshots, all plans, manifests, data/binary hashes, original logs, exported states and split-update audits are retained.

```bash
python3 bench/backtrack_investigation.py /workspace/prism-block-error/capture-plan.json
python3 bench/measure_repair_blocks.py
python3 bench/backtrack_investigation.py /workspace/prism-block-error/screen-plan.json
python3 bench/backtrack_investigation.py /workspace/prism-block-error/repeat-plan.json
python3 bench/backtrack_investigation.py /workspace/prism-block-error/optimized-plan.json
python3 bench/summarize_repair_blocks.py
```

Completed runs are skipped; incomplete logs and exclusive capture files are preserved. Use a new root in saved plans for a fresh study. Source is in `gpu/repair_block_capture.cuh`, integration in `gpu/oca_cuda.cu`, the reused helper `gpu/repair_damping.h`, and the measurement/summarization scripts above. No push was performed. The11 paused jobs remain paused.
