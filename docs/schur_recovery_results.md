# Numerical recovery controls and six-scene validation

Status: complete. Frozen same-host study on `2237c6528e79`, RTX 2000 Ada 16 GB. All tables use native time to an independently audited common target; values are median [min, max] seconds. Misses and invalid endpoints remain in denominators. Three repeats are executions, not independent datasets.

The current curvature-plus-floor candidate remains the incumbent. The simple ×4-with-floor control matches its Ladybug time within the observed spread; transient ×4 recovery requires more rebuilds and is slower there. Final-3068 does not give a consistent recovery-rule ranking. The experiments support retaining a safe numerical damping floor, but do not demonstrate a general advantage for estimating its value from curvature or establish a novel TR algorithm.

## Primary extension: 1% above fixed useful-quality anchors

| Scene | Prism, guard off | Prism, curvature + floor | Caspar FP32 | Caspar FP64 |
|---|---:|---:|---:|---:|
| ladybug-810 | 0.118 [0.110, 0.146] | 0.110 [0.109, 0.110] | 0.143 [0.142, 0.204] | 0.381 [0.376, 0.383] |
| ladybug-1469 | 0.307 [0.306, 0.307] | 0.307 [0.306, 0.336] | 0/3 hits | 0.946 [0.946, 0.951] |
| dubrovnik-356 | 1/3 hits | 0/3 hits | 0/3 hits | 0/3 hits |
| venice-951 | 1.456 [1.454, 1.456] | 1.452 [1.452, 1.462] | 0/3 hits | 1/3 hits |
| final-3068 | 0/3 hits | 2/3 hits | 0/3 hits | 0/3 hits |
| final-13682 | 4.263 [4.260, 4.263] | 4.261 [4.260, 4.292] | 7.080 [6.429, 7.090] | 14.987 [14.982, 14.988] |

## Combined context: previous four scenes plus this extension

The previously reported four-scene comparison and the new six-scene comparison use the same frozen candidate and Caspar binaries on the same host. They are separate timing batches, and the new study declares a different scoring-consistency tolerance. The previous results were not rerun for this table. Related BAL subsets are not independent recordings.

| Scene | Prism, curvature + floor | Caspar FP32 | Caspar FP64 |
|---|---:|---:|---:|
| ladybug-1723 | 0.445 [0.378, 0.451] | 0/3 hits | 1.394 [1.393, 1.411] |
| final-1936 | 0.565 [0.556, 0.569] | 1.163 [1.163, 1.173] | 2.559 [2.559, 2.564] |
| trafalgar-126 | 0.132 [0.130, 0.145] | 0/3 hits | 1.494 [1.194, 1.607] |
| final-4585 | 1.843 [1.837, 1.917] | 0/3 hits | 0/3 hits |
| ladybug-810 | 0.110 [0.109, 0.110] | 0.143 [0.142, 0.204] | 0.381 [0.376, 0.383] |
| ladybug-1469 | 0.307 [0.306, 0.336] | 0/3 hits | 0.946 [0.946, 0.951] |
| dubrovnik-356 | 0/3 hits | 0/3 hits | 0/3 hits |
| venice-951 | 1.452 [1.452, 1.462] | 0/3 hits | 1/3 hits |
| final-3068 | 2/3 hits | 0/3 hits | 0/3 hits |
| final-13682 | 4.261 [4.260, 4.292] | 7.080 [6.429, 7.090] | 14.987 [14.982, 14.988] |

Target-hit counts: `{"caspar32": {"hits": 9, "runs": 30}, "caspar64": {"hits": 19, "runs": 30}, "rayleigh": {"hits": 26, "runs": 30}}`. Per-scene finite speed ratios are recorded in comparisons.json only when both arms reach all three targets. There is no finite speedup assigned to a failed target and no broad average over a selectively successful subset.

## Recovery ablations

| Scene | Prism, guard off | Prism, ×4 transient | Prism, ×4 + floor | Prism, curvature + floor |
|---|---:|---:|---:|---:|
| ladybug-1723 | 0/3 hits | 0.491 [0.487, 0.537] | 0.443 [0.442, 0.452] | 0.454 [0.434, 0.468] |
| final-1936 | 0.550 [0.550, 0.551] | 0.550 [0.550, 0.555] | 0.555 [0.552, 0.567] | 0.552 [0.550, 0.566] |
| trafalgar-126 | 0.132 [0.128, 0.135] | 0.131 [0.130, 0.134] | 0.139 [0.129, 0.144] | 0.139 [0.135, 0.144] |

Additional scenes selected by the predeclared negative-curvature/guard-activation rule:

| Scene | Prism, guard off | Prism, ×4 transient | Prism, ×4 + floor | Prism, curvature + floor |
|---|---:|---:|---:|---:|
| final-3068 | 3.415 [2.788, 5.037] | 1.697 [1.041, 2.579] | 2/3 hits | 2/3 hits |

Both Final-3068 batches retained together: guard-off and curvature now have six runs, while each ×4 control has three. The changing outcomes of the identical guard-off configuration demonstrate why the latest batch alone is insufficient for attribution.

| Scene | Prism, guard off | Prism, ×4 transient | Prism, ×4 + floor | Prism, curvature + floor |
|---|---:|---:|---:|---:|
| final-3068 | 3/6 hits | 1.697 [1.041, 2.579] | 2/3 hits | 4/6 hits |

## Remaining stalls

These are directly observed terminal states of the primary guarded runs. They distinguish the persistent numerical floor from the much larger controller damping and collapsed camera radius at termination.

| Scene / repeat | Excess above target | Final lambda | Numeric floor | Raw camera norm / radius | Backtrack evaluations |
|---|---:|---:|---:|---:|---:|
| dubrovnik-356 / 1 | 0.00744% | 45 | 1e-16 | 3801.2 | 287 |
| dubrovnik-356 / 2 | 0.00481% | 11.3 | 1e-16 | 5866.8 | 316 |
| dubrovnik-356 / 3 | 0.00392% | 29.5 | 1e-16 | 10841717.5 | 445 |
| final-3068 / 2 | 0.80477% | 14.2 | 1.32e-07 | 2616.4 | 849 |

These runs stop on the inherited eight-outer relative-improvement criterion (OCA_FTOL=1e-5), before the native cap. In the recorded terminal states, controller damping is far above the numerical floor and the camera step is strongly clipped. This points to poor nonlinear progress and excessive contraction as the next issue to investigate; it does not establish which tracks or model errors cause it. Merely increasing the numerical repair floor would not directly address this observed regime. Full counters and source traces are in stall-analysis.json.

A same-target Final-3068 guard-off pair has identical binary, input and solver flags. Initial rho differs by roughly 5e-16, but by outer 13 the two runs report rho=0.02113 and rho=0.10127, on opposite sides of the 0.1 acceptance threshold. The decision differs before any numerical repair can act (both guards are off). This is consistent with amplification of numerical perturbations, but the trace alone does not establish the source of the perturbations or which observations amplify them. The paired prefix is preserved in final3068-repeatability.json.

## Target sensitivity

The 0.5% and 2% targets are declared alternatives; the primary 1% target is unchanged. Ladybug-1723 and Trafalgar-126 were specified in advance. Additional scenes follow the recorded ambiguity rule, not a search for favorable results.

### extension-half-percent

| Scene | Prism, guard off | Prism, curvature + floor | Caspar FP32 | Caspar FP64 |
|---|---:|---:|---:|---:|
| dubrovnik-356 | 0/3 hits | 1/3 hits | 0/3 hits | 0/3 hits |
| venice-951 | 1.572 [1.562, 1.573] | 1.567 [1.566, 1.582] | 0/3 hits | 1/3 hits |
| final-3068 | 0.991 [0.936, 1.317] | 2.725 [0.985, 3.239] | 0/3 hits | 0/3 hits |

### extension-two-percent

| Scene | Prism, guard off | Prism, curvature + floor | Caspar FP32 | Caspar FP64 |
|---|---:|---:|---:|---:|
| dubrovnik-356 | 1.347 [1.326, 1.362] | 1.324 [1.323, 1.325] | 0/3 hits | 0/3 hits |
| venice-951 | 1.455 [1.453, 1.456] | 1.457 [1.456, 1.460] | 0/3 hits | 2/3 hits |
| final-3068 | 2/3 hits | 1.272 [0.810, 3.537] | 0/3 hits | 0/3 hits |

### ladybug-half-percent

| Scene | Prism, guard off | Prism, ×4 transient | Prism, ×4 + floor | Prism, curvature + floor | Caspar FP32 | Caspar FP64 |
|---|---:|---:|---:|---:|---:|---:|
| ladybug-1723 | 0/3 hits | 0.983 [0.973, 1.539] | 0.776 [0.742, 0.874] | 0.761 [0.611, 0.817] | 0/3 hits | 2.381 [2.373, 2.644] |

### ladybug-two-percent

| Scene | Prism, guard off | Prism, ×4 transient | Prism, ×4 + floor | Prism, curvature + floor | Caspar FP32 | Caspar FP64 |
|---|---:|---:|---:|---:|---:|---:|
| ladybug-1723 | 0.236 [0.230, 0.254] | 0.232 [0.231, 0.233] | 0.234 [0.231, 0.235] | 0.230 [0.229, 0.251] | 0/3 hits | 0.607 [0.607, 0.608] |

### trafalgar-half-percent

| Scene | Prism, guard off | Prism, curvature + floor | Caspar FP32 | Caspar FP64 |
|---|---:|---:|---:|---:|
| trafalgar-126 | 0.178 [0.169, 0.195] | 0.170 [0.170, 0.170] | 0/3 hits | 2.752 [2.574, 2.805] |

### trafalgar-two-percent

| Scene | Prism, guard off | Prism, curvature + floor | Caspar FP32 | Caspar FP64 |
|---|---:|---:|---:|---:|
| trafalgar-126 | 0.132 [0.131, 0.139] | 0.126 [0.125, 0.126] | 1.087 [1.077, 1.133] | 0.675 [0.665, 0.678] |

## Counters and endpoints

| Phase | Scene | Arm | Hits | Median cost | Rebuilds across repeats | Rejects across repeats |
|---|---|---|---:|---:|---|---|
| controls | ladybug-1723 | off | 0/3 | 453843.991182 | [0, 0, 0] | [10, 11, 9] |
| controls | ladybug-1723 | x4 | 3/3 | 452633.030704 | [5, 4, 7] | [1, 2, 1] |
| controls | ladybug-1723 | x4_floor | 3/3 | 452444.701978 | [1, 1, 1] | [1, 1, 1] |
| controls | ladybug-1723 | rayleigh | 3/3 | 452558.789632 | [1, 1, 1] | [2, 1, 1] |
| controls | final-1936 | x4 | 3/3 | 5095070.523927 | [0, 0, 0] | [0, 0, 0] |
| controls | final-1936 | x4_floor | 3/3 | 5095070.523927 | [0, 0, 0] | [0, 0, 0] |
| controls | final-1936 | rayleigh | 3/3 | 5095070.523927 | [0, 0, 0] | [0, 0, 0] |
| controls | final-1936 | off | 3/3 | 5095070.523927 | [0, 0, 0] | [0, 0, 0] |
| controls | trafalgar-126 | x4_floor | 3/3 | 105234.264419 | [0, 0, 0] | [0, 0, 0] |
| controls | trafalgar-126 | rayleigh | 3/3 | 105234.212555 | [0, 0, 0] | [0, 0, 0] |
| controls | trafalgar-126 | off | 3/3 | 105234.226642 | [0, 0, 0] | [0, 0, 0] |
| controls | trafalgar-126 | x4 | 3/3 | 105234.264376 | [0, 0, 0] | [0, 0, 0] |
| extension | ladybug-810 | off | 3/3 | 225203.271271 | [0, 0, 0] | [0, 0, 0] |
| extension | ladybug-810 | rayleigh | 3/3 | 225203.271271 | [0, 0, 0] | [0, 0, 0] |
| extension | ladybug-810 | caspar32 | 3/3 | 225559.553370 | [0, 0, 0] | [5, 2, 1] |
| extension | ladybug-810 | caspar64 | 3/3 | 225379.603688 | [0, 0, 0] | [0, 0, 0] |
| extension | ladybug-1469 | rayleigh | 3/3 | 429635.115428 | [0, 0, 0] | [1, 1, 1] |
| extension | ladybug-1469 | caspar32 | 0/3 | 5744727.876037 | [0, 0, 0] | [3, 3, 3] |
| extension | ladybug-1469 | caspar64 | 3/3 | 429722.183018 | [0, 0, 0] | [3, 3, 3] |
| extension | ladybug-1469 | off | 3/3 | 429631.920053 | [0, 0, 0] | [1, 1, 1] |
| extension | dubrovnik-356 | caspar32 | 0/3 | 1181359.335402 | [0, 0, 0] | [6, 6, 6] |
| extension | dubrovnik-356 | caspar64 | 0/3 | 1199035.795731 | [0, 0, 0] | [5, 5, 5] |
| extension | dubrovnik-356 | off | 1/3 | 724033.364777 | [0, 0, 0] | [2, 12, 16] |
| extension | dubrovnik-356 | rayleigh | 0/3 | 724042.082649 | [0, 0, 0] | [16, 18, 20] |
| extension | venice-951 | caspar64 | 1/3 | 2022112.772295 | [0, 0, 0] | [6, 4, 4] |
| extension | venice-951 | off | 3/3 | 2013038.282111 | [0, 0, 0] | [0, 0, 0] |
| extension | venice-951 | rayleigh | 3/3 | 2013038.295013 | [0, 0, 0] | [0, 0, 0] |
| extension | venice-951 | caspar32 | 0/3 | 2072605.435285 | [0, 0, 0] | [60, 32, 40] |
| extension | final-3068 | off | 0/3 | 1842285.458189 | [0, 0, 0] | [18, 16, 18] |
| extension | final-3068 | rayleigh | 2/3 | 1818840.149316 | [1, 1, 1] | [19, 21, 5] |
| extension | final-3068 | caspar32 | 0/3 | 2646205.255382 | [0, 0, 0] | [11, 11, 15] |
| extension | final-3068 | caspar64 | 0/3 | 1977460.494577 | [0, 0, 0] | [13, 13, 13] |
| extension | final-13682 | rayleigh | 3/3 | 26022217.673538 | [0, 0, 0] | [0, 0, 0] |
| extension | final-13682 | caspar32 | 3/3 | 27520084.712579 | [0, 0, 0] | [1, 1, 0] |
| extension | final-13682 | caspar64 | 3/3 | 27580841.407789 | [0, 0, 0] | [0, 0, 0] |
| extension | final-13682 | off | 3/3 | 26022217.680246 | [0, 0, 0] | [0, 0, 0] |
| extension-controls | final-3068 | off | 3/3 | 1798067.121757 | [0, 0, 0] | [6, 10, 15] |
| extension-controls | final-3068 | x4 | 3/3 | 1808119.495621 | [3, 1, 0] | [3, 2, 4] |
| extension-controls | final-3068 | x4_floor | 2/3 | 1805679.444686 | [1, 0, 1] | [6, 2, 15] |
| extension-controls | final-3068 | rayleigh | 2/3 | 1817249.411270 | [0, 1, 0] | [2, 30, 6] |
| extension-half-percent | dubrovnik-356 | off | 0/3 | 724070.280046 | [0, 0, 0] | [20, 16, 17] |
| extension-half-percent | dubrovnik-356 | rayleigh | 1/3 | 724034.101385 | [0, 0, 0] | [16, 2, 17] |
| extension-half-percent | dubrovnik-356 | caspar32 | 0/3 | 1181345.950401 | [0, 0, 0] | [6, 6, 6] |
| extension-half-percent | dubrovnik-356 | caspar64 | 0/3 | 1199035.795732 | [0, 0, 0] | [5, 5, 5] |
| extension-half-percent | venice-951 | rayleigh | 3/3 | 1976769.664172 | [0, 0, 0] | [0, 0, 0] |
| extension-half-percent | venice-951 | caspar32 | 0/3 | 2064148.569701 | [0, 0, 0] | [32, 35, 40] |
| extension-half-percent | venice-951 | caspar64 | 1/3 | 2020220.615743 | [0, 0, 0] | [6, 4, 11] |
| extension-half-percent | venice-951 | off | 3/3 | 1976767.863261 | [0, 0, 0] | [0, 0, 0] |
| extension-half-percent | final-3068 | caspar32 | 0/3 | 2649350.303182 | [0, 0, 0] | [11, 11, 11] |
| extension-half-percent | final-3068 | caspar64 | 0/3 | 1977460.494577 | [0, 0, 0] | [13, 13, 13] |
| extension-half-percent | final-3068 | off | 3/3 | 1802967.073118 | [0, 0, 0] | [2, 1, 1] |
| extension-half-percent | final-3068 | rayleigh | 3/3 | 1802267.034687 | [1, 0, 1] | [4, 1, 6] |
| extension-two-percent | dubrovnik-356 | off | 3/3 | 730421.381390 | [0, 0, 0] | [1, 1, 1] |
| extension-two-percent | dubrovnik-356 | rayleigh | 3/3 | 730421.287115 | [0, 0, 0] | [1, 1, 1] |
| extension-two-percent | dubrovnik-356 | caspar32 | 0/3 | 1181371.075064 | [0, 0, 0] | [5, 6, 6] |
| extension-two-percent | dubrovnik-356 | caspar64 | 0/3 | 1199035.795732 | [0, 0, 0] | [5, 5, 5] |
| extension-two-percent | venice-951 | rayleigh | 3/3 | 2013038.156035 | [0, 0, 0] | [0, 0, 0] |
| extension-two-percent | venice-951 | caspar32 | 0/3 | 2088516.266802 | [0, 0, 0] | [40, 51, 52] |
| extension-two-percent | venice-951 | caspar64 | 2/3 | 2038829.799243 | [0, 0, 0] | [7, 4, 4] |
| extension-two-percent | venice-951 | off | 3/3 | 2013038.328046 | [0, 0, 0] | [0, 0, 0] |
| extension-two-percent | final-3068 | caspar32 | 0/3 | 2645889.708542 | [0, 0, 0] | [11, 11, 19] |
| extension-two-percent | final-3068 | caspar64 | 0/3 | 1977460.496284 | [0, 0, 0] | [13, 13, 13] |
| extension-two-percent | final-3068 | off | 2/3 | 1836910.323795 | [0, 0, 0] | [9, 27, 4] |
| extension-two-percent | final-3068 | rayleigh | 3/3 | 1814721.038906 | [0, 0, 1] | [2, 2, 6] |
| ladybug-half-percent | ladybug-1723 | off | 0/3 | 453743.571523 | [0, 0, 0] | [9, 14, 11] |
| ladybug-half-percent | ladybug-1723 | x4 | 3/3 | 450383.670879 | [21, 7, 14] | [6, 2, 2] |
| ladybug-half-percent | ladybug-1723 | x4_floor | 3/3 | 450362.235733 | [1, 1, 1] | [2, 4, 1] |
| ladybug-half-percent | ladybug-1723 | rayleigh | 3/3 | 450363.051153 | [1, 1, 1] | [1, 2, 1] |
| ladybug-half-percent | ladybug-1723 | caspar32 | 0/3 | 1024408.251903 | [0, 0, 0] | [4, 4, 4] |
| ladybug-half-percent | ladybug-1723 | caspar64 | 3/3 | 450287.992292 | [0, 0, 0] | [21, 19, 30] |
| ladybug-two-percent | ladybug-1723 | off | 3/3 | 456128.535543 | [0, 0, 0] | [1, 1, 1] |
| ladybug-two-percent | ladybug-1723 | x4 | 3/3 | 456128.707820 | [0, 0, 0] | [1, 1, 1] |
| ladybug-two-percent | ladybug-1723 | x4_floor | 3/3 | 456128.497412 | [0, 0, 0] | [1, 1, 1] |
| ladybug-two-percent | ladybug-1723 | rayleigh | 3/3 | 456128.563228 | [0, 0, 0] | [1, 1, 1] |
| ladybug-two-percent | ladybug-1723 | caspar32 | 0/3 | 1024407.094236 | [0, 0, 0] | [4, 4, 4] |
| ladybug-two-percent | ladybug-1723 | caspar64 | 3/3 | 457086.085772 | [0, 0, 0] | [0, 0, 0] |
| trafalgar-half-percent | trafalgar-126 | off | 3/3 | 104699.864903 | [0, 0, 0] | [0, 0, 0] |
| trafalgar-half-percent | trafalgar-126 | rayleigh | 3/3 | 104699.919395 | [0, 0, 0] | [0, 0, 0] |
| trafalgar-half-percent | trafalgar-126 | caspar32 | 0/3 | 105661.790654 | [0, 0, 0] | [259, 259, 259] |
| trafalgar-half-percent | trafalgar-126 | caspar64 | 3/3 | 105055.528153 | [0, 0, 0] | [0, 0, 0] |
| trafalgar-two-percent | trafalgar-126 | off | 3/3 | 105705.810244 | [0, 0, 0] | [0, 0, 0] |
| trafalgar-two-percent | trafalgar-126 | rayleigh | 3/3 | 105705.811236 | [0, 0, 0] | [0, 0, 0] |
| trafalgar-two-percent | trafalgar-126 | caspar32 | 3/3 | 106513.268400 | [0, 0, 0] | [95, 88, 93] |
| trafalgar-two-percent | trafalgar-126 | caspar64 | 3/3 | 106612.018582 | [0, 0, 0] | [0, 0, 0] |

## Protocol and reproducibility

All arms share the original observation set, FP64 endpoint evaluator and SIMPLE_RADIAL objective with k2 fixed to zero. Guard-off and curvature arms use the unchanged previously selected binary. The two ×4 controls are an isolated derivative; they differ only in the repair size and whether the repair persists as a lower damping bound. All repairs rebuild point factors/RHS with camera and point damping coupled, retain the linearization and restart CG. Each arm has the same total 32-rebuild limit, original nonlinear acceptance and radius checks, and native cap. The transient control permits later controller damping to fall again. The retained ×4 control isolates persistence from measured-curvature selection.

| Scene | Anchor | Primary target | Native cap (s) |
|---|---:|---:|---:|
| ladybug-810 | 223466.118246366 | 225700.779428829 | 8 |
| ladybug-1469 | 425487.494986305 | 429742.369936168 | 8 |
| dubrovnik-356 | 716838.885750828 | 724007.274608336 | 8 |
| venice-951 | 1999370.246783932 | 2019363.949251771 | 12 |
| final-3068 | 1801421.752397439 | 1819435.969921414 | 12 |
| final-13682 | 27318392.631312046 | 27591576.557625167 | 20 |
| ladybug-1723 | 448194.125000000 | 452676.066250000 | 8 |
| final-1936 | 5074937.972536108 | 5125687.352261469 | 8 |
| trafalgar-126 | 104534.241529263 | 105579.583944555 | 4 |

Ladybug-810/1469 anchors come from the minimum valid exported endpoint of three guard-off and three Caspar FP64 calibration runs at the same budget. Calibration is excluded from speed comparisons. Other anchors are historical and their sources and input hashes are frozen in plan.json. These are useful reference costs, not certified optima. Ladybug subsets are correlated; scene count does not imply that many independent recordings.

Native solver timer, parsing/export/audit excluded; Prism includes solver-local setup, Caspar excludes graph setup (recorded). All numerical rebuild work charged. GPU serialized; timeout after lock.

Native time primary; 600 secondary: Prism accepted outer steps, Caspar attempted iterations. Process timeout 180s excludes lock wait.

Caspar is the pinned standalone generated backend with the existing COLMAP-style default parameter profile, not a full COLMAP reconstruction run. No baseline parameters were tuned in this study.

The scoring-consistency tolerance for this new study is 1e-6 relative (0.0001%), declared before measurements based on the earlier 2.25e-7 arithmetic-order discrepancy. This is distinct from the previous report’s 1e-7 rule. No threshold was changed after seeing this study’s endpoints. A failed consistency check excludes a timing claim even if the endpoint appears close to target. Caspar FP32 native stopping retains the existing 0.1% empirical margin; qualification always uses the original-observation FP64 audit.

Totals: {"audit_or_execution_failures": 1, "complete": true, "max_valid_audit_error": 4.1514028668264664e-07, "measurement_runs": 252, "native_seconds": 744.467747921, "process_wall": 1334.6047834763303, "rebuilt_limit_runs": 0, "runs": 268, "valid_measurements": 252}.

Recovery formula, retained-floor and rebuild-accounting checks passed for 166 runs. Compatibility checks compare a single visited Final-1936 trajectory: accepted/rejected counts, products and audited objective match the frozen binary with the new controls disabled/defaulted. The CUDA fatbinary sections of the frozen and control executables are byte-identical (device-code-check.json), confirming that these controls change host-side recovery logic, not GPU kernels. This is not a general claim of GPU bitwise repeatability. The existing 100-case dense monotonicity and energy-identity check passed; it is an exact-arithmetic directional argument, not an all-directions or nonlinear convergence certificate.

One Final-13682 launch returned ETXTBSY before executing the solver: an objcopy section inspection briefly reopened the executable, without changing its hash. The unexecuted launch and original phase record are retained in infrastructure/blocked-launch/. That cell was repeated after the original scene batch, with all successful trials retained. infrastructure-incident.json records the event and recovery. It supplies no solver outcome or timing sample.

### Excluded or failed runs

- `/workspace/prism-schur-recovery/calibration/ladybug-1469-caspar64-2`: ('audit disagreement', 3.772123028467352e-06); cost=425773.66534093436, reported=425772.0592702864, audit_error=3.772123028467352e-06.

## Novelty boundary

Roundoff-induced Schur indefiniteness and the resulting need for additional LM damping are explicit prior art: Demmel et al., Square Root Bundle Adjustment (CVPR 2021), section 6.4, reports the issue on 84/97 explicit-FP32 problems and seven FP64 problems. Its square-root formulation is a stability alternative. [Primary paper](https://cvg.cit.tum.de/_media/spezial/bib/demmel2021rootba.pdf).

Ceres already treats invalid LM steps as rejected steps that shrink the trust region and improve conditioning. The ×4 controls here are generic recovery baselines, not a full reproduction of Ceres or RootBA. [Official source](https://github.com/ceres-solver/ceres-solver/blob/master/internal/ceres/levenberg_marquardt_strategy.h).

The candidate contribution is the measured-curvature repair coupled to point elimination and a persistent floor in this mixed-storage GPU implementation. The monotonicity inequality alone is standard algebra. These experiments evaluate whether the quantitative measurement contributes beyond simple damping recovery; they cannot establish uniqueness in the literature. No multishift menu or improved residual-Hessian model is active in this candidate.

For a failed Rayleigh quotient q, the simple ×4 update already has the same directional positivity guarantee whenever q + 3 lambda > 0. The measured rule is more conservative and may add no benefit in that regime. Moreover, with frozen Schur blocks and u=(C+lambda Dp)^(-1) W^T E p, the directional derivative is q'(lambda)=1+u^T Dp u/(p^T p), so coupled point damping can improve the direction by more than the camera-only lower bound predicts. These identities explain why a simple recovery rule can suffice; they are standard fixed-state algebra, not a new convergence result. Per-repair directional lower bounds are retained in recovery-validation.json.

The frozen candidate, control source/binary/headers, exact commands, input and binary hashes, logs, result JSON and losslessly compressed exported states are under `/workspace/prism-schur-recovery/`. The original candidate and production defaults remain unchanged. Builders and runners: `bench/build_schur_recovery.py`, `bench/schur_recovery_study.py`, `bench/run_schur_recovery.py`, and this report generator.

To reproduce after calibration: `python3 bench/run_schur_recovery.py`. Completed result cells are resumed. Regenerate the report with `python3 bench/report_schur_recovery.py`.
