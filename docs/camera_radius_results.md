# Three actual radii from a shared camera Krylov subspace

The radius menu has a useful local signal, but no end-to-end win is established. On ten distinct sampled states, selective evaluation chooses the larger radius at five, retains the current radius at three, and finds no acceptable candidate at two. Corrected TR-one remains the measured incumbent: 0.474/0.753 s on Trafalgar126/Dubrovnik88 versus corrected TR-five at 0.683/0.828 s in the [previous matched-width study](camera_tr_width_results.md). These are historical timings, not timings of the new projected solver. No fresh Caspar comparison was run.

## Frozen experiment

Four seven-iteration instrumented owner runs: Trafalgar126 and Dubrovnik88, each under corrected TR-one and TR-five. At outer iterations 0, 3 and 6, construct a fresh depth-64, twice-reorthogonalized Krylov basis from the same frozen equilibrated camera Schur operator and RHS. Point damping, state and scaling are fixed across each capture's radius candidates. These candidates are diagnostic only; the owner resumes its original policy without committing any diagnostic candidate.

There are 12 captures and 36 candidates. The two initial states are repeated across owner widths; they provide ten distinct sampled states, not twelve independent examples. This is a two-scene development experiment, not statistical confirmation.

The old TR-five prototype radially clips several shifted/depth directions to one active radius. Here, with Q orthonormal, H = Qᵀ Sτ Q and bQ = Qᵀ b, solve

```
min_y  0.5 yᵀ H y − bQᵀ y     subject to ||y||₂ ≤ R
R ∈ {Δ/2, Δ, 2Δ}
(H + λI)y = bQ, λ ≥ 0, H + λI positive semidefinite
λ (||y||₂ − R) = 0
```

One eigendecomposition of H serves all three radii. A secular root determines each boundary solution, including explicit singular/indefinite hard-case handling. Reconstruct the camera vector Qy, lift it to physical coordinates, back-substitute points using the same frozen point factors, and score the actual retracted BA state. Acceptance uses the full unregularized GN prediction and actual camera norm. The radius constrains scaled cameras; this is not a joint camera-and-point trust region.

This projected approach follows established [Lanczos trust-region methodology, Gould et al. (1999)](https://www.numerical.rl.ac.uk/media/people/nick-gould/GoulLuciRomaToin99_siopt.pdf). Sharing a projected space across radii is not itself a novelty claim. This implementation uses dense eigendecomposition and full reorthogonalization for diagnosis, rather than an optimized GLTR implementation.

Frozen selective replay rule, set before the runs:

1. Evaluate the current radius. Accept only if actual reduction and full GN prediction are positive, rho ≥ 0.1, and camera norm is feasible.
2. If rejected, evaluate half radius and accept if it passes.
3. If current is accepted with rho > 0.75 and norm ≥ 0.8Δ, evaluate double radius; choose it only if acceptable and lower cost.

At most two nonlinear trials. All three candidates were actually evaluated for diagnosis; the selective policy and its work sums are counterfactual, not measured rollouts.

## Results

Incremental gain below means extra **one-step cost reduction relative to the acceptable current-radius candidate**, not runtime speedup or percent reduction in final cost. Initial states are shown once.

| Scene | Owner | Outer | Selective choice | Extra reduction | Extra reduction / current reduction |
|---|---|---:|---|---:|---:|
| Trafalgar126 | both, same initial state | 0 | 2Δ | 3,512,982 | 54.62% |
| Trafalgar126 | TR-one | 3 | 2Δ | 2,901 | 0.53% |
| Trafalgar126 | TR-one | 6 | Δ | 0 | 0% |
| Trafalgar126 | TR-five | 3 | Δ | 0 | 0% |
| Trafalgar126 | TR-five | 6 | none accepted | 0 | — |
| Dubrovnik88 | both, same initial state | 0 | 2Δ | 6,506,312 | 56.95% |
| Dubrovnik88 | TR-one | 3 | 2Δ | 93,637 | 5.29% |
| Dubrovnik88 | TR-one | 6 | 2Δ | 103 | 0.11% |
| Dubrovnik88 | TR-five | 3 | Δ | 0 | 0% |
| Dubrovnik88 | TR-five | 6 | none accepted | 0 | — |

Across the twelve captures, the rule selects larger at seven, current at three, and none at two; it would use 21 nonlinear trials versus 12 for current alone. Deduplicating the initial states gives five larger selections and 17 trials versus ten. These counts do not demonstrate fewer nonlinear solver iterations or retries.

Five of the ten distinct states give the **same camera vector at current and double radius** (relative distance below 1e-8). The unconstrained solution inside the depth-64 subspace already fits the current radius. Enlarging the feasible set cannot improve that subspace's quadratic optimum. Where larger candidates do differ, both their norms and directions can change; they are not generally collinear copies.

The selective rule misses a useful smaller candidate at Trafalgar/TR-one/outer6: current is acceptable (rho 0.425, gain 2,284.6), but half radius gives gain 3,996.8 with rho 0.841. A rejection-only contraction test does not find every useful smaller step. This is recorded, not used to tune the frozen policy after seeing results.

## Why radius diversity still fails later

Two captures have no acceptable radius:

- Trafalgar/TR-five/outer6: all three radii produce the same interior step, norm 0.189Δ. Its nonlinear cost increases by approximately 166,470 despite positive full GN prediction. Halving Δ leaves the rejected step feasible and therefore unchanged. The candidate must be constrained below its actual norm to change it within this fixed subspace.
- Dubrovnik/TR-five/outer6: current and double coincide and increase cost by approximately 18,082. Halving becomes active but increases cost by approximately 1,490,632. A smaller camera radius does not guarantee smaller nonlinear error, particularly with point back-substitution outside that radius constraint.

Depth-64 projected KKT residuals are tiny, but **full camera-space relative residuals reach 0.524**. At these two failed captures the current-radius residuals are 0.519 and 0.524. The basis is not an accurate full-space solution there. We therefore cannot attribute the failures solely to radius selection, point motion, or the nonlinear model. Nor should an interior solution in an insufficient subspace be interpreted as an accurate full-space Newton step.

## Work and verification

- All four bounded owner runs completed: **3.804574 native solve seconds**, **6.350350 process seconds** total, including diagnostic overhead inside the respective clocks. Independent Python audits are outside both clocks.
- Each capture adds 64 basis operator applications and three full-residual validation applications: **804 additional matvecs** total, included in owner counters. Original owner work is still present; these are not production performance runs.
- Median measured common basis/allocation/eigendecomposition construction: **73.49 ms**. The robust basis is expensive and must not be treated as free.
- Sum of common construction plus current candidate reconstruction, true-cost and full-GN scoring: **0.842365 s** over twelve captures. Counterfactual selective sum: **0.873952 s**, **3.75%** more. These exclude validation/export and are estimates from separately timed components, not paired end-to-end runtimes. Timing order is fixed and there are no repeats.
- **304 CPU optimality tests** pass, including SPD, PSD, singular and indefinite hard cases.
- **52 independent exported-state cost audits** pass: twelve source states, 36 candidates and four owner endpoints. Maximum relative discrepancy **2.06e-12** against original BAL observations.
- Independent NumPy checks verify projected KKT, complementarity, shifted PSD, feasibility and reduced prediction. Maximum logged projected relative KKT residual **6.27e-13**; maximum QᵀQ deviation **1.23e-15**. Full-space residuals are exported and explicitly not required to be tiny.
- Camera vectors are exported to check actual distinctness. Reduced predicted improvement is nondecreasing with radius in all captures; actual nonlinear reduction need not be.
- Production `gpu/oca_cuda.cu` remains identical to the frozen v7 source. No defaults changed. Old paused jobs remain paused.

## Next decision

The promising mechanism is **selective radius expansion when the current step is constrained and accurately predicted**, not unconditional evaluation of a wide radius menu. Before a rollout comparison:

1. Make basis accuracy observable and adaptive, using the Lanczos residual relation or a checked full residual, while retaining a strict work cap and the incumbent fallback. Reuse the existing solve's basis rather than paying for a second robust depth-64 sweep.
2. On an interior rejection, contract below the rejected step norm so another solve cannot simply return the same candidate. For example, test a predeclared rule `Δnew = min(Δ/4, ||z_rejected||/2)`; handle zero camera motion/point-dominated failures separately. This rule is a proposed experiment, not a tested result here.
3. Run a short matched end-to-end comparison against corrected TR-one, charging basis construction, abandoned candidates and fallback work. Local gain is insufficient to replace the incumbent.

Artifacts: `/workspace/prism-camera-radius/` contains frozen protocol, complete source overlay, build log, binary, header snapshots, four run manifests/logs/CSVs, projected matrices, candidate vectors, 52 states and `summary.json`. Binary SHA256: `1ca950e8e42500411fb23aff569791f4841f95f47e593bfa6a25e94139bdac8f`.

Reproduction code: `bench/build_camera_radius.py`, `bench/camera_radius_study.py`, `bench/summarize_camera_radius.py`, `bench/test_projected_radius.cc`, `gpu/projected_radius.h`, `gpu/camera_radius_capture.inc`. The build uses the previous isolated corrected-TR source and snapshots headers; preserve that artifact for exact reproduction. The run harness refuses to overwrite an existing protocol or logs.
