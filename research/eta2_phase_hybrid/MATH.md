# What the prototype solves

The later [metadata reconciliation](METADATA_RECONCILIATION.md) gives Claude's
exact diagnostic definition. It uses pair-specific normalization, so even our
raw diameter differs before applying radius clipping. The experimental
threshold and measurements below have not been retroactively changed.

Write the frozen Gauss–Newton blocks as U, W, V and gradients as g_c, g_p.
Let V_tau denote the exact damped, safeguarded point factor used by Eta2,
including its existing floor rules. Eliminating the point increment gives

    S_tau = U - W V_tau^{-1} W^T
    b_tau = g_c - W V_tau^{-1} g_p.

With the native diagonal camera equilibration E, the sweep solves

    (K + lambda_j I) y_j = b',
    K = E S_tau E,  b' = E b_tau,
    lambda_j = lambda_center * [0.01, 0.1, 1, 10, 100].

The physical camera increment is -E y_j; point back-substitution uses the same
V_tau for every lane. Radius clipping occurs in y coordinates before point
back-substitution and nonlinear scoring. In particular, clipping the camera
part is not a uniform scaling of the entire joint camera/point increment.

Eta2 couples tau to the central lambda. Holding tau fixed *within* the menu is
therefore essential: changing tau per lane would change S_tau and b_tau as
well as the camera shift. Such a collection is not the shifted-system family
required by this recurrence. These are five camera-damping alternatives at one
point damping, not five joint-LM alternatives. Between attempts the champion
rebuilds its coupled point factors normally.

## Sharing and preconditioning

All lanes start from zero, so their initial residuals coincide. Ordinary CG on
the smallest shifted system generates the shared Krylov space. The zeta
recurrence updates the remaining four solutions without their own Schur
products. A fresh product for every lane checks its true residual at exit.
No recurrence vector is transferred across a changed point factor or RHS.

Applying a general block preconditioner to this *same* family produces

    M^{-1/2} K M^{-1/2} + lambda_j M^{-1},

which is not a scalar identity shift. Inserting PCG residuals into the ordinary
zeta recurrence would therefore be invalid. Diagonal equilibration E here is
already part of the frozen champion's damping metric; it is not that invalid
substitution. The handover instead restarts the original single-shift PCG from
zero, retaining the current nonlinear state and radius controller.

This is a constraint on preserving the original damping metric, not a theorem
that all preconditioned multishift methods are impossible. For example, choosing
K + sigma M as the physical family would restore identity shifts after a fixed
congruence. It also changes the optimization algorithm's damping geometry and
would require a separate experiment. No such method was tested here.

## What collapse can and cannot establish

For the five camera vectors let G_ij = y_i^T y_j. With clipping scales
a_j = min(1, R/||y_j||), the diagnostic is

    D_R^2 = max_{i<j}(a_i^2 G_ii + a_j^2 G_jj - 2 a_i a_j G_ij)
            / max_j(a_j^2 G_jj).

The all-zero bank has diameter zero. The raw diagnostic uses a_j=1. The switch
requires D_R <= 1e-3 on two consecutive accepted, non-rescued, residual-qualified
menus. The safety cap at eight accepted steps is separately labeled. The
follow-up removes that early cap; it does not retune the collapse threshold.

Three limitations matter:

1. Radius projection can erase amplitude diversity. In the zero bare-operator
   check, raw diameter is 0.9999 but clipped diameter is approximately 3.2e-8
   (exact value zero). Scoring the raw norm spread would overstate the options
   available to this radius-limited solver.
2. This is diversity of computed camera increments in equilibrated coordinates,
   not a proof that fully solved joint increments agree. Loose forcing can leave
   important soft modes unresolved, and point back-substitution can amplify a
   small camera difference. The five true residual checks prevent us from calling
   an unqualified capped recurrence converged; they do not remove this limitation
   of the champion's intentionally loose forcing, up to eta=0.5.
3. A winning shift observes a different camera damping at fixed point damping.
   Feeding it into next iteration's central lambda also changes the next point
   damping. That is a heuristic controller intervention, not a trust-region
   identity. The separate menu-only and feedback arms expose this distinction.

The cost comparison must be against one preconditioned solve, not five. The
least-damped seed can dominate the shared depth even if the selected lane
converged much earlier. Five exit audits and five nonlinear candidate scores add
further work. This prototype charges all of it and makes no novelty claim for
the known shifted recurrence or its numerical stabilization.
