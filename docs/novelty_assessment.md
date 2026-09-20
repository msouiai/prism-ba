# Publication assessment during the expanded study

**Current verdict: Prism is not yet supported as a novel, broadly superior
BA algorithm.** The local experiment suite is still running. Completed
mechanism checks and closer prior art already narrow what a paper can claim.
This is an interim assessment, not a completed benchmark verdict.

## What has been established

The full eight-snapshot linear audit is complete, with three alternating
shared/independent repetitions at each of two tolerances. At the initial
linearization, shared CG saves 1.63–1.77x wall time at matched true residual
accuracy. None of the outer-5 snapshots passes the full accuracy gate:
iteration limits and nonfinite high-shift solutions prevent a speed claim.
See [the complete table](krylov_audit_results.md) and
[validation limitations](novelty_validation_notes.md).

The mathematical analysis explains why a camera damping menu can still
require retries: increasing camera damping does not generally shrink the
point increment to zero when point damping is fixed. Bounded backtracking
can help, but eight probes do not guarantee rescue. The block and congruence
identities and nonlinear counterexamples pass the included numerical checks.
These are explanatory classical facts, not new convergence theorems.

There is a closer precedent than plain shifted CG:
[Lin, O'Malley and Vesselinov's LM-RLSQR (2016)](https://agupubs.onlinelibrary.wiley.com/doi/10.1002/2016WR019028).
It already combines basis reuse across damping values with nonlinear
candidate selection. Our inference is that Prism needs a specific additional
BA contribution and evidence for it; this broad combination cannot be the
paper's claimed first invention. See [the prior-art and theory audit](novelty_analysis.md).

## Work executing under the frozen protocol

- Caspar-fp32 defaults and a declared development profile, with returned
  states evaluated in CPU fp64 against original double observations.
- Four identical-binary Prism arms: one/five shifts, safeguard off/on.
- Joint-damping Ceres LM and traditional Dogleg, with a small development
  grid and global profiles frozen before follow-up evaluation.
- Four evaluation scenes, six perturbed initializations, three repetitions
  per cell, and the full 600-outer budget on the largest scene.

[Retained measurements](novelty_results.md) are regenerated during the runs.
The raw progress manifest is `/workspace/prism-novelty/study-status.json`.
Missing cells and failed runs are retained. A monitor refreshes reports and
plots when all declared local nonlinear cells have returned. Completion of
that manifest does not supply a second GPU or automatically prove novelty.

The Ceres CPU baseline is a nonlinear algorithm comparison, not an equal-GPU
implementation comparison. Prism endpoint objectives currently come from its
GPU double implementation, with independently checked initial costs;
Caspar/Ceres endpoints have separate CPU checks. Hardware and validation
scope are disclosed rather than conflated.

## Decision criteria

A viable algorithmic claim requires multi-shift plus safeguard to improve
quality-versus-time over single-shift plus the same safeguard across
instances, not merely show fewer rejected attempts. It must also explain
its advantage over established globalization and recycled-damping methods.
A linear speedup on easy snapshots is insufficient when later solves fail
accuracy checks. Mixed or negative measurements should lead to a narrower
engineering contribution or a revised solver, not post-hoc benchmark tuning.

Only one GPU is accessible. The second-GPU replication package is prepared
at `/workspace/prism-novelty/replication`; replication remains unperformed.
No publication-readiness or cross-hardware robustness claim is warranted yet.
