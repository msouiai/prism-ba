# Calibrated initialization-noise stress test

The frozen conservative CG marginal-value rule is compared with the sustained eta2 champion. Same binary, initial lambda 0.1, original L2 observations, intrinsics and prior quality targets. This phase changes starting cameras and points only; observation noise and Caspar are not tested. No solver tuning or default changes.

Completed 126 runs: champion 55/63 target hits; conservative 51/63. Both arms hit all three timing repeats on 16/21 matched starting states.

All-case geometric speedup is withheld because at least one matched starting state has a target miss.

**Verdict: retain the existing champion.** The stress test exposes seed-dependent reversals. It does not show catastrophic numerical failure, and many missed endpoints are only a fraction of a percent above target. Nevertheless, there is a substantial same-target slowdown on a case where both arms succeed, independent of how near-target misses are classified.

Venice mild seed 43 is the clearest counterexample: candidate median 0.3544s versus champion 0.2022s, about 75% more time. CG matvecs fall 83 to 74, but outer iterations increase 8 to 20, with zero rejections in both arms. On mild seed 17, the candidate instead improves 0.3062s to 0.1953s. A cheap linear solve is not a reliable predictor of the best nonlinear trajectory.

Dubrovnik mild seed 17 gives another warning: the champion reaches the target in all 3 repeats, median 1.1975s with 25 outers/1 reject; the candidate misses all 3 at roughly 0.59% above target, with 74 outers/17 rejects. The small error gap should not be described as a catastrophic quality regression, but the extra outer work and rejection storm matter for convergence speed.

Trafalgar retains a 1.1046x speedup at stronger noise, but mild noise reverses the result to 0.9315x. Venice mild averages 1.0059x across seeds, hiding its large per-seed win and loss. The aggregate therefore cannot substitute for the paired-seed tables.

## Input calibration and its limits

Three fixed Gaussian directions per scene (seeds 17,29,43), scaled independently to initial full reprojection RMS ratios 1.10 and 1.50. The same seed direction is shared by the two severity levels. Rotation changes are additive angle-axis coordinates; camera centers and points use Gaussian coordinate changes relative to scene radius. Translation is reconstructed from the perturbed rotation and center. This is not isotropic SO(3) noise.

Calibration uses only the starting objective, never solver outcomes. All observation bytes and intrinsics are unchanged; all 18 serialized variants meet RMS tolerance 1e-6 with zero new observation depth-sign changes. The original objective is unchanged, so the previous targets remain applicable.

Full RMS is a poor proxy for uniform geometric disruption on these data. Trafalgar and Dubrovnik reach the requested cost increase through a few highly sensitive observations while most projected features barely move. Venice has much more distributed image displacement. Therefore this panel measures sensitivity to these particular initializations; it cannot establish robustness to general pose error. The contrast was identified during input calibration before solver measurements and the predeclared panel was retained.

| Scene | Level | Seed | Amplitude | RMS ratio | Projection displacement px: median / p95 / max |
|---|---|---:|---:|---:|---:|
| trafalgar-126 | mild | 17 | 6.16923e-05 | 1.100000 | 0.000345404 / 0.00108888 / 173.26 |
| trafalgar-126 | strong | 17 | 0.000150514 | 1.500000 | 0.000842702 / 0.0026566 / 422.712 |
| trafalgar-126 | mild | 29 | 8.8511e-05 | 1.100000 | 0.000537908 / 0.00157305 / 173.261 |
| trafalgar-126 | strong | 29 | 0.000215944 | 1.500000 | 0.00131236 / 0.00383785 / 422.713 |
| trafalgar-126 | mild | 43 | 3.26758e-05 | 1.100000 | 0.000173498 / 0.000560085 / 173.26 |
| trafalgar-126 | strong | 43 | 7.97208e-05 | 1.500000 | 0.000423292 / 0.00136647 / 422.712 |
| dubrovnik-356 | mild | 17 | 5.72232e-05 | 1.100000 | 0.000211653 / 0.000657985 / 209.305 |
| dubrovnik-356 | strong | 17 | 0.000139611 | 1.500000 | 0.000516381 / 0.00160532 / 510.652 |
| dubrovnik-356 | mild | 29 | 7.17457e-05 | 1.100000 | 0.000256835 / 0.000828246 / 317.666 |
| dubrovnik-356 | strong | 29 | 0.000175041 | 1.500000 | 0.000626613 / 0.00202071 / 775.026 |
| dubrovnik-356 | mild | 43 | 6.48925e-05 | 1.100000 | 0.00023297 / 0.000775314 / 226.191 |
| dubrovnik-356 | strong | 43 | 0.000158322 | 1.500000 | 0.000568391 / 0.00189158 / 551.852 |
| venice-89 | mild | 17 | 0.420518 | 1.100000 | 1.19591 / 3.35963 / 28.8222 |
| venice-89 | strong | 17 | 1.22125 | 1.500000 | 3.47309 / 9.75699 / 83.7042 |
| venice-89 | mild | 29 | 0.501037 | 1.100000 | 1.467 / 5.10612 / 28.0265 |
| venice-89 | strong | 29 | 1.26939 | 1.500000 | 3.7168 / 12.9364 / 71.0068 |
| venice-89 | mild | 43 | 0.491093 | 1.100000 | 1.51413 / 4.79803 / 35.1541 |
| venice-89 | strong | 43 | 1.16821 | 1.500000 | 3.60191 / 11.4139 / 83.6251 |

## Summary by scene and severity

Clean cells have three timing runs per arm; noisy cells have three seeds x three timing runs per arm. The speed column is the geometric mean of paired seed-median time ratios, and is shown only when every run in both arms hits. Noisy seeds are not timing repeats or independent scenes.

| Scene | Level | Champion hits | Conservative hits | Speedup (champion / conservative) |
|---|---|---:|---:|---:|
| trafalgar-126 | clean | 3/3 | 3/3 | 1.1244x |
| trafalgar-126 | mild | 9/9 | 9/9 | 0.9315x |
| trafalgar-126 | strong | 9/9 | 9/9 | 1.1046x |
| dubrovnik-356 | clean | 3/3 | 3/3 | 1.5141x |
| dubrovnik-356 | mild | 8/9 | 3/9 | Withheld: miss |
| dubrovnik-356 | strong | 5/9 | 6/9 | Withheld: miss |
| venice-89 | clean | 3/3 | 3/3 | 0.9974x |
| venice-89 | mild | 9/9 | 9/9 | 1.0059x |
| venice-89 | strong | 6/9 | 6/9 | Withheld: miss |

## Every matched input

Time-to-target median [min,max] uses successful runs only and is marked if any repeat missed. Cost and work are medians over all three runs, including misses. A miss may be an early stall or a cap exit; it is not assigned an invented target time.

| Input | Arm | Hits | Target seconds median [min,max] | Final audited cost | Cost gap to target | Outers | Rejects | Matvecs | Extra stops | Repair fallback runs |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| trafalgar-126-clean | champion | 3/3 | 0.1128 [0.1123, 0.1374] | 105290.457630 | -0.2738% | 7 | 0 | 195 | 0 | 0/3 |
| trafalgar-126-clean | conservative | 3/3 | 0.1003 [0.1002, 0.1018] | 105393.523063 | -0.1762% | 7 | 0 | 164 | 1 | 0/3 |
| trafalgar-126-mild-seed17 | champion | 3/3 | 0.1467 [0.1439, 0.1469] | 105150.245620 | -0.4066% | 8 | 0 | 270 | 0 | 0/3 |
| trafalgar-126-mild-seed17 | conservative | 3/3 | 0.1311 [0.1304, 0.1358] | 105205.619882 | -0.3542% | 8 | 0 | 235 | 3 | 0/3 |
| trafalgar-126-strong-seed17 | champion | 3/3 | 0.1225 [0.1211, 0.1268] | 105439.114362 | -0.1330% | 8 | 0 | 210 | 0 | 0/3 |
| trafalgar-126-strong-seed17 | conservative | 3/3 | 0.1111 [0.1110, 0.1136] | 105523.359959 | -0.0533% | 8 | 0 | 183 | 2 | 0/3 |
| trafalgar-126-mild-seed29 | champion | 3/3 | 0.1100 [0.1099, 0.1114] | 105538.774082 | -0.0387% | 6 | 0 | 188 | 0 | 0/3 |
| trafalgar-126-mild-seed29 | conservative | 3/3 | 0.1320 [0.1238, 0.1456] | 105207.443639 | -0.3525% | 7 | 0 | 227 | 3 | 0/3 |
| trafalgar-126-strong-seed29 | champion | 3/3 | 0.1490 [0.1481, 0.1689] | 105557.068042 | -0.0213% | 8 | 0 | 278 | 0 | 0/3 |
| trafalgar-126-strong-seed29 | conservative | 3/3 | 0.1354 [0.1353, 0.1365] | 104762.882060 | -0.7735% | 9 | 0 | 239 | 4 | 0/3 |
| trafalgar-126-mild-seed43 | champion | 3/3 | 0.1067 [0.1066, 0.1129] | 105347.709266 | -0.2196% | 7 | 0 | 180 | 0 | 0/3 |
| trafalgar-126-mild-seed43 | conservative | 3/3 | 0.1233 [0.1130, 0.1240] | 105199.408081 | -0.3601% | 7 | 0 | 219 | 2 | 0/3 |
| trafalgar-126-strong-seed43 | champion | 3/3 | 0.1483 [0.1475, 0.1643] | 105270.733830 | -0.2925% | 8 | 0 | 272 | 0 | 0/3 |
| trafalgar-126-strong-seed43 | conservative | 3/3 | 0.1334 [0.1319, 0.1374] | 105295.662331 | -0.2689% | 8 | 0 | 234 | 3 | 0/3 |
| dubrovnik-356-clean | champion | 3/3 | 1.0048 [1.0021, 1.0217] | 728616.690368 | -0.3763% | 11 | 0 | 324 | 0 | 0/3 |
| dubrovnik-356-clean | conservative | 3/3 | 0.6637 [0.6584, 0.6638] | 731004.824660 | -0.0498% | 8 | 0 | 207 | 1 | 0/3 |
| dubrovnik-356-mild-seed17 | champion | 3/3 | 1.1975 [1.1922, 1.2323] | 721564.700113 | -1.3406% | 25 | 1 | 181 | 0 | 0/3 |
| dubrovnik-356-mild-seed17 | conservative | 0/3 | MISS | 735679.443285 | +0.5893% | 74 | 17 | 602 | 1 | 0/3 |
| dubrovnik-356-strong-seed17 | champion | 0/3 | MISS | 742430.251257 | +1.5124% | 73 | 20 | 275 | 0 | 0/3 |
| dubrovnik-356-strong-seed17 | conservative | 0/3 | MISS | 738577.001166 | +0.9855% | 78 | 5 | 517 | 1 | 0/3 |
| dubrovnik-356-mild-seed29 | champion | 2/3 | 2.2259 [2.1220, 2.3298] (hits only) | 730574.092120 | -0.1087% | 35 | 2 | 512 | 0 | 0/3 |
| dubrovnik-356-mild-seed29 | conservative | 0/3 | MISS | 732977.611142 | +0.2199% | 60 | 18 | 328 | 1 | 0/3 |
| dubrovnik-356-strong-seed29 | champion | 3/3 | 1.2728 [1.2717, 1.2746] | 729032.220365 | -0.3195% | 29 | 3 | 122 | 0 | 0/3 |
| dubrovnik-356-strong-seed29 | conservative | 3/3 | 1.2699 [1.2690, 1.2703] | 729044.414797 | -0.3179% | 29 | 3 | 122 | 0 | 0/3 |
| dubrovnik-356-mild-seed43 | champion | 3/3 | 0.7124 [0.7117, 0.7133] | 729980.633550 | -0.1899% | 9 | 0 | 218 | 0 | 0/3 |
| dubrovnik-356-mild-seed43 | conservative | 3/3 | 0.6915 [0.6904, 0.6966] | 730081.647793 | -0.1760% | 9 | 0 | 207 | 1 | 0/3 |
| dubrovnik-356-strong-seed43 | champion | 2/3 | 1.6406 [1.3212, 1.9600] (hits only) | 731324.879731 | -0.0061% | 21 | 1 | 571 | 0 | 0/3 |
| dubrovnik-356-strong-seed43 | conservative | 3/3 | 2.4680 [2.4253, 2.7970] | 731356.633619 | -0.0017% | 27 | 0 | 735 | 1 | 0/3 |
| venice-89-clean | champion | 3/3 | 0.4428 [0.4428, 0.4488] | 306304.226590 | -0.0049% | 25 | 1 | 103 | 0 | 0/3 |
| venice-89-clean | conservative | 3/3 | 0.4440 [0.4423, 0.4482] | 306304.226731 | -0.0049% | 25 | 1 | 103 | 0 | 0/3 |
| venice-89-mild-seed17 | champion | 3/3 | 0.3062 [0.3062, 0.3276] | 305824.538307 | -0.1615% | 15 | 0 | 97 | 0 | 0/3 |
| venice-89-mild-seed17 | conservative | 3/3 | 0.1953 [0.1947, 0.2218] | 305672.347929 | -0.2112% | 9 | 0 | 67 | 2 | 0/3 |
| venice-89-strong-seed17 | champion | 3/3 | 0.4112 [0.4098, 0.4165] | 306209.568281 | -0.0358% | 26 | 0 | 82 | 0 | 0/3 |
| venice-89-strong-seed17 | conservative | 3/3 | 0.4104 [0.4101, 0.4106] | 306209.568280 | -0.0358% | 26 | 0 | 82 | 0 | 0/3 |
| venice-89-mild-seed29 | champion | 3/3 | 0.2383 [0.2377, 0.2573] | 306000.706047 | -0.1040% | 10 | 1 | 81 | 0 | 0/3 |
| venice-89-mild-seed29 | conservative | 3/3 | 0.2095 [0.2094, 0.2387] | 306069.021403 | -0.0817% | 10 | 1 | 54 | 1 | 0/3 |
| venice-89-strong-seed29 | champion | 3/3 | 2.1715 [2.1667, 2.1739] | 306313.577963 | -0.0018% | 152 | 1 | 370 | 0 | 0/3 |
| venice-89-strong-seed29 | conservative | 3/3 | 2.3008 [2.2987, 2.3027] | 306315.055865 | -0.0013% | 162 | 1 | 388 | 1 | 0/3 |
| venice-89-mild-seed43 | champion | 3/3 | 0.2022 [0.2020, 0.2027] | 306286.422730 | -0.0107% | 8 | 0 | 83 | 0 | 0/3 |
| venice-89-mild-seed43 | conservative | 3/3 | 0.3544 [0.3536, 0.3547] | 306256.130495 | -0.0206% | 20 | 0 | 74 | 1 | 0/3 |
| venice-89-strong-seed43 | champion | 0/3 | MISS | 306789.345223 | +0.1535% | 284 | 3 | 669 | 0 | 0/3 |
| venice-89-strong-seed43 | conservative | 0/3 | MISS | 306770.294428 | +0.1473% | 284 | 3 | 669 | 1 | 0/3 |

## Verification and reproducibility

All 126 original-observation FP64 endpoint audits passed; maximum relative discrepancy 7.44e-15. Maximum native/calibrated initial-cost discrepancy 4.44e-15. Native solver work: 138.340s. Candidate extra stops across 63 runs: 88; repair disabled it on 0 runs.

All timings are native solve times on host2237c6528e79, RTX2000 Ada, with locally serialized GPU runs. Input generation, loading/export and independent CPU audits are outside target time. A hit requires an actual TARGET event within 4s and an audited endpoint no greater than the fixed target. Arms are interleaved, with three timing repeats per identical input. No diagnostic GPU probes or learning logs were enabled.

[Registered protocol](cg_value_noise_protocol.md). Input builder/runner: `bench/cg_value_noise.py`; reporter: `bench/report_cg_value_noise.py`. Exact inputs, manifests, logs, traces and endpoint states: `/tmp/prism-cg-value-noise/`. Compact durable source/binary/trace package: `/workspace/prism-cg-value-noise-evidence.tar.xz`; raw inputs/endpoints remain under /tmp. Input seeds, amplitudes, original hashes and generator source permit reconstruction of the perturbations.
