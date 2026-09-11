# Same-state Venice52 curvature audit — 2026-09-11

This is a diagnostic, not an optimization or speed experiment. Freeze the
previous depth-rescue source/binary/config and reproduce three independent
first curvature-cutoff failures in the one-shot de-clipping probe. Keep the
original input, lambda, point damping, state, scaling E and search direction
fixed for all comparisons within a capture. No recovery policy, floor,
precision or controller change is committed to the running solver.

MFREE's reported six FP64 trajectories reach 241602–241656 with no cutoff
at 300 outers. That is supporting cross-trajectory evidence, not a same-state
causal test. No endpoint states from the other solver are needed here.

## Registration before diagnostic runs

- N=3 Venice52 captures (BAL filename `venice-52.txt`), at the first cutoff
  in `OCA_DEPTH_DECLIP=1`. Same champion configuration and inherited depth
  cap512, residual tolerance1e-3, radius expansion4. Stop after capture.
- Record actual pAp, pp, quotient, damping, CG index, state and cost.
  Classify nonfinite, strictly negative, zero, or small-positive quotient
  failing `pAp > 1e-14*pp`. Do not call every cutoff negative curvature.
- Repeat the same mixed operator product five times on the identical
  direction to estimate atomic reduction variability, without changing data.
- Rebuild the unrounded cross blocks and point Jacobians in FP64 directly
  from the exact captured state, using the same analytic Jacobian function.
  Hold original camera block Hcc, scaling E, camera shift and Cdiag-based
  point damping fixed when swapping components.
- Evaluate: stored cross + stored point factor; stored cross + QR recomputed
  from stored FP32 point rows; FP64 cross + stored factor; stored cross +
  FP64-point QR; FP64 cross + FP64-point QR. Record same-vector GPU products.
  The extra stored-row QR distinguishes the guarded Cholesky/QR preparation
  algorithm from precision loss in the point rows themselves.
- Export all operator components, direction and products. Independently
  compute scalar Schur Rayleigh quotients on the CPU with extended-precision
  accumulation and triangular solves from the exported factors. Compare
  with GPU signs and values, not other optimization endpoints.
- Independently evaluate the nonnegative full-Jacobian energy with points
  eliminated at FP64 precision, including point damping, intrinsic priors
  and camera damping. This avoids subtracting two large positive quadratic
  terms and checks consistency of the FP64 Schur reference.
- Quantify component rounding, cross/point interaction, and finite arithmetic
  discrepancies. Attribute numerical inconsistency only if supported by
  same-vector evidence. A sign reversal does not prove a faster optimizer,
  successful target crossing, or equivalence to MFREE's full implementation.

Builds, solves and CPU audits use `/tmp/prism_gpu.lock`. Diagnostic overhead
is explicitly excluded from performance claims. Preserve compressed arrays,
exact state and trace hashes. Keep both the original champion and the prior
negative depth-rescue experiment unchanged on their existing branches.
