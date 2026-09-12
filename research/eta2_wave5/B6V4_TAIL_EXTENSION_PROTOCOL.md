# B6v4 Final3068 distribution extension

Registered after B6v4 N=10 and B6v5 N=20 completed, before any extension
run.  The purpose is to decide whether B6v4's removal of a mathematically
discarded Schur diagonal changes Final3068 basin reliability.

The controls are pooled before looking at any new active result:

- `off`: B6v4 N=10 plus B6v5 N=20;
- `dots`: B6v4 N=10 plus B6v5 N=20.

Pooling is valid for this reliability question because both derived-off
binaries reproduce the same frozen champion within `1.2e-14`, B6v5 is formed
by adding a dormant opt-in path to B6v4, and the dots implementation in both
is inherited unchanged from the same B6v2 derivation.  The pooled control
counts are therefore fixed at N=30 before this extension.

Run 20 fresh Final3068 repetitions of `prep` and `dots-prep` with the B6v4
binary and frozen target 1,744,796.9841897595.  Combine them with each arm's
existing B6v4 N=10 to obtain N=30 active cohorts.  No additional Venice runs:
all four B6v4 arms and all four B6v5 arms were 0/10, and their endpoint modes
overlap.

Report hit counts, Wilson 95% intervals, two-sided Fisher exact p-values,
conditional target-time medians/ranges, and endpoint medians.  Evidence for a
reliability loss requires both an active hit rate at least 15 percentage
points below its matched control and Fisher p < 0.05.  Otherwise the result
is unresolved/equivalent at this sample size; it is not evidence for a
reliability gain.  Speed claims continue to come from the paired stable panel
and Muell cohorts, not this multimodal tail cohort.
