# Completed coverage and reachability study — 2026-09-11

Eta2 reaches the registered targets much faster than the measured frozen
Ceres dogleg profile on both storm scenes. Every available banked Caspar32
endpoint misses those targets. Venice52 remains a counterexample: the banked
Ceres LM runs reach its tighter target, and neither the original Eta2 nor the
tested stopping extensions do. The original Eta2 champion is unchanged.

## Same-host storm results

Each target was fixed before that scene's Eta2 measurements, at 1.01 times
the lower of the two complete Ceres N=3 median endpoints. Ceres used the
original frozen binary, 600 iterations and a 3600-process-second allowance;
Eta2 used its frozen flags, 600 outers and 60 native seconds, N=10. The
per-scene execution-order amendment changed scheduling, not this target rule.

| Scene | Fixed target | Eta2 hits | Eta2 crossing median [range], s | Ceres dogleg hits | Dogleg crossing median [range], s |
|---|---:|---:|---:|---:|---:|
| Final3068 | 1,744,796.9841897595 | 8/10 | 3.692232 [2.881787, 4.269963] | 2/3 | 1,302.742597 [686.494044, 1,918.991149] |
| Final4585 | 7,767,397.3902649265 | 10/10 | 1.696919 [1.691897, 1.704240] | 2/3 | 2,038.777140 [1,958.539994, 2,119.014287] |

The ratios of these **successful-subset** medians are 352.83 and 1201.46.
They are not unconditional expected-runtime speedups. Both Final3068 arms
have misses; the Ceres profiles and hardware must be named with the result.
Fresh Ceres LM is 0/3 on each storm target. Its native full-solve medians are
10.715 and 66.826 seconds, respectively; these are not target times.

Final4585 dogleg endpoints span 7.115M–8.306M despite all three runs reporting
parameter-tolerance convergence. The median reference is 7.690M. This is an
endpoint spread, not proof of distinct mathematical basins. Targets are based
on the preregistered median rule, not the luckiest observed endpoint.

The [complete ledger](SAME_TARGET_LEDGER.md) explicitly includes all available
Caspar32 profile/cap combinations with their FP64 rescored endpoints and full
native solve times. Final3068 paper/200 is **0/3**, median endpoint 2.039539M,
median full solve 0.771995 seconds; paper/2000 is also **0/3**, 0.760548 seconds.
Default settings miss too. Final4585's available groups are **0/1, 0/1, 0/1,
0/2**, with full solve times spanning 9.591–128.390 seconds. Those incomplete
banked group sizes are not represented as fresh N=3 measurements.

## Collaborator rows

Claude's exact-target Final3068 CSV contributes MFREE base **0/10 observed**
and guarded deep-reject **5/10 observed**. Successful deep runs finish in
15.693669 seconds median, range 14.971012–16.499705. These are **upper bounds
on crossing time**, measured on Claude's separate GPU host. A ratio to the
Codex-host Eta2 times is not a verified same-host speedup. The observed 8/10
versus 5/10 ordering does not establish a population reliability ranking;
see [RELIABILITY.md](RELIABILITY.md).

Claude also identifies the original Caspar-f64 aggregate as approximately
2.6351M and reports a target miss. It is included with that provenance.
Individual f64 repetitions, their count and solve times were not supplied;
none are fabricated from the old table's unrelated `3/3` column.

## Venice52: the stopping extension did not transfer

At the fixed target **243740.27**, both primary Eta2 arms are **0/10**.
The original champion has median endpoint 246309.540 in 1.546 seconds. With
FTOL disabled and the outer cap raised to 10000, the median is 244929.689 in
60.007 seconds. Longer execution improves the endpoint but does not meet the
registered criterion. This bounded miss does not prove unreachability.

The banked same-host Ceres LM runs hit **3/3** in 4.935336 seconds median,
range 4.678916–4.960021. Their 36.720-second median full solve is not their
crossing time. Claude's separate MFREE 300-outer endpoints near 241.6k show
reachability in that architecture; they do not establish it for Eta2.

Two subsequent, separately registered N=3 probes also miss: FTOL=1e-7 has
median endpoint 246040.002; tighter forcing from initialization has median
257725.345 at the 600-outer cap. Neither is promoted. Disabling FTOL changes
stop-confirmation/backtracking interactions as well as termination; tighter
forcing from initialization is not an isolated late-phase CG intervention.

## Ceres setup sensitivity

The separate [five-arm screen](ceres_setup/README.md) addresses whether the
minimal frozen driver's defaults inflate the comparison. On Final3068, all
five arms are **0/3** at the unchanged target within the 60-second allowance.
Normalization, stricter stopping, and inner eta=.01 lower the median LM
endpoint from 2.183295M to 1.810676M. That is a substantial setup effect, but
it does not produce a target hit in this screen. The stricter arms exhaust
their time allowances; they are not labeled converged accuracy floors.

The new driver first reproduced the original LM endpoint to better than
1e-9 relative in all three control runs. All 15 exported states passed an
independent original-observation audit, and the linked Ceres dependencies
match the old frozen binary's dependencies. These timings and endpoints stay
separate from the original Ceres reference medians. Five settings on one
scene do not establish globally optimal Ceres tuning.

## Evidence and claim boundaries

The study completed **58 primary/probe runs plus 15 setup-screen runs**, with
no native process failures. Forty-six Eta2 states and fifteen new Ceres
states were independently scored and preserved losslessly. The twelve old
Ceres runs retain the frozen driver's endpoint rescore and accepted/rejected
traces. The final audit verifies the original Eta2 source plus 44 headers,
the frozen binaries, input hashes, flags, target rule, and compressed states.
Banked Caspar32 and collaborator measurements remain separate additions.

The local matched model uses original-observation squared reprojection cost,
focal length and k1 free per camera, and k2 fixed at zero. Caspar32's internal
float representation is distinguished from its original-double endpoint
rescore. Native solve clocks exclude file loading and independent endpoint
audits. All timed local solves were serialized on the Codex host: RTX 2000
Ada and EPYC 9354, with a 6.8-core CPU quota and eight Ceres threads.

These results support scoped claims against the named measured profiles.
They do not establish the world's fastest BA solver, unrestricted endpoint
domination, or a benefit from multi-shift: this Eta2 champion uses one shift
and PCG. The optional external GPU tier was inspected for feasibility, not
benchmarked; see EXTERNAL_GPU_FEASIBILITY.md. The older paused 37/48 A/B/C/D
sweep tests a different solver configuration and remains paused by decision.

Reproduction: README.md, PROTOCOL.md, ORDER_NOTE_2.md, and the hashed native
evidence. Tables: SAME_TARGET_LEDGER.md and same-target-runs.csv. Figures:
figures/storm_target_attainment.png and figures/venice_reachability.png.
Verification: audit.json and ceres_setup/audit.json. The code and findings
live on research/eta2-external-coverage; the original algorithm is preserved.
