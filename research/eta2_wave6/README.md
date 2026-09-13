# Eta2 wave 6: categorical-map campaign

This directory follows the categorical mathematics map in evidence order.
The first deliverable is a deterministic trajectory and paired-inference
substrate; the opening FTLE then selects the next mathematical intervention.

The frozen Eta2 champion and the wave-5 optimized candidate remain controls.
See `PROTOCOL.md` for the preregistered sequence and decision rules.

Current high-level results:

- deterministic reductions make exact paired trajectory experiments possible;
- graph effective resistance validates count starvation but does not beat the
  cheap observation count on the known Final3068 witness;
- the apparent positive opening FTLE is an FP32-fragment finite jump, not a
  scale-consistent Lyapunov exponent;
- FP64 fragments reduce an `epsilon=1e-12` ten-outer separation by 216,602x on
  Venice and 443,916x on Final3068, but the paired full-convergence test fails:
  23/35 versus 25/35 hits and 1.63x median target time on double hits.
- monotone soft acceptance makes 206/213 low-rho proposals locally better,
  yet its 60-pair Final3068 cohort is unresolved: 41/60 versus 38/60 hits,
  12 versus 9 discordant wins, and 1.077x median target time on double hits.
- a banded camera preconditioner has a strong fixed-system signal on Venice52
  (RCM band 32 improves conditioning 106.6x), but the registered structural
  gate fails: no sequence scene retains 80% normalized coupling at band 16,
  and required widths grow to 138--215 cameras on the larger sequences.
- exact gauge-quotient posterior variance identifies geometric starvation at
  Venice camera 34 in 5/5 terminal states, but the cheap local Schur-block
  score gives the identical top-one decision; no probing/prior arm is earned.
- a focal-depth camera chart (`q=t_z/f`, `ell=log(f)`) improves camera 34's
  local scaled condition by 170.8x and retains 12.7x more of the captured
  healthy-camera motion, but a fresh solve exposes another soft direction:
  it remains about 331 radii long and raises true cost in 5/5 terminal states.
- a rank-one residual tensor model improves Gauss--Newton prediction on all
  five registered Final3068 plateau transitions, but only by 1.86% at the
  median and never by the required 20%.  Its correction is concentrated in
  200 observations but its projection coefficient falls to 0.003--0.031, so
  preceding-step curvature is mostly irrelevant to the next clipped/retry
  direction; a native three-solve tensor step is not earned.
- a faithful three-accept lifted robust opening jointly optimises persistent
  observation weights and improves the Final3068 screen from 3/5 to 4/5 while
  cutting median rejects 15 to 4.  It is nevertheless rejected: Venice stays
  0/5 and its median endpoint worsens 5.768% (260.53k versus 246.33k).  The
  result confirms an objective-opening basin effect that does not transfer
  across the two tail mechanisms.
- a per-track damage filter cleanly separates the archived E4 pair, but not
  fresh trajectories: all 5/5 Final hits and 5/5 misses contain an early event,
  with 20 events in each class and nearly identical median concentration.  The
  preregistered diagnostic gate fails, so no active filter or threshold sweep
  is run.
- a q=3 generalized visibility-subgraph preconditioner collapses the hard
  Muell fixed solve from 42 products to 2.  Reused-symbolic CPU LDLT plus solve
  is 119.36 ms versus frozen Hcc's 131.19 ms, but serial numeric formation adds
  301.38 ms, Ladybug grows from 1.85 to 605.47 ms without saving a product,
  and both available GPU sparse-direct backends take over 60 seconds in
  symbolic analysis.  It is retained as a strong algebraic diagnostic and not
  promoted into Eta2.

See `D11_VISIBILITY_SUBGRAPH_RESULTS.md` for the current decision.  The scientific
champion remains unchanged.
