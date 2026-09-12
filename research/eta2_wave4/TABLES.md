# Wave 4 registered tail tables

Each row has its own fresh control cohort. Conditional time includes all native
setup, opening and cleanup. A dash means no observed target success. N=5 is
screening; do not pool rows or interpret a difference of one hit as established
reliability. The original observations and full-L2 targets are unchanged.

## aside

| Scene | Arm | Hits | Median final L2 | Conditional native seconds [range] | Median rejects |
|---|---|---:|---:|---:|---:|
| final-3068 | nonmonotone5 | 2/5 | 1,801,328.59 | 2.058 [1.900, 2.216] | 5 |
| final-3068 | off | 3/5 | 1,742,588.04 | 3.406 [2.349, 3.616] | 5 |
| final-3068 | rho001 | 4/5 | 1,743,557.49 | 3.472 [2.451, 4.893] | 2 |
| final-3068 | rho01 | 4/5 | 1,742,093.47 | 4.666 [3.568, 5.170] | 3 |
| venice-52 | nonmonotone5 | 0/5 | 261,126.68 | — | 0 |
| venice-52 | off | 0/5 | 246,324.76 | — | 5 |
| venice-52 | rho001 | 0/5 | 247,757.64 | — | 0 |
| venice-52 | rho01 | 0/5 | 247,757.62 | — | 0 |

## o5

| Scene | Arm | Hits | Median final L2 | Conditional native seconds [range] | Median rejects |
|---|---|---:|---:|---:|---:|
| final-3068 | cauchy | 5/5 | 1,739,664.28 | 2.602 [1.574, 6.973] | 1 |
| final-3068 | off | 4/5 | 1,742,545.66 | 4.590 [2.948, 6.591] | 7 |
| venice-52 | cauchy | 0/5 | 245,922.92 | — | 4 |
| venice-52 | off | 0/5 | 246,321.09 | — | 7 |

## o2

| Scene | Arm | Hits | Median final L2 | Conditional native seconds [range] | Median rejects |
|---|---|---:|---:|---:|---:|
| final-3068 | homotopy | 1/5 | 1,825,568.93 | 25.911 [25.911, 25.911] | 3 |
| final-3068 | off | 4/5 | 1,744,674.24 | 4.033 [1.941, 5.872] | 7 |
| venice-52 | homotopy | 0/5 | 370,203.57 | — | 3 |
| venice-52 | off | 0/5 | 246,328.97 | — | 9 |

## o1

| Scene | Arm | Hits | Median final L2 | Conditional native seconds [range] | Median rejects |
|---|---|---:|---:|---:|---:|
| final-3068 | off | 4/5 | 1,742,756.61 | 3.498 [2.786, 3.973] | 7 |
| final-3068 | oi10 | 1/5 | 1,806,589.91 | 6.082 [6.082, 6.082] | 16 |
| final-3068 | oi3 | 2/5 | 1,868,715.22 | 7.019 [6.136, 7.902] | 14 |
| final-3068 | oi5 | 2/5 | 1,769,095.51 | 5.877 [4.205, 7.549] | 14 |
| venice-52 | off | 0/5 | 247,529.64 | — | 8 |
| venice-52 | oi10 | 0/5 | 256,270.76 | — | 3 |
| venice-52 | oi3 | 0/5 | 255,833.68 | — | 3 |
| venice-52 | oi5 | 0/5 | 252,381.75 | — | 2 |

O1 Final3068 rows with zero accepted opening sweeps are Eta2 fallback outcomes
after an incomplete numerical attempt; they are **not evidence for an O1 basin
effect**. See the report and per-sweep logs for the valid/incomplete distinction.

Total scored native rows in these cohorts and gated panels: **255**.
Compatibility, memory checks, kernel tests and witness replays are separate.
