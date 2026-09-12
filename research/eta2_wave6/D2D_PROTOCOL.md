# D2d protocol: FP64-fragment attribution on Final3068

Registered after the Venice D2c result and before running Final3068 with FP64
fragments.  This is the secondary diagnostic allowed by D2c, using the same
derived binary, seeds 620000--620003, doses `{1e-8, 1e-10, 1e-12}`, fixed
reductions, ten-outer horizon, and FP64 residual-space metric.

Report the log-log slope of median absolute separation at every saved outer and
the first discrete global, CG, or point-safeguard split.  Compare with the
matching FP32 D2b rows.

The registered mechanistic gate is passed if FP64 does either of the following:

1. keeps the perturbation slope in `[0.75, 1.25]` for at least two outers longer
   than FP32; or
2. reduces median `D10` at `epsilon=1e-12` by at least 100x without introducing
   an earlier discrete split.

Passing the gate permits, but does not promote, a full-convergence paired
robustness experiment.  Failure means fragment quantisation explains Venice's
smooth-map defect but is not the leading Final3068 branch mechanism.  This
diagnostic makes no endpoint or speed claim.
