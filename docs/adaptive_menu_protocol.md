# Adaptive candidate-menu pilot (frozen before runs)

Controller opt-in, five CG shifts retained. This is candidate-scoring
adaptation, not a claim of a one-shift linear solve. Every scored step
competes by original true cost; no hysteresis discount or worse-step preference.

Central shift scored first at each checkpoint. Full mode scores the other
four using batched multi-RHS. Narrow mode scores the center only, expanding
in the same sweep when no improving candidate exists. Full mode for first
two outers, every eighth outer, after failure/rescue, on a useful boundary
winner, or when remembered extra-candidate progress/time justifies its cost.
These full probes bypass the analytic flat-menu gate. Narrow flat menus
retain the gate. This deliberately changes candidate ordering only in the
opt-in controller; fixed controls retain their own original paths.

Across checkpoints, measure marginal reduction in the best-so-far candidate
cost attributable to center and extras separately (no repeated counting of
unchanged gains). Divide by their measured scoring time. Memory is EWMA
with new weight 0.5 of extra-rate/center-rate, capped at 4; zero center gain
and positive extra gain gives 4, no extra gain gives 0. Expand when EWMA>=1.
Boundary winner is useful if at positive CG depth and extras contributed
more than 1% of cumulative menu gain. No observed-rate update without an
actual full comparison. History acts on exploration, not on step ranking.

Preserve pre-retry menu center after zero-depth, uninformative/flat, or
backtracking-rescued accepts. Positive-depth nonlinear extra gain above 1%
can overrule a flat model proxy. Otherwise retain existing center updates.
Both exploration adaptation and this confidence rule are part of this pilot;
the pilot cannot attribute any gain exclusively to either component.

Controls: fixed one-shift+guard and fixed five-shift+guard. All three use
one new frozen binary, Config A + retry cache + multi-RHS + diag-norm,
full fp64 unshared dof9 scoring, 600-outer cap. Adaptive has no hysteresis.
N=3, cyclic arm order. Host and CUDA memcheck gates before benchmarking.

Development: Venice52 and Ladybug1197 (opposing prior multi-shift outcomes).
Evaluation held out from this controller's development: Ladybug598 and
Trafalgar126. Already seen in prior fixed-arm study, not globally unseen.
No parameter fitting after pilot outcomes. Freeze source/flags on development
completion before evaluation; do not choose per-scene profiles.

Primary comparisons: solver time to empirical best endpoint*(1+epsilon),
epsilon=1%,3%,5%, plus endpoints, scoring work, matvecs, retries and ranges.
All three repeats must attain a target for a complete median crossing claim.
Small cost regressions are tradeoffs, not automatic rejection. Retain all
failures. No full-largest-scene, cross-GPU or global-novelty claim from this
four-scene pilot. Broader old experiment resumes afterward.
