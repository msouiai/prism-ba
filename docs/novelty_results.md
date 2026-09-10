# Prism novelty study: retained measurements

LOCAL STUDY IN PROGRESS: comparisons are preliminary.
Three repeats are required for a cell-level comparison. Incomplete experiments remain visible; this file is a progress report until all declared cells finish.
All costs use the original double-observation SIMPLE_RADIAL objective. Prism reports GPU-fp64 costs with an independent initial-cost check; its endpoints are not separately CPU-audited. Caspar-fp32 and Ceres endpoints are CPU-fp64 evaluations of returned states. Caspar native float traces do not certify crossings.
Ceres is CPU (8 threads); Prism and Caspar use the GPU. Do not interpret Ceres timings as an equal-GPU kernel comparison. GPU/CPU runs share the benchmark lock.
Development, evaluation and perturbed instances are separate experiments. Different perturbation seeds are different instances, not extra timing repeats.

| Experiment | Scene | Arm | Completed / failed / planned | Cost median [range] | Solver seconds median [range] | Rejects / matvecs / scored medians |
|---|---|---|---|---:|---:|---|
| ablation-development | venice-52 | A-single | 3 / 0 / 3 | 247,437 [245,824, 248,943] | 50.9422 [50.1328, 61.2011] | 37 / 45574 / 4856 |
| ablation-development | venice-52 | B-single-guarded | 3 / 0 / 3 | 253,491 [253,434, 253,563] | 42.2963 [35.5774, 44.4292] | 0 / 32932 / 4869 |
| ablation-development | venice-52 | C-multi | 3 / 0 / 3 | 254,276 [254,267, 254,341] | 30.1288 [28.1871, 35.7617] | 12 / 24444 / 5477 |
| ablation-development | venice-52 | D-multi-guarded | 3 / 0 / 3 | 248,716 [248,687, 248,740] | 31.9541 [30.706, 39.2794] | 0 / 24893 / 5577 |
| ablation-development | ladybug-1197 | A-single | 3 / 0 / 3 | 366,256 [366,245, 366,323] | 11.7789 [10.9322, 12.8331] | 22 / 6771 / 1050 |
| ablation-development | ladybug-1197 | B-single-guarded | 3 / 0 / 3 | 366,129 [366,121, 366,164] | 15.5262 [12.2863, 15.699] | 0 / 8723 / 1490 |
| ablation-development | ladybug-1197 | C-multi | 3 / 0 / 3 | 366,334 [366,097, 366,340] | 30.0899 [29.373, 31.3485] | 325 / 17009 / 3823 |
| ablation-development | ladybug-1197 | D-multi-guarded | 3 / 0 / 3 | 366,362 [366,050, 366,375] | 24.7532 [22.774, 25.5111] | 242 / 13754 / 3184 |
| ablation-development | final-3068 | A-single | 3 / 0 / 3 | 2.29109e+06 [2.29109e+06, 2.29109e+06] | 13.0394 [12.9481, 13.1372] | 143 / 2349 / 458 |
| ablation-development | final-3068 | B-single-guarded | 3 / 0 / 3 | 1.68931e+06 [1.68921e+06, 1.69969e+06] | 242.247 [238.882, 245.943] | 18 / 50830 / 6459 |
| ablation-development | final-3068 | C-multi | 3 / 0 / 3 | 1.6935e+06 [1.68598e+06, 1.69694e+06] | 151.795 [134.097, 161.959] | 73 / 31083 / 6710 |
| ablation-development | final-3068 | D-multi-guarded | 3 / 0 / 3 | 1.68547e+06 [1.68065e+06, 1.69169e+06] | 254.297 [236.973, 270.06] | 13 / 51440 / 11113 |
| ablation-development | final-4585 | A-single | 3 / 0 / 3 | 7.67684e+06 [7.67684e+06, 7.67684e+06] | 1,880.53 [1,880.39, 1,880.88] | 4703 / 62934 / 12228 |
| ablation-development | final-4585 | B-single-guarded | 3 / 0 / 3 | 6.75722e+06 [6.74268e+06, 7.99269e+06] | 459.753 [395.764, 828.437] | 1196 / 10157 / 8329 |
| ablation-development | final-4585 | C-multi | 3 / 0 / 3 | 1.07248e+07 [1.07248e+07, 1.07248e+07] | 872.027 [871.9, 873.855] | 4774 / 13827 / 22224 |
| ablation-development | final-4585 | D-multi-guarded | 3 / 0 / 3 | 8.05825e+06 [8.03503e+06, 8.06189e+06] | 1,027.69 [981.709, 1,064.4] | 3148 / 20924 / 50527 |
| ablation-evaluation | ladybug-598 | A-single | 3 / 0 / 3 | 179,956 [179,952, 179,956] | 2.69469 [2.67633, 3.04621] | 2 / 2596 / 497 |
| ablation-evaluation | ladybug-598 | B-single-guarded | 3 / 0 / 3 | 179,952 [179,952, 179,952] | 3.1962 [3.1554, 3.2845] | 0 / 3083 / 570 |
| ablation-evaluation | ladybug-598 | C-multi | 3 / 0 / 3 | 180,416 [180,414, 180,417] | 2.80413 [2.73473, 3.26585] | 6 / 2596 / 664 |
| ablation-evaluation | ladybug-598 | D-multi-guarded | 3 / 0 / 3 | 180,210 [180,209, 180,211] | 3.28457 [3.23469, 3.5716] | 0 / 3086 / 735 |
| ablation-evaluation | trafalgar-126 | A-single | 3 / 0 / 3 | 104,215 [104,151, 104,216] | 9.37322 [8.48195, 10.4697] | 0 / 17670 / 2087 |
| ablation-evaluation | trafalgar-126 | B-single-guarded | 3 / 0 / 3 | 104,211 [104,148, 104,223] | 6.09822 [4.86692, 6.74997] | 0 / 11045 / 1507 |
| ablation-evaluation | trafalgar-126 | C-multi | 3 / 0 / 3 | 103,995 [103,971, 104,140] | 10.1389 [4.41338, 11.1336] | 0 / 17773 / 3509 |
| ablation-evaluation | trafalgar-126 | D-multi-guarded | 3 / 0 / 3 | 104,007 [103,976, 104,105] | 8.06183 [4.30095, 9.8661] | 0 / 13929 / 2766 |
| ablation-evaluation | dubrovnik-173 | A-single | 3 / 0 / 3 | 374,869 [374,868, 374,871] | 12.1016 [10.8408, 13.121] | 109 / 6407 / 815 |
| ablation-evaluation | dubrovnik-173 | B-single-guarded | 3 / 0 / 3 | 374,868 [374,867, 374,915] | 8.58791 [8.54433, 9.75238] | 27 / 4186 / 634 |
| ablation-evaluation | dubrovnik-173 | C-multi | 3 / 0 / 3 | 374,867 [374,867, 374,868] | 13.6983 [13.6023, 16.5052] | 115 / 7081 / 1770 |
| ablation-evaluation | dubrovnik-173 | D-multi-guarded | 3 / 0 / 3 | 374,868 [374,867, 374,932] | 7.38434 [6.93278, 9.39177] | 32 / 3434 / 911 |
| ablation-evaluation | venice-1672 | A-single | 1 / 0 / 3 | 2.17724e+06 [2.17724e+06, 2.17724e+06] | 270.647 [270.647, 270.647] | 81 / 18249 / 3123 |
| ablation-evaluation | venice-1672 | B-single-guarded | 0 / 0 / 3 | — | — | — / — / — |
| ablation-evaluation | venice-1672 | C-multi | 0 / 0 / 3 | — | — | — / — / — |
| ablation-evaluation | venice-1672 | D-multi-guarded | 0 / 0 / 3 | — | — | — / — / — |
| ablation-perturbed | venice-52-seed17 | A-single | 3 / 0 / 3 | 265,642 [265,607, 266,194] | 27.7382 [22.2653, 31.753] | 13 / 23428 / 3591 |
| ablation-perturbed | venice-52-seed17 | B-single-guarded | 3 / 0 / 3 | 255,050 [254,941, 255,067] | 33.2375 [29.8474, 59.3949] | 0 / 28478 / 4025 |
| ablation-perturbed | venice-52-seed17 | C-multi | 3 / 0 / 3 | 255,233 [255,227, 256,497] | 27.6571 [27.3856, 29.9674] | 9 / 22635 / 5013 |
| ablation-perturbed | venice-52-seed17 | D-multi-guarded | 3 / 0 / 3 | 242,664 [242,604, 242,672] | 30.2233 [28.0305, 35.2156] | 0 / 24698 / 5412 |
| ablation-perturbed | venice-52-seed29 | A-single | 3 / 0 / 3 | 267,872 [267,526, 268,065] | 29.9741 [23.3272, 49.0074] | 9 / 25419 / 3963 |
| ablation-perturbed | venice-52-seed29 | B-single-guarded | 3 / 0 / 3 | 254,738 [254,685, 255,300] | 30.5179 [22.3907, 33.1194] | 0 / 25766 / 3998 |
| ablation-perturbed | venice-52-seed29 | C-multi | 3 / 0 / 3 | 249,299 [249,179, 249,755] | 31.0764 [31.0317, 40.651] | 48 / 25463 / 5680 |
| ablation-perturbed | venice-52-seed29 | D-multi-guarded | 3 / 0 / 3 | 246,724 [246,710, 246,745] | 31.9173 [30.7534, 34.9951] | 0 / 26092 / 5764 |
| ablation-perturbed | venice-52-seed43 | A-single | 3 / 0 / 3 | 265,076 [264,972, 265,564] | 27.2155 [21.7584, 44.0523] | 17 / 23185 / 3500 |
| ablation-perturbed | venice-52-seed43 | B-single-guarded | 3 / 0 / 3 | 259,027 [258,411, 260,522] | 73.8594 [54.0355, 80.6469] | 0 / 65600 / 7431 |
| ablation-perturbed | venice-52-seed43 | C-multi | 3 / 0 / 3 | 254,866 [254,831, 254,952] | 30.7778 [25.9038, 31.5466] | 15 / 25077 / 5618 |
| ablation-perturbed | venice-52-seed43 | D-multi-guarded | 3 / 0 / 3 | 246,910 [246,865, 246,926] | 27.755 [27.1902, 28.3194] | 0 / 22613 / 5046 |
| ablation-perturbed | final-3068-seed17 | A-single | 1 / 0 / 3 | 1.68736e+06 [1.68736e+06, 1.68736e+06] | 178.129 [178.129, 178.129] | 319 / 38096 / 4188 |
| ablation-perturbed | final-3068-seed17 | B-single-guarded | 0 / 0 / 3 | — | — | — / — / — |
| ablation-perturbed | final-3068-seed17 | C-multi | 0 / 0 / 3 | — | — | — / — / — |
| ablation-perturbed | final-3068-seed17 | D-multi-guarded | 0 / 0 / 3 | — | — | — / — / — |
| ablation-perturbed | final-3068-seed29 | A-single | 0 / 0 / 3 | — | — | — / — / — |
| ablation-perturbed | final-3068-seed29 | B-single-guarded | 0 / 0 / 3 | — | — | — / — / — |
| ablation-perturbed | final-3068-seed29 | C-multi | 0 / 0 / 3 | — | — | — / — / — |
| ablation-perturbed | final-3068-seed29 | D-multi-guarded | 0 / 0 / 3 | — | — | — / — / — |
| ablation-perturbed | final-3068-seed43 | A-single | 0 / 0 / 3 | — | — | — / — / — |
| ablation-perturbed | final-3068-seed43 | B-single-guarded | 0 / 0 / 3 | — | — | — / — / — |
| ablation-perturbed | final-3068-seed43 | C-multi | 0 / 0 / 3 | — | — | — / — / — |
| ablation-perturbed | final-3068-seed43 | D-multi-guarded | 0 / 0 / 3 | — | — | — / — / — |
| caspar32-development | venice-52 | caspar32-default-200 | 3 / 0 / 3 | 280,005 [279,284, 281,333] | 1.68025 [1.47678, 1.92975] | — / — / — |
| caspar32-development | venice-52 | caspar32-default-2000 | 3 / 0 / 3 | 276,647 [276,449, 278,015] | 7.66743 [7.64679, 8.02231] | — / — / — |
| caspar32-development | venice-52 | caspar32-paper-200 | 3 / 0 / 3 | 274,087 [271,621, 275,051] | 1.81682 [1.63611, 1.83536] | — / — / — |
| caspar32-development | venice-52 | caspar32-paper-2000 | 3 / 0 / 3 | 270,143 [260,968, 270,925] | 4.08584 [2.64973, 19.6699] | — / — / — |
| caspar32-development | ladybug-1197 | caspar32-default-200 | 3 / 0 / 3 | 484,816 [484,816, 484,817] | 0.293528 [0.292214, 0.295112] | — / — / — |
| caspar32-development | ladybug-1197 | caspar32-default-2000 | 3 / 0 / 3 | 484,815 [484,814, 484,815] | 0.292291 [0.283357, 0.296277] | — / — / — |
| caspar32-development | ladybug-1197 | caspar32-paper-200 | 3 / 0 / 3 | 971,531 [971,528, 971,541] | 0.21429 [0.206489, 0.217167] | — / — / — |
| caspar32-development | ladybug-1197 | caspar32-paper-2000 | 3 / 0 / 3 | 971,533 [971,526, 971,549] | 0.212302 [0.206048, 0.221247] | — / — / — |
| caspar32-development | final-3068 | caspar32-default-200 | 3 / 0 / 3 | 2.64687e+06 [2.63605e+06, 2.64943e+06] | 0.831559 [0.670087, 2.35007] | — / — / — |
| caspar32-development | final-3068 | caspar32-default-2000 | 3 / 0 / 3 | 2.64605e+06 [2.64583e+06, 2.64927e+06] | 0.696028 [0.672604, 0.719633] | — / — / — |
| caspar32-development | final-3068 | caspar32-paper-200 | 3 / 0 / 3 | 2.03954e+06 [2.03189e+06, 2.04366e+06] | 0.771995 [0.745947, 1.01706] | — / — / — |
| caspar32-development | final-3068 | caspar32-paper-2000 | 3 / 0 / 3 | 2.04158e+06 [2.03956e+06, 2.04365e+06] | 0.760548 [0.748022, 0.83712] | — / — / — |
| caspar32-development | final-4585 | caspar32-default-200 | 1 / 0 / 3 | 1.10356e+07 [1.10356e+07, 1.10356e+07] | 13.972 [13.972, 13.972] | — / — / — |
| caspar32-development | final-4585 | caspar32-default-2000 | 1 / 0 / 3 | 8.94201e+06 [8.94201e+06, 8.94201e+06] | 128.39 [128.39, 128.39] | — / — / — |
| caspar32-development | final-4585 | caspar32-paper-200 | 1 / 0 / 3 | 1.69321e+07 [1.69321e+07, 1.69321e+07] | 9.59128 [9.59128, 9.59128] | — / — / — |
| caspar32-development | final-4585 | caspar32-paper-2000 | 2 / 0 / 3 | 1.58006e+07 [1.54203e+07, 1.6181e+07] | 53.6822 [20.3752, 86.9892] | — / — / — |
| caspar32-evaluation | ladybug-598 | caspar32-default-200 | 3 / 0 / 3 | 196,926 [186,029, 241,350] | 0.142542 [0.136658, 0.148485] | — / — / — |
| caspar32-evaluation | ladybug-598 | caspar32-default-2000 | 3 / 0 / 3 | 193,758 [183,731, 202,092] | 0.115868 [0.0980752, 0.211923] | — / — / — |
| caspar32-evaluation | trafalgar-126 | caspar32-default-200 | 3 / 0 / 3 | 106,708 [106,636, 106,730] | 0.93169 [0.930103, 0.931774] | — / — / — |
| caspar32-evaluation | trafalgar-126 | caspar32-default-2000 | 3 / 0 / 3 | 104,570 [104,537, 104,613] | 8.78178 [7.86711, 8.80493] | — / — / — |
| caspar32-evaluation | dubrovnik-173 | caspar32-default-200 | 3 / 0 / 3 | 378,987 [378,914, 378,991] | 3.26755 [3.26367, 3.27779] | — / — / — |
| caspar32-evaluation | dubrovnik-173 | caspar32-default-2000 | 3 / 0 / 3 | 377,855 [377,841, 377,863] | 11.8778 [11.2629, 12.3059] | — / — / — |
| caspar32-evaluation | venice-1672 | caspar32-default-200 | 0 / 0 / 3 | — | — | — / — / — |
| caspar32-evaluation | venice-1672 | caspar32-default-2000 | 0 / 0 / 3 | — | — | — / — / — |
| caspar32-evaluation | final-3068 | caspar32-default-200 | 0 / 0 / 3 | — | — | — / — / — |
| caspar32-evaluation | final-3068 | caspar32-default-2000 | 0 / 0 / 3 | — | — | — / — / — |
| caspar32-evaluation | final-4585 | caspar32-default-200 | 0 / 0 / 3 | — | — | — / — / — |
| caspar32-evaluation | final-4585 | caspar32-default-2000 | 0 / 0 / 3 | — | — | — / — / — |
| ceres-evaluation | ladybug-598 | ceres-lm-10000-600 | 3 / 0 / 3 | 180,316 [180,154, 180,402] | 23.9121 [13.5106, 30.1985] | — / — / — |
| ceres-evaluation | ladybug-598 | ceres-dogleg-10000-600 | 3 / 0 / 3 | 180,211 [180,211, 180,212] | 8.74088 [7.95374, 10.7565] | — / — / — |
| ceres-evaluation | trafalgar-126 | ceres-lm-10000-600 | 3 / 0 / 3 | 104,122 [104,121, 104,124] | 13.062 [11.5797, 15.156] | — / — / — |
| ceres-evaluation | trafalgar-126 | ceres-dogleg-10000-600 | 3 / 0 / 3 | 104,107 [104,107, 104,107] | 1.49957 [1.48058, 1.54727] | — / — / — |
| ceres-evaluation | dubrovnik-173 | ceres-lm-10000-600 | 2 / 0 / 3 | 377,744 [377,737, 377,750] | 25.7157 [21.0233, 30.408] | — / — / — |
| ceres-evaluation | dubrovnik-173 | ceres-dogleg-10000-600 | 2 / 0 / 3 | 374,922 [374,922, 374,922] | 10.3158 [9.42168, 11.2099] | — / — / — |
| ceres-evaluation | venice-1672 | ceres-lm-10000-600 | 0 / 0 / 3 | — | — | — / — / — |
| ceres-evaluation | venice-1672 | ceres-dogleg-10000-600 | 0 / 0 / 3 | — | — | — / — / — |
| ceres-evaluation | final-3068 | ceres-lm-10000-600 | 0 / 0 / 3 | — | — | — / — / — |
| ceres-evaluation | final-3068 | ceres-dogleg-10000-600 | 0 / 0 / 3 | — | — | — / — / — |
| ceres-evaluation | final-4585 | ceres-lm-10000-600 | 0 / 0 / 3 | — | — | — / — / — |
| ceres-evaluation | final-4585 | ceres-dogleg-10000-600 | 0 / 0 / 3 | — | — | — / — / — |
| ceres-tuning | venice-52 | ceres-lm-10000-600 | 3 / 0 / 3 | 241,327 [241,327, 241,327] | 36.7203 [29.0874, 37.2605] | — / — / — |
| ceres-tuning | venice-52 | ceres-lm-1-600 | 3 / 0 / 3 | 242,329 [242,329, 242,329] | 37.1807 [35.2866, 40.7624] | — / — / — |
| ceres-tuning | venice-52 | ceres-dogleg-10000-600 | 3 / 0 / 3 | 254,752 [254,752, 254,753] | 14.6834 [12.4247, 15.36] | — / — / — |
| ceres-tuning | venice-52 | ceres-dogleg-1-600 | 3 / 0 / 3 | 260,975 [260,975, 260,975] | 14.0521 [11.3743, 14.2822] | — / — / — |
| ceres-tuning | ladybug-1197 | ceres-lm-10000-600 | 3 / 0 / 3 | 368,001 [367,996, 368,002] | 17.3545 [16.6631, 22.5504] | — / — / — |
| ceres-tuning | ladybug-1197 | ceres-lm-1-600 | 3 / 0 / 3 | 367,280 [367,278, 367,283] | 18.2813 [16.3134, 20.1671] | — / — / — |
| ceres-tuning | ladybug-1197 | ceres-dogleg-10000-600 | 3 / 0 / 3 | 366,743 [366,641, 366,746] | 25.9352 [23.2365, 28.8802] | — / — / — |
| ceres-tuning | ladybug-1197 | ceres-dogleg-1-600 | 3 / 0 / 3 | 366,841 [366,745, 366,843] | 42.2534 [39.9781, 46.2546] | — / — / — |

## Does multi-shift help beyond the same safeguard?

D versus B: negative cost/time changes favor five shifts with safeguard. A resolved cost difference needs three successful repeats per arm, a median gap >0.15%, and disjoint observed ranges. Ranges are not tail bounds.

| Experiment | Scene | D/B cost change | D/B wall change | Cost evidence |
|---|---|---:|---:|---|
| ablation-development | final-3068 | -0.2278% | +4.97% | not resolved |
| ablation-development | final-4585 | +19.2540% | +123.53% | resolved |
| ablation-development | ladybug-1197 | +0.0636% | +59.43% | not resolved |
| ablation-development | venice-52 | -1.8837% | -24.45% | resolved |
| ablation-evaluation | dubrovnik-173 | -0.0000% | -14.01% | not resolved |
| ablation-evaluation | ladybug-598 | +0.1431% | +2.76% | not resolved |
| ablation-evaluation | trafalgar-126 | -0.1958% | +32.20% | resolved |
| ablation-evaluation | venice-1672 | — | — | incomplete |
| ablation-perturbed | final-3068-seed17 | — | — | incomplete |
| ablation-perturbed | final-3068-seed29 | — | — | incomplete |
| ablation-perturbed | final-3068-seed43 | — | — | incomplete |
| ablation-perturbed | venice-52-seed17 | -4.8567% | -9.07% | resolved |
| ablation-perturbed | venice-52-seed29 | -3.1462% | +4.59% | resolved |
| ablation-perturbed | venice-52-seed43 | -4.6777% | -62.42% | resolved |

## Fixed quality targets

For each input instance, Fbest is the lowest reported fp64 endpoint among the frozen measured arms. It is an empirical reference, not an optimum. Targets are Fbest*(1+epsilon), epsilon=1%,0.1%,0.01%.
Prism/Ceres crossings charge all untraced solver time before the accepted-state crossing. For Caspar-fp32, only its checked endpoint certifies attainment; the bound is full solver runtime, not a claimed first crossing. Setup-inclusive bounds are additional columns. Missing means no certified attainment in that run.
The machine-readable crossing table retains every repeat: `novelty-crossings.json`.

