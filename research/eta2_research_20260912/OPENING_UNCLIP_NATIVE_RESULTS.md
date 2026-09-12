# opening_unclip: registered native comparison

Same derived binary, algorithm off/on; original-binary compatibility is reported separately. Identical original-observation targets, audited FP64 endpoints, all overhead counted in native time. Medians [min,max] are observed ranges, not confidence intervals. Misses remain censored.

## practical

| Cell | Off hits | On hits | Off target seconds | On target seconds | Speedup | Range signal |
|---|---:|---:|---:|---:|---:|---|
| ladybug-539-1.005 | 3/3 | 3/3 | 0.0876 [0.0864, 0.0950] | 0.0863 [0.0861, 0.0924] | 1.015× | overlap |
| ladybug-539-1.01 | 3/3 | 3/3 | 0.0648 [0.0589, 0.0657] | 0.0656 [0.0588, 0.0656] | 0.988× | overlap |
| ladybug-539-1.02 | 3/3 | 3/3 | 0.0638 [0.0593, 0.0651] | 0.0628 [0.0591, 0.0655] | 1.016× | overlap |
| trafalgar-138-1.005 | 3/3 | 3/3 | 0.3074 [0.2955, 0.3264] | 0.2959 [0.2942, 0.2961] | 1.039× | overlap |
| trafalgar-138-1.01 | 3/3 | 3/3 | 0.2306 [0.2303, 0.2318] | 0.2312 [0.2307, 0.2314] | 0.997× | overlap |
| trafalgar-138-1.02 | 3/3 | 3/3 | 0.1268 [0.1265, 0.1269] | 0.1265 [0.1265, 0.1272] | 1.002× | overlap |
| final-394-1.005 | 3/3 | 3/3 | 0.2414 [0.2404, 0.2418] | 0.2414 [0.2404, 0.2415] | 1.000× | overlap |
| final-394-1.01 | 3/3 | 3/3 | 0.1711 [0.1707, 0.1715] | 0.1712 [0.1703, 0.1712] | 0.999× | overlap |
| final-394-1.02 | 3/3 | 3/3 | 0.1271 [0.1265, 0.1273] | 0.1271 [0.1262, 0.1274] | 1.000× | overlap |

| Cell / arm | Median full cost | Rejects | PCG/outer | Retry-entry / native wall | Nonaccepted / native wall | Curvature cutoffs / accepts |
|---|---:|---|---|---|---|---|
| ladybug-539-1.005 / off | 164531.79 | [0, 0, 0] | 4.78, 4.78, 4.78 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| ladybug-539-1.005 / on | 164531.79 | [0, 0, 0] | 4.78, 4.78, 4.78 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| ladybug-539-1.01 / off | 165514.08 | [0, 0, 0] | 6, 6, 6 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| ladybug-539-1.01 / on | 165514.08 | [0, 0, 0] | 6, 6, 6 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| ladybug-539-1.02 / off | 165514.08 | [0, 0, 0] | 6, 6, 6 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| ladybug-539-1.02 / on | 165514.08 | [0, 0, 0] | 6, 6, 6 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| trafalgar-138-1.005 / off | 102905.06 | [0, 0, 0] | 44.8, 44.8, 44.8 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| trafalgar-138-1.005 / on | 102905.08 | [0, 0, 0] | 44.8, 44.8, 44.8 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| trafalgar-138-1.01 / off | 103407.73 | [0, 0, 0] | 45.3, 45.3, 45.3 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| trafalgar-138-1.01 / on | 103407.43 | [0, 0, 0] | 45.3, 45.3, 45.3 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| trafalgar-138-1.02 / off | 104518.55 | [0, 0, 0] | 28.1, 28.1, 28.1 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| trafalgar-138-1.02 / on | 104518.47 | [0, 0, 0] | 28.1, 28.1, 28.1 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| final-394-1.005 / off | 305941.8 | [0, 0, 0] | 11.3, 11.3, 11.3 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| final-394-1.005 / on | 305941.89 | [0, 0, 0] | 11.3, 11.3, 11.3 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| final-394-1.01 / off | 306990.87 | [0, 0, 0] | 8.56, 8.56, 8.56 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| final-394-1.01 / on | 306993.19 | [0, 0, 0] | 8.56, 8.56, 8.56 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| final-394-1.02 / off | 309661.69 | [0, 0, 0] | 5.25, 5.25, 5.25 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |
| final-394-1.02 / on | 309661.8 | [0, 0, 0] | 5.25, 5.25, 5.25 | 0, 0, 0 | 0, 0, 0 | [0, 0, 0] / [0, 0, 0] |

## tail

| Cell | Off hits | On hits | Off target seconds | On target seconds | Speedup | Range signal |
|---|---:|---:|---:|---:|---:|---|
| venice-52 | 0/5 | 0/5 | — | — | — | target_miss |
| final-3068 | 4/5 | 2/5 | 3.4944 [3.0189, 4.4656] | 3.9480 [3.3733, 4.5227] | — | target_miss |
| ladybug-1197 | 5/5 | 5/5 | 0.2303 [0.2301, 0.2310] | 0.2304 [0.2302, 0.2309] | 1.000× | overlap |

| Cell / arm | Median full cost | Rejects | PCG/outer | Retry-entry / native wall | Nonaccepted / native wall | Curvature cutoffs / accepts |
|---|---:|---|---|---|---|---|
| venice-52 / off | 246128.99 | [13, 13, 4, 12, 7] | 2.7, 2.77, 3.02, 4.9, 1.67 | 0.0398, 0.0515, 0.0198, 0.052, 0.0318 | 0.0686, 0.0587, 0.0338, 0.0867, 0.0557 | [1, 1, 1, 1, 0] / [0, 0, 0, 0, 0] |
| venice-52 / on | 253187.57 | [3, 3, 2, 2, 5] | 1.69, 3.38, 2.23, 1.86, 2.62 | 0.0216, 0.0174, 0.0158, 0.0115, 0.0215 | 0.0358, 0.0338, 0.0321, 0.0233, 0.037 | [1, 1, 1, 1, 1] / [0, 0, 0, 0, 0] |
| final-3068 / off | 1740875.7 | [16, 7, 4, 4, 7] | 2.15, 3.29, 3.27, 3.07, 10.1 | 0.156, 0.0575, 0.0519, 0.04, 0.104 | 0.202, 0.0808, 0.0753, 0.0624, 0.124 | [1, 1, 1, 1, 1] / [0, 0, 0, 0, 0] |
| final-3068 / on | 1746670.4 | [14, 5, 17, 15, 5] | 2.18, 3.86, 3.53, 3.05, 4.98 | 0.14, 0.0493, 0.0996, 0.145, 0.0696 | 0.184, 0.0644, 0.138, 0.183, 0.099 | [1, 1, 1, 1, 1] / [0, 0, 0, 0, 0] |
| ladybug-1197 / off | 369149.15 | [1, 1, 1, 1, 1] | 7.36, 7.36, 7.36, 7.36, 7.36 | 0.0258, 0.026, 0.026, 0.026, 0.0246 | 0.0783, 0.0783, 0.0781, 0.0779, 0.0737 | [0, 0, 0, 0, 0] / [0, 0, 0, 0, 0] |
| ladybug-1197 / on | 369175.11 | [1, 1, 1, 1, 1] | 7.36, 7.36, 7.36, 7.36, 7.36 | 0.0242, 0.0259, 0.0259, 0.0259, 0.026 | 0.0733, 0.078, 0.0783, 0.0783, 0.0777 | [0, 0, 0, 0, 0] / [0, 0, 0, 0, 0] |

## Limits

CSV target times have 0.0001-second resolution. Host steady-clock attempt tracing adds no GPU barrier; numeric continuations are included, and attempt acceptance/matvec totals must match native summaries. Retry-entry and nonaccepted-attempt fractions are distinct. Endpoint overshoot at a target stop is not automatically a quality advantage.
N3 practical/N5 tail are screening cohorts. Report any larger-repetition confirmation separately. A configuration is not promoted solely by a favorable median on a subset. Frozen Eta2 remains the champion unless the complete registered gate passes.
