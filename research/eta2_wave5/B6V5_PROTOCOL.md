# B6v5 reduction-order-safe preparation fusion protocol

Registered after B6v4's N=10 tail cohort and before building or running this
follow-up.  B6v4 was a strong speed win (6.73% panel, 2.00% Muell), but its
dead-diagonal pruning shortens each observation thread before the next RHS
atomic.  Although the discarded diagonal cannot affect the mathematical
step, that scheduling change can alter the existing nondeterministic atomic
sum.  The Final3068 cohort was inconclusive across arms (off 9/10, prep 6/10,
dots 5/10, dots-prep 7/10), so the full arm is not promoted from that cohort.

B6v5 isolates the three transformations that passed the standalone bitwise
audit while retaining the champion's `MFRhsDiagFused` kernel unchanged:

1. point-factor construction plus the first `V_tau^-1 b_p` solve;
2. direct equilibration from the stored `H_cc` diagonal;
3. `(b_c - correction) * E` in one kernel.

The safe arm is `OCA_W5_PREP_SAFE=1`.  It has the same legality checks as
B6v4 and cannot be combined with `OCA_W5_PREP_FUSE=1`.  The latter remains the
full pruning arm.  The native comparison uses four fresh interleaved arms:
`off`, `safe`, `dots`, and `dots-safe`.

Run N=3 compatibility and the nine-cell practical panel.  Proceed to N=3
Muell/profile if safe improves off or dots-safe improves dots with identical
work.  Proceed to a fresh N=20 Final3068 cohort and N=10 Venice cohort only if
the panel gain survives.  The larger Final cohort is preregistered because
the prior N=10 four-arm hit rates ranged from 5/10 to 9/10 even between two
arithmetic-identical controls.

Promotion requires a panel and Muell timing gain, unchanged work on stable
cells, no endpoint movement above 0.15%, and no evidence that the
Final3068/Venice endpoint distribution changes relative to its corresponding
control.  If the safe gain is negligible, retain B6v4 pruning as an optional
throughput tradeoff and keep B6v2 dots-only as the production candidate.
