# Adaptive candidate scoring

`OCA_ADAPTIVE_MENU=1` opts into the controller. It requires five allocated
shifts, fp64 unshared dof9 and full observation scoring. Do not combine with
hysteresis, learned menu policies, candidate pruning, shift pruning or
negative-curvature reseeding. Standard retry caching, multi-RHS, diagonal
norm and guarded backtracking remain supported.

The Krylov recurrence still carries five shifts. The controller changes
which candidates are lifted/scored; it does not yet give narrow attempts
the shorter seed solve of a true one-shift configuration.

At each checkpoint it scores the center first. In full mode, remaining
shifts use a batched RHS pass. All scored candidates compete by the original
minimum-cost rule. If a narrow attempt has no improving candidate, it scores
the remaining shifts in that sweep. The first two outers, every eighth outer,
a failed/rescued attempt and a useful boundary winner request a full menu.
Periodic full menus bypass the flat-model gate, so a bad model proxy cannot
permanently suppress exploration.

The remembered value is an EWMA (weight 0.5) of extra-candidate reduction per
scoring second divided by center-candidate reduction per scoring second,
capped at 4. Gains are incremental improvements to the best candidate found
so far, not repeated sums of the same objective reduction at every checkpoint.
A ratio at least 1 requests a full menu. Positive extra gain with no center
gain gets value 4; zero extra gain gets 0. Unmeasured value remains unchanged.
This measures immediate scoring productivity, not future trajectory utility.

Point-only/zero-depth, uninformative and backtracking-rescued accepts preserve
the pre-retry menu center. Otherwise original center updates remain. Extra
nonlinear gain above 1% can override an apparently flat model. This pilot
combines exploration adaptation and the confidence rule; a later ablation
would be needed to isolate them.

`ADAPT` log rows retain scoring counts/times, marginal gains, controller value,
mode and selected shift/depth. `center_frozen` records eligibility for the
freeze rule; only an accepted attempt actually applies it. The benchmark
summarizer validates scoring counts, bounded controller values and gain
accounting. Unit tests: compile/run `bench/test_adaptive_menu.cc` with C++17.

`bench/adaptive_menu_experiment.py` runs fixed single, fixed multi and adaptive
arms, three repeats by default. `bench/summarize_adaptive_menu.py` reports
endpoint/work ranges and time to 1%,3%,5% acceptable-cost bands.
See `docs/adaptive_menu_protocol.md` for the frozen four-scene pilot.
