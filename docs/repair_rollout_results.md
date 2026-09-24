# Matched-state point-repair rollouts on Dubrovnik88

The simple missing-fallback explanation is incomplete. From the first two captured single-shift states, ordinary five-shift PRISM already invokes and wins with point repair. At the later two states, explicitly repairing an accepted menu step improves its immediate objective, but the ordinary menu has the lower objective after three steps in both repeats. **Do not enable the accepted-step repair probe by default.**

The end-to-end incumbent remains **single guarded: 1.245 s**, versus fixed five **2.321 s** and Caspar FP64 **1.334 s** at the existing medium target in the [previous unprofiled screen](menu_caspar_ablation_results.md). This study does not rerun or replace those timings.

## Frozen experiment

Four checkpoints precede the previously observed single-shift repair wins at zero-based outers 15, 16, 17 and 18. Each is captured from the original Dubrovnik88 input using the same single-guarded flags. Every capture reproduces a repair win at its selected outer. Captures are separate runs, so adjacent checkpoints are not asserted to be successive states of one identical trajectory.

Each checkpoint branches into single guarded, fixed five guarded, and fixed five with an additional accepted-step repair probe. There are two repeats per branch, three outer iterations per continuation: **24 branch runs plus four captures**, all successful. No rejection occurs in any continuation. The probe runs only on the first replayed outer, and only when the ordinary accepted step has not already used fallback. Subsequent outers use the existing five-shift policy. No result-dependent state substitutions or timing reruns are used.

Replay preserves exact camera rotations, translations, intrinsics and points, plus lambda, point-damping floor/ratchet, previous gradient norm, acceptance/rejection history and convergence/backtracking controller state. Derived factors are rebuilt. One-to-five replay is an explicit menu intervention: the previous single central-shift index maps to the five-menu center; all other numerical policy settings must match. Point-safeguard workspace has no persistent algorithmic history. Diagnostic counters may restart; continuation work is obtained by subtracting the saved totals.

The isolated diagnostic source and binary live under `/workspace/prism-repair-rollout`; the production source and frozen v7 binary are unchanged. [Build script](../bench/build_repair_rollout.py), [study runner](../bench/repair_rollout_study.py), [audit/summarizer](../bench/summarize_repair_rollout.py). The diagnostic source patch, full inputs/binary/tooling/header hashes, policy manifests and raw states are retained there.

No phase profiler or candidate-norm logging is enabled. Native branch time includes solver setup, checkpoint restore, factor rebuilding, the probe and all three steps; capture time is reported separately. These diagnostic continuation times are not end-to-end time-to-target measurements.

## Immediate and three-step outcomes

Costs are medians of two repeats; lower is better. State numbers identify the saved pre-step outer.

| State | Arm | After one step | After three steps | Native seconds | Objective reduction / native second |
|---|---|---:|---:|---:|---:|
| 15 | single | 360770.867 | 359742.220 | 0.325 | 6279.5 |
| 15 | five | 360770.890 | 359830.267 | 0.311 | 6257.9 |
| 15 | five-probe | 360770.890 | 359731.851 | 0.333 | 6133.3 |
| 16 | single | 360187.873 | 359430.119 | 0.425 | 3154.3 |
| 16 | five | 360187.884 | 358946.128 | 0.472 | 3881.6 |
| 16 | five-probe | 360188.035 | 358756.700 | 0.306 | 6581.1 |
| 17 | single | 359742.427 | 359224.718 | 0.316 | 3053.4 |
| 17 | five | 359732.000 | 358344.209 | 0.291 | 6332.7 |
| 17 | five-probe | 359206.793 | 358410.003 | 0.307 | 5799.6 |
| 18 | single | 359426.967 | 358856.361 | 0.361 | 2437.7 |
| 18 | five | 359548.547 | 358407.258 | 0.354 | 3767.8 |
| 18 | five-probe | 359004.312 | 358480.080 | 0.413 | 3134.7 |

The extra probe is **inactive at states 15 and 16** in both repeats because normal fallback already repairs the first step. Its apparent differences from the ordinary-five rows are execution/trajectory variability, not a benefit from the intervention. In particular, ordinary five ranges 359731.445–359929.089 at state 15 and 358756.701–359135.555 at state 16. Do not rank an inactive probe as a distinct improved algorithm.

At state 17, the extra repair reduces the first-step objective by about **525.2** beyond the ordinary menu, but ends **65.8 higher** after three steps. At state 18, it reduces the first-step objective by about **544.2**, but ends **72.8 higher** after three steps. Those three-step penalties are about **3.6% and 5.5% of the ordinary branch’s total objective reduction**, respectively; they are only about 0.02% of the absolute endpoint objective. The ordering repeats in both executions.

Ordinary five and the probe use the same matvec counts in these active comparisons: **194 at state 17**, **257 at state 18**. The additional probe costs **2.459–2.475 ms** and one extra full objective evaluation. The observed regression in objective after three steps therefore cannot be explained by a shorter solve caused by probe overhead: the horizon is fixed and every branch completes three accepted steps. It can arise from the changed step and subsequent controller behavior.

## Why this does not yet isolate the damping cause

At fixed trial cameras, the objective separates over point tracks. Choosing, for every point, the lower-cost option between its old position and its proposed position cannot increase the full objective in exact arithmetic. The probe applies that existing pointwise choice to the accepted menu direction, then recomputes the full objective and checks a descent slope and Armijo bound before replacing the ordinary step. It preserves the original direction if any acceptance test fails. Both active states freeze one point; all four active probes improve the immediate objective and pass the tests.

That is a one-step guarantee. It provides no ordering for the objectives of subsequent nonlinear iterations. The probe also deliberately follows the existing safe feedback for a nonuniform repaired step: it retains the prior lambda instead of applying the menu’s Schur-model rho update to a direction that no longer matches that prediction. At both active states, the next lambda is approximately **6.969e-7 after repair**, versus **3.485e-6 after the ordinary menu**—a factor of five. Consequently this experiment measures a repaired step **with its existing repair feedback**, not a pure point-position intervention with identical future damping.

The next discriminating test is a small factorial continuation at states 17 and 18: ordinary/repaired step crossed with ordinary/repair next-lambda choices, using frozen values from this study. This separates the step geometry from the damping update without reusing an invalid Schur prediction for the repaired direction. It remains an experiment, not a proposed default. The current result already rules out promoting “repair every accepted menu winner” on immediate objective improvement alone.

## Verification and limitations

All **28 endpoints** pass independent CPU FP64 objective audits against the original observations; maximum relative discrepancy is 2.75e-15. The exact matrix-state tail of each checkpoint is independently scored on the CPU and matched to its saved objective. Every branch loads the identical checkpoint hash and initial matrix-state hash for its state. All manifests are checked for the expected menu/probe flags and unchanged remaining settings. A separate negative check deliberately changes the menu-gate policy and confirms that replay rejects the incompatible checkpoint.

Captured uninterrupted single continuations and replayed single continuations can diverge under CUDA reductions and factor rebuilding. Maximum endpoint relative differences are 4.60e-7, 6.39e-7, 1.64e-8 and **6.04e-4** for states 15–18. Exact checkpoint identity is verified; bitwise trajectory reproducibility is not claimed. Two repeats and four selected states cannot establish a general speedup or a tail guarantee.

Native work totals **4.219 s for captures** and **8.430 s for branches** (12.650 s total), plus the separately recorded rejected-policy guard check. Existing paused jobs remain paused.

The first ineligible probe completed normally, but the original parser incorrectly required probe activation. The parser was corrected to retain ineligible cases, and that completed output was recovered without rerunning. Its process-wall value was not persisted and is explicitly null; its native runtime, trace and independently audited endpoint are intact. The original protocol and tooling are archived. Verification confirms that the parser change did not alter the binary, arms, checkpoints, order or horizon.

A counting clarification was also applied to the previous ablation documentation: point-safeguard evaluations are already included in backtrack/total-scored counts; the point-evaluation column is a subset, not additional work. No previous numerical results changed.
