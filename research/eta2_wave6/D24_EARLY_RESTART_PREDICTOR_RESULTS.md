# D24 result: no interpretable outer-15 signal predicts Eta2 misses

## Verdict

D24 fails its development gate, so the sealed 38-run D21 held-out cohort is
not parsed and no online restart scheduler is built. None of five
preregistered scalar controller/progress features reaches even `0.62` balanced
accuracy on the 80-run fit split, and none reaches `0.61` on the chronological
50-run validation split. The MFREE observation that lambda history predicts a
Final3068 basin does not transfer to Eta2 in this form.

The unchanged arithmetic restart remains useful because independent attempts
are nearly independent, not because Eta2 exposes a reliable early hardness
signal. The frozen solver winners and portfolio labels remain unchanged.

## Blinded design

Development uses the 130 B6v7 gated runs with repetitions 20--149. Repetitions
20--99 fit one univariate threshold; repetitions 100--149 validate it. Before
parsing development, SHA-256 hashes sealed every stdout log, curve, result, and
the episode ledger for the 38 D21 first attempts. The development program has
no code path to those files.

Every feature uses only state available after completed outer 15. For each
feature, both threshold orientations are fitted on training, with a frozen
preference order. Advancement requires training balanced accuracy at least
`0.80`, validation balanced accuracy at least `0.75`, and validation miss
sensitivity and hit specificity each at least `0.70`.

All 130 development runs have complete checkpoint data.

## Results

| Feature | Fit orientation / threshold | Train balanced accuracy | Validation sensitivity | Validation specificity | Validation balanced accuracy |
|---|---|---:|---:|---:|---:|
| log10 lambda at 15 | low / -6.7637 | 0.586 | 0.167 | 0.750 | 0.458 |
| max log10 lambda, 10--15 | high / -5.1674 | 0.612 | 0.333 | 0.625 | 0.479 |
| rejects through 15 | high / 2.5 | 0.556 | 0.111 | 0.844 | 0.477 |
| max raw/radius, 10--15 | low / 33.963 | 0.589 | 0.722 | 0.406 | 0.564 |
| cost/target at 15 | high / 1.09046 | 0.619 | 1.000 | 0.219 | 0.609 |

The apparent strongest miss detector, cost/target, labels all 18 validation
misses but also labels 25 of 32 eventual hits as misses. Acting on it would
abort most successful trajectories and destroy the portfolio's fast path.
The controller-specific features are worse: post-lambda, maximum lambda, and
rejection count all validate below chance in balanced accuracy. Raw/radius has
some miss sensitivity but only 40.6% specificity.

No feature passes the training threshold, so selecting by its validation value
would already violate the registered protocol. There is no chosen rule and no
post-hoc multivariate combination.

## Implication

Eta2's Final3068 basin outcome is not encoded by a simple outer-15 lambda,
rejection, clipping, or cost scalar. This agrees with the earlier finding that
very close arithmetic trajectories can separate later through discrete
solver/controller branches. A useful racing policy would need either saved
and resumable parallel trajectories or a richer learned state representation;
learned components are excluded in this campaign. The honest scheduler remains
fresh independent attempts without early prediction.

## Evidence

- `D24_EARLY_RESTART_PREDICTOR_PROTOCOL.md`
- `d24-heldout-inventory.json`
- `d24_early_restart/analyze.py`
- `d24-development-results.json`

