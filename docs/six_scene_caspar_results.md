# Six additional scenes: PRISM versus Caspar FP64

Timing clarification from the [menu ablation audit](menu_caspar_ablation_results.md): this study’s PRISM harness enabled `OCA_LEARN_LOG`, which adds a blocking norm per scored candidate. These historical times include that instrumentation; they are not logging-free solver timings. The new ablation separates timing runs from diagnostic logging. No historical raw results are replaced.

2026-09-08. PRISM is the stronger candidate in this sampled screen: 36/36 target hits versus Caspar FP64’s 32/36. Across 18 scene/target cells, PRISM wins 13, Caspar wins five, and none fall within the predeclared 5% tie band. Two PRISM wins are target-reliability wins without a finite speed ratio. These are six scenes, not 18 independent scene samples.

The frozen restart rule never activated in 36 PRISM runs; there were zero rejected attempts. This supports fixed-five behavior with point repair, but adds no evidence for active restart recovery or the isolated benefit of multi-shift. Defaults remain unchanged.

## Frozen protocol

Six additional BAL scenes, two repeats, reversed scene/target/arm order in repeat two. Three thresholds were frozen before outcomes: rounded historical anchor ×1.02, ×1.005, ×1.0. These are convenience-sampled, historically seen scenes; anchors are not certified optima. Four native seconds per run, except Final961 (961 cameras, 187103 points, 1692975 observations), which has eight. No tuning or extra runs followed outcomes.

Same original observations, SIMPLE_RADIAL model, fixed principal point, zero k2; frozen PRISM v7 versus the previously precision-verified Caspar FP64 executable. Caspar uses the pinned COLMAP-generated backend directly, with unchanged driver defaults, not full COLMAP reconstruction. All exported endpoints were independently CPU-scored. See [baseline details](current_caspar_results.md).

## Median native time to the same target

Both repeats hit unless marked miss. Ratios compare native first crossings only.

| Scene | Target level / cost | PRISM seconds | Caspar FP64 seconds | Verdict |
|---|---|---:|---:|---|
| ladybug-598 | loose / 183600 | 0.269 | 0.195 | Caspar 1.38× as fast |
| ladybug-598 | medium / 180900 | 0.644 | 0.345 | Caspar 1.87× as fast |
| ladybug-598 | tight / 180000 | 0.889 | Miss (0/2) | PRISM alone hits |
| dubrovnik-135 | loose / 484500 | 0.423 | 0.351 | Caspar 1.21× as fast |
| dubrovnik-135 | medium / 477375 | 0.614 | 0.544 | Caspar 1.13× as fast |
| dubrovnik-135 | tight / 475000 | 1.059 | 1.188 | PRISM 1.12× as fast |
| trafalgar-257 | loose / 122400 | 0.316 | 0.509 | PRISM 1.61× as fast |
| trafalgar-257 | medium / 120600 | 0.362 | 0.734 | PRISM 2.03× as fast |
| trafalgar-257 | tight / 120000 | 0.459 | 1.021 | PRISM 2.23× as fast |
| venice-89 | loose / 313650 | 0.754 | 1.723 | PRISM 2.29× as fast |
| venice-89 | medium / 309037.5 | 1.011 | 3.446 | PRISM 3.41× as fast |
| venice-89 | tight / 307500 | 1.493 | Miss (0/2) | PRISM alone hits |
| final-93 | loose / 161568 | 0.188 | 0.179 | Caspar 1.05× as fast |
| final-93 | medium / 159192 | 0.182 | 0.237 | PRISM 1.30× as fast |
| final-93 | tight / 158400 | 0.418 | 1.837 | PRISM 4.39× as fast |
| final-961 | loose / 1703400 | 1.412 | 1.873 | PRISM 1.33× as fast |
| final-961 | medium / 1678350 | 2.408 | 3.207 | PRISM 1.33× as fast |
| final-961 | tight / 1670000 | 3.794 | 5.893 | PRISM 1.55× as fast |

Caspar’s tight-target misses are close in objective value; missing a threshold is not proof of a large reconstruction-quality difference:

| Scene | Tight target | Caspar median endpoint cost | Above target |
|---|---:|---:|---:|
| ladybug-598 | 180000 | 180121.036 | 0.067% |
| venice-89 | 307500 | 308576.746 | 0.350% |

## Endpoint cost and process wall

Values are medians across two repeats. Wall runs through returned/exported endpoints. Caspar includes in-driver CPU diagnostics; PRISM’s independent endpoint audits happen afterward. Caspar graph setup is outside its native timer, whereas PRISM includes solver-local setup. Neither clock is a fully normalized end-to-end pipeline comparison. Native caps are not strict wall deadlines.

| Scene | Level | PRISM cost | Caspar cost | PRISM wall seconds | Caspar wall seconds |
|---|---|---:|---:|---:|---:|
| ladybug-598 | loose | 183388.583 | 183408.394 | 0.960 | 0.735 |
| ladybug-598 | medium | 180859.334 | 180712.764 | 1.271 | 0.838 |
| ladybug-598 | tight | 179963.187 | 180121.036 | 1.507 | 4.522 |
| dubrovnik-135 | loose | 480520.910 | 481424.882 | 1.240 | 0.989 |
| dubrovnik-135 | medium | 476358.599 | 477368.824 | 1.416 | 1.210 |
| dubrovnik-135 | tight | 474788.173 | 474885.893 | 1.868 | 1.870 |
| trafalgar-257 | loose | 121542.839 | 121994.518 | 0.886 | 0.963 |
| trafalgar-257 | medium | 120143.731 | 120518.680 | 0.937 | 1.221 |
| trafalgar-257 | tight | 119124.595 | 119988.094 | 1.062 | 1.462 |
| venice-89 | loose | 312913.142 | 313586.153 | 1.583 | 2.417 |
| venice-89 | medium | 308264.126 | 309014.010 | 1.795 | 4.130 |
| venice-89 | tight | 307268.915 | 308576.746 | 2.379 | 4.742 |
| final-93 | loose | 158911.979 | 160375.787 | 0.800 | 0.657 |
| final-93 | medium | 158911.979 | 159012.306 | 0.821 | 0.718 |
| final-93 | tight | 158367.566 | 158399.587 | 1.012 | 2.377 |
| final-961 | loose | 1695935.803 | 1702004.940 | 2.846 | 3.270 |
| final-961 | medium | 1678039.342 | 1676910.928 | 3.865 | 4.566 |
| final-961 | tight | 1669944.940 | 1669956.547 | 5.224 | 7.262 |

## Verification and interpretation

72 pipelines / 72 solver stages; 96.372 total native seconds and 150.844 measured process-wall seconds (excluding outer orchestration/audits). All 72 binary/input manifests matched frozen files; PRISM source matched v7, Caspar matched the previous verified FP64 build, and selected PRISM state copies matched their audited stage. Maximum endpoint relative audit discrepancy: 3.4e-12. Maximum Caspar initial native/reference discrepancy: 4.51e-10; initial CPU/reference discrepancy: 1.98e-10. Caspar accepted-cost traces were monotone. All 11 older jobs remain paused.

The larger Final961 favors PRISM at all three targets (1.33–1.55× native). Trafalgar257 and Venice89 also consistently favor PRISM. Ladybug598 and Dubrovnik135 change winner with target quality; Final93 narrowly favors Caspar at the loose threshold (just outside the 5% tie band) and favors PRISM at the others. Two repeats establish a useful directional signal, not statistical significance or a universal solver ranking. A publication claim still needs broader independent evaluation and a matched ablation to attribute gains to multi-shift rather than point repair or other configuration differences.

Artifacts: `/workspace/prism-caspar-six/{PROTOCOL.md,plan.json,results.json,summary.json,completion.json}`, raw per-run manifests, traces and states under `prism/screen/` and `caspar-runs/`. The runner is `bench/current_caspar_comparison.py`; this batch’s aggregation/check script is `/workspace/prism-caspar-six/summarize.py`.
