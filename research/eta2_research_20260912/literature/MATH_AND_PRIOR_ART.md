# Mathematical and prior-art audit of the Eta2 research briefs

Date: 2026-09-12. Scope: Briefs 1, 3, 4, 6, 7, 9 and 12, with the diagnostic assumptions needed by Brief 0. This is a bounded review, not a new benchmark or a complete novelty search. No solver was changed and no GPU run was launched for this audit.

The [frozen theory note](../../eta2_champion/docs/theory_and_novelty.md), [configuration](../../eta2_champion/champion.json), source and build script were inspected. The source SHA256 remains `22c18359a526526ae0a5b5109187878ab1cef33b453f6bbddc2aa92597a607d8`; all 44 header hashes match `source_manifest.json`. The builder uses `nvcc -O3 -DNDEBUG -std=c++17 -arch=sm_89`, with no `--use_fast_math` option. This is a mixed-storage solver with FP64 arithmetic in the principal solve, **not** a uniformly FP64 stored operator. A new comparison still needs its own binary/flag/score-init verification.

## Decisions that affect the experiments

| Brief | Audit decision |
|---|---|
| 0/1 | Long-wavelength under-solving is a hypothesis. Measure the missing direction in one explicit metric, remove gauge and rank artifacts, then decide whether a coarse solve is justified. |
| 1 | The geometry, multigrid and deflation principles already have direct BA predecessors. A matrix-free implementation and its interaction with cheap inexact solves remain useful empirical questions. |
| 3 | Boundary-truncated PCG is a valid distinct test. Its optional quadratic-progress stopping rule substantially repeats already-tested and explicitly excluded work; omit that knob. A numerical curvature trip is not genuine negative curvature to exploit. |
| 4 | The sum-of-squares identity is valid with consistent blocks and an accurate point solve. Changing only the denominator in an inconsistent CG recurrence is not a stability fix. |
| 6 | A PI radius policy is a reasonable small experiment, but accept/reject alternation alone does not prove a limit cycle. “All LM updates are sign based” is false. |
| 7 | **Blocked as stated:** coupled point damping makes both the reduced operator and RHS depend on lambda, so Eta2's Schur systems are not a scalar-shift family. No free shared-recurrence ARC implementation follows from the brief. |
| 9 | Both opening and late nonlinear collective corrections have already failed on inspected BAL samples. The new, narrowly distinct test is a coarse diagnostic at full-problem terminal witnesses, before implementing another correction schedule. |
| 12 | LM is not exactly implicit Euler for the true gradient flow when its Jacobian is replaced by Gauss–Newton. A two-stage method needs explicit coefficients, a consistent tangent chart, and charged second-stage work. |

The current champion stays frozen throughout. The scored objective remains the original observation L2 objective with SIMPLE_RADIAL, unshared intrinsics and k2 fixed at zero. Each promoted experiment must retain the user's N>=3 cells, N>=5 tail claims, preregistration, both signs of change, and explicit time-to-target misses. Disjoint observed ranges are a screening rule, not a confidence interval or proof of population separation.

## 1. Coarse-space hypothesis, geometry and algebra

### What the observations do and do not establish

The assertion that Eta2 *never* resolves long-wavelength camera modes is stronger than the evidence. A cheap residual tolerance can leave low-energy error, but high damping can also make an accurate linear solve almost useless. The [earlier depth interpretation](../../eta2_depth_rescue/INTERPRETATION.md) reports Final3068 terminal probes meeting relative residual below 1e-3 in one iteration while their directions were severely clipped. The later [pair/precision experiment](../../eta2_pair_precision/FINDINGS.md) showed that correcting linear precision did not make Venice's proposals nonlinearly acceptable. Neither observation establishes an unresolved global camera mode.

For a fixed SPD system A z=b, the quadratic error is exactly `0.5*r^T*A^-1*r`; a small Euclidean residual can coexist with substantial error in small-eigenvalue directions. This motivates Brief 0, but does not establish its outcome. The elastic-network analogy is useful intuition: the actual reduced blocks are anisotropic, geometry-dependent couplings, rather than scalar springs inferred solely from graph edges.

### Correct similarity modes in the native camera chart

The native retraction is `R_new=Exp(dw) R`, `t_new=t+dt`; `t` is world-to-camera translation, not camera center. Define `C=-R^T t`. For a cluster centroid Cbar, construct the physical finite transform

```
C_i(eps) = Cbar + exp(eps*s) Exp(eps*omega) (C_i-Cbar) + eps*v
R_i(eps) = R_i Exp(eps*omega)^T
t_i(eps) = -R_i(eps) C_i(eps).
```

Recover the native increments using `Log(R_i(eps) R_i^T)` and `t_i(eps)-t_i`, then take a centered derivative. The resulting tangent is

```
dw_i = -R_i omega
dC_i = v + omega x (C_i-Cbar) + s*(C_i-Cbar)
dt_i = R_i(omega x C_i) - R_i dC_i.
```

Therefore substituting `dw=omega` or storing `dC` directly in the translation slots is wrong. Intrinsic increments are zero. The existing [collective derivation](../../geometry_agenda/T4_MATH.md) gives the equivalent origin-centered formula. Verify finite differences against this analytic derivative and verify first-order invariance when cameras and points receive the same global similarity.

With native camera tangent basis Zraw and `d_c=E z`, form `Z=E^-1 Zraw`. Rank-revealing local QR/SVD must drop singleton scale columns and other dependent directions. Define `K_eff=min(K,ncam)` before diagnostics; K=128 on Venice52 does not describe 128 nonempty clusters. At that limit the span can approach all camera extrinsic directions, making a high projection fraction nearly automatic. Report requested/effective K, basis rank, rank/(active camera dimension), cluster sizes and setup cost.

### Define the projection metric explicitly

For the camera part of the missing direction, use

```
delta_z = E^-1 (d_exact,c - d_eta2,c)
Q = orth(Z)
fraction = ||Q^T delta_z||_2 / ||delta_z||_2.
```

This is the camera D_c norm in native coordinates. It is neither the Euclidean norm of translation/rotation slots nor the A-energy fraction. An optional energy fraction is

```
sqrt((Z^T A delta_z)^T (Z^T A Z)^-1 (Z^T A delta_z)
     / (delta_z^T A delta_z)).
```

Label these separately, and label a negligible denominator undefined. Compare raw-to-raw directions first; use a second, explicitly named diagnostic for the actual clipped directions. Remove the seven global similarity gauge modes, or report their contribution separately. Exclude k2-only modes from the Ritz spectrum. Damping turns otherwise free modes into small positive eigenvalues; those alone are not evidence of useful unresolved geometry.

For the spectrum, apply symmetric Lanczos to `M^-1/2 A M^-1/2`, or use the equivalent generalized A/M inner products. Ordinary Euclidean Lanczos on `M^-1 A` is generally invalid because that product is nonsymmetric. Fix M within the solve and charge all diagnostic products. A 50-step Ritz approximation is not a complete spectrum or a certified smallest eigenvalue.

### Two-level operator definitions

Let `Ac=Z^T A Z`, `Q_c=Z Ac^-1 Z^T`, and `P=I-A Q_c`, after rank reduction and numerical SPD checks. Three well-defined choices are:

```
additive inverse:     B_add = M^-1 + Q_c
balanced inverse:    B_bal = P^T M^-1 P + Q_c
deflated system:     (P A) y = P b
reconstruction:      z = Q_c b + P^T y.
```

`P A=A-AZ Ac^-1 Z^T A` is symmetric positive semidefinite; its nullspace and compatible RHS require deliberate handling. Do not insert P as an arbitrary nonsymmetric preconditioner into unchanged PCG. Additive correction is SPD when M is SPD, but it does not algebraically annihilate the selected eigenmodes in the way projected deflation does. A changed preconditioner or changing approximate coarse solve needs a restart/flexible algorithm, not stale PCG conjugacy.

These are standard constructions; [Tang, Nabben, Vuik and Erlangga (2009)](https://link.springer.com/content/pdf/10.1007/s10915-009-9272-6.pdf), sections 2.3–2.4, explicitly compares additive, deflated and balancing variants and their sensitivity to implementation errors. Use the additive variant first if the witness test passes; its simplicity is a stronger first experiment than three simultaneous algorithm changes.

### Coarse assembly is not a constant-cost pass

The formulas in the brief are algebraically valid, including the camera U term and `lambda*Z`. But each point first needs its complete `T_j` across observing clusters; after the point solve, its contribution must be redistributed. A point-major fused traversal can achieve this with local storage, but storage and arithmetic depend on the number k_j of observing clusters. The coarse block accumulation scales with roughly `sum_j k_j^2` seven-mode block interactions; it is not a single ordinary Schur product. Dense AZ storage at 13,682 cameras and K=32 is 220,663,296 bytes (about 210 MiB), before other buffers. The additive variant does not need to retain dense AZ. Rebuilding Ac per lambda retry remains necessary under coupled point damping.

### Direct BA prior art that must be cited

- [Byröd and Åström, BMVC 2009](https://lup.lub.lu.se/search/files/6053078/1612241.pdf), section 4, already constructs hierarchical camera translation/rotation/scale representations for Schur-system preconditioning. It is not merely fine block smoothing. The implementation is an overcomplete basis change plus conventional preconditioning, rather than the exact additive seven-mode policy proposed here.
- [Konolige and Brown, *Multigrid for Bundle Adjustment* (2020)](https://arxiv.org/pdf/2007.01941), sections 3.1–3.4, is even closer: seven similarity near-nullspace modes, visibility-based aggregation, local QR prolongation, and a reduced camera multigrid solver. Their extra camera-coordinate constant columns also warn that a rigid-only space can miss important intrinsic error. This paper already supplies the global-mode/elasticity motivation.
- [Katyan, Das and Kumar, WACV 2020](https://openaccess.thecvf.com/content_WACV_2020/papers/Katyan_Two-Grid_Preconditioned_Solver_for_Bundle_Adjustment_WACV_2020_paper.pdf) presents a deflated algebraic two-grid BA solver using GMRES. [Das, Katyan and Kumar, WACV 2021](https://openaccess.thecvf.com/content/WACV2021/papers/Das_A_Deflation_Based_Fast_and_Robust_Preconditioner_for_Bundle_Adjustment_WACV_2021_paper.pdf) studies BA deflation of large Hessian eigenvalues. The latter PDF's indexed text was available; direct fetch returned 403 during this review, so no more specific implementation equivalence is asserted.
- [Manam and Govindu, CVPR 2026](https://www.merl.com/publications/TR2026-053) addresses parallel-rigidity/uniqueness structure. Its filters remove observations or components; such filtering would change this campaign's scored problem and is excluded. Graph information can inform a partition without adopting their data filtering.

**Available claim if successful:** a particular inexpensive GPU implementation, coupled-damping rebuild strategy and validated inexact-solve interaction. “First coarse grid/deflation/rigid-mode BA” is unavailable. The [existing Schur-preconditioner result](../../schur_preconditioner/RESULTS.md) also warns why isolated linear wins are insufficient: Muell's captured solve improved 5.388x, yet the integrated always-on method was 20.1% slower to target.

## 2. Brief 3: boundary-truncated PCG

[Steihaug (1983)](https://epubs.siam.org/doi/abs/10.1137/0720042) establishes the preconditioned truncated-CG trust-region approach. For a fixed SPD metric M, define the constraint `z^T M z<=R^2`. At a crossing along p, solve

```
a = p^T M p; b = z^T M p; c = z^T M z - R^2
a*tau^2 + 2*b*tau + c = 0.
```

Use a numerically stable positive root, with explicit guards for zero a and roundoff in the discriminant. In exact arithmetic, ordinary CG started at zero has monotone Euclidean iterate norms; PCG has the corresponding property in its fixed preconditioner metric. The brief's concern applies to PCG in an unmatched Euclidean metric, not all CG.

Changing from Eta2's `||z||_2` ball to an M-ball changes the feasible set and the meaning of R. A copied scalar R is not a matched radius. The clean first ablation is boundary truncation in the existing ball, stopping at the first crossing without claiming monotonicity. A separately registered M-norm arm should specify initialization and transport/recalibration as M changes across attempts. Neither metric removes that change automatically. Record the discarded-work counter in passive baseline traces before expecting large savings.

The subproblem is also important: running truncated PCG on A_lambda minimizes the already damped reduced quadratic inside another radius. It is a **damped, camera-constrained** model. It is not automatically the undamped full BA trust-region subproblem; point-only movement remains unconstrained. Continue scoring the actual full candidate and recompute points for the selected camera step.

At genuine negative curvature, a boundary candidate can exploit the model. At Venice's audited mixed-storage events, the consistent operator is positive: treating a numerical defect as a saddle direction is unsupported. First verify the operator and distinguish strictly negative, small positive and nonfinite pAp. Removing the persistent floor and changing the truncation policy at once is a combined intervention; record the same events under a consistent operator and retain the original nonlinear safeguards. A small-positive cutoff is a breakdown policy, not an ST negative-curvature event.

**Drop the optional model-progress stopping knob.** It substantially overlaps `/workspace/prism-ba/docs/cg_value_results.md` and `gpu/cg_value.h`: that campaign already accumulated `alpha*r^T*M^-1*r/2` without new GPU products, tested trailing model-gain windows and a work-only comparator, and found only a localized gain with counterexamples. The selected conservative arm gave 1.0322x over five medium cells, below its extension gate. This is distinct from the older Frank–Wolfe-gap implementation in frozen `tr_cg_stop.inc`, but is the relevant prohibited marginal-value experiment. [Ceres' CG source](https://github.com/ceres-solver/ceres-solver/blob/master/internal/ceres/conjugate_gradients_solver.h) also implements quadratic-progress termination and cites Nash/Sofer (1990) and Nash (2000). The reduced damped gain is not the full undamped predicted BA decrease after camera clipping or point rescue.

The statement “ST-CG is not used in BA” was not established by this bounded search and should not appear as a novelty claim. [Ceres documents LM and Dogleg](https://ceres-solver.readthedocs.io/latest/nnls_solving.html); this supports a claim about those particular implementations, not every BA solver. Our earlier `/workspace/prism-ba/docs/cg_stopping_results.md` already tested projected Krylov TR candidates on another solver generation, with a Dubrovnik regression. Boundary-only truncation differs, but better quadratic models have not reliably transferred to the nonlinear trajectory.

## 3. Brief 4: consistent Gram products and sum-of-squares curvature

Write `y=J_c E v`, `s=J_p^T y`, `H_p=J_p^T J_p+lambda D_p`, and `u=H_p^-1 s`. With one common Jacobian and symmetric point solve, completing the square gives

```
v^T A_lambda v = ||y-J_p u||^2 + lambda*u^T D_p u
                 + lambda*||v||^2 + (Ev)^T Q_intr (Ev).
```

The associated product includes the intrinsic term:

```
A_lambda v = E J_c^T (y-J_p u) + lambda*v + E Q_intr E v.
```

The brief's shorthand Ap omits that last term unless it is explicitly folded into an augmented Jacobian. Omitting it silently changes the solve. The same stored J must feed the gradient, camera normal/scaling, point normal/damping, cross action and transposed action. Replacing W alone or only the denominator does not implement this construction.

For an approximate point solve u, define `e=s-H_p u`. Then the exact identity for that u is

```
v^T [E J_c^T(y-J_p u)+lambda*v+E Q_intr E v]
   = SOS(u) + u^T e.
```

Thus a nonnegative SOS need not equal the dot product with the actual Ap. Using SOS in the CG denominator while updating the residual with a mismatched Ap can destroy conjugacy and conceal error. Even with exact point algebra, floating-point evaluation of a positive scalar alone is not a backward-stability theorem for an entire CG solve. Cancellation can still occur in y-J_p u and in transpose accumulation. Nonnegative finite terms cannot produce a negative sum, but overflow/NaN and underflow remain possible.

**Minimal valid test:** first implement one consistent FP64 Jacobian path and validate symmetry, product agreement, full-block/Schur equivalence, point residuals, SOS-versus-pAp agreement, and explicitly recomputed final residual. Audit the recorded numerical events. Then, separately, try one consistently rounded FP32 Jacobian with FP64 accumulation/factorization. It defines a perturbed local linear model; it does not change the original scored nonlinear objective or guarantee the original trajectory. The earlier FP32-fragment refutation includes large endpoint regressions, not only curvature warnings, so consistency must not be assumed to cure all storage-related basin sensitivity.

[Demmel et al., CVPR 2021](https://www.usenko.net/pdf/demmel2021rootba.pdf), sections 5 and 6.4, already identifies numerical Schur indefiniteness and avoids the normal-equation cancellation through square-root/nullspace marginalization. The displayed damped SOS is a useful variational identity closely related to that construction; “first PSD BA” or “backward stable by a one-line replacement” is not supportable. The brief's 3000/3000 negative toy count has no supplied seed/code here and was not independently reproduced; it should not become our result. Rounding sign depends on the instance, and there are exactly representable examples with no negative eigenvalues.

The practical-target speed ceiling is explicit: the frozen nine-cell report saw no numerical recovery before its targets. Benefits must come from tail stability or separately measured bandwidth savings; zero cutoff events alone is not a speed win.

## 4. Brief 6: PI control without overclaiming the analogy

[Gustafsson's stepsize-control work](https://doi.org/10.1145/210232.210242) and [Söderlind's 2003 digital-filter paper](https://portal.research.lu.se/en/publications/digital-filters-in-adaptive-time-stepping/) establish the ODE-controller analogy. Those stability analyses concern a specified stepsize/error plant; Eta2's radius, point damping, inexact solve and nonlinear rescue do not satisfy that plant model automatically.

In log coordinates the proposed rule is a PI-type filter, but `e=|1-rho|` needs a positive floor and finite-prediction guards. It has equilibria near rho=0.7 **and** rho=1.3, not only 0.7. It can shrink after a highly successful rho>1 step; retain this behavior only if it is intentionally registered. Very small predicted reduction makes rho noisy, so the history policy for those cases must be explicit. Define first-history initialization, saturation, rejected-step treatment and how the existing accepted-interior lambda reduction interacts with the new R rule.

Rejecting steps exactly as the champion and updating history only on acceptance leaves a pure zero-accept retry storm's within-storm policy unchanged. PI may prevent entry into such a storm, but cannot be credited with a new reaction to an already identical freeze. Log accepted/rejected transitions, damping/radius, prediction scale and time in each branch; a few oscillations are not evidence of a deterministic limit cycle. Screen one global parameter setting first; tuning on a grid requires a separate selection cohort and frozen transfer rule.

“All BA damping updates are sign based” is false. [Ceres' actual accepted-step rule](https://github.com/ceres-solver/ceres-solver/blob/master/internal/ceres/levenberg_marquardt_strategy.cc) uses a smooth cubic function of step quality, while rejected steps increase their shrink factor. PI's distinct ingredient is history, not merely continuous response to rho.

The proposed [arXiv:2608.25524](https://arxiv.org/html/2608.25524v1) exists: Hoang and Lewis, submitted 26 August 2026. Its section 3.4 uses threshold-based damping; its main architecture is hybrid-subspace adequacy plus Armijo acceptance. It is relevant prior art for separating acceptance from damping, not evidence that PI radius control is already the same algorithm. Its memory/Krylov enrichment also overlaps directions excluded from this campaign. No priority conclusion for PI-in-BA follows from this focused search.

## 5. Brief 7: ARC requires a different valid system family

Eta2 has

```
A(lambda) = E[U-W(V+lambda Dp)^-1 W^T]E + lambda I
b(lambda) = -E[gc-W(V+lambda Dp)^-1 gp].
```

Consequently

```
A(lambda2)-A(lambda1) = (lambda2-lambda1)I
  + EW[(V+lambda1 Dp)^-1-(V+lambda2 Dp)^-1]W^T E.
```

The second term is generally nonzero and non-scalar, and the RHS changes. Standard shifted-CG recurrences require a fixed base matrix plus scalar shifts and compatible shared RHS/residuals. This property is absent after Eta2's coupled point elimination. Monotone A(lambda) does not establish monotone camera-step norm when b(lambda) also changes. The [existing architecture note](../../schur_preconditioner/ARCHITECTURE.md) already identifies this obstruction.

There are valid alternatives, but each changes cost or model:

1. Work in the **full** scaled variable with `D=diag(Dc,Dp)` frozen within an outer. Then `D^-1/2 H D^-1/2 + lambda I` is a genuine shift family with a common scaled gradient. Charge camera-plus-point Krylov vectors and products; it is not the cheap reduced camera engine.
2. Freeze point damping while solving a cubic-regularized **camera** model. This produces a reduced shift family but changes the coupled model and point-response path. It does not inherit the full-step ARC theorem without a new derivation.
3. Solve the coupled reduced systems separately while root-finding, charging point factors, RHS and preconditioner rebuilds for every lambda.

For a cubic `sigma*||d||_M^3/3`, stationarity is `(H+sigma*||d||_M*M)d=-g`. An identity shift is appropriate only in coordinates whitened by the fixed metric. Changing M per shift also breaks ordinary sharing. A five-point log interpolation is not an exact secular solve or a complexity certificate; bracket and verify the residual, positive definiteness/adequate decrease, and inexact-ARC requirements.

[Dussault, Migot and Orban, *Scalable adaptive cubic regularization methods*](https://link.springer.com/article/10.1007/s10107-023-02007-6) is the direct precedent: published online in 2023, volume 207 in 2024. Its ARCqK uses simultaneous shifted Krylov solves and quadratic-model acceptance. The accessible [earlier author manuscript](https://optimization-online.org/wp-content/uploads/2021/03/8317.pdf) spells out the fixed-Hessian family and inexact conditions. Thus even a valid root-finder marriage would not make shifted-Krylov ARC itself new. A Gauss–Newton approximation and perspective singularities also prevent casually importing the usual cubic-regularization complexity theorem.

**Recommendation:** do not implement the advertised free Schur ARC graft. If the earlier diagnostics justify ARC, preregister one of the three mathematically valid architectures and its overhead first. The original multi-shift-as-candidate generator remains excluded.

## 6. Brief 9: terminal coarse diagnostic before another correction

[Ni, Steedly and Dellaert, ICCV 2007](https://dellaert.github.io/files/Ni07iccv.pdf) already uses submap/base-node parametrization and global relative alignment. The repository's [collective BAL experiment](../../collective_bal/README.md) then measured exact finite similarity corrections on all-camera, fixed-intrinsics sampled problems: 135 runs, no saved fine step, bridge-only time ratios 0.909x/0.906x/0.884x. The [Astra late insertion oracle](../../astra_followup/README.md) is stronger overlap: 216 interventions plus 54 continuation controls, N=3, checkpoints 2/4/8, one/two coarse iterations, and two targets; none saved a fine accepted step, even under hindsight-best insertion choices.

These are limited CPU samples, not full Eta2 terminal witnesses, so Brief 9 is not universally refuted. But “try late rather than opening” has already been done. The new pre-test must inspect the actual full-problem stall geometry and justify a different useful subspace before building another controller.

Distinguish two coarse models:

- Restricting the **eliminated camera** quadratic gives gradient `Z^T*(-b_lambda)` and Hessian `Z^T A_lambda Z` (with signs adjusted to the chosen convention). Using bare `Z^T gc` drops the eliminated-point contribution.
- Moving cameras and passenger points by a joint similarity basis B gives gradient `B^T g` and GN curvature `B^T J^T J B` with its specified damping. It is not generally the first model; passenger motion is not the optimal point back-substitution.

For either SPD quadratic, half the projected gradient times its coarse inverse is the unrestricted **coarse quadratic** decrement. Large values may justify a trial; zero values show only no first-order descent in that span. They do not certify full stationarity or justify stopping the fine solver. Global similarity gauge directions must be removed or handled explicitly, and coarse cost/setup/verification must be charged. The sampled-work results demonstrate why a positive coarse decrease need not replace one useful fine iteration.

## 7. Brief 12: define the flow and method before testing

For frozen positive D, consider `D*x_dot=-g(x)`. Linearizing backward Euler with the **true** Hessian gives `(H_true+D/h)d=-g`. Replacing H_true by J^T J gives the LM-shaped step; that replacement is an approximate-Jacobian integration, not exact implicit Euler for the original flow. Intrinsic solve priors, variable diagonal scaling and post-solve clipping add further differences.

A two-stage Rosenbrock/W method can legitimately reuse a fixed operator with a second RHS, but “ROS2” is not enough to specify it. Fix the coefficients, approximate Jacobian, h-to-lambda mapping and stage retraction. A gradient computed at the intermediate camera state lives in that state's tangent coordinates: transport it, or differentiate the fixed-base retraction chart, before adding it to the original linear RHS. Include the point component of both stage RHSs and both Schur back-substitutions. Reuse factors and preconditioner only because the operator is deliberately held fixed; do not reuse a previous Krylov space.

The necessary cheap checks are order/consistency on quadratic and simple nonlinear Euclidean models, tangent finite differences, and no-op-stage recovery. On witnesses, compare the proposed two-stage total model/true decrease per measured work against two ordinary LM steps or an equal-time champion budget, not only against one step. Extra gradient, second solve, stage arrays, two full costs and synchronization are not free, and a universal “1.7 outers” cost estimate is not established.

[Ascher, van den Doel, Huang and Svaiter (2009)](https://archive.numdam.org/articles/10.1051/m2an/2009025/) studies artificial-time/optimization tradeoffs and gives no blanket reason accurate transient integration should accelerate approach to a minimizer. Earlier curved/geodesic-update negatives in [the research handoff](../../../docs/research_brief_feedback_2026-09-11.md) are related cost/model warnings, not an identical ROS2 test. Keep this direction low priority and do not expand beyond witness tests without a clear per-work benefit.

## Recommended immediate order

1. Complete Brief 0 on the newly registered witnesses with exact state/history and objective parity. Label nonconverged “exact” solves as unresolved diagnostics.
2. Compute the rank-aware, gauge-aware K=8/32/128 projection diagnostics. If supported, implement one additive coarse preconditioner, with all assembly cost measured.
3. In parallel with that decision, use the coherent operator to validate the SOS identity and numerical-event mechanism. Keep speed claims separate from precision correctness.
4. Allow boundary-only ST-CG and one PI policy as separately registered changes. Drop the duplicated quadratic-progress stopping knob.
5. Require a new full-witness mechanism for nonlinear coarse correction. Redesign ARC's system family before coding. Defer ROS2 until those cheaper decisions are resolved.

No new solver, speed result, hit-rate result or novelty claim is established by this audit.
