# D7 result: focal-depth coordinates move the soft mode but do not fix it

## Verdict

The registered native gate fails.  Reparameterising each camera by
`q = t_z/f` and `ell = log(f)` substantially improves the *local* conditioning
of Venice camera 34 and makes the already captured terminal direction much
smaller in the new trust metric.  Once the damped system is solved again in
that metric, however, a different distributed soft direction appears, the
step remains about 331 radii long, and the clipped nonlinear proposal raises
the true cost in all five terminal replicas.  No native rollout is justified.

This separates two claims that looked equivalent before the experiment:

- the additive `(t_z,f)` chart does expose a severe focal/depth correlation;
- aligning that correlation with a more natural chart does not remove the
  global family of soft camera modes that dominates the trust step.

## Registered fixed-state results

All numbers below are medians; the five terminal replicas agree to the shown
precision.  `Captured ratio` re-expresses the identical physical direction in
the coherent chart metric.  `Exact ratio` resolves the registered coherent
FP64 damped system in that chart before clipping.

| terminal chart | captured ratio | exact ratio | clip factor | true decrease | pred | rho | camera-34 scaled condition |
|---|---:|---:|---:|---:|---:|---:|---:|
| additive `(t_z,f)` | 377.245 | 917.380 | 0.001090 | +2.0756 | 8.3758 | 0.2478 | 2.379e8 |
| `(q,f)` | 29.720 | 330.790 | 0.003023 | -23.1229 | 23.4442 | -0.9863 | 1.393e6 |
| `(q,log f)` | 29.720 | 330.790 | 0.003023 | -55.2158 | 23.4442 | -2.3552 | 1.393e6 |

The original mixed-storage capture has `||z_raw||/R = 428.257–428.267`.
Changing coordinates therefore retains 12.693x more of the captured healthy
camera motion after clipping and improves camera 34's local scaled condition
by 170.79x.  Those are real metric effects.  They are not useful steps:

1. the freshly solved ratio-chart direction is still 330–331 radii long;
2. its largest camera becomes camera 15 and carries only about 6.5% of the
   scaled energy, so regularising camera 34 exposes distributed softness;
3. only 42.49% of the new weakest local eigenvector lies in the `(q,log f)`
   pair and its largest coordinate loading is 40.65%, below the registered 90%
   isolation threshold;
4. both registered nonlinear ratio retractions fail true-cost acceptance in
   5/5 terminal states despite a positive quadratic prediction.

The distinction between the two ratio charts is entirely in their nonlinear
retraction at these states: their first-order damped solutions and predictions
are effectively identical, while additive focal length gives `-23.12` true
decrease and log focal length gives `-55.22`.  The log chart adds curvature in
the wrong direction at this step size.

## Opening negative controls

The three archived successful-opening rejection states are identical at the
reported precision, as expected from their controlled captures.

| opening chart | exact ratio | true decrease | rho | camera-34 condition change |
|---|---:|---:|---:|---:|
| additive | 1.6316 | 397,642 | 0.99836 | reference |
| `(q,f)` | 1.6241 | 402,037 | 0.99593 | 1.18x worse |
| `(q,log f)` | 1.6241 | 403,155 | 0.99870 | 1.18x worse |

All three controls pass the registered safety gate: the chart does not create
an oversized opening direction and does not reduce the true decrease.  This
also sharpens the mechanism.  The chart is benign where the solver is already
healthy; it cannot repair the late soft manifold.

## Numerical scope

The coherent FP64 diagonal equilibration differs from the captured
mixed-storage equilibration by 14.69% in relative 2-norm at the terminal states
and 53.67% at the opening states; the largest coordinate-wise differences are
larger.  This is consistent with the separately measured fragment-precision
sensitivity and is why D7 compares all three charts inside one coherent model
rather than claiming native parity.  It also makes the decision conservative:
the preregistered gate already fails on model fidelity and mode isolation, so
there is no basis for paying for a native implementation under the noisier
production operator.

All objective checks, archive hashes, member hashes, baseline source and flag
verification, Cholesky residuals and per-state values are recorded in
`d7-intrinsics-chart-results.json`.  The frozen decision rule is in
`D7_INTRINSICS_CHART_PROTOCOL.md`; the executable analysis is
`analyze_d7_intrinsics_chart.py`.

## Consequence for the categorical map

The untried intrinsics-chart cell is now a measured negative in this direct
form.  It supplied a useful diagnostic coordinate but no solver actuator.
The result reinforces the earlier local-floor result: camera 34 is an obvious
symptom, yet suppressing or re-expressing it reveals other soft modes and does
not make the nonlinear model trustworthy.  The next categorical-map work
should therefore return to linear-algebra throughput or to measurement and
portfolio reliability, rather than another local camera regulariser.
