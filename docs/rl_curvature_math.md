# Interpreting the curvature features

Let `H = J^T J` and `g = J^T r` at the current BA state, in the same local
coordinates as the solver. Write the quadratic damping metric as `D`, so
the damped equations are `(H + lambda D)d = -g`. Camera and point metrics
can be incorporated in block-diagonal D when their regularization shares
lambda; otherwise use the actual block regularization matrix R below.

## What the directional multiplier identifies

For an inexact, unmodified step define linear residual

```
e = (H + R)d + g.
```

Multiplying by d gives

```
alpha_quad = -g^T d / (d^T H d)
           = 1 + d^T R d / (d^T H d) - d^T e / (d^T H d).
```

Thus even before radius clipping, alpha_quad combines regularization energy
and incomplete-solve error. A large alpha alone cannot prove excessive
damping. If the step is uniformly shortened to `s d`, the multiplier measured
on that actual step becomes `alpha_quad / s`. Camera-only clipping, point
safeguards and retriangulation can change direction as well as scale. This
pilot's feature uses the actual step scored by the incumbent, so these
distinctions matter. The rho feature separately tests nonlinear agreement.

The next more identifiable feature would be the dimensionless pair
`d^T R d / d^T H d` and `d^T e / d^T H d`, with a flag describing modifications
between the solve and scoring. The current pilot does not measure the first
term separately, so it does not claim to identify this decomposition. Adding
its metric-weighted norm may require new GPU reductions; that cost must be
measured, not called free.

## Which spectrum the CG recurrence describes

For fixed SPD A and fixed SPD preconditioner M, PCG is CG on
`B = M^-1/2 A M^-1/2`. In exact arithmetic its recurrence defines a Lanczos
tridiagonal with

```
T_00 = 1 / alpha_0
T_ii = 1 / alpha_i + beta_(i-1) / alpha_(i-1)
|T_(i,i-1)| = sqrt(beta_(i-1)) / alpha_(i-1).
```

The off-diagonal sign does not affect eigenvalues. Ritz values are projections
onto the explored Krylov subspace; shallow solves can miss weak directions,
and finite precision can lose orthogonality. A small estimated condition
number does not certify a well-conditioned full system. The depth>=4 mask
is an experimental heuristic, not an error bound. The host test recovers
the complete spectrum on a small dense preconditioned SPD problem and checks
that invalid and short recurrences are not used.

In this solver A is the scaled damped Schur operator. Before camera scaling,
its coupled-damping form is

```
S(lambda) = U + lambda D_c - W (V + lambda D_p)^-1 W^T.
```

Both point elimination and the preconditioner vary with lambda between
solves. Subtracting lambda from these Ritz values does not recover the
undamped spectrum. A failed curvature test invalidates the current summary;
every retry starts a separate recurrence. There is no cross-shift spectral
reuse or extra matrix-vector product in this pilot.

## What a performance result would establish

Predictive features, a lower one-step cost, and a faster complete trajectory
are different claims. Policies here act on prior-outer features and must be
evaluated through their future geometries. Matching action limits and search
budgets across feature classes controls those choices, but does not prove
that either finite controller class is optimal. A negative result rules out
these tested controllers, not every curvature-informed learned policy.
