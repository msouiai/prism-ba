# D2c result: FP32 Jacobian fragments cause the Venice finite jump

## Registered verdict

The FP64-fragment diagnostic passes the criterion **FP32 fragments explain the
jump**.  Changing only stored Jacobian fragments from FP32 to FP64 restores the
expected linear perturbation law over four decades:

| Fragment storage | median D10 at 1e-8 | at 1e-10 | at 1e-12 | log-log slope |
|---|---:|---:|---:|---:|
| FP32 | 0.006337 | 0.006096 | 0.006793 | -0.0075 |
| FP64 | 3.1335e-4 | 3.1338e-6 | 3.1360e-8 | **0.999915** |

The FP64 median amplification is 0.014206, 0.014208 and 0.014216, a maximum to
minimum ratio of 1.00065.  At the smallest dose, FP64 lowers the terminal
separation by **216,602x**.  All 12 paired trajectories retain identical global
accept/reject, CG-depth/retry, and point-safeguard choices.

The derived binary passed its repeatability gate first: two unperturbed runs
have identical state hashes at all eleven saved states, identical endpoint
cost `265559.9020234335`, and identical work and discrete-trace hashes.

## Interpretation

The frozen Eta2 path stores the 27-value observation fragments in FP32 while
performing state updates, Schur arithmetic, reductions and acceptance in FP64.
At the initial perturbation the mathematical residual difference scales exactly
with epsilon.  In the FP32-fragment path, independent nearby states round their
Jacobians onto different fragment bins; repeated nonlinear iteration amplifies
that quantisation into an epsilon-independent residual separation near 0.006.
With FP64 fragments the same deterministic map is smooth and contractive over
the measured horizon.

This resolves the D2/D2b ambiguity for Venice.  The very large small-dose
`A10` was not chaos and was not a controller switch.  It was the ratio of a
finite mixed-storage jump to a shrinking input perturbation.

## Scope

This is a numerical attribution, not evidence that FP64 fragment storage is a
better production solver.  The final cost difference after ten outers is tiny,
and prior campaigns show that a more accurate local direction can select a
worse long-run basin.  FP64 also doubles fragment traffic.  Final3068 has real
accept/reject splits in addition to its finite jump, so it requires a separate
registered diagnostic before any reliability claim.

The practical follow-up is to ask whether the quantisation changes tail hit
rate under common perturbations, and only then consider a compact correction
such as FP32-high plus a low-bit residual.  Full rows are in `d2c-results.json`,
the compact comparison in `d2c-summary.json`, and the repeatability evidence in
`d2c-validation.json`.
