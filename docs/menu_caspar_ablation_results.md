# Menu ablation against Caspar FP64

Three original scenes, three unprofiled repeats per arm; six separate diagnostic profiles. Both PRISM arms hit **9/9** targets, Caspar **6/9**. Single shift wins two sampled scenes, fixed five one. All comparisons use the same effective quality threshold. See [protocol](menu_caspar_ablation_protocol.md).

| Scene | Single shift | Fixed five | Caspar FP64 | Native-time winner |
|---|---:|---:|---:|---|
| trafalgar-126 | 2.249 s (3/3) | 1.170 s (3/3) | Miss (0/3) | five |
| dubrovnik-88 | 1.245 s (3/3) | 2.321 s (3/3) | 1.334 s (3/3) | single |
| final-1936 | 3.327 s (3/3) | 3.568 s (3/3) | 4.985 s (3/3) | single |

Five is **1.92× faster than single** on Trafalgar; Caspar misses the four-second target. Single is **1.86× faster than five** on Dubrovnik and **1.07× faster than Caspar**. Single is **1.07× faster than five** on Final1936 and **1.50× faster than Caspar**; five remains **1.40× faster than Caspar**. The two single-digit differences are modest, descriptive wins, not broad superiority claims.

Trafalgar is variable: five spans **0.820–1.608 s**, single **2.241–2.478 s**. This variability includes different nonlinear trajectories, not just timer jitter. The profiled Trafalgar run even reverses the single/five ordering; it must not replace the three unprofiled repeats.

## Work to reach the target

Unprofiled medians; total scored counts menu + alpha + backtrack evaluations. Point evaluations are a separately displayed subset already included in total scored.

| Scene | Arm | Accepted steps | Matvecs | Menu evaluations | Total scored | Point evaluations |
|---|---|---:|---:|---:|---:|---:|
| trafalgar-126 | single | 67 | 4860 | 213 | 749 | 0 |
| trafalgar-126 | five | 33 | 2276 | 304 | 568 | 0 |
| dubrovnik-88 | single | 21 | 859 | 50 | 188 | 5 |
| dubrovnik-88 | five | 40 | 1543 | 307 | 627 | 0 |
| final-1936 | single | 11 | 106 | 15 | 103 | 0 |
| final-1936 | five | 5 | 183 | 55 | 95 | 0 |

PRISM has **zero rejected outer attempts in all 18 timing runs**. Caspar has 25 logged rejected decisions (22 Dubrovnik, three Final1936); these are different units of work and omit unlogged terminal/discarded attempts. Zero PRISM rejections does not mean safeguards were unused: single shift invokes point repair five times on Dubrovnik and it wins four times in **each** repeat. Fixed five never invokes it there. The safeguards are identically configured, but the menu changes which states and fallback branches they encounter.

On Dubrovnik, five needs almost twice as many accepted steps and about 1.8× as many matvecs. The slowdown is a trajectory problem as well as extra scoring. On Final1936, five reduces accepted steps from 11 to five, but increases matvecs from 106 to 183: its deeper sweeps outweigh much of the saved linearization work. Trafalgar benefits from both fewer accepted steps and fewer total matvecs.

## Separate phase diagnostics

One instrumented run per PRISM arm/scene, seconds. Candidate scoring includes back-substitution/retraction/cost work. Point repair is nested in backtrack. Profiling and candidate logging are enabled only here; these are not the speed-table runs.

| Scene | Arm | Assembly | Point factor/RHS | Krylov | Candidates | Alpha | Backtrack |
|---|---|---:|---:|---:|---:|---:|---:|
| trafalgar-126 | single | 0.125 | 0.125 | 1.606 | 0.054 | 0.052 | 0.000 |
| trafalgar-126 | five | 0.098 | 0.099 | 1.772 | 0.123 | 0.044 | 0.000 |
| dubrovnik-88 | single | 0.097 | 0.125 | 0.921 | 0.036 | 0.030 | 0.014 |
| dubrovnik-88 | five | 0.184 | 0.238 | 1.637 | 0.149 | 0.075 | 0.000 |
| final-1936 | single | 0.637 | 0.841 | 1.381 | 0.151 | 0.268 | 0.000 |
| final-1936 | five | 0.298 | 0.391 | 2.397 | 0.357 | 0.121 | 0.000 |

On Final1936, five saves **0.789 s** in assembly plus point factor/RHS, but spends **1.016 s more in Krylov** and **0.206 s more in candidate scoring**; alpha saves 0.147 s. Krylov occupies about **66%** of the five-shift diagnostic return time. Optimizing only candidate scoring misses the largest component. Caspar has no matched phase instrumentation in this frozen driver.

## Mathematical interpretation and next experiment

For a fixed positive-definite equilibrated Schur operator S, a shifted solve has condition number κ(S + σI) = (λmax(S) + σ)/(λmin(S) + σ). Lower σ generally worsens conditioning. The five-shift recurrence is seeded at the lowest damping, λ/100, while the single arm solves at λ. Sharing matrix-vector products across shifts does not make the longer least-damped solve free. This is a mechanism consistent with the Final1936 counts, not a measured eigenvalue diagnosis.

A larger menu guarantees a no-worse immediate objective only if it actually contains the same candidate at the same state. Here stopping depth, menu gates, damping feedback, point damping and safeguard activation affect that premise. Even exact one-step dominance would not imply faster progress several nonlinear iterations later. The Dubrovnik fallback difference is a concrete reason to avoid attributing the outcome solely to the number of candidate evaluations.

The next useful short experiment is a matched-state, two- or three-step rollout on Dubrovnik88 around the four single-shift repair wins: compare the ordinary accepted menu step with the safeguarded alternative, charging all probing and rollout work. That tests whether accepting an available menu step suppresses a better fallback trajectory. For Final1936, use a fixed Krylov-work budget and measure the quality lost by stopping earlier; preserve a fully scored central candidate as a control. Prior coverage-only experiments were not a general fix, so merely adding the central candidate again is not a new solution. Keep the current algorithms unchanged until either test produces a repeatable improvement.

## Audits, timing scopes and complete statistics

All 33 replacement runs pass independent endpoint audits; maximum relative discrepancy is 1.1e-14. Timing runs consume 73.081 native seconds; separate profiles 15.127 seconds. Seven preliminary logged pipelines are retained separately and excluded. Binary hashes, original input hashes, target flags, menu widths and identical remaining PRISM settings are verified against the frozen protocol.

Native crossing time includes PRISM solver-local setup but excludes its CLI upload; Caspar excludes graph setup. Process wall includes differing CPU-check scopes. The following wall columns are diagnostics, not normalized end-to-end speed comparisons. Objective reduction per second uses native return time and is meaningful only within a scene.

| Scene | Arm | Crossing range (s) | Median CPU endpoint | Median process wall (s) | Median objective reduction/s |
|---|---|---:|---:|---:|---:|
| trafalgar-126 | single | 2.241–2.478 | 104508.102321 | 2.850 | 6.65e+06 |
| trafalgar-126 | five | 0.820–1.608 | 104478.086796 | 1.749 | 1.27665e+07 |
| trafalgar-126 | caspar64 | Miss | 104790.046458 | 4.422 | 3.74119e+06 |
| dubrovnik-88 | single | 1.200–1.257 | 358716.225796 | 1.937 | 2.39264e+07 |
| dubrovnik-88 | five | 2.308–2.329 | 359000.935271 | 3.002 | 1.29227e+07 |
| dubrovnik-88 | caspar64 | 1.274–1.341 | 358892.705043 | 1.895 | 2.26393e+07 |
| final-1936 | single | 3.317–3.329 | 5074764.653080 | 7.116 | 5.3351e+07 |
| final-1936 | five | 3.564–3.580 | 5064073.119045 | 7.348 | 4.97506e+07 |
| final-1936 | caspar64 | 4.984–4.998 | 5072458.171542 | 8.884 | 3.57745e+07 |

The scene set is selected, N=3, and within-scene arm order is fixed. There is no learned selector and no legitimate universal algorithm obtained by choosing the best arm after seeing these results. This screen supports keeping single shift as a serious baseline and testing the menu’s benefit separately from the safeguards.

Code: [runner](../bench/menu_caspar_ablation.py), [auditor/summarizer](../bench/summarize_menu_caspar_ablation.py). Full raw artifacts: `/workspace/prism-menu-ablation`; preliminary excluded artifacts: `/workspace/prism-menu-ablation-logged-pilot`. No solver binary/default changes; previous jobs remain paused.
