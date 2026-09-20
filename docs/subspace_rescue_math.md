# Coupled camera–point rescue in a two-direction subspace

This experiment solves a restricted convex quadratic exactly in real arithmetic, then tests its proposal against the original nonlinear objective. It does not infer a new lambda from a scaled step and does not claim full-space trust-region convergence.

## Context and motivation

The preceding large-scene trace shows repeated rescued steps with camera damping frozen. Correcting rho only on ordinary accepts leaves that branch untouched. Earlier point-only contraction roots were accurate conditionally but failed after recoupling cameras. The present experiment changes the immediate rescue direction while keeping the existing damping controller, so it tests a different, precisely defined mechanism.

Low-dimensional model minimization is established optimization practice. [Byrd, Schnabel and Shultz (1988)](https://link.springer.com/article/10.1007/BF01580735) study two-dimensional approximations to spherical trust-region subproblems. Only the publisher abstract was accessed here; its convergence statements must not be transferred to the different box, directions and acceptance policy below. [Ceres' official documentation](https://ceres-solver.readthedocs.io/latest/nnls_solving.html) describes the GN residual model and the distinction between line search and trust-region step control. Neither reference establishes novelty or guarantees for this prototype.

## Exact projected model

At one fixed state and failed menu direction `d=(d_c,d_p)`, define observation-space directions

```
u = J_c d_c,   v = J_p d_p,
g_c = r^T u,  g_p = r^T v,
A = u^T u, B = u^T v, C = v^T v.
```

The GN objective change along the separately scaled step is

```
q(a,b) = g_c a + g_p b + (A a^2 + 2 B a b + C b^2)/2.
```

Its Hessian is the Gram matrix of `[u v]`, hence positive semidefinite and `B^2 <= AC` by Cauchy–Schwarz. The cross term is measured directly, not dropped or approximated by separate damping responses. These identities hold for any supplied direction, even when its generating CG solve is inexact.

Minimize `q` on `0<=a,b<=1`. The box allows contraction of either block, including freezing one, but no growth or sign reversal. It is a fixed restriction in coefficients of the existing direction, not a radius in a full-space damping metric.

## Global box solution

For fixed `a` on either vertical edge, the minimizing `b` is `clip(-(g_p+B*a)/C,0,1)` when `C>0`. When `C=0`, choose an endpoint by the linear slope. The analogous formula solves horizontal edges. Corners are therefore covered. For a positive determinant, the unconstrained stationary point is

```
a = (B*g_p-C*g_c)/(A*C-B^2),
b = (B*g_c-A*g_p)/(A*C-B^2).
```

Include it if feasible. Compare these candidates with the origin. Convexity establishes global optimality: any interior optimum with a nonsingular Hessian is this stationary point; a singular Hessian has a flat null direction at an interior optimum, which can be followed to a boundary optimum. Purely linear and zero models are handled by the edges/origin.

The C++ implementation also explicitly includes the best uniform point `(t,t)`:

```
t = clip(-(g_c+g_p)/(A+2B+C),0,1),
```

with linear/zero-curvature endpoint handling. All coefficients are normalized by their largest magnitude and the tiny host solve uses long double. A roundoff-size excess beyond the Gram coupling bound is clipped; materially unusable/nonfinite coefficients are rejected. The final prediction and slope are re-evaluated using the original coefficients, and must be finite with positive predicted decrease and negative slope. This is numerical safeguarding, not a formal floating-point optimality certificate.

## What follows, and what does not

The box contains every uniform contraction in `[0,1]`. Therefore its minimum model value is no greater than the optimal scalar model value or any original dyadic model value. This is a same-state, same-direction statement, not a comparison of nonlinear costs or future trajectories.

A strictly negative `q(a,b)` under a PSD Hessian implies negative first-order slope `g_c*a+g_p*b`, since the quadratic term is nonnegative. Nevertheless the actual residual is nonlinear. The implementation requires

```
F(Retract(d(a,b))) < F(current),
F(Retract(d(a,b))) <= F(current) + 1e-4*(g_c*a+g_p*b).
```

If the proposal fails, all eight original dyadic uniform fallbacks remain available. Thus the proposal adds at most one nonlinear evaluation to a rescue search, making the explicit bound nine rather than eight. The old fallback directions, acceptance rule and order are unchanged if the new proposal fails at that state. An accepted new proposal changes the state, so no global trajectory dominance is asserted. A finite fallback menu alone is not a convergence proof.

A global convex subproblem optimum can still be a poor nonlinear proposal. For example, starting at `(0,0)` with residuals `(1-a+K*a^2, 1-b)` and `K=10`, the linear model prefers `(1,1)` but its true objective increases from 1 to 50. A smaller uniform step such as `(1/8,1/8)` decreases the objective. The nonlinear Armijo gate is therefore essential even with exact box minimization.

## Implementation and scope

`gpu/subspace_model.cuh` computes the five coefficients in one observation pass with a 40-byte persistent reduction buffer. No new per-observation or full-step buffer is allocated; existing candidate buffers are reused. The pass runs only when the original menu failed, backtracking is ready and the existing full-direction slope is negative.

`OCA_SUBSPACE_RESCUE=1` proposes the uniform quadratic minimizer; `2` proposes the box minimizer; `3` audits coefficients and the box minimizer without changing behavior. All modes are off by default. Original backtracking, FP64 unshared CD9 L2 are required. Point-feedback, corrected full-rho, replay and alternative backtracking policies are explicitly incompatible. Paired demand is permitted: rescued status and the winning step are carried through fallback, while scalar rescue alpha has no damping-feedback consumer in the allowed configuration.

The existing rescued-step lambda freeze remains. Consequently a successful result would support better immediate candidate selection, not a repaired damping-update theorem. Scalar and box arms share the same GPU pass and acceptance gate, isolating the value of independent block scaling.

## Independent checks

The host test verifies the C++ solution on 2,003 models including collinear, opposite, zero and highly anisotropic directions, and coefficient scales over 200 orders of magnitude. Independent projected KKT residuals and 40,060 random feasible comparisons verify optimality; explicit comparison verifies scalar dominance. GPU coefficients are checked against independently implemented central differences of camera-only and point-only nonlinear retractions, including k2 masking and partial CUDA blocks. Recorded results and limits are in the companion results report.

## Recorded amendment: calibrate the observed model error

The original screen accepted none of its 483 scalar/box proposals. The GN optimum generally remained the full step that the nonlinear objective had already rejected. The remaining experiment therefore fits the observed discrepancy rather than solving that same GN model more accurately.

Let `delta=F(Retract(d))-F(current)` be the already available failed full-step cost change. Define

```
E = max(0, delta-q(1,1)),
q_E(a,b) = q(a,b) + E*max(a,b)^2,    0<=a,b<=1.
```

When E is positive this model matches the observed full-step cost change exactly, preserves the gradient at the origin, and remains convex because the squared nonnegative maximum is convex. A nonfinite rejected-step cost cannot calibrate E and falls back without a proposal. A single observed discrepancy does **not** identify a full nonlinear error surface; this choice is an explicit surrogate, not an upper bound on true cost away from `(1,1)`.

For uniform scaling, its minimizer has

```
t = clip(-(g_c+g_p)/(A+2B+C+2E),0,1).
```

With positive E, substitute its definition to obtain

```
t = clip(-(g_c+g_p)/(2*(delta-g_c-g_p)),0,1).
```

Thus the scalar ablation is exactly quadratic interpolation from the current value/slope and observed full-step value. There is no fitted scene-specific coefficient. It is related to the earlier interpolation work, but proposes a continuous step here instead of rounding to a dyadic menu index.

The coupled problem splits into two triangles. On `a>=b`, replace A by `A+2E`; on `b>=a`, replace C by `C+2E`. Enumerate the stationary point in each triangle and its edges: the diagonal, either zero-coordinate edge, and either unit-coordinate edge. These cover all minimizers of the convex piecewise quadratic. Include the scalar optimum explicitly, so model dominance over calibrated scalar scaling still holds.

`OCA_SUBSPACE_RESCUE=4` uses calibrated scalar interpolation; `5` uses the calibrated box. Both share the same five GPU coefficients and at most one extra nonlinear cost evaluation. The kernel is unchanged from the finite-difference/memory-checked implementation; the new host solver is independently checked on 2,002 models with nonsmooth projected-subgradient KKT checks and 40,040 random feasible comparisons. Worst normalized KKT residual is `2.23e-16`. Numerical validity checks and the original fallback remain.

The ability to fit a rejected step without another observation pass makes this a cheap hypothesis to test. It does not prove that independent camera/point coefficients model the actual nonlinear error better than the scalar interpolation control. That distinction must come from the fixed comparison.

## Certificates explaining the BA outcomes

For the raw convex quadratic, `(1,1)` is a global box minimizer whenever

```
g_c + A + B <= 0,   g_p + B + C <= 0.
```

These are exactly the upper-corner KKT inequalities. They hold, within the recorded numerical tolerances, for all 31 audit models. Thus the repeated full-step proposals are not a failure of the 2x2 optimizer: they are the correct solution of an inadequate local model on this box.

For the calibrated model, let t be its scalar optimum with `0<t<1` and `E>0`, and set

```
u = g_c+t*(A+B),   v = g_p+t*(B+C).
```

At `(t,t)`, the penalty subgradient is `2*E*t*(theta,1-theta)`, `0<=theta<=1`. Scalar stationarity gives `u+v+2*E*t=0`. If both u and v are nonpositive, choose `theta=-u/(2*E*t)`. The resulting full subgradient is zero, proving that uniform scaling is also a global coupled optimum. This is sufficient; uniqueness is not required.

`bench/check_subspace_certificates.py` verifies this certificate on all 107 single-shift Dubrovnik calibrated box models and 60 of 61 five-shift models. The box can move independently on Ladybug (11 of 19 single-shift and 39 of 47 five-shift proposals), but those extra degrees of freedom still do not establish a nonlinear performance gain.

The calibrated Dubrovnik median scale is approximately `1.4e-4` with one shift and `1.0e-4` with five. Both are far below the smallest original eight-step dyadic trial, `1/256`. Accepting a tiny Armijo step prevents that search from reaching the original fallback or its rejection-driven damping change. The Armijo decrease condition alone permits arbitrarily small progress, and the retained rescued-step lambda freeze compounds the issue. These are observed/proved limitations of the present policy, not justification for choosing another arbitrary minimum scale.
