# B6v2 dots-only PCG protocol

Registered after the combined B6 arm completed and before any B6v2 solver
outcome.  B6 showed a 3.62% practical-panel speedup but fused PCG vector
updates changed floating-point rounding and sampled a slower Final3068 tail.
This isolation retains only the synchronization change:

1. `p^T A p` and `p^T p` remain ordinary FP64 cuBLAS dot products, with
   device result pointers and one 16-byte host copy for the pair.
2. After the existing preconditioner application, `r^T r` and `r^T z` are
   evaluated in the same way.  Moving the preconditioner before `r^T r` is
   legal because it only reads `r` and writes `z`.
3. Every `DAXPY` and `DSCAL` call, including its ordering and rounding point,
   is restored exactly to the frozen champion.

The arm is `OCA_W5_CG_DOTS=1` and is legal only on the champion-like CD=9,
single-shift, unshared, PCG path.  No custom reduction, operator, recurrence,
forcing rule, controller, or objective change is allowed.

Run N=3 disabled compatibility, then the N=3 nine-cell practical panel.
Proceed to the N=3 Muell/profile cohorts and fresh N=10 Venice52/Final3068
tails only if panel geometric-mean target time improves with unchanged median
product counts.  Promotion requires no stable endpoint movement above 0.15%,
no tail hit-rate loss, and a practical timing gain.  If dots-only loses most
of B6's speed, the vector fusions may be retained only as a documented
arithmetic-changing experiment, not as a transparent optimization.

