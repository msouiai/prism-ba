# D2b protocol: perturbation-scale ladder for the opening map

Registered before generating or running the new perturbation doses.

The D2 result cannot be called a positive finite-time Lyapunov exponent because
`epsilon=1e-12` and `1e-10` disagree in amplification.  D2b holds the binary,
flags, directions, ten-outer horizon, compact-state instrument, and residual-
space metric fixed.  For seeds 620000--620003 on Final3068 and Venice52 it adds
`epsilon` in `{1e-8, 1e-9, 1e-11}` and reuses the registered D2 rows at `1e-10`
and `1e-12` for the same four directions.

For each dose, let `D10(epsilon)` be the median absolute FP64 residual-space
separation after ten accepted outers.  Fit a least-squares line to
`log(D10)` versus `log(epsilon)` over all five doses and also report every
adjacent-decade slope.  The fixed classification is:

- **smooth linear regime:** at least three consecutive doses have slope in
  `[0.75, 1.25]`, their amplification factors agree within 3x, and no discrete
  solver decision differs;
- **finite-jump plateau:** the slope over the three smallest doses is at most
  0.25 and their maximum/minimum `D10` ratio is at most 3;
- **piecewise/ambiguous:** neither condition.

The first differing global accept/reject decision, CG-depth sequence, and
point-safeguard aggregate are retained as mechanism evidence.  A finite-jump
plateau rules out interpreting the large small-dose amplification as a smooth
Lyapunov exponent and prioritises localisation of a rounding or discrete-choice
boundary.  A smooth regime with positive exponent supports map-changing or
portfolio work.  A stable smooth regime supports controller work.

This is a diagnostic only.  It changes no Eta2 algorithm and makes no endpoint,
speed, or novelty claim.
