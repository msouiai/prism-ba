# pi: registered native comparison

Same derived binary, algorithm off/on; original-binary compatibility is reported separately. Identical original-observation targets, audited FP64 endpoints, all overhead counted in native time. Medians [min,max] are observed ranges, not confidence intervals. Misses remain censored.

## practical

| Cell | Off hits | On hits | Off target seconds | On target seconds | Speedup | Range signal |
|---|---:|---:|---:|---:|---:|---|
| ladybug-539-1.005 | 3/3 | 3/3 | 0.0862 [0.0862, 0.0950] | 0.0862 [0.0858, 0.0962] | 1.000× | overlap |
| ladybug-539-1.01 | 3/3 | 3/3 | 0.0600 [0.0589, 0.0655] | 0.0596 [0.0588, 0.0656] | 1.007× | overlap |
| ladybug-539-1.02 | 3/3 | 3/3 | 0.0653 [0.0586, 0.0657] | 0.0636 [0.0587, 0.0653] | 1.027× | overlap |
| trafalgar-138-1.005 | 3/3 | 3/3 | 0.3091 [0.2925, 0.3189] | 0.2894 [0.2889, 0.2904] | 1.068× | faster_disjoint |
| trafalgar-138-1.01 | 3/3 | 3/3 | 0.2305 [0.2289, 0.2312] | 0.2282 [0.2276, 0.2288] | 1.010× | faster_disjoint |
| trafalgar-138-1.02 | 3/3 | 3/3 | 0.1267 [0.1264, 0.1268] | 0.1267 [0.1262, 0.1269] | 1.000× | overlap |
| final-394-1.005 | 3/3 | 3/3 | 0.2409 [0.2400, 0.2430] | 0.2296 [0.2288, 0.2303] | 1.049× | faster_disjoint |
| final-394-1.01 | 3/3 | 3/3 | 0.1709 [0.1706, 0.1709] | 0.1748 [0.1742, 0.1756] | 0.978× | slower_disjoint |
| final-394-1.02 | 3/3 | 3/3 | 0.1268 [0.1266, 0.1273] | 0.1257 [0.1253, 0.1259] | 1.009× | faster_disjoint |

| Cell / arm | Median full cost | Rejects | PCG/outer | Retry-entry / native wall | Nonaccepted / native wall | Curvature cutoffs / accepts |
|---|---:|---|---|---|---|---|
| ladybug-539-1.005 / off | 164531.79 | [0, 0, 0] | 4.78, 4.78, 4.78 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| ladybug-539-1.005 / on | 164531.19 | [0, 0, 0] | 4.78, 4.78, 4.78 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| ladybug-539-1.01 / off | 165514.08 | [0, 0, 0] | 6, 6, 6 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| ladybug-539-1.01 / on | 165514.08 | [0, 0, 0] | 6, 6, 6 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| ladybug-539-1.02 / off | 165514.08 | [0, 0, 0] | 6, 6, 6 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| ladybug-539-1.02 / on | 165514.08 | [0, 0, 0] | 6, 6, 6 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| trafalgar-138-1.005 / off | 102905.07 | [0, 0, 0] | 44.8, 44.8, 44.8 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| trafalgar-138-1.005 / on | 103073.77 | [0, 0, 0] | 48.5, 48.5, 48.5 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| trafalgar-138-1.01 / off | 103407.8 | [0, 0, 0] | 45.3, 45.3, 45.3 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| trafalgar-138-1.01 / on | 103413.54 | [0, 0, 0] | 45.3, 45.3, 45.3 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| trafalgar-138-1.02 / off | 104518.54 | [0, 0, 0] | 28.1, 28.1, 28.1 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| trafalgar-138-1.02 / on | 104551.82 | [0, 0, 0] | 28.1, 28.1, 28.1 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| final-394-1.005 / off | 305942.02 | [0, 0, 0] | 11.3, 11.3, 11.3 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| final-394-1.005 / on | 306024.27 | [0, 0, 0] | 10.6, 10.6, 10.6 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| final-394-1.01 / off | 306989.31 | [0, 0, 0] | 8.56, 8.56, 8.56 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| final-394-1.01 / on | 307021.75 | [0, 0, 0] | 9, 9, 9 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| final-394-1.02 / off | 309661.54 | [0, 0, 0] | 5.25, 5.25, 5.25 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| final-394-1.02 / on | 310044.82 | [0, 0, 0] | 5.62, 5.62, 5.62 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |

## tail

| Cell | Off hits | On hits | Off target seconds | On target seconds | Speedup | Range signal |
|---|---:|---:|---:|---:|---:|---|
| venice-52 | 0/5 | 0/5 | — | — | — | target_miss |
| final-3068 | 1/5 | 2/5 | 4.1371 [4.1371, 4.1371] | 3.4479 [3.2927, 3.6031] | — | target_miss |

| Cell / arm | Median full cost | Rejects | PCG/outer | Retry-entry / native wall | Nonaccepted / native wall | Curvature cutoffs / accepts |
|---|---:|---|---|---|---|---|
| venice-52 / off | 246344.45 | [6, 2, 11, 1, 1] | 1.68, 2.43, 1.87, 1.76, 1.64 | 0.0287, 0.0184, 0.0349, 0.0148, 0.00975 | 0.0503, 0.0295, 0.0526, 0.0234, 0.0154 | [0, 1, 1, 1, 1] / [0, 0, 0, 0, 0] |
| venice-52 / on | 276621.42 | [2, 1, 7, 2, 2] | 4.13, 3.37, 3.52, 3.95, 10.4 | 0.0113, 0.00854, 0.0265, 0.00959, 0.0076 | 0.0205, 0.0159, 0.0363, 0.0146, 0.0159 | [1, 1, 1, 1, 0] / [0, 0, 0, 0, 0] |
| final-3068 / off | 1832083.1 | [8, 15, 11, 12, 10] | 4.03, 2.54, 5.62, 1.55, 3.27 | 0.0804, 0.171, 0.127, 0.0861, 0.0904 | 0.111, 0.216, 0.184, 0.122, 0.128 | [1, 1, 1, 1, 1] / [0, 0, 0, 0, 0] |
| final-3068 / on | 1807501.2 | [14, 2, 12, 13, 1] | 3.82, 3.12, 3.9, 3.32, 3.24 | 0.159, 0.0154, 0.11, 0.085, 0.0146 | 0.201, 0.0301, 0.135, 0.0982, 0.0191 | [1, 1, 1, 1, 1] / [0, 0, 0, 0, 0] |

## Limits

CSV target times have 0.0001-second resolution. Host steady-clock attempt tracing adds no GPU barrier; numeric continuations are included, and attempt acceptance/matvec totals must match native summaries. Retry-entry and nonaccepted-attempt fractions are distinct. Endpoint overshoot at a target stop is not automatically a quality advantage.
For passenger and soft-kick arms, ordinary LM retry/failure fractions exclude the terminal probe; its fresh fine setup and intervention are reported separately. Legacy raw result stop_ftol means an FTOL message was seen, which can precede an intercepted stop and continuation; summary ftol_marker_runs is not a certified final-stop-reason count. Full score_init values are retained in the companion JSON.
N3 practical/N5 tail are screening cohorts. Report any larger-repetition confirmation separately. A configuration is not promoted solely by a favorable median on a subset. Frozen Eta2 remains the champion unless the complete registered gate passes.
