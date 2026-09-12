# O2: signed-depth projection homotopy

Registered before native candidate scores, 2026-09-12. Parent campaign:
`research/eta2_wave4/PROTOCOL.md`; source baseline is frozen Eta2, source SHA256
`22c18359a526526ae0a5b5109187878ab1cef33b453f6bbddc2aa92597a607d8`.
The original champion and all its saved evidence remain unchanged.

## One fixed intervention

For each original observation `o`, save its signed camera depth `d0[o]` at the
input state. It remains fixed throughout the run. At stage `s`, use

```
D[o] = s * Yz[o] + (1-s) * d0[o]
q[o] = -Yxy[o] / D[o]
pixel[o] = f * (1 + k1 * dot(q[o], q[o])) * q[o]
```

Retain all observations, SIMPLE_RADIAL distortion, independent camera
intrinsics, and `k2=0`. Do not take the absolute value of signed BAL depths,
clamp denominators, drop observations, or use a robust loss. The surrogate can
have poles; a nonfinite trial is ineligible for acceptance. At `s=1`, explicitly
use the original projection operation, avoiding an unnecessary arithmetic
change in the baseline path.

The schedule is exactly `s = 0, 0.25, 0.5, 0.75, 0.9, 1`. Two accepted outers
advance each surrogate stage. At the final `s=1` stage, two accepted outers merely
complete the schedule: the objective and histories do not change, and ordinary
Eta2 continues. Each stage with `s<1` has a cap of **18 attempts**, counting inner
retries and numerical-recovery attempts. Hitting that cap, or an ordinary
stage-stopping condition, skips all remaining surrogate stages directly to
`s=1` from the current state and records an incomplete stage. There is no state
restoration and no per-scene rule.

The full stage objective, residuals, Jacobians, Schur/RHS assembly, regularizer
statistics, model prediction, point safeguards, and trial/backtracking cost
must all use the same stage and the same original-observation depth array.
Changing assembly alone is not a valid implementation.

## Transitions and accounting

At a change in `s`, preserve the current geometry, intrinsics, damping center,
radius, numerical damping floor, cumulative work counters, accepted-step warmup
count, and overall wall/outer budgets. Refresh every numeric factor/RHS cache;
reset objective-dependent previous RHS norm, FTOL streak, previous-cost history,
convergence/confirmation state and comparable controller observation history.
Recompute the current stage cost. Retain cumulative intervention counters for
accounting while resetting their stage-local stopping-history roles explicitly.
Log every changed history and every incomplete stage. Such resets are an
explicit part of O2, not a claim that the controller history is unchanged.

If a newly entered surrogate has nonfinite cost at the current state, record a
stage-domain failure and skip directly to `s=1` from that state. If the original
objective itself is nonfinite, terminate as failure. This handles the surrogate
domain without inventing a denominator floor or silently discarding data.

Evaluate and log the original full L2 objective throughout staging, including
registered-target crossings in both directions. **Only the `s=1` original-L2
stage can stop successfully on a registered target.** A staging diagnostic
crossing is not a scored hit. Final exported state and endpoint cost always use
the original objective. If the global budget expires before `s=1`, report the
incomplete schedule and no scored target hit, even if a staging diagnostic was
below target.

Charge initial-depth storage, all allocation/factor refresh/history-transition
work, extra original-objective evaluations, and every attempt to native time.
Never compare surrogate costs directly with the registered original-L2 target.

## Correctness gates before a native grid

1. Audit the two requested primary sources and distinguish their methods from
   this fixed-denominator interpolation. No novelty priority assertion.
2. Analytic projection Jacobians and joint camera/point directional derivatives
   pass finite differences at all stages with signed depths, nonzero radial
   distortion, and nonzero camera/point directions. Include pole/nonconvex
   counterexamples and exact `s=1` baseline identity.
3. A source coverage ledger covers assembly, all executed cost paths, full-step
   prediction, per-point safeguard, backtracking, exports and stopping.
4. Default-off source identity and N>=3 compatibility against frozen Eta2;
   tiny native stage objective/model/RHS/point-equation checks and memory check.
5. Parent registers the native cell/rep schedule and owns isolated timing.

No CPU test, compile, GPU check, or grid is launched during a parent's isolated
timing window. This document authorizes prototype preparation; it does not
claim an implemented or validated native solver. Any additional native guard
or history semantics must be documented before scored runs.
