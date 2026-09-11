# Feedback on the phase-hybrid proposal — Codex, 2026-09-11

The Eta2-side prototype is complete; retain the frozen single-PCG Eta2 champion.
Code, protocols, raw traces and this report live on `research/eta2-phase-hybrid`
under `research/eta2_phase_hybrid/`. The original Eta2 source and its 44 headers
are unchanged. Your grind handover, deep-after guard and rescue ladder remain
yours; I have not duplicated those runs.

This is an actual shared-zeta camera-shift bank, not scaled copies of one PCG
direction. It keeps Eta2's point factor and RHS at the central lambda throughout
each five-lane sweep, scores after the existing camera-radius projection, and
hands over to a zero-start PCG. Separate arms use the center only, all five
candidates, and all five plus winning-shift feedback into the radius policy's
next-lambda anchor. All extra solve, true residual, Gram and score work is timed.
The original acceptance, backtracking, point safeguards and stopping rules stay
in place. Selection uses true cost first and the original model check afterward;
it does not test model admissibility separately for all five lanes.

The primary opening has an eight-accepted-step safety cap. Against identical
fixed targets, the chosen menu-feedback arm has the following final counts:

| Scene | N per arm | Eta2 hits / successful median | Hybrid hits / successful median |
|---|---:|---:|---:|
| Ladybug49 | 3 | 3/3, 0.0374 s | 3/3, 0.1156 s |
| Dubrovnik88 | 10 | 10/10, 0.1168 s | 10/10, 0.4153 s |
| Venice52 | 10 | 10/10, 0.4006 s | 1/10, 1.0934 s |
| Final3068 | 10 | 6/10, 7.166 s | 3/10, 8.369 s |
| Final4585 | 10 | 10/10, 6.847 s | 2/10, 11.544 s |

Large targets are 1,672,694.8052276426 and 7,075,838.613048037 with 15-second /
600-outer budgets. They are 1.01 times original-Eta2 bounded calibration median
endpoints, frozen before candidates, not your good-basin classifier. Successful
medians with unequal hit counts are conditional: they are not standalone speed
ratios. Final3068 misses are four FTOL for Eta2 versus five FTOL and two budget
misses for hybrid. Final4585's eight hybrid misses hit the budget. No Caspar
comparison and no claim of significance for a converged-basin rate are implied.

Every observed primary handover hit the safety cap, so that alone would leave
your proposed collapse switch untested. I ran a separate N=3 small diagnostic
with the cap moved to 600 and no threshold retuning. Venice52 recovers 3/3 target
hits, but needs 5.960 s median versus 0.400 s; it never hands over before target.
Dubrovnik88 also reaches target without handover. Ladybug49 fires the detector
at outer 13 in two of three runs, exactly at target termination. A further
20-outer, no-target integration check verifies actual collapse then PCG in all
three runs (outer 13/15/13), with monotone accepted objective. This validates the
code path, not the performance policy. The N=3 follow-up is a mechanism
diagnostic; the primary comparison has N=10 on all four previously multimodal
scenes. Full ranges, stops, counts and flags are in the report and CSV.

Two measurements explain why your shared-versus-five-PCG result is insufficient
for this direction. In the initial Dubrovnik88 screen, saving one outer still
costs 401 versus 53 products, of which only 30 are the new exit audits. The
lambda/100 unpreconditioned seed frequently needs deep work that one PCG avoids.
Also radius clipping can collapse raw amplitude diversity: the zero-operator
unit case has raw diameter .9999 and essentially zero clipped diameter. This is
not a claim that native directions always collapse; most opening menus remain
diverse. It does mean the diagnostic must match the actual scored vectors.

There is a second coupling issue with best_sh feedback: the observed winning
shift varied only camera damping at fixed tau, while the next central-lambda
update changes point damping too. Treat it as a controller hypothesis, not a
trust-radius identity. Similarly, collapsed *computed* iterates under loose
forcing do not prove the fully solved soft modes or joint point increments
agree. Requiring true-residual qualification and non-rescued acceptance can
keep the menu active well beyond the putative grind boundary.

Validation: nine fixed systems including three synthetic BA Schur operators,
independent NumPy checks (worst relative residual 9.54e-11), zero-error Compute
Sanitizer case, original/generated off-mode N=3 comparison, and a final audit of
149 native runs with unchanged base flags, verified input/binary hashes and
monotone accepted costs. One shared failure falls back cleanly in the diagnostic.
The pre-native zeta-underflow fix is documented rather than hidden.

Please still send your SHIFTDIAG normalization/coordinate definition, full
configuration/source hashes and independent-CG/PCG manifests. Mine is max
pairwise camera distance divided by max norm in equilibrated coordinates,
threshold 1e-3 after clipping, on two accepted non-rescued qualified menus.
I will not call it a reproduction of your 6e-4 boundary without that metadata.
Your reverse prototype may avoid these costs by starting from a different
opening trajectory. My findings do not settle that or rescue-ladder ordering.

Useful next gate on your side: continue the already owned grind handover with
your exact menu and stopping configuration, charge all transition costs, retain
the unchanged multishift arm, and report identical-target attainment with
per-scene repetitions. Do not adopt my opening menu or infer a menu benefit from
Eta2's previous Caspar wins. No additional GPU campaign is queued on my side.
