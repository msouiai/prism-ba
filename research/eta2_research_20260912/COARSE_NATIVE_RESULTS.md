# coarse: registered native comparison

Same derived binary, algorithm off/on; original-binary compatibility is reported separately. Identical original-observation targets, audited FP64 endpoints, all overhead counted in native time. Medians [min,max] are observed ranges, not confidence intervals. Misses remain censored.

## practical

| Cell | Off hits | On hits | Off target seconds | On target seconds | Speedup | Range signal |
|---|---:|---:|---:|---:|---:|---|
| ladybug-539-1.005 | 3/3 | 3/3 | 0.0862 [0.0859, 0.0957] | 0.0860 [0.0859, 0.0927] | 1.002× | overlap |
| ladybug-539-1.01 | 3/3 | 3/3 | 0.0587 [0.0586, 0.0633] | 0.0656 [0.0655, 0.0658] | 0.895× | slower_disjoint |
| ladybug-539-1.02 | 3/3 | 3/3 | 0.0644 [0.0587, 0.0658] | 0.0630 [0.0594, 0.0652] | 1.022× | overlap |
| trafalgar-138-1.005 | 3/3 | 3/3 | 0.3075 [0.2952, 0.3232] | 0.3013 [0.3000, 0.3092] | 1.021× | overlap |
| trafalgar-138-1.01 | 3/3 | 3/3 | 0.2313 [0.2297, 0.2317] | 0.2314 [0.2299, 0.2323] | 1.000× | overlap |
| trafalgar-138-1.02 | 3/3 | 3/3 | 0.1263 [0.1262, 0.1273] | 0.1266 [0.1261, 0.1272] | 0.998× | overlap |
| final-394-1.005 | 3/3 | 3/3 | 0.2411 [0.2407, 0.2413] | 0.2414 [0.2410, 0.2417] | 0.999× | overlap |
| final-394-1.01 | 3/3 | 3/3 | 0.1713 [0.1712, 0.1717] | 0.1712 [0.1707, 0.1713] | 1.001× | overlap |
| final-394-1.02 | 3/3 | 3/3 | 0.1272 [0.1271, 0.1275] | 0.1272 [0.1271, 0.1273] | 1.000× | overlap |

| Cell / arm | Median full cost | Rejects | PCG/outer | Retry-entry / native wall | Nonaccepted / native wall | Curvature cutoffs / accepts |
|---|---:|---|---|---|---|---|
| ladybug-539-1.005 / off | 164531.8 | [0, 0, 0] | 4.78, 4.78, 4.78 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [None, None, None] |
| ladybug-539-1.005 / on | 164531.8 | [0, 0, 0] | 4.78, 4.78, 4.78 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [None, None, None] |
| ladybug-539-1.01 / off | 165514.08 | [0, 0, 0] | 6, 6, 6 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [None, None, None] |
| ladybug-539-1.01 / on | 165514.08 | [0, 0, 0] | 6, 6, 6 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [None, None, None] |
| ladybug-539-1.02 / off | 165514.08 | [0, 0, 0] | 6, 6, 6 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [None, None, None] |
| ladybug-539-1.02 / on | 165514.08 | [0, 0, 0] | 6, 6, 6 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [None, None, None] |
| trafalgar-138-1.005 / off | 102905.09 | [0, 0, 0] | 44.8, 44.8, 44.8 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [None, None, None] |
| trafalgar-138-1.005 / on | 102905.18 | [0, 0, 0] | 44.8, 44.8, 44.8 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [None, None, None] |
| trafalgar-138-1.01 / off | 103407.61 | [0, 0, 0] | 45.3, 45.3, 45.3 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [None, None, None] |
| trafalgar-138-1.01 / on | 103407.47 | [0, 0, 0] | 45.3, 45.3, 45.3 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [None, None, None] |
| trafalgar-138-1.02 / off | 104518.47 | [0, 0, 0] | 28.1, 28.1, 28.1 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [None, None, None] |
| trafalgar-138-1.02 / on | 104518.3 | [0, 0, 0] | 28.1, 28.1, 28.1 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [None, None, None] |
| final-394-1.005 / off | 305941.98 | [0, 0, 0] | 11.3, 11.3, 11.3 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [None, None, None] |
| final-394-1.005 / on | 305942.08 | [0, 0, 0] | 11.3, 11.3, 11.3 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [None, None, None] |
| final-394-1.01 / off | 306990.93 | [0, 0, 0] | 8.56, 8.56, 8.56 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [None, None, None] |
| final-394-1.01 / on | 306993.17 | [0, 0, 0] | 8.56, 8.56, 8.56 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [None, None, None] |
| final-394-1.02 / off | 309661.5 | [0, 0, 0] | 5.25, 5.25, 5.25 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [None, None, None] |
| final-394-1.02 / on | 309661.79 | [0, 0, 0] | 5.25, 5.25, 5.25 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [None, None, None] |

## tail

| Cell | Off hits | On hits | Off target seconds | On target seconds | Speedup | Range signal |
|---|---:|---:|---:|---:|---:|---|
| venice-52 | 0/5 | 0/5 | — | — | — | target_miss |
| final-3068 | 4/5 | 4/5 | 3.8133 [3.3924, 5.0908] | 4.8538 [3.2978, 5.7117] | — | target_miss |

| Cell / arm | Median full cost | Rejects | PCG/outer | Retry-entry / native wall | Nonaccepted / native wall | Curvature cutoffs / accepts |
|---|---:|---|---|---|---|---|
| venice-52 / off | 247538.58 | [5, 7, 8, 7, 10] | 1.65, 1.65, 5.95, 1.66, 3.5 | 0.0252, 0.0312, 0.0313, 0.0314, 0.0275 | 0.0446, 0.0544, 0.0539, 0.0548, 0.0498 | [0, 0, 1, 0, 1] / [None, None, None, None, None] |
| venice-52 / on | 246326.91 | [1, 2, 1, 2, 1] | 4.66, 2.17, 4.58, 3.59, 3.87 | 0.0243, 0.0238, 0.0119, 0.0237, 0.0176 | 0.0278, 0.0349, 0.0161, 0.0339, 0.0194 | [2, 1, 1, 1, 2] / [None, None, None, None, None] |
| final-3068 / off | 1740423.1 | [16, 4, 15, 4, 8] | 3.39, 3.96, 4.63, 2.75, 3.62 | 0.137, 0.054, 0.115, 0.039, 0.0897 | 0.177, 0.0697, 0.149, 0.0629, 0.11 | [1, 1, 1, 1, 1] / [None, None, None, None, None] |
| final-3068 / on | 1741993.1 | [2, 2, 14, 2, 5] | 6.13, 4.84, 2.25, 4.01, 3.77 | 0.0556, 0.0313, 0.265, 0.037, 0.0644 | 0.0572, 0.0404, 0.312, 0.0411, 0.0733 | [1, 1, 0, 1, 1] / [None, None, None, None, None] |

## Limits

CSV target times have 0.0001-second resolution. Host steady-clock attempt tracing adds no GPU barrier; numeric continuations are included, and attempt acceptance/matvec totals must match native summaries. Retry-entry and nonaccepted-attempt fractions are distinct. Endpoint overshoot at a target stop is not automatically a quality advantage.
N3 practical/N5 tail are screening cohorts. Report any larger-repetition confirmation separately. A configuration is not promoted solely by a favorable median on a subset. Frozen Eta2 remains the champion unless the complete registered gate passes.
