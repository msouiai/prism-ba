# B6v2: dots-only PCG synchronization

## Verdict

Dots-only batching is the current wave-5 systems winner and a promotion
candidate.  It improves the practical-panel target-time geometric mean by
**1.32%**, preserves the exact work count on all nine cells, and loses no tail
hits in fresh N=10 cohorts.  The frozen Eta2 champion remains untouched while
an exact-rounding vector-fusion follow-up tries to recover the rest of B6's
larger gain.

## Intervention and compatibility

The active arm leaves every cuBLAS vector update unchanged.  It changes only
the synchronization of two independent dot-product pairs in each PCG
iteration: results are produced by ordinary FP64 cuBLAS into device memory and
returned in one 16-byte copy per pair.  The derived-off binary reproduced the
frozen champion at `7.1e-15` relative endpoint error in the N=3 compatibility
gate.

## Practical panel

All 54 rows hit.  Median products, outers, and rejects are identical in every
cell.  Maximum median endpoint movement is below `1e-6` relative.  Geometric
mean target-time ratio is **0.9868**.  Five cells have disjoint ranges in the
active arm's favour and none has a disjoint slowdown.

| Cell | Active/control target time | Products, off/on |
|---|---:|---:|
| final-394, 1.005 | 0.993 | 135 / 135 |
| final-394, 1.01 | 0.995 | 86 / 86 |
| final-394, 1.02 | 0.988 | 50 / 50 |
| ladybug-539, 1.005 | 0.988 | 52 / 52 |
| ladybug-539, 1.01 | 1.084 | 42 / 42 |
| ladybug-539, 1.02 | 0.985 | 42 / 42 |
| trafalgar-138, 1.005 | 0.902 | 594 / 594 |
| trafalgar-138, 1.01 | 0.977 | 462 / 462 |
| trafalgar-138, 1.02 | 0.978 | 232 / 232 |

The one 8.4% median slowdown is a 60 ms cell whose ranges overlap broadly;
it does not survive the registered disjoint-range rule.  The strict Trafalgar
cell is the strongest signal: 9.8% faster with identical 594 products.

## Profiles and Muell

At Trafalgar-138/1.005, Krylov time fell from 0.243 to 0.236 seconds and target
time by 2.1% in the separately profiled cohort.  On Muell, Krylov fell from
3.051 to 3.036 seconds.  The independent Muell timing cohort kept 980 products
and 3/3 hits, with target time 4.2218 to 4.2025 seconds (0.46% faster; ranges
disjoint).  The decreasing benefit with larger products matches the launch and
synchronization hypothesis.

## N=10 tails

| Scene | Hits off/on | Conditional target median off/on | Endpoint median off/on |
|---|---:|---:|---:|
| Final3068 | 8/10 / 8/10 | 4.092 / 4.197 s | 1,743,427 / 1,739,387 |
| Venice52 | 0/10 / 0/10 | n/a | 246,343.30 / 246,346.95 |

Final3068's conditional-time ranges overlap (`2.189--5.881` versus
`2.680--4.860` seconds), so the 2.56% median difference is unresolved.  Its
active endpoint is 0.232% lower.  Venice's relative median movement is
`+0.0015%`.  Product counts differ on the tails because the runs sample their
known trajectory modes; hit rates do not regress.

## Attribution from B6 and B6v2

Dot synchronization accounts for about one third of the combined B6 panel
gain (1.32% of 3.62%).  The remaining gain is in vector launch fusion.  The
combined implementation allowed `z + beta*p` to contract into one FMA, whereas
the champion rounds the scale before the add.  The next arm uses explicit
round-to-nearest multiply then add inside one kernel, retaining the champion's
two arithmetic rounding points while avoiding the extra global-memory pass and
launch.

