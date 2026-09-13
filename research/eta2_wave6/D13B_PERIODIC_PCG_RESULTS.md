# D13b verdict: periodic PCG residual replacement is rejected

## Verdict

Periodic exact-residual replacement and a valid Hcc-PCG restart every eight
iterations is rejected.  It is 1.456x slower in geometric-mean time to the
same target on the nine registered practical cells, and every cell is slower.
On Muell it turns the frozen solver's 3/3 target hits at 4.225 s into 0/3
within the 12 s cap, increases the median Schur-product count from 980 to
3,309, and ends 0.484% higher in cost.  The preregistered tail gate therefore
fails; Final3068 and Venice52 were not run.

The frozen Eta2 champion remains the scientific winner.  The wave-5 optimized
candidate remains the systems winner, with its previously measured 8.66%
panel speed gain and identical-scientific-algorithm caveat.

## Native rows

All rows are N=3 at identical registered targets.  `Restart/control` is the
ratio of median target-crossing times.  Endpoint differences below 0.15% are
unresolved.

| Cell | Control hits | Restart hits | Restart/control | Products control -> restart | Replacements | Outers control -> restart |
|---|---:|---:|---:|---:|---:|---:|
| Ladybug539 1.005 | 3/3 | 3/3 | 1.086x | 52 -> 54 | 3 | 9 -> 9 |
| Ladybug539 1.010 | 3/3 | 3/3 | 1.123x | 42 -> 44 | 3 | 6 -> 6 |
| Ladybug539 1.020 | 3/3 | 3/3 | 1.019x | 42 -> 44 | 3 | 6 -> 6 |
| Trafalgar138 1.005 | 3/3 | 3/3 | 2.853x | 594 -> 2,054 | 214 | 13 -> 21 |
| Trafalgar138 1.010 | 3/3 | 3/3 | 2.058x | 462 -> 1,053 | 109 | 10 -> 14 |
| Trafalgar138 1.020 | 3/3 | 3/3 | 1.330x | 232 -> 338 | 34 | 8 -> 9 |
| Final394 1.005 | 3/3 | 3/3 | 2.436x | 135 -> 430 | 38 | 11 -> 16 |
| Final394 1.010 | 3/3 | 3/3 | 1.209x | 86 -> 109 | 7 | 9 -> 10 |
| Final394 1.020 | 3/3 | 3/3 | 1.029x | 50 -> 54 | 2 | 8 -> 8 |
| Final1936 | 3/3 | 3/3 | 0.961x, overlapping | 16 -> 16 | 0 | 4 -> 4 |
| Muell-gba146 | 3/3 | **0/3** | no crossing | 980 -> 3,309 | 343 | 16 -> 30 |

Final1936 is the intended inactive control: every linear solve terminates
before depth eight, no residual replacement fires, product and outer counts
are identical, and the timing ranges overlap.  The no-flag derived binary also
reproduces the frozen binary on the N=3 compatibility cell with identical
products and outers and relative endpoint error below `2e-15`.

## Why the fixed-system result did not transfer

At the frozen Muell outer-11 witness, restart-8 changes a 128-product miss into
a 22-product hit.  That isolated result does not imply an always-on schedule.
Natively, every restart discards accumulated A-conjugacy.  On systems that
would have converged without replacement, the extra exact product and lost
subspace increase work; the changed directions then alter accepted outer
steps.  Trafalgar138 at the tight target grows from 594 to 2,054 products, and
Muell enters a feedback loop in which 343 replacements accompany 30 outers
instead of 16.  The method fixes a particular finite-precision recurrence at a
particular state while degrading the nonlinear trajectory that creates later
states.

This closes periodic restarting as a global Eta2 policy.  It does not refute a
one-shot rescue triggered after an observed deep-solve failure, but such a
rescue would be a tail mechanism and must leave all earlier PCG recurrences
unchanged.  The stronger campaign conclusion remains that optimizing a linear
residual metric in isolation is not a reliable proxy for nonlinear BA
progress.

## Provenance

The opt-in implementation is a reversible overlay on the checksum-pinned
champion.  Every replacement explicitly computes `r=b-Ax`, charges its Schur
product, reapplies the existing preconditioner, and starts a mathematically
valid PCG segment without a new camera vector.  Registration, raw parsed rows,
and summaries are in `d13b-native-registration.json`,
`d13b-compatibility-results.json`, `d13b-panel-results.json`, and
`d13b-controls-results.json`, with their corresponding `*-summary.json`
files.  Build and run scripts are in `d13_krylov/`.
