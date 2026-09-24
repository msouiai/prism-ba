# Initialization noise: frozen PRISM versus Caspar FP64

Timing clarification from the [menu ablation audit](menu_caspar_ablation_results.md): this study’s PRISM harness enabled `OCA_LEARN_LOG`, which adds a blocking norm per scored candidate. These historical times include that instrumentation; they are not logging-free solver timings. The new ablation separates timing runs from diagnostic logging. No historical raw results are replaced.

Four contrasting original BAL objectives, three seeded starting states, one solve per seed and arm:24 pipelines. Gaussian additions use sigma0.001 radians per angle-axis coordinate and0.001 times median centered point radius per translation/point coordinate. Intrinsics stay unchanged; original observation bytes are identical. The existing medium targets and4/4/12/20 second native caps are retained. No new calibration or solver tuning. See [protocol](noise_caspar_protocol.md).

Certified target hits: PRISM **9/12**, Caspar **6/12**. PRISM restart activations: **0/12**. Logged rejections: PRISM0, Caspar41.

Seeds are different initializations, not timing repeats or independent scenes. Medians mix initialization difficulty with runtime variability. Compare each matched seed as well as the aggregate. Previous unperturbed runs are historical context, not newly interleaved controls.

The median winner is preserved on the three smaller problems: PRISM on Trafalgar126 and Final1936, Caspar on Dubrovnik88. Final1936 still flips winner on seed17, so the median does not imply dominance at every initialization. All six noisy Final13682 runs miss the unchanged target; Caspar has the lower endpoint cost on each seed, with median 28,577,939.41 versus PRISM 37,369,898.88. No equal-quality speed ratio is available there.

The largest scene's initial objective increases 18.75–117.66×, whereas the three smaller problems increase only1.02–1.67×. Small parameter noise is not uniformly mild in reprojection cost. This single-level, three-seed test does not establish general robustness. PRISM's zero rejections mean the test still does not exercise active early restart. Caspar remains faster on Dubrovnik88 despite its logged rejections; counts alone do not determine wall time.

## Scene-level comparison

Median native certified crossing is shown only if all three seeds hit. Rank success count first; if both3/3, compare median with a5% tie band. No finite speed ratio for misses.

| Scene | Unperturbed medium winner | PRISM noisy hits / time | Caspar noisy hits / time | Noisy verdict |
|---|---|---:|---:|---|
| trafalgar-126 | PRISM | 3/3; 1.895s | 0/3; — | PRISM |
| dubrovnik-88 | Caspar | 3/3; 2.343s | 3/3; 1.265s | Caspar 1.85× as fast |
| final-1936 | PRISM | 3/3; 3.772s | 3/3; 4.881s | PRISM 1.29× as fast |
| final-13682 | Caspar | 0/3; — | 0/3; — | unresolved |

## Starting-cost effect

These ratios quantify the perturbation effect; a symmetric parameter perturbation is not guaranteed to increase every initial objective.

| Scene | Seed | Initial cost / original initial cost |
|---|---:|---:|
| trafalgar-126 | 17 | 1.66537 |
| dubrovnik-88 | 17 | 1.05612 |
| final-1936 | 17 | 1.13943 |
| final-13682 | 17 | 117.664 |
| final-13682 | 29 | 34.7641 |
| final-1936 | 29 | 1.16763 |
| dubrovnik-88 | 29 | 1.0217 |
| trafalgar-126 | 29 | 1.52487 |
| trafalgar-126 | 43 | 1.54301 |
| dubrovnik-88 | 43 | 1.0512 |
| final-1936 | 43 | 1.15645 |
| final-13682 | 43 | 18.7548 |

## Each matched seed

| Scene | Seed | PRISM hit / seconds | Caspar hit / seconds | PRISM cost gap | Caspar cost gap | PRISM rejections | Caspar logged rejections | PRISM restarted |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| trafalgar-126 | 17 | 2.191 | Miss | -0.0067179% | 0.266454% | 0 | 0 | False |
| trafalgar-126 | 29 | 1.895 | Miss | -0.00317655% | 0.230411% | 0 | 0 | False |
| trafalgar-126 | 43 | 0.832 | Miss | -0.104764% | 0.24478% | 0 | 0 | False |
| dubrovnik-88 | 17 | 2.343 | 1.265 | -0.00683161% | -0.276121% | 0 | 9 | False |
| dubrovnik-88 | 29 | 2.396 | 1.087 | -0.0149118% | -0.172662% | 0 | 7 | False |
| dubrovnik-88 | 43 | 2.206 | 1.433 | -0.00706044% | -0.0318048% | 0 | 12 | False |
| final-1936 | 17 | 5.745 | 5.210 | -0.31417% | -0.0170328% | 0 | 3 | False |
| final-1936 | 29 | 3.772 | 4.876 | -0.0811311% | -0.0436642% | 0 | 1 | False |
| final-1936 | 43 | 3.750 | 4.881 | -0.227503% | -0.0414783% | 0 | 1 | False |
| final-13682 | 17 | Miss | Miss | 40.6315% | 15.2987% | 0 | 3 | False |
| final-13682 | 29 | Miss | Miss | 16.9832% | 4.54219% | 0 | 3 | False |
| final-13682 | 43 | Miss | Miss | 36.7939% | 4.61062% | 0 | 2 | False |

Positive cost gaps mean the final endpoint is above the unchanged target. Negative gaps mean below it; a hit also requires a certified stopping event within cap. PRISM retains its1e-8 relative inward stopping margin; both arms require independent CPU endpoint scoring. Native clocks have different setup scopes. Caspar process wall includes in-driver CPU checks while PRISM independent endpoint audits run after its process-wall window. All abandoned PRISM restart work is charged.

Caspar rejection counts come from its existing full-precision score-decrease acceptance trace. The checked driver computes this indicator independently of the backend acceptance flag. These are logged, completed decisions; a final diagonal-exit rejection or budget-discarded attempt may not be logged and is not added to this count. PRISM counts are its logged rejected outer attempts. These counts are diagnostic, not identical units of work across algorithms.

## Endpoint costs and wall times

| Scene | Seed | Arm | Final CPU cost | Native return seconds | Process wall seconds |
|---|---:|---|---:|---:|---:|
| trafalgar-126 | 17 | restart | 104527.219018 | 2.204 | 2.854 |
| trafalgar-126 | 17 | caspar64 | 104812.776810 | 4.009 | 4.456 |
| dubrovnik-88 | 17 | caspar64 | 358012.626760 | 1.265 | 1.825 |
| dubrovnik-88 | 17 | restart | 358979.385386 | 2.352 | 3.297 |
| final-1936 | 17 | restart | 5058994.054447 | 5.764 | 9.410 |
| final-1936 | 17 | caspar64 | 5074073.567106 | 5.210 | 9.095 |
| final-13682 | 17 | caspar64 | 31497752.795931 | 21.358 | 41.112 |
| final-13682 | 17 | restart | 38418278.987307 | 22.917 | 42.503 |
| final-13682 | 29 | caspar64 | 28559245.387975 | 20.429 | 40.833 |
| final-13682 | 29 | restart | 31957917.991562 | 29.741 | 48.247 |
| final-1936 | 29 | restart | 5070820.619495 | 3.792 | 7.708 |
| final-1936 | 29 | caspar64 | 5072722.043125 | 4.876 | 8.822 |
| dubrovnik-88 | 29 | caspar64 | 358384.049118 | 1.087 | 1.692 |
| dubrovnik-88 | 29 | restart | 358950.377255 | 2.402 | 3.098 |
| trafalgar-126 | 29 | restart | 104530.920952 | 1.906 | 2.408 |
| trafalgar-126 | 29 | caspar64 | 104775.099892 | 4.004 | 4.402 |
| trafalgar-126 | 43 | restart | 104424.726910 | 0.849 | 1.380 |
| trafalgar-126 | 43 | caspar64 | 104790.120411 | 4.005 | 4.401 |
| dubrovnik-88 | 43 | caspar64 | 358889.730532 | 1.433 | 1.994 |
| dubrovnik-88 | 43 | restart | 358978.563865 | 2.214 | 2.885 |
| final-1936 | 43 | restart | 5063392.359612 | 3.770 | 7.400 |
| final-1936 | 43 | caspar64 | 5072832.972908 | 4.881 | 8.760 |
| final-13682 | 43 | caspar64 | 28577939.405247 | 21.111 | 41.424 |
| final-13682 | 43 | restart | 37369898.879676 | 20.584 | 39.876 |

## Verification

24/24 pipelines returned independently audited states; 24 solver-stage manifests match frozen binaries and exact perturbed input hashes. All12 inputs passed observation-byte, intrinsic, seeded-parameter and serialization checks before any measurement. Retained PRISM best-state copies and cumulative stage times match. Maximum endpoint relative audit error 3.65e-12; maximum Caspar native/CPU endpoint difference 4.13e-14. Original source files and PRISM v7 source are unchanged. All11 older jobs remain paused.

Native solver work: 192.162s. Measured process wall: 339.885s, excluding outer orchestration and separate audits. No additional runs or noise levels were selected after outcomes.

Artifacts: `/workspace/prism-caspar-noise/` contains the protocol, twelve verified inputs, per-run traces/states/manifests, `results.json`, `annotated-results.json`, `results.csv`, `summary.json`, and `verification.json`. Reproduce with `python3 bench/noise_caspar_screen.py`, then `python3 bench/summarize_noise_caspar.py /workspace/prism-caspar-noise`.
