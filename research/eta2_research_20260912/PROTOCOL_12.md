# Brief 12 registration: ROS2 witness pre-test

Start on the three small full Venice witnesses, N3 per configuration, before building a new GPU solver. This bounded diagnostic tests the low-prior flow proposal against coherent FP64 reference steps, not native Eta2 wall-clock supremacy.

Use the autonomous frozen-metric flow D*x_dot=-g(x), original objective, native camera retraction, Euclidean points and fixed k2. D uses the saved camera scaling and positive point diagonal/trace floor, held fixed for the experiment at a witness. Approximate the flow Jacobian with the coherent GN Hessian plus the same intrinsic solve regularizer. Include both camera and point gradient components.

Fix standard ROS2 coefficients gamma=1+1/sqrt(2), a21=1/gamma, c21=-2/gamma, m1=3/(2gamma), m2=1/(2gamma). Source: [KPP's maintained numerical-method documentation](https://kpp.readthedocs.io/en/stable/num_methods/rosenbrock-methods.html), checked before this registration. Set flow step h=1/lambda_champion, so both methods use the same artificial time scale. Define K=H_GN+D/(h*gamma), factor it once, solve

```
K k1 = -g0
xstage = Retract_x(k1/gamma)
K k2 = -g_in_fixed_base_chart(xstage) - (2/(gamma*h))*D*k1
dROS = (3*k1+k2)/(2*gamma).
```

Transport the stage camera gradient through the derivative of the base SO(3) exponential chart, rather than adding gradients from different tangent frames. The point/stage RHS and damping change relative to the champion's first solve; disclose stage damping lambda_champion/gamma. Reuse only the fixed operator/factors within this two-RHS construction, not Krylov vectors across solves.

Controls: one coherent LM step at the saved champion lambda, and two successive coherent LM steps at that same lambda and frozen D, relinearizing for the second. Preserve original input/state; apply the saved camera radius separately to reported feasible proposals, with corresponding point completion, and retain raw proposals as diagnostics. Explicitly describe any distinction between clipping the ROS combination and completing its points; do not silently replace the combination with a plain GN back-substitution. Actual accepted-cost decrease uses the full unchanged objective.

Validate second-order consistency on Euclidean quadratic and nonlinear toy flows, arbitrary-approximate-Jacobian cancellation, and finite-difference tangent transport before the witness grid. Measure full setup, gradient, factor, solve and scoring work with one CPU thread; alternate control/candidate ordering. CPU timing is a pre-test, not a GPU estimate. A nonlinear-pole or failed-linear-certificate case is invalid/rejected, never silently dropped.

Kill unless ROS2 has greater accepted decrease per measured CPU wall than the two-LM control with disjoint N3 ranges on at least2/3 witnesses and no >0.15% full-cost regression on another. A pass only permits a separately registered native equal-wall experiment. The first-stage norm, second-stage norm, rho and direct full objective remain visible. No theorem of faster optimization follows from the order of a time integrator.
