# Damping after a nonlinear repaired step

Let F(x)=0.5||r(x)||^2, g=J^T r and H_GN=J^T J. For **any** tangent direction d, the unregularized Gauss–Newton predicted decrease is

    P(d) = -g^T d - 0.5 ||Jd||^2.

This identity does not require a converged linear solve. For a left-rotation camera retraction, J is the derivative of the residual along that retraction at its origin. A point mask or nonuniform point scaling changes d, and therefore changes both terms and camera–point cross terms. Substituting the prediction of the failed full step, or a Schur-only prediction, is not valid in general.

For uniform scaling alpha, write s=g^T d and q=||Jd||^2. Then P(alpha*d)=-alpha*s-0.5*alpha^2*q, rather than alpha*P(d). For mixed camera/point directions dc and dp, P(a*dc+b*dp)=-a*gc-b*gp-0.5*(a^2*cc+2*a*b*cp+b^2*pp). An arbitrary per-point mask requires evaluating the actual Jd or equivalent masked coefficients.

For a genuinely accepted state x+, define rho=(F(x)-F(x+))/P(d), provided P is positive and sufficiently above rounding uncertainty. The model is evaluated before overwriting x and only after the demand menu has selected its retained winner. This prevents attaching a discarded candidate's prediction to a restored fallback.

We require finite costs/slope/curvature, negative slope, nonnegative squared-Jacobian norm, positive actual decrease, and P>64*epsilon*max(1,F). The guard is a practical rounding screen, not a condition-number-dependent forward-error bound. Invalid predictions retain damping. The objective acceptance test itself is unchanged.

## Joint feedback experiment

Apply one common multiplicative factor to the retained camera/point damping pair after original demand bookkeeping:

- Audit mode1: factor 1.
- Relax mode2: factor 0.5 if rho>0.75; otherwise1.
- Symmetric mode3: factor 0.5 if rho>0.75; factor 2 if rho<0.25; otherwise1.

Pair components are clipped to their existing positive floors and 1e8 ceiling. No relative-objective-progress override is used. Only rescued accepted steps receive this feedback. Ordinary accepted steps and rejection logic retain their previous rules. The next iteration checks its numerical factor keys against the new tau, so no factorization or scalar-shift Krylov recurrence is reused across a changed operator by assumption.

A single observed model error cannot identify separate camera and point damping corrections. Updating both by one scalar is a controlled experiment, not a derived optimal two-parameter solution. We deliberately restrict it to the retained-pair controller; the fixed-menu tau ratchet has different state semantics.

## Why good agreement alone is insufficient

Consider scalar residual r(x)=1+x+1000*x^2 at x=0. At d=-1e-6, the GN model has rho about 0.999 and the cost decreases. At d=-1, the true cost is 500000 versus the initial 0.5. Thus agreement of a sufficiently tiny step does not certify a longer direction. More generally, for a smooth residual and descent direction, rho(alpha*d) approaches1 as alpha approaches0 even if the full step crosses a projection pole or a strongly nonlinear region.

The finite-menu point safeguard is also not an exact trust-region subproblem solution. Therefore a standard-looking agreement ratio does not transfer a trust-region convergence theorem to this solver. This round tests whether bounded feedback corrects a measured freeze; it does not assert a theorem or claim novelty for the ratio itself. Both repeated target success and prospective behavior matter.

A scale-invariance boundary test exposed threshold flips from floating-point roundoff at exactly rho=0.25 or0.75. The implementation conservatively retains the pair within 64*epsilon*max(1,abs(rho)) of either threshold. This numerical dead band was added before benchmark execution; the initial failing test is recorded. It is not temporal hysteresis or a fitted scene parameter.

An explicit least-squares identifiability example uses residual vectors [3-a-b, sqrt(2)*a^2] and [3-a-b, sqrt(2)*b^2]. At the origin they have identical residuals, gradients and GN matrices. At(a,b)=(1,1), both have F=1.5, P=4 and rho=0.75. But their camera-only costs are 3 and 2, respectively, with the point-only costs reversed. The single full-step agreement observation cannot distinguish which block carries the nonlinear error. The independent algebra gate also verifies the actual masked prediction against exact affine-residual objective differences in 1000 cases.
