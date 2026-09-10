# Extended terminal probe amendment

Registered after the first six terminal probes and before running the extension.
The four allowed step sizes failed at all three v2 endpoints and two of three
eta2 endpoints, despite a negative small-step finite-difference derivative.

Repeat the same N=3/arm diagnostic, changing only the terminal probe (the state
is still never replaced). Permit 12 backtracking scales instead of four, with
the same initial alpha=1/12, contraction .25 and Armijo coefficient 1e-4.
Also evaluate symmetric directional differences at epsilon=1e-4 through 1e-8.
Compare the estimated true directional curvature with the analytic GN bound
12*g^T D^-1 g. Report the estimates at every scale; neither cancellation nor
finite-difference truncation error is a certified curvature measurement.

This is an exploratory mechanism test on new terminal states, not a paired
comparison of the old four-trial and new twelve-trial endpoint distributions.
No target, solver trajectory, damping controller or winner is changed.
