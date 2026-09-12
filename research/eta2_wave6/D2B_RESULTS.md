# D2b result: the large opening amplification is a finite numerical jump

## Registered verdict

Both scenes satisfy the preregistered **finite-jump plateau** rule.  Across five
perturbation doses from `1e-8` to `1e-12`, the absolute separation after ten
accepted outers is essentially independent of perturbation size:

| Scene | D10 at 1e-8 | 1e-9 | 1e-10 | 1e-11 | 1e-12 | all-dose slope | smallest-three slope / ratio |
|---|---:|---:|---:|---:|---:|---:|---:|
| Venice52 | 0.00634 | 0.00656 | 0.00610 | 0.00576 | 0.00679 | -0.0004 | -0.0235 / 1.18x |
| Final3068 | 175.6 | 179.9 | 133.0 | 114.1 | 153.1 | 0.0317 | -0.0305 / 1.34x |

The registered plateau gate requires a smallest-three-dose slope at most 0.25
and a D10 ratio at most 3.  Both pass by a wide margin.  A differentiable map in
the linear perturbation regime would instead preserve `D10/epsilon` and produce
a slope near one.  Therefore the D2 `A10` values as large as 35,906 are not a
finite-time Lyapunov exponent of the mathematical Eta2 iteration.  They divide
a finite arithmetic/discrete jump by an ever smaller input perturbation.

## When the jump appears

The per-outer fitted slope makes the transition visible:

| Outer | Venice slope | Final3068 slope |
|---:|---:|---:|
| 0 | 1.000 | 1.000 |
| 1 | 0.882 | 0.998 |
| 2 | 0.649 | 0.993 |
| 3 | 0.475 | 0.960 |
| 4 | 0.373 | 0.528 |
| 5 | 0.282 | 0.420 |
| 6 | 0.129 | 0.695 |
| 7 | 0.032 | 0.173 |
| 10 | -0.0004 | 0.032 |

Final3068 remains almost perfectly linear through outer three, then crosses
algorithmic branches.  Depending on dose, 1--4 of four pairs change a global
accept/reject decision by outer ten, and most change a CG-depth choice.  The
finite jump later drives the controller, so soft acceptance could change the
subsequent branch, but it is not the source of the initial loss of smoothness.

Venice is cleaner and more revealing.  Across all 20 pairs, the global
accept/reject sequence and CG depths remain identical through outer ten.  Even
eight individual pairs whose aggregate point-safeguard choices also remain
identical end on the same approximately 0.006 plateau.  The discontinuity is
therefore below the logged controller and safeguard choices.  The frozen path
stores its camera/point Jacobian fragments in FP32 while state, reductions and
acceptance are FP64; rounding of those fragments is the leading testable source.

## Consequence

The campaign should not claim chaotic opening dynamics from D2.  Deterministic
reductions make the map reproducible, but not continuous: fixed-order IEEE
rounding and FP32 fragment quantisation can still map arbitrarily close states
to a finite separation after several nonlinear iterations.

Before soft/filter acceptance or another controller is tested, run a diagnostic
FP64-fragment Venice ladder with every other deterministic choice fixed.  If
the slope returns to one, fragment quantisation is the source.  If the plateau
persists, localise the next finite-precision boundary.  Final3068's acceptance
split can then be revisited after the numerical jump is understood.

The provisional trace summarizer initially compared complete floating-point
log lines and labeled every changed `rho` as a decision split.  The preserved
logs were reparsed into accept/reject bits, discrete CG tuples, and discrete
point-safeguard tuples before this report.  Distances, slopes and classifications
were unchanged.  Full rows are in `d2b-results.json`; compact statistics are in
`d2b-summary.json`.
