# BA-specific accuracy and damping pilot

**Verdict: retain the sustained eta2 champion; the selected rule failed the registered transfer gate.**

Selected from development only: `joint`. Transfer geometric speedup versus champion: withheld because a target was missed.

## Mechanism and mathematical limits

At fixed geometry, the full gradient g=(bc,bp) is independent of damping. The reduced camera RHS bc-W(V+lambda Dp)^-1bp changes with lambda. Using consecutive reduced norms to set CG accuracy therefore mixes geometric progress with the change in the eliminated point system. This is an exact algebraic observation, not proof that the existing forcing is suboptimal on every scene.

The prototype uses a fixed initial normalization for the camera and point gradient norms, costing two extra GPU reductions per new assembly. This is a progress signal only: the true CG residual check remains in the solver coordinate system. It is not invariant to arbitrary within-block reparameterization.

The model variant places a sqrt(abs(1-rho)) floor on forcing accuracy. The joint variant also limits accepted lambda decay using that discrepancy. These mappings are explicitly heuristic. Full model prediction and true cost are used for rho, but discrepancy does not certify the error of an inexact damped solve. All radius, rejection, numeric repair and acceptance safeguards are preserved.

Interpretation after transfer: removing lambda dependence does not necessarily improve the forcing signal. With exact point back-substitution, the full damped linear residual is (camera Schur residual,0). Full-gradient progress includes point components eliminated by that solve. Replacing reduced progress by a normalized full gradient can discard useful information about the camera problem. This is a structural explanation to investigate, not a causal ablation proving why each timing changed.

## Prior art and novelty assessment

[Eisenstat and Walker](https://users.wpi.edu/~walker/Papers/forcing_terms%2CSISC_17%2C1996%2C16-32.pdf) established adaptive forcing; [large-scale BA already uses inexact Newton methods](https://www.microsoft.com/en-us/research/publication/bundle-adjustment-in-the-large/). Full-gradient forcing and model-discrepancy feedback should not be presented as new general concepts. This pilot tests their implementation and coupling in Prism, with established controls retained. Neither a new formula nor a speedup alone establishes algorithmic novelty.

For an ideal SPD quadratic A, the unclaimed damped model improvement is 0.5*e^T*A^-1*e, where e=A*d+g. A certified lower eigenvalue bound would upper-bound this quantity; the smallest explored Ritz value is generally not such a bound. Clipping and mixed-precision assembly further prevent treating a simple spectral heuristic as a certificate. No convergence theorem for this implementation is claimed.

## Development comparisons

N3 per arm/scene/initialization. Original = prior reduced-norm heuristic; champion = sustained multiplier2; constant = eta0.5; reduced-ew2 = safeguarded EW2 with forcing held through retries; gradient-ew2 substitutes the normalized full gradient; model adds discrepancy; joint additionally modifies accepted damping decay. These are not all single-factor ablations: reduced-ew2 also changes retry history versus original.

| Scene | Lambda | Quality | Arm | Hits | Target seconds median [min,max] | Audited cost | Outers | Rejects | Matvecs |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|
| ladybug-598 | 0.1 | primary | original | 3/3 | 0.1164 [0.1064, 0.1430] | 182109.314 | 6 | 0 | 84 |
| ladybug-598 | 0.1 | primary | champion | 3/3 | 0.0944 [0.0941, 0.0944] | 182108.571 | 8 | 0 | 51 |
| ladybug-598 | 0.1 | primary | constant | 3/3 | 0.1122 [0.1099, 0.1194] | 181476.372 | 9 | 0 | 39 |
| ladybug-598 | 0.1 | primary | reduced-ew2 | 3/3 | 0.1150 [0.1146, 0.1212] | 181375.339 | 8 | 0 | 80 |
| ladybug-598 | 0.1 | primary | gradient-ew2 | 3/3 | 0.1481 [0.1478, 0.1577] | 182197.133 | 6 | 0 | 157 |
| ladybug-598 | 0.1 | primary | model | 3/3 | 0.1049 [0.1044, 0.1316] | 181914.215 | 9 | 0 | 51 |
| ladybug-598 | 0.1 | primary | joint | 3/3 | 0.0878 [0.0855, 0.0897] | 181965.124 | 6 | 0 | 43 |
| ladybug-598 | 10.0 | primary | champion | 3/3 | 0.1041 [0.1040, 0.1048] | 182065.052 | 10 | 1 | 46 |
| ladybug-598 | 10.0 | primary | constant | 3/3 | 0.1102 [0.1091, 0.1341] | 182122.856 | 10 | 0 | 39 |
| ladybug-598 | 10.0 | primary | reduced-ew2 | 3/3 | 0.1369 [0.1365, 0.1423] | 181712.882 | 10 | 0 | 82 |
| ladybug-598 | 10.0 | primary | gradient-ew2 | 3/3 | 0.2171 [0.2158, 0.2270] | 182125.342 | 12 | 0 | 212 |
| ladybug-598 | 10.0 | primary | model | 3/3 | 0.1091 [0.1082, 0.1093] | 182148.151 | 10 | 1 | 54 |
| ladybug-598 | 10.0 | primary | joint | 3/3 | 0.1048 [0.1045, 0.1053] | 181995.766 | 10 | 0 | 51 |
| ladybug-598 | 10.0 | primary | original | 3/3 | 0.1366 [0.1359, 0.1367] | 181712.882 | 10 | 0 | 82 |
| dubrovnik-356 | 0.1 | primary | champion | 3/3 | 1.0134 [1.0070, 1.0420] | 728611.868 | 11 | 0 | 324 |
| dubrovnik-356 | 0.1 | primary | constant | 0/3 | MISS | 737167.506 | 48 | 9 | 1079 |
| dubrovnik-356 | 0.1 | primary | reduced-ew2 | 3/3 | 0.7772 [0.7668, 0.7982] | 730958.133 | 12 | 0 | 189 |
| dubrovnik-356 | 0.1 | primary | gradient-ew2 | 3/3 | 1.0130 [1.0096, 1.0141] | 730536.348 | 12 | 0 | 311 |
| dubrovnik-356 | 0.1 | primary | model | 3/3 | 1.0747 [1.0717, 1.0761] | 730457.716 | 14 | 0 | 306 |
| dubrovnik-356 | 0.1 | primary | joint | 3/3 | 1.1995 [1.1969, 1.2230] | 726928.872 | 16 | 0 | 328 |
| dubrovnik-356 | 0.1 | primary | original | 3/3 | 1.3264 [1.3256, 1.3297] | 730422.155 | 11 | 1 | 474 |
| dubrovnik-356 | 10.0 | primary | constant | 2/3 | 3.1082 [2.4390, 3.7773] (hits only) | 729904.515 | 43 | 2 | 467 |
| dubrovnik-356 | 10.0 | primary | reduced-ew2 | 3/3 | 1.2899 [1.2841, 1.2907] | 731323.075 | 20 | 1 | 321 |
| dubrovnik-356 | 10.0 | primary | gradient-ew2 | 3/3 | 0.7960 [0.7936, 0.8138] | 723770.549 | 12 | 0 | 226 |
| dubrovnik-356 | 10.0 | primary | model | 3/3 | 3.5434 [3.0985, 3.8817] | 731042.423 | 67 | 1 | 563 |
| dubrovnik-356 | 10.0 | primary | joint | 3/3 | 1.3430 [1.3420, 1.3434] | 728476.719 | 16 | 0 | 416 |
| dubrovnik-356 | 10.0 | primary | original | 3/3 | 2.3178 [2.3177, 2.3281] | 731149.699 | 24 | 3 | 734 |
| dubrovnik-356 | 10.0 | primary | champion | 0/3 | MISS | 734921.301 | 45 | 2 | 1213 |
| venice-89 | 0.1 | primary | constant | 0/3 | MISS | 308118.009 | 117 | 3 | 270 |
| venice-89 | 0.1 | primary | reduced-ew2 | 3/3 | 0.4457 [0.4447, 0.4577] | 306262.185 | 28 | 0 | 85 |
| venice-89 | 0.1 | primary | gradient-ew2 | 3/3 | 0.4573 [0.4552, 0.4592] | 306212.348 | 29 | 1 | 86 |
| venice-89 | 0.1 | primary | model | 3/3 | 0.4658 [0.4556, 0.4824] | 306212.348 | 29 | 1 | 86 |
| venice-89 | 0.1 | primary | joint | 3/3 | 0.2782 [0.2778, 0.2784] | 305683.972 | 14 | 0 | 74 |
| venice-89 | 0.1 | primary | original | 3/3 | 0.3036 [0.3029, 0.3037] | 306237.788 | 16 | 1 | 75 |
| venice-89 | 0.1 | primary | champion | 3/3 | 0.4427 [0.4419, 0.4428] | 306304.227 | 25 | 1 | 103 |
| venice-89 | 10.0 | primary | reduced-ew2 | 3/3 | 0.2884 [0.2880, 0.2884] | 305845.499 | 14 | 2 | 78 |
| venice-89 | 10.0 | primary | gradient-ew2 | 3/3 | 0.2641 [0.2640, 0.2669] | 305449.596 | 14 | 1 | 70 |
| venice-89 | 10.0 | primary | model | 3/3 | 0.2656 [0.2637, 0.2658] | 305449.596 | 14 | 1 | 70 |
| venice-89 | 10.0 | primary | joint | 3/3 | 0.3419 [0.3395, 0.3598] | 306311.881 | 18 | 0 | 84 |
| venice-89 | 10.0 | primary | original | 3/3 | 0.2837 [0.2832, 0.2838] | 305362.308 | 14 | 1 | 87 |
| venice-89 | 10.0 | primary | champion | 3/3 | 0.2665 [0.2642, 0.2665] | 305564.640 | 14 | 1 | 70 |
| venice-89 | 10.0 | primary | constant | 3/3 | 0.4967 [0.4957, 0.4975] | 305986.204 | 34 | 0 | 80 |

Selection losses are mean log median-time ratios versus champion, with a missed run penalized at4*cap. No transfer outcomes enter selection.

| Arm | Penalized development score, higher is better |
|---|---:|
| champion | 1.0000x |
| constant | 0.3832x |
| gradient-ew2 | 1.3480x |
| joint | 1.5397x |
| model | 1.2314x |
| original | 1.2832x |
| reduced-ew2 | 1.4490x |

These penalty-derived ratios are not measured speedups when a target is missed. Lambda10 is a stress setting, not the global champion initialization; successes against a failed stress comparator do not establish deployment gains.

Leave-family-out selection diagnostic: `{"dubrovnik-356": {"held_log_loss": -1.1545671033028415, "selected": "joint"}, "ladybug-598": {"held_log_loss": 0.592836366338567, "selected": "gradient-ew2"}, "venice-89": {"held_log_loss": -0.10768425009681369, "selected": "joint"}}`.

## Frozen transfer at two quality targets

Initial lambda0.1 for all arms, including Muell. The baseline is the new global eta2 champion, not the older scene-specific initialization map. All targets were registered before this sweep. Transfer scenes were excluded from rule selection, but were familiar from previous research; these are not pristine holdouts.

| Scene | Lambda | Quality | Arm | Hits | Target seconds median [min,max] | Audited cost | Outers | Rejects | Matvecs |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|
| trafalgar-126 | 0.1 | primary | champion | 3/3 | 0.1128 [0.1127, 0.1267] | 105290.456 | 7 | 0 | 195 |
| trafalgar-126 | 0.1 | primary | reduced-ew2 | 3/3 | 0.1333 [0.1326, 0.1388] | 105208.601 | 7 | 0 | 249 |
| trafalgar-126 | 0.1 | primary | joint | 3/3 | 0.1321 [0.1311, 0.1629] | 105177.006 | 7 | 0 | 241 |
| trafalgar-126 | 0.1 | tighter | champion | 3/3 | 0.2289 [0.2282, 0.2293] | 104391.980 | 11 | 0 | 455 |
| trafalgar-126 | 0.1 | tighter | reduced-ew2 | 3/3 | 0.2295 [0.2286, 0.2386] | 104384.049 | 10 | 0 | 464 |
| trafalgar-126 | 0.1 | tighter | joint | 3/3 | 0.1776 [0.1774, 0.1787] | 104505.624 | 9 | 0 | 340 |
| final-1936 | 0.1 | primary | reduced-ew2 | 3/3 | 0.5417 [0.5403, 0.5701] | 5085877.911 | 4 | 0 | 21 |
| final-1936 | 0.1 | primary | joint | 3/3 | 0.5392 [0.5344, 0.5658] | 5096406.924 | 4 | 0 | 20 |
| final-1936 | 0.1 | primary | champion | 3/3 | 0.5084 [0.5004, 0.5107] | 5098339.730 | 4 | 0 | 16 |
| final-1936 | 0.1 | tighter | reduced-ew2 | 3/3 | 0.8490 [0.8488, 0.8492] | 5052905.868 | 5 | 0 | 48 |
| final-1936 | 0.1 | tighter | joint | 3/3 | 0.6512 [0.6388, 0.6592] | 5064523.979 | 5 | 0 | 22 |
| final-1936 | 0.1 | tighter | champion | 3/3 | 0.7480 [0.7341, 0.7846] | 5055268.517 | 5 | 0 | 33 |
| muell-gba146 | 0.1 | primary | joint | 3/3 | 4.4408 [4.4360, 4.4501] | 1943110.306 | 17 | 0 | 1024 |
| muell-gba146 | 0.1 | primary | champion | 3/3 | 4.2345 [4.2294, 4.2432] | 1946467.171 | 16 | 0 | 980 |
| muell-gba146 | 0.1 | primary | reduced-ew2 | 3/3 | 4.5354 [4.5304, 4.5386] | 1945371.454 | 16 | 0 | 1065 |
| muell-gba146 | 0.1 | tighter | joint | 0/3 | MISS | 1936804.443 | 38 | 0 | 2985 |
| muell-gba146 | 0.1 | tighter | champion | 0/3 | MISS | 1936804.450 | 37 | 0 | 2980 |
| muell-gba146 | 0.1 | tighter | reduced-ew2 | 0/3 | MISS | 1936804.487 | 37 | 0 | 2981 |

Largest-scene extension was not run because the medium transfer gate failed. No new Caspar comparison is claimed.

At primary targets, joint requires241 vs195 matvecs on Trafalgar,20 vs16 on Final1936, and1024 vs980 on Muell. Thus the regressions are accompanied by extra linear work, not just the two added reductions. At tighter targets it uses340 vs455 on Trafalgar and22 vs33 on Final1936. All three arms miss the tighter Muell target within12s, so no six-setting aggregate speedup is assigned.

A more targeted follow-up would compare consecutive reduced gradients at the same reference damping and camera metric, using a counterfactual point elimination at the new geometry. That would separate geometric progress from damping changes while retaining camera-space relevance. It requires extra point-factor/RHS work and has NOT been implemented or validated in this pilot.

## Verification and artifacts

192 independently audited endpoints; native solver total 268.717s; maximum relative reported/audited discrepancy 2.53e-10. N3 parent/new off and champion smoke checks preserve work counts and costs within1e-7. CPU tests verify forcing safeguards, retry idempotence, accepted-only damping updates, lambda dependence of the Schur RHS, and the exact block residual identity on a toy system.

Native target times include new reductions and control work; exclude input loading, state export and CPU audits. A hit requires both an actual target event within cap and an original-observation CPU FP64 endpoint at or below target. No interpolation. Same RTX2000 Ada host2237c6528e79; SIMPLE_RADIAL, k2fixed0, half-sum squared original residuals.

[Registered protocol](ba_accuracy_protocol.md). Code: `gpu/ba_accuracy.h`, `bench/build_ba_accuracy.py`, `bench/ba_accuracy_study.py`, `bench/report_ba_accuracy.py`. Full source/build, hashes, manifests, traces and endpoints: `/tmp/prism-ba-accuracy`. Production defaults unchanged.
