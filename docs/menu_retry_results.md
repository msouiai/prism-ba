# Measured iteration-performance results

Times are solver wall seconds; ranges are observed sample ranges, not tail bounds.
Positive cost/time changes mean the optimized arm is worse/slower.
No verdict is assigned before both arms have at least three repeats.

## v4-A60

Config A, max_iter=60; optimized flags: `{'OCA_RETRY_CACHE': '1', 'OCA_MULTI_RHS': '1', 'OCA_DIAG_NORM': '1', 'OCA_MENU_BACKTRACK': '8'}`.

Reference provenance: All available completed reference runs from v2-A60, same reference binary/common flags/config/budget/data: {'final-4585': [1, 2, 3]}. Imported before any V4 candidate runs. These controls are not interleaved with V4; missing final-3068 controls are collected by the normal interleaved harness. No completed reference discarded.

| Scene | N ref/opt | Cost change | Ref seconds median [range] | Opt seconds median [range] | Time change | Cost comparison | Timing ranges |
|---|---:|---:|---:|---:|---:|---|---|
| final-4585 | 3/3 | -32.1387% | 70.931 [70.804, 70.950] | 51.274 [49.900, 53.043] | -27.71% | resolved difference | disjoint, faster |

Crossings in both directions, in replicate order. Targets are the other arm’s
median endpoint; comparisons use exact costs without a tie tolerance. “Never”
means not reached within the tested budget. Bounds charge all setup/cleanup
time omitted by the original CSV clock before the crossing.

- **final-4585**: reference → optimized median: never, never, never; optimized → reference median: ≤2.867, ≤2.874, ≤2.872

## v4-quality-A

Config A, max_iter=600; optimized flags: `{'OCA_RETRY_CACHE': '1', 'OCA_MULTI_RHS': '1', 'OCA_DIAG_NORM': '1', 'OCA_MENU_BACKTRACK': '8'}`.

Reference provenance: All available completed reference runs from v2-quality-A, same reference binary/common flags/config/budget/data: {'venice-52': [1, 2, 3], 'ladybug-1197': [1, 2, 3], 'final-3068': [1]}. Imported before any V4 candidate runs. These controls are not interleaved with V4; missing final-3068 controls are collected by the normal interleaved harness. No completed reference discarded.

| Scene | N ref/opt | Cost change | Ref seconds median [range] | Opt seconds median [range] | Time change | Cost comparison | Timing ranges |
|---|---:|---:|---:|---:|---:|---|---|
| venice-52 | 3/3 | -2.1794% | 29.174 [28.945, 29.411] | 31.199 [25.833, 60.616] | +6.94% | resolved difference | overlap |
| ladybug-1197 | 3/3 | -0.0556% | 34.279 [28.513, 36.669] | 25.936 [21.535, 33.978] | -24.34% | not resolved | overlap |
| final-3068 | 3/3 | +0.1129% | 164.171 [162.951, 227.200] | 260.499 [228.039, 264.407] | +58.68% | not resolved | disjoint, slower |

Crossings in both directions, in replicate order. Targets are the other arm’s
median endpoint; comparisons use exact costs without a tie tolerance. “Never”
means not reached within the tested budget. Bounds charge all setup/cleanup
time omitted by the original CSV clock before the crossing.

- **venice-52**: reference → optimized median: never, never, never; optimized → reference median: ≤4.415, ≤4.544, ≤33.656
- **ladybug-1197**: reference → optimized median: never, never, never; optimized → reference median: ≤11.438, ≤33.090, ≤22.723
- **final-3068**: reference → optimized median: ≤144.821, never, ≤102.417; optimized → reference median: ≤205.369, never, never


## Work counts

Values are medians [observed ranges]. Rescues are failed shift menus
accepted by full-step backtracking without rebuilding the system.
Rejects count attempts that still require the original damping ladder.
Total scoring includes menu, original alpha grid, and backtracking.
N below three is incomplete and supports no verdict.

### v4-A60

Config A, outer budget 60.

| Scene | Arm | N | Rejects | Rescues | Backtrack evaluations | Total scoring | Matvecs |
|---|---|---:|---:|---:|---:|---:|---:|
| final-4585 | reference | 3 | 454.0 [454.0, 454.0] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 2244.0 [2244.0, 2244.0] | 722.0 [722.0, 722.0] |
| final-4585 | optimized | 3 | 27.0 [15.0, 30.0] | 57.0 [57.0, 57.0] | 539.0 [427.0, 563.0] | 1233.0 [1111.0, 1282.0] | 1246.0 [1200.0, 1380.0] |

### v4-quality-A

Config A, outer budget 600.

| Scene | Arm | N | Rejects | Rescues | Backtrack evaluations | Total scoring | Matvecs |
|---|---|---:|---:|---:|---:|---:|---:|
| venice-52 | reference | 3 | 15.0 [12.0, 25.0] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 5331.0 [5270.0, 5368.0] | 23854.0 [23598.0, 23913.0] |
| venice-52 | optimized | 3 | 0.0 [0.0, 0.0] | 4.0 [4.0, 5.0] | 5.0 [5.0, 6.0] | 5656.0 [4621.0, 10337.0] | 25483.0 [21038.0, 50859.0] |
| ladybug-1197 | reference | 3 | 389.0 [293.0, 419.0] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 4452.0 [3566.0, 4497.0] | 18969.0 [16144.0, 20780.0] |
| ladybug-1197 | optimized | 3 | 211.0 [182.0, 359.0] | 41.0 [13.0, 47.0] | 217.0 [70.0, 238.0] | 3409.0 [2944.0, 4244.0] | 14400.0 [11628.0, 19049.0] |
| final-3068 | reference | 3 | 82.0 [71.0, 97.0] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 7433.0 [7332.0, 9749.0] | 33582.0 [33254.0, 46590.0] |
| final-3068 | optimized | 3 | 0.0 [0.0, 0.0] | 132.0 [112.0, 241.0] | 217.0 [139.0, 387.0] | 11412.0 [9350.0, 11498.0] | 52880.0 [45779.0, 53786.0] |
