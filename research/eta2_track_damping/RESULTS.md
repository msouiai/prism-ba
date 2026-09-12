# Static long-track damping: paired transfer screen

Full original-observation objective; one binary off/on; N=5 per arm per scene. Ranges are observed samples, not confidence intervals. Misses are censored. Native times count the intervention and attempt tracing.

| Scene | Off hits | On hits | Off target seconds | On target seconds | Off median cost | On median cost | Cost delta |
|---|---:|---:|---|---|---:|---:|---:|
| final-3068 | 4/5 | 4/5 | 3.1911 [1.8563, 3.3823] | 2.0249 [1.4477, 3.8824] | 1743472.197 | 1744387.702 | +0.053% |
| venice-52 | 0/5 | 0/5 | — | — | 246399.376 | 261513.850 | +6.134% |

Conditional crossing times on different successful subsets are not a matched speedup. Target-stopped endpoint overshoot is not by itself a quality win.

| Scene / arm | Outers | Rejects | PCG/outer | Retry/native wall | Failed/native wall | Curvature repairs | FTOL / cap |
|---|---|---|---|---|---|---|---|
| final-3068 / off | [55, 51, 33, 53, 66] | [3, 4, 2, 10, 2] | 4.35, 6.39, 4.27, 2.42, 3.53 | 0.0444, 0.0618, 0.0381, 0.132, 0.0209 | 0.0582, 0.0769, 0.0679, 0.16, 0.0364 | [1, 1, 1, 1, 1] | 1 / 0 |
| final-3068 / on | [50, 45, 23, 77, 20] | [1, 11, 1, 4, 1] | 3.56, 5.56, 8.65, 3.14, 9.8 | 0.0297, 0.135, 0.0203, 0.0399, 0.0222 | 0.0368, 0.178, 0.0338, 0.0609, 0.037 | [1, 0, 0, 1, 0] | 1 / 0 |
| venice-52 / off | [129, 102, 129, 100, 142] | [6, 1, 7, 2, 8] | 1.65, 1.77, 1.67, 4.51, 3.34 | 0.0278, 0.0147, 0.0316, 0.0152, 0.0315 | 0.0489, 0.0232, 0.0553, 0.0243, 0.0527 | [0, 1, 0, 1, 1] | 5 / 0 |
| venice-52 / on | [71, 71, 71, 71, 71] | [2, 2, 2, 2, 2] | 1.73, 1.73, 1.73, 1.73, 1.73 | 0.0142, 0.0142, 0.0142, 0.0142, 0.0141 | 0.0271, 0.0272, 0.0271, 0.0272, 0.0271 | [0, 0, 0, 0, 0] | 5 / 0 |

## Input classes and initial scores

| Scene | Points: ≤2 / 3–5 / ≥6 obs | Observations in those classes | Initial score range |
|---|---|---|---|
| final-3068 | [170322, 92149, 48383] | [340644, 327250, 985918] | [90993342.0243, 90993342.0243] |
| venice-52 | [26823, 20032, 17198] | [53646, 73576, 219951] | [11152062.7728, 11152062.7728] |

Registered extension gate: **FAIL**. Hit gate=False; endpoint gate=False.
No per-scene parameter or alternative dose was selected from these outcomes. All traces, commands, source/input hashes, audited results and exact compressed scored endpoints are retained.
