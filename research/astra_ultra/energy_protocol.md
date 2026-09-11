# U3: full-model energy credit for eliminated points

Registered before stopping-rule measurements. Use all15frozen screen cases,
ordinary LM parents k=0,2,4 with their actual lambda, for45systems if all states
are reached. Same6DOF gauge, original block GN matrix, damping and pixel loss.
All stopping arms share the same block-camera-preconditioned PCG trajectory;
no basis recycling or changed preconditioner. Camera preconditioner is B+lambda
Dc before Schur elimination, not the Schur block diagonal. Point back-substitution
is exact. This is a CPU linear-work/one-step diagnostic, not timed native BA.

P0=.5 gp'C^-1gp. At x, camera gain b'x-.5x'Sx; full gain includes P0.
Exact missing energy epsilon=.5r'S^-1r is an expensive oracle. The actual cheap
upper bound U=.5 sum(r²/(lambda Dc)) follows S>=lambda Dc, checked numerically
and derived from PSD original GN. Gauge coordinates are excluded. Neither
the Schur Cholesky oracle nor per-iterate diagnostic true residuals are free
operations in a deployable method; their timings are not speed claims.

Predeclared stopping rules, at least1PCG iteration: relative residual<=0.5 or0.8;
Ceres/Nash camera progress k*(Qk-Qprevious)/Qk<0.1; exact-energy oracle with
and without P0, epsilon<=0.1*achieved_gain; cheap-bound counterparts
U<=0.1*achieved_gain. No tolerance sweep. Q=x'Sx-2b'x. Ceres source checked:
https://github.com/ceres-solver/ceres-solver/blob/master/internal/ceres/conjugate_gradients_solver.h

Max128PCG iterations or true residual<=1e-10. Residual recomputation every10
iterations is shared. Recurrence residuals screen prospective exits; each
prospective exit is then checked with a fresh true residual (or the already
fresh periodic one). Charge every such product, including failed checks.
Oracle epsilon/diagnostic matrices are recorded separately. No zero-iteration
exit. One identical full pixel evaluation at each rule's chosen step measures
whether reduced quadratic work retains useful nonlinear progress.

Opportunity gate: cheap full-credit rule uses>=20% fewer charged Schur products
than eta0.5 on>=4parents spanning>=2families, and each selected trial retains
>=90% of that ordinary step's positive true-cost decrease; no new invalid
trial among ordinary-valid parents. Also require P0 to actually change at least
one such selected stopping decision versus the otherwise identical no-P0 rule.
Report eta0.8 and Nash comparisons separately; equal cheap controls preclude a
novelty claim. If oracle helps but bound does not, stop at the estimator gap.
If the cheap gate passes, register bounded complete PCG trajectories before
running them; identical target comparisons then decide promotion. No Lanczos,
new bound tuning, native capture generation or GPU port to rescue a failure.
