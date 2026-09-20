# Adaptive menu: completed four-scene pilot

**Verdict: promising relative to fixed five-shift scoring, but not a universal
replacement for fixed one-shift.** All 36 runs succeeded (three configurations,
four scenes, three repeats), using one frozen executable and a 600-outer cap.
The controller was unchanged between development and evaluation.

## Time to acceptable quality

The reference is the lowest endpoint observed across these fixed arms on each
scene, not a known optimum. Numbers are median conservative solver-time
crossing bounds. Missing attainment remains missing.

| Scene | Single, within 3% | Five shifts, within 3% | Adaptive, within 3% |
|---|---:|---:|---:|
| Venice-52 (development) | not reached in 3/3 | 10.874 s | 3.877 s |
| Ladybug-1197 (development) | 0.466 s | 0.891 s | 0.619 s |
| Ladybug-598 (evaluation) | 0.189 s | 0.278 s | 0.232 s |
| Trafalgar-126 (evaluation) | 0.236 s | 0.323 s | 0.282 s |

Adaptive beats fixed five-shift at this band on all four scenes, with disjoint
observed three-run ranges. Fixed one-shift is faster on three scenes but does
not reach this band's Venice target. N=3 ranges are not distributional or tail
guarantees; the evaluation scenes were held out from development of this
controller, but had appeared in the previous fixed-arm study.

At the tighter 1% band, adaptive is the only configuration that reaches the
Venice target in all repeats (median 8.450 s). It also improves Trafalgar's
crossing bound to 0.370 s from 1.019 s for five shifts and 1.123 s for one.
However, adaptive is slower at 1% on both Ladybug scenes. At the 5% band,
adaptive beats five-shift median times on all four scenes again, while
single-shift remains faster on both Ladybug scenes and Trafalgar.

## Endpoint tradeoffs

Changes below are adaptive relative to fixed five-shift medians.

| Scene | Final cost change | Full solver-time change | Retries, five → adaptive | Total scored change |
|---|---:|---:|---:|---:|
| Venice-52 | -1.888% | -8.60% | 0 → 0 | -23.27% |
| Ladybug-1197 | +0.115% | -28.65% | 299 → 143 | -0.81% |
| Ladybug-598 | -0.164% | +25.09% | 0 → 0 | +9.45% |
| Trafalgar-126 | +0.00013% | -22.24% | 0 → 0 | -36.47% |

These endpoint runtimes have different stopping trajectories and should not
replace the time-to-quality comparisons. Small cost differences are treated
as tradeoffs, not automatic failures. Ladybug-598 illustrates why the chosen
quality band matters: its adaptive run takes longer to finish, but reaches
the 3% band sooner than five-shift. Single-shift remains faster there.

Venice's median reprojection error also improves from 0.361256 px for five
shifts to 0.355995 px for adaptive, with median observation cheirality
violations decreasing from 10 to 2. These diagnostics do not establish
accuracy against a ground-truth reconstruction.

## What was implemented and checked

The controller scores the central shift first, expands in the same sweep
if no improving candidate exists, and periodically checks the full menu.
It remembers extra progress per scoring second with a fixed EWMA and requests
full exploration after failure/rescue or a useful boundary winner. It keeps
the best scored step, without the previous hysteresis discount. A confidence
rule preserves the next center after point-only/uninformative/rescued steps.

Build and host controller tests passed. CUDA memcheck reported zero errors.
The benchmark audit validated candidate counts, marginal-gain accounting and
bounded controller values across 2,342 adaptive attempts; it exercised 14
expansions from a narrow attempt within the same sweep.

Full menus were used at about 18.5% of checkpoints on Venice, 22.0% on
Ladybug-598, 20.2% on Trafalgar, but 90.2% on Ladybug-1197. Consequently,
this policy still often pays the full menu cost in the retry-heavy regime.

## Limits and next experiment

This implementation retains five Krylov shifts even in center-only scoring
mode. It reduces scoring work but does not get the shorter seed solve of a
true one-shift configuration. It also combines candidate-order/exploration
changes with a confidence rule for the next lambda. A component ablation is
needed before attributing gains solely to learned menu value.

The next focused experiment should separate those components and investigate
center-system convergence or a true one-shift solve in narrow mode, with
verified linear accuracy. Expansion should distinguish a camera-menu failure
from a common point-step failure; blindly expanding after every rejection
can keep the menu unnecessarily wide. None of these follow-ups is claimed
implemented or validated by this pilot.

The feature remains opt-in (`OCA_ADAPTIVE_MENU=1`). No production default was
changed. The original benchmark queue resumes after this pilot; its frozen
binaries are unchanged. Full raw records, source hashes and SVGs are under
`/workspace/prism-adaptive`. See [the detailed results](adaptive_menu_results.md),
[protocol](adaptive_menu_protocol.md) and [usage](../bench/ADAPTIVE_MENU.md).
