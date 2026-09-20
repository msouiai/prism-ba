# Bounded rejection study results

Exploratory: two repeats per original pilot arm; one repeat per corrected-coverage recheck arm. Medians and observed ranges are not confidence intervals.
All timed arms use full fp64 scoring, the same 600-outer budget and eight-probe backtracking.
Diagnostic runs have extra logging and are excluded from runtime comparisons.

## coverage-pilot

Completed: 24; recorded execution failures: 0.

| Scene | Arm | N | Cost median [range] | Seconds median [range] | Rejects | Rescues | Matvecs | All scoring |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| dubrovnik-173 | coverage | 2 | 374,867.730 [374,866.471, 374,868.989] | 10.724 [9.560, 11.887] | 52 | 38 | 4559.5 | 2136.5 |
| dubrovnik-173 | multi | 2 | 374,866.879 [374,866.439, 374,867.319] | 9.190 [8.743, 9.637] | 46.5 | 46 | 4319.5 | 1167 |
| dubrovnik-173 | single | 2 | 374,867.192 [374,866.795, 374,867.589] | 8.832 [8.348, 9.316] | 29 | 55.5 | 4290.5 | 638.5 |
| ladybug-1197 | coverage | 2 | 366,009.522 [365,991.180, 366,027.865] | 21.239 [20.185, 22.293] | 118 | 57 | 10724 | 4091.5 |
| ladybug-1197 | multi | 2 | 366,208.741 [366,120.684, 366,296.797] | 30.089 [23.599, 36.578] | 339.5 | 13 | 16602.5 | 3863 |
| ladybug-1197 | single | 2 | 366,166.010 [366,145.577, 366,186.444] | 14.218 [13.504, 14.932] | 0 | 3.5 | 7900.5 | 1353 |
| trafalgar-126 | coverage | 2 | 104,052.274 [103,976.463, 104,128.085] | 5.549 [3.575, 7.523] | 0 | 0 | 9375.5 | 2263 |
| trafalgar-126 | multi | 2 | 103,977.756 [103,975.207, 103,980.304] | 9.179 [6.316, 12.041] | 0 | 0 | 15806.5 | 3155 |
| trafalgar-126 | single | 2 | 104,126.558 [104,047.647, 104,205.469] | 8.132 [6.427, 9.837] | 0 | 1 | 14868 | 1896 |
| venice-52 | coverage | 2 | 242,638.773 [242,617.067, 242,660.479] | 30.005 [27.929, 32.082] | 0 | 3 | 24088 | 6111.5 |
| venice-52 | multi | 2 | 248,796.823 [248,763.207, 248,830.439] | 44.619 [25.716, 63.521] | 0 | 4 | 36790.5 | 7653.5 |
| venice-52 | single | 2 | 253,641.723 [253,439.074, 253,844.373] | 50.667 [30.337, 70.997] | 0 | 3 | 44189 | 5492.5 |

Time to 1%, 3%, 5% above the lowest endpoint observed across the pilot cohorts on each scene.
Untraced solver overhead is charged before the crossing; missing attainment stays missing.

| Scene | Arm | 1% seconds | 3% seconds | 5% seconds |
|---|---|---:|---:|---:|
| dubrovnik-173 | coverage | 1.2031 (2/2) | 0.9254 (2/2) | 0.4938 (2/2) |
| dubrovnik-173 | multi | 1.1654 (2/2) | 0.7972 (2/2) | 0.3902 (2/2) |
| dubrovnik-173 | single | 0.6441 (2/2) | 0.5289 (2/2) | 0.4262 (2/2) |
| ladybug-1197 | coverage | 5.4909 (2/2) | 1.0479 (2/2) | 0.8025 (2/2) |
| ladybug-1197 | multi | 1.8884 (2/2) | 0.9253 (2/2) | 0.7698 (2/2) |
| ladybug-1197 | single | 0.9670 (2/2) | 0.6653 (2/2) | 0.5200 (2/2) |
| trafalgar-126 | coverage | 0.4427 (2/2) | 0.3626 (2/2) | 0.2615 (2/2) |
| trafalgar-126 | multi | 0.7031 (2/2) | 0.3323 (2/2) | 0.2312 (2/2) |
| trafalgar-126 | single | 1.1121 (2/2) | 0.3575 (2/2) | 0.2909 (2/2) |
| venice-52 | coverage | 4.6997 (2/2) | 2.0884 (2/2) | 1.1087 (2/2) |
| venice-52 | multi | — (0/2) | 29.1326 (2/2) | 22.2424 (2/2) |
| venice-52 | single | — (0/2) | — (0/2) | 36.9961 (2/2) |

## rearm-pilot

Completed: 8; recorded execution failures: 0.

| Scene | Arm | N | Cost median [range] | Seconds median [range] | Rejects | Rescues | Matvecs | All scoring |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| dubrovnik-173 | multi | 2 | 374,867.530 [374,867.016, 374,868.043] | 10.730 [8.290, 13.171] | 35 | 49 | 5235 | 1252.5 |
| dubrovnik-173 | rearm | 2 | 374,892.582 [374,868.545, 374,916.619] | 7.841 [7.452, 8.229] | 22.5 | 51.5 | 3651 | 958.5 |
| ladybug-1197 | multi | 2 | 366,034.231 [366,027.948, 366,040.514] | 36.600 [36.036, 37.165] | 402.5 | 13.5 | 20188.5 | 4588.5 |
| ladybug-1197 | rearm | 2 | 365,952.002 [365,929.990, 365,974.013] | 27.598 [21.657, 33.538] | 224 | 132 | 14387.5 | 4200.5 |

Time to 1%, 3%, 5% above the lowest endpoint observed across the pilot cohorts on each scene.
Untraced solver overhead is charged before the crossing; missing attainment stays missing.

| Scene | Arm | 1% seconds | 3% seconds | 5% seconds |
|---|---|---:|---:|---:|
| dubrovnik-173 | multi | 1.1039 (2/2) | 0.8023 (2/2) | 0.3961 (2/2) |
| dubrovnik-173 | rearm | 1.0956 (2/2) | 0.8011 (2/2) | 0.3965 (2/2) |
| ladybug-1197 | multi | 1.9728 (2/2) | 1.1281 (2/2) | 0.9785 (2/2) |
| ladybug-1197 | rearm | 2.7688 (2/2) | 0.9181 (2/2) | 0.7553 (2/2) |

## coverage-v2-pilot

Completed: 8; recorded execution failures: 0.

| Scene | Arm | N | Cost median [range] | Seconds median [range] | Rejects | Rescues | Matvecs | All scoring |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| dubrovnik-173 | coverage | 1 | 374,867.888 [374,867.888, 374,867.888] | 13.845 [13.845, 13.845] | 72 | 34 | 6494 | 2273 |
| dubrovnik-173 | multi | 1 | 374,867.387 [374,867.387, 374,867.387] | 9.191 [9.191, 9.191] | 52 | 38 | 4374 | 1152 |
| ladybug-1197 | coverage | 1 | 366,098.261 [366,098.261, 366,098.261] | 17.657 [17.657, 17.657] | 104 | 41 | 8983 | 3347 |
| ladybug-1197 | multi | 1 | 366,363.795 [366,363.795, 366,363.795] | 29.543 [29.543, 29.543] | 284 | 14 | 16641 | 3617 |
| trafalgar-126 | coverage | 1 | 104,038.255 [104,038.255, 104,038.255] | 7.462 [7.462, 7.462] | 0 | 0 | 12866 | 2589 |
| trafalgar-126 | multi | 1 | 103,973.652 [103,973.652, 103,973.652] | 11.323 [11.323, 11.323] | 0 | 0 | 19129 | 3714 |
| venice-52 | coverage | 1 | 242,622.967 [242,622.967, 242,622.967] | 34.628 [34.628, 34.628] | 0 | 3 | 28265 | 6604 |
| venice-52 | multi | 1 | 248,719.800 [248,719.800, 248,719.800] | 53.271 [53.271, 53.271] | 0 | 4 | 44756 | 9097 |

Time to 1%, 3%, 5% above the lowest endpoint observed across the pilot cohorts on each scene.
Untraced solver overhead is charged before the crossing; missing attainment stays missing.

| Scene | Arm | 1% seconds | 3% seconds | 5% seconds |
|---|---|---:|---:|---:|
| dubrovnik-173 | coverage | 1.0974 (1/1) | 0.8207 (1/1) | 0.3883 (1/1) |
| dubrovnik-173 | multi | 1.0968 (1/1) | 0.7915 (1/1) | 0.3848 (1/1) |
| ladybug-1197 | coverage | 5.5617 (1/1) | 1.1091 (1/1) | 0.8718 (1/1) |
| ladybug-1197 | multi | 1.5393 (1/1) | 0.8917 (1/1) | 0.7416 (1/1) |
| trafalgar-126 | coverage | 0.4227 (1/1) | 0.3424 (1/1) | 0.2403 (1/1) |
| trafalgar-126 | multi | 1.2254 (1/1) | 0.6266 (1/1) | 0.5265 (1/1) |
| venice-52 | coverage | 4.9725 (1/1) | 2.0642 (1/1) | 1.0633 (1/1) |
| venice-52 | multi | — (0/1) | 35.2158 (1/1) | 27.8893 (1/1) |

## Logged diagnosis

| Scene/arm | Rejections | After safeguard disabled | Rejections with gate firing | Rejections without center scored | Curvature-truncated rejections | Nonfinite candidates |
|---|---:|---:|---:|---:|---:|---:|
| dubrovnik-173-multi | 51 | 51 | 29 | 25 | 0 | 0 |
| dubrovnik-173-single | 15 | 15 | 0 | 0 | 0 | 0 |
| dubrovnik-88-multi | 0 | 0 | 0 | 0 | 0 | 0 |
| dubrovnik-88-single | 0 | 0 | 0 | 0 | 0 | 0 |
| ladybug-1197-multi | 294 | 286 | 282 | 211 | 0 | 0 |
| ladybug-1197-single | 0 | 0 | 0 | 0 | 0 | 0 |
| ladybug-49-multi | 0 | 0 | 0 | 0 | 0 | 0 |
| ladybug-49-single | 0 | 0 | 0 | 0 | 0 | 0 |
| trafalgar-126-multi | 0 | 0 | 0 | 0 | 0 | 0 |
| trafalgar-126-single | 0 | 0 | 0 | 0 | 0 | 0 |
| venice-52-multi | 0 | 0 | 0 | 0 | 0 | 0 |
| venice-52-single | 0 | 0 | 0 | 0 | 0 | 0 |

These are associations on each trajectory. An unscored center is not proof it would have succeeded.

## Same-state camera/point damping forks

One saved Ladybug-1197 state at outer 40, full menu without model gating, one outer and no retries/backtracking.
Point damping and camera center varied independently; controller history is reset. This isolates a local response, not a full-run performance claim.

| Camera center | Point tau | Initial cost | Best menu cost | Final cost after optional alpha grid | Accepted |
|---:|---:|---:|---:|---:|---:|
| 0.1 | 0.0001 | 366,888.81141 | 366,876.20981 | 366,874.54634 | 1 |
| 0.0001 | 0.0001 | 366,888.81141 | 366,876.19647 | 366,874.56156 | 1 |
| 1e-07 | 0.0001 | 366,888.81141 | 366,876.19645 | 366,874.56158 | 1 |
| 0.1 | 1e-07 | 366,888.81141 | 366,860.09634 | 366,860.09634 | 1 |
| 0.0001 | 1e-07 | 366,888.81141 | 1,856,140,059.50000 | 366,888.81141 | 0 |
| 1e-07 | 1e-07 | 366,888.81141 | 1,855,944,360.70000 | 366,888.81141 | 0 |
