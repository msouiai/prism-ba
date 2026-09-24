# CG-capture reuse: expansion cost and time to equal quality

Capturing the existing CG subspace removes the large quality regression of the earlier projected-first prototype in this small screen. Reusing a captured basis is 2.6–2.7× faster than rebuilding that projection at the first expansion snapshots. It does not yet beat the existing controller in total time to the selected quality targets: the final version is 15.2% slower on Ladybug and 1.1% slower on Dubrovnik. Keep it opt-in; these are exploratory N=2 results, not a universal verdict on recycling.

## What changed

`OCA_KRYLOV_REUSE=3` captures ordinary narrow CG search directions and their shifted operator products. `=4` captures the same data but rebuilds the projection on expansion, providing a control. Both require the existing demand menu and its FP64, unshared, diagonally equilibrated configuration. All tests here use paired demand mode 2. The older modes 1/2 remain available.

The narrow solve retains its CG recurrence, per-iteration forcing termination, checkpoint scoring, model predictions, alpha search and nonlinear guards. Capture only copies vectors; it adds no narrow-path operator applications. On the explicit same-state/same-point-damping menu expansion, the code removes the seed shift from saved products and orthogonalizes directions and products together. That constructs the camera-space projected operator without recomputing those products. The basis can then grow up to 64 vectors. Ordinary retries and accepted steps cannot use a stale capture.

Every terminal expanded shift must satisfy a true full-operator residual check at the existing forcing tolerance. Insufficient accuracy triggers the original wide CG sweep. On success, prefix projections reconstruct candidates at the original checkpoint depths plus the terminal depth. Expansion termination still checks the captured depth and then 8/16/32/64, rather than every iteration; the legacy center-anchor scoring schedule is not reproduced exactly. Therefore only the narrow path is preserved, not a bitwise-identical entire nonlinear trajectory.

The first frozen version also recomputed true residuals while reconstructing checkpoint candidates. The follow-up removes these duplicate applications: the terminal accuracy gate stays, while checkpoint model decreases come from the Galerkin solution. Intermediate checkpoint candidates remain inexact, as in legacy CG, and still undergo actual nonlinear objective evaluation. `OCA_CAPTURE_VERIFY_PREFIX=1` restores the duplicate checks for an ablation. This was an engineering follow-up, not parameter tuning; both stages are reported.

At the largest scene dimension previously used (13,682 cameras × 9 variables), the basis and two capture arrays require about 182 MiB of vectors, plus small host matrices. No largest-scene test was run in this study.

## Identical-operator expansion experiment

The first real expansion on each scene supplies one fixed operator, RHS, damping menu and capture. N=3 alternating-order import/rebuild comparisons. Every solve uses the same inherited relative-residual target of 0.5; this is the solver's deliberately loose inexact-LM forcing target, not a claim of 1e-6 linear accuracy. All 12 linear solves pass. Timings exclude allocation/copy setup and already-paid narrow work, but include import/build, extension, reconstruction and terminal verification.

| Scene | Saved depth | Rebuild ms | Reuse ms | Rebuild/reuse | Operator calls, rebuild/reuse |
|---|---:|---:|---:|---:|---|
| ladybug-1197 | 12 | 26.379 | 9.805 | 2.69× | 17 / 5 |
| dubrovnik-356 | 9 | 44.417 | 17.332 | 2.56× | 14 / 5 |

The five remaining reuse calls certify the five shifts. Maximum relative residuals were 0.49910 on Ladybug and 0.48117 on Dubrovnik, agreeing closely between methods. The first rebuild timings were colder (54.8 and 77.0 ms); all samples are retained and the table uses medians. This measures projection rebuilding versus reuse, not reuse versus ordinary wide CG and not an end-to-end speedup.

## First frozen end-to-end budget screen

All arms used the same frozen binary, N=2, rotated/reversed ordering. Caps: 3 s Ladybug and 8 s Dubrovnik; the existing budget checks can overshoot by an attempt. The capture arms in this stage still include the redundant checkpoint residual checks. Costs are independently CPU-audited; lower is better.

| Scene | Arm | Median cost | Native seconds | Operator calls | Scored candidates |
|---|---|---:|---:|---:|---:|
| ladybug-1197 | legacy | 366,423.15 | 3.065 | 1461 | 518.5 |
| ladybug-1197 | rebuild | 366,601.12 | 3.106 | 1531 | 442 |
| ladybug-1197 | reuse | 366,564.42 | 3.166 | 1481 | 496.5 |
| dubrovnik-356 | legacy | 753,687.66 | 8.424 | 1037 | 1504 |
| dubrovnik-356 | rebuild | 754,419.50 | 8.453 | 1247 | 1256 |
| dubrovnik-356 | reuse | 754,006.11 | 8.403 | 1120 | 1387 |

Reuse cost was 0.0386% higher than legacy on Ladybug and 0.0423% higher on Dubrovnik, compared with the earlier prototype's 16.9% Dubrovnik regression. All 12 runs had zero nonlinear rejections. Reuse had a median two CG fallbacks on Ladybug and none on Dubrovnik; its median expansion counts were 8 and 58. Near-equal budget endpoints do not establish a timing speedup.

## Follow-up: time to equal quality

No damping or stopping parameters were retuned. The final code removes only the duplicate checkpoint verification applications. N=2 per arm, same binary, rotated/reversed order. The existing target hook records the first accepted crossing; every endpoint is then independently CPU-certified. All 12 runs hit their target before the cap.

Ladybug target: 366,600, with a 6 s cap, matching the earlier quality study. Dubrovnik target: 754,100, with a 12 s cap, chosen just above the first screen's 754,006 reuse median. **This Dubrovnik target is earlier/easier than the previous study's 723,500 target.** It measures early progress, not deep convergence. It is a same-scene follow-up, not held-out validation.

| Scene | Existing controller | Capture with duplicate checks | Final capture | Existing/final |
|---|---:|---:|---:|---:|
| ladybug-1197 | 2.653 s | 2.890 s | 3.057 s | 0.868× |
| dubrovnik-356 | 6.886 s | 7.875 s | 6.960 s | 0.989× |

A ratio below 1 means the final capture version is slower. Ladybug varied across independent trajectories: final-capture times were 3.323 and 2.792 s, versus 2.504 and 2.802 s for legacy. Dubrovnik was more consistent: all arms finished near cost 754,099.117636 with 1,368 scored candidates. Final capture used 790 operator calls versus legacy's 799, yet took 6.960 s versus 6.886 s. Capture/import overhead and candidate scoring consume the small net linear-work saving. The checked version used 1,085 calls and 7.875 s; removing duplicates cut that version's time by 11.6%.

## Verification and artifacts

The analytic test reproduces a saved CG iterate after importing four directions with zero new operator calls, extends it, and checks smaller/larger shifted solutions against exact answers. It also checks that reconstruction without repeated verification makes zero operator calls and preserves the solution and model prediction. Relative residuals in the analytic shifted tests were at most 4.1e-16.

The narrow Ladybug-49 integration gate matched the previous controller to floating-point precision at eight iterations. Compute Sanitizer reported zero errors for the analytic test, both capture modes on the narrow gate, and actual expansion/scoring paths. The final expansion check exercised eleven expansions and passed a CPU objective audit. CLI and core library builds passed. The diagnostic-only process exit is excluded from the core-library build; this guard was added after timing, without numerical solver changes.

All 24 timed BA runs passed CPU objective audits and finite/monotone trace checks; maximum relative endpoint discrepancy was 1.8e-11. The first screen used 69.232 native solver seconds and the quality follow-up 61.739, totaling 130.971 s. No timed runs were excluded or rerun. No Caspar runs or larger scenes were added; the broad queue remains paused.

- `/workspace/prism-recycle-cg/`: first protocol, frozen binary/source/headers, fixed-operator audit, budget screen, sanitizer checks and summary.
- `/workspace/prism-recycle-cg-fast/`: follow-up protocol and targets, frozen binary/source/headers, quality runs, expanded-path checks and summary.
- `gpu/cg_capture.cuh`: capture and import, plus the CLI diagnostic helper.
- `gpu/retained_krylov.cuh`: projected solve and optional reconstruction without repeated verification.
- `bench/cg_capture_screen.py`, `bench/cg_capture_audit.py`, `bench/cg_capture_quality.py`: experiment drivers.
- `bench/summarize_cg_capture.py`, `bench/summarize_cg_capture_quality.py`: reports from raw run artifacts.

```bash
cmake --build gpu/build --target oca_cuda oca_core test_cg_capture -j2
flock /tmp/prism_gpu.lock gpu/build/test_cg_capture
# Reproduce reports from the immutable frozen artifacts:
python3 bench/summarize_cg_capture.py
python3 bench/summarize_cg_capture_quality.py
```

Legacy per-phase profiler buckets are not adapted to the projection blocks; use native total times and operator counters. Frozen binaries and manifests retain the exact timed versions; do not overwrite them with the current build.

## Assessment

This validates an implementation route for reusing CG work while preserving the successful narrow path. It does not yet justify enabling reuse globally. The first-snapshot speedup over rebuilding a projection was real, but ordinary wide CG is a stronger baseline: many expansions are already very short, and five certification products can absorb their avoided work. At hard systems, the 64-vector cap can still force a restart. The next investigation should determine when a saved basis has enough value to justify import and verification, using fixed-operator captures across shallow and deep expansions; it should not assume that every expansion benefits.

Recycling damping solves is prior art, including [Lin, O’Malley and Vesselinov (2016)](https://doi.org/10.1002/2016WR019028). No novelty, Caspar superiority, or broad performance claim follows from this experiment.
