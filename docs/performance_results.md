# Measured iteration-performance results

Times are solver wall seconds; ranges are observed sample ranges, not tail bounds.
Positive cost/time changes mean the optimized arm is worse/slower.
No verdict is assigned before both arms have at least three repeats.

## quality-A

Config A, max_iter=600; optimized flags: `{'OCA_RETRY_CACHE': '1', 'OCA_MULTI_RHS': '1'}`.

Reference provenance: final-3068 only: all three same-session reference runs from norm-quality-A, identical reference binary/common flags/config/budget/data. This cell is not interleaved with its optimized arm; no controls discarded.

| Scene | N ref/opt | Cost change | Ref seconds median [range] | Opt seconds median [range] | Time change | Cost comparison | Timing ranges |
|---|---:|---:|---:|---:|---:|---|---|
| venice-52 | 3/3 | +0.0519% | 30.400 [28.878, 35.643] | 30.508 [30.218, 73.197] | +0.35% | not resolved | overlap |
| ladybug-1197 | 3/3 | +0.0053% | 33.851 [25.293, 44.962] | 40.746 [33.872, 41.572] | +20.37% | not resolved | overlap |
| trafalgar-257 | 3/3 | -0.0040% | 7.923 [7.465, 12.347] | 9.775 [9.372, 10.314] | +23.37% | not resolved | overlap |
| dubrovnik-135 | 3/3 | -0.0000% | 15.569 [13.926, 16.212] | 13.712 [13.540, 15.693] | -11.92% | not resolved | overlap |
| final-3068 | 3/3 | +0.1837% | 194.882 [114.789, 217.953] | 196.972 [104.002, 247.951] | +1.07% | not resolved | overlap |

Crossings in both directions, in replicate order. Targets are the other arm’s
median endpoint; comparisons use exact costs without a tie tolerance. “Never”
means not reached within the tested budget. Bounds charge all setup/cleanup
time omitted by the original CSV clock before the crossing.

- **venice-52**: reference → optimized median: never, ≤24.011, ≤25.277; optimized → reference median: never, never, never
- **ladybug-1197**: reference → optimized median: ≤23.346, ≤42.853, never; optimized → reference median: never, never, ≤39.114
- **trafalgar-257**: reference → optimized median: never, never, never; optimized → reference median: ≤9.188, ≤8.921, ≤9.601
- **dubrovnik-135**: reference → optimized median: never, never, never; optimized → reference median: ≤13.516, ≤13.713, ≤10.168
- **final-3068**: reference → optimized median: never, ≤182.282, ≤173.379; optimized → reference median: ≤187.264, never, never

## quality-B

Config B, max_iter=600; optimized flags: `{'OCA_RETRY_CACHE': '1', 'OCA_MULTI_RHS': '1'}`.

| Scene | N ref/opt | Cost change | Ref seconds median [range] | Opt seconds median [range] | Time change | Cost comparison | Timing ranges |
|---|---:|---:|---:|---:|---:|---|---|
| venice-52 | 3/3 | +0.0619% | 30.148 [27.166, 31.394] | 28.983 [28.425, 33.044] | -3.86% | not resolved | overlap |
| ladybug-1197 | 3/3 | -0.0067% | 32.253 [31.123, 33.225] | 33.242 [24.553, 39.328] | +3.07% | not resolved | overlap |
| dubrovnik-135 | 3/3 | +0.0001% | 15.409 [13.680, 15.425] | 13.638 [12.540, 15.367] | -11.50% | not resolved | overlap |
| final-3068 | 3/3 | -0.5169% | 106.005 [93.552, 211.687] | 172.016 [157.522, 179.015] | +62.27% | not resolved | overlap |
| final-4585 | 3/3 | +0.0264% | 1070.905 [520.156, 1282.168] | 802.501 [404.709, 1055.359] | -25.06% | not resolved | overlap |

Crossings in both directions, in replicate order. Targets are the other arm’s
median endpoint; comparisons use exact costs without a tie tolerance. “Never”
means not reached within the tested budget. Bounds charge all setup/cleanup
time omitted by the original CSV clock before the crossing.

- **venice-52**: reference → optimized median: never, ≤9.378, ≤24.865; optimized → reference median: never, never, never
- **ladybug-1197**: reference → optimized median: never, never, never; optimized → reference median: ≤27.333, ≤30.781, never
- **dubrovnik-135**: reference → optimized median: ≤15.194, ≤15.270, ≤13.410; optimized → reference median: never, never, ≤12.504
- **final-3068**: reference → optimized median: never, never, never; optimized → reference median: ≤126.872, ≤102.353, ≤108.437
- **final-4585**: reference → optimized median: ≤1157.947, never, ≤997.055; optimized → reference median: never, ≤786.318, never

## storm-A60

Config A, max_iter=60; optimized flags: `{'OCA_RETRY_CACHE': '1', 'OCA_MULTI_RHS': '1'}`.

| Scene | N ref/opt | Cost change | Ref seconds median [range] | Opt seconds median [range] | Time change | Cost comparison | Timing ranges |
|---|---:|---:|---:|---:|---:|---|---|
| final-4585 | 3/3 | -0.0000% | 94.886 [94.875, 94.898] | 83.411 [83.401, 83.473] | -12.09% | not resolved | disjoint, faster |

Crossings in both directions, in replicate order. Targets are the other arm’s
median endpoint; comparisons use exact costs without a tie tolerance. “Never”
means not reached within the tested budget. Bounds charge all setup/cleanup
time omitted by the original CSV clock before the crossing.

- **final-4585**: reference → optimized median: never, ≤94.887, never; optimized → reference median: ≤83.473, ≤83.402, never

## norm-quality-A

Config A, max_iter=600; optimized flags: `{'OCA_RETRY_CACHE': '1', 'OCA_MULTI_RHS': '1', 'OCA_DIAG_NORM': '1'}`.

| Scene | N ref/opt | Cost change | Ref seconds median [range] | Opt seconds median [range] | Time change | Cost comparison | Timing ranges |
|---|---:|---:|---:|---:|---:|---|---|
| ladybug-1197 | 3/3 | -0.0485% | 35.750 [34.569, 41.262] | 27.517 [24.085, 32.120] | -23.03% | not resolved | disjoint, faster |
| final-3068 | 3/3 | +0.4326% | 194.882 [114.789, 217.953] | 118.014 [84.211, 126.011] | -39.44% | not resolved | overlap |
| venice-52 | 3/3 | +0.0175% | 31.289 [31.041, 31.974] | 29.569 [29.323, 33.611] | -5.50% | not resolved | overlap |

Crossings in both directions, in replicate order. Targets are the other arm’s
median endpoint; comparisons use exact costs without a tie tolerance. “Never”
means not reached within the tested budget. Bounds charge all setup/cleanup
time omitted by the original CSV clock before the crossing.

- **ladybug-1197**: reference → optimized median: never, never, never; optimized → reference median: never, ≤17.389, ≤20.395
- **final-3068**: reference → optimized median: never, ≤154.471, ≤148.658; optimized → reference median: never, never, never
- **venice-52**: reference → optimized median: ≤11.011, never, ≤28.392; optimized → reference median: never, never, never

## norm-storm-A60

Config A, max_iter=60; optimized flags: `{'OCA_RETRY_CACHE': '1', 'OCA_MULTI_RHS': '1', 'OCA_DIAG_NORM': '1'}`.

Reference provenance: Same-session controls from storm-A60. Additional arm is NOT interleaved with those controls.

| Scene | N ref/opt | Cost change | Ref seconds median [range] | Opt seconds median [range] | Time change | Cost comparison | Timing ranges |
|---|---:|---:|---:|---:|---:|---|---|
| final-4585 | 3/3 | -0.0000% | 94.886 [94.875, 94.898] | 70.830 [70.800, 70.970] | -25.35% | not resolved | disjoint, faster |

Crossings in both directions, in replicate order. Targets are the other arm’s
median endpoint; comparisons use exact costs without a tie tolerance. “Never”
means not reached within the tested budget. Bounds charge all setup/cleanup
time omitted by the original CSV clock before the crossing.

- **final-4585**: reference → optimized median: never, ≤94.887, never; optimized → reference median: ≤70.831, ≤70.801, ≤70.971
