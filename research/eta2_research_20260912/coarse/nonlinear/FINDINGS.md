# Nonlinear passenger-cluster correction: registered witness pretest

The actual passenger formulation passes the mechanism gate on **2/3** witness states. A native continuation can be separately registered.

This experiment transforms each camera cluster and its assigned points together. It does not impose the old fine radius. Every original observation remains in the objective. The earlier eliminated-point oracle is a different model; its raw gains are shown for context, not pooled.

| Witness | Eta2 gain | Passenger gain (3 attempts) | / Eta2 | Initial decrement | Camera norm / old radius | CPU seconds | Prior eliminated-point raw gain |
|---|---:|---:|---:|---:|---:|---:|---:|
| Final3068-0 | 0.200350711 | 0.00194926065 | 0.00972924 | 9.29055e-06 | 4.95652 | 11.215 | 0.00188236711 |
| Final3068-5 | 15.267473 | 827.241545 | 54.1833 | 65.4815 | 774.79 | 7.066 | 128.020732 |
| Final3068-6 | 0.0263232524 | 0.849299222 | 32.2642 | 0.214451 | 10730.5 | 10.968 | 0.410405666 |

All cells use three deterministic CPU repetitions of the same saved state, not three independent trajectories. These are mechanism observations, not endpoint wins, target hit rates, or evidence of GPU speed. Full CPU wall includes loading, clustering, metric factorization, normal assembly and backtracking objective scores.

Maximum score-init relative discrepancy: 7.49e-15; joint metric whitening error: 8.17e-09; damped coarse solve relative residual: 1.34e-15.

The joint metric keeps all seven modes where passengers make them independent, including singleton-camera scale. The fixed episode metric and initial world centroids stay unchanged across three left-increment similarity steps. Intrinsics remain fixed. Analytically invariant same-cluster Jacobian rows are zero, but their full scores are still evaluated and numerical drift is reported.

The geometry materially limits interpretation: deterministic center clustering isolates a handful of distant cameras while one cluster holds 3058–3059 of 3068 cameras. Only 395–582 of 1,653,812 observations cross clusters. Six singleton clusters have no first-observation passenger points, explaining the measured joint rank 50. This is consistent with correcting a few outlying cameras; it does not demonstrate recovery of distributed long-wavelength modes. No clustering rule was changed after these outcomes.

All three full steps are accepted at witnesses 0 and 5 without backtracking. Witness 6 accepts after 0, 1, 5 halvings. Its full-step success alone is not evidence for more accurate quadratic modeling: nonlinear backtracking remains necessary. Same-cluster cumulative cost drift is at most 1.28e-7 objective units, far below the measured gains.

The best cumulative relative objective improvement is 0.04433% (witness 5); witness 6 improves 0.0000435% and witness 0 only0.000000106%. Thus large ratios against a nearly stopped fine step are not endpoint-quality wins under the 0.15% rule. The improvement also does not by itself establish that a full trajectory can reach the registered target. The frozen Eta2 champion remains the current winner until a separately registered native same-target continuation earns promotion.

Original source-normal/prediction mismatches remain in the campaign numerical audit. These coherent CPU coarse calculations do not repair or silently replace the frozen compact native operator.

See `ledger.csv` for all nine runs, `results/*.json` for every attempted alpha, rho, point motion and cost, `toy_checks.json` for pre-grid correctness, and `IMPLEMENTATION_NOTES.md` for frozen algebra choices.
