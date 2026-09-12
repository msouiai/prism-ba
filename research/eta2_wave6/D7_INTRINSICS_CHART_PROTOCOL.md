# D7 protocol: focal-depth camera chart

Registered before computing any transformed-chart statistic or proposal.

## Question

The five archived Venice terminal states are dominated by camera 34.  Its
weakest local reduced direction is approximately 53.4% optical-axis
translation and 46.3% focal length in Eta2's scaled coordinates, even though
the camera has 2,959 observations.  D6 confirmed the same direction through
the exact gauge-quotient posterior covariance.  D7 asks whether this geometric
starvation is primarily a coordinate effect: perspective observations often
constrain the ratio `q = t_z / f` more directly than additive `t_z` and `f`.

This is a fixed-state diagnostic.  It does not change the frozen champion and
does not launch an optimizer rollout unless the gate below passes.

## Frozen charts

All rotation, transverse-translation, distortion and point coordinates remain
unchanged.  The two candidate camera charts are fixed in advance:

1. `ratio-linear`: `(q, f)`, with `t_z = q f` and additive `f`;
2. `ratio-log`: `(q, ell)`, with `t_z = q exp(ell)` and `f = exp(ell)`.

At the current state their tangent-to-physical maps on rows `(t_z, f)` are

```
ratio-linear: [[f, t_z/f], [0, 1]]
ratio-log:    [[f, t_z  ], [0, f]]
```

The retractions use the nonlinear definitions above, rather than applying the
linear tangent map as an additive physical step.  The existing additive
`(t_z, f)` chart is the control.  Focal lengths must be finite and positive;
otherwise the candidate is invalid rather than silently repaired.

## Fixed states and reconstruction

Use exactly the five `venice-terminal-0..4` archives and the selected attempt 2
from the three successful-opening archives used by D6.  Rebuild the coherent
FP64 point-damped Schur model from the original Venice52 observations and each
captured state.  Include the frozen champion's physical focal and distortion
priors, remove inactive `k2`, and verify the additive diagonal equilibration
against the captured `E`.

For a chart with block-diagonal tangent map `T`, form

```
S_y = T^T S_x T,       b_y = T^T b_x,
E_y = diag(S_y)^(-1/2),
(E_y S_y E_y + lambda I) z_y = E_y b_y.
```

Solve this small diagnostic system by dense FP64 Cholesky to relative residual
below `1e-10`; this isolates the chart and damping metric from CG truncation.
Back-substitute points from the resulting physical camera direction.  If the
scaled direction exceeds the captured radius, radially clip it before point
back-substitution, matching the champion.  Evaluate prediction on the actual
joint tangent and true cost on the chart's nonlinear retraction.  Also map the
champion's captured raw physical direction into each candidate's scaled metric;
this separates a metric effect from a changed damped solve.

## Reported quantities

For every state and chart report:

- `||z_raw||/R`, the top camera and its squared-energy fraction;
- the fraction of healthy-camera physical step retained after clipping;
- predicted decrease, true decrease and rho for the recompleted clipped step;
- camera 34's local scaled condition number, weakest-vector loading on the two
  chart coordinates, and their normalized Hessian correlation;
- the same quantities when only the captured champion direction is re-expressed
  in the chart metric.

The opening states are negative controls: their recorded ratio is about 1.55
and their rejected motion is distributed rather than camera-34 dominated.

## Gate

A native `ratio-log` arm is justified only if all of the following hold:

1. in at least four of five terminal states it reduces the re-expressed
   captured-direction radius ratio by at least 10x **and** retains at least 10x
   more healthy-camera physical motion after clipping;
2. in at least four of five terminal states, its exact damped clipped proposal
   has strictly larger true decrease than the additive exact control, with
   finite positive prediction;
3. camera 34's weakest local mode has at least 90% loading on one of `(q, ell)`
   and its diagonally scaled local condition number improves by at least 10x in
   at least four of five terminal states;
4. none of the three opening controls acquires `||z_raw||/R > 2`, and none loses
   more than 0.15% of the additive control's true decrease.

`ratio-linear` is an explanatory control and cannot be promoted by this screen.
If the gate fails, stop.  A coordinate chart that merely rotates the reported
weak eigenvector, without improving the trust metric and true proposal, is not
an algorithmic result.

## Reproducibility

Record hashes of this protocol, the analysis, BAL input, every archive and each
consumed archive member.  Restore only under `/dev/shm`, validate the existing
manifests, and remove restored files after each case.
