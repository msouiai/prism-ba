# Lambda hysteresis priority pilot

Fixed retention fraction 95%; same instrumented binary in both arms. All previously scored candidates remain scored. Per-shift best checkpoint candidates are compared before the existing alpha search. The 95% guarantee applies to menu reduction at that stage, not the final alpha-optimized endpoint or future trajectory.
Venice/Ladybug use 600 outers; final-3068 uses a 100-outer transient/retry-stress cap. No full-convergence claim for that scene. N=3 ranges are not tail bounds.

| Phase | Scene | Arm | N | Iterations median | Cost median [range] | Seconds median [range] | Rejects | Center reversals | Near ties / competitive menus | Preferred switches |
|---|---|---|---:|---:|---|---|---:|---:|---|---:|
| main | ladybug-1197 | control | 3 | 130 | 366350 [366306, 366366] | 27.0717 [26.0545, 31.8566] | 308 | 8 | 86 / 94 | 21 |
| main | ladybug-1197 | hysteresis | 3 | 145 | 366051 [366040, 366289] | 33.438 [32.723, 39.4315] | 322 | 6 | 91 / 97 | 14 |
| main | venice-52 | control | 3 | 600 | 248723 [248702, 248779] | 69.2732 [42.9544, 71.4847] | 0 | 255 | 163 / 179 | 147 |
| main | venice-52 | hysteresis | 3 | 371 | 253974 [253972, 253980] | 34.0911 [32.1587, 36.8894] | 0 | 34 | 180 / 192 | 175 |
| stress | final-3068 | control | 3 | 100 | 1.76266e+06 [1.76192e+06, 1.77037e+06] | 44.6174 [40.5338, 44.6747] | 0 | 6 | 6 / 8 | 5 |
| stress | final-3068 | hysteresis | 3 | 100 | 1.7455e+06 [1.6894e+06, 1.75846e+06] | 36.4566 [36.0558, 37.2065] | 0 | 6 | 10 / 19 | 9 |

## Time to common quality

Targets use the lowest observed endpoint across both arms on each scene times (1+epsilon). Accepted trace times charge untraced solver overhead. An unattained target remains missing.

| Scene | Epsilon | Arm | Reached / runs | Median upper-bound seconds (only if all three reach) |
|---|---:|---|---|---:|
| final-3068 | 0.01 | control | 0/3 | — |
| final-3068 | 0.01 | hysteresis | 1/3 | — |
| final-3068 | 0.001 | control | 0/3 | — |
| final-3068 | 0.001 | hysteresis | 1/3 | — |
| final-3068 | 0.0001 | control | 0/3 | — |
| final-3068 | 0.0001 | hysteresis | 1/3 | — |
| ladybug-1197 | 0.01 | control | 3/3 | 1.53639 |
| ladybug-1197 | 0.01 | hysteresis | 3/3 | 2.05185 |
| ladybug-1197 | 0.001 | control | 3/3 | 22.911 |
| ladybug-1197 | 0.001 | hysteresis | 3/3 | 24.4594 |
| ladybug-1197 | 0.0001 | control | 0/3 | — |
| ladybug-1197 | 0.0001 | hysteresis | 2/3 | — |
| venice-52 | 0.01 | control | 3/3 | 45.6216 |
| venice-52 | 0.01 | hysteresis | 0/3 | — |
| venice-52 | 0.001 | control | 3/3 | 59.6471 |
| venice-52 | 0.001 | hysteresis | 0/3 | — |
| venice-52 | 0.0001 | control | 2/3 | — |
| venice-52 | 0.0001 | hysteresis | 0/3 | — |
