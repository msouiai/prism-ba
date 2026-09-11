# What the Venice tail does and does not imply

This is a local mathematical interpretation of the completed logs, not a
new algorithm or an established causal attribution.

Write the damped normal equations after eliminating points as

\[
S_\lambda d_c=b_\lambda,\qquad
S_\lambda=U_\lambda-WV_\lambda^{-1}W^\top.
\]

With zero initial iterate, one PCG step has the form

\[
p=M^{-1}b_\lambda,\qquad
 d_c^{(1)}=\frac{b_\lambda^\top M^{-1}b_\lambda}
 {p^\top S_\lambda p}\,p.
\]

It minimizes the quadratic along one preconditioned gradient direction.
A residual-based stopping test can accept that step while leaving slow
spectral components unresolved. The observed one-iteration tail therefore
motivates checking tighter forcing. It does not by itself establish that
inexact CG causes the objective floor: an exact solve with excessive damping
can also make slow progress, and a different early trajectory can change the
late state.

For the latter possibility, consider a scalar positive-curvature mode of an
exact quadratic, with curvature h and a fixed damping floor lambda. The exact
damped Newton update contracts the error by

\[
 e_{k+1}=\frac{\lambda}{h+\lambda}e_k.
\]

For h much smaller than lambda, this factor is close to one even with a
perfect linear solve. This is an illustrative local model in a fixed metric,
not a fitted estimate of Venice's spectrum. Neither h nor a full spectral
condition number has been measured in the present experiment.

The model-agreement ratio near one in seven extended runs establishes good
agreement only along their chosen steps; it does not validate the quadratic
in every direction. Those seven are not radius-clipped in their last100
attempts, while three worse runs are clipped. All ten accept their last100
attempts with extremely small gains. A single explanation based solely on
rejection counts would miss this terminal behavior.

Finally, the frozen implementation stores its cross fragments in float32
while substantial other arithmetic is double, and retains a nondecreasing
numeric-repair floor after detected negative curvature. Mixed precision and
conditioning are plausible reasons to inspect that floor; the present logs
do not prove which produced a particular repair, nor that reducing the floor
would be numerically safe. The two registered probes retain the numerical
safeguard. They can establish an empirical improvement, but isolating a late
forcing effect from a changed trajectory would need a separate checkpoint
intervention and is not part of this coverage test.
