# One versus five shifts under the same trust-region controller

**The corrected single-shift trust-region prototype is the provisional winner on both sampled scenes.** Both widths reach 6/6 targets. The initial width-only comparison exposed a damping-placement weakness; it is retained below, not used as evidence that multishift is inherently superior.

## Corrected, matched-controller comparison

Medians of three independent executions per arm. Both arms use the same revised binary, controller, point safeguards, Cauchy candidate and native target test. The only differing solver flag is `OCA_NSHIFTS=1` versus `5`.

| Scene | TR one shift | TR five shifts | One-shift speedup |
|---|---:|---:|---:|
| trafalgar-126 | **0.474 s** | 0.683 s | **1.44×** |
| dubrovnik-88 | **0.753 s** | 0.828 s | **1.10×** |

Trafalgar one-shift times span **0.461–0.614 s**, five-shift **0.515–0.691 s**; one shift wins each paired repeat. Dubrovnik spans **0.753–0.902 s** versus **0.646–0.990 s**; one shift wins two of three paired repeats. The roughly 10% Dubrovnik median advantage is modest and variable. Three repeats on two development scenes do not establish a universal winner. Caspar and the older guarded LM configurations were not rerun in this ablation.

## What the first comparison revealed

The original TR prototype was recompiled with only its width guard relaxed from five to one-or-five; the source patch is retained. Four six-iteration sanity checks were followed by 12 target runs. Initial radii match between arms to floating-point precision. Five shifts hit 6/6; one shift hit 0/6 within the four-second caps.

| Scene | Original TR one: median endpoint | Original TR five: median target time |
|---|---:|---:|
| trafalgar-126 | 113733.104 (miss) | 0.682 s (3/3 hits) |
| dubrovnik-88 | 582444.995 (miss) | 0.786 s (3/3 hits) |

This was not a convincing demonstration of a multishift speed advantage. In both single-shift cases, lambda reached **0.625 after the second accepted step and remained there**. Steps became much smaller than the radius, so the radius stopped expanding. The old menu-center update then retained the same lambda. The point-damping floor also remained high. Objective costs continued to decrease, but slowly; these are budget misses, not solver crashes or rejected steps.

For an exact reduced trust-region solution, a positive multiplier must accompany a boundary step: λ(||z|| − Δ) = 0. Radius feasibility alone does not ensure that condition. Our finite candidate approximation was allowing a strongly interior step while keeping positive damping indefinitely. Five shifts could escape by choosing a lower multiplier from its menu; that capability was masking the placement weakness in the one-shift control.

## Shared correction and protocol amendment

One correction was chosen after inspecting that failure and frozen before the second batch. If an accepted camera step has norm below 0.8 times the old radius and rho ≥ 0.25, the next damping center is at most **one tenth of the current center**, subject to the original damping floor. A menu-selected center that is already lower is retained. All other radius, scoring, acceptance, backtracking and point-safeguard rules stay identical.

The decade matches the existing menu spacing; no values were swept and no scene-specific tuning was performed. This prevents the observed damping stall, but is still a placement heuristic, not an exact trust-region multiplier root or a convergence proof. The prototype remains a camera-space trust-region approximation with separate point damping.

The second batch repeats the same four sanity checks and 12 target runs, under the same targets and four-second caps. Both arms use the corrected binary. The initial batch and its frozen protocol remain intact. This is a documented development revision on observed scenes, so subsequent validation must use a scene not used to develop the controller.

Existing medium targets are 104534.24152926281 for Trafalgar126 and 359003.9111293723 for Dubrovnik88; the effective threshold is each times (1−1e-8). A hit requires a native crossing within cap and an independently audited endpoint below that effective threshold. Radius initialization uses the central candidate; measured initial values agree across widths (approximately 660.163626638326 and 893.428266661775). Arm order reverses in the second repeat, scene order alternates, and every completed result is retained. Profiling and candidate-norm logging are disabled.

## Work in the corrected comparison

Unprofiled medians; all model-evaluation matvecs are already included in total matvecs. Full-objective scores include menu/backtracking/point full-cost checks; trackwise safeguard comparisons and full-GN prediction passes are separate work.

| Scene | Width | Accepted steps | Total matvecs | Model matvecs (subset) | Full objective scores | Full-GN predictions |
|---|---|---:|---:|---:|---:|---:|
| trafalgar-126 | tr1 | 15 | 933 | 73 | 21 | 15 |
| trafalgar-126 | tr5 | 15 | 1383 | 280 | 31 | 15 |
| dubrovnik-88 | tr1 | 14 | 516 | 57 | 25 | 14 |
| dubrovnik-88 | tr5 | 10 | 630 | 145 | 19 | 10 |

On Trafalgar both widths need a median 15 accepted steps, while five uses **1383 versus 933 matvecs**. On Dubrovnik five reduces accepted steps from 14 to 10, but still uses **630 versus 516 matvecs**. Model evaluation contributes materially: five spends 280/145 model matvecs on the two scenes versus 73/57 for one shift. The extra shifted candidates do not repay their total cost at these two quality targets under the corrected controller.

This is evidence about the current menu implementation, including its depth choices and damping feedback. It does not prove that every multishift trust-region method is slower, or that a continuous small-subspace radius solve would behave the same way.

## An actual rejection-reuse case

Dubrovnik five-shift repeat three rejects one step with rho **0.02185**. The radius contracts **7147.426 → 1786.857**. It retains the same 26-entry candidate bank and point damping **1e-7**, reuses the point factor and assembly, and accepts the smaller-radius candidate with rho **0.62299**. The candidate-bank path skips a new CG sweep and new candidate-model matvecs; back-substitution, nonlinear scoring and the full GN prediction still cost work.

This provides one integrated BA activation of the rejection-reuse path, beyond the earlier GPU component test. It is not a statistical speedup estimate for rejection-heavy scenes. All other timed runs have zero rejected outer attempts.

## Complete corrected endpoints and audits

| Scene | Width | Median endpoint | Median native return (s) | Median process wall (s) |
|---|---|---:|---:|---:|
| trafalgar-126 | tr1 | 104487.443996 | 0.477 | 0.999 |
| trafalgar-126 | tr5 | 104494.004637 | 0.691 | 1.168 |
| dubrovnik-88 | tr1 | 358846.140766 | 0.766 | 1.423 |
| dubrovnik-88 | tr5 | 358634.054973 | 0.833 | 1.462 |

All **32 exported endpoints across both batches** pass independent CPU FP64 objective audits; the maximum relative discrepancy is 1.56e-14. Every accepted TR step passes the logged radius, positive prediction and rho checks. The largest norm/radius ratio is 1.0000000000000002. Initial state and radius, input/binary/header hashes, source patches, manifests and expected arm flags are checked. Logged interior damping reductions are verified against the shared correction; the final target-reaching iteration does not print its post-step lambda and is excluded from that particular log check.

First batch native time: 29.440 s. Corrected batch: 9.336 s. Combined **38.776 native seconds**, excluding compilation and CPU audits. Native timing includes solver-local setup and all trial work; process walls are retained separately. No failed target was silently retried or omitted. Existing paused jobs remain paused; no production defaults or frozen binaries changed.

## Current decision and next test

Keep **corrected one-shift TR as the provisional incumbent**, with corrected five-shift TR retained as the comparison arm. This ablation does not justify the extra menu width on either sampled target after the damping-placement weakness is corrected. The next useful test is both frozen variants against Caspar FP64 on a medium scene not used to develop this controller. That is more informative than further tuning on these two scenes.

The ordinary guarded single-shift solver is not the same algorithm as this one-shift TR prototype: the latter uses model selection, a radius, a Cauchy candidate, full-step model acceptance and the revised damping placement.

Code: [original width-only builder](../bench/build_camera_tr_ablation.py), [first runner](../bench/camera_tr_width_study.py), [first auditor](../bench/summarize_camera_tr_width.py), [shared correction builder](../bench/build_camera_tr_interior.py), [corrected runner](../bench/camera_tr_interior_study.py), [corrected auditor](../bench/summarize_camera_tr_interior.py). The common implementation is described in [the camera-TR prototype report](camera_tr_results.md).

Artifacts: `/workspace/prism-camera-tr-ablation` retains the original comparison; `/workspace/prism-camera-tr-interior` contains the corrected comparison, all raw logs/CSV/states, source patch, frozen protocol and summaries. Reproduce using the respective `build_*`, study and summarize scripts with the retained source snapshots.
