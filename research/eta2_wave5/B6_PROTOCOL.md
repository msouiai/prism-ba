# B6 batched-reduction PCG protocol

Registered before any B6 solver outcome.  The frozen Eta2 champion remains the
control.  The single active arm, `OCA_W5_CG_BATCH=1`, is legal only for its
single-shift, unshared, camera-block-PCG path and changes three execution
details inside each CG iteration:

1. `p^T A p` and `p^T p` use two ordinary cuBLAS FP64 dot products with
   device result pointers, followed by one 16-byte host copy instead of two
   host-result calls.
2. After applying the preconditioner, `r^T r` and `r^T z` are batched in the
   same way.  Their mathematical evaluation points are unchanged.
3. `x += alpha*p` with `r -= alpha*Ap`, and later
   `p = z + beta*p`, each use one elementwise kernel instead of two BLAS
   launches.

No custom reduction is introduced: cuBLAS retains its reduction order and
precision.  No CG recurrence, tolerance, candidate, damping, radius, scoring,
or acceptance logic changes.  The arm reports iterations and the number of
batched dot pairs.

Run N=3 disabled compatibility, then the same N=3 nine-cell practical panel.
Proceed to N=3 Muell and N=5 Venice52/Final3068 only if the panel geometric
mean improves and product counts remain unchanged.  Promotion requires a
target-time improvement with no stable endpoint movement above 0.15% and no
tail hit-rate loss.  Kill if the extra handle/API work erases the saved
synchronizations, or if any cell changes the CG stopping depth; this is a
latency optimization, not permission to perturb the algorithm.
