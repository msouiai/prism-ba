# D2c protocol: does FP32 fragment quantisation create the finite jump?

Registered after D2b classified both openings as finite-jump plateaus and
before building or running the FP64-fragment diagnostic.

The derived diagnostic changes exactly one numerical representation in the
deterministic B6v7 path: the stored camera/point Jacobian fragments change from
FP32 to FP64.  State, residual evaluation, normal-equation arithmetic, fixed
reduction trees, solver flags, stopping rules, compact camera-major ordering,
and ten-outer horizon remain fixed.  This is an attribution experiment, not a
production candidate; all overhead is reported.

Venice52 is the primary scene because all 20 D2b pairs retained identical
global accept/reject and CG-depth sequences, yet their ten-outer distance
plateaued near 0.006.  Use the same seeds 620000--620003 and doses
`{1e-8, 1e-10, 1e-12}`.  Run two unperturbed trajectories first; their state,
cost, discrete-decision and work hashes must be exact matches.

Let `D10_64(epsilon)` be the median FP64 residual-space separation.  Compare
its log-log slope with the FP32-fragment D2b slope over the same three doses.

- **FP32 fragments explain the jump:** FP64 slope is at least 0.75, all three
  median amplification values are within 5x, no discrete choice differs, and
  the `1e-12` median D10 falls by at least 100x from the FP32 result.
- **FP32 fragments do not explain it:** FP64 slope is at most 0.25 and its D10
  maximum/minimum ratio is at most 3.
- otherwise report **partial attribution**.

If the first condition passes, Final3068 may be run later as a separately
registered secondary diagnostic.  It is not part of this gate because its
known accept/reject splits confound the precision source with the controller.
No endpoint quality or speed claim follows from this diagnostic.
