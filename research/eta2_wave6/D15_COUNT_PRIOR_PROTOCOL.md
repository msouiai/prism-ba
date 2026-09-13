# D15 protocol: sparse count-gated camera prior

Registered 2026-09-13 after the C1 effective-resistance result and before
constructing or scoring any modified fixed-system direction.

## Question

C1 showed that Final3068 camera 550 is globally starved, but that the expensive
effective-resistance rank adds no useful information over its unique-track
count.  Wave 3 showed why detection alone is insufficient: global clipping and
broad block floors can identify a bad camera and still make the nonlinear
trajectory worse.  This experiment asks whether a **sparse, count-selected
camera prior inside the coupled Schur solve** preserves the healthy-camera
direction at the three archived Final3068 terminal witnesses.

This is a fixed-state mechanism test.  It makes no endpoint, hit-rate, speed or
novelty claim unless the fixed-state gate below is passed.

## Immutable camera gate

At load time count unique observed tracks per camera.  Let `m` be the median
count and `q = ceil(0.01*n_cam)`.  Sort cameras lexicographically by
`(count, camera_id)` and select the first `q` cameras whose count is also below
`m/4`.  Thus at most one percent of cameras is touched (up to the unavoidable
ceiling for a finite camera count), ties are deterministic, and the threshold
is the count-starvation definition already used in wave 3.  No cost, step,
seed, endpoint or scene identity enters the gate.

## Prior and diagnostic doses

Reconstruct each camera's coherent scaled Schur diagonal block

`B_i = E_i (U_i - W_i V^-1 W_i^T) E_i`

from the same captured fragments and point factors used by the operator.  Let
`mu_ref` be the median largest eigenvalue of the ungated active 8 by 8 blocks.
For each gated camera form

`Delta_i(a) = Q_i diag(max(0, a*mu_ref - mu_ik)) Q_i^T`

on the eight active coordinates; inactive `k2` stays untouched.  This is a
Gaussian information prior / modified-Newton floor applied only where the
combinatorial gate says observations are insufficient.  Doses are fixed in
advance at `a in {0, 1, 10, 100, infinity}`.  `infinity` is implemented as the
well-defined constrained limit: all active increments of a gated camera are
zero.  The dose grid is diagnostic and does not license a scene-specific
native configuration.

For every dose solve the full coupled reduced system from zero with the frozen
Eta2 Hcc preconditioner modified by the same `Delta`, stopping at Eta2's
Euclidean relative-residual threshold `eta=0.5`.  Also compute and report the
explicit true residual.  Clip the resulting camera vector to the archived
radius exactly as Eta2 does, re-complete every point from the clipped camera
step, and score every original observation in FP64 on the plain L2 objective.

The three witnesses are frozen captures 0, 5 and 6 from
`eta2_research_20260912/evidence/collect/final-3068-capture-*`.  Their archived
states, lambdas, radii and input hashes are immutable.  Reconstructed fixed
systems must reproduce each archived initial objective to `1e-8` relative and
the unmodified direction's true decrease to `1e-6` relative or `1e-6`
absolute.  A larger discrepancy stops the experiment as an invalid replay.

## Selection and promotion gates

The diagnostic selects the **smallest finite dose** which, on both high-ratio
witnesses 5 and 6:

1. raises true decrease by at least 0.15% relative to the unmodified clipped
   direction (with a `1e-6` absolute floor),
2. does not lower `rho`, and
3. leaves at least 95% of the ungated cameras' unscaled step norm available
   before the final global clip.

It must also leave witness 0's true decrease within 0.15% or be inactive there.
The constrained `infinity` row is an explanatory bound only and cannot be
selected for production.

If no finite dose passes, count-gated priors stop at the fixed-state negative.
If a finite dose passes, the native arm is the same gate and dose everywhere,
activated only when `raw_norm/R > 100` and gated cameras carry over half of raw
step energy.  The activation quantities are measured before changing the
direction and add no controller memory.  Native testing is Final3068 N=10 at
the registered target, then Venice52 N=5 and the nine practical cells N=3.
Kill on no Final hit-rate gain, any Venice endpoint regression above its floor,
or disjoint slowdown/regression on at least five practical cells.

## Boundary

Effective resistance, observability priors, Gaussian camera priors, modified
Newton eigenvalue floors and freezing under insufficient support are all
established ideas.  A positive result could support a mechanism claim about
sparse combinatorial gating of a Schur-space prior; the method itself would
still require a primary-source prior-art audit before any novelty claim.
