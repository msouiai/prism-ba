# Adaptive and selective radius rollouts

**Corrected TR-one remains the general incumbent.** Four sequential experiments failed to improve both sampled scenes consistently. Initial-only expansion is a repeatable local winner on Trafalgar, but loses on Dubrovnik. No default was changed and no new Caspar comparison was run.

The previous [matched-state radius study](camera_radius_results.md) established local gains, duplicate interior steps and inaccurate depth-64 subspace solves. This follow-up tests actual nonlinear trajectories and time to the same frozen quality targets.

## Results

Each table entry is the median native target-crossing time from three runs. Each phase has its own freshly measured baseline using the **same binary as its candidate**. Compare within rows; baseline variation across phases includes different reduction orders/trajectories and timing variation.

| Experiment | Trafalgar TR-one | Candidate | Dubrovnik TR-one | Candidate |
|---|---:|---:|---:|---:|
| Adaptive projected radii | 0.530 s | 1.056 s | 0.758 s | **0/3 hit within 4 s** |
| Persistent saved-direction ray search | 0.463 s | 0.903 s | 0.755 s | 1.008 s |
| Initial expansion only | 0.456 s | **0.387 s** | **0.750 s** | 0.887 s |
| Initial expansion + separate point damping | **0.495 s** | 0.544 s | **0.732 s** | 0.847 s |

All other cells hit 3/3. The adaptive Dubrovnik endpoints are approximately 360,486, above the 359,003.911 target; misses are not imputed as four-second hits. Trafalgar's frozen target is 104,534.241529. All crossings use the same inherited 1e-8 inward margin. Different endpoint overshoots remain visible in raw result JSON.

Initial-only expansion reduces Trafalgar time by **15.2%** (1.18× speedup), winning all three pairs. It increases Dubrovnik time by **18.3%**, losing all three pairs. These are two development scenes, not independent confirmation or evidence for a scene classifier. Separate point damping loses two of three Trafalgar pairs and all three Dubrovnik pairs.

## Sequential experiments and their interpretation

### 1. Adaptive projected solve

Grow a twice-reorthogonalized shared camera Krylov basis through depths 16, 32, 64 and 128. At each checkpoint solve the projected radius problem and explicitly check the full camera-space residual

```
||(S_tau + lambda I) z - b|| / ||b|| <= 0.1.
```

If the check passes, this replaces the ordinary CG solve; it does not add a second sweep on successful solves. If the cap is reached without passing, the original CG solver runs as a fallback and all abandoned basis work is charged. Outer zero uses the incumbent to initialize the radius. Neighboring-radius solves reuse the current basis and may grow it within the same cap. This experiment does not retain the projected basis across nonlinear states. On nonlinear retries the existing direction bank is reused; full projected-basis retry reuse is not implemented.

Evaluate current radius first. An acceptable boundary-limited step with rho > 0.75 triggers a double-radius test. Rejection triggers

```
R_next = max(1e-14, min(R/4, ||z_rejected||/2)).
```

This contracts below a nonzero rejected step norm, except at the absolute radius floor. Actual nonlinear cost, full unregularized GN prediction and camera feasibility determine acceptance. Point safeguards remain active. The current and at most one neighboring projected candidate are tested; existing fallback/safeguard work can add evaluations.

The two traced seven-iteration runs show six successful current-radius residual checks (maximum 0.09534) and six cap failures. Trafalgar outer3 rejects a projected step with rho -12.05, contracts from radius 5281.3 to 1320.3, and accepts with rho 0.997. Thus residual control and meaningful contraction work, but this implementation is not fast enough.

Median total matvec counts: Trafalgar 2054 versus baseline 1063; Dubrovnik 3449 versus 510. Repeated capped attempts plus fallback are expensive. Successful projected solves still have orthogonalization, small dense eigensolve and explicit verification costs.

There is an additional algorithmic change: the projected camera multiplier supplies the menu-placement anchor. Because the inherited point damping follows that placement, Dubrovnik point damping drops from 0.0591 to 1e-7 by outer3. Therefore this experiment does **not** isolate Krylov depth or radius choice as the sole cause of its trajectory regression.

### 2. Cheap saved-direction search

After the first experiment lost, replace basis construction with exact scalar minimization along each already saved camera direction. For direction z, bdot = bᵀz and curvature = zᵀSz, use

```
a = min(R/||z||, bdot/curvature)  // positive bdot and curvature
predicted reduction = a*bdot - 0.5*a*a*curvature.
```

For nonpositive curvature and positive bdot, use the radius boundary. Unlike the earlier clipping code, a may exceed one. Rank rays using existing coefficients; no new matvec is required for this ranking. Lift and point back-substitution are recomputed for the chosen neighboring camera step. The same selective current/neighbor policy and full nonlinear acceptance apply. These are solutions over a finite union of rays, not exact full-space or Krylov-space TR solutions.

This removes the large projected-basis overhead but still loses. Trafalgar has three nonlinear rejections in every timed run versus zero for baseline; Dubrovnik has one versus zero. The first expansion is good in both traced scenes, while later extrapolation can have poor nonlinear agreement. Median matvec counts become 1939 versus 933 and 684 versus 511: trajectory changes consume more linear work even though ray ranking itself is cheap.

### 3. Initial expansion only

After persistent ray search lost, allow its extra test only at outer zero; subsequent iterations return to the original corrected TR-one policy. This is a predeclared follow-up based on the observed early/late distinction, not a parameter sweep. No learned gate or scene-specific condition is used.

All timed runs have zero rejections. Trafalgar needs median 791 matvecs versus 933; Dubrovnik needs 644 versus 510. Consequently, the remaining contradiction cannot be explained purely by retries. A better immediate step can change subsequent damping, conditioning and convergence work adversely.

### 4. Separate point damping

After the initial-only version split the scenes, keep its camera policy but separate point damping from camera-lambda placement. Initialize point tau from the original first-iteration value. After an accepted step, multiply by 0.25 if rho > 0.75, by 0.5 if rho >= 0.25, otherwise retain it; clamp below at 1e-7. Keep tau fixed on rejection so cached operators remain valid. This is a bounded model-agreement heuristic, not a joint trust-region optimality result.

It does not establish a consistent improvement. Trafalgar has one rejection in one repeat; Dubrovnik has none. Median matvec counts are 1084 versus baseline 1031 and 594 versus 502. This rules out this particular schedule as a remedy; it does not rule out every independent point controller.

## Mathematical implication

The standard BA Schur reduction is documented in the [Ceres solver source documentation](https://ceres-solver.googlesource.com/ceres-solver/+/master/docs/source/nnls_solving.rst). Applying block elimination to **jointly damped** camera and point equations gives, by direct algebra,

```
S(lambda) = B + lambda*Dc - G*(C + lambda*Dp)^(-1)*G^T.
```

In general this is not `S(0) + lambda*I`, even after fixed camera equilibration. The reduced RHS also changes through point elimination. The fixed-point-damping camera family enables ordinary shifted Krylov reuse, but that convenience does not make its radius a joint camera-and-point trust region. This explains a structural limitation, not a proof that multishift cannot win. Better joint geometry and exact scalar-shift reuse cannot simply be assumed together.

The useful next research direction is a small **joint camera/point subspace model**, checked at frozen contradictory states before another rollout. It should predict the actual mixed step and distinguish point-model error from insufficient camera solve accuracy. Further fitting of radius multipliers or damping schedules on these same two scenes is not justified by this series.

## Validation and reproducibility

Four phases × (two traced seven-iteration runs + twelve timed target runs) = **56 runs**. Every phase reverses arm and scene order in the second repeat. Target runs disable profiler, candidate learning logs and detailed radius traces. Each has a four-second native cap and a 40-second process timeout; native caps are checked at solver boundaries and may slightly overshoot. Traces are for diagnosis and are excluded from target medians.

Total measured native solve time, including the eight traced runs, is **47.369 seconds**; total subprocess wall time is **79.968 seconds**. Build time and independent Python audits are outside these totals.

All **56 exported endpoints** pass independent CPU cost audits against original BAL observations. Maximum relative discrepancy is **2.27e-14**. Independent verification also checks initial/final CSV costs, monotonic accepted costs, binary/source/header/data hashes, accepted camera feasibility and rho, depth cap and successful residual thresholds, and that early-only variants emit extra radius trials only at outer zero. The projected math's 304 KKT tests and 1000 scalar-ray KKT/contraction checks pass.

Artifacts retain each full source snapshot, header snapshot, binary, protocol, manifests, logs, CSVs, states and results:

- `/workspace/prism-adaptive-radius/`: `adaptive/` and `ray/`; combined `verification.json`.
- `/workspace/prism-early-radius/early/`.
- `/workspace/prism-separate-tau/separate/`.

Repository code: `gpu/adaptive_radius_solve.inc`, `gpu/adaptive_radius_select.inc`; `bench/build_adaptive_radius.py`, `bench/build_early_radius.py`, `bench/build_separate_tau.py`; corresponding `*_study.py` harnesses; `bench/summarize_adaptive_radius.py`, `bench/verify_radius_rollouts.py`, `bench/test_radius_ray.py`. Follow-up builds consume the prior frozen artifact, preserving the tested revision rather than altering its files. Production `gpu/oca_cuda.cu` still matches frozen v7; the 11 older jobs remain paused. No default promotion or push was performed.
