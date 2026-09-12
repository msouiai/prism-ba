# soft_kick: registered native comparison

Same derived binary, algorithm off/on; original-binary compatibility is reported separately. Identical original-observation targets, audited FP64 endpoints, all overhead counted in native time. Medians [min,max] are observed ranges, not confidence intervals. Misses remain censored.

## practical

| Cell | Off hits | On hits | Off target seconds | On target seconds | Speedup | Range signal |
|---|---:|---:|---:|---:|---:|---|
| ladybug-539-1.005 | 3/3 | 3/3 | 0.0870 [0.0868, 0.0954] | 0.0962 [0.0861, 0.0963] | 0.904× | overlap |
| ladybug-539-1.01 | 3/3 | 3/3 | 0.0592 [0.0586, 0.0656] | 0.0655 [0.0590, 0.0660] | 0.904× | overlap |
| ladybug-539-1.02 | 3/3 | 3/3 | 0.0632 [0.0591, 0.0650] | 0.0629 [0.0591, 0.0654] | 1.005× | overlap |
| trafalgar-138-1.005 | 3/3 | 3/3 | 0.3044 [0.2933, 0.3051] | 0.2936 [0.2928, 0.2938] | 1.037× | overlap |
| trafalgar-138-1.01 | 3/3 | 3/3 | 0.2304 [0.2300, 0.2305] | 0.2304 [0.2303, 0.2306] | 1.000× | overlap |
| trafalgar-138-1.02 | 3/3 | 3/3 | 0.1268 [0.1266, 0.1268] | 0.1266 [0.1260, 0.1266] | 1.002× | overlap |
| final-394-1.005 | 3/3 | 3/3 | 0.2410 [0.2405, 0.2413] | 0.2401 [0.2397, 0.2412] | 1.004× | overlap |
| final-394-1.01 | 3/3 | 3/3 | 0.1705 [0.1701, 0.1710] | 0.1706 [0.1704, 0.1709] | 0.999× | overlap |
| final-394-1.02 | 3/3 | 3/3 | 0.1268 [0.1264, 0.1273] | 0.1267 [0.1264, 0.1273] | 1.001× | overlap |

| Cell / arm | Median full cost | Rejects | PCG/outer | Retry-entry / native wall | Nonaccepted / native wall | Curvature cutoffs / accepts |
|---|---:|---|---|---|---|---|
| ladybug-539-1.005 / off | 164531.8 | [0, 0, 0] | 4.78, 4.78, 4.78 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| ladybug-539-1.005 / on | 164531.79 | [0, 0, 0] | 4.78, 4.78, 4.78 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| ladybug-539-1.01 / off | 165514.08 | [0, 0, 0] | 6, 6, 6 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| ladybug-539-1.01 / on | 165514.08 | [0, 0, 0] | 6, 6, 6 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| ladybug-539-1.02 / off | 165514.08 | [0, 0, 0] | 6, 6, 6 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| ladybug-539-1.02 / on | 165514.08 | [0, 0, 0] | 6, 6, 6 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| trafalgar-138-1.005 / off | 102905.13 | [0, 0, 0] | 44.8, 44.8, 44.8 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| trafalgar-138-1.005 / on | 102905.09 | [0, 0, 0] | 44.8, 44.8, 44.8 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| trafalgar-138-1.01 / off | 103407.69 | [0, 0, 0] | 45.3, 45.3, 45.3 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| trafalgar-138-1.01 / on | 103407.49 | [0, 0, 0] | 45.3, 45.3, 45.3 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| trafalgar-138-1.02 / off | 104518.53 | [0, 0, 0] | 28.1, 28.1, 28.1 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| trafalgar-138-1.02 / on | 104518.47 | [0, 0, 0] | 28.1, 28.1, 28.1 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| final-394-1.005 / off | 305941.92 | [0, 0, 0] | 11.3, 11.3, 11.3 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| final-394-1.005 / on | 305941.96 | [0, 0, 0] | 11.3, 11.3, 11.3 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| final-394-1.01 / off | 306990.67 | [0, 0, 0] | 8.56, 8.56, 8.56 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| final-394-1.01 / on | 306993.52 | [0, 0, 0] | 8.56, 8.56, 8.56 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| final-394-1.02 / off | 309661.79 | [0, 0, 0] | 5.25, 5.25, 5.25 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| final-394-1.02 / on | 309661.8 | [0, 0, 0] | 5.25, 5.25, 5.25 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |

## tail

| Cell | Off hits | On hits | Off target seconds | On target seconds | Speedup | Range signal |
|---|---:|---:|---:|---:|---:|---|
| venice-52 | 0/5 | 0/5 | — | — | — | target_miss |
| final-3068 | 3/5 | 3/5 | 3.7093 [3.5160, 3.7937] | 3.5142 [2.1076, 4.1243] | — | target_miss |

| Cell / arm | Median full cost | Rejects | PCG/outer | Retry-entry / native wall | Nonaccepted / native wall | Curvature cutoffs / accepts |
|---|---:|---|---|---|---|---|
| venice-52 / off | 246448.22 | [6, 11, 1, 1, 7] | 1.65, 1.56, 1.76, 1.81, 1.67 | 0.0253, 0.0339, 0.0176, 0.00873, 0.0318 | 0.0444, 0.0583, 0.0278, 0.0143, 0.0556 | [0, 1, 1, 1, 0] / [0, 0, 0, 0, 0] |
| venice-52 / on | 244956.25 | [1, 13, 11, 11, 8] | 1.79, 1.97, 2.02, 2.12, 1.84 | 0.00938, 0.038, 0.0331, 0.0363, 0.0337 | 0.0152, 0.0589, 0.0647, 0.0586, 0.0586 | [0, 1, 1, 1, 1] / [0, 0, 0, 0, 0] |
| final-3068 / off | 1741000 | [25, 13, 2, 4, 5] | 2.9, 2.03, 3.61, 4.58, 4.47 | 0.132, 0.174, 0.032, 0.0397, 0.0583 | 0.175, 0.227, 0.0361, 0.0584, 0.079 | [1, 0, 1, 1, 1] / [0, 0, 0, 0, 0] |
| final-3068 / on | 1743445 | [20, 3, 8, 23, 6] | 1.67, 8.24, 7.09, 2.66, 3.21 | 0.113, 0.0701, 0.0872, 0.203, 0.0575 | 0.151, 0.0921, 0.124, 0.239, 0.0917 | [1, 1, 1, 2, 1] / [0, 0, 0, 0, 0] |

| Cell / arm | Terminal probe / native wall |
|---|---|
| venice-52 / off | 0, 0, 0, 0, 0 |
| venice-52 / on | 0.01306, 0.006199, 0.007659, 0.007179, 0.008621 |
| final-3068 / off | 0, 0, 0, 0, 0 |
| final-3068 / on | 0.01394, 0, 0, 0.01637, 0 |

## Limits

CSV target times have 0.0001-second resolution. Host steady-clock attempt tracing adds no GPU barrier; numeric continuations are included, and attempt acceptance/matvec totals must match native summaries. Retry-entry and nonaccepted-attempt fractions are distinct. Endpoint overshoot at a target stop is not automatically a quality advantage.
For passenger and soft-kick arms, ordinary LM retry/failure fractions exclude the terminal probe; its fresh fine setup and intervention are reported separately. Legacy raw result stop_ftol means an FTOL message was seen, which can precede an intercepted stop and continuation; summary ftol_marker_runs is not a certified final-stop-reason count. Full score_init values are retained in the companion JSON.
N3 practical/N5 tail are screening cohorts. Report any larger-repetition confirmation separately. A configuration is not promoted solely by a favorable median on a subset. Frozen Eta2 remains the champion unless the complete registered gate passes.
