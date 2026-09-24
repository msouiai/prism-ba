# Retained Krylov basis: bounded prototype results

The reuse mechanism works, but the full prototype is not ready to replace the current controller. It is off by default. In the short budget screen, Ladybug loses only 0.074% objective quality, while Dubrovnik loses 16.90%. The projected-rebuild control also regresses on Dubrovnik, so these results do not isolate basis retention as the cause.

## Implementation

`OCA_KRYLOV_REUSE=1` enables retention; `=2` uses the same projected solver but rebuilds on menu expansion. Both require the existing demand menu (`OCA_DEMAND_MENU=1` or `2`) and its restricted FP64, unshared, diagonally equilibrated configuration. This screen uses paired demand mode 2.

`gpu/retained_krylov.cuh` stores at most 64 camera-space basis vectors plus the next vector, builds a symmetric projected operator with two-pass full orthogonalization, and solves its shifted systems by dense Cholesky. It checks depths 8, 16, 32 and 64. Every proposed shift must pass a true full-operator residual check at the existing forcing tolerance before the projected menu is scored. If any shift fails at the cap, the original CG sweep runs instead. Residual checks, projection work, reconstruction, allocation, and fallback all count in native timing and operator-call totals.

Retention is allowed only on the explicit same-state, same-point-damping menu expansion. Accepted nonlinear steps and ordinary retries reset the basis, including retries that change point damping. The follow-up Dubrovnik run exercised five joint damping rebuilds. Nonlinear scoring, alpha search, saved narrow fallback, and acceptance guards remain in place.

This prototype changes the linear iteration schedule: it scores the qualified terminal projected depth, whereas legacy CG also scores intermediate checkpoints. Therefore legacy-versus-prototype is not a pure reuse ablation. The rebuild-versus-reuse control isolates the policy difference more closely, but independent GPU runs can still follow different floating-point trajectories. No claim of equivalent iterates is made.

At 13,682 cameras and nine variables per camera, 64 FP64 basis vectors alone occupy 60.126 MiB. The extra next vector and work vector bring the main vector allocation to roughly 62 MiB. Full orthogonalization adds bandwidth and synchronization costs. No largest-scene run was performed here.

## Frozen budget screen

N=2 per scene and arm, rotated/reversed order, same frozen executable and flags except the tested option. Native caps: Ladybug 3 s, Dubrovnik 8 s. Caps are checked at existing solver boundaries and can overshoot by an attempt. CPU-audited objective, lower is better. These are budget endpoints, not times to equal quality.

| Scene | Method | Median cost | Native seconds | Matvecs | Scored candidates | Expansions | CG fallbacks |
|---|---|---:|---:|---:|---:|---:|---:|
| ladybug-1197 | legacy | 366,515.69 | 3.158 | 1565.5 | 459 | 6 | 0 |
| ladybug-1197 | rebuild | 366,756.10 | 3.134 | 1551.5 | 358.5 | 5.5 | 5.5 |
| ladybug-1197 | reuse | 366,785.73 | 3.249 | 1546 | 369.5 | 5 | 7 |
| dubrovnik-356 | legacy | 753,687.66 | 8.335 | 1037 | 1504 | 61 | 0 |
| dubrovnik-356 | rebuild | 871,567.59 | 8.328 | 1244.5 | 642.5 | 5 | 0 |
| dubrovnik-356 | reuse | 881,032.18 | 8.290 | 1245.5 | 659 | 7 | 0 |

All 12 budget runs had zero nonlinear rejections. Reuse retained a median 92 vectors across five expansions on Ladybug and 72 vectors across seven expansions on Dubrovnik; these are cumulative basis lengths available for reuse, not measured wall-time savings. Ladybug needed a median seven legacy CG fallbacks. Dubrovnik needed none in this short screen, yet its objective still regressed. Avoiding restarts alone does not ensure good nonlinear progress.

## Iteration-cap follow-up

No solver tuning followed the budget screen. N=2 rebuild/reuse runs requested 30 Ladybug iterations or 100 Dubrovnik iterations, with a 30 s safety cap. All four Ladybug runs reached 30 iterations:

| Ladybug, 30 iterations | Rebuild | Reuse |
|---|---:|---:|
| Native seconds | 2.741 | 2.405 |
| CPU cost | 366,629.21 | 366,956.61 |
| Matvecs | 1355 | 1120.5 |

Reuse took 12.3% less time (1.140× ratio), with 0.089% higher cost and 17.3% fewer total operator calls. This is an equal-iteration comparison, not a time-to-equal-quality speedup; differing paths and N=2 limit causal attribution.

Dubrovnik does not support an equal-iteration ratio. Rebuild reached 100 iterations in 8.159 and 9.043 s, with costs 870,726 and 825,316. Reuse reached 100 iterations in 8.000 s at cost 876,370 in one repeat; the other converged after 90 accepted iterations, five rejections, and 24.536 s at cost 689,103. That second run used 35 CG fallbacks and five joint damping rebuilds. Preserve this variability rather than averaging it into a speedup claim.

One follow-up repeat overlapped a small analytic GPU test. Its complete artifacts were preserved in `excluded-overlap/`, excluded from reported results, and repeated once after the test ended. The replacement is the 24.536 s run above; no other reruns or selection were performed.

## Verification and reproduction

Both CLI and core library built. The analytic test covers basis extension, post-hoc larger/smaller shifts against exact solutions, model predictions, non-SPD rejection and reset. Its true residuals were at most 5.1e-16. Compute Sanitizer reported zero errors for that test and both projected modes on Ladybug-49. All 20 included BA endpoints passed independent CPU audits (maximum relative discrepancy 5.82e-12); accepted objective traces were finite and monotone. The default-off smoke endpoint differed from the prior executable by about 0.000095%, within existing GPU reduction variability.

The 12-run budget screen used 68.988 native solver seconds; the eight included follow-ups used 60.028 seconds. The broad queue remains paused. No Caspar reruns or large-scene jobs were started.

```bash
cmake --build gpu/build --target oca_cuda oca_core test_retained_krylov -j2
flock /tmp/prism_gpu.lock gpu/build/test_retained_krylov
# Runner requires the frozen binary at ROOT/prism-frozen.
python3 bench/retained_krylov_screen.py --root /workspace/prism-recycle
python3 bench/retained_krylov_screen.py --root /workspace/prism-recycle --fixed-work
python3 bench/summarize_retained_krylov.py
```

Artifacts: `/workspace/prism-recycle/`, including the protocol, frozen source/header/binary, manifests, logs, exported states, CPU audits, per-run metrics, summary, smoke checks, and hashes. Per-phase legacy profiling has not been adapted to the new projection block; use the native total and operator counters reported here.

## Assessment

The next useful change would preserve the existing CG checkpoint/selection behavior while retaining its generated subspace for later shifts. That would avoid confounding reuse with a new iteration schedule. An identical captured-operator microbenchmark should then measure expansion cost separately from nonlinear trajectory changes. Merely increasing the basis cap or running larger scenes is not justified by this screen.

The prior-art basis is [Lin, O’Malley and Vesselinov (2016)](https://doi.org/10.1002/2016WR019028): recycle a Krylov space across damping choices at a fixed linearization. This implementation adapts that principle to the reduced camera operator; it is not their LSQR implementation, and reuse itself is not a novelty claim.
