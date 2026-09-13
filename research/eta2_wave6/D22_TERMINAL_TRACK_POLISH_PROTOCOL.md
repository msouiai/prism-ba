# D22 protocol: exact two-view point polish only at a proposed stop

Registered 2026-09-13 after D21 closed and before building or scoring D22.
This revisits the categorical map's exact per-track algebra only with a new
mechanism: use it as a stopping/stationarity audit, never as an opening or
per-attempt candidate policy.

## Hypothesis

Wave-5 A1 repaired the recorded E4 point almost exactly but harmed native
trajectories because it made 11,709 greedy point substitutions across five
Final3068 runs.  D22 cannot change the opening basin: Eta2 runs bit-identically
until its existing FTOL/failure rule proposes termination.  Only then, and only
if the registered target has not already been reached, D22 performs one
separable point polish at the unchanged cameras.

For every exactly two-observation track, undistort both measurements on the
origin-connected SIMPLE_RADIAL branch, apply Lindstrom's deterministic
two-step epipolar correction, and solve the resulting 3x3 inhomogeneous DLT
normal equations.  Replace the point only if its full distorted-pixel L2 track
cost strictly decreases, both depth signs match the old point, and the new
absolute depths are no closer to either projection horizon.  Since cameras are
fixed and point track costs separate, simultaneous accepted replacements
cannot increase the mathematical objective.  The full GPU objective is still
recomputed before committing the state.

This is one terminal pass, not periodic retriangulation.  It changes neither
observations nor the scored objective, and it never runs on a trajectory that
has already hit the target.  The solver stops after the audit; a later
continuation is a separate experiment only if this pass exposes useful
unclaimed decrease.

## Frozen implementation and compatibility

Derive reversibly from deterministic B6v7 and reuse the audited wave-5
Lindstrom kernel.  Coordinate `k2` and all cameras/intrinsics stay unchanged.
The feature-off binary must match the deterministic parent exactly in endpoint
SHA256, accepted-cost hash, normalized decisions, hit, outers, rejects,
products and audited cost on Ladybug539 1.01.

The active log reports stop cause, eligible two-view tracks, algebra failures,
depth-margin failures, accepted track replacements, summed local decrease,
recomputed full decrease and kernel wall.  The curve receives the terminal
audited cost so a crossing is counted only when the returned state really
meets the target.

## Registered Final3068 gate

- Five common-input deterministic pairs at first screen, using fresh
  `epsilon=1e-12` perturbations, seeds 660058--660062.
- Fixed target 1744796.9841897595 and 60-second cap.
- Advance to five more registered seeds 660063--660067 only if the first five
  contain at least one D22-only target hit or the median terminal cost decrease
  exceeds 0.15%.
- The ten-pair gate passes with at least two D22-only hits, zero control-only
  hits, and median active/control native wall at most 1.20 on pairs where the
  terminal audit runs.

Because paths are deterministic and identical before the terminal call, a
control-only hit is an implementation or scoring failure, not sampling noise.
All endpoints are independently rescored in FP64.

## Conditional controls

Only after the ten-pair Final gate passes: Venice52 N=5 at 243740.27 and the
nine practical B6v7 cells N=3.  D22 must cause no endpoint regression above
0.15%, no target-hit loss, and no disjoint time loss on five or more practical
cells.  The frozen Eta2 champion, B6v7 systems candidate and existing portfolio
labels remain unchanged until every gate passes.  A failed screen closes this
terminal policy without detector or threshold tuning.

