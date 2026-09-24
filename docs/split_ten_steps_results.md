# Ten-step split-damping follow-up

2026-09-08. **Current winner on the new repair-active scene is single shift + point repair.** Split beats frozen paired at the tighter target in one run, but does not beat single. Across the broader recent studies there is no universal winner: frozen paired won Ladybug1197 and Trafalgar126; single won Dubrovnik173 and Dubrovnik356; frozen paired was fastest on Venice52. Those separate studies are not one pooled controlled benchmark.

## Ten completed steps

1. Verified current source against frozen v3 and kept all arms on that binary.
2. Saved the baseline-only selection protocol before pilots.
3. Ran short frozen-paired pilots on Dubrovnik173, Venice89, and Final93: 14, 0, and 0 point-repair calls respectively.
4. Selected only Dubrovnik173, the sole repair-active pilot. Froze target at pilot CPU cost times 1.001 = 376109.651356, cap 4 seconds.
5. Ran single, frozen paired, and split, all with point repair, first repeat.
6. Repeated in reverse arm order.
7. Independently audited split decisions and following damping pairs.
8. Accounted for matrix-vector products, backtracking, and extra block probes; checked a mathematical probe-elision opportunity offline.
9. Ran all three arms once at the predeclared tighter target, pilot cost times 0.999 = 375358.183521, cap 6 seconds.
10. Saved provenance and published this winner ledger. No solver or default changes.

## Equal-quality results

| Target on Dubrovnik173 | Single + point repair | Frozen paired + point repair | Split + point repair | Winner |
|---|---:|---:|---:|---|
| 376109.651356, median of two | 1.250 s (2/2) | 1.770 s (2/2) | 1.901 s (2/2) | Single |
| 375358.183521, one run | 2.342 s (1/1) | 4.863 s (1/1) | 2.929 s (1/1) | Single |

All times are native first-target-crossing times with independently CPU-audited final states. Every comparison run hit its target. Pilot caps were 2 seconds or 40 iterations; caps can be exceeded by an in-progress iteration. Targets were selected using frozen baseline endpoints, not candidate results; this makes the screen targeted rather than a representative benchmark.

At the first target, split takes 7.4% longer than frozen paired and 52.2% longer than single. At the tighter target, split is 1.66 times as fast as frozen paired (39.8% less time), but takes 25.1% longer than single. The tighter result has only one repeat and is provisional. The appropriate next step is to repeat that comparison before calling the late-progress benefit reliable.

## What actually changed

Split lowered point damping once in each of its three runs, and never lowered camera damping. Unlike the preceding Ladybug/Trafalgar screen, this exercises an active decision outside the two development scenes. It does not show that all accepted repair steps should relax damping.

At the first target, median matrix-vector counts were 482 single, 679.5 frozen, and 659 split. Median backtracking evaluations were 17, 21, and 30. Every comparison run had zero outer rejections. Split's modest reduction in matrix-vector work against frozen was offset by more backtracking and additional work: median model/probe time 0.0866 seconds, plus point-repair time 0.0636 seconds. The model/probe component alone is about 4.6% of its crossing time and cannot explain the entire gap to single.

Legacy scoring counts exclude two isolated block cost probes per split call. Add 56 probes across the two initial split runs; the tighter split run adds 40.

## Mathematical optimization opportunity

For either block, the unchanged rule requires finite model values, negative slope g, nonnegative curvature h, and predicted reduction P = -g - h/2 above its numerical floor before it can reduce damping. If any model-only prerequisite fails, no actual trial cost can change the decision: the factor must be 1. Therefore an implementation can skip that block's retraction and nonlinear cost evaluation after checking these prerequisites, while preserving the mathematical damping decision. This does not imply bitwise-identical GPU trajectories or an end-to-end speedup.

Offline checks found 50 of 56 block probes in the two-repeat screen ineligible on model-only grounds; all 50 actually returned factor 1. This is 89.3% of these probes, **not 89.3% of solver runtime**. The existing model/probe time is only 0.0866 seconds per solve, and model evaluation itself would remain. No code change or claimed runtime saving has been made in this round.

## Validation and scope

Twelve total solves including pilots consumed 26.297 native solver seconds. Every CPU endpoint audit and monotonic-cost check passed; maximum relative discrepancy 3.11e-15. Recomputed 48 split decisions and verified 45 available following-iteration damping pairs. Binary, data, and state hashes are recorded. Eleven old jobs remain paused. No new Caspar run, large-scene run, push, or default change occurred.

Artifacts: `/workspace/prism-split-ten/`, including frozen plans, selection, per-run manifests/logs/traces/states/results, screen summary, all-split-audits, probe-eligibility, provenance, and completion. `steps.json` records the original ten-step plan.

## Verdict and next action

Single + point repair is the new scene's winner at both quality levels. Frozen paired remains the winner of the preceding additional-scene screen. Split remains experimental: its active point-damping change is promising for tighter-target progress against frozen paired, but it is not the fastest overall. Next, repeat the tighter comparison and then implement model-gated probe skipping with decision-equivalence checks. Keep reporting per-scene winners rather than promoting a post-hoc best-of-scenes configuration as one universal solver.
