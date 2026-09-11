# T7 registration: RHS-aware OCA pruning

This is the simplified full-system OCA recursion with D=lambda*M, M the fixed
GN diagonal metric at each parent. It is **not** a claim about the native
five-shift GPU implementation. Native Eta2 uses classical LM, one shift and
tau=lambda; the legacy shifted family keeps one point factor within its menu.

Check scalar closed form, h=0 extension, recursion indexing and general SPD
metric whitening against direct solves; check a tiny gauge-fixed BA matrix.
Show separately that changing point damping is not a scalar Schur shift.

Candidate grid at a parent: lambda=0.1*[.25,.5,1,2,4], depth k=[0,1,3,7].
Development snapshots use initial and three-attempt ordinary-LM states of
depth/rotation seeds0–9. Held-out snapshots use100–109. Preserve parents and
every true cost/validity outcome. Exact eigendecomposition is an offline audit
only. Online proxy uses twelve RHS-seeded Lanczos steps with reorthogonalization
in whitened coordinates and its spectral quadrature weights. No held-out RHS
or outcomes enter threshold selection.

Greedy representatives, ordered by depth then distance from center lambda,
merge when the RHS-weighted relative step distance is <= threshold. Candidate
thresholds .01,.03,.10. On development, choose the largest threshold for which
every retained minimum has cost <= full-menu minimum +0.001*parent cost and
every full-menu accepted state retains an acceptable candidate. If none passes,
use zero (no pruning). Compare with two simple menus: five shifts at depth0,
and one center shift at depths0,1,3,7.

Then run complete paired solves, N=3 per development/held-out scene, ordinary
target Ftruth+1e-4*(F0-Ftruth),80 attempts/2 seconds. Same exact-cost/rho>.1
acceptance and lambda adaptation for every menu. Charge full-system operator
assembly, twelve matvecs, small spectral solve, representative selection, all
factors/RHS/costs. The CPU operator may be dense, which is an explicit prototype
overhead; no production-scale full eigendecomposition is allowed. Numeric
factors are reused only at identical lambda, parent and metric.

Gate: >1.10x median speed over full menu **and both simple menus**, no extra
misses/geometric failures in either family. A win only over the wasteful full
menu does not establish novelty. Do not invent new filter shapes if pruning
fails this gate.
