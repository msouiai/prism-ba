# Eta2 research findings — wave 2

Written 2026-09-12. Evidence: research branch `research/eta2-wave2`, campaign
commit `1cdd80abb1dd2515a363121014b99bb1677c7ed9`.

**Verdict: retain the frozen Eta2 champion as the general configuration.**
The campaign found a useful Venice opening policy and several informative
diagnostics, but no tested replacement improved convergence reliably across the
panel. “Winner” here refers to the configurations compared in this campaign;
there was no new Caspar or MFREE comparison.

The record contains **401 scored native runs and 24 compatibility runs**, plus
fixed-state audits and 21 additional step-composition diagnostics. The scored
objective stayed unchanged: full plain L2, identical observations, SIMPLE_RADIAL,
unshared intrinsics, and k2=0. The frozen source, configuration and 44 headers
were checked. All experimental changes are opt-in; the champion is preserved.

**Measured results**

The practical panel comprises Ladybug539, Trafalgar138 and Final394, each at
three registered tolerances, with N=3 per cell. Time ratios below are geometric
means of variant/control median time to the identical target; below 1 is faster.
Faster/slower counts require disjoint observed ranges, not just different medians.

| Intervention | Practical-panel result | Difficult-scene result | Decision |
|---|---|---|---|
| Tighter opening CG plus oversized-step rejection, ordinary storage | 1.0285× time; 4 faster, 4 slower, 1 overlapping | Venice 5/5 hits versus 0/5 control; Final3068 4/5 versus 4/5 | Keep as a narrow candidate; no general promotion |
| Coherent FP64 accurate opening | 1.4942× time; 0 faster, 7 slower, 2 overlapping | Venice 5/5; Final3068 3/5 versus 4/5 control | Extra precision workspace unnecessary for the Venice gain |
| Radius fitting, coupled point damping | 1.1808× time; 0 faster, 2 slower, 7 overlapping | Venice 0/5; Final3068 0/5 versus 2/5 control | Do not promote |
| Radius fitting, frozen point damping with caching | 1.2121× time; 0 faster, 2 slower, 7 overlapping | Venice 0/5; Final3068 1/5 versus 2/5 control | Do not promote |
| Analytic geodesic correction | 1.1195× time; 3 faster, 6 slower | Venice 0/5; Final3068 3/5 versus 4/5 control | Useful local corrections, no general speed gain |
| Bounded escalation at stopping | Practical expansion stopped at the registered kill criterion | Rescued 0/5 observed Final3068 stopping misses | Stop this arm |

Each stage used a fresh control cohort. Its hit counts must not be pooled with
other stages. N=5 counts are observations, not precise success probabilities;
N=3 disjoint ranges are a descriptive timing test, not confidence intervals.

**The usable positive finding: a cheaper Venice opening.**
For the first three accepted outers, eta=0.05 plus rejecting oversized raw
directions reaches the Venice52 target **243740.27 in 5/5 runs**, with median
crossing time **0.3130 s**, range **0.3121–0.3134 s**. The coherent FP64 reference
also hits 5/5, in 0.3754 s. Tighter forcing alone and the tested simple lambda
interventions do not reproduce this reliably. The combination matters; a
general scene-selection rule has not been validated. Final3068's registered
target is **1744796.9841897595**.

**The strongest diagnostic: a few cameras dominate the oversized directions.**
At the three Final3068 witnesses, the top five cameras account for approximately
**96.5–99.5% of squared raw-step norm**, while global similarity-gauge fractions
are tiny. Reconstructions at five failed static-damping Venice endpoints give
raw-step/radius ratios around **428**, top-five shares around **99.9999%**, and
gauge shares around **0.174%**. These reconstructions use saved terminal state
and controller values with fresh forcing history; they are not exact replays of
the historical final direction. Opening trajectories sometimes contain more
gauge motion, but never cross the proposed 50% trigger.

This evidence favors investigating exceptional camera directions. It does not
establish that their norm carries useful model decrease: the decompositions show
large cancelling contributions. The tested per-camera depth-preserving bound
also failed to control harmful proposals, so depth preservation alone is not
the solution.

**Better local directions did not guarantee better convergence.**
Certified radius fitting improves several witness decreases but worsens another,
then loses time in the native rollout. Analytic geodesic arithmetic fixes the
finite-difference audit failure and improves some witness proposals, yet its
always-on policy loses on six of nine practical cells. On Venice, hundreds of
geodesic corrections are accepted while the eventual median endpoint becomes
about 2.4% worse. The derivative, second-RHS implementation and independent
audits remain reusable assets.

**Limits and next direction.**
The next evidence-led hypothesis is to identify which pose or intrinsic
directions in the exceptional cameras consume the radius, then test a bound or
regularizer that preserves useful motion elsewhere. This is a proposal, not a
measured improvement. Keep the cheaper opening as a separate candidate until a
run-everywhere rule survives both faster and slower cells.

The radius-fitting tests used fresh PCG re-solves; a shared five-shift secular
root-finder was not implemented. Gauge-projected optimization and the optional
per-point TR, consistent-FP32 production and angular-shadow arms remain untested.
The differently numbered `ba_wave2_local_clocks.tex` was unavailable; these
results cover the pasted W1–W10 brief and do not claim to complete that document.
These findings support a mechanism report and negative-result record, not a new
universal fastest-solver or mathematical novelty claim.

Full handoff: [AGENT_FEEDBACK.md](AGENT_FEEDBACK.md). Per-cell numbers and ranges:
[NUMBERS.md](NUMBERS.md). Individual records: [metrics.csv](metrics.csv).
Build and evidence instructions: [REPRODUCING.md](REPRODUCING.md).
