# stcg: registered native comparison

Same derived binary, algorithm off/on; original-binary compatibility is reported separately. Identical original-observation targets, audited FP64 endpoints, all overhead counted in native time. Medians [min,max] are observed ranges, not confidence intervals. Misses remain censored.

## practical

| Cell | Off hits | On hits | Off target seconds | On target seconds | Speedup | Range signal |
|---|---:|---:|---:|---:|---:|---|
| ladybug-539-1.005 | 3/3 | 3/3 | 0.0859 [0.0859, 0.0953] | 0.0880 [0.0863, 0.0916] | 0.976× | overlap |
| ladybug-539-1.01 | 3/3 | 3/3 | 0.0597 [0.0585, 0.0635] | 0.0658 [0.0594, 0.0660] | 0.907× | overlap |
| ladybug-539-1.02 | 3/3 | 3/3 | 0.0656 [0.0587, 0.0659] | 0.0644 [0.0594, 0.0659] | 1.019× | overlap |
| trafalgar-138-1.005 | 3/3 | 3/3 | 0.3021 [0.2924, 0.3247] | 0.3557 [0.3555, 0.3560] | 0.849× | slower_disjoint |
| trafalgar-138-1.01 | 3/3 | 3/3 | 0.2294 [0.2289, 0.2298] | 0.2375 [0.2373, 0.2379] | 0.966× | slower_disjoint |
| trafalgar-138-1.02 | 3/3 | 3/3 | 0.1262 [0.1262, 0.1263] | 0.1298 [0.1298, 0.1302] | 0.972× | slower_disjoint |
| final-394-1.005 | 3/3 | 3/3 | 0.2404 [0.2403, 0.2404] | 0.2043 [0.2041, 0.2044] | 1.177× | faster_disjoint |
| final-394-1.01 | 3/3 | 3/3 | 0.1706 [0.1705, 0.1707] | 0.1397 [0.1397, 0.1399] | 1.221× | faster_disjoint |
| final-394-1.02 | 3/3 | 3/3 | 0.1271 [0.1267, 0.1271] | 0.1401 [0.1397, 0.1402] | 0.907× | slower_disjoint |

| Cell / arm | Median full cost | Rejects | PCG/outer | Retry-entry / native wall | Nonaccepted / native wall | Curvature cutoffs / accepts |
|---|---:|---|---|---|---|---|
| ladybug-539-1.005 / off | 164531.79 | [0, 0, 0] | 4.78, 4.78, 4.78 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| ladybug-539-1.005 / on | 164531.19 | [0, 0, 0] | 4.78, 4.78, 4.78 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| ladybug-539-1.01 / off | 165514.08 | [0, 0, 0] | 6, 6, 6 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| ladybug-539-1.01 / on | 165514.08 | [0, 0, 0] | 6, 6, 6 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| ladybug-539-1.02 / off | 165514.08 | [0, 0, 0] | 6, 6, 6 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| ladybug-539-1.02 / on | 165514.08 | [0, 0, 0] | 6, 6, 6 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| trafalgar-138-1.005 / off | 102905.08 | [0, 0, 0] | 44.8, 44.8, 44.8 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| trafalgar-138-1.005 / on | 103006.28 | [1, 1, 1] | 53.3, 53.3, 53.3 | 0.0809, 0.0777, 0.0809 | 0.159, 0.154, 0.159 | [0, 0, 0] / [0, 0, 0] |
| trafalgar-138-1.01 / off | 103407.58 | [0, 0, 0] | 45.3, 45.3, 45.3 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| trafalgar-138-1.01 / on | 103519.35 | [0, 0, 0] | 45.3, 45.3, 45.3 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| trafalgar-138-1.02 / off | 104518.5 | [0, 0, 0] | 28.1, 28.1, 28.1 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| trafalgar-138-1.02 / on | 104534.36 | [0, 0, 0] | 28.1, 28.1, 28.1 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| final-394-1.005 / off | 305941.93 | [0, 0, 0] | 11.3, 11.3, 11.3 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| final-394-1.005 / on | 305989.7 | [0, 0, 0] | 10.4, 10.4, 10.4 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| final-394-1.01 / off | 306991.87 | [0, 0, 0] | 8.56, 8.56, 8.56 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| final-394-1.01 / on | 307834.08 | [0, 0, 0] | 7.38, 7.38, 7.38 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| final-394-1.02 / off | 309661.8 | [0, 0, 0] | 5.25, 5.25, 5.25 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| final-394-1.02 / on | 307834.08 | [0, 0, 0] | 7.38, 7.38, 7.38 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |

## tail

| Cell | Off hits | On hits | Off target seconds | On target seconds | Speedup | Range signal |
|---|---:|---:|---:|---:|---:|---|
| venice-52 | 0/5 | 0/5 | — | — | — | target_miss |
| final-3068 | 4/5 | 0/5 | 2.8371 [1.3569, 3.6837] | — | — | target_miss |

| Cell / arm | Median full cost | Rejects | PCG/outer | Retry-entry / native wall | Nonaccepted / native wall | Curvature cutoffs / accepts |
|---|---:|---|---|---|---|---|
| venice-52 / off | 247566.9 | [7, 5, 7, 7, 1] | 1.67, 1.67, 1.69, 1.67, 1.63 | 0.032, 0.0252, 0.0321, 0.0315, 0.0097 | 0.0557, 0.0448, 0.056, 0.0552, 0.0154 | [0, 0, 0, 0, 1] / [0, 0, 0, 0, 0] |
| venice-52 / on | 258003.99 | [2, 2, 2, 2, 2] | 1.56, 1.56, 1.56, 1.56, 1.56 | 0.0123, 0.0127, 0.0127, 0.0127, 0.0127 | 0.025, 0.0257, 0.0257, 0.0257, 0.0258 | [0, 0, 0, 0, 0] / [0, 0, 0, 0, 0] |
| final-3068 / off | 1741661.8 | [0, 2, 17, 1, 6] | 5.71, 6.03, 5.65, 3.29, 5.36 | 0.0212, 0.0376, 0.202, 0.02, 0.0655 | 0.0185, 0.0582, 0.29, 0.0243, 0.087 | [1, 1, 1, 1, 1] / [0, 0, 0, 0, 0] |
| final-3068 / on | 1821191.7 | [19, 20, 95, 19, 13] | 2.19, 1.74, 1.58, 1.69, 3.13 | 0.164, 0.116, 0.163, 0.0871, 0.201 | 0.205, 0.171, 0.28, 0.135, 0.268 | [3, 23, 25, 21, 1] / [1, 13, 10, 13, 0] |

## Limits

CSV target times have 0.0001-second resolution. Host steady-clock attempt tracing adds no GPU barrier; numeric continuations are included, and attempt acceptance/matvec totals must match native summaries. Retry-entry and nonaccepted-attempt fractions are distinct. Endpoint overshoot at a target stop is not automatically a quality advantage.
For passenger and soft-kick arms, ordinary LM retry/failure fractions exclude the terminal probe; its fresh fine setup and intervention are reported separately. Legacy raw result stop_ftol means an FTOL message was seen, which can precede an intercepted stop and continuation; summary ftol_marker_runs is not a certified final-stop-reason count. Full score_init values are retained in the companion JSON.
N3 practical/N5 tail are screening cohorts. Report any larger-repetition confirmation separately. A configuration is not promoted solely by a favorable median on a subset. Frozen Eta2 remains the champion unless the complete registered gate passes.
