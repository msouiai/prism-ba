# frontload: registered native comparison

Same derived binary, algorithm off/on; original-binary compatibility is reported separately. Identical original-observation targets, audited FP64 endpoints, all overhead counted in native time. Medians [min,max] are observed ranges, not confidence intervals. Misses remain censored.

## practical

| Cell | Off hits | On hits | Off target seconds | On target seconds | Speedup | Range signal |
|---|---:|---:|---:|---:|---:|---|
| ladybug-539-1.005 | 3/3 | 3/3 | 0.0861 [0.0857, 0.0958] | 0.1244 [0.1244, 0.1368] | 0.692× | slower_disjoint |
| ladybug-539-1.01 | 3/3 | 3/3 | 0.0590 [0.0587, 0.0591] | 0.1372 [0.1247, 0.1407] | 0.430× | slower_disjoint |
| ladybug-539-1.02 | 3/3 | 3/3 | 0.0658 [0.0590, 0.0658] | 0.1063 [0.0974, 0.1287] | 0.619× | slower_disjoint |
| trafalgar-138-1.005 | 3/3 | 3/3 | 0.2932 [0.2928, 0.2934] | 0.2828 [0.2730, 0.3082] | 1.037× | overlap |
| trafalgar-138-1.01 | 3/3 | 3/3 | 0.2300 [0.2290, 0.2301] | 0.2108 [0.2103, 0.2176] | 1.091× | faster_disjoint |
| trafalgar-138-1.02 | 3/3 | 3/3 | 0.1265 [0.1261, 0.1266] | 0.1568 [0.1510, 0.1606] | 0.807× | slower_disjoint |
| final-394-1.005 | 3/3 | 3/3 | 0.2415 [0.2404, 0.2416] | 0.3769 [0.3190, 0.4093] | 0.641× | slower_disjoint |
| final-394-1.01 | 3/3 | 3/3 | 0.1710 [0.1710, 0.1713] | 0.3095 [0.2962, 0.3468] | 0.553× | slower_disjoint |
| final-394-1.02 | 3/3 | 3/3 | 0.1275 [0.1271, 0.1276] | 0.2604 [0.2458, 0.2619] | 0.490× | slower_disjoint |

| Cell / arm | Median full cost | Rejects | PCG/outer | Retry-entry / native wall | Nonaccepted / native wall | Curvature cutoffs / accepts |
|---|---:|---|---|---|---|---|
| ladybug-539-1.005 / off | 164531.79 | [0, 0, 0] | 4.78, 4.78, 4.78 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| ladybug-539-1.005 / on | 164685.93 | [0, 0, 0] | 5.75, 5.75, 5.75 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| ladybug-539-1.01 / off | 165514.08 | [0, 0, 0] | 6, 6, 6 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| ladybug-539-1.01 / on | 164685.93 | [0, 0, 0] | 5.75, 5.75, 5.75 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| ladybug-539-1.02 / off | 165514.08 | [0, 0, 0] | 6, 6, 6 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| ladybug-539-1.02 / on | 167145.03 | [0, 0, 0] | 5.8, 5.8, 5.8 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| trafalgar-138-1.005 / off | 102905.06 | [0, 0, 0] | 44.8, 44.8, 44.8 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| trafalgar-138-1.005 / on | 102947.83 | [0, 0, 0] | 36.5, 36.5, 36.5 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| trafalgar-138-1.01 / off | 103407.53 | [0, 0, 0] | 45.3, 45.3, 45.3 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| trafalgar-138-1.01 / on | 103244.73 | [0, 0, 0] | 31.4, 31.4, 31.4 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| trafalgar-138-1.02 / off | 104518.29 | [0, 0, 0] | 28.1, 28.1, 28.1 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| trafalgar-138-1.02 / on | 104398.96 | [0, 0, 0] | 24, 24, 24 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| final-394-1.005 / off | 305941.71 | [0, 0, 0] | 11.3, 11.3, 11.3 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| final-394-1.005 / on | 305601.76 | [0, 0, 0] | 16.8, 11.5, 14.8 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| final-394-1.01 / off | 306992.3 | [0, 0, 0] | 8.56, 8.56, 8.56 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| final-394-1.01 / on | 306845.6 | [0, 0, 0] | 13.9, 11.6, 10.9 | 0.0611, 0, 0 | 0.0237, 0, 0 | [1, 0, 0] / [0, 0, 0] |
| final-394-1.02 / off | 309661.8 | [0, 0, 0] | 5.25, 5.25, 5.25 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| final-394-1.02 / on | 309308.21 | [0, 0, 0] | 9.67, 8, 8 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |

## tail

| Cell | Off hits | On hits | Off target seconds | On target seconds | Speedup | Range signal |
|---|---:|---:|---:|---:|---:|---|
| venice-52 | 0/5 | 5/5 | — | 0.3733 [0.3730, 0.3830] | — | target_miss |
| final-3068 | 2/5 | 0/5 | 4.2020 [3.5458, 4.8581] | — | — | target_miss |
| ladybug-1197 | 5/5 | 5/5 | 0.2307 [0.2307, 0.2314] | 0.4117 [0.3652, 0.4391] | 0.560× | slower_disjoint |

| Cell / arm | Median full cost | Rejects | PCG/outer | Retry-entry / native wall | Nonaccepted / native wall | Curvature cutoffs / accepts |
|---|---:|---|---|---|---|---|
| venice-52 / off | 246330.22 | [10, 4, 8, 10, 2] | 5.46, 1.59, 1.67, 3.48, 2.47 | 0.0395, 0.0198, 0.0353, 0.028, 0.017 | 0.0651, 0.0295, 0.0614, 0.0463, 0.0296 | [1, 1, 0, 1, 1] / [0, 0, 0, 0, 0] |
| venice-52 / on | 243382 | [1, 1, 1, 1, 1] | 6.52, 6.52, 6.52, 6.52, 6.52 | 0.0877, 0.0663, 0.0661, 0.0662, 0.0631 | 0.0949, 0.0971, 0.0967, 0.0966, 0.0922 | [0, 0, 0, 0, 0] / [0, 0, 0, 0, 0] |
| final-3068 / off | 1800553.9 | [18, 19, 15, 3, 10] | 1.75, 3.1, 3.5, 3.45, 4.56 | 0.139, 0.141, 0.223, 0.0357, 0.0834 | 0.176, 0.183, 0.283, 0.0518, 0.111 | [0, 1, 1, 1, 1] / [0, 0, 0, 0, 0] |
| final-3068 / on | 1897761.1 | [19, 19, 16, 17, 15] | 3.03, 2.2, 2.56, 2.77, 2.06 | 0.237, 0.157, 0.18, 0.0933, 0.131 | 0.322, 0.218, 0.243, 0.138, 0.179 | [0, 0, 0, 1, 1] / [0, 0, 0, 0, 0] |
| ladybug-1197 / off | 369145.92 | [1, 1, 1, 1, 1] | 7.36, 7.36, 7.36, 7.36, 7.36 | 0.0258, 0.026, 0.0259, 0.0259, 0.0259 | 0.0781, 0.0782, 0.0779, 0.0778, 0.0776 | [0, 0, 0, 0, 0] / [0, 0, 0, 0, 0] |
| ladybug-1197 / on | 369564.08 | [1, 1, 0, 0, 0] | 11.6, 12.9, 10.1, 14.3, 14.5 | 0.173, 0.204, 0.127, 0, 0 | 0.0575, 0.0965, 0.0332, 0, 0 | [1, 1, 1, 0, 0] / [0, 0, 0, 0, 0] |

## Limits

CSV target times have 0.0001-second resolution. Host steady-clock attempt tracing adds no GPU barrier; numeric continuations are included, and attempt acceptance/matvec totals must match native summaries. Retry-entry and nonaccepted-attempt fractions are distinct. Endpoint overshoot at a target stop is not automatically a quality advantage.
N3 practical/N5 tail are screening cohorts. Report any larger-repetition confirmation separately. A configuration is not promoted solely by a favorable median on a subset. Frozen Eta2 remains the champion unless the complete registered gate passes.
