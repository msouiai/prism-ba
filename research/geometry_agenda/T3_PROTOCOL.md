# T3 registration before comparative runs

Use the same two synthetic families, development seeds 0–9, held-out 100–109,
three timing repetitions and six-DOF CPU problem contract. Each arm starts at
lambda=0.1 and generates the same lambda/4, lambda, 4*lambda menu at its parent.
The ordinary baseline, post1, post3, pre1, pre3 and selective-pre1 differ only
in nonlinear point relaxation. All points remain independent candidate states.

Point steps use batched 3x3 GN with diagonal damping 1e-4, and per-point exact
cost/validity checks over t=1,0.5,0.25; one or three steps. Point0.z stays fixed.
Selective-pre1 chooses the worst quartile of per-track nonlinear-model defect
relative to linearized residual motion, computed from the already evaluated
raw candidate; charge feature cost and full projection work.

Rank by complete unchanged valid reprojection cost; accept only strict decrease.
For post arms, polish only the already selected raw winner. Pre arms polish
each candidate before ranking and commit its entire state. Skip polishing of
invalid raw candidates; retain those failures in the record. Use the same
lambda update (halve after acceptance, x4 after rejection; bounds 1e-8..1e8).
Cap 80 attempts / 2 seconds. Target is the original frozen formula from T2.

Report changed winners, point-solver cost, original and polished costs, point
stationarity, geometry and time-to-target. Diagnostic initial-state menus also
use 30 point iterations as a tightly iterated reference and report stationarity
rather than assuming global point minima. No held-out parameter tuning.

Gate: candidate changes in at least 10% of held-out ranked menus and at least
1.10x time-to-target versus ordinary menu and the corresponding post-only arm,
without extra misses or geometric failures. Otherwise retain point polishing
only as an engineering option and proceed to T4. No CPU result promotes Eta2.
