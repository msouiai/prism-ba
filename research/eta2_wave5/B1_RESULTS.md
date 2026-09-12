# B1 factored-Jacobian results

## Version 1: mathematically clean, economically negative

The first registered implementation is numerically equivalent for practical
purposes but slower.  It compresses the stored camera--point cross fragment
from 27 to 13 FP32 values per observation and retains the existing six FP32
point-Jacobian values, reducing total fragment storage from 33 to 19 floats.
Every operator contraction reconstructs the two Jacobian rows and applies
`W = Jc^T Jp` without materialising the 9x3 block.

The disabled derived binary matches the frozen champion to `6.7e-15` relative
endpoint cost.  On Ladybug49, an all-observation audit against the champion's
definition of a directly formed FP64 product rounded to FP32 gives relative
Frobenius error `7.47e-8`; maximum absolute error is `1.45e3` against a maximum
reference magnitude of `1.48e10`.  The storage representation therefore
passes the algebra and rounding gate.

All 54 paired practical-panel runs reached their identical registered targets,
with identical product and outer counts in every cell.  Endpoint changes are
at most `0.0036%`.  The geometric mean target-time ratio is nevertheless
`1.0385`: the compact path is 3.85% slower.

| Cell | Off (s) | Factored (s) | Delta | Time ranges |
|---|---:|---:|---:|---|
| Final394 1.005 | 0.2415 | 0.2587 | +7.1% | disjoint |
| Final394 1.01 | 0.1711 | 0.1824 | +6.6% | disjoint |
| Final394 1.02 | 0.1272 | 0.1339 | +5.3% | disjoint |
| Ladybug539 1.005 | 0.0957 | 0.0898 | -6.2% | overlap |
| Ladybug539 1.01 | 0.0591 | 0.0622 | +5.2% | overlap |
| Ladybug539 1.02 | 0.0655 | 0.0670 | +2.3% | overlap |
| Trafalgar138 1.005 | 0.2981 | 0.3114 | +4.5% | overlap |
| Trafalgar138 1.01 | 0.2317 | 0.2439 | +5.3% | disjoint |
| Trafalgar138 1.02 | 0.1268 | 0.1334 | +5.2% | disjoint |

The phase profile identifies reconstruction cost rather than nonlinear drift.
On Muell, both arms use 980 products, 16 outers, and no rejects, but Krylov
rises from 3.053 to 3.537 s (`+15.9%`) and point-factor plus RHS from 0.243 to
0.282 s (`+16.0%`); assembly is unchanged at 0.73 s.  Native target time rises
12.6%.  On Trafalgar138 1.005, Krylov rises from 0.244 to 0.255 s and RHS from
0.013 to 0.015 s.

Compiled resource usage explains much of the loss.  The original/factored
register counts are 40/48 for Pass 1, 40/72 for Pass 2, and 46/78 for fused
RHS plus diagonal.  Pass 2 also retains 18 KiB of shared memory per 256-thread
block.  The representation saves reads but lowers occupancy and repeats
avoidable algebra.

The version-1 production gate fails, so its tail runs are not launched.  One
mechanism-driven implementation follow-up is allowed before rejecting B1 as a
family: contract `R` and the point vector before applying `dr/dY`, avoiding the
six explicit point-row values in Pass 1/2, and compute the Schur diagonal from
the 2x2 matrix `Jp V^-1 Jp^T` using two triangular solves per observation
instead of nine.  This preserves the same 13-value representation and the same
operator; it is an implementation optimization, not a new tuned arm.  It will
be registered as version 2 before timing.

Raw version-1 evidence is in `b1-panel-results.json` and
`b1-profile-results.json`; summaries are in `b1-panel-summary.json` and
`b1-profile-summary.json`.
