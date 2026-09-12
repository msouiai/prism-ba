# Registered STCG arm: local speed gains, no promotion

All 74 timed runs completed, 54 practical and20 tail, with independent original-observation endpoint audits and matching attempt/native counters. The original/derived-off compatibility check passed before these runs.

The M-norm boundary-truncated arm is faster at the two tighter Final394 targets: **1.177x and1.221x**, with non-overlapping N3 timing ranges. Four practical cells regress with non-overlapping ranges; the largest is tight Trafalgar138, **17.7% slower**. Three Ladybug cells overlap. Both arms hit all27 practical targets. These are real local results, not a consistent replacement.

The tail comparison fails decisively for promotion in this sample. Final3068 hits are **4/5 off versus0/5 on**; median endpoint cost rises4.57%. Venice hits remain0/5 in both arms, and the on endpoint rises4.22%. The candidate's shorter termination time on misses is not time to equal quality. Full median/range, rejection, PCG and retry-wall rows are in `../STCG_NATIVE_RESULTS.md` and the machine-readable summary.

The proposed savings in inner work do appear: Venice averages about1.56 PCG iterations per outer under STCG versus1.63–1.69 off. This does not buy comparable nonlinear progress. Final's on arm also encounters and accepts computed-cutoff boundary proposals, yet misses the registered target in all five runs. A numerically accepted boundary event is not evidence of true negative curvature or improved basin selection.

This is a combined intervention: boundary truncation, an M-norm radius, variable-metric radius retention and removal of the persistent numerical floor. It does not isolate which change causes each result. In particular, retaining lambda*R^2 while M changes can materially change the physical constraint: in a lambda-dominated block M approximately equals lambda I, so the Euclidean radius is R/sqrt(lambda). Shrinking R while increasing lambda then contracts that physical radius faster than under the original metric. This is an algebraic risk of the registered rule, not a measured causal attribution for every failed run.

Do not compare the original floor event's immediate acceptance count with STCG's directly: a floor event necessarily restarts before scoring, whereas STCG scores its boundary proposal. The trace retains the following attempts so continuation outcomes can be studied. The requested universal 'persistent floor unnecessary' conclusion is unsupported.

**Frozen Eta2 remains the champion.** The standard STCG method is not broadly refuted. A pure boundary ablation in the original radius metric with the existing numerical repair would be distinct, but is not silently substituted for the failed registered arm or promoted from its two favorable cells.
