# Unchanged restart rule: three additional original-input scenes

2026-09-08. **The frozen rule reached all six additional targets, without firing a restart.** Fixed-five behavior leads on Venice89 and Final93; Ladybug598 has small timing differences rather than a convincing winner. This is a useful check for unnecessary triggering, but not evidence for active restart recovery on another scene.

## Protocol

Unchanged v7 binary and early-restart rule. Original Ladybug598, Venice89, and Final93 inputs; original profile, coupling, default initial damping, and point safeguard1. These scenes were not used to derive the early-rejection trigger, although they appeared in earlier project experiments. They are additional validation cases, not a pristine blind benchmark.

Targets were fixed before new results: Ladybug598 cost180000, cap4 seconds; Venice89 cost307500, cap3 seconds; Final93 cost158400, cap3 seconds. Ladybug's target lay between historical single-shift and fixed-multi endpoints; Venice/Final targets came from earlier short baseline results. Two repeats per arm, reverse scene/arm order on repeat2. Native accounting, total process-wall reporting, endpoint retention, and CPU auditing use the unchanged early-restart harness.

## Time to equal quality

| Scene | Fixed-five + repair | Paired + repair | Restart rule | Practical winner |
|---|---:|---:|---:|---|
| Ladybug598 | 0.990 s | 0.953 s | 0.907 s, inactive | No clear winner |
| Venice89 | 1.476 s | 1.766 s | 1.474 s, inactive | Fixed-five behavior |
| Final93 | 0.423 s | 0.593 s | 0.422 s, inactive | Fixed-five behavior |

All entries reached their target in both repeats. Times are median native first-target crossings with independently CPU-audited endpoints. There were zero rejected attempts in all 18 runs, and no restart requests. The restart arm therefore followed its initial fixed-five path throughout.

The small Ladybug timing differences do not establish a benefit from an inactive restart policy. Its fixed-five control varied from 0.898 to 1.081 seconds, while the restart arm took 0.930 and 0.885 seconds. Both represent successful fixed-five trajectories. Paired took 0.947 and 0.959 seconds.

Using the direct fixed-five control rather than attributing inactive-policy timings to a restart benefit, fixed-five was **1.20x as fast as paired on Venice89** (16.4% less native time), and **1.40x on Final93** (28.7% less time). Matrix-vector counts support that comparison: Venice 730 versus780, Final370 versus445, with additional scoring/trajectory effects not isolated by those counts.

## Wall-time accounting

Median total process wall through returned/exported endpoints:

| Scene | Fixed-five | Paired | Restart rule, inactive |
|---|---:|---:|---:|
| Ladybug598 | 1.665 s | 1.569 s | 1.515 s |
| Venice89 | 2.297 s | 2.558 s | 2.272 s |
| Final93 | 1.059 s | 1.219 s | 1.065 s |

This includes launches, input loading, exports, and harness bookkeeping; independent CPU audits are performed afterward. Native caps do not impose a strict process-wall deadline. No second-stage launch occurred, so this round does not remeasure active restart overhead.

## Validation and artifacts

18 pipelines/stages consumed **18.188 native solver seconds**, with **30.440 seconds summed process wall**. All endpoint audits and per-stage monotonicity/initial-objective checks passed; maximum relative endpoint discrepancy 6.35e-14. Binary, data, and selected-state hashes were verified, as were absence of restart requests and the unchanged source. Eleven older jobs remain paused. No solver code/default change, large-scene test, Caspar run, or push occurred.

Artifacts: `/workspace/prism-restart-validation/` contains the frozen protocol and plan, per-run logs/manifests/CSV/JSONL/states and selected endpoints, results, summary, provenance, and completion. All runs used `/workspace/prism-early-restart/prism-v7` and `bench/early_restart_screen.py` without modification.

## Current verdict

Across the development and additional-scene rounds, the restart candidate has reached **12/12 targets across six scenes**, but only Ladybug1197 actually restarted (two runs). Paired from the start also reached all those targets; the restart candidate's appeal is retaining faster fixed-five behavior on several other scenes. Do not confuse combined descriptive coverage with held-out evidence of active recovery or a universal speedup.

Current per-scene ledger: paired from the start wins Ladybug1197; fixed-five behavior is preferred on Dubrovnik173, Venice52, Venice89, and Final93; Ladybug598 is approximately tied. No new Caspar conclusion follows.

Next, locate another scene with an early rejection streak using a small baseline-only screen, then apply this exact frozen restart rule without changing its threshold. That will test the unresolved question: whether active recovery works outside Ladybug1197. Keep defaults unchanged until that evidence exists; a no-trigger screen alone is not sufficient justification for promotion.
