# Brief 9 registration: terminal coarse stopping oracle

Only the actual three Final3068 terminal witnesses are tested here, because earlier opening/late nonlinear collective corrections already failed on samples. Use K8 and the finite-difference-verified native Sim(3) cluster basis of Brief1. No new basis selection, K sweep, damping reset or stopping-rule change.

Construct the coherent FP64 damped Schur operator and reduced gradient at each saved state with the saved lambda/scaling/intrinsic regularizer. Form Ac=Z^T A Z and bc=Z^T b; rank/gauge accounting follows the existing coarse diagnostic. Report the unconstrained camera decrement .5 bc^T Ac^-1 bc. It excludes the constant point-only elimination decrease, so do not confuse it with a full-step prediction or a stationarity certificate.

Construct the resulting coarse camera direction and its version clipped to the saved Eta2 radius; conditionally back-substitute Euclidean points with the same model. Score the full original objective and prediction for both. N3 CPU repetitions at all3 witnesses; independent product/parity and positive-factor checks before interpreting the numbers. No huge dense camera matrix is necessary: sparse camera/point operators and a small coarse matrix suffice.

Report the original brief's zero-decrement kill and, separately, the more practical feasibility gate: to justify another nonlinear collective rollout, the clipped proposal must give an accepted true decrease exceeding twice the stored Eta2 witness decrease on at least2/3 states. If that fails, stop this terminal oracle/correction branch. A large unconstrained decrement with rejected or ineffective feasible proposals is not evidence that the original stop should be overridden. All overhead is diagnostic CPU cost; no GPU speed claim. Do not hide original prediction-budget mismatches or relabel a reduced-residual reference as exact full GN.

If the gate passes, a passenger-point nonlinear base-node solve is a separately registered continuation, because it differs from eliminated-point coarse curvature. The original optimizer, objective and champion remain unchanged during this screen.
