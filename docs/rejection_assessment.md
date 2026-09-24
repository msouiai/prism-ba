# Assessment of the bounded rejection investigation

Completed 2026-09-07: 40 timed runs, zero execution failures, **13.79 minutes of
summed solver time**. Diagnostic logging, saved-state forks, build time, input
loading and memory checks are additional. The broad 384-run queue remains
paused; its completed results and frozen executables were preserved.

## Main finding

The user's same-state intuition is correct: a candidate set containing the
standalone candidate cannot have a worse minimum nonlinear cost. Our full runs
change trajectories, stopping depths and the coupled point/camera damping state.
They are not a controlled test of that dominance property.

The strongest local evidence is the saved Ladybug-1197 state. Both the low-lambda
single solve and the completed five-shift menu reject. With point damping held
fixed, lambda=10 succeeds, whereas the original five-shift menu ends at 1e-5.
The useful lambda lies six decades above that menu's upper end. Changing point
tau from 1e-7 to 1e-4 also succeeds without that large camera shift. This isolates
a **damping-range/joint-state problem** at that state. It does not prove that
all retries have the same cause, or that arbitrarily large camera lambda is safe.

In a full diagnostic trace, Ladybug repeatedly returned to camera center 1e-7
after an accept at point tau=1e-4, then repeated a three-rejection ladder. Of
294 rejections, 286 occurred after backtracking was permanently disabled for
convergence confirmation. Dubrovnik-173 had 51 rejections, all after that switch.
The tested traces had no nonfinite candidate costs or curvature-truncated
rejected attempts; the older long-depth CG recurrence audit cannot explain
these specific traces.

## Most consistent experimental change: rearm the safeguard

If original-policy convergence confirmation finds substantial further progress,
re-enable backtracking. Later proposed stops still require confirmation. Two
repeats per arm, same frozen executable within the comparison:

| Scene | Median rejected attempts | Median solver seconds | Endpoint cost change |
|---|---:|---:|---:|
| Ladybug-1197 | 402.5 → 224 (−44.3%) | 36.60 → 27.60 (−24.6%) | −0.0225% |
| Dubrovnik-173 | 35 → 22.5 (−35.7%) | 10.73 → 7.84 (−26.9%) | +0.0067% |

Both also reduce total matvecs and total cost evaluations. These tiny endpoint
changes are sensible tradeoffs under the user's quality-band preference. This
is promising exploratory agreement on two retry-heavy cases, **not a formal
verdict**: the reproduction protocol requires at least three repeats per verdict
cell, and no universal or tail claim follows from two.

Most of the targeted retries occur late, after the 3% quality target has already
been reached. The runtime saving therefore primarily concerns continued
optimization. This is not evidence of a universal improvement in time to every
acceptable-quality threshold. Repeated control trajectories also vary.

## Candidate coverage: useful, but no consensus

`OCA_MENU_COVERAGE` adds the central stopping candidate, scores computed terminal
iterates and expands failed model-flat shortcuts. The first two-repeat pilot
helped Ladybug, Venice and Trafalgar in median full-run runtime, but hurt
Dubrovnik. It also contained avoidable duplicate scoring; those measurements
are retained separately.

After correcting the duplicates, a **one-repeat paired recheck** retained the
same qualitative pattern:

| Scene | Rejected attempts, multi → coverage | Runtime change | Cost change |
|---|---:|---:|---:|
| Ladybug-1197 | 284 → 104 | −40.2% | −0.0725% |
| Dubrovnik-173 | 52 → 72 | +50.6% | +0.00013% |
| Venice-52 | 0 → 0 | −35.0% | −2.451% |
| Trafalgar-126 | 0 → 0 | −34.1% | +0.0621% |

One repeat does not resolve timing variability. Candidate coverage also worsens
Ladybug's time to the 1% target despite lowering its eventual runtime and cost.
Thus fewer retries or better endpoints alone cannot justify enabling it globally.
The saved low-lambda failing state still rejects with coverage enabled: candidate
omission is not the sole explanation. Guarded single shift remains a strong
baseline and has not been displaced uniformly.

## Next focused design

Keep the successful **camera lambda / point tau pair**, with evidence about which
parameter changed during the last rescue. On failure, expand the camera damping
range at fixed tau using the existing factorization, with a small evaluation
budget, before restarting a point-damping ladder. Recycled Krylov bases can
support additional shifts; this is known prior art, not a novelty claim.

Use the same saved states to test this first: require that a known improving
high-lambda candidate is recovered without repeated factorization. Then test
Ladybug-1197 against Dubrovnik-173 and one healthy scene. Do not add another
large-scene sweep until those small contradictory cases support the mechanism.
No dynamic range-expansion implementation or performance claim is made here.

## Validation and files

* CUDA release builds passed. New flags were verified in each frozen binary.
* Both the initial and corrected prototypes passed Compute Sanitizer memcheck
  on Ladybug-49 with zero errors.
* The rearm trace checker validated 12 rearm events, 13 confirmation switches
  and 117 Armijo rescues in its diagnostic run. Rescued steps cannot rearm the
  safeguard; only sufficiently improving original-policy accepts do so.
* All 40 timed traces are monotone and independently match initial fp64 costs
  within relative 1e-6. This is not an independent audit of every final state.
* A small mathematical check matches shared/independent CG iterates to about
  3.2e-17 on a fixed SPD example and verifies the point-damping counterexample.
  It is not a production GPU accuracy proof.
* The working CUDA source matches the corrected frozen source; the broad-study
  executable hash is unchanged. Python syntax and `git diff --check` pass.

Code: `gpu/oca_cuda.cu`, `bench/rejection_experiment.py`,
`bench/summarize_rejection_study.py`, `bench/check_rejection_trace.py`,
`bench/check_rejection_math.py`. Flags remain opt-in. Raw artifacts and diagnostic
scripts: `/workspace/prism-rejection`. No new GitHub push was performed.

See [research and derivations](rejection_research.md) and
[all measured costs, work counts and 1%/3%/5% crossings](rejection_results.md).
