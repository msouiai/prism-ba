# D16 protocol: count-gated camera projection before global clipping

Registered 2026-09-13 after D15 closed and before building or running a D16
native binary.  D15 established that its immutable count/ratio gate is local
and causal, but a finite dose-one prior rescued only one of 24 deterministic
pairs.  This experiment changes the actuator while retaining that gate.

## Motivation and fixed rule

When `raw_norm/R > 100` and the D15 bottom-one-percent count gate carries more
than half of the raw camera-step energy, set the eight active increments of
those gated cameras to zero.  Recompute the camera norm, apply Eta2's unchanged
global radius clip to the remaining vector, back-substitute every point from
that actual camera step, and evaluate the full plain-L2 objective.  `k2` stays
fixed as in the champion.  The full-model prediction and rho are evaluated on
the projected and clipped joint step, so acceptance is honest.

This is the constrained limit of a local Gaussian prior, or equivalently an
active-set removal of locally unobservable camera variables for one attempt.
It differs from the failed global cap and block-floor experiments: the
combinatorial gate touches at most one percent of cameras and leaves every
healthy camera increment bit-identical before the ordinary global clip.

An exploratory replay made the choice between another finite dose and this
limiting actuator.  Projecting the original direction raises true decrease by
15.53% and 35.37% at archived high-ratio witnesses 5 and 6 and raises rho from
0.2664 to 0.5238 and 0.2674 to 0.4355.  It would hurt the benign witness by
80.8%, but that witness has raw/R=39.3 and therefore cannot activate the
registered native rule.  These observed replays select the mechanism; they
are not counted as fresh evidence.

## Deterministic paired gate

Apply the D16 transformation to the checksum-pinned D0v3 deterministic B6v7
source.  The feature-disabled binary must exactly match the D0v3 parent on the
Ladybug539 1.01 cell in endpoint SHA256, every accepted cost string, normalized
decision trace, hit, outer, rejection, and Schur-product counts.

Use fresh Final3068 perturbation seeds `660024..660047` at `epsilon=1e-12`.
Both arms in a pair receive byte-identical input.  Target, cap, objective and
all champion/system flags are unchanged: target `1744796.9841897595`, cap 60
seconds, SIMPLE_RADIAL, unshared intrinsics, `k2=0`, full FP64 endpoint audit.
Alternate arm order.

Primary inference is a directional Wald SPRT on discordant target hits with
`q0=0.50`, `q1=0.70`, `alpha=beta=0.05`, maximum 24 pairs, where q is the
probability of a D16-only hit conditional on discordance.  Stop only at a
registered boundary or the pair cap.  Promotion also requires median D16/control
time-to-target at most 1.20 on double hits.  Report exact one-sided McNemar,
paired endpoint deltas, projection count, and post/pre-projection norm ratio.

If the upper boundary is crossed, continue to ordinary stochastic Final3068
N=10, Venice52 N=5, and the nine practical cells N=3.  If harmful, stop.  If
inconclusive at cap, retain the champion and close this local-actuator cell;
do not tune the ratio, energy fraction, count quantile, or projection strength.
