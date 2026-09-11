# Verdict: keep the frozen Eta2 champion

The two registered one-shot grafts are implemented and tested. Neither
passes its requested improvement gate. This is a negative result for these
specific policies, with useful evidence about why depth alone is insufficient.
The original algorithm and frozen champion source, flags and binary remain
unchanged. No new candidate is promoted.

Registration commit: `75ae3f4`; implementation commit: `d45914d`.
All 76 runs completed and independently scored their exported states against
the original fixed observations in CPU FP64. Same host, RTX 2000 Ada, serialized
native solves, 600 outers / 60 native seconds. No primary run hit a cap.

## Identical-target results

| Scene / arm | Target hits | Conditional target seconds, median [range] | Final cost, median | Outers | Rejects | Schur products |
|---|---:|---:|---:|---:|---:|---:|
| final-3068 / original | 6/10 | 3.310 [3.094, 6.217] | 1,743,777.959 | 62 | 8 | 300.5 |
| final-3068 / stop | 7/10 | 3.163 [1.432, 5.932] | 1,744,457.546 | 65.5 | 10 | 345 |
| venice-52 / declip | 0/10 | — | 246,337.154 | 105 | 7 | 394.5 |
| venice-52 / original | 0/10 | — | 246,351.957 | 122 | 4 | 438.5 |

Targets were fixed before these runs: Final3068 **1,744,796.9841897595**;
Venice52 **243,740.27**. Target times include native solver entry and are
conditional on hits. Final costs are endpoints under target early-exit,
not a converged-quality comparison. Counts, outers, rejects and products
in the table are per-arm medians.

**The apparent Final3068 7/10 versus 6/10 is not a measured rescue benefit.**
Every one of the candidate's seven hits occurred before a depth probe. The
three runs that would have stopped above target received the probe and all
three still missed. Thus the directly observed intervention result is
**0/3 rescued stopping endpoints**. The fresh baseline is 6/10, compared with
8/10 in the earlier independent batch; do not silently substitute historical
hits into this fresh paired-order experiment. N=10 does not estimate a precise
population success probability.

| Final3068 probe repeat | Original stopping cost | CG iterations | Raw relative residual | Probe accepted | Final target hit |
|---|---:|---:|---:|---|---|
| 0 | 1,850,855.484 | 12 | 0.000840364 | no | no |
| 1 | 1,762,641.758 | 1 | 3.35756e-06 | yes | no |
| 8 | 1,778,068.402 | 1 | 0.00027928 | yes | no |

The two accepted probes reduced cost by only about 0.16 and 0.20 initially;
subsequent ordinary iterations still stopped above target. Their deep solves
met the tightened residual tolerance in one iteration because damping was
large. The remaining probe met the tolerance in 12 iterations but failed
true-cost acceptance. None needed the 512 cap. The full per-probe traces are
in each run's `stdout.log` and `result.json`.

**Venice52 is 0/10 for both arms.** All ten de-clipping probes fire at the
same first eligible phase, after outer 39. Each encounters the existing
curvature cutoff in 10–55 iterations; none reaches the tighter residual
criterion. The registered conservative policy vetoes each and restores the
controller, so zero deep steps are committed. Endpoint/time differences
between these rejected-probe runs and fresh controls are not a performance
claim. Specifically, truncation is a cutoff failure, not proof of a negative
eigenvalue. Two truncated candidates had lower true cost and otherwise
passed model/radius checks; a policy accepting them would be a different,
unmeasured ablation.

## No-regression screen, N=3 per arm and scene

These runs use the ordinary stopping endpoint, with target early-exit
disabled. Consequently their native times are not time-to-equal-quality.
The requested guard was any paired endpoint regression >0.5% or paired wall
regression >20%, in addition to reporting median changes.

| Scene / arm | Median endpoint delta | Median native seconds | Median time delta | Registered pairwise gate |
|---|---:|---:|---:|---|
| dubrovnik-88 / original | +0.00000% | 0.425 | +0.00% | reference |
| dubrovnik-88 / off | +0.00011% | 0.420 | -1.07% | pass (0/3) |
| dubrovnik-88 / stop | +0.00021% | 0.475 | +11.95% | pass (0/3) |
| dubrovnik-88 / declip | -0.00006% | 0.474 | +11.61% | pass (0/3) |
| dubrovnik-88 / both | -0.00005% | 0.487 | +14.61% | FAIL (1/3) |
| ladybug-1197 / original | +0.00000% | 4.703 | +0.00% | reference |
| ladybug-1197 / off | -0.00408% | 4.795 | +1.96% | FAIL (1/3) |
| ladybug-1197 / stop | -0.01186% | 6.570 | +39.71% | FAIL (2/3) |
| ladybug-1197 / declip | +0.00072% | 4.492 | -4.49% | pass (0/3) |
| ladybug-1197 / both | -0.00566% | 6.138 | +30.53% | FAIL (2/3) |

No pair breaches the endpoint regression limit. The stop and combined arms
fail time gates. The flags-off control also has one Ladybug1197 pair with a
31.95% time increase, despite only 1.96% median time increase and virtually
identical endpoint quality. This exposes timing/trajectory variability in
this small screen; a single paired failure is the pre-registered rejection
rule, not proof that every such outlier was caused by a new mechanism.
The de-clipping flag never fires on Ladybug1197. The initial Dubrovnik88
compatibility check has identical 33-outer counts, at most 0.000353% paired
endpoint difference, and passes both tolerances. Bitwise determinism is not
claimed for atomic reductions.

## What to carry forward

The requested one-shot stopping graft fails its reliability criterion;
the de-clipping graft fails its target-hit criterion. The former's
successful-run median does not breach the 20% threshold, but those successes
never used its probe. Keep the original champion.

The more promising follow-up is **controller recovery, not another larger
CG cap**: the current radius can erase nearly the entire deep direction.
Away from clamps/interior exceptions, Eta2's update preserves lambda*R^2.
Restoring an old damping center while retaining a contracted radius does not
restore that controller pair. Separately, Venice's deep solve encounters a
curvature cutoff before convergence; audit its Rayleigh quotient with a
higher-precision operator at the same state before treating tighter CG as a
valid accuracy oracle. Neither follow-up has been tested here.

[INTERPRETATION.md](INTERPRETATION.md) develops those mathematical arguments
and their limits. [PROTOCOL.md](PROTOCOL.md) is the unchanged registration;
[summary.json](summary.json) contains every group, range and paired gate.
[README.md](README.md) gives the implementation and reproduction commands.
