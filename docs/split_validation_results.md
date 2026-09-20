# Unchanged split damping: additional-scene validation

2026-09-08. The unchanged optimized split policy reached all four targets, but never changed damping on either scene. This supports conservative behavior on these cases, not a new speed benefit. Keep it experimental and disabled by default.

## Protocol

Two repeats each of fixed single shift, frozen paired controller, and split controller. All three use point safeguard mode 1 and the identical `/workspace/prism-block-error/prism-v3` binary. Reverse both scene and arm order on repeat 2. Existing Ladybug1197 target: 366600, 6-second cap. Trafalgar126 target: 104100, 3-second cap, fixed before these runs using earlier 3-second endpoints near 104078 and 104054. These scenes did not inform the split rule, although they have been used elsewhere in this project.

Times below are median native time to first cross the shared target, with independently CPU-validated exported endpoints. A cap miss has no finite target time. Two repeats are descriptive and do not establish statistical significance.

| Scene | Single + point repair | Frozen paired + point repair | Split + point repair |
|---|---:|---:|---:|
| Ladybug1197 | 3.386 s (2/2) | 2.542 s (2/2) | 2.662 s (2/2) |
| Trafalgar126 | Miss (0/2) | 1.857 s (2/2) | 2.169 s (2/2) |

Split was 4.7% slower than frozen paired on Ladybug and 16.8% slower on Trafalgar. Ladybug's small difference is not a reason to discard the approach. Trafalgar's difference cannot be attributed to active split decisions or probe overhead: neither occurred. Its split-arm median matrix-vector count was 4419 versus 3703.5 for frozen paired, so the trajectories differed; these two repeats cannot establish why. GPU reduction/trajectory variability is a plausible explanation, not a demonstrated cause. Single-shift Ladybug times also varied from 3.074 to 3.697 seconds.

## What the rule did

Ladybug produced 12 split calls across both repeats. Every isolated camera and point proposal had nonpositive predicted reduction and failed to decrease the actual objective. The gate correctly left both damping values unchanged in all 12 cases. Median model/probe time was 0.0334 seconds per solve. Trafalgar had no backtracking repairs and therefore no split calls.

All runs had zero outer rejections. Ladybug median backtracking evaluations were 6 single, 23 frozen paired, and 15 split; differing trajectories and no damping changes prevent assigning the latter difference to the new rule. Trafalgar had zero backtracking evaluations in every arm. Legacy scoring counts omit the split rule's two isolated block cost probes per call: add 24 evaluations across the Ladybug split runs.

## Validation and artifacts

12 solves consumed 31.418 native solver seconds. All CPU endpoint audits and monotonic-cost checks passed; maximum relative endpoint discrepancy was 5.42e-12. Independently recomputed all 12 split decisions and checked 11 available following-iteration damping pairs. Binary/data hashes and exported-state hashes are retained. The 11 previously paused jobs remain paused. No solver code, defaults, or Caspar implementation changed, and no new Caspar comparison was run.

Artifacts: `/workspace/prism-split-validation/` contains the frozen `plan.json`, `PROTOCOL.md`, per-run manifests/logs/traces/states/results, `summarize.py`, `split-audits.json`, `summary.json`, `provenance.json`, and `completion.json`.

## Decision

Retain split damping as an experimental candidate: it still solves both original development counterexamples, and this additional screen found no target failures. Frozen paired remains faster here. Before spending time on a large run, select a short additional case with actual repaired steps, using baseline traces only, then test the unchanged rule. We need evidence that its independent damping changes help outside the development scenes; an inactive-rule run cannot supply that evidence.
