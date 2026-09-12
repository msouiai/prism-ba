# Brief 0 witness decomposition and independent normal-equation audit

Nine captured states were audited: seven primary witnesses plus two Ladybug repeat controls. Each has one native Eta2 proposal and three repeated FP64 reference solves, including the reference clipped to the same radius. All original observations were scored. This is fixed-state mechanism evidence; it is not a convergence-speed or hit-rate experiment.

**There is no universal solve-versus-point-model failure across these witnesses.** Final3068 mainly shows a camera-model/radius restriction; Venice contains both useful unresolved directions and a raw-reference overshoot; Ladybug opening has concentrated point-model error, but the historical extreme fling is absent.

| State | Eta2 decrease | Reference decrease | Clipped reference decrease | Reference full scaled normal residual |
|---|---:|---:|---:|---:|
| venice-52/0 | 0.547017814 | 35.5099769 | 35.5099769 | 3.28e-06 |
| venice-52/1 | 0.0270144107 | -20.0457822 | 0.0348621697 | 1.31e-10 |
| venice-52/2 | 0.956920775 | 1.29923805 | 1.29923805 | 2.95e-07 |
| final-3068/0 | 0.200350714 | -218.75708 | 0.200350713 | 6.38e-09 |
| final-3068/5 | 15.267473 | -205309.548 | 15.2779153 | 6.52e-10 |
| final-3068/6 | 0.0263232532 | -533926.616 | 0.0263727873 | 1.57e-09 |
| ladybug-1197/0 | 6115573.85 | 6166994.3 | 6166994.3 | 3.45e-09 |

“Reference” means **source solve with certified reduced residual**, not an exact full GN direction. Independent full-normal checks are reported above. Clipped references need not satisfy the camera normal equations.

## Nonlinear mechanism

- **Final3068:** every unclipped reference loses objective value. Camera-only model error is about 232, 217,956 and 553,092, while point-only error is about 2.6e-7, 8.82 and 0.0238. Clipping returns almost the same small useful decrease as Eta2. Greater linear accuracy alone does not remove this camera-model/radius bind. The clipped step can have meaningful point/cross error (especially captures 5 and 6), but that is distinct from why the raw reference fails.
- **Venice:** capture 0 has a materially better hypothetical direction (35.51 decrease versus 0.547), but both ratios are already adequate. Its camera, point and cross errors strongly cancel: +903.2, -281.7 and -620.4. Capture 1 raw reference loses 20.05 through camera/cross errors; clipping restores 0.03486 decrease versus Eta2 0.02701. Capture 2 reference improves 1.299 versus 0.957. A single binary rule would obscure these distinct cases.
- **Ladybug1197 outer 1:** native point-only model error is 1.526M, with top 200 points accounting for 98.39% of absolute point error. Two-observation tracks account for only 26.42% of that absolute point error, so it is not exclusively a two-view pathology. One point moves beyond the camera-center radius (16.30 versus 12.32); all three controls agree. The old 2.4e4 fling is not reproduced. Both native and reference remain nonlinear descent proposals (rho about 0.799 and 0.805).

The signed decomposition is algebraic, not causal. Negative point/cross terms can cancel positive camera error; an absolute concentration fraction can be high even when the total point error is tiny. Per-track length/parallax signed, absolute, positive and negative totals remain in every JSON.

## Numerical qualification

Reduced-PCG residuals below 1e-10 do not imply the independent full-normal residual reaches 1e-10. Unclipped scaled full residuals range from 1.31e-10 to 3.28e-6 across the primary references. Point residuals relative only to the conditional RHS can look much worse; after Dp whitening against the full scaled gradient, the Final point residual is only 2.59–3.93e-10. This illustrates why a single raw point residual ratio was insufficient.

Extended-precision worst-track checks retain arithmetic sensitivity. Repeated affected points include Venice 60378, Final3068 250233 and Ladybug 98124. The Ladybug point has projected-depth cancellation condition about 1.47e9; reevaluating its Jacobian in extended precision changes it by about 8.49e-8 relative. These are local arithmetic qualifications, not evidence of a true nonlinear saddle. The large nonlinear failures remain far larger than the observed independent scoring discrepancies.

6 CPU/native agreement checks exceeded the original budget, all retained in [retained_mismatches.json](retained_mismatches.json). They concern raw-reference predictions for two Final3068 captures; no threshold was loosened. Both CPU and native still predict descent while the actual proposal strongly increases cost. All initial/candidate cost and true-decrease comparisons passed. The mechanism screen leaves those budget-violating reference rows unresolved rather than relabelling them exact.

## Deliverables and validation

[ledger.csv](ledger.csv) contains all arms and states, including repeat controls. `results/*-normals.json` contains absolute/RHS/backward/whitened residuals and extended-precision worst-point details. `results/<scene>-<capture>.json` contains the full decomposition, all bins and top-200 indices. No optional full per-point archives were written.

Synthetic tests verify decomposition against direct model scoring (maximum discrepancy 6.71e-13), bin conservation, blocked parallax against dense pairs, and uncertified-source rejection. The native toy matches CPU costs/predictions to normalized discrepancy below 4.7e-16. CPU timings are diagnostic overhead and are not solver timing claims.
