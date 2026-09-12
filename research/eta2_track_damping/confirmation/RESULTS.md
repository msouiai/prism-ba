# Fresh N=10 static track-damping confirmation

This is the new user-requested cohort, separate from the earlier N=5 screen: 40 tail runs and 18 control runs. Frozen derived binary off/on; full original-observation objective; all endpoints independently audited.

## Primary prediction

Final3068 target hits: **6/10 off → 3/10 on**. On-arm FTOL misses: **7**. The requested zero-miss observation fails in this cohort.
Successful-run median crossing: 3.65245s off versus 1.7805s on. Within fresh-control +20%: True; within historical +20%: True. Fresh controls supply 4 FTOL misses.
The zero-miss and timing conditions are separate. A favorable successful-subset median does not compensate for target misses. These are stochastic whole-run comparisons, not replay of identical internal failure states.

## Identical-target crossings

| Scene | Off hits | On hits | Off crossing seconds | On crossing seconds | Timing signal |
|---|---:|---:|---|---|---|
| final-3068 | 6/10 | 3/10 | 3.6524 [3.1619, 4.3497] | 1.7805 [1.5835, 2.4113] | misses_or_unequal_successful_subsets |
| venice-52 | 0/10 | 0/10 | — | — | misses_or_unequal_successful_subsets |
| final-4585 | 3/3 | 3/3 | 1.6784 [1.6772, 1.6784] | 1.7220 [1.7202, 1.7254] | slower_disjoint |
| dubrovnik-88 | 3/3 | 3/3 | 0.0830 [0.0744, 0.0830] | 0.1262 [0.1261, 0.1263] | slower_disjoint |
| ladybug-539 | 3/3 | 3/3 | 0.0594 [0.0588, 0.0596] | 0.0596 [0.0593, 0.0596] | overlap |

N=10 tail cells stop at target; N=3 control cells run to ordinary termination and use the registered target only to score crossings. No cap/termination time substitutes for a missed crossing. Ranges are observed samples, not confidence intervals.
The preregistration mislabeled the rounded Dubrovnik88 reference as Caspar; it was the supplied MFREE library endpoint. The frozen target 362571.82 and every measured comparison are unchanged. See [provenance correction](PROVENANCE_CORRECTION.md).

## Endpoints and total native time

| Scene | Off median cost [range] | On median cost [range] | Cost delta | Off native median | On native median |
|---|---|---|---:|---:|---:|
| final-3068 | 1743115.341404 [1739834.261373, 1950815.253818] | 1791194.512172 [1733661.757166, 1795977.026258] | +2.758% | 3.6758s | 2.9617s |
| venice-52 | 246355.207850 [244965.790359, 247575.321933] | 261513.851811 [261513.606108, 261513.957825] | +6.153% | 1.3347s | 0.7525s |
| final-4585 | 6900194.844513 [6590085.114515, 6937724.358391] | 6866800.277283 [6682065.855438, 6925722.645863] | -0.484% | 54.6177s | 46.9390s |
| dubrovnik-88 | 358945.149136 [358944.778827, 358945.526077] | 359810.627998 [359810.508800, 359810.652528] | +0.241% | 0.4267s | 0.4189s |
| ladybug-539 | 163977.973519 [163977.958492, 163979.733482] | 163978.299740 [163977.981197, 163980.616800] | +0.000% | 1.2045s | 1.1919s |

Total native time here is time to each run's own termination, not equal-quality speed. Target-stopped endpoint overshoot is not automatically a quality advantage. Final4585 N=3 does not establish a basin noise floor.

## Solver counters

| Scene / arm | Outers | Rejects | PCG/outer | Retry/native | Failed/native | Numerical repairs | Stops |
|---|---|---|---|---|---|---|---|
| final-3068 / off | [56, 65, 50, 51, 88, 63, 97, 78, 66, 52] | [8, 5, 18, 7, 23, 3, 21, 5, 6, 15] | 4.8, 3.2, 1.94, 5, 3.44, 5.44, 3.45, 3.01, 3.52, 1.81 | 0.0904, 0.0521, 0.202, 0.0792, 0.136, 0.0334, 0.115, 0.047, 0.0698, 0.159 | 0.122, 0.0844, 0.256, 0.133, 0.182, 0.0468, 0.159, 0.0663, 0.0911, 0.184 | [1, 1, 1, 1, 1, 1, 1, 1, 1, 0] | {'target': 6, 'ftol': 4} |
| final-3068 / on | [43, 51, 31, 64, 54, 108, 22, 21, 43, 46] | [21, 13, 8, 18, 14, 13, 3, 5, 19, 16] | 5.63, 4.71, 8.16, 4.05, 4.57, 2.75, 9.09, 13, 5.51, 5.22 | 0.208, 0.142, 0.148, 0.149, 0.129, 0.0772, 0.0724, 0.113, 0.193, 0.167 | 0.279, 0.194, 0.188, 0.203, 0.191, 0.102, 0.113, 0.16, 0.249, 0.227 | [0, 0, 1, 0, 0, 0, 0, 0, 0, 0] | {'ftol': 7, 'target': 3} |
| venice-52 / off | [139, 129, 109, 125, 128, 113, 126, 95, 147, 131] | [7, 7, 9, 5, 6, 5, 7, 1, 1, 2] | 1.86, 1.67, 5.76, 1.65, 1.66, 2.92, 1.68, 1.62, 1.62, 1.5 | 0.0302, 0.0317, 0.037, 0.0242, 0.028, 0.0284, 0.0322, 0.0155, 0.00951, 0.015 | 0.0515, 0.0553, 0.0614, 0.0429, 0.0464, 0.0464, 0.0563, 0.0245, 0.0157, 0.0237 | [1, 0, 1, 0, 0, 1, 0, 1, 1, 1] | {'ftol': 10} |
| venice-52 / on | [71, 71, 71, 71, 71, 71, 71, 71, 71, 71] | [2, 2, 2, 2, 2, 2, 2, 2, 2, 2] | 1.73, 1.73, 1.73, 1.73, 1.73, 1.73, 1.73, 1.73, 1.73, 1.73 | 0.0141, 0.0137, 0.0142, 0.0142, 0.0142, 0.0142, 0.0141, 0.0141, 0.0142, 0.0142 | 0.0272, 0.0264, 0.0272, 0.0272, 0.0272, 0.0272, 0.0272, 0.0272, 0.0272, 0.0272 | [0, 0, 0, 0, 0, 0, 0, 0, 0, 0] | {'ftol': 10} |
| final-4585 / off | [159, 116, 137] | [43, 25, 32] | 3.74, 3.55, 9.3 | 0.15, 0.124, 0.126 | 0.205, 0.172, 0.172 | [1, 2, 1] | {'ftol': 2, 'time_cap': 1} |
| final-4585 / on | [164, 132, 141] | [39, 36, 34] | 5.03, 4.3, 2.95 | 0.149, 0.134, 0.13 | 0.207, 0.188, 0.186 | [1, 1, 2] | {'time_cap': 1, 'ftol': 2} |
| dubrovnik-88 / off | [33, 33, 33] | [2, 1, 1] | 2.79, 2.76, 2.76 | 0.0226, 0.012, 0.0122 | 0.0461, 0.0279, 0.0284 | [0, 0, 0] | {'ftol': 3} |
| dubrovnik-88 / on | [36, 36, 36] | [1, 1, 1] | 2.39, 2.39, 2.39 | 0.0123, 0.0123, 0.0121 | 0.0214, 0.0214, 0.0213 | [0, 0, 0] | {'ftol': 3} |
| ladybug-539 / off | [32, 34, 34] | [4, 4, 2] | 49.6, 48.6, 60.4 | 0.03, 0.142, 0.0363 | 0.0329, 0.0775, 0.0294 | [1, 1, 1] | {'ftol': 3} |
| ladybug-539 / on | [34, 35, 33] | [0, 2, 0] | 49.4, 79.1, 16 | 0.00629, 0.0442, 0.0067 | 0.00709, 0.047, 0.00945 | [1, 0, 1] | {'ftol': 3} |

## Misses

- final-3068 / off: rep 2: cost 1938977.030584, ftol; rep 4: cost 1762872.590914, ftol; rep 6: cost 1747726.328844, ftol; rep 9: cost 1950815.253818, ftol
- final-3068 / on: rep 0: cost 1795885.767378, ftol; rep 1: cost 1795977.026258, ftol; rep 3: cost 1795367.303270, ftol; rep 4: cost 1783957.719598, ftol; rep 5: cost 1787021.721073, ftol; rep 8: cost 1795819.000910, ftol; rep 9: cost 1795858.513835, ftol
- venice-52 / off: rep 0: cost 244968.080183, ftol; rep 1: cost 247551.456593, ftol; rep 2: cost 246296.909504, ftol; rep 3: cost 247567.405966, ftol; rep 4: cost 247555.777179, ftol; rep 5: cost 244965.790359, ftol; rep 6: cost 247575.321933, ftol; rep 7: cost 246360.660846, ftol; rep 8: cost 246319.354316, ftol; rep 9: cost 246349.754855, ftol
- venice-52 / on: rep 0: cost 261513.925480, ftol; rep 1: cost 261513.957825, ftol; rep 2: cost 261513.783861, ftol; rep 3: cost 261513.916540, ftol; rep 4: cost 261513.904648, ftol; rep 5: cost 261513.606108, ftol; rep 6: cost 261513.809395, ftol; rep 7: cost 261513.864306, ftol; rep 8: cost 261513.839316, ftol; rep 9: cost 261513.758518, ftol

## Verification and scope

All 58 rows verified. Maximum independent objective discrepancy: 3.61e-13 relative. Original source, 44 headers, fixed flags, derived binary/header hashes, input hashes, initial scores, trace counts, crossing times and endpoint-container hashes checked. No algorithm rebuild or coefficient change during the grid.
Historical reference: 8/10 successes, median 3.692232392s, giving +20% ceiling 4.430678870s. This older timing stream is context; fresh off/on is the primary comparison.
The external MFREE 23-scene/dose results are supplied evidence and have not been independently reproduced here. No new Caspar run or global fastest-solver claim follows. Raw state exports were staged in RAM, independently audited and retained in verified compressed form on disk.
