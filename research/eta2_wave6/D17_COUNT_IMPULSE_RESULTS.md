# D17 result: one projection impulse removes repeated cost, not basin ambiguity

## Verdict

D17 does not earn a fresh cohort.  On the registered 24-pair development
replay it reaches the Final3068 target in 10/24 runs versus 9/24 for the frozen
control.  There are two D17-only rescues, one control-only harm, eight double
hits and 13 double misses.  The net gain of one hit fails the preregistered
requirement of at least two.  The frozen Eta2 champion remains the winner.

This is design evidence on a previously measured cohort, not a confirmatory
hit-rate estimate.  No p-value is attached and no fresh seeds are run.

## Intervention and compatibility

D17 retains D16's count gate, raw/radius threshold (`>100`) and gated-energy
threshold (`>0.5`).  It projects the selected cameras on the first qualifying
attempt, marks the impulse spent before seeing acceptance, then runs ordinary
Eta2 forever.  Thus it is a one-time perturbation followed by infinite dwell,
with no threshold or cooldown tuning.

With D17 disabled, the derived binary exactly matches the D0v3 deterministic
parent in endpoint SHA256, every accepted cost string, normalized decision
trace, hit, outer, rejection, Schur-product count and final cost.

## Development replay

| Quantity | Control | D17 |
|---|---:|---:|
| Target hits | 9/24 | 10/24 |
| D17-only rescues / control-only harms | - | 2 / 1 |
| Double hits / double misses | 8 / 13 | 8 / 13 |
| Pairs receiving one impulse | - | 18/24 |
| Double-hit target-time ratio | - | 1.0011 median |

The D17-only rescues are seeds `660031` and `660040`; the control-only harm is
seed `660028`.  Median paired endpoint movement is `-0.00199%`, effectively
zero.  D17 eliminates D16's hundreds of repeated projections and its resulting
60-second cap hits, so the timing part of the hypothesis is correct.

The basin part is more complicated:

- seed `660040` is rescued by one impulse in both D16 and D17;
- seed `660031` is rescued only when the projection is not repeated;
- seed `660034` required D16's repeated interventions and is not rescued by
  D17;
- seed `660028` is harmed by the first impulse itself, so repetition cannot be
  the sole cause of D16's harms;
- seed `660035` is harmed by repeated D16 but remains a hit under one-shot D17.

The required intervention count is therefore trajectory-dependent and cannot
be inferred from D16's trigger alone.  Immediate nonlinear quality also does
not supply the missing sign: the harmful seed-660028 impulse raises rho from
about `0.523` to `0.868` and is accepted, just as the rescuing impulses are.
This is another concrete instance of the campaign's selection-perturbation
law: a locally better accepted proposal can select a worse future basin.

## Decision

The infinite-dwell cell closes without changing the frozen champion.  No
projection-count, outer-window, cooldown or threshold sweep follows.  The
mechanism remains usable as an ensemble branch: the union of control and D17
would hit 11/24, but that is a portfolio result and must count both trajectory
costs under a separate protocol.

Machine-readable evidence is in `d17-compatibility.json`,
`d17-development-results.json`, and `d17-development-summary.json`; source and
build provenance are under `d17_count_impulse/`.
