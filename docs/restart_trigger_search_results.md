# Bounded search for another active early-restart case

2026-09-08. **No qualifying case was found in the four-scene screen.** This round does not add evidence for active restart recovery and does not change the winner ledger.

The frozen protocol used original Ladybug49, Dubrovnik135, Trafalgar257, and Final871 inputs, fixed-five + point repair, original profile, unchanged v7 binary, four outer iterations each, and a two-second native cap. A case qualified only if it had two consecutive rejected attempts at outer index0,1,2, matching the unchanged restart rule. Qualifying cases would have received a short matched comparison. The protocol specified stopping if none qualified.

| Scene | Completed outer iterations | Rejected attempts | Maximum rejection streak | Native solver time |
|---|---:|---:|---:|---:|
| Ladybug49 | 4 | 0 | 0 | 0.067 s |
| Dubrovnik135 | 4 | 0 | 0 | 0.400 s |
| Trafalgar257 | 4 | 0 | 0 | 0.292 s |
| Final871 | 4 | 0 | 0 | 1.156 s |

All four runs completed the entire early-trigger window. No candidate comparison was launched: it would have tested another inactive restart. The total was **1.915 native solver seconds** across 16 outer iterations; loading and CPU audits are additional. All CPU endpoint audits and monotonicity checks passed, and binary/data/state hashes were recorded. Exact audit errors are retained in `summary.json`.

These were baseline trigger probes without common-quality races. They do not establish fixed-five as the fastest configuration on these four scenes, nor do they prove that early restart is uniquely useful on Ladybug1197.

Current evidence remains: the restart candidate hit12/12 targets across six earlier scenes, with actual restarts only on Ladybug1197 (two runs). Paired from the start is still the Ladybug1197 winner; fixed-five behavior leads several other short tests. No universal winner or default change is justified.

Artifacts: `/workspace/prism-restart-active/` contains frozen protocol/plan, pilot logs/manifests/traces/states/results, exact trigger selection, summary, provenance, and completion. Eleven old jobs remain paused. No source change, trigger adjustment, large run, Caspar run, or push occurred.

The next economical action is to search existing baseline traces for an additional early-trigger case before scheduling more solves. Keep scene selection based on baseline behavior and keep the trigger frozen; do not weaken the rejection criterion just to manufacture another active example.
