# D24 protocol: an interpretable early signal for Eta2 restart racing

Registered 2026-09-13 after D23 closed and before parsing the development or
held-out controller trajectories.

## Hypothesis

The unchanged three-attempt B6v7 portfolio reaches the Final3068 target in
`37/38` episodes but wastes a complete solve before each restart. On the MFREE
line, the lambda trajectory around outers 10--15 was a strong basin predictor.
Eta2 may expose the same information in its controller state even though cost
at outer five was already rejected as an early predictor.

This is a diagnostic for a fixed scheduler rule. It does not train or insert a
learned solver component. If a single scalar threshold does not transfer, no
multivariate model, scene-specific rule, or threshold sweep follows.

## Data split and blinding

Development uses only the 130 B6v7 gated runs with repetitions 20--149 in
`eta2_wave5/b6v7-extension-results.json`:

- threshold fit: repetitions 20--99 (80 runs);
- chronological validation: repetitions 100--149 (50 runs).

The final test is the first attempt from each of the 38 fresh D21 episodes.
Before development parsing, an inventory freezes the SHA-256 of every held-out
stdout log, curve, result, and the D21 episode ledger. Development code cannot
open those paths. A test stage is written but refuses to run without a second
registration containing the selected development rule and its result hash.

## Fixed checkpoint and features

All features use only information available after completed outer 15
(`o=0..14` in attempt logs). Runs reaching the target before then would be
classified as known successes and need no prediction. The five candidate
scalars, in mechanism-priority order, are:

1. `log10_lambda15`: log10 of the final post-decision camera lambda at outer 15;
2. `max_log10_lambda10_15`: largest pre/post camera lambda over outers 10--15;
3. `rejects15`: rejected attempts through outer 15;
4. `max_raw_radius10_15`: largest raw camera norm divided by radius over outers
   10--15;
5. `cost_ratio15`: accepted cost after outer 15 divided by the fixed target.

For each feature independently, fit both threshold orientations on the first
80 runs and select the threshold with maximum balanced accuracy. Ties use the
smallest numerical threshold and then `high => miss`. Choose the first feature
in the priority list whose fitted rule satisfies every gate below on the
chronological validation set. This preference rule is frozen before values are
read and avoids post-hoc selection of the best validation score.

## Development and held-out gates

A rule advances only with:

- training balanced accuracy at least `0.80`;
- validation balanced accuracy at least `0.75`;
- validation miss sensitivity at least `0.70`;
- validation hit specificity at least `0.70`;
- complete checkpoint data for every run.

The threshold is fitted on training only and frozen. The D21 held-out test
passes only if balanced accuracy remains at least `0.75`, miss sensitivity at
least `0.70`, and hit specificity at least `0.70`. Report confusion matrices,
class counts, all five fitted development rules, and Wilson intervals for
sensitivity and specificity. The test is descriptive at N=38; passing earns a
fresh prospective scheduler experiment, not promotion.

If development fails, stop without reading held-out values. If held-out fails,
close the fixed early-predictor path. No threshold movement is permitted after
either failure.

