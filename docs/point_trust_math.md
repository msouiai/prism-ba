# Point damping: identities, guarantees, and limits

This derivation motivates the opt-in point-damping experiment; it does not establish convergence or novelty for the resulting nonlinear controller.

The standard LM context and distinction between predicted and actual reduction are described in [Ceres' official least-squares documentation](https://ceres-solver.readthedocs.io/latest/nnls_solving.html) and §3.2 of [Madsen, Nielsen and Tingleff, *Methods for Non-Linear Least Squares Problems* (DTU, 2004)](https://www2.imm.dtu.dk/pubdb/edoc/imm3215.pdf). The block identities and experimental bounds below are derived here and checked independently in the accompanying tests.

## 1. Which system is being solved?

For `F = 1/2 ||r||²`, let `g=Jᵀr` and partition the Gauss–Newton matrix as

```
H = [ U   G ]       Damping = diag(lambda D_c, tau D_p).
    [ Gᵀ  V ]
```

The full step is `d=-(H+Damping)^(-1)g`. Write `x=-d`, `V_tau=V+tau D_p`,

```
S_tau = U - G V_tau^(-1) Gᵀ,
b_tau = g_c - G V_tau^(-1) g_p,
(S_tau + lambda D_c) x_c = b_tau,
x_p = V_tau^(-1) (g_p - Gᵀ x_c).
```

For fixed `tau`, changing camera damping is a shifted system after equilibration. Changing `tau` changes **both** `S_tau` and `b_tau`; old factors/RHS or a scalar-shift CG recurrence cannot simply be retained.

For positive fixed `D_c`, as `lambda→infinity`, `x_c→0` while `x_p→V_tau^(-1)g_p`, generally nonzero. Thus camera damping alone does not provide the small **full-step** limit of ordinary full-space LM. A menu of camera lambdas can repeatedly fail for a common point-block reason, although that fact alone does not prove points caused a particular BA rejection.

## 2. Match the actual metrics

Point damping uses

```
D_p[j,j] = max(V[j,j], 1e-3 * trace(V)/3)
```

within each 3×3 point block, multiplied by `tau`. This matches `MFPointFactorTau` when a block has positive trace and positive tau. An entirely zero block has a tiny implementation jitter; it has zero contribution to the studied D-norm and is skipped. `R0` is the undamped point QR factor, so `V=R0ᵀ R0` up to roundoff.

The tested camera metric comes from Schur-diagonal equilibration, with the existing camera diagonal floor. Consequently it can itself change when tau changes. A theorem assuming a fixed camera metric must not silently be applied across such updates.

## 3. Reduced prediction is not full objective prediction

For any camera vector `x_c` and its exact point back-substitution, not necessarily an exact camera solve, define

```
P_reg = b_tauᵀ x_c - 1/2 x_cᵀ(S_tau + lambda D_c)x_c
        + 1/2 g_pᵀ V_tau^(-1) g_p.
```

Then the undamped full GN predicted reduction is exactly

```
P_full = gᵀx - 1/2 xᵀH x
       = P_reg + 1/2 lambda x_cᵀD_c x_c + 1/2 tau x_pᵀD_p x_p.
```

Adding just the eliminated point constant to a shifted camera-model decrease still does not supply both damping-energy corrections. If camera and point halves are subsequently scaled differently, the prediction must also reflect their changed cross term. This identity does not assume that the existing recurrence equals the analytic expression under finite-precision/inexact solves. After rejecting point feedback, the amended experiment adds an opt-in direct prediction for the existing rho update (section 9).

`bench/point_trust_math.py` verifies the identity on 200 dense random block systems with arbitrary, inexact camera vectors. Maximum relative discrepancy: `1.91e-14`.

## 4. A scaled step is not generally another damping solution

In a normalized eigenbasis, `x_i(lambda)=b_i/(mu_i+lambda)`. Requiring `x_i(lambda_new)=alpha x_i(lambda)` gives

```
lambda_new = (mu_i+lambda)/alpha - mu_i.
```

This depends on `i` unless the participating eigenvalues coincide. For eigenvalues 1 and 10, lambda 0.1 and alpha 0.25, the required new lambdas are 3.4 and 30.4. Therefore an `alpha→lambda` or `alpha→tau` rule needs an explicit approximation or norm criterion; scalar division is not a general identity.

## 5. An exact conditional trust-region problem

Hold the camera step and linearization fixed. The point forcing `h` is then fixed, and the conditional step is

```
p(t) = (V+t D_p)^(-1) h.
```

This is the multiplier form of minimizing the point quadratic subject to a D-norm radius. Let `W=D_p^(-1/2) V D_p^(-1/2)` and `z=D_p^(1/2) p(tau)`. A requested contraction alpha solves

```
|| (W+t I)^(-1)(W+tau I) z || = alpha ||z||.
```

In an eigenbasis this squared norm is a sum of nonnegative terms

```
sum_i z_i² ((mu_i+tau)/(mu_i+t))².
```

For nonzero forcing and `t>0` it is strictly decreasing. This yields a unique root above tau for `0<alpha<1` on the contributing subspace.

The diagonal metric gives `trace(W)<=3`, hence `0<=mu_i<=3`. Therefore a valid root bracket is

```
t_lo = tau/alpha,
t_hi = (tau+3)/alpha - 3.
```

These are spectral bounds, not fitted constants. The GPU uses geometric bisection, retaining the upper endpoint whose **computed** norm meets the target. It uses up to 12 bisections plus the initial norm and upper-bound evaluation. The upper endpoint is capped at `1e8`; if the cap cannot meet the target or inputs are unusable, the proposed update is invalid and not applied. This is a numerical check of the mathematical contraction condition, not a formal floating-point certificate.

Using the accepted, uniformly scaled point vector as input does not double-shrink it: the norm ratio and its damping root are invariant under a common nonzero rescaling of the input vector/forcing. The saved rescue alpha is carried through narrow/wide fallback so the vector and contraction request match.

## 6. Cheap directional approximation

Let `mu_bar = pᵀVp / (pᵀD_p p)`. Requiring stationarity projected onto the current point direction after scaling it by alpha gives

```
t_R = (tau+mu_bar)/alpha - mu_bar.
```

It is exact for a single active eigendirection. It is **not** generally the root of the full point-norm equation, and may over- or under-contract. The implemented Rayleigh arm measures its achieved conditional contraction without claiming it meets the target.

In the short BA diagnostics, its ratio/requested-alpha median was 2.719 on Dubrovnik (too little contraction) and 0.520 on Venice (more contraction). All 21 scalar-root proposals across those diagnostics satisfied the requested conditional norm contraction; no proposals were invalid. Ladybug-49 had no rescue calls in its diagnostic window.

## 7. Why this is not yet a full BA trust-region solver

With camera damping and its metric fixed, eliminating cameras instead produces

```
T = V - Gᵀ(U+lambda D_c)^(-1)G,
p(t) = (T+t D_p)^(-1) b_p_cond.
```

Here T is generally not block diagonal. It differs from the V used by the cheap conditional point solve. The full coupled point norm is itself monotone in tau under a fixed camera metric and exact solves, but its root is generally different and costs coupled solves to evaluate. Schur-based camera re-equilibration changes the metric too.

`bench/point_trust_coupling_gap.py` constructs 500 dense PSD block systems. Applying the **exact conditional** root and then re-solving the coupled problem violated the requested contraction in 2 cases with a fixed camera metric, and 5 with a recomputed Schur-diagonal camera metric. The worst changing-metric contraction was 0.315 for a requested 0.125. Matrices and seeds are retained in `coupling-gap.json`. Thus even before changing the nonlinear state, conditional contraction is not a universal guarantee for the re-coupled solver.

The deployed experimental feedback additionally carries the damping guess to the **next nonlinear state**. Full objective acceptance and the original backtracking safeguards remain, but no global convergence theorem is asserted for this transfer. The Rayleigh and root arms leave camera damping untouched by the new feedback itself; ordinary accepted-step camera updates remain active.

## 8. Numerical validation and implementation

`gpu/point_trust.cuh` uses the stored point QR factors and diagonal metric, with a 24-byte reduction buffer. It does not allocate a new per-observation or per-point persistent buffer. Each probe streams point factors, diagonals and the point step; it is not free. The recorded timing includes these probes.

`gpu/test_point_trust.cu` compares GPU metrics and contractions to independent Eigen dense solves in whitened coordinates. Twelve old-tau/alpha combinations cover rank-deficient and anisotropic blocks, partial CUDA blocks, zero blocks/steps, invalid tau and the cap. Root damping agrees with a 60-iteration CPU root to better than 1%; maximum normalized contraction discrepancy was `8.89e-16`. Compute Sanitizer reports zero errors. Eigen is only an optional test dependency, not a new CLI/core requirement.

The test bounds do not substitute for BA performance results. Those are recorded separately in the results report under `/workspace/prism-point-trust/` and the repository docs.

## 9. Direct prediction for the actual accepted step

For the actual full increment `d`, including independently scaled camera and point halves, evaluate

```
P_direct = -rᵀJd - 1/2 ||Jd||².
```

This is exactly the unregularized Gauss–Newton model reduction in real arithmetic, regardless of the CG residual or the damping used to generate `d`. It handles the camera–point cross term through the summed residual direction `Jd`. It is a model prediction, not the nonlinear actual decrease and not a claim that the step minimizes that model.

`gpu/full_step_model.cuh` streams the observation Jacobians once and reduces two scalars into a 16-byte device buffer. `OCA_FULL_MODEL_RHO=1` substitutes this prediction in the existing accepted-step Nielsen update. Existing relative-gain overrides, pre-rejection lambda rebasing and rescued-step lambda freezing remain. Thus this is not a replacement with textbook LM. The feature is limited to fixed-menu FP64, unshared 9-parameter cameras and L2, without point feedback or replay; paired demand mode would override that camera update and is rejected explicitly. Defaults remain off.

Independent CPU central differences of the nonlinear projection, with an independently implemented rotation retraction, check 12 masked/unmasked and mixed-block scaling cases. Maximum normalized discrepancy is `3.81e-10`; Compute Sanitizer reports zero errors. Exact prediction can improve the meaning of rho without guaranteeing a better nonlinear trajectory, and its extra observation pass must pay for itself in measured time to equal quality.
