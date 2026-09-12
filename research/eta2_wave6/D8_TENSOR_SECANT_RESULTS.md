# D8 result: rank-one tensor curvature is real but too weak

## Verdict

The preregistered gate fails, so a native tensor-Gauss--Newton step is not
earned.  A one-secant residual tensor improves the prediction of all five
committed Final3068 transitions, but its median improvement is only 1.86% and
none of the five reaches the required 20% improvement.  Building the full
three-solve sparse tensor step would therefore add substantial work without a
measured model-fidelity signal large enough to justify it.

This is a fixed-trajectory result.  The deterministic replay exactly matches
the previously recorded 52-outer cost trace and endpoint state, including
endpoint SHA256
`ccfdefc4c0bc9ca251f9d7ba706452161db839743e6d54ae0db58ed21ed94925`.

## Registered results

`res ratio` and `cost ratio` are tensor error divided by Gauss--Newton error,
so values below one favor the tensor model.  `beta` is the scalar multiplying
the previous step's residual secant error in the rank-one model.

| outer | actual decrease | res ratio | cost ratio | beta | forward-step cosine | top-200 correction energy |
|---:|---:|---:|---:|---:|---:|---:|
| 37 | 8.71265 | 0.85141 | 0.85144 | 0.17920 | -0.95286 | > 0.999999999999 |
| 40 | 7.95247 | 0.95331 | 0.95331 | 0.03069 | +0.25960 | > 0.999999999997 |
| 43 | 2.39457 | 0.98383 | 0.98383 | 0.00384 | +0.39072 | > 0.999999999891 |
| 47 | 0.12233 | 0.98970 | 0.98970 | 0.00309 | +0.32018 | > 0.999999999999 |
| 51 | 0.02106 | 0.98142 | 0.98142 | 0.00764 | -0.11735 | > 0.999999999948 |

The tensor residual-error improvement is 14.86%, 4.67%, 1.62%, 1.03% and
1.86%, respectively.  The normalized cost-prediction improvement is
numerically the same to four significant figures.  Both models predict the
correct decrease sign in 5/5 transitions.

## Mechanism

The tensor information is highly concentrated but poorly aligned with the
next step.  More than 99.999999989% of the tensor correction energy lies in
the largest 200 of 1,653,812 observations at every transition.  The previous
step therefore contains a strong local nonlinear residual signature.  The
rank-one model can affect a new direction only through

```
beta = (<s,d>_D / ||s||_D^2)^2.
```

After outer 37 this coefficient is only 0.003--0.031.  Thus almost all of the
recorded nonlinear correction is projected away.  At outer 37 the coefficient
is larger, 0.179, and the model earns its largest gain, but even that gain
misses the registered threshold.  This is direct evidence that immediately
preceding secant curvature does not transfer reliably to the changing
clipped/retry directions in the plateau.

This result does not say that every tensor method is ineffective in BA.  It
rejects the sparse `p=1` Bouaricha--Schnabel construction for this measured
failure regime.  Higher-rank history would increase memory and solve cost and
would approach the already excluded cross-iteration subspace family without a
supporting signal here.

## Numerical certificates

- Every native left-SO(3) camera tangent and additive point tangent
  reconstructs its stored target state with relative residual error below
  `7.49e-13`.
- The rank-one model interpolates the previous residual vector to reported
  precision (recorded relative error zero in FP64 arithmetic).
- The coherent FP64 Gauss--Newton predicted decreases agree with the native
  logged quadratic predictions to their expected compact-fragment rounding
  difference.
- Input, state, replay, executable, protocol and analysis hashes are retained
  in `d8-capture-manifest.json` and `d8-tensor-results.json`.

## Decision against the frozen gate

| gate | outcome |
|---|---|
| residual error at least 20% lower on at least 3/5 | **fail: 0/5** |
| lower median residual error | pass: ratio 0.98142 |
| cost error at least 20% lower on at least 3/5 | **fail: 0/5** |
| lower median cost error | pass: ratio 0.98142 |
| sign accuracy no worse | pass: 5/5 versus 5/5 |
| no error blow-up above 2x | pass |
| all reconstruction/interpolation certificates below `1e-9` | pass |

The frozen Eta2 champion and B6v7 systems candidate remain unchanged.

