# T3: changed rankings, insufficient benefit

On 20 held-out synthetic scenes, N=3, every arm hits the fixed cost target.
One pre-ranking point step changes 13.3% of selected menu entries, three steps
change 16.1%, and selective one-step relaxation changes 18.6%. Thus nonlinear
point relaxation does affect ranking; the mechanism is measurable.

It does not repay its cost. Median paired speeds relative to the raw menu are
post1 0.866x, post3 0.712x, pre1 0.723x, pre3 0.456x, selective 0.495x.
Pre1 runs at 0.694x post1 speed; pre3 at 0.590x post3. Point relaxation consumes
41.6% of pre1 and 67.1% of pre3 time. The selective prototype still projects
all observations and pays for selection, so it is not a production sparse
implementation and cannot establish the cost of a future selective GPU kernel.

At target crossing, point NRMSE>0.15 occurs on 3/20 raw cases and 1/20 in every
polished arm. This is a geometric benefit at these stopping snapshots, but it
does not satisfy the convergence-speed gate. The target is not a geometry
certificate. The 30-step point references record remaining stationarity and
must not be called globally optimal elimination. Candidate-order, immutable-
parent, fixed-camera, gauge and per-point monotonicity checks all pass.

T3 is unsupported as a speed improvement under this implementation and screen.
Keep polishing as an engineering/reconstruction option; do not promote it or
call a few point iterations exact variable projection. Next is T4.

## Prior art

Ceres describes nonlinear inner iterations that refine independent parameter
blocks after a successful trust-region step. Our post-only comparator follows
that structural idea, implemented in the local reference rather than running
Ceres itself. Pre-ranking relaxation adds candidate-dependent point work and
changes which complete camera–point state is selected. That difference did
not pass its measured cost gate.
[Ceres, Inner Iterations](https://raw.githubusercontent.com/ceres-solver/ceres-solver/master/docs/source/nnls_solving.rst).

PoVar first eliminates landmarks in a separable object-space/projective
formulation, then uses a distinct projective refinement and metric upgrade.
Its reduced system damps cameras but uses undamped landmark blocks at the
stationary branch. Our finite point steps on the original pinhole pixel loss
are not the same algorithm or an exact PoVar baseline.
[PoVar, sections 3.2 and 4.1–4.2](https://arxiv.org/html/2405.05079).

Reproduce `check_points.py`, then `run_t3.py --split development` and
`run_t3.py --split held_out`. `T3_PROTOCOL.md` predates comparisons; `t3_*` JSON
retains all menus, costs, times, point references, stationarity and geometry.
