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
- a BA-sign-correct randomized Nyström correction is strictly dominated on the
  hard Muell system: ranks 4/8/16 save no post-switch Krylov work and only add
  4/8/16 sketch products.  Its mandatory attribution control uncovers a much
  stronger result: restarting the unchanged Hcc-PCG recurrence at iteration 8
  cuts that fixed solve from 42 to 15 total products and from 130.35 to 46.51
  ms, including explicit residual replacement, while shallow controls never
  trigger.  Nyström is closed; the restart
  signal advances to a native and residual-minimizing-Krylov follow-up.
- right-preconditioned GMRES(8), aligned with Eta2's Euclidean residual forcing
  rule, dominates both uninterrupted and restarted Hcc-PCG on the two hard
  Muell captures.  It uses 6 products / 18.88 ms across the pair versus 37 /
  114.79 ms for periodic restart-8 and 170 / 530.08 ms for uninterrupted PCG,
  while storing only nine camera vectors and passing explicit residual and
  Arnoldi-orthogonality checks.  This fixed-system winner now advances to the
  native nonlinear gate.  The native gate rejects it: it is 1.330x slower on
  the nine-cell panel, loses one tight Trafalgar hit, and turns Muell from 3/3
  hits at 4.22 s into 0/3 at the 12 s cap.  Its different early directions
  prevent the solver from reaching the states on which the isolated solve won.
- periodic exact-residual Hcc-PCG restart at depth eight also fails natively.
  It is 1.456x slower on the nine-cell panel, loses on every cell, and turns
  Muell from 3/3 hits at 4.23 s into 0/3 within 12 s while increasing Schur
  products from 980 to 3,309.  The fixed-witness gain was real, but repeated
  conjugacy erasure changes and ultimately degrades the nonlinear trajectory.
- one-reduction Chronopoulos--Gear PCG halves scalar reduction phases but has
  no fixed-system speed crossover on this GPU.  The capped Muell capture is
  unchanged at 399.7 ms, the converged Muell capture is 2.3% slower from its
  extra drain product, and shallow systems are 30--49% slower.  Numerical
  audits pass; the native gate is not opened.
- a sparse unique-track-count gate plus a local Schur-space Gaussian prior
  improves the two archived Final3068 witness decreases by 6.48--7.10% while
  preserving healthy-camera motion.  It is causal but not promotable: a
  24-pair deterministic cohort gives one D15-only hit, zero control-only hits,
  13 double hits and 10 double misses, so the directional SPRT is inconclusive
  at cap.  No-activation pairs are bit-identical; the gate is sound, while the
  finite prior is usually too weak to overcome the subsequent global clip.
- replacing that finite prior by hard projection is a much stronger causal
  perturbation, but it has no net reliability advantage: 24 deterministic
  pairs give 9/24 hits in both arms, with two D16-only rescues and two
  control-only hits.  Endpoint swings from -9.06% to +2.18% show that the
  starved camera controls a basin branch, while persistent freezing selects
  either side unpredictably.  D16 is not promoted.
- a one-shot version with infinite dwell removes D16's repeated-work pathology
  but not its ambiguity.  On the same 24-pair development cohort it gives
  10/24 hits versus 9/24 control, with two rescues and one harm; the net-one
  result misses its preregistered advance threshold, so no fresh cohort runs.
- a top-one geometric-starvation gate identifies Venice camera 34 in all five
  terminal states and a one-camera prior collapses raw/R from 428 to about
  0.85 while raising fixed-state decrease from 1.60 to about 583.  It still
  stops before native rollout: its best-balanced dose retains 94.475% of the
  healthy-camera norm, below the preregistered 95% locality threshold.
- restricting the prior to camera 34's single weakest eigenvector improves the
  fixed steps further but retains only 87.667% of healthy motion after the
  global re-solve.  The eigenvector itself contains 99.9973% of raw-step
  energy, motivating a direct quotient projection that preserves all other
  coordinates.  D20's fixed projection raises true decrease from about 1.60
  to 481, but its native gate is inactive: fresh Venice trajectories give 0/5
  target hits in both arms and zero projections.  Four runs remain below the
  fixed ratio threshold; in the fifth, camera 34 owns the oversized step but
  camera 32 owns the weakest local block.  The archived mechanism is real but
  conditional on the trajectory that created it, so D20 is not promoted.
- a three-attempt arithmetic-trajectory portfolio turns B6v7's run-to-run
  basin variation into 37/38 Final3068 target hits and crosses its registered
  high-reliability SPRT boundary.  It rescues 13/14 first-attempt misses and
  records mean/p90 wall of 5.93/10.04 s, better than the historical
  Eta2-to-MFREE composition.  Its median is 4.263 s, above the registered
  3.923 s ceiling and 11% slower than that historical cascade, so it is a
  Pareto alternative rather than the new operational winner.
- terminal exact two-view triangulation is a sound but immaterial stationarity
  audit. Five deterministic Final3068 pairs remain 2/5 hits in both arms; on
  the three misses it replaces 32,561 tracks but lowers terminal cost by only
  0.001304% at the median, about 115x below the registered advancement bar.
  Every preterminal path is exact and the kernel costs about 5 ms, so the
  negative isolates the mechanism: the stopped gap is not fixed-camera
  two-view point nonstationarity. D22 closes before its extension and controls.

See `D13_NATIVE_RESULTS.md`, `D13B_PERIODIC_PCG_RESULTS.md`,
`D14_CA_PCG_RESULTS.md`, `D15_COUNT_PRIOR_RESULTS.md`, and
`D16_COUNT_PROJECT_RESULTS.md` for the principal decisions; D17's dwell-time
follow-up is in `D17_COUNT_IMPULSE_RESULTS.md`, and the geometric-prior screen
is in `D18_GEOMETRIC_PRIOR_RESULTS.md`.  D20's fixed and native conclusions are
in `D20_SLOPPY_QUOTIENT_RESULTS.md` and `D20_NATIVE_RESULTS.md`.  The scientific
champion remains unchanged.  The portfolio result is in
`D21_RESTART_PORTFOLIO_RESULTS.md`. The terminal algebra audit is in
`D22_TERMINAL_TRACK_POLISH_RESULTS.md`.
