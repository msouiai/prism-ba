# Prism versus COLMAP Caspar: controlled fp64 comparison

All costs are `0.5 sum ||residual||²`, SIMPLE_RADIAL with fixed principal point and k2=0. Lower is better.
Every completed repeat is retained. N=3 per cell; ranges are observed ranges, not confidence or tail bounds.
Prism uses fixed Config A with cache, batched scoring, and diagonal-norm optimizations. The guarded arm adds `OCA_MENU_BACKTRACK=8`.
Prism budgets are 600 accepted outer iterations on Venice/Ladybug/final-3068 and **60 only on final-4585**.
Caspar uses COLMAP defaults with separate 200 and 2,000 iteration caps. Iteration counts are not equivalent work across algorithms.
Caspar is COLMAP’s vendored backend, run through a standalone BAL adapter; this is not a full COLMAP reconstruction pipeline benchmark.
COLMAP commit: `ed8080bcf42ef0e42d3f5d0cd21eeff0698dfde8`. Default COLMAP precision is fp32; this experiment explicitly builds its f64 backend.
Prism controls come from the completed retry study and were collected before Caspar, not interleaved with it. All use the same GPU and data hashes.
Solver wall time excludes file parsing and initial problem upload. Caspar graph setup is reported separately; Prism’s solver timer includes its internal workspace preparation. Crossings below also report Caspar with graph setup charged to avoid overstating its speed.

| Scene | Arm | N | Final cost median [range] | Solver seconds median [range] | Iterations |
|---|---|---:|---:|---:|---|
| venice-52 | prism-reference | 3 | 254,262.815 [253,853.009, 254,532.253] | 29.174 [28.945, 29.411] | 310, 327, 316 |
| venice-52 | prism-guarded | 3 | 248,721.458 [248,697.048, 248,788.146] | 31.199 [25.833, 60.616] | 293, 353, 549 |
| venice-52 | caspar200 | 3 | 272,846.984 [272,593.935, 273,369.582] | 4.474 [4.410, 4.475] | 200, 200, 200 |
| venice-52 | caspar2000 | 3 | 261,914.774 [261,769.068, 262,260.399] | 44.785 [44.662, 44.850] | 2000, 2000, 2000 |
| ladybug-1197 | prism-reference | 3 | 366,301.077 [366,281.792, 366,343.645] | 34.279 [28.513, 36.669] | 104, 147, 136 |
| ladybug-1197 | prism-guarded | 3 | 366,097.345 [365,979.905, 366,288.160] | 25.936 [21.535, 33.978] | 138, 146, 135 |
| ladybug-1197 | caspar200 | 3 | 366,879.252 [366,819.474, 366,918.986] | 5.642 [5.465, 6.024] | 200, 200, 200 |
| ladybug-1197 | caspar2000 | 3 | 366,243.610 [366,238.836, 366,244.412] | 56.534 [54.623, 56.819] | 2000, 2000, 2000 |
| final-3068 | prism-reference | 3 | 1,694,241.513 [1,675,242.368, 1,696,372.209] | 164.171 [162.951, 227.200] | 337, 330, 469 |
| final-3068 | prism-guarded | 3 | 1,696,153.924 [1,690,630.073, 1,698,754.356] | 260.499 [228.039, 264.407] | 600, 600, 600 |
| final-3068 | caspar200 | 3 | 1,977,460.495 [1,977,460.495, 1,977,460.495] | 3.210 [3.209, 3.219] | 40, 40, 40 |
| final-3068 | caspar2000 | 3 | 1,977,460.495 [1,977,460.360, 1,977,460.496] | 3.204 [3.202, 3.206] | 40, 40, 40 |
| final-4585 | prism-reference | 3 | 12,109,193.071 [12,109,193.071, 12,109,193.071] | 70.931 [70.804, 70.950] | 60, 60, 60 |
| final-4585 | prism-guarded | 3 | 8,217,450.033 [8,122,319.083, 8,222,033.919] | 51.274 [49.900, 53.043] | 60, 60, 60 |
| final-4585 | caspar200 | 3 | 12,105,689.037 [12,105,689.037, 12,105,689.037] | 34.513 [34.512, 34.520] | 200, 200, 200 |
| final-4585 | caspar2000 | 3 | 11,456,039.814 [11,456,039.814, 11,456,039.814] | 310.845 [310.830, 310.857] | 2000, 2000, 2000 |

## Endpoint quality versus Caspar 2,000

A quality difference is called resolved only when the median gap exceeds 0.15% and the observed ranges are disjoint. Negative changes favor Prism.

| Scene | Prism arm | Median cost change | Quality comparison |
|---|---|---:|---|
| venice-52 | prism-reference | -2.9215% | resolved |
| venice-52 | prism-guarded | -5.0373% | resolved |
| ladybug-1197 | prism-reference | +0.0157% | not resolved |
| ladybug-1197 | prism-guarded | -0.0399% | not resolved |
| final-3068 | prism-reference | -14.3224% | resolved |
| final-3068 | prism-guarded | -14.2256% | resolved |
| final-4585 | prism-reference | +5.7014% | resolved |
| final-4585 | prism-guarded | -28.2697% | resolved |

## Time to common objective

Targets are each fixed arm’s median endpoint, chosen mechanically after all repeats. Each cell lists all three replicates.
`—` means the target was not reached within that run’s budget; it is not an extrapolation.
Times are conservative solver-wall upper bounds: all untraced solver overhead is charged before the crossing. Values in parentheses additionally charge Caspar graph setup. No tolerance is added to the target cost.

| Scene | Target arm / cost | Measured arm | Crossing seconds, reps 1 / 2 / 3 |
|---|---|---|---|
| venice-52 | prism-reference / 254,262.815331 | prism-reference | ≤17.650 / — / ≤28.946 |
| venice-52 | prism-reference / 254,262.815331 | prism-guarded | ≤4.415 / ≤4.544 / ≤33.656 |
| venice-52 | prism-reference / 254,262.815331 | caspar200 | — / — / — |
| venice-52 | prism-reference / 254,262.815331 | caspar2000 | — / — / — |
| venice-52 | prism-guarded / 248,721.457779 | prism-reference | — / — / — |
| venice-52 | prism-guarded / 248,721.457779 | prism-guarded | — / ≤31.199 / ≤59.113 |
| venice-52 | prism-guarded / 248,721.457779 | caspar200 | — / — / — |
| venice-52 | prism-guarded / 248,721.457779 | caspar2000 | — / — / — |
| venice-52 | caspar2000 / 261,914.773694 | prism-reference | ≤3.697 / ≤4.993 / ≤3.962 |
| venice-52 | caspar2000 / 261,914.773694 | prism-guarded | ≤1.548 / ≤1.538 / ≤2.119 |
| venice-52 | caspar2000 / 261,914.773694 | caspar200 | — / — / — |
| venice-52 | caspar2000 / 261,914.773694 | caspar2000 | ≤44.363 (≤44.560) / ≤44.644 (≤44.837) / — |
| ladybug-1197 | prism-reference / 366,301.077035 | prism-reference | — / ≤32.495 / ≤36.669 |
| ladybug-1197 | prism-reference / 366,301.077035 | prism-guarded | ≤11.438 / ≤33.090 / ≤22.723 |
| ladybug-1197 | prism-reference / 366,301.077035 | caspar200 | — / — / — |
| ladybug-1197 | prism-reference / 366,301.077035 | caspar2000 | ≤21.373 (≤21.605) / ≤21.522 (≤21.731) / ≤22.594 (≤22.809) |
| ladybug-1197 | prism-guarded / 366,097.344652 | prism-reference | — / — / — |
| ladybug-1197 | prism-guarded / 366,097.344652 | prism-guarded | ≤14.958 / — / ≤25.936 |
| ladybug-1197 | prism-guarded / 366,097.344652 | caspar200 | — / — / — |
| ladybug-1197 | prism-guarded / 366,097.344652 | caspar2000 | — / — / — |
| ladybug-1197 | caspar2000 / 366,243.609717 | prism-reference | — / — / — |
| ladybug-1197 | caspar2000 / 366,243.609717 | prism-guarded | ≤12.164 / — / ≤23.078 |
| ladybug-1197 | caspar2000 / 366,243.609717 | caspar200 | — / — / — |
| ladybug-1197 | caspar2000 / 366,243.609717 | caspar2000 | ≤54.595 (≤54.826) / — / ≤51.295 (≤51.511) |
| final-3068 | prism-reference / 1,694,241.513084 | prism-reference | ≤162.951 / — / ≤112.093 |
| final-3068 | prism-reference / 1,694,241.513084 | prism-guarded | ≤205.369 / — / — |
| final-3068 | prism-reference / 1,694,241.513084 | caspar200 | — / — / — |
| final-3068 | prism-reference / 1,694,241.513084 | caspar2000 | — / — / — |
| final-3068 | prism-guarded / 1,696,153.923586 | prism-reference | ≤144.821 / — / ≤102.417 |
| final-3068 | prism-guarded / 1,696,153.923586 | prism-guarded | ≤194.973 / — / ≤260.500 |
| final-3068 | prism-guarded / 1,696,153.923586 | caspar200 | — / — / — |
| final-3068 | prism-guarded / 1,696,153.923586 | caspar2000 | — / — / — |
| final-3068 | caspar2000 / 1,977,460.494577 | prism-reference | ≤2.831 / ≤2.848 / ≤2.842 |
| final-3068 | caspar2000 / 1,977,460.494577 | prism-guarded | ≤2.507 / ≤2.533 / ≤2.546 |
| final-3068 | caspar2000 / 1,977,460.494577 | caspar200 | — / — / — |
| final-3068 | caspar2000 / 1,977,460.494577 | caspar2000 | ≤3.203 (≤3.578) / — / ≤3.206 (≤3.523) |
| final-4585 | prism-reference / 12,109,193.070959 | prism-reference | ≤70.804 / ≤70.951 / ≤70.931 |
| final-4585 | prism-reference / 12,109,193.070959 | prism-guarded | ≤2.867 / ≤2.874 / ≤2.872 |
| final-4585 | prism-reference / 12,109,193.070959 | caspar200 | ≤33.976 (≤35.103) / ≤33.978 (≤35.074) / ≤33.984 (≤35.095) |
| final-4585 | prism-reference / 12,109,193.070959 | caspar2000 | ≤33.983 (≤35.174) / ≤33.989 (≤35.069) / ≤33.974 (≤35.109) |
| final-4585 | prism-guarded / 8,217,450.033194 | prism-reference | — / — / — |
| final-4585 | prism-guarded / 8,217,450.033194 | prism-guarded | ≤36.463 / — / ≤49.901 |
| final-4585 | prism-guarded / 8,217,450.033194 | caspar200 | — / — / — |
| final-4585 | prism-guarded / 8,217,450.033194 | caspar2000 | — / — / — |
| final-4585 | caspar2000 / 11,456,039.813929 | prism-reference | — / — / — |
| final-4585 | caspar2000 / 11,456,039.813929 | prism-guarded | ≤2.867 / ≤2.874 / ≤2.872 |
| final-4585 | caspar2000 / 11,456,039.813929 | caspar200 | — / — / — |
| final-4585 | caspar2000 / 11,456,039.813929 | caspar2000 | — / ≤310.790 (≤311.869) / ≤310.776 (≤311.911) |

## Validation and stopping

| Scene | Caspar budget | Exit codes, reps 1 / 2 / 3 | Graph setup seconds median [range] | Max initial relative error | Max final relative error |
|---|---:|---|---:|---:|---:|
| venice-52 | 200 | 0 / 0 / 0 | 0.197 [0.190, 0.313] | 4.01e-15 | 1.92e-15 |
| venice-52 | 2000 | 0 / 0 / 0 | 0.197 [0.193, 0.240] | 4.18e-15 | 8.88e-16 |
| ladybug-1197 | 200 | 0 / 0 / 0 | 0.216 [0.214, 0.216] | 1.4e-11 | 3.81e-12 |
| ladybug-1197 | 2000 | 0 / 0 / 0 | 0.216 [0.209, 0.231] | 1.4e-11 | 2.68e-12 |
| final-3068 | 200 | 2 / 2 / 2 | 0.350 [0.329, 0.417] | 3.7e-11 | 8.24e-15 |
| final-3068 | 2000 | 2 / 2 / 2 | 0.375 [0.316, 0.377] | 3.7e-11 | 8.83e-15 |
| final-4585 | 200 | 0 / 0 / 0 | 1.111 [1.096, 1.127] | 1.98e-15 | 4.31e-15 |
| final-4585 | 2000 | 0 / 0 / 0 | 1.135 [1.079, 1.190] | 2.18e-15 | 3.25e-15 |

Exit 0 = iteration cap; 1 = absolute score threshold; 2 = damping exceeded threshold. A damping exit is not a proof of convergence.
Initial costs are checked independently with NumPy at relative tolerance 1e-6; final Caspar costs are checked from returned poses/intrinsics/points by a separate CPU projection loop at the same tolerance.
Logging-only instrumentation populates upstream’s unassigned `initial_score` result field. Acceptance is inferred from cost decreases because this revision never updates its `step_accepted` logging field. Solver decisions are unchanged.

Raw Caspar logs, per-run JSON and manifest: `/workspace/caspar-comparison/runs`. Prism source directories are recorded in the manifest.
