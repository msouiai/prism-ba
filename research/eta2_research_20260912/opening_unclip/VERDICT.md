# Opening unclipping alone: does not explain the Venice success

The complete84-run native grid is in [OPENING_UNCLIP_NATIVE_RESULTS.md](../OPENING_UNCLIP_NATIVE_RESULTS.md). All target and endpoint audits pass. This arm changes just the radial scaling shortcut during the first three accepted outers, preserving original precision and forcing.

Venice target hits remain**0/5 off and0/5 on**. Median endpoint rises from246129 to253188, **2.87% worse**, even though reject counts fall from4–13 to2–5. Fewer rejects alone therefore do not establish better convergence. The full accurate-opening arm's separately confirmed10/10 Venice success cannot be attributed to this clipping switch alone.

The modified branch is actually exercised once in every Venice on-run. It is never exercised before handoff on Final3068, Ladybug1197, or any of the nine practical cells; [branch_activity.json](branch_activity.json) records this. Thus the observed Final3068 hit counts4/5 off versus2/5 on are reported but are not evidence for an algorithmic clipping regression on that scene. They illustrate the small-cohort trajectory variability of an inactive control. Practical timing ranges overlap in all nine cells, and both arms hit27/27. Ladybug1197 hits5/5 in each arm with overlapping crossing ranges.

No promotion. The supported local statement remains that the combined accurate-opening arm helps Venice, with unresolved attribution among accuracy, coherent products and their interaction with the opening radius/retry path. This negative single-ingredient test is retained rather than changing the candidate's window or flags after seeing its result.
