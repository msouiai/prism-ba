# CG marginal model-value results

**Verdict: retain the sustained eta2 champion.**

Selected on development only: `conservative`. All configurations start at lambda 0.1. A target is fixed before running an arm; timings below are actual native TARGET events, checked against independent original-observation FP64 endpoint audits. N=3 per cell; no interpolated crossings. SIMPLE_RADIAL, k2 fixed at zero, half sum of squared original pixel residuals. Host2237c6528e79, RTX2000 Ada. Defaults unchanged.

The conservative rule delivers a modest measured gain: 1.0322x geometrically over five medium scene/target settings. Trafalgar improves at both targets; Final1936 and Muell have zero interventions. The 5% registered extension gate is not met. This is useful localized evidence, not a broadly established replacement. The work-only comparator scores 1.0478x overall but slows the primary Trafalgar target by 16.3% and Venice development by 20.0%; its gains at tighter targets do not erase those counterexamples.

## Mathematics and limits

For a fixed SPD reduced camera operator A and fixed SPD preconditioner M, let G_j be the decrease in q(x)=x^T A x/2-b^T x. PCG supplies the increment without new GPU work:

```
delta_j = alpha_j * (r_j^T M^-1 r_j) / 2
G_j = sum(delta_i, i <= j)
```

If the next step costs dt and gives model gain dG, then (G+dG)/(T+dt) exceeds G/T exactly when dG/dt exceeds G/T. The implementation estimates the next rate with a trailing three-step window. T includes measured setup and CG time plus the previous attempt's scoring/acceptance time. Two consecutive low-rate windows are needed. The first possible extra stop is depth 4. This algebra justifies the rate comparison; the backward-looking forecast itself is heuristic.

The rate arm uses a marginal/average threshold of 1; conservative uses 0.1. The work-only comparator replaces time by iteration count and ignores setup. Passive computes the rate rule but never acts. All retain the champion's original residual stop. Extra stops require residual <=0.5 times the RHS norm and pass the existing explicit true-residual check at that tolerance. Retries, a preceding rejected/low-rho attempt, and numeric repair suppress intervention; repair disables it permanently. Existing coupled damping, camera radius, full-model prediction, true-cost acceptance and rescue checks remain.

G measures only reduced damped camera-model decrease, not the full undamped nonlinear BA gain. The eliminated-point constant is omitted. Camera-radius clipping can change the final step, and later CG gains can rebound after a quiet window. A small recent gain is neither an upper bound on remaining linear error nor proof that terminating improves nonlinear time-to-target. No global convergence or novelty claim is made.

This is established quadratic-decrease truncation: [Nash's survey](https://doi.org/10.1016/S0377-0427(00)00426-X) describes marginal-versus-average model reduction. [Ceres already implements a quadratic-model CG stopping test](https://github.com/ceres-solver/ceres-solver/blob/master/internal/ceres/conjugate_gradients_solver.h). Our time accounting, trailing window and safeguards are an experimental adaptation, not evidence of a new algorithmic principle.

## Verification and cost

CPU and GPU model-gain identities passed: maximum relative discrepancies 1.7e-15 and 1.22e-13. N3 parent/new-disabled/passive smoke preserved work counts and audited costs within 1e-7. Separate GPU identity runs add explicit operator applications and are excluded from all performance comparisons.

Performance modes allocate zero additional GPU bytes and launch no extra probe kernels, reductions or synchronization. They add host scalar arithmetic and steady-clock reads. Passive timing measures this overhead plus ordinary run variation. Active extra stops still pay the existing explicit true-residual check.

Across the five medium settings passive monitoring has a 0.9833x geometric speedup (about 1.7% extra time) with unchanged work counts. The lack of new GPU work does not imply zero runtime overhead. Small same-work timing differences include host overhead and measurement variation.

## Development

| Scene | Lambda | Quality | Arm | Hits | Target seconds median [min,max] | Audited cost | Outers | Rejects | Matvecs |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|
| ladybug-598 | 0.1 | primary | champion | 3/3 | 0.1026 [0.0940, 0.1030] | 182108.571 | 8 | 0 | 51 |
| ladybug-598 | 0.1 | primary | passive | 3/3 | 0.0960 [0.0946, 0.1023] | 182108.571 | 8 | 0 | 51 |
| ladybug-598 | 0.1 | primary | rate | 3/3 | 0.0840 [0.0835, 0.0895] | 182151.496 | 7 | 0 | 43 |
| ladybug-598 | 0.1 | primary | conservative | 3/3 | 0.0929 [0.0926, 0.0937] | 182068.388 | 8 | 0 | 50 |
| ladybug-598 | 0.1 | primary | work-only | 3/3 | 0.0881 [0.0873, 0.0892] | 182099.556 | 8 | 0 | 41 |
| dubrovnik-356 | 0.1 | primary | passive | 3/3 | 1.0052 [1.0042, 1.0322] | 728606.414 | 11 | 0 | 324 |
| dubrovnik-356 | 0.1 | primary | rate | 0/3 | MISS | 740510.276 | 46 | 13 | 325 |
| dubrovnik-356 | 0.1 | primary | conservative | 3/3 | 0.6630 [0.6570, 0.6817] | 731004.011 | 8 | 0 | 207 |
| dubrovnik-356 | 0.1 | primary | work-only | 3/3 | 0.4710 [0.4699, 0.4796] | 729576.670 | 10 | 0 | 82 |
| dubrovnik-356 | 0.1 | primary | champion | 3/3 | 1.0040 [1.0007, 1.0065] | 728614.791 | 11 | 0 | 324 |
| venice-89 | 0.1 | primary | rate | 3/3 | 0.5056 [0.5048, 0.5058] | 306296.691 | 30 | 1 | 109 |
| venice-89 | 0.1 | primary | conservative | 3/3 | 0.4426 [0.4424, 0.4704] | 306304.227 | 25 | 1 | 103 |
| venice-89 | 0.1 | primary | work-only | 3/3 | 0.5313 [0.5291, 0.5336] | 306295.120 | 32 | 1 | 112 |
| venice-89 | 0.1 | primary | champion | 3/3 | 0.4427 [0.4427, 0.4615] | 306304.227 | 25 | 1 | 103 |
| venice-89 | 0.1 | primary | passive | 3/3 | 0.4426 [0.4412, 0.4584] | 306304.227 | 25 | 1 | 103 |

| Arm | Penalized development score (higher better) |
|---|---:|
| champion | 1.0000 |
| conservative | 1.1870 |
| passive | 1.0219 |
| rate | 0.4064 |
| work-only | 1.2742 |

A miss receives 4*cap for selection; scores involving misses are not measured speedups. Only rate and conservative were eligible for selection. All arms and constants were fixed in advance.

| Scene / quality | Arm | Extra stops median [min,max] | CG matvecs median | Outers median |
|---|---|---:|---:|---:|
| ladybug-598 / primary | champion | 0 [0, 0] | 51 | 8 |
| ladybug-598 / primary | passive | 0 [0, 0] | 51 | 8 |
| ladybug-598 / primary | rate | 1 [1, 1] | 43 | 7 |
| ladybug-598 / primary | conservative | 1 [1, 1] | 50 | 8 |
| ladybug-598 / primary | work-only | 3 [3, 3] | 41 | 8 |
| dubrovnik-356 / primary | champion | 0 [0, 0] | 324 | 11 |
| dubrovnik-356 / primary | passive | 0 [0, 0] | 324 | 11 |
| dubrovnik-356 / primary | rate | 4 [4, 5] | 325 | 46 |
| dubrovnik-356 / primary | conservative | 1 [1, 1] | 207 | 8 |
| dubrovnik-356 / primary | work-only | 3 [3, 3] | 82 | 10 |
| venice-89 / primary | champion | 0 [0, 0] | 103 | 25 |
| venice-89 / primary | passive | 0 [0, 0] | 103 | 25 |
| venice-89 / primary | rate | 2 [2, 2] | 109 | 30 |
| venice-89 / primary | conservative | 0 [0, 0] | 103 | 25 |
| venice-89 / primary | work-only | 3 [3, 3] | 112 | 32 |

On Dubrovnik356, conservative makes one extra stop and changes the complete trajectory from 11 outers/324 matvecs to 8/207 in all three repeats: median 1.0040s to 0.6630s. The aggressive rate rule misses the target in all three repeats: two terminate at 46 outers after 13 rejects, while another reaches the cap after 80 outers and numeric repair. An inexpensive local quadratic step is not necessarily a good nonlinear trajectory.


## Frozen medium transfer

Trafalgar126 and Final1936 use both existing quality targets; Muell146 uses its existing primary target. Tighter Muell was excluded before this study after repeated 12s misses in earlier work. These scenes were excluded from controller selection but are familiar research data, not pristine population holdouts.

| Scene | Lambda | Quality | Arm | Hits | Target seconds median [min,max] | Audited cost | Outers | Rejects | Matvecs |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|
| trafalgar-126 | 0.1 | primary | champion | 3/3 | 0.1131 [0.1125, 0.1281] | 105290.458 | 7 | 0 | 195 |
| trafalgar-126 | 0.1 | primary | passive | 3/3 | 0.1193 [0.1191, 0.1267] | 105290.455 | 7 | 0 | 195 |
| trafalgar-126 | 0.1 | primary | work-only | 3/3 | 0.1314 [0.1279, 0.1330] | 104762.610 | 10 | 0 | 211 |
| trafalgar-126 | 0.1 | primary | conservative | 3/3 | 0.1030 [0.1017, 0.1074] | 105393.532 | 7 | 0 | 164 |
| trafalgar-126 | 0.1 | tighter | passive | 3/3 | 0.2358 [0.2290, 0.2475] | 104392.066 | 11 | 0 | 455 |
| trafalgar-126 | 0.1 | tighter | work-only | 3/3 | 0.1856 [0.1852, 0.1870] | 104461.562 | 12 | 0 | 341 |
| trafalgar-126 | 0.1 | tighter | conservative | 3/3 | 0.2096 [0.2090, 0.2112] | 104438.029 | 11 | 0 | 407 |
| trafalgar-126 | 0.1 | tighter | champion | 3/3 | 0.2310 [0.2267, 0.2318] | 104391.931 | 11 | 0 | 455 |
| final-1936 | 0.1 | primary | work-only | 3/3 | 0.4946 [0.4933, 0.4973] | 5098459.807 | 4 | 0 | 15 |
| final-1936 | 0.1 | primary | conservative | 3/3 | 0.5186 [0.5057, 0.5207] | 5098339.730 | 4 | 0 | 16 |
| final-1936 | 0.1 | primary | champion | 3/3 | 0.5027 [0.5003, 0.5078] | 5098339.730 | 4 | 0 | 16 |
| final-1936 | 0.1 | primary | passive | 3/3 | 0.5079 [0.5001, 0.5354] | 5098339.730 | 4 | 0 | 16 |
| final-1936 | 0.1 | tighter | conservative | 3/3 | 0.7292 [0.7292, 0.7368] | 5055268.517 | 5 | 0 | 33 |
| final-1936 | 0.1 | tighter | champion | 3/3 | 0.7277 [0.7274, 0.7380] | 5055268.517 | 5 | 0 | 33 |
| final-1936 | 0.1 | tighter | passive | 3/3 | 0.7274 [0.7268, 0.7335] | 5055268.517 | 5 | 0 | 33 |
| final-1936 | 0.1 | tighter | work-only | 3/3 | 0.6268 [0.6267, 0.6429] | 5069155.488 | 5 | 0 | 20 |
| muell-gba146 | 0.1 | primary | champion | 3/3 | 4.2364 [4.2363, 4.2430] | 1946467.135 | 16 | 0 | 980 |
| muell-gba146 | 0.1 | primary | passive | 3/3 | 4.2336 [4.2322, 4.2401] | 1946467.168 | 16 | 0 | 980 |
| muell-gba146 | 0.1 | primary | work-only | 3/3 | 4.2363 [4.2348, 4.2365] | 1946467.144 | 16 | 0 | 980 |
| muell-gba146 | 0.1 | primary | conservative | 3/3 | 4.2288 [4.2259, 4.2341] | 1946467.141 | 16 | 0 | 980 |

| Task | Speedup (champion time / selected time) |
|---|---:|
| final-1936/primary | 0.9693x |
| final-1936/tighter | 0.9978x |
| muell-gba146/primary | 1.0018x |
| trafalgar-126/primary | 1.0975x |
| trafalgar-126/tighter | 1.1017x |

Geometric speedup: 1.0322x.

| Scene / quality | Arm | Extra stops median [min,max] | CG matvecs median | Outers median |
|---|---|---:|---:|---:|
| trafalgar-126 / primary | champion | 0 [0, 0] | 195 | 7 |
| trafalgar-126 / primary | passive | 0 [0, 0] | 195 | 7 |
| trafalgar-126 / primary | work-only | 4 [4, 4] | 211 | 10 |
| trafalgar-126 / primary | conservative | 1 [1, 1] | 164 | 7 |
| trafalgar-126 / tighter | champion | 0 [0, 0] | 455 | 11 |
| trafalgar-126 / tighter | passive | 0 [0, 0] | 455 | 11 |
| trafalgar-126 / tighter | work-only | 4 [4, 4] | 341 | 12 |
| trafalgar-126 / tighter | conservative | 1 [1, 1] | 407 | 11 |
| final-1936 / primary | champion | 0 [0, 0] | 16 | 4 |
| final-1936 / primary | passive | 0 [0, 0] | 16 | 4 |
| final-1936 / primary | work-only | 2 [2, 2] | 15 | 4 |
| final-1936 / primary | conservative | 0 [0, 0] | 16 | 4 |
| final-1936 / tighter | champion | 0 [0, 0] | 33 | 5 |
| final-1936 / tighter | passive | 0 [0, 0] | 33 | 5 |
| final-1936 / tighter | work-only | 3 [3, 3] | 20 | 5 |
| final-1936 / tighter | conservative | 0 [0, 0] | 33 | 5 |
| muell-gba146 / primary | champion | 0 [0, 0] | 980 | 16 |
| muell-gba146 / primary | passive | 0 [0, 0] | 980 | 16 |
| muell-gba146 / primary | work-only | 0 [0, 0] | 980 | 16 |
| muell-gba146 / primary | conservative | 0 [0, 0] | 980 | 16 |

Conservative stops once on each Trafalgar run. At the primary target, matvecs fall 195 to 164 with seven outers unchanged; at the tighter target they fall 455 to 407 with 11 outers unchanged. Final1936 remains 16/33 matvecs at its primary/tighter targets, and Muell remains 980. The improvement therefore comes from less camera linear work on Trafalgar, not fewer rejections across the panel.

A mathematically relevant follow-up is the full damped quadratic gain after point elimination: it includes the constant 0.5*bp^T(V+lambda*Dp)^-1*bp as well as camera gain G. The current timing rule uses G alone. The solver has an optional computation of this point term, but it is not enabled in the frozen champion; including it would require accounting for an extra reduction or fusing that computation. That change should be measured separately rather than silently folded into these results.


The largest extension was skipped because the registered medium gate failed. No fresh Caspar comparison was run. Earlier Caspar measurements are unchanged.

## Evidence

117 independently audited endpoints; maximum relative cost discrepancy 5.59e-12; 98.046 native solver seconds including smoke diagnostics. Medium-panel target hits: 60/60.

[Protocol](cg_value_protocol.md). Implementation: `gpu/cg_value.h`; builder: `bench/build_cg_value.py`; runner: `bench/cg_value_study.py`; reporter: `bench/report_cg_value.py`. Exact binary, source, local headers, input/code hashes, commands, traces, logs and audited endpoints: `/tmp/prism-cg-value/`. The compact durable evidence package is `/workspace/prism-cg-value-evidence.tar.xz`; raw endpoints remain in /tmp to conserve shared quota.
