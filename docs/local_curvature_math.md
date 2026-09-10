# Fixed-state nonlinear curvature in camera–point directions

This study measures the original full BA objective on exact saved states and directions. Its secant models are diagnostic approximations, not a new convergent BA solver. Standard GN modeling and step control are described in [Ceres' official nonlinear least-squares documentation](https://ceres-solver.readthedocs.io/latest/nnls_solving.html). The projected derivatives, interpolation formulas and limits below are derived for the specific two-parameter path used here.

## 1. A fixed path makes the question identifiable

Save one state and failed direction `(d_c,d_p)`. Define

```
phi(a,b) = F(Retract(a*d_c,b*d_p)),   phi(0,0)=F0.
```

The rotation update is left multiplication `Exp(a*[omega]_x)*R`; translation and intrinsics receive the scaled camera increments, and points receive `b*d_p`. With `RX=R*X`, `RdX=R*d_p`, the observation's camera-space coordinates are

```
q(a,b) = Exp(a*[omega]_x)*(RX+b*RdX) + t+a*dt.
```

BAL projection is `-q_xy/q_z`, followed by focal scaling and radial distortion. Thus phi is smooth in a neighborhood that excludes zero depth, but can vary sharply as depths approach zero. No cheirality constraint or robust loss is introduced by this study.

For fixed cameras, depth is exactly linear in b: `z(b)=z0+b*(RdX)_z`. A positive root `-z0/(RdX)_z` identifies a point-only projection pole along the path. For the joint path, opposite endpoint depth signs imply an intermediate zero by continuity. Equal endpoint signs do not exclude an intermediate zero; endpoint sign checks are not a full path certificate.

## 2. True curvature versus GN curvature

Write the residual vector along this path as r(a,b). At zero,

```
g_i = r^T r_i,
H_true[i,j] = r_i^T r_j + r^T r_ij.
```

The existing five GPU coefficients supply g and `H_GN[i,j]=r_i^T r_j`. The omitted residual-curvature term can be positive or negative. The true projected Hessian can therefore be indefinite even though the GN Gram matrix is positive semidefinite. The derivatives include the chosen rotation retraction's curvature; they are not simply Euclidean camera-coordinate derivatives.

A single observed full-step discrepancy cannot identify three Hessian entries. Even if the path were exactly quadratic, it supplies only a combination proportional to `H_cc+2*H_cp+H_pp`. Adding any symmetric matrix `[[t,s],[s,-t-2s]]` leaves that combination unchanged. A full-step observation also contains higher-order terms. Fitting one scalar penalty to it therefore imposes additional assumptions about independent block curvature that the observation does not determine.

## 3. Three local measurements

With g known, evaluate `phi(h,0)`, `phi(0,h)` and `phi(h,h)`. The unique quadratic matching these values and the gradient has

```
A_h = 2*(phi(h,0)-F0-h*g_c)/h^2,
C_h = 2*(phi(0,h)-F0-h*g_p)/h^2,
B_h = (phi(h,h)-phi(h,0)-phi(0,h)+F0)/h^2.
```

Under sufficient smoothness, one-sided Taylor expansion gives `H_h = H_true + O(h)`. This is local and asymptotic: it says nothing across a projection pole or when the chosen h is not in the local regime. Finite precision also introduces cancellation proportional to approximately `epsilon*F0/h^2`. Smaller h is not automatically better.

The radii `.5`, `.125` and `.03125` were frozen before measurements; `.125` is the primary radius. Four validation points at fractions `(.25,.75)`, `(.75,.25)`, `(.25,.25)` and `(.75,.75)` of each radius are excluded from fitting. Model errors are absolute prediction errors divided by `max(1,abs(g dot [a,b]))`. The denominator is the local linear scale, not the current total objective, so a large constant cost cannot hide a poor model.

The scalar control uses only `phi(h,h)` and `g_c+g_p`, then minimizes its interpolating quadratic on `[0,h]`. Its curvature equals the sum of all entries of the coupled secant matrix by construction. The coupled model pays for two additional axis measurements and must provide value beyond this cheaper scalar fit.

## 4. Global minimization of an indefinite 2x2 box model

Minimize `g^T z + z^T H_h z/2` on `[0,h]^2`. The compact box ensures a minimum even if H is indefinite. Enumerate all four corners and the stationary minimum on each edge when its one-dimensional curvature is positive; nonpositive-curvature edge minima occur at endpoints. Include a feasible interior stationary point only when H is positive definite. Singular interior minima have a flat direction reaching the boundary; an indefinite interior stationary point cannot be a local minimum.

This yields a global solution in exact arithmetic. Host calculations use long double for the candidate arithmetic, but there is no formal floating-point optimality certificate. An independent test checks 2,000 symmetric models, including 1,389 indefinite cases, against 5.2 million feasible grid points and necessary projected KKT conditions. Maximum KKT residual is `5.56e-17`.

The same-box coupled model minimum cannot exceed the scalar model minimum, but actual nonlinear cost can. Every proposed point is evaluated on all original observations and must pass the original negative-slope Armijo condition. The comparison also retains the original first accepted dyadic rescue among `.5,...,1/256`; beating a scalar surrogate is not sufficient to beat the existing rescue.

## 5. Independent derivative and state checks

States retain raw rotation matrices, positions and intrinsics in the existing `PRISMS01` format. Directions are stored separately without parameter conversion. CPU retraction uses an independent Rodrigues implementation, with sinc formulas stable near zero. Original-state and rejected-full-step CPU costs are compared with their GPU measurements.

Residual-direction central differences check the projected coefficients at epsilons `1e-6` and `1e-7`. One small Venice camera-gradient combination is cancellation-sensitive at those epsilons. A separately derived analytic CPU derivative supplies a stronger audit without relaxing the coefficient threshold:

```
dq_c = omega cross RX + dt,   dq_p = RdX,
d(-q_xy/q_z) = -(dq_xy*q_z-q_xy*dq_z)/q_z^2.
```

The radial/focal derivative then follows by the chain rule. Both successful and noisy finite-difference results are retained; they are not all described as passing. Independent analytic coefficients are checked against the five GPU quantities.

## 6. What a local improvement would establish

A lower actual cost on one saved direction is evidence about that state and path only. It does not imply a better next-state damping update, fewer future iterations, lower time to equal quality, or superiority to Caspar. A coupled model can be more predictive yet propose a smaller, less useful step because its box is smaller than the already-successful original rescue.

An optional model improvement after saving the original accepted rescue could preserve the better actual candidate at the current state. That safeguard proves only same-state cost non-increase relative to the saved rescue; it does not pay for the extra observation passes or establish trajectory dominance. This study measures those costs and opportunities before implementing an online policy.

## 7. Concentrated error suggests a separable nonlinear diagnostic

After measuring concentration of positive full-step GN prediction error, an additional fixed-state diagnostic was recorded in `pointwise-diagnostic-protocol.json`. It does not replace the failed online gate for the secant model.

For fixed camera parameters, the L2 BA objective separates by 3D point:

```
F(cameras,X) = sum_p F_p(cameras,X_p),
F_p = 1/2 sum_{observations of p} ||residual||^2.
```

Fix a camera scale a and give each point a finite menu of scales B. Then

```
min_{b_p in B for every p} sum_p F_p(cameras(a),X_p+b_p*d_p)
  = sum_p min_{b in B} F_p(cameras(a),X_p+b*d_p).
```

This is an exact separability identity, not a quadratic approximation. Selection must sum the **entire track** of each point before choosing its scale; choosing independently per observation would not correspond to a valid common 3D point.

The diagnostic menu is `{0,alpha/2,alpha,.5,1}`, where alpha is the original accepted uniform rescue. Camera scales are `{alpha,1}`. At camera scale alpha, the original point configuration is feasible because alpha belongs to the menu, so the optimized track sum cannot exceed the original rescue cost at that state. A reconstructed mixed step is checked independently on every observation and must satisfy the original negative-slope Armijo gate; otherwise the original rescue is retained.

The full mixed slope is `a*g_c + sum_p b_p*g_p_projected`, with each point's projected gradient accumulated across all its observations. This differs from using one global point slope times a single scale.

Non-regression relative to the saved rescue is by construction in this diagnostic. A material additional decrease would nevertheless identify a useful mechanism: allowing well-behaved points to move without forcing them to share the scale needed by a few problematic tracks. It would not establish a faster BA rollout. The menu costs up to ten full observation-equivalent evaluations across the two camera scales before reuse/fusion, and a future GPU implementation would need grouped track reductions. This is related to established nonlinear inner/coordinate optimization, not a claimed new general optimization principle.

## 8. The minimal zero/full point safeguard

A final fixed-state work ablation fixes the camera scale to one and restricts each point to `{0,1}`. This requires only two track-cost values per point. It has the exact bound

```
sum_p min(F_p(cameras_full,X_p), F_p(cameras_full,X_p+d_p))
  <= F(cameras_full,X+d_p).
```

It need not beat the original uniformly scaled rescue, so that rescue is explicitly retained and compared. A midpoint menu `{0,.5,1}` tests whether interpolation adds enough value to justify another point-cost evaluation. These are pre-recorded menu ablations, not scene-specific scale tuning.

The mixed full-camera candidate must also pass the full projected-slope Armijo check. Even a passing pointwise candidate can be worse than the original rescue; that occurs on the late Venice capture. An online implementation must preserve the original candidate comparison rather than accepting the first cheaper-looking pointwise step immediately. Same-state cost protection does not establish rollout convergence or speedup.
