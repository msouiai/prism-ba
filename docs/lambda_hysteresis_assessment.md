# Lambda hysteresis: completed priority pilot

**Verdict: keep this 95% selection rule opt-in. It reduces damping chattering,
but is not a general improvement and did not reduce retries in this pilot.**
All 18 paired runs completed successfully, plus three logging-off controls.
The original benchmark queue was paused for this experiment and is resumed
after report generation. Its frozen executable files were not replaced.

## Results

Three fresh repeats per arm, same new executable and matching instrumentation.

| Scene / budget | Median cost change, hysteresis/control | Median solve-time change | Median retries control → hysteresis | Interpretation |
|---|---:|---:|---:|---|
| Venice-52 / 600 | +2.111% | -50.79% | 0 → 0 | Faster termination at worse quality; not an equal-quality speedup. |
| Ladybug-1197 / 600 | -0.0818% | +23.52% | 308 → 322 | Cost difference below the declared 0.15% gate; slower with more retries. |
| final-3068 / 100 | -0.9734% | -18.29% | 0 → 0 | Better early progress; no evidence about late retries or full convergence. |

Venice's median menu-center reversals fell from 255 to 34. Its hysteresis
endpoints all missed even the 1%-above-best quality target reached by all
three controls. The lower endpoint runtimes therefore do not constitute a
speedup to the same quality. Two controls reached the 600-outer cap; all
hysteresis runs terminated earlier. Stopping behavior is part of the result.

Final-3068's hysteresis costs ranged from 1,689,400.75 to 1,758,460.43, versus
1,761,923.45 to 1,770,365.86 for control. The ranges are disjoint, but the
spread within hysteresis is substantial. These are three-run observed
ranges, not confidence intervals or tail guarantees. The 100-outer window
contained no retries in either arm and cannot establish a retry reduction.

Full ranges, iteration counts, work, and common-quality crossings are in
[the results](lambda_hysteresis_results.md). Raw JSON/logs and illustrative
first-repeat SVGs are under `/workspace/prism-hysteresis`.

## What the diagnostics establish

Many competing choices have similar immediate reductions. In the first two
Venice controls, only 0–2 competing menus had a relative reduction gap at
most 1e-6, despite many being within 5%. Thus near-competitiveness is
established, but numerical roundoff is not established as its cause.

The policy picks the closest previous absolute lambda among candidates
retaining at least 95% of the best positive menu reduction. It works as
implemented: checks passed for the reduction and nearest-history guarantees
on every logged attempt across all 18 runs. Nevertheless, local reduction
retention does not preserve the nonlinear basin, later progress, or stopping.
The guarantee applies before the existing alpha search, not to the best
alpha-optimized alternative that could have followed a different candidate.

The labels also need care: a point-only/zero-CG-depth step has no informative
camera-damping preference, and an alpha-rescaled step does not correspond to
an exact solution at its recorded menu lambda. Existing gating can leave
some shifts unscored. Histories of menu indices alone would be misleading.

## Cost and validation scope

Per-shift full-step snapshots and logging add work. Both paired arms pay it.
The separate logging-off Venice control had median cost 248,738.45 and
runtime 30.78 seconds (range 28.71–60.22). Instrumented control's median was
69.27 seconds (42.95–71.48), but the iteration trajectories differ, so their
ratio is not an isolated measurement of instrumentation overhead. A direct
production speed claim from the instrumented comparison is unwarranted.

The new feature is disabled by default and supports unshared fp64 dof9 with
full observation scoring. The CUDA build and host selection tests passed.
CUDA memcheck reported zero errors while exercising 13 changed selections
in a 30-outer run. Frozen source/executable hashes and logs are retained.
Prism endpoint costs remain GPU-fp64 with independent initial-cost checks;
no new independent CPU endpoint audit is claimed.

## Consequence for the next controller

History can influence the trajectory strongly, but choosing a slightly worse
current step simply to keep lambda near its past value is too blunt here.
A separately preregistered follow-up should retain the best current step and
use confidence in the damping evidence to update only the next menu center.
Point-only, flat/gated, and backtracking-rescued steps should not automatically
be treated as evidence for a new camera damping scale. This is a proposed
next experiment, not an implemented or demonstrated improvement.
