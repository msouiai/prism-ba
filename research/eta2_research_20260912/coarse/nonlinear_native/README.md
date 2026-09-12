# Native passenger correction at a confirmed FTOL stop

Registered by `../../PROTOCOL_09_NATIVE.md`. The original source and defaults
are unchanged. `build.py` verifies the pinned source/44 headers and inverse
applies all twelve overlays to recover that source exactly.

Binary: `build/prism-passenger`; switch: `OCA_PASSENGER=1` (unset/0 is off).
Use the frozen champion CLI and flags. `OCA_STCG_ATTEMPTS=/absolute/path.json`
uses the exact common attempt-trace header, byte-identical to `../../steihaug`.
The build manifest records source, headers, protocol, compiler and binary hash.
Build with `TMPDIR=/dev/shm`; no fast-math flags are used.

At the first surviving FTOL/function-tolerance stop, after the champion's
ordinary backtrack confirmation/rearming policy, queue one fresh assembly.
Do not intervene for outer-cap, wall-budget or max-failure-only stops. At the
next outer the current state, lambda, point factors and E are fresh. The hook
runs before the forcing-history assignment overwrites `prev_bnorm`. If the
budget expires first, no correction is attempted.

The exact three-attempt passenger model is used: K8 deterministic center
clustering, first-original-observation point anchors, fixed initial centroids,
fixed joint metric, seven local similarity coordinates subject to rank 1e-10,
undamped GN prediction, alpha 1 through 1/256, accept gain>0 and rho>.1. Coarse
lambda starts at current fine lambda; failed attempts multiply it by ten and
accepted rho>.75 divide it by ten. Nonfinite/failed coarse Cholesky also counts
as a failed attempt. The coarse model does not inherit the fine radius clip.

GPU kernels build the small normal from the two local cluster Jacobian blocks,
apply similarities, and use the native `ComputeCost` on all original
observations. Same-cluster rows are analytically zero only in the derivative;
their observations remain in every objective score. Intrinsics are fixed.
CPU handles clustering, joint stacked-metric QR followed by 7x7 SVD, and the
small dense solve. The metric QR is a real CPU pass over camera/point data,
not free setup. All transfers/setup/work are inside the native solve clock.
Owned device buffers are destroyed before the correction's CSV/target stamp.

An accepted correction resumes at the same next outer after reassembly. Fine
lambda, radius, numerical floor, forcing history, last relative progress and
backtracking confirmation are preserved, with before/after values printed.
Only convergence bookkeeping is reset: FTOL/failure counters, convergence
flag, previous cost. No coarse accept is mislabeled as an LM accept. An episode
with zero accepted steps honors the pending stop; no repeated intervention.

## Work and trace accounting

`PASSENGER_TRIAL` reports every alpha, predicted/true gain, rho, lambda,
decrement, solve residual and cross-cluster observation count.
`PASSENGER_SUMMARY` reports attempts/accepts/backtracks/full scores/normal
assemblies/setup and episode wall. Its PCG-products count is explicitly zero.
`PASSENGER_EVENT` identifies pending/probe/fine-continuation and the exact
zero-based common trace row. Probe work is inside a common trace row with zero
ordinary LM accepts and zero PCG products; it must not be counted as an
ordinary nonlinear rejection. `trace_report.py RUN_FOLDER` preserves raw
totals and writes `passenger_trace.json`, separating this work and exposing
corrected unchanged-state retry wall. The following fresh fine continuation
has `raw_retry_entry=0`; it is not an unchanged-state retry.

Normal CSV rows contain correction cost and the actual post-correction wall,
including copies and buffer destruction. Duplicate outer indices are possible
because coarse work is not counted as an ordinary LM outer. Use the first
time-indexed full-objective crossing, not the earlier FTOL stop timestamp.

## Completed correctness gates

`toy_verification.json` compares native GPU matrices/actions with the separate
CPU passenger reference. Normal relative error 2.01e-16; gradient 1.35e-13;
joint metric 6.13e-15; action 3.55e-15; same-cluster image drift 1.14e-13 pixels.
Clustering, anchors and joint rank agree. Kernel memcheck/leak-check passes;
native tiny off/on memchecks pass, with the true stop hook exercised once.

The tiny native problem at fine lambda 1e-16 shows the expected finite-precision
limit of a Gram normal with gauge modes: coarse Cholesky fails on two attempts,
and the intermediate raised-coarse-lambda attempt succeeds. This is retained;
the fine numerical floor is not raised by those coarse failures.

`compatibility.json` contains N3 original/off runs on Dubrovnik88. Median costs
358945.593104 vs 358945.628309, relative delta 9.81e-8. Original seconds
[.411126,.416281,.421372], off [.411372,.409494,.421883]; ranges overlap.
This is compatibility evidence only. No active-arm efficacy grid was run here.
