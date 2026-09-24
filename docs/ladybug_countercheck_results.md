# Ladybug1197 counterexample recheck

2026-09-08. **Frozen paired + point repair remains the winner on Ladybug1197.** Fixed-five still misses the established target in both repeats. Keep defaults unchanged; the recent Dubrovnik/Venice wins do not establish a universal fixed-five winner.

Original input, target 366600, native cap 6 seconds, same frozen v4 binary, original COMMON profile/default starting damping, point safeguard mode 1 for both arms, repair feedback and split disabled. Two repeats with reversed arm order.

| Configuration | Target hits | Median time to target | Median final CPU cost | Median native return time |
|---|---:|---:|---:|---:|
| Fixed-five + point repair | 0/2 | Not reached | 367006.80 | 6.099 s |
| Frozen paired + point repair | 2/2 | **2.440 s** | 366567.13 | 2.457 s |

Paired crossings were 2.585 and 2.295 seconds. Fixed-five's final cost is only about 0.111% above the shared target; this is a target-reliability failure, not catastrophic final-quality deterioration. No finite equal-quality speed ratio is available because fixed-five did not cross. An in-progress iteration explains return time slightly beyond the six-second cap.

The work traces are more revealing: fixed-five had median 32 outer rejections, 388.5 backtracking evaluations, 2797 matrix-vector products, and 1107 scored candidates. Paired had zero outer rejections, 25 backtracking evaluations, 1138.5 matrix-vector products, and 355 scored candidates. Comparisons count complete capped/target-stopped runs, so they have differing duration and progress; they are not matched-state causal measurements. Nevertheless, the rejection burden is a concrete signal to investigate for an adaptive controller.

All four endpoint audits and monotonic-cost checks passed; maximum CPU relative discrepancy 4.42e-12. Native solver time totaled 17.111 seconds. Binary, input, and exported-state hashes were checked; eleven old jobs remain paused. No source algorithm change, default change, extra scene, Caspar run, or push occurred.

Artifacts: `/workspace/prism-ladybug-countercheck/` contains the frozen protocol/plan, logs/manifests/CSV/JSONL/states/results, summary, provenance, and completion.

Current recent original-input winner ledger: **fixed-five + point repair on Dubrovnik173 and Venice52; frozen paired + point repair on Ladybug1197.** These are short, two-repeat scene-specific observations, not an oracle configuration or a new comparison against Caspar.

Next: inspect the onset of fixed-five's repeated rejection and test a bounded transition to paired mode after a prespecified sustained-rejection condition. Validate the trigger against the winning Dubrovnik/Venice traces before implementing it, so it does not discard fixed-five's beneficial behavior there. A scene-name switch or a retrospectively chosen best configuration would not establish an online selection method.
