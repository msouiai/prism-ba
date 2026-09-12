# B6v3 exact-rounding vector-fusion protocol

Registered after B6v2 completed and before any B6v3 solver outcome.  B6v2
established that device-result FP64 dot batching is safe and accounts for a
1.32% panel speedup.  The combined B6 arm reached 3.62%, but its fused
`p = z + beta*p` expression allowed one FMA where the champion has a rounded
scale followed by an add.

B6v3 fuses the vector launches while explicitly preserving the champion's
rounding points:

- `x += alpha*p` and `r -= alpha*Ap` use explicit round-to-nearest FP64 FMA,
  matching the two independent cuBLAS DAXPY calls element by element.
- `p = z + beta*p` uses explicit round-to-nearest FP64 multiply into a local
  temporary, then explicit FP64 add.  This matches cuBLAS DSCAL followed by
  DAXPY without the intermediate global-memory round trip.
- dot batching is exactly B6v2.

A deterministic standalone audit over 1,000,003 values must compare all three
fused results bit-for-bit against cuBLAS before the solver is run.  The native
panel has three contemporaneous arms: off, dots-only, and exact-fused.  Run N=3
on the nine practical cells.  Exact-fused proceeds to N=3 profile/Muell and
fresh N=10 Venice52/Final3068 only if it beats off in panel geometric-mean
target time, is no slower than dots-only, and preserves median product counts.
Promotion requires no tail hit loss and no stable endpoint regression above
0.15%.  The frozen champion remains unchanged.

