# Safeguard selection and factored FP64 derivatives — 2026-09-09

**New best tested large-scene PRISM candidate: factored FP64 derivatives plus direct directional full-model evaluation.** It reaches the audited target in 14.397 s versus 16.333 s for guarded TR (11.9% less time, N=1). Caspar FP32 remains faster at 7.550 s. The separate safeguard-selection fix resolves a demonstrated candidate-ranking problem but is not a general speed improvement.

## 1. Candidate ranking really can reverse after the point safeguard

At the same captured Final-13682 outer-6 state, compare legacy depth 64 with the projected depth-96 direction:

| Proposal | Raw nonlinear cost | Cost after the same point safeguard |
|---|---:|---:|
| Legacy | 33,812,461.796 | 27,390,471.821 |
| Projected | 35,167,929.568 | **27,232,832.638** |

Only the safeguarded projected proposal meets the target, 27,318,392.35812812. Both safeguarded proposals pass the existing full FP64 GN model/radius acceptance check. The legacy proposal looks better before safeguarding, so the old selection order can discard the useful projected proposal.

The diagnostic run did not change selection. It captured both raw/safeguarded step vectors and the common state. A separate NumPy implementation reconstructed the SO(3), translation, point and intrinsic updates, exported states, and evaluated original BAL observations. All four costs agree with GPU costs within 2.57e-14 relative. Files and hashes are under `diagnostic/capture` and `diagnostic/cpu-pair`.

The opt-in pair candidate evaluates both proposals with identical point safeguards before nonlinear ranking, whenever a projected/legacy pair exists. Each safeguarded proposal must satisfy finite cost, negative slope, Armijo, camera-radius and direct FP64 full-model acceptance. Original raw proposals remain available if their safeguarded version does not improve them. All extra work is charged.

This resolves the captured selection issue, but a better immediate step can lead to a worse later trajectory. On Dubrovnik the pair candidate repeatedly needs approximately 35–36 accepted steps and nine rejections, versus approximately 14 accepted and zero rejections for the incumbent. It remains experimental.

## 2. Reusing stored blocks: fast but insufficiently accurate

A diagnostic reconstructs the GN prediction from the stored camera Hessian, camera/point gradients, float cross blocks and float point Jacobians:

`prediction = -g^T d - 0.5 (dc^T Hcc dc + 2 dc^T W dp + ||B dp||^2)`.

On the seven-outer large diagnostic, this costs roughly **69 ms versus 246 ms** for direct derivative evaluation. However, relative prediction discrepancy reaches **2.25e-6** there and **0.00340** on a small-scene late step. Stored-fragment rounding, different accumulation and cancellation matter. The logged fragment-rounding estimate does not cover all those effects and is not a certified total error bound; it even underestimates measured discrepancy on some steps.

**This approximation is never used for acceptance.** It is retained only as a measured negative result.

## 3. FP64 algebraic alternative

Rather than reconstruct the model from rounded blocks, the new candidate reduces derivative work while retaining FP64 calculations.

For `q = R X`, `P = q + t`, normalized coordinates `u=-Px/Pz`, `v=-Py/Pz`, `s=u²+v²`, and `D=1+k1*s+k2*s²`:

- Assembly factors the Jacobian through the 2x3 derivative of `(f D u, f D v)` with respect to `P`. Camera rotation derivatives use the existing left-rotation convention; translation and point derivatives follow by the chain rule.
- Full-model evaluation computes `delta P = delta omega × q + delta t + R delta X`, then propagates the directional derivative through normalization, radial distortion and focal length. It forms `Jd` directly, without constructing all 24 Jacobian entries first.
- The existing full GN slope/curvature reduction, TR acceptance, solver controller and point factorization remain. No large cache is added and arithmetic precision is not reduced. Existing float fragment storage is unchanged.

These are algebraically equivalent derivatives, not bitwise-identical operation orders. Floating-point reassociation can change trajectories.

### Derivative validation

Two GPU tests total 200,000 derivative comparisons, including positive and mixed-sign depths, arbitrary rotations and both k2-mask settings. Each test also checks 500 directional finite differences of the actual retraction.

Across the tests:

- Maximum gradient norm-relative discrepancy versus the existing generated Jacobian: 1.35e-15.
- Maximum directional discrepancy scaled by absolute reference products: 3.35e-15.
- Maximum normalized finite-difference discrepancy: 1.09e-8.

The factored BA candidate also passes the full small-scene endpoint and CG-curvature audit. These tests establish numerical agreement on sampled cases, not an unrestricted proof about overflow, singular projection depths or every possible input.

## Timing results

All endpoints are independently evaluated against original FP64 BAL observations. Small/medium comparisons use N=3, alternating paired order and no diagnostic instrumentation. Mandatory algorithm checks remain charged.

### Factored FP64 candidate versus guarded TR

| Scene | Guarded TR median | Factored candidate median | Time change | Paired wins |
|---|---:|---:|---:|---:|
| Trafalgar-126 | 0.53984 s | **0.43902 s** | -18.7% | 2/3 |
| Dubrovnik-88 | **0.68320 s** | 0.71987 s | +5.4% | 1/3 |
| Final-1936 | 3.01951 s | **2.54471 s** | -15.7% | 3/3 |

All 18 endpoints qualify. On Dubrovnik, different iteration counts contribute to the regression. Final-1936 keeps the same approximately 179–180 matvecs and eight accepted steps, providing a clearer execution-cost comparison. N=3 is a screening result, not strong statistical certainty.

### Paired-safeguard candidate versus its fresh guarded control

| Scene | Control median | Pair candidate median | Time change |
|---|---:|---:|---:|
| Trafalgar-126 | 0.53635 s | 0.42666 s | -20.5% |
| Dubrovnik-88 | 0.68719 s | 1.36003 s | +97.9% |
| Final-1936 | 2.99400 s | 3.22795 s | +7.8% |

All 18 endpoints qualify. This candidate also includes the earlier FP32-products/reference-ranking machinery; these are comparisons to the incumbent, not an isolated timing attribution to safeguarding alone.

### Fresh Final-13682 comparison, N=1

| Arm | Time to audited target | Audited endpoint cost |
|---|---:|---:|
| Guarded projected TR | 16.33300 s | 27,232,249.360 |
| Pair safeguard/reference ranking | 18.18724 s | 27,233,569.149 |
| **Factored FP64 guarded TR** | **14.39736 s** | 27,232,249.165 |
| **Caspar FP32** | **7.54957 s** | 27,236,094.643 |

All four qualify within the 20-second cap. The pair candidate now reaches the target, resolving the preceding reference-ranking candidate's budget miss, but remains slower than the incumbent. The factored candidate is the best PRISM arm on this run. Caspar FP32 remains approximately 1.91x faster than it.

The effective target is nominal times 1-1e-8. Caspar FP32 retains the fixed 0.1% tighter native stopping margin; credit is given at that stricter crossing only after original-observation endpoint qualification. Timings are solver-native, exclude CLI input loading and retain the documented differences in solver-local setup inclusion. Single-run fluctuations in Caspar versus previous studies are not evidence of a regression/improvement in Caspar itself.

## Profiling explains the gain

Separate seven-outer Nsight attribution, not another benchmark repeat. Compare with the previous guarded-TR profile on this scene:

| Kernel/work | Guarded profile | Factored profile |
|---|---:|---:|
| Assembly, per outer | 356.97 ms | 294.67 ms |
| Full GN model, per outer | 245.59 ms | **26.56 ms** |
| Assembly, seven outers | 2.499 s | 2.063 s |
| Full model, seven outers | 1.719 s | **0.186 s** |

Those two kernel totals save approximately **1.97 s**, consistent with the approximately **1.94 s** uninstrumented improvement. Schur pass 1/2 remain approximately 26.12/21.80 ms; point factorization, diagonal preparation and RHS work are essentially unchanged. The benefit comes from fewer derivative operations, not fewer retries or a cheaper linear operator.

## Reproduction and artifacts

Recommended next comparison baseline: `/workspace/prism-tr-safeguard/factored/prism-tr`. Keep it opt-in pending broader scene validation; this study does not promote it into the production source.

- `gpu/bal_factored_grad.cuh`: factored FP64 Jacobian and directional derivative.
- `bench/build_factored_ba.py`: isolated build from frozen guarded TR; supports a fresh `--output` directory.
- `bench/build_pair_safeguard.py`: paired safeguard experiment; modes `OCA_PAIR_SAFE=1` diagnostic, `2` selection.
- `gpu/block_full_model.cuh`: diagnostic rounded-block prediction only.
- `bench/test_factored_ba.cu`: generated-derivative and finite-difference checks.
- `bench/tr_pair_study.py`, `bench/tr_safeguard_large.py`: bounded paired benchmarks and Caspar comparison.
- `bench/pair_large_diagnostic.py`, `bench/audit_pair_capture.py`: capture and independent reconstruction.
- `bench/profile_factored_ba.py`, `bench/summarize_safeguard_study.py`: attribution and verification.

All artifacts, frozen sources/headers, commands, hashes, logs and states are under `/workspace/prism-tr-safeguard/`. Historical harness labels `double`/`storage` mean incumbent/candidate; the factored candidate computes in FP64.

50 completed BA endpoints were independently audited, plus four captured proposal states. Recorded completed BA native time is 150.353 s, including diagnostic/capture runs; excludes build, input loading, CPU audits, derivative microtests and profiler export. The original production solver was unchanged, GPU work was serialized, and no paused jobs were resumed.
