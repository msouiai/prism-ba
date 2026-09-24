# Ceres setup sensitivity on Final3068

This is a separate comparator screen, not a replacement of the original registered Ceres results. The original Eta2 champion and target are unchanged.

Fixed target: 1744796.9841897595. Complete records: 15/15. N=3 per arm; 600 iterations and 60 native seconds.

| Arm | Completed | Valid | Hits | Endpoint median [range] | Full solve median [range], s | Conditional crossing median [range], s |
|---|---:|---:|---:|---:|---:|---:|
| control | 3/3 | 3 | 0 | 2,183,295.459 [2,183,295.459, 2,183,295.461] | 11.273 [10.545, 11.474] | — |
| normalize | 3/3 | 3 | 0 | 1,930,209.408 [1,930,209.397, 1,930,209.422] | 10.874 [10.834, 12.115] | — |
| strict_stop | 3/3 | 3 | 0 | 1,822,254.768 [1,822,196.209, 1,822,280.095] | 60.906 [60.887, 60.969] | — |
| normalize_strict | 3/3 | 3 | 0 | 1,813,919.574 [1,813,901.853, 1,814,053.156] | 60.734 [60.546, 60.763] | — |
| normalize_strict_eta01 | 3/3 | 3 | 0 | 1,810,675.541 [1,810,164.003, 1,811,893.132] | 60.825 [60.291, 60.863] | — |

All arms use LM / ITERATIVE_SCHUR / SCHUR_JACOBI, radius 10000 and eight threads. control reproduces the old minimal options. normalize changes world coordinates by a similarity; strict_stop sets gradient, function and parameter stopping tolerances to 1e-16; normalize_strict combines them; normalize_strict_eta01 also uses inner eta=.01 instead of .1.

Normalization preserves the intended reprojection objective, as checked before solving and after converting endpoints back to original coordinates. It can still change damping, conditioning, numerical errors and the parameter-norm stopping test. It is not a pure stopping intervention. Stricter tolerances and inner accuracy are likewise kept as separately labeled arms.

The three new control runs must reproduce the old LM endpoint regime to within .1% before other arms start. See control-validation.json. The native target callback uses accepted states only, and successful endpoints are independently rescored against original observations in FP64. A target event after the 60-second allowance does not count as a hit.

The [Ceres 2.2 BAL example](https://github.com/ceres-solver/ceres-solver/blob/2.2.0/examples/bundle_adjuster.cc) motivated this screen. These five settings do not establish globally optimal tuning of Ceres. The screen was registered after the primary Final3068 stage; there is no held-out baseline-selection claim.

Reproduction and provenance: PROTOCOL.md, registration.json, run.py, build-manifest.json, evidence/. Independent verification of exported states and the frozen Ceres shared-library dependencies: audit.py and audit.json after completion.
