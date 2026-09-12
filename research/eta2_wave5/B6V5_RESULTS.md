# B6v5: reduction-order-safe preparation fusion

## Verdict

The three bitwise preparation fusions are behavior-preserving but do not
replace the B6v2 dots-only production candidate.  They improve the practical
panel by **1.79%** alone and **2.03%** when combined with dots, but show no
measurable Muell benefit.  This establishes that nearly all of B6v4's
large-scene gain comes from removing the discarded Schur-diagonal work.

## Arithmetic and compatibility

The standalone CUDA audit used 100,003 synthetic point blocks and 10,007
camera blocks.  Factor-plus-solve, direct equilibration, and fused
`(b_c-correction)E` were bit-identical to the separated operations.  The
derived-off binary reproduced the frozen champion at `1.14e-14` relative
endpoint difference.

Unlike B6v4, safe mode retains `MFRhsDiagFused` unchanged, including the
discarded diagonal arithmetic and RHS atomic timing.  It only removes three
launch/global-memory round trips whose outputs passed the bitwise audit.

## Practical panel

All 108 rows hit and all nine median product counts matched.

| Comparison | Geometric-mean target-time ratio | Disjoint faster / overlap / slower |
|---|---:|---:|
| safe / off | 0.9821 | 8 / 1 / 0 |
| dots+safe / dots | 0.9887 | 6 / 3 / 0 |
| dots / off | 0.9909 | 7 / 2 / 0 |
| dots+safe / off | 0.9797 | 7 / 2 / 0 |

Maximum median endpoint movement was 0.00189%.

## Muell and profile

Safe/off target time was 4.2141 → 4.2161 s (ratio 1.0005, ranges overlap).
Dots/dots+safe was 4.2064 → 4.2017 s (ratio 0.9989, ranges overlap).  The
profile bucket remained 0.241–0.243 s for all arms.  At this scale the saved
launches and small point/camera array passes are below measurement resolution;
the 3.05 s Krylov phase dominates.

## Tail distributions

The preregistered larger cohort supports behavior preservation:

| Scene | off | safe | dots | dots+safe |
|---|---:|---:|---:|---:|
| Final3068 target hits, N=20 | 10/20 | 10/20 | 13/20 | 11/20 |
| Venice target hits, N=10 | 0/10 | 0/10 | 0/10 | 0/10 |

Final3068 conditional target-time ranges overlap broadly.  Off/safe endpoint
medians differ by +0.139%, and dots/dots+safe by +0.091%, below the 0.15%
cost threshold and small relative to the scene's basin spread.  Venice modes
overlap in every arm; no arm reaches 243,740.27.

## Decision

Safe fusion is a useful implementation asset for a future small-scene CUDA
graph or persistent-kernel path, where several launch savings can be combined.
As a standalone change it fails the registered requirement for a Muell timing
gain.  B6v2 dots-only therefore remains the production candidate while B6v4's
larger pruning arm receives the final distribution test.
