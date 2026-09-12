# passenger: registered native comparison

Same derived binary, algorithm off/on; original-binary compatibility is reported separately. Identical original-observation targets, audited FP64 endpoints, all overhead counted in native time. Medians [min,max] are observed ranges, not confidence intervals. Misses remain censored.

## practical

| Cell | Off hits | On hits | Off target seconds | On target seconds | Speedup | Range signal |
|---|---:|---:|---:|---:|---:|---|
| ladybug-539-1.005 | 3/3 | 3/3 | 0.0865 [0.0858, 0.0957] | 0.0857 [0.0856, 0.0958] | 1.009× | overlap |
| ladybug-539-1.01 | 3/3 | 3/3 | 0.0590 [0.0587, 0.0656] | 0.0650 [0.0591, 0.0657] | 0.908× | overlap |
| ladybug-539-1.02 | 3/3 | 3/3 | 0.0652 [0.0591, 0.0657] | 0.0651 [0.0592, 0.0657] | 1.002× | overlap |
| trafalgar-138-1.005 | 3/3 | 3/3 | 0.3127 [0.2934, 0.3195] | 0.2939 [0.2939, 0.2940] | 1.064× | overlap |
| trafalgar-138-1.01 | 3/3 | 3/3 | 0.2305 [0.2301, 0.2314] | 0.2304 [0.2302, 0.2313] | 1.000× | overlap |
| trafalgar-138-1.02 | 3/3 | 3/3 | 0.1265 [0.1261, 0.1267] | 0.1266 [0.1264, 0.1266] | 0.999× | overlap |
| final-394-1.005 | 3/3 | 3/3 | 0.2409 [0.2404, 0.2410] | 0.2402 [0.2401, 0.2408] | 1.003× | overlap |
| final-394-1.01 | 3/3 | 3/3 | 0.1702 [0.1701, 0.1714] | 0.1704 [0.1702, 0.1708] | 0.999× | overlap |
| final-394-1.02 | 3/3 | 3/3 | 0.1265 [0.1264, 0.1270] | 0.1267 [0.1265, 0.1273] | 0.998× | overlap |

| Cell / arm | Median full cost | Rejects | PCG/outer | Retry-entry / native wall | Nonaccepted / native wall | Curvature cutoffs / accepts |
|---|---:|---|---|---|---|---|
| ladybug-539-1.005 / off | 164531.79 | [0, 0, 0] | 4.78, 4.78, 4.78 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| ladybug-539-1.005 / on | 164531.79 | [0, 0, 0] | 4.78, 4.78, 4.78 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| ladybug-539-1.01 / off | 165514.08 | [0, 0, 0] | 6, 6, 6 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| ladybug-539-1.01 / on | 165514.08 | [0, 0, 0] | 6, 6, 6 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| ladybug-539-1.02 / off | 165514.08 | [0, 0, 0] | 6, 6, 6 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| ladybug-539-1.02 / on | 165514.08 | [0, 0, 0] | 6, 6, 6 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| trafalgar-138-1.005 / off | 102905.14 | [0, 0, 0] | 44.8, 44.8, 44.8 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| trafalgar-138-1.005 / on | 102905.08 | [0, 0, 0] | 44.8, 44.8, 44.8 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| trafalgar-138-1.01 / off | 103407.48 | [0, 0, 0] | 45.3, 45.3, 45.3 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| trafalgar-138-1.01 / on | 103407.45 | [0, 0, 0] | 45.3, 45.3, 45.3 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| trafalgar-138-1.02 / off | 104518.5 | [0, 0, 0] | 28.1, 28.1, 28.1 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| trafalgar-138-1.02 / on | 104518.5 | [0, 0, 0] | 28.1, 28.1, 28.1 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| final-394-1.005 / off | 305937.91 | [0, 0, 0] | 11.3, 11.3, 11.3 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| final-394-1.005 / on | 305938 | [0, 0, 0] | 11.3, 11.3, 11.3 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| final-394-1.01 / off | 306993.02 | [0, 0, 0] | 8.56, 8.56, 8.56 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| final-394-1.01 / on | 306993.49 | [0, 0, 0] | 8.56, 8.56, 8.56 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| final-394-1.02 / off | 309661.79 | [0, 0, 0] | 5.25, 5.25, 5.25 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| final-394-1.02 / on | 309661.5 | [0, 0, 0] | 5.25, 5.25, 5.25 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |

## tail

| Cell | Off hits | On hits | Off target seconds | On target seconds | Speedup | Range signal |
|---|---:|---:|---:|---:|---:|---|
| venice-52 | 0/5 | 0/5 | — | — | — | target_miss |
| final-3068 | 4/5 | 4/5 | 3.1194 [1.7829, 4.0271] | 3.6059 [3.5136, 5.5624] | — | target_miss |

| Cell / arm | Median full cost | Rejects | PCG/outer | Retry-entry / native wall | Nonaccepted / native wall | Curvature cutoffs / accepts |
|---|---:|---|---|---|---|---|
| venice-52 / off | 247562.94 | [6, 12, 5, 1, 7] | 1.65, 1.58, 3.68, 2.01, 1.7 | 0.0281, 0.029, 0.0242, 0.0122, 0.0321 | 0.0494, 0.0458, 0.043, 0.0199, 0.0561 | [0, 1, 1, 0, 0] / [0, 0, 0, 0, 0] |
| venice-52 / on | 246321.36 | [7, 1, 6, 2, 2] | 5.68, 1.95, 6.88, 2.17, 4.58 | 0.0262, 0.00735, 0.0232, 0.0105, 0.0126 | 0.0451, 0.012, 0.0387, 0.0163, 0.0203 | [1, 1, 1, 1, 1] / [0, 0, 0, 0, 0] |
| final-3068 / off | 1741668.9 | [8, 1, 17, 3, 1] | 5.16, 6.72, 2.94, 3.55, 3.25 | 0.0955, 0.0378, 0.0848, 0.0353, 0.018 | 0.119, 0.0444, 0.122, 0.0375, 0.0283 | [1, 1, 1, 1, 1] / [0, 0, 0, 0, 0] |
| final-3068 / on | 1743477.7 | [4, 15, 7, 15, 5] | 3.42, 2.87, 3.49, 1.73, 3.77 | 0.0535, 0.104, 0.0831, 0.146, 0.0575 | 0.0639, 0.135, 0.115, 0.194, 0.0891 | [1, 1, 1, 0, 1] / [0, 0, 0, 0, 0] |

| Cell / arm | Terminal probe / native wall |
|---|---|
| venice-52 / off | 0, 0, 0, 0, 0 |
| venice-52 / on | 0.03118, 0.02714, 0.03073, 0.02661, 0.03473 |
| final-3068 / off | 0, 0, 0, 0, 0 |
| final-3068 / on | 0, 0, 0, 0.07289, 0 |

## Limits

CSV target times have 0.0001-second resolution. Host steady-clock attempt tracing adds no GPU barrier; numeric continuations are included, and attempt acceptance/matvec totals must match native summaries. Retry-entry and nonaccepted-attempt fractions are distinct. Endpoint overshoot at a target stop is not automatically a quality advantage.
For passenger and soft-kick arms, ordinary LM retry/failure fractions exclude the terminal probe; its fresh fine setup and intervention are reported separately. Legacy raw result stop_ftol means an FTOL message was seen, which can precede an intercepted stop and continuation; summary ftol_marker_runs is not a certified final-stop-reason count. Full score_init values are retained in the companion JSON.
N3 practical/N5 tail are screening cohorts. Report any larger-repetition confirmation separately. A configuration is not promoted solely by a favorable median on a subset. Frozen Eta2 remains the champion unless the complete registered gate passes.
