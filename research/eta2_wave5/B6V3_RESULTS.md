# B6v3: exact-rounding PCG vector fusion

## Verdict

Rejected at the practical-panel gate.  Exact-rounding fusion is numerically
sound but does not outperform the dots-only arm: geometric-mean target-time
ratios in the same three-arm cohort are **0.9976** for exact-fused and
**0.9856** for dots-only.  The registered Muell, profile, and tail extensions
were therefore not run.  B6v2 remains the current systems winner.

## Arithmetic audit

The fused kernels were designed to preserve the champion's rounding points:
two explicit FP64 FMAs for the independent `x/r` DAXPY updates, and an explicit
round-to-nearest multiply followed by an explicit add for the former
DSCAL-plus-DAXPY `p` update.  A deterministic audit over 1,000,003 elements
compared the three result vectors bit-for-bit against cuBLAS:

```
VECTOR_ROUNDING_AUDIT n=1000003 mismatch_x=0 mismatch_r=0 mismatch_p=0
```

The derived-off binary also passed the N=3 frozen compatibility gate at
`1.0e-14` relative endpoint error.

## Three-arm panel

All 81 rows reached their fixed targets.  Every cell retained identical
median products, outers, and rejects.  Median endpoint movements remained far
below the 0.15% threshold.

| Cell | Dots/control | Exact/control | Products |
|---|---:|---:|---:|
| final-394, 1.005 | 1.026 | 0.990 | 135 |
| final-394, 1.01 | 0.992 | 0.992 | 86 |
| final-394, 1.02 | 0.996 | 0.994 | 50 |
| ladybug-539, 1.005 | 0.991 | 1.100 | 52 |
| ladybug-539, 1.01 | 0.988 | 1.084 | 42 |
| ladybug-539, 1.02 | 0.982 | 0.954 | 42 |
| trafalgar-138, 1.005 | 0.947 | 0.939 | 594 |
| trafalgar-138, 1.01 | 0.975 | 0.966 | 462 |
| trafalgar-138, 1.02 | 0.975 | 0.971 | 232 |

The exact kernels add a small benefit on deep-CG Trafalgar, where saved vector
traffic can amortise their launches.  They are noisy and often slower on the
42--52-product Ladybug cells.  Consequently their incremental gain is not a
run-everywhere optimization.  The faster one-FMA implementation from B6 is
also left rejected because it changes the recurrence's arithmetic semantics.

