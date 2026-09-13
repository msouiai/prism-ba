# D21 protocol: sequential arithmetic-trajectory portfolio

Registered 2026-09-13 after D20 closed and before any fresh D21 episode.  This
tests Component 9 of the categorical map using the deterministic-measurement
lessons from Components 6 and 8.  It does not modify Eta2 and carries no claim
of nonlinear-solver novelty.

## Hypothesis and development evidence

The optimized B6v7 implementation reaches the registered Final3068 target in
100/150 independent process launches.  The outcome is selected by small
floating-point reduction-order differences, while objective, source state and
algorithm are unchanged.  The fresh 130-run portion has negligible lag-one hit
correlation (about 0.022).  Grouped chronologically as hypothetical cascades:

- one attempt hits 89/130 (68.5%);
- up to two attempts hit 60/65 groups (92.3%);
- up to three attempts hit 43/43 groups, with median/mean/p90 charged native
  time 3.52/4.52/7.39 seconds.

These are development data and choose the fixed policy; they are not the
confirmatory result.  The registered policy runs the exact same B6v7 solver
from the exact same input in a new process up to three times, stopping at the
first registered target hit.  It uses no early predictor, state transfer,
input perturbation, parameter change or scene-specific solver flag.  A miss
discards its state.  A hit returns that state; three misses return the
lowest-cost audited endpoint.

The physical interpretation is a reproducible algorithm portfolio over
pseudo-orbits of a numerically sensitive outer map.  It exploits the measured
basin lottery rather than pretending it is measurement noise.

## Frozen execution

- Binary and flags: `research/eta2_wave5/optimized_candidate.json` (B6v7).
- Scene: `/workspace/bal/final-3068.txt`, checksum pinned in registration.
- Target: 1744796.9841897595; per-attempt cap: 60 native seconds.
- Objective: unchanged full plain-L2 SIMPLE_RADIAL, unshared intrinsics,
  `k2=0`; every retained endpoint is independently scored in FP64.
- Every attempt is a separate process.  All startup and solver time is logged.
- Total time to success is the sum of full native solve times for preceding
  misses plus the successful attempt's target-crossing time.  Process wall is
  also summed.  A three-miss episode is charged all three complete runs.

## Sequential confirmatory cohort

Episodes continue until a Bernoulli SPRT on cascade success crosses a boundary
or reaches 60 episodes.  The hypotheses are `p0=0.85`, `p1=0.95`, with
`alpha=beta=0.05`; boundaries and likelihood updates are fixed in the runner.
This asks whether the three-attempt scheduler behaves like a high-reliability
portfolio rather than a merely moderate one.  All episodes, including those
after early first-attempt hits, are retained.

Promotion as the operational reliability winner requires:

1. crossing the upper SPRT boundary;
2. median total native time at most 1.20 times B6v7's banked single-attempt
   conditional median of 3.26935 seconds;
3. mean total native time below 6.59 seconds and p90 below 18.1 seconds, the
   collaborator-reported Eta2-to-MFREE cascade values.

The cross-machine MFREE comparison is contextual, not a same-host superiority
test.  If the upper boundary is not crossed, the frozen Eta2 champion, B6v7
systems candidate, and Eta2-to-MFREE reliability portfolio keep their current
status.  There is no retry-count or seed tuning after the cohort.

