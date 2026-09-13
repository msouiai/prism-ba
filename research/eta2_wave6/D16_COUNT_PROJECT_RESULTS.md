# D16 result: hard local projection changes the basin but has no net advantage

## Verdict

D16 is not promoted.  In 24 preregistered deterministic pairs on Final3068,
the frozen control and D16 each reached the registered target in 9 runs.  The
four discordant pairs split exactly: two D16-only rescues and two control-only
hits.  The directional SPRT ended inconclusive at its cap (`LLR=-0.349`,
boundaries `+-2.944`), and the exact one-sided paired probability is `p=0.6875`.
The frozen Eta2 champion remains the scientific winner.

Hard projection is nevertheless a stronger causal intervention than D15's
finite local prior.  Paired endpoint changes range from `-9.06%` to `+2.18%`.
It can move a trajectory into either basin, so a starved camera is a genuine
branch variable but freezing it is not a directionally reliable policy.

## Registered intervention

The immutable D15 count gate selects the bottom `ceil(0.01*ncam)` cameras by
unique track count, also requiring a count below one quarter of the scene
median.  On an attempt with `||z_raw||/R > 100`, D16 activates only if selected
cameras carry more than half of the squared raw camera-step norm.  It then
zeros their eight active camera increments, recomputes the norm, applies the
ordinary global clip, recompletes the point step, and evaluates the full model
and full plain-L2 objective on that actual step.

This is the infinite-prior, active-constraint limit of D15.  Healthy camera
increments are unchanged before the ordinary global clip.  The derived binary
with D16 disabled exactly reproduces the deterministic parent in endpoint
SHA256, every accepted cost string, normalized decision trace, hit, outer,
rejection, and Schur-product counts.

## Fixed-state motivation

On the two archived high-ratio Final3068 witnesses, projecting the original
camera direction increased true decrease by `15.53%` and `35.37%`, and raised
rho from `0.2664` to `0.5238` and from `0.2674` to `0.4355`.  A benign witness
would lose `80.8%` of its decrease, but its ratio is only `39.3`, so the native
rule cannot activate there.  These replays selected the limiting actuator and
were not counted as fresh evidence.

## Paired result

Seeds `660024..660047` use byte-identical `epsilon=1e-12` perturbed inputs in
both arms.  The target is `1744796.9841897595`, with the unchanged 60-second
native cap and full FP64 endpoint rescore.

| Quantity | Control | D16 |
|---|---:|---:|
| Target hits | 9/24 | 9/24 |
| Variant-only / control-only hits | 2 | 2 |
| Double hits / double misses | 7 / 13 | 7 / 13 |
| Activated pairs | - | 18/24 |
| Total projections | - | 2,357 |
| Double-hit target-time ratio | - | 1.0023 median |

The seven double-hit time ratios range from `0.927` to `1.063`, so the
prototype's host-side diagnostic overhead is negligible when D16 is inactive
or fires once.  Repeated activation can be very expensive: two misses hit the
60-second cap after roughly 500 projections.  Those runs are retained in every
reliability statistic.

The two D16-only rescues are large:

- seed `660034`: control `1.8463M`, D16 `1.7438M`, 14 projections;
- seed `660040`: control `1.9175M`, D16 `1.7437M`, one projection.

The two control-only hits show the opposite effect:

- seed `660028`: control `1.7199M`, D16 `1.7574M`, 65 projections;
- seed `660035`: control `1.7402M`, D16 `1.7673M`, 77 projections.

Pairs with no activation are bit-identical.  The median paired endpoint change
over all pairs is `-0.0560%`, below the campaign's practical quality threshold.

## Interpretation and next test

Count starvation is a valid sparse detector, and the selected camera can
control basin selection.  Neither a finite quadratic prior nor a persistent
hard constraint supplies the missing directional information.  D16's repeated
projection changes the optimisation problem for the remainder of difficult
runs; the low-activation rescues and high-activation harms motivate a separate
dynamical-systems test of a single impulse followed by an infinite dwell time.
That is a new registered intervention, not a tuned D16 threshold.

Machine-readable evidence is in `d16-paired-compatibility.json`,
`d16-paired-results.json`, and `d16-paired-summary.json`; build and source
manifests are under `d16_count_project/`.
