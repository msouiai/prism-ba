# W5 derivative audit: analytic directional residual curvature

The registered finite-difference correction passes its nonlinear witness gate,
but independent RHS reconstruction differs enough to leave full-normal relative
errors up to0.00809. Before a native arm, replace only r'' by its analytic
directional derivative along the same left-SO(3)/additive joint retraction.
No residual-Hessian tensor or operator change, no outer-history acceleration.

For Y=RX+t, let v=omega cross RX+dt+R dX and
a=omega cross(omega cross RX)+2 omega cross(R dX). Differentiate
u=-Yxy/Yz and f*u*(1+k1*||u||²) twice, including df and dk1 cross terms.
This avoids subtracting nearly equal residuals. The extra residual evaluation
is unnecessary for this BA-specific implementation of known geodesic acceleration.

Same four witnesses, N3 repeated source solves, same first direction, same
lambda/tau/operator and0.75 full-D acceleration guard, same radius scaling and
full true-cost acceptance. Compare all old finite-difference and new analytic
rows, including a negative/no-change result. Validate formula with independent
central finite differences on a nonsingular toy and independently recompute
the full-normal residual at real states. No native grid until this audit is
complete. Analytic r'' is established calculus, not a standalone novelty claim.
