# B4 direct reduced solve protocol

Registered before any B4 solver outcome is run.  The frozen Eta2 champion and
all nonlinear controls remain unchanged.  The sole intervention is selected by
the camera-system dimension: when `9*ncam <= 1536`, explicitly form the same
equilibrated damped Schur operator used by Eta2 and solve it with FP64
cuSOLVER Cholesky.  Larger systems use the original camera-block-PCG path
bit-for-bit.  The threshold is fixed from the wave-5 brief's `n_c <= 2000`
range, reduced to 1536 because the test GPU has 1/64-rate FP64 and because it
covers Venice52 (`n_c=468`) and Trafalgar138 (`n_c=1242`) while bounding the
dense buffer at 18 MiB.

The dense matrix is formed from Eta2's already-rounded camera-point fragments,
the current point factor, the current diagonal scaling, and the persistent
camera-edge CSR.  Thus it represents the same numerical operator as the
matrix-free product; this experiment changes solve accuracy and algebraic
execution, not derivatives, damping, scoring, radius clipping, or acceptance.
On Cholesky failure the attempt falls back to the original PCG and records the
failure.

Gates, in order:

1. N=3 disabled-mode compatibility against the frozen champion.
2. One operator audit on Ladybug49: compare a dense product before
   factorisation with the existing matrix-free product on the registered RHS;
   require relative L2 error below `1e-5`.
3. N=3 paired practical panel.  The selector should touch only Trafalgar138;
   untouched cells are a control for dispatch neutrality.
4. N=5 Venice52 and Final3068 tails.  Venice exercises the direct path;
   Final3068 must remain bit-compatible because it is above the threshold.

Report formation and factor/solve wall separately under `OCA_PROFILE`, direct
solve/fallback counts, targets, endpoints, outers, rejects, and matrix-free
products.  Promote only if Trafalgar time-to-target improves with disjoint
ranges and Venice reliability does not fall.  Kill if formation plus FP64
factorisation costs at least as much as the PCG it replaces, if the audit
fails, or if exact directions harm either selected scene's hit rate.  No
threshold tuning after outcomes.
