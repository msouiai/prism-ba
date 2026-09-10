# Terminal relaxation probe amendment

Registered after the 30-run gradient audit and before compiling/running this
probe, 2026-09-10. This is a diagnostic prompted by that audit, not a held-out
algorithm-selection experiment.

For unshared 9-DOF L2 BA, each scalar residual row touches at most 12 variables.
Writing H=J^T J and D=diag(H), Cauchy-Schwarz gives H <= 12 D. Replacing zero
or tiny diagonal entries by larger positive floors preserves the inequality.
Thus d=-D^-1 g with alpha=1/12 decreases the Gauss-Newton quadratic by at least
alpha*g^T D^-1 g/2. This is a local quadratic statement; nonlinear cost must
still be tested. It does not claim that gradient descent is a new algorithm.

At the terminal state only, after fresh undamped assembly, evaluate this joint
camera/point direction, with four allowed alpha values: (1/12)*(.25)^j,
j=0..3. Stop on the first true-cost Armijo pass with coefficient 1e-4. Check the
gradient sign/scale with a central directional derivative at epsilon=1e-6.
Never replace the solver state. Report terminal cost, actual possible gain,
stop reason, scaled gradient, last effective damping, trials and probe cost.

Use Final3068 N=3 each for v2 library-equivalent and eta2, max60 outers and
30 process seconds. These are distinct diagnostic arms, not a fair timing
comparison; retain every outcome. First require a zero-error memcheck on
Ladybug49 and an off-mode four-outer objective parity check. If no diagnostic
sample reaches an early stop, report that limitation rather than forcing one.

This probe tests whether a reported stall still admits straightforward descent.
Any solver recovery needs a separate, prospectively registered target test.
No improvement to the champion is claimed merely because a terminal candidate
has lower cost.
