# D15 deterministic paired confirmation protocol

Registered 2026-09-13 after the preregistered stochastic native screen and
before generating or running any paired input.  The stochastic screen was
directionally positive but unresolved: Final3068 target hits were 7/10 for
D15 and 5/10 for the frozen champion (one-sided Fisher exact `p=0.325`), while
the practical and Venice controls passed.  These rows are not pooled with the
paired cohort.

## Instrument and compatibility

The D15 source transformation is applied to the checksum-pinned D0v3
deterministic B6v7 measurement source.  Both paired arms use this one derived
binary, the frozen champion flags, the four wave-5 systems-only flags, and
`OCA_W6_DETERMINISTIC=1`.  The control leaves `OCA_D15_COUNT_PRIOR` unset; the
variant sets it to the already selected dose `1`.  No D15 gate, dose, trigger,
target, controller, stopping rule, or scored objective changes.

Before the paired cohort, the feature-disabled derived binary and the D0v3
parent must produce an identical endpoint-state SHA256, accepted-cost string
sequence, normalized decision trace, hit, outer, rejection and Schur-product
count on the unperturbed Ladybug539 1.01 compatibility cell.  A mismatch stops
the experiment.

## Common perturbations

Use Final3068 seeds `660000..660023`, in that order, at the D1 registered field
dose `epsilon=1e-12`.  Each pair receives the same byte-identical generated BAL
input.  Observation rows and indices remain byte-identical to the source;
`k2=0`.  Generate one input in `/dev/shm`, record its SHA256 and independent
initial residual distance, run both arms in alternating order, then delete it.

The registered target is `1744796.9841897595`, the cap is 60 seconds, and each
endpoint is independently rescored in FP64 on every original observation.
Time-to-target is taken from the first crossing in the native curve.

## Decision rule

Primary evidence is paired target-hit discordance.  Run a directional Wald
SPRT with `q0=0.50`, `q1=0.70`, `alpha=beta=0.05`, where
`q=P(D15-only hit | discordant pair)`.  Concordant pairs are retained but add
zero likelihood.  Stop early only if the registered SPRT reaches its D15-better
or D15-harmful boundary; otherwise stop at 24 pairs and report
`inconclusive_at_cap`.  Also report the exact one-sided McNemar/binomial
probability on the observed discordances; it is descriptive and does not
replace the registered sequential decision.

Secondary evidence is the paired target-time ratio on double hits, paired
endpoint delta in both directions, activation count, and trigger/build wall.
D15 is promoted only on the D15-better SPRT boundary, with no median target-time
loss above 20% on double hits.  It is killed on the harmful boundary.  Any
other outcome retains the frozen champion and records D15 as an unresolved
conditional mechanism.  No parameter may be changed after seeing a pair.
