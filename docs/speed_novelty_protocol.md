# Frozen speed and curvature-recovery confirmation

Registered 2026-09-10, before running the selected inputs. Machine: the Codex host, RTX 2000 Ada. Machine-readable selection, binary hashes, targets and raw outputs live under `/tmp/prism-speed-novelty/`.

The question is whether the sustained-eta2 champion transfers to new BAL instances, and whether measured curvature adds value beyond multiplying damping by four and retaining a floor. This is a short confirmation experiment, not sufficient evidence for a universal fastest-solver claim.

## Frozen panel and configurations

| Instance | Cameras | Points | Observations | Measured native cap |
|---|---:|---:|---:|---:|
| Ladybug-539 | 539 | 65,220 | 277,273 | 5 s |
| Trafalgar-138 | 138 | 44,033 | 165,899 | 5 s |
| Final-394 | 394 | 100,368 | 534,408 | 8 s |

These instances were selected before downloading or observing solver results. Searches of local reports and collaboration records found no previous use. Their dataset families are familiar: different BAL instances are not necessarily independent captures or disjoint observations. Input URLs and hashes are recorded. The public sources are the [Ladybug](https://grail.cs.washington.edu/projects/bal/ladybug.html), [Trafalgar](https://grail.cs.washington.edu/projects/bal/trafalgar.html) and [Final](https://grail.cs.washington.edu/projects/bal/final.html) dataset pages.

The champion is the exact binary with SHA256 `1e3d2cf22a8a43075114e0ca2024923dad330461e35d0074938d0412cd77ecc0`, initial lambda 0.1 and sustained forcing multiplier 2, with all flags frozen from `prism-rl-sustained/candidate.json`. There is no learned controller or multishift menu.

Comparison arms: champion; the existing pinned Caspar FP32 and FP64 binaries; Ceres 2.2.0 LM with iterative Schur/Schur-Jacobi; and Ceres Dogleg with sparse Schur/SuiteSparse. Both Ceres arms use initial radius 10000 and eight CPU threads. These are additional CPU algorithm baselines, not replacements for comparisons with other GPU solvers. No solver parameters are tuned on the new inputs.

## Targets, repeats and measurements

1. Check derivative compatibility on the previously used Ladybug-49 input, N=3. Check identical CUDA fatbinary sections and run the existing 100-case Schur monotonicity/energy-identity test.
2. Calibrate each new input using N=3 guard-off eta2 and N=3 Caspar FP64 runs, at 15 native seconds and 600 iterations. Choose the minimum independently audited endpoint across valid calibration arms. This is a bounded reference cost, not an optimum certificate.
3. Freeze all three scene anchors before starting any measured target run. Test 0.5%, 1% and 2% above each anchor. The primary tolerance is 1%.
4. Run N=3 per scene, tolerance and comparison arm, rotating arm order within each scene/target block. Run guard-off and retained-times-four recovery at the primary tolerance, N=3, on every selected scene. Champion primary runs are shared with the speed comparison. Total: 153 measured runs and 18 calibration runs.

The objective is half the sum of squared residuals over the original observation set, with SIMPLE_RADIAL intrinsics and k2 fixed to zero. Every terminal state is exported and independently evaluated against original FP64 observations. Relative audit tolerance is 1e-6, far below the quality tolerances. Caspar FP32 retains the existing conservative native stopping margin of 0.1%; qualification uses the audited objective, not its native FP32 score.

Report median and min–max only when all three repeats reach the target inside the cap. Retain misses, final costs, relative target gaps, iteration/rejection counts, numerical rebuilds, cap hits and audit errors. Do not average speedups over an undisclosed changing subset of successes. A small target miss is reported numerically, not described as a large quality regression.

Native solve time is primary. Prism includes local solver setup; external graph construction is separately recorded and excluded from the external native timers. Export, loading and independent evaluation are outside native solve time. Also report native plus separately recorded graph setup for successful runs. All algorithms, including CPU baselines, run serially under the local GPU lock. The native cap is primary; iteration caps differ between accepted Prism outers and attempted external outers. Ceres may complete an iteration beyond the native cap: retain the endpoint and classify any late target crossing as a miss.

## Attribution and preflight amendment

The isolated derivative changes only the host-side recovery formula: the champion uses `4*max(lambda,lambda-q)`, while the simple control uses `4*lambda`. Both retain the floor, rebuild coupled camera/point damping, restart CG, charge all repair work, and retain existing acceptance and radius checks. Guard-off removes numerical recovery without changing eta2.

Preflight discovered that the original fixed-eta wrapper refuses guard-off configurations. Before any selected-scene calibration, the derivative received a research-only `OCA_SCHUR_ABLATION` bypass of that configuration validation. The original champion binary is unchanged. The failed preflight attempts and initial protocol are retained under `compatibility-v1-preflight/` and `protocol-v1-preflight.json`; `amendment.json` explains the change. Compatibility checks compare original versus derivative with eta2 and default recovery, and compare guard-off original versus derivative with the fixed-eta wrapper disabled. This tests visited trajectories and identical device code, not universal bitwise determinism.

Curvature sizing must deliver at least 1.10x faster time at equal target-hit reliability on at least two guard-active instances, without a greater than 1.10x slowdown on another, to support incremental performance value in this panel. Fewer than two active instances means insufficient evidence. No scene substitution, tuning or champion promotion follows from a single promising run.

## Reproduction

Builders and runner: `bench/build_speed_novelty.py` and `bench/speed_novelty_study.py`. Run phases sequentially: `compatibility`, `calibrate`, `measure`. A completed cell is resumed only when its target, cap and binary hash agree. The runner hash is frozen in `protocol.json`.

Losslessly compressed endpoint states, logs, exact commands, code and input hashes accompany the report. Generated raw state exports are removed only after verifying the compressed stream reconstructs the same SHA256. Original BAL files and previous experiments are not altered.

## Separately registered late-stage diagnostic

After calibration revealed negative curvature after useful-quality targets on Ladybug-539, a separate follow-up was registered at 12:10:24 UTC, before any late-stage champion-versus-times-four comparison. Its selection rule includes every new panel instance with negative curvature in any guard-off calibration repeat: only Ladybug-539 qualified. All three recovery arms receive three fresh repeats, with the same 15-second/600-iteration limit as calibration, continuing until stall or the cap. It does not change the primary panel, its targets or its novelty criterion. Endpoint quality, work and repair magnitudes are diagnostic; time to stall is not time to equal quality. The plan is `late-diagnostic-plan.json`; runner is `bench/speed_novelty_late.py`.
