# Fixed-Schur-system Krylov audit

A diagnostic executable captures the actual operator, RHS and five shifts at an outer iteration. Both methods solve those same equations. Shared recurrence and independent CG each stop at requested relative residual, with a 2,048-iteration cap. True residual checks and solution export occur outside timing. Independent solves can stop each shift separately; the shared sweep follows the seed system.
Each captured system has N=3 alternating-order repeats. A speed ratio is reported only if every solve meets the true residual target within 1% numerical slack and has no detected nonpositive curvature. Different snapshots are not repetitions of one operator. No nonlinear speedup follows from this microbenchmark alone.

| Scene | Outer | Tolerance | N shared/independent | Shared/independent matvec medians | Shared/independent seconds medians | Independent/shared time | Max true residual shared/independent |
|---|---:|---:|---|---|---|---|---|
| venice-52 | 0 | 0.0001 | 3/3 | 26/45 | 0.026458/0.044674 | 1.688x | 8.55e-05/8.55e-05 |
| venice-52 | 0 | 1e-06 | 3/3 | 40/68 | 0.040597/0.067437 | 1.661x | 9.73e-07/9.73e-07 |
| venice-52 | 5 | 0.0001 | 3/3 | 2048/4685 | 2.077864/4.642073 | accuracy/curvature gate failed | 0.00122/0.00114 |
| venice-52 | 5 | 1e-06 | 3/3 | 2048/6105 | 2.077444/6.056663 | accuracy/curvature gate failed | 0.00207/0.00197 |
| ladybug-1197 | 0 | 0.0001 | 3/3 | 28/47 | 0.040843/0.067313 | 1.648x | 7.51e-05/9.82e-05 |
| ladybug-1197 | 0 | 1e-06 | 3/3 | 44/73 | 0.064114/0.104536 | 1.630x | 9.53e-07/9.53e-07 |
| ladybug-1197 | 5 | 0.0001 | 3/3 | 1402/2232 | 2.042886/3.192071 | accuracy/curvature gate failed | nonfinite/9.98e-05 |
| ladybug-1197 | 5 | 1e-06 | 3/3 | 2048/3337 | 2.982677/4.772796 | accuracy/curvature gate failed | nonfinite/6.25e-06 |
| final-3068 | 0 | 0.0001 | 3/3 | 29/50 | 0.119373/0.203408 | 1.704x | 8.84e-05/8.84e-05 |
| final-3068 | 0 | 1e-06 | 3/3 | 47/78 | 0.192812/0.317216 | 1.645x | 8.02e-07/8.02e-07 |
| final-3068 | 5 | 0.0001 | 3/3 | 2048/3580 | 8.397450/14.551600 | accuracy/curvature gate failed | nonfinite/0.000553 |
| final-3068 | 5 | 1e-06 | 3/3 | 2048/4468 | 8.396890/18.162034 | accuracy/curvature gate failed | nonfinite/0.000543 |
| final-4585 | 0 | 0.0001 | 3/3 | 27/48 | 0.597388/1.059920 | 1.774x | 9.48e-05/9.48e-05 |
| final-4585 | 0 | 1e-06 | 3/3 | 45/76 | 0.995317/1.678032 | 1.686x | 9.52e-07/9.52e-07 |
| final-4585 | 5 | 0.0001 | 3/3 | 1587/2455 | 35.123735/54.219935 | accuracy/curvature gate failed | nonfinite/9.99e-05 |
| final-4585 | 5 | 1e-06 | 3/3 | 2048/3402 | 45.309364/75.133033 | accuracy/curvature gate failed | nonfinite/1.61e-05 |
