# D8 protocol: rank-one residual tensor model

Registered before restoring states or evaluating any tensor-model prediction.

## Question

Does a rank-one secant tensor model predict Eta2's committed steps more
faithfully than its Gauss--Newton residual model in the Final3068 plateau and
retry regime?  This is the gate for building a native tensor step.  It is not
outer extrapolation: the prior accepted state supplies an interpolation
condition for the residual model at the current state.

The construction follows Bouaricha and Schnabel's sparse nonlinear
least-squares tensor method:

<https://ftp.mcs.anl.gov/pub/tech_reports/reports/P552.pdf>

Their model uses one or two past directions and a minimum-Frobenius-norm,
low-rank tensor.  The registered screen uses `p=1`, the sparse case they report
as the practical default.  Regularized tensor-Newton methods are a distinct
modern family; this screen does not claim to implement their full-Hessian
method:

<https://www.numerical.rl.ac.uk/media/people/jennifer-scott/GouldReesScott_COA_2019.pdf>

## Frozen trajectory and state selection

Use the deterministic FP32-fragment Eta2 measuring binary from D0 with the
wave-5 B6v7 flags.  Regenerate D3's perturbation seed `640005` at epsilon
`1e-10`.  This is the first miss in D3's registered sequential order, selected
from its recorded control outcome before D8.  Its required input SHA256 is
`522398e82dae465e94d929acb29cabcb44c10f896b0b68eadc5f75a5997b39ea`;
the previous run stopped at outer 52 with independently rescored cost
`1812797.3488586906`.

Replay once and retain exact binary states only at the union of outer
boundaries needed for current indices

```
k = {37, 40, 43, 47, 51}, with states k-1, k, and k+1.
```

The indices were selected from the existing cost/controller trace to span the
onset of the plateau, an ordinary weak step, the low-rho retry branch, a later
retry, and the terminal step.  They were not selected using tensor results.
The replay must reproduce every old scalar cost and the prior endpoint-state
SHA256 exactly; otherwise the screen is invalid.

## Tensor model

At current state `x_k`, express both `s = x_(k-1)-x_k` and
`d = x_(k+1)-x_k` in the code's local tangent: left-log rotation and additive
translation, focal length, radial distortion and Euclidean point coordinates.
Drop the fixed `k2` coordinate.  Reapplying each tangent through the native
chart convention must reconstruct its state to a relative residual-space
error below `1e-9`.

Use the current coherent FP64 Jacobian and the champion damping metric `D`:
the point diagonal uses the native `max(diag(V), 1e-3 mean(diag(V)))` rule, and
the camera diagonal is the diagonal of the coherently point-damped Schur
operator at that attempt's recorded `tau=lambda`.  In whitened coordinates,

```
s_hat = sqrt(D) s
d_hat = sqrt(D) d
e     = r(x_(k-1)) - r(x_k) - J_k s
a     = 2 e / ||s_hat||^4
M(d)  = r(x_k) + J_k d + 0.5 a (s_hat^T d_hat)^2.
```

The implementation must verify interpolation by evaluating `M(s)` against
the previous residual vector.  Residual ordering, observations, SIMPLE_RADIAL
model, unshared intrinsics and `k2=0` stay identical to the scored objective.

## Measurements and gate

For the actual committed transition at each registered `k`, compare GN and
tensor predictions against `r(x_(k+1))`:

- relative residual-change error
  `||r_next-r_model|| / max(||r_next-r_current||, tiny)`;
- absolute scalar cost-prediction error, normalized by the actual absolute
  cost change;
- predicted versus true decrease and whether each model gets its sign right;
- `D`-metric cosine and norm ratio between the previous and next directions;
- fraction of the tensor correction concentrated in the top 200 observations.

The full `p=1` tensor solve is earned only if all of these hold:

1. tensor residual-change error is at least 20% lower than GN at three of five
   transitions and lower in the median;
2. tensor normalized cost-prediction error is at least 20% lower than GN at
   three of five transitions and lower in the median;
3. the tensor prediction has the correct decrease sign at least as often as
   GN, and neither error metric is more than twice GN on any transition;
4. interpolation and state-reconstruction certificates pass everywhere.

If the gate passes, build the analytic `p=1` sparse tensor step using three
damped normal solves and test it at the same states before any native rollout.
If it fails, stop: secant curvature from the immediately preceding accepted
state does not model the trajectory's useful nonlinearity, so the extra solves
have no supported payoff.

## Scope

This is deterministic fixed-trajectory mechanism evidence, not a convergence
or speed claim.  A native candidate, if earned, still requires the standard
paired tails and nine-cell time-to-target protocol.  The frozen scientific
champion and optimized B6v7 candidate remain untouched.
