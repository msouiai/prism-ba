# D17 protocol: one count-gated projection impulse with infinite dwell

Registered 2026-09-13 before building or running D17.  This is a
dynamical-systems/hysteresis follow-up to D16, not a new starvation threshold.

## Fixed intervention

Retain D16's immutable camera gate and trigger exactly:

- bottom `ceil(0.01*ncam)` by unique track count and below one quarter of the
  scene median;
- `||z_raw||/R > 100`;
- selected cameras carry more than half of squared raw camera-step energy.

At the first qualifying attempt only, set the eight active increments of the
selected cameras to zero, recompute the norm, apply the ordinary global clip,
back-substitute points, and score the full model and plain-L2 objective on the
actual step.  Mark the impulse spent before acceptance is known.  Every later
attempt is bit-identical to ordinary Eta2; there is no reset after rejection
and no second projection.  This is an infinite dwell time after one local
impulse.  It tests whether D16's repeated constraint, rather than its first
basin perturbation, caused its symmetric harms and long cap-hit runs.

## Compatibility

Derive from the checksum-pinned D0v3 deterministic B6v7 source.  With D17
disabled, require exact agreement with the D0v3 parent on Ladybug539 1.01 in
endpoint SHA256, accepted-cost strings, normalized decision trace, hit, outer,
rejection, Schur-product count and final cost.

## Development replay and advance rule

Replay D17 on the 24 already-spent D16 perturbations (`660024..660047`,
`epsilon=1e-12`) and reuse their exact deterministic control rows.  This cohort
is design evidence and carries no confirmatory p-value.  Report all pairs,
hit classifications, endpoints, trigger outer, and target time.  D17 earns a
fresh preregistered cohort only if:

1. it has at least two more hits than control (at least two net rescues);
2. it creates at most one control-only harm;
3. its median D17/control target-time ratio on double hits is at most 1.20.

Otherwise close this dwell-time cell without tuning a projection count,
cooldown length, ratio, energy threshold, count quantile, or outer cutoff.

If the gate passes, register fresh seeds `660048..660071` and the same
directional SPRT used by D16 before generating those inputs.  The frozen Eta2
champion remains the winner until that fresh test crosses its upper boundary.
