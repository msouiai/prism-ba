# What the existing evidence supports

The new coverage study is in progress. This file audits existing claims; it
does not preannounce a result from the new Ceres or Eta2 runs.

The frozen Eta2 three-instance study is
[speed_novelty_results.md](../eta2_champion/docs/speed_novelty_results.md):
Ladybug539, Trafalgar138 and Final394; N=3 per scene/arm/tolerance; original
observations, k2 fixed, independently audited endpoints. Eta2 has the lowest
median target time in all nine scene/tolerance comparisons and 27/27 hits.
Its primary-target speed ratios versus Ceres LM are 20.43x, 12.48x and 25.06x;
versus Ceres dogleg they are 36.01x, 11.95x and 39.93x. This is a named-panel
same-host time-to-target result, not a universal SOTA claim.

Strict endpoint domination of Caspar32 does not follow from that table.
At the primary Ladybug539 target, Caspar32's audited median endpoint is
165447.466513 versus Eta2's 165514.082613: Caspar stops slightly lower, while
Eta2 is faster. Both meet the same target. Moreover, those endpoints occur at
target termination, not a common long-convergence budget. The user's practical
1% quality tolerance supports a speed comparison without requiring endpoint
domination; it does not turn a small cost difference into a strict inequality.

`/workspace/prism-novelty/novelty-results.json` is a different ledger: its Prism
arms are A-single, B-single-guarded, C-multi and D-multi-guarded, not the current
Eta2 configuration. It banks the relevant Ceres Venice52 endpoint and the old
profile selection, but its Prism speed rows must not be relabeled Eta2. The
remaining 11/48 legacy evaluation cells belong to that older study.

The new storm-scene coverage and fixed Ceres-derived targets will appear in a
separate report, with failures and bounded misses retained. A successful result
can expand the measured scope; it cannot establish fastest among all BA solvers
without a defined competitor set and further evidence.
