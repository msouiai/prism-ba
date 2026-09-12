# B1 version-2 contraction protocol

Registered after the version-1 profile and before any version-2 solver run.

Version 1 proved that the 13-value factorization is accurate but exposed an
implementation bottleneck: Pass 2 used 72 registers instead of 40 and fused
RHS/diagonal used 78 instead of 46; Muell Krylov and preparation each rose by
about 16%.  Version 2 keeps the exact same stored factors and makes only two
algebraic contractions:

```
W^T v = R^T P^T (Jc v)
W u   = Jc^T P (R u)
```

These remove the explicit six-value point row from Pass 1 and Pass 2.  For the
Schur diagonal, it computes the 2x2 matrix `Jp V^-1 Jp^T` with two triangular
solves per observation and evaluates each camera-coordinate quadratic form;
version 1 and the champion perform nine triangular solves.  Factored Pass 2
uses 128 threads per camera, reducing its shared memory from 18 to 9 KiB and
allowing more blocks to reside concurrently.  Fused preparation also uses
128-thread blocks.  These choices are fixed from compiled resource usage,
before timing.

The active flag remains `OCA_W5_FACTORED_J=1`; there are no parameters.  The
binary and modified source are separately hashed in `b1v2-build-manifest.json`.
Disabled-mode compatibility against the frozen champion is required at N=3.
Then run the all-observation algebra audit and the same N=3 nine-cell paired
panel.  Run profiled Trafalgar138 and Muell cells only if needed to attribute
the panel result.  Proceed to N=3 Muell and N=5 tails only if target-time
performance is no worse overall and no stable-cell endpoint moves by more than
0.15%.

The decision rule is unchanged: the representation needs an end-to-end target
time gain, not just lower traffic or a faster isolated expression.  Kill B1
as a production family if version 2 is not faster in geometric-mean panel
target time or if it changes hit-rate behavior.  No further kernel tuning is
allowed after this result; subsequent low-precision work must use B2's
FP64-residual iterative-refinement protocol rather than another B1 variant.
