# Thirty further steps: coupled subspace rescue

Completed 2026-09-08. **No tested variant is ready to promote.** This round explains why two mathematically well-defined rescue models fail: raw GN prefers the already-rejected full step, while calibration from that failed step often makes the accepted step too small. Independent camera/point scaling does not reliably cure either problem.

[Derivations, limitations and optimality certificates](subspace_rescue_math.md). Evidence root: `/workspace/prism-subspace-rescue/`. All changes are local, opt-in and off by default.

## Scope and evidence

There were **43 BA runs**, totaling **179.582 seconds of native solver time**: two diagnostic runs, 24 original screening runs, two held-out controls and 15 calibrated screening runs. Of 30 target runs, 18 hit. All exported states passed independent CPU objective audits, with maximum relative discrepancy `4.80e-12`. All accepted-cost monotonicity and evaluation-count checks passed. No large run was launched because the medium gate failed.

The study compares the existing baseline, optimal uniform model scaling, and optimal coupled camera/point model scaling. Fixed one/five-shift medium tests are separate from paired-demand controls. Original bounded backtracking and damping updates remain, including lambda freezing after rescues. Point feedback and the earlier direct-rho correction are disabled. There is at most one extra nonlinear evaluation per rescue search, followed on failure by all eight original dyadic trials.

Each screening cell has one run. Results that never accept a new proposal cannot establish a speedup from that proposal, even when observed timing is lower. Ladybug is particularly variable across these short runs; no best repetition was selected or used to promote a candidate.

## First model: exact GN minimization in the box

For the existing failed direction, compute the two observation-space vectors `J_c*d_c` and `J_p*d_p`. Their five inner products define the exact projected GN quadratic including camera–point coupling. Enumerating interior and boundary stationary points finds its minimum for camera/point scales in `[0,1]^2`. The uniform ablation restricts the two scales to be equal.

**None of 483 proposals was accepted across the 24 screening runs.** The 31 diagnostic models all satisfy the KKT conditions making the full `(1,1)` step a global box optimum, even though its true nonlinear cost failed. This gives a mathematical explanation for the negative result; improving the tiny quadratic solve cannot change that answer.

Selected equal-quality times from the original screen:

| Scene / controller | Baseline | Uniform GN model | Coupled GN model |
|---|---:|---:|---:|
| Dubrovnik-356 / single | 4.733 s | 5.404 s | 5.398 s |
| Dubrovnik-356 / five | 1.616 s | 1.653 s | 1.667 s |
| Dubrovnik-356 / paired | 6.900 s | Miss at 8 s | Miss at 8 s |
| Ladybug-1197 / single | 5.505 s | 3.210 s | 3.037 s |
| Ladybug-1197 / five | Miss at 6 s | Miss at 6 s | Miss at 6 s |
| Ladybug-1197 / paired | 3.314 s | 3.503 s | 3.087 s |

The apparent Ladybug single-shift improvement cannot be attributed to successful new proposals: there were none. Its baseline matvec count was 3,089 here, versus 1,708 in the later baseline run. These are short, numerically sensitive trajectories; neither equal flags nor no successful proposal implies bitwise-identical floating-point execution.

Ladybug-49 had no calls in its 40-iteration control. Venice-52 had seven calls per candidate arm, no successful proposals, and fixed-work endpoint costs 249,080.937 baseline, 255,482.716 scalar and 252,004.953 coupled. The held-out Trafalgar-126 baseline/box pair also had no calls; it is an inactive control, not validation of an active rescue mechanism. All raw endpoints remain in `summary.json`.

## Recorded amendment: fit the observed nonlinear discrepancy

After the zero-success screen, `amendment.json` redirected the remaining mathematical/ablation work to one calibrated model:

```
q_E(a,b) = q_GN(a,b) + E*max(a,b)^2,
E = max(0, observed_full_step_change - q_GN(1,1)).
```

This model is convex and fits the observed rejected full step when E is positive, but it is not an error bound elsewhere. Splitting the box into two triangles gives another finite exact solve. On the uniform line it reduces to ordinary quadratic interpolation using the current value/slope and rejected full-step value. No penalty factor was tuned by scene. The five-coefficient GPU pass is unchanged.

The calibrated screen accepted **479 of 480 proposals**, yet produced poor time-to-quality results:

| Scene / shifts | Baseline | Calibrated scalar | Calibrated coupled |
|---|---:|---:|---:|
| Dubrovnik-356 / one | **4.738 s** | Miss at 8 s | Miss at 8 s |
| Dubrovnik-356 / five | **1.617 s** | Miss at 8 s | Miss at 8 s |
| Ladybug-1197 / one | **3.199 s** | 5.404 s | 5.376 s |
| Ladybug-1197 / five | Miss at 6 s | Miss at 6 s | Miss at 6 s |

Targets are cost ≤754,100 for Dubrovnik and ≤366,600 for Ladybug. Returned costs for missed cells:

| Scene / shifts | Baseline | Calibrated scalar | Calibrated coupled |
|---|---:|---:|---:|
| Dubrovnik / one | 754,052 | 1,231,347 | 1,231,328 |
| Dubrovnik / five | 752,679 | 764,582 | 764,660 |
| Ladybug / five | 366,978 | 369,289 | 368,310 |

Venice-52 at 40 iterations returned costs 252,349 baseline, 255,906 scalar and 256,931 coupled. Faster fixed-work return times for these worse endpoints are not equal-quality speedups. No calibrated arm qualified for confirmation/promotion, and no further model constants were tried.

## Why acceptance is misleading here

The coupled single-shift Dubrovnik run accepted all 107 model proposals but ended far above target. Its median camera and point scales were both `0.0001401`, compared with the original eight-step menu's smallest trial `1/256 ≈ 0.003906`. Five-shift median scales were approximately `0.0001037`. Fitting a model to a very poor full step can recommend an excessively cautious interpolation step.

The mathematical certificate is stronger than merely observing similar scales: all 107 single-shift Dubrovnik models satisfy sufficient subgradient conditions proving the calibrated coupled optimum is uniform. Sixty of 61 five-shift models satisfy the same certificate. In this regime, optimizing a second scale cannot improve this surrogate.

On Ladybug, the coupled solver did choose genuinely different block scales: 11/19 single-shift and 39/47 five-shift proposals. The single-shift variant was still about 68% slower than its baseline, and the five-shift variant still missed. Thus the failure is not entirely explained by the optimum lying on the uniform line.

Tiny accepted proposals short-circuit the original fallback and its possible rejection-driven damping changes. They also retain the rescued-step lambda freeze. Armijo acceptance proves sufficient decrease proportional to the proposed slope; it does not guarantee substantial progress per second or per iteration.

The extra model pass contributed 1.146 seconds of the 8.058-second single-shift Dubrovnik miss. Eliminating that overhead would not make its endpoint reach the target. For five-shift Ladybug, backtracking evaluations fell from 361 to 47 and rejected attempts from 40 to 17, but final cost worsened. Fewer retries and near-perfect proposal acceptance are therefore inadequate selection metrics.

## Implementation and validation

- `gpu/subspace_box.h`: normalized long-double host enumeration for raw and calibrated convex models; finite/descent checks and bounded coefficient safeguards.
- `gpu/subspace_model.cuh`: one observation pass for the five projected coefficients; 40-byte persistent device buffer, no new per-observation or full-step buffer.
- `gpu/oca_cuda.cu`: opt-in `OCA_SUBSPACE_RESCUE` modes 1=raw scalar, 2=raw box, 3=audit, 4=calibrated scalar, 5=calibrated box. Original mode 0 remains the default.
- Raw host tests: 2,003 models, projected KKT residual at most `1.12e-16`, scalar dominance, 40,060 random feasible comparisons, singular/opposite/anisotropic/zero cases and wide coefficient scales.
- Calibrated host tests: 2,002 models, nonsmooth projected-subgradient residual at most `2.23e-16`, scalar dominance and 40,040 random feasible comparisons. An explicit nonlinear counterexample verifies why exact GN minimization can fail actual cost.
- GPU coefficients: 12 independent finite-difference cases including separate camera/point scaling, k2 masking and partial blocks; maximum normalized discrepancy `4.80e-10`. Compute Sanitizer: zero errors. The calibrated amendment changes only the host model solve/integration; its GPU coefficient kernel is identical to the tested kernel.
- Four runtime compatibility checks reject point feedback, direct-rho correction, alternative backtracking policy and replay combinations. Paired-demand fallback retains the winning vector and rescued status; no allowed consumer interprets its placeholder alpha as a uniform point-feedback scale.
- CLI and core library builds pass. Eigen remains an optional test dependency. The runner accounts for the explicit ninth possible rescue evaluation instead of silently using the old eight-evaluation bound.
- Stage plans, binary/data hashes, logs, CSV traces, CPU-audited states and numerical certificates are retained. `prism-v1` is the original-model screen binary and `prism-v2` the calibrated binary. `provenance.json` records final hashes and state/result manifest checks.

The flags remain research options rather than recommendations. All 11 original broad jobs remain paused. No GitHub publication or new Caspar comparison was performed.

## Thirty-step completion ledger

| Steps | Completed work |
|---|---|
| 1–2 | Prior large failure retained; primary subspace/LM context checked without borrowing an inapplicable theorem. |
| 3–9 | Projected model, coupling bound, box minimizer, singular cases, scalar dominance, nonlinear acceptance and fallback budget derived. |
| 10–15 | Independent host optimality tests; GPU coefficients/finite differences/memory checks; opt-in integration and compatibility/fallback review. |
| 16–18 | Two diagnostic scenes, scalar control, frozen screen protocol and binaries. |
| 19–25 | Small inactive/contradictory cases; medium single/five factorial; paired-demand controls; original candidates rejected. |
| 26 | Held-out Trafalgar control, correctly identified as inactive. |
| 27 | Failed large gate; recorded amendment to derive and independently test a calibrated convex model instead. |
| 28 | Fifteen-run calibrated scalar/coupled screen and cost attribution; saved-model KKT certificates explain full/uniform optima. |
| 29–30 | CPU/provenance/budget/build/paused-process audits and complete math/results reporting. |

## Decision and next mathematical question

Reject these candidate policies for promotion. Keep their coefficient calculation and saved-model certificates as diagnostic tools. This round supplies no new general speedup or novelty claim.

The next useful question is whether model error measured at a rejected full step is representative at the scale where useful progress is possible. Investigate that on a few saved states/directions, with actual cost measurements at modest scales and separately along the camera/point directions. One full-step discrepancy cannot identify independent block nonlinear curvature. Establish what those measurements predict before adding another global damping or minimum-step heuristic, or paying for a larger benchmark sweep.
