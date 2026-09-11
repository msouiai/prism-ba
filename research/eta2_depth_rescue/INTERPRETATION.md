# What the depth experiment can establish

## Residual accuracy is not a nonlinear stopping certificate

For an SPD reduced system A x = b, the quadratic gap at an inexact solution
is r^T A^-1 r / 2. Thus a Euclidean residual tolerance alone does not bound
the model gap independently of small eigenvalues. This motivates tighter CG,
but neither the linear residual nor FTOL establishes nonlinear stationarity.

Conversely, high damping can make A approximately lambda I (or its block
preconditioned counterpart). Then one PCG iteration can be an accurate solve
whose nonlinear progress is tiny. Two failed Final3068 stopping probes show
this exact operational signature: residual ratios below 1e-3 after one
iteration, with very small allowed camera movement. Raising the cap again
would not change their residual-based stopping decision.

## Radial clipping can discard the benefit of a better solve

Eta2 computes a camera direction x, then clips it to alpha x with
alpha = min(1, R / ||x||) and back-substitutes points for that camera step.
The better Krylov minimizer before clipping need not be better after clipping.
The full nonlinear acceptance gate remains necessary, including for points.

At three failed Final3068 stopping confirmations the observed tuples
(raw camera norm, allowed radius) are approximately
(308.47, 5.28e-4), (1.115, 5.16e-7), and (18.564, 2.01e-9).
The deep direction retains fractions about 1.71e-6, 4.63e-7 and 1.09e-10.
The latter two probes are accepted but do not reach the registered target.
The first is rejected even though the raw linear residual meets the tighter
tolerance. These observations refute the sufficiency of this stop-only
confirmation on these three states, not every possible depth-based policy.

## Damping and radius encode shared controller history

Away from its interior-step exception and numerical clamps, Eta2 updates

    lambda_next = lambda * (R_old / R_next)^2.

Consequently lambda*R^2 is invariant under that part of the controller.
A quarter-radius rejection raises lambda sixteenfold; a doubled-radius
accept reduces lambda fourfold. An eight-small-step stop can therefore fire
while the controller is still recovering from severe radius contraction.

The proposed stopping probe restores an earlier damping center but retains
the current radius. It consequently does not reverse that coupled controller
history. This is a stronger follow-up hypothesis than simply requesting more
CG iterations. A future registered intervention could save and restore the
(lambda,R) pair at a meaningful-progress boundary, subject to the numerical
floor and a fresh nonlinear acceptance check. A matched radius-only versus
depth-only versus pair-restoration test is needed for attribution. It has
not been measured in this experiment; no improvement is claimed for it.

## Venice probes encounter a different obstruction

All ten conditional de-clipping probes fire after outer 39 and encounter the
existing PCG curvature cutoff in 10–55 iterations. None meets the requested
linear residual tolerance. This experiment conservatively rejects such
probes and leaves the normal solver's numerical-repair floor unchanged.

The cutoff tests pAp > 1e-14*pp, so a failure may be tiny positive curvature,
strictly negative curvature, or nonfinite arithmetic. The current probe log
does not distinguish those alternatives. In exact arithmetic damped
Gauss–Newton normal equations should be positive definite after positive
damping, but the implementation mixes float32 cross fragments with other
double-precision terms and eliminates points by subtraction. That makes a
numerical curvature audit appropriate; it does not establish the cause.

Two truncated trial steps had lower true cost and passed the model/radius
checks before the explicit conservative truncation veto. Thus these results
do not rule out a Steihaug-style truncated-candidate policy. Testing that
would require a separately registered arm; silently accepting it here would
change the tested mechanism after seeing outcomes. The useful next audit is
the failed Rayleigh quotient against a higher-precision operator at the same
state, before tuning deeper budgets or expanded radii further.
