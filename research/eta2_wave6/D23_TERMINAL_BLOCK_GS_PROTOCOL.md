# D23 protocol: terminal nonlinear block Gauss--Seidel audit

Registered 2026-09-13 after D22 closed and before building or scoring D23.

## Question and mechanism

D22 shows that exact two-view point algebra at fixed terminal cameras lowers
Final3068 misses by only `0.001304%` at the median. The remaining stop gap may
instead be blockwise nonstationarity: Eta2's clipped, inexact joint step can be
small even while fixing all points exposes a useful camera step, or fixing the
updated cameras exposes a useful point step.

D23 leaves deterministic B6v7 bit-identical until its existing FTOL or failure
rule proposes termination. It then runs at most eight nonlinear block
Gauss--Seidel sweeps using the solver's existing resection--intersection
primitive:

1. assemble at the current state and solve all independent damped 9x9 camera
   blocks with points fixed;
2. commit the simultaneous camera update only if the full original L2 pixel
   objective decreases;
3. reassemble at the accepted cameras, solve all independent damped 3x3 point
   blocks with cameras fixed, and commit only if the full objective decreases;
4. stop at the first sweep where neither half decreases the objective.

Every committed half-step therefore lowers the scored objective. No robust
loss, observation change, periodic invocation, opening change, or resumed Eta2
trajectory is involved. This is a stopping/stationarity audit, not a proposed
new BA method. Earlier `OCA_RI_OPEN` and fixed-outer `OCA_RI_AT` experiments
changed a live trajectory and then resumed Eta2; their basin regressions do not
answer this terminal-only question.

## Frozen implementation and correctness

Derive reversibly from deterministic B6v7. `OCA_D23_TERMINAL_RI=8` is the sole
active flag and is forbidden together with the historical RI flags. The
feature-off binary must match the deterministic parent exactly on
Ladybug539-1.01 in endpoint bytes, accepted-cost and normalized-decision
hashes, target result, outer/reject/product counts, and independently audited
cost.

The active log records the original stop cost, terminal cost, number of
accepted sweeps, number of curve states added, elapsed terminal wall, and
whether the terminal state reaches the target. The returned state and every
curve crossing are independently scored on the unchanged objective.

## Registered Final3068 gate

- First screen: five fresh deterministic `epsilon=1e-12` perturbation pairs,
  seeds 660068--660072, target `1744796.9841897595`, 60-second cap.
- Advance to seeds 660073--660077 only if the first screen has at least one
  D23-only target hit or median terminal relative decrease above `0.15%`.
- Full gate: at least two D23-only hits, zero control-only hits, exact paired
  preterminal paths, and median active/control native wall at most `1.20` on
  pairs where D23 runs.

Target-reaching Eta2 runs stop before D23 and must remain exact double hits.
Because every D23 commit is monotone, a control-only hit indicates a harness or
scoring failure. No sweep-count or damping tuning follows a failed screen.

## Conditional controls

Only after the full Final gate passes: Venice52 N=5 at target `243740.27`, then
the nine B6v7 practical cells N=3. No endpoint may regress above `0.15%`, no
target hit may be lost, and no disjoint time loss may occur on five or more
panel cells. The frozen Eta2 scientific champion, B6v7 systems winner, and
existing portfolio labels remain unchanged until all gates pass.

