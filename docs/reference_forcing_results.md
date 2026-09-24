# Fixed-reference reduced-gradient forcing

**Verdict: current sustained eta2 champion retained.**

Selected rule: `reference-safe`. The selection used only lambda 0.1 development tasks; high-damping stress outcomes were excluded.

## What was implemented

The forcing ratio compares reduced gradients at two geometries while holding the reference damping and camera metric fixed:

```
b(x,lambda) = bc(x) - W(x) [V(x)+lambda Dp(x)]^-1 bp(x)
q = ||E_old b(x_new,lambda_old)|| / ||E_old b(x_old,lambda_old)||
eta = clip(1.8 q^2, 1e-12, 0.5)
```

The stored denominator, damping and E come from the accepted attempt before its geometry update. The next numerator uses the new geometry with that old damping/E. Geometry-dependent point diagonals retain the solver trace-based floor. The safeguarded candidate additionally applies the EW-style previous-eta floor. History advances only on acceptance and forcing is held through retries; numeric repair permanently switches control back to the champion formula on the current trajectory.

The point factor and reduced RHS are recomputed at reference damping, then the actual point factors are restored. Existing Rf,uu,corr,w and cached R0f are reused. The only added GPU buffer is E_old: 72*ncam bytes (985104 bytes on Final13682). No new observation-sized or point-factor buffer is allocated. Native timing includes the extra kernels, synchronization and anchor copies. CG matvec counts omit this additional work; probe timing is reported separately.

## Verification

N3 parent/new champion/passive/current-RHS-verification smoke tests preserve work counts and endpoint costs within 1e-7. Maximum GPU reconstructed/current RHS norm discrepancy: 1.61e-15.

The CPU example changes the ordinary reduced norm ratio to 1.075642 solely by changing damping at fixed geometry; the reference ratio stays 1. With the prescribed geometry change, it becomes 1.1. CPU tests also check accepted-only anchors, metric consistency, retry idempotence and repair fallback. These verify the measurement, not a convergence theorem.

## Development at the deployment initialization

N3 on Ladybug598, Dubrovnik356 and Venice89, lambda 0.1, unchanged fixed targets. Champion=sustained eta2; probe=extra reference work with champion decisions; reduced-ew2=the preceding safeguarded reduced-RHS control; reference/reference-safe=new candidates.

| Scene | Lambda | Quality | Arm | Hits | Target seconds median [min,max] | Audited cost | Outers | Rejects | Matvecs |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|
| ladybug-598 | 0.1 | primary | champion | 3/3 | 0.0951 [0.0936, 0.1027] | 182108.571 | 8 | 0 | 51 |
| ladybug-598 | 0.1 | primary | probe | 3/3 | 0.1010 [0.1003, 0.1117] | 182108.571 | 8 | 0 | 51 |
| ladybug-598 | 0.1 | primary | reference | 3/3 | 0.0978 [0.0951, 0.0983] | 181815.177 | 7 | 0 | 54 |
| ladybug-598 | 0.1 | primary | reference-safe | 3/3 | 0.0930 [0.0926, 0.0950] | 181825.952 | 7 | 0 | 49 |
| ladybug-598 | 0.1 | primary | reduced-ew2 | 3/3 | 0.1151 [0.1144, 0.1154] | 181375.529 | 8 | 0 | 80 |
| dubrovnik-356 | 0.1 | primary | probe | 3/3 | 1.0658 [1.0608, 1.0711] | 728618.481 | 11 | 0 | 324 |
| dubrovnik-356 | 0.1 | primary | reference | 3/3 | 1.0005 [0.9984, 1.0137] | 731142.839 | 10 | 0 | 317 |
| dubrovnik-356 | 0.1 | primary | reference-safe | 3/3 | 0.9712 [0.9690, 0.9864] | 726110.399 | 10 | 0 | 297 |
| dubrovnik-356 | 0.1 | primary | reduced-ew2 | 3/3 | 0.7669 [0.7652, 0.7672] | 730961.204 | 12 | 0 | 188 |
| dubrovnik-356 | 0.1 | primary | champion | 3/3 | 1.0020 [1.0011, 1.0046] | 728614.276 | 11 | 0 | 324 |
| venice-89 | 0.1 | primary | reference | 3/3 | 0.5572 [0.5570, 0.5591] | 306194.950 | 30 | 1 | 87 |
| venice-89 | 0.1 | primary | reference-safe | 3/3 | 0.5585 [0.5575, 0.5597] | 304516.953 | 30 | 1 | 88 |
| venice-89 | 0.1 | primary | reduced-ew2 | 3/3 | 0.4452 [0.4449, 0.4452] | 306262.185 | 28 | 0 | 85 |
| venice-89 | 0.1 | primary | champion | 3/3 | 0.4428 [0.4424, 0.4435] | 306304.226 | 25 | 1 | 103 |
| venice-89 | 0.1 | primary | probe | 3/3 | 0.5194 [0.5181, 0.5570] | 306304.226 | 25 | 1 | 103 |

| Arm | Penalized development score (higher is better) |
|---|---:|
| champion | 1.0000 |
| probe | 0.9105 |
| reduced-ew2 | 1.0239 |
| reference | 0.9180 |
| reference-safe | 0.9422 |

A missed run receives 4*cap during selection. Penalty-derived scores are not measured speedups when misses occur. Both candidate definitions were frozen before measurement; selection chooses one without fitting parameters.

## Separate high-damping stress test

Dubrovnik356 lambda 10; these results do not enter selection.

| Scene | Lambda | Quality | Arm | Hits | Target seconds median [min,max] | Audited cost | Outers | Rejects | Matvecs |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|
| dubrovnik-356 | 10.0 | stress | champion | 1/3 | 1.9868 [1.9868, 1.9868] (hits only) | 732769.793 | 42 | 2 | 1213 |
| dubrovnik-356 | 10.0 | stress | probe | 2/3 | 2.1089 [2.1073, 2.1105] (hits only) | 729621.209 | 23 | 2 | 589 |
| dubrovnik-356 | 10.0 | stress | reference-safe | 3/3 | 1.8418 [1.8417, 1.8436] | 729988.045 | 18 | 0 | 585 |

The unchanged champion itself is variable at lambda 10: 1/3 target hits, versus 2/3 for passive probing and 3/3 for reference-safe. A hit-only median must not be called an aggregate speedup here. Comparing champion/probe repeat0, cost differences start at roughly machine precision and grow: about 6e-9 relative by outer 11 and 1.4e-6 by outer 15. The early damping sequence agrees. This is consistent with roundoff-sensitive trajectories; these few runs do not establish a robust stress speedup. No numeric repair disabled the passive controller.

A separate post-study diagnostic checked Rf, factor-status flags, the actual reduced RHS and camera metric byte-for-byte before/after every probe: 143 checks across N3 stress runs passed. Current-RHS norm reconstruction also passed. These instrumented runs use a separate binary, include host snapshots, and are excluded from all selection and speed comparisons. This rules out corruption of those restored/preserved arrays on the checked trajectories, not every possible numerical interaction.

## Frozen transfer

Initial lambda 0.1, N3 per cell. Both prior targets on Trafalgar126 and Final1936; prior primary target on Muell146. The tighter Muell target was excluded prospectively because every preceding arm missed it in all 12s repeats. It is not counted as a success here. These scenes were excluded from this controller selection but are familiar research data, not pristine population holdouts.

| Scene | Lambda | Quality | Arm | Hits | Target seconds median [min,max] | Audited cost | Outers | Rejects | Matvecs |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|
| trafalgar-126 | 0.1 | primary | champion | 3/3 | 0.1136 [0.1134, 0.1259] | 105290.484 | 7 | 0 | 195 |
| trafalgar-126 | 0.1 | primary | probe | 3/3 | 0.1292 [0.1169, 0.1331] | 105290.457 | 7 | 0 | 195 |
| trafalgar-126 | 0.1 | primary | reduced-ew2 | 3/3 | 0.1365 [0.1328, 0.1419] | 105208.511 | 7 | 0 | 249 |
| trafalgar-126 | 0.1 | primary | reference-safe | 3/3 | 0.1221 [0.1220, 0.1368] | 105251.245 | 7 | 0 | 210 |
| trafalgar-126 | 0.1 | tighter | probe | 3/3 | 0.2382 [0.2352, 0.2405] | 104392.089 | 11 | 0 | 455 |
| trafalgar-126 | 0.1 | tighter | reduced-ew2 | 3/3 | 0.2304 [0.2272, 0.2346] | 104384.050 | 10 | 0 | 464 |
| trafalgar-126 | 0.1 | tighter | reference-safe | 3/3 | 0.2025 [0.2023, 0.2031] | 104443.251 | 10 | 0 | 381 |
| trafalgar-126 | 0.1 | tighter | champion | 3/3 | 0.2313 [0.2287, 0.2352] | 104392.071 | 11 | 0 | 455 |
| final-1936 | 0.1 | primary | reduced-ew2 | 3/3 | 0.5416 [0.5408, 0.5626] | 5085877.911 | 4 | 0 | 21 |
| final-1936 | 0.1 | primary | reference-safe | 3/3 | 0.6081 [0.5912, 0.6095] | 5086248.003 | 4 | 0 | 20 |
| final-1936 | 0.1 | primary | champion | 3/3 | 0.5006 [0.5001, 0.5020] | 5098339.730 | 4 | 0 | 16 |
| final-1936 | 0.1 | primary | probe | 3/3 | 0.5607 [0.5582, 0.5689] | 5098339.730 | 4 | 0 | 16 |
| final-1936 | 0.1 | tighter | reference-safe | 3/3 | 0.9260 [0.9253, 0.9271] | 5052889.048 | 5 | 0 | 48 |
| final-1936 | 0.1 | tighter | champion | 3/3 | 0.7343 [0.7321, 0.7469] | 5055268.517 | 5 | 0 | 33 |
| final-1936 | 0.1 | tighter | probe | 3/3 | 0.8046 [0.8045, 0.8139] | 5055268.517 | 5 | 0 | 33 |
| final-1936 | 0.1 | tighter | reduced-ew2 | 3/3 | 0.8491 [0.8480, 0.8506] | 5052905.868 | 5 | 0 | 48 |
| muell-gba146 | 0.1 | primary | champion | 3/3 | 4.2324 [4.2299, 4.2409] | 1946467.159 | 16 | 0 | 980 |
| muell-gba146 | 0.1 | primary | probe | 3/3 | 4.3603 [4.3582, 4.3895] | 1946467.176 | 16 | 0 | 980 |
| muell-gba146 | 0.1 | primary | reduced-ew2 | 3/3 | 4.5311 [4.5257, 4.5402] | 1945371.439 | 16 | 0 | 1065 |
| muell-gba146 | 0.1 | primary | reference-safe | 3/3 | 4.4021 [4.3903, 4.4128] | 1946377.808 | 16 | 0 | 989 |

| Task | Speedup (champion time / selected time) |
|---|---:|
| final-1936/primary | 0.8232x |
| final-1936/tighter | 0.7929x |
| muell-gba146/primary | 0.9614x |
| trafalgar-126/primary | 0.9306x |
| trafalgar-126/tighter | 1.1427x |

Geometric speedup: 0.9223x.

## Passive probe overhead

| Scene / quality | Champion median seconds | Probe median seconds | Probe/champion | Reference probes | Probe kernel/restoration seconds |
|---|---:|---:|---:|---:|---:|
| trafalgar-126 / primary | 0.1136 | 0.1292 | 1.1371 | 6 | 0.0037 |
| trafalgar-126 / tighter | 0.2313 | 0.2382 | 1.0297 | 10 | 0.0062 |
| final-1936 / primary | 0.5006 | 0.5607 | 1.1201 | 3 | 0.0580 |
| final-1936 / tighter | 0.7343 | 0.8046 | 1.0958 | 4 | 0.0771 |
| muell-gba146 / primary | 4.2324 | 4.3603 | 1.0302 | 15 | 0.1332 |

Probe timers include reference kernels, factor restoration and synchronization, but omit the separately charged anchor copies. Passive total-time differences also contain timing and GPU summation variation; they are not exact isolated kernel costs.

The largest extension was skipped because the registered transfer gate failed. No fresh Caspar runs or new Caspar speedup claims are made.

## Interpretation and reproducibility

The selected controller is 8.4% slower geometrically over the five transfer settings. All 60 transfer runs hit their registered targets. The sole selected-rule win is tighter Trafalgar: 11 to 10 outers and 455 to 381 CG matvecs, giving 1.143x speedup. On Final1936 the outer counts are unchanged, but matvecs rise 16 to 20 at the primary target and 33 to 48 at the tighter target. Its passive probe alone costs roughly 10-12% in total time; the active controller adds still more linear work. Muell stays at 16 outers with 980 to 989 matvecs and about 4% more time. These observations separate measurement overhead from worse forcing decisions.

Do not optimize the probe alone and assume the controller will win: Final1936 remains slower than passive probing, and Venice development needs 30 rather than 25 outers despite fewer CG matvecs. A useful next hypothesis is to estimate the marginal value of another linear iteration from quantities already produced by CG and model acceptance. Any such rule needs a separately registered comparison against the same champion and fixed targets.

Holding damping/E fixed removes their direct change from the history ratio. It does not prove that the resulting ratio predicts the value of another CG iteration or the best nonlinear trajectory. Changed forcing can alter later outer counts. Any improvement must exceed its own reference-measurement cost and must be assessed at each quality target.

This is an experimental adaptation of inexact-solve forcing. [Adaptive forcing is established prior art](https://users.wpi.edu/~walker/Papers/forcing_terms%2CSISC_17%2C1996%2C16-32.pdf); implementation and timing evidence alone do not establish novelty. No global convergence claim is made for guarded, clipped, mixed-precision BA.

129 original-observation FP64 endpoint audits, including 3 post-study diagnostics; maximum relative discrepancy 1.87e-12; 138.682 native solver seconds (diagnostics account for 16.240s). Transfer hits 60/60. Same RTX2000 Ada host2237c6528e79. SIMPLE_RADIAL,k2fixed0, half-sum squared original pixel residuals. A hit requires an actual TARGET event within cap and an audited endpoint <=target. No interpolation; loading/export/audit excluded.

[Registered protocol](reference_forcing_protocol.md). Source: `gpu/reference_forcing.h`, `bench/build_reference_forcing.py`, `bench/reference_forcing_study.py`, `bench/report_reference_forcing.py`, `bench/verify_reference_restoration.py`. Frozen binaries, headers, code hashes, logs, traces and endpoints: `/tmp/prism-reference-forcing/`. Durable compact source/binary/trace package: `/workspace/prism-reference-forcing-evidence.tar.xz` (raw endpoints remain under /tmp). Production defaults unchanged.
