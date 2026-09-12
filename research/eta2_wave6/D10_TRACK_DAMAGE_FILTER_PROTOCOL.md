# D10 protocol: a per-track damage filter for the Final3068 branch

Registered before building the active filter or running a native active arm.
The fixed-state numbers below are exploratory evidence inherited from the
wave-3/4 archives; they select the dimensionless rule, but they do not count as
a native result.

## Hypothesis and boundary

The categorical map proposes filter acceptance only if the Final3068 branch is
a discrete switch.  D2/D2c found that it is: FP64 fragments restore a smooth
small-perturbation map, while the recorded trajectories separate after a
controller decision.  A classical Fletcher--Leyffer filter, however, needs an
independent violation measure.  BA has no scored constraint violation, and the
already-tested global alternatives (lower rho, five-state nonmonotonicity and
monotone soft acceptance) do not provide one.

The E4 replay supplies a candidate local measure.  At accepted outer 6, both
proposals reduce full L2 by about 28k and improve the worst existing track, but
one previously fitted two-observation track is damaged by 256 in the eventual
hit trajectory and by 1794 in the eventual miss trajectory.  Define, for the
actual joint candidate at the proposed cameras,

```
delta_j = max(0, F_j(x+d) - F_j(x))
H       = sum_j delta_j
D       = max_j delta_j
q       = D / H
b       = D / (F(x) - F(x+d)).
```

The archived hit proposal has `(q,b)=(0.0178,0.00891)` and the miss proposal
has `(0.1127,0.0660)`.  D10 calls a proposal *concentrated-damage* when
`q > 0.05` and `b > 0.05`.  Both inequalities are scale-free and both are
required, so a harmless increase in the only worsening track does not fire the
rule.  This is a step filter, rather than a second objective: it asks whether
one track consumes an excessive fraction of both all local damage and the
global gain.  It leaves the scored objective unchanged.

## Stage 1: untouched-trajectory diagnostic

Derive a reversible diagnostic from the deterministic wave-6 optimized Eta2
binary.  For every full-L2-decreasing proposal, before the existing rho gate,
compute and log `(D,H,q,b)`, the maximising point, rho, accepted count and the
eventual endpoint.  The logging arm cannot alter a proposal or controller
state.  Run ten new deterministic Final3068 perturbations at field scale
`1e-10` and three unperturbed repetitions each on Venice52 and Ladybug539.

Proceed to an active arm only if all of the following hold:

1. at least one concentrated-damage event occurs in Final3068's first ten
   accepted outers;
2. the event rate is at most 5% of eligible proposals on Ladybug539;
3. concentrated-damage events are more frequent among Final misses than hits,
   with the direction reported without treating N=10 as a significance claim.

If the fixed thresholds fail, stop.  Do not tune them on these trajectories.

## Stage 2: paired active screen

If stage 1 passes, reject an otherwise champion-acceptable proposal only when
it is concentrated-damage and fewer than ten states have been accepted.  The
ordinary Eta2 rejection path updates lambda and radius.  The exact same
instrumented binary runs both arms; the off arm logs the metric and never
applies it.  Use twenty fresh deterministic Final3068 perturbations, identical
within each pair, alternating arm order.  Target is
`1744796.9841897595`, cap 45 native seconds and 600 outers.  Every endpoint is
independently rescored in FP64.

Promotion to Venice N=10 and the nine-cell panel requires at least three more
active-only than control-only target hits, at least one actual filtered step,
and median target time on double hits no worse than 1.20x.  Any failure stops
the filter without a threshold sweep.  Tail claims need N>=10; the frozen
scientific champion and the optimized systems candidate remain unchanged.

## Prior-art scope

Filter methods normally keep a nondominated frontier in objective and
constraint violation.  Here `q,b` are candidate-local diagnostics rather than
a constraint function, so their convergence theory does not transfer.  The
experiment tests a narrower BA mechanism: whether a globally successful step
should be vetoed when its damage is concentrated on one track.  A positive
native result would require a later convergence argument; a negative result
closes this measured filter signal, not filter methods in general.

