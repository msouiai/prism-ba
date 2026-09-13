# D13 native verdict: always-on GMRES is rejected

## Verdict

Always-on right-preconditioned GMRES(8) is rejected despite its 6.17x
fixed-system win.  On the nine registered practical cells it is 1.330x slower
in geometric-mean time to the same target.  Seven of nine cells have disjoint
timing ranges in the losing direction, and the tight Trafalgar cell falls from
3/3 hits to 2/3.  The large Muell control falls from 3/3 hits at 4.217 s to 0/3
within the 12 s cap.  The preregistered tail gate therefore fails and Venice52
and Final3068 were not run.

The frozen champion remains the current scientific winner.  The wave-5
optimized candidate remains the current systems winner, with its previously
measured 8.66% panel speed gain and identical-algorithm caveat.

## Native rows

All comparisons are N=3 and use identical registered targets.  `GMRES/control`
is the ratio of median crossing times; endpoint deltas below 0.15% remain
unresolved.

| Cell | Control hits | GMRES hits | GMRES/control | Products control → GMRES | Outers control → GMRES |
|---|---:|---:|---:|---:|---:|
| Ladybug539 1.005 | 3/3 | 3/3 | 1.046x | 52 → 55 | 9 → 9 |
| Ladybug539 1.010 | 3/3 | 3/3 | 1.196x | 42 → 45 | 6 → 7 |
| Ladybug539 1.020 | 3/3 | 3/3 | 1.070x | 42 → 42 | 6 → 6 |
| Trafalgar138 1.005 | 3/3 | **2/3** | 2.326x conditional | 594 → 1417 | 13 → 19 |
| Trafalgar138 1.010 | 3/3 | 3/3 | 1.435x | 462 → 553 | 10 → 13 |
| Trafalgar138 1.020 | 3/3 | 3/3 | 1.339x | 232 → 263 | 8 → 10 |
| Final394 1.005 | 3/3 | 3/3 | 1.388x | 135 → 183 | 11 → 15 |
| Final394 1.010 | 3/3 | 3/3 | 1.424x | 86 → 129 | 9 → 11 |
| Final394 1.020 | 3/3 | 3/3 | 1.099x | 50 → 61 | 8 → 8 |
| Final1936 | 3/3 | 3/3 | 1.008x | 16 → 16 | 4 → 4 |
| Muell-gba146 | 3/3 | **0/3** | no crossing | 980 → 3215 | 16 → 24 |

The no-flag derived binary reproduces the frozen binary to `1.8e-15` relative
endpoint error on the N=3 compatibility cell, with identical 42 products and
six outers.  The regression is caused by the enabled method rather than the
overlay or build.

## Why the fixed result did not transfer

The fixed Muell witnesses are states reached by the champion's PCG trajectory.
At those exact states, GMRES reaches the loose Euclidean residual gate in two
steps.  When GMRES is active from outer zero, however, its different
residual-minimising directions alter the accepted nonlinear path before those
states exist.  It then reaches low-damping systems where restarted GMRES(8)
stagnates: several Muell attempts consume 128 Arnoldi iterations / 144 products
and still have relative residuals from 0.66 to 0.99.  PCG's energy-minimising
directions are more useful to the nonlinear trajectory even when they are less
efficient for the isolated Euclidean forcing test.

This is another concrete instance of the campaign's central warning: linear
accuracy and nonlinear usefulness are different objectives.  It also narrows
the remaining opportunity.  Replacing PCG globally is dead.  A PCG-preserving
residual replacement or minimum-residual rescue may still help only after a
deep solve is already detected; it must leave shallow attempts and their
directions identical.

## Provenance

The opt-in source is derived reversibly from the checksum-pinned champion and
stores nine camera vectors.  It verifies the exact residual every cycle and
checks the Arnoldi residual identity.  Registration, complete native rows and
summaries are in `d13-native-registration.json`, `d13-panel-results.json`,
`d13-panel-summary.json`, `d13-controls-results.json`, and
`d13-controls-summary.json`.  Build and run scripts are in `d13_krylov/`.
