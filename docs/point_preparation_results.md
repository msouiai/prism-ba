# Point preparation and fresh Caspar comparison

**Verdict:** the combined FP64 fused RHS/diagonal plus guarded-Cholesky candidate is the best tested PRISM option on the two large scenes in this study. Final13682: 12.539s versus factored 14.366s and Caspar FP32 median 8.345s; Final4585: 5.722s while Caspar FP32 misses the 20s budget. Largest-candidate comparisons are N=1; small-panel medians use N=3. Keep the candidate opt-in. These are execution optimizations, not evidence by themselves of a new optimization algorithm.

Current results use independently audited original-double observations, the same scene target for all arms, and solver-native time to the qualified target. Caspar FP32 uses the established 0.1% tighter native stopping margin. This is an empirical guard, not a certified rounding bound. Input loading is excluded; established solver setup-scope differences remain. GPU jobs were serialized. CPU builds and audits could overlap loading.

## Fresh confirmation

| Scene | Arm | Runs/hits | Median qualifying seconds |
|---|---|---:|---:|
| final-13682 | control | 3/3 | 16.329861 |
| final-13682 | factored | 3/3 | 14.356089 |
| final-13682 | caspar32 | 3/3 | 8.344655 |
| final-4585 | control | 1/1 | 7.200038 |
| final-4585 | factored | 1/1 | 6.341708 |
| final-4585 | caspar32 | 1/0 | miss within 20s |

Control is old guarded projected TR; factored changes FP64 derivatives and computes directional Jd directly. Read protocol-amendment.json for the inherited scope-label correction. The frozen binary hashes and flags were correct. Final13682 has N=3, Final4585 N=1. These scenes do not establish universal superiority.

## Fixed-system experiments

The fused observation-owned kernel reads each float W block once for both FP64 RHS correction and the FP64 forward-solve diagonal. It preserves the matrix and arithmetic precision; atomic arrival order can change. This differs from earlier camera-owned/full-backsolve fusion experiments.

```
CHECK fused_rhs relative=2.8233332340027675e-16 max_scaled=2.7560412305345534e-11
CHECK fused_diagonal relative=6.3342575788694137e-17 max_scaled=1.2124255655665243e-14
FUSION rep=0 separate_ms=223.480698 fused_ms=153.628357
FUSION rep=1 separate_ms=223.243484 fused_ms=153.592545
FUSION rep=2 separate_ms=223.615875 fused_ms=153.59053
```

For point factors, accumulate A = B^T B from the same stored float Jacobian in FP64, then form an upper Cholesky factor R. Accept it only with positive finite diagonals, a small reconstruction residual, and the conditioning screen below. Otherwise run the original Givens QR over the observations. Damping continues through the original QR augmentation, preserving the cached undamped factor interface.

`budget = 64 * eps64 * max(1, 2 * track_length)`

`budget * ||R||_F^2 * ||R^-1||_F^2 < 1e-8` and `maxabs(R^T R - A) <= budget * maxabs(A)`.

The Frobenius product bounds the spectral condition number of the computed factor product in exact arithmetic. This is a conservative floating-point screening rule, not an interval-certified error bound. There are no scene-specific thresholds. The normal-equation approach loses QR stability near singularity, hence the mandatory fallback. No point damping policy or nonlinear acceptance rule changes.

The captured system contains all 4,456,117 points / 28,987,644 observations of the initial Final13682 linearization. The extended test compares all factors, actual-RHS inverse actions, and all three inverse columns at damping 10, 0.1, 1e-4, 1e-8. It does not cover every later linearization.

```
TIME qr_ms=208.285599 guarded_ms=33.2194252 fallback=11189 points=4456117 tau=10
CHECK undamped_R relative=1.5973169157620588e-15 max_scaled=4.9498661563409129e-12
DAMPING 10
CHECK damped_R relative=6.8070803151134517e-18 max_scaled=9.2430230136386626e-13
CHECK damped_inverse_actual_rhs relative=1.3201391226480185e-18 max_scaled=5.0047607618695632e-16
CHECK inverse_column relative=3.4383273030353568e-20 max_scaled=1.1102230246251565e-16
CHECK inverse_column relative=1.5109229696689113e-21 max_scaled=2.6020852139652106e-18
CHECK inverse_column relative=3.2217257329198648e-21 max_scaled=2.2204460492503131e-16
DAMPING 0.10000000000000001
CHECK damped_R relative=1.2429398237209768e-16 max_scaled=2.5214806903184643e-12
CHECK damped_inverse_actual_rhs relative=2.2182099625846818e-17 max_scaled=2.0261570199409107e-14
CHECK inverse_column relative=8.695161030171285e-20 max_scaled=3.8612902953954986e-15
CHECK inverse_column relative=7.0518311946379602e-20 max_scaled=1.2212453270876722e-15
CHECK inverse_column relative=9.4098428008827011e-21 max_scaled=2.4790877314581477e-15
DAMPING 0.0001
CHECK damped_R relative=1.4409779365668473e-15 max_scaled=2.9837243786801082e-12
CHECK damped_inverse_actual_rhs relative=6.7862324745822799e-14 max_scaled=7.2145411514423109e-12
CHECK inverse_column relative=4.5029700113604333e-19 max_scaled=1.9644903635682703e-12
CHECK inverse_column relative=1.330788737938523e-18 max_scaled=1.123878767828046e-12
CHECK inverse_column relative=9.0278937044243331e-20 max_scaled=1.9644903635682707e-12
DAMPING 1e-08
CHECK damped_R relative=1.5984919603196385e-15 max_scaled=4.947989908618735e-12
CHECK damped_inverse_actual_rhs relative=1.3671740528692182e-15 max_scaled=7.3133022938698372e-12
CHECK inverse_column relative=1.0082679595778533e-22 max_scaled=6.5042930083629592e-12
CHECK inverse_column relative=3.9771854992941699e-22 max_scaled=7.1740026349660051e-12
CHECK inverse_column relative=2.7350358803076521e-23 max_scaled=7.1737825802856264e-12
```

## fused-small

Historical harness labels: double = factored control; storage = candidate. Candidate manifest gives the exact source/binary.

| Scene | Control seconds | Candidate seconds | Candidate change |
|---|---:|---:|---:|
| trafalgar-126 | 0.482881062 | 0.438316619 | -9.23% |
| dubrovnik-88 | 0.630008179 | 0.606057977 | -3.8% |
| final-1936 | 2.549375463 | 2.437814324 | -4.38% |

## combined-small

Historical harness labels: double = factored control; storage = candidate. Candidate manifest gives the exact source/binary.

| Scene | Control seconds | Candidate seconds | Candidate change |
|---|---:|---:|---:|
| trafalgar-126 | 0.530109808 | 0.501974162 | -5.31% |
| dubrovnik-88 | 0.644868277 | 0.579460163 | -10.14% |
| final-1936 | 2.586001972 | 2.176805209 | -15.82% |

## fused-large

Historical harness labels: double = factored control; storage = candidate. Candidate manifest gives the exact source/binary.

| Scene | Control seconds | Candidate seconds | Candidate change |
|---|---:|---:|---:|
| final-13682 | 14.353673246 | 13.848541681 | -3.52% |

## combined-large

Historical harness labels: double = factored control; storage = candidate. Candidate manifest gives the exact source/binary.

| Scene | Control seconds | Candidate seconds | Candidate change |
|---|---:|---:|---:|
| final-13682 | 14.365794752 | 12.538782777 | -12.72% |

## combined-other

Historical harness labels: double = factored control; storage = candidate. Candidate manifest gives the exact source/binary.

| Scene | Control seconds | Candidate seconds | Candidate change |
|---|---:|---:|---:|
| final-4585 | 6.328351799 | 5.721842602 | -9.58% |

## Numerical edge cases

PASS: scaled well-conditioned blocks, rank-one, rank-two, zero and ill-conditioned blocks; expected QR fallback and factors verified.

## Instrumented attribution

Point preparation fell from 3.113s in the previous factored profile to 1.288s in the new seven-outer profile (about 59% less). Krylov remains 7.220s and assembly 2.071s: those are now the leading costs. The observed 1.825s phase saving agrees with the 1.827s paired native saving. Guarded factors total 0.233s; fused RHS/diagonal totals 0.965s. These measurements attribute this trajectory, not every BA instance.

Separate seven-outer Nsight/profile run; excluded from benchmark ratios. The kernel table and synchronized phase timings are in `combined-profile/final-13682.kernels.csv` and `.log`. Endpoint independently audited.

## Reproduction and limits

Artifacts: `/workspace/prism-tr-point-prep`. Builders, harnesses and report generator: `bench/*point_prep*.py`; candidate kernels: `gpu/point_prep_candidate.cuh`. Frozen candidate builds include the complete source, headers, compiler command and hashes. A self-contained package includes the tested binary, rebuild script, flags and results. Production `gpu/oca_cuda.cu` is unchanged in this study.

Capture v1 failed because it attempted to read the unused optional Bo32 pointer. Capture v2 uses the active float buffer. The initial fused build similarly targeted the unused optional path and was not BA tested; fused-v2 fixes activation. Failed/unused artifacts are retained.

No hardware-counter profiling was attempted again because the driver denied access in the preceding study. The 11 pre-existing paused jobs were not resumed. No push or production-default change was made.

The self-contained package was rebuilt successfully, and its rebuilt binary reached the Trafalgar target with an independent original-double endpoint audit (zero reported/audited cost difference in this smoke run). This additional run is excluded from the comparison medians and the 54 timed-endpoint count.
