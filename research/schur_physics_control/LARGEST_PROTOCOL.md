# Final13682 extension — registered before runs, 10 September 2026

Purpose: extend the coarse Schur screen to the largest BAL scene previously
used in this project (13,682 cameras, 4,456,117 points, 28,987,644 observations).
Keep testing short, use existing quality targets, and distinguish scene size
from actual activation of the preconditioner.

Reference: unchanged frozen eta2 configuration, measured generated binary
`build/prism-coarse` from commit 2db2175. Candidate: same binary, changing only
`OCA_COARSE_RANK` from 0 to 16. Rank16 was the less costly active candidate in
the preceding Muell screen; it was not promoted. No new tuning or compilation.

Primary target: 27591576.557625167. Tighter target: 27318392.631312046.
Both are copied from `research/eta2_champion/docs/rl_sustained_protocol.md`.
Run N=3 alternating pairs per target, max600 outers, max12 native seconds,
max120 process seconds (large text input loading is outside native timing).
Report native TARGET events, final cost, outers, rejects, products, coarse
activation counts, hit/miss, and process/GPU memory observations. Keep all
outcomes; a miss is not assigned an artificial target time.

Then make one paired activation probe with no target, max30 outers and max12
native seconds. If rank16 activates, complete N=3 for that probe; otherwise
stop at N=1 and report that it did not exercise the active mechanism. These
capped endpoints are diagnostic, not equal-quality speed ratios. No gradient
instrumentation is enabled in timing runs. Total intended native budget is
under180 seconds. Serialize GPU via /tmp/prism_gpu.lock; retain small traces
and hashes, without exporting full states or multi-gigabyte Schur captures.

Require the existing measured binary hash and frozen source/header checks to
pass before execution. Earlier CUDA memchecks already exercised rank16 and
its workspace; no source change requires recompilation for this extension.
The incumbent remains eta2 unless there is consistent useful target gain.
No new Caspar or v2 comparison is inferred from this Prism-only test.

Diagnostic amendment before executing the diagnostic: also run one capped
eta2 endpoint with the existing extended terminal curvature probe, max30
outers and max12 native seconds, no target. This is a separate instrumented
binary/trajectory, and its timing is excluded from all speed ratios. Verify
its previously measured hash and retain all scales and the no-state-change
marker. N=1 is a transfer observation, not a claim about this scene's endpoint
distribution. This adds no state export and at most one short run.
