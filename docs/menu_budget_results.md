# Ten steps: short-budget and shared-target menu comparison

2026-09-08. **Local shared-target winners: fixed-five on two states, paired on one, single on one.** All 27 target runs reached their goals. This establishes short time-to-quality benefits for multishift on some controlled restarts. It does not replace **single + point repair as the incumbent on the original full Dubrovnik173 problem**, which was not rerun here.

## Ten completed steps

1. Froze binary, four shared BAL restart files, initial damping pairs, objective targets, and incumbent ledger.
2. Ran single, fixed-five, and paired with one-second native caps on all four states.
3. Repeated in reverse scene and arm order.
4. Compared objective decreases at a common 0.5-second post-initialization CSV cutoff, excluding later accepted states.
5. Ran all three arms to targets fixed from the preceding study, with two-second native caps.
6. Repeated those target comparisons in reverse order.
7. Audited initial objectives, actual starting damping pairs, final endpoints, and target crossings.
8. Repeated all three arms once more on the closest target comparison: later Dubrovnik173, where the first two medians differed by less than 1 ms.
9. Accounted for matrix-vector products, scoring, backtracking, and differing local winners.
10. Saved provenance and published this report; no algorithm or default changes.

## Time to equal quality: current local winners

All arms use point repair. Initial lambda/tau and geometry are identical within each state, with coupling disabled as in the preceding restart study. Targets were frozen before this round as initial cost minus three times the previous study's median single-hold one-outer decrease. These are fresh restarts, not continuations of controller/Krylov history.

| Shared post-repair state | Single | Fixed-five | Paired | Current local winner |
|---|---:|---:|---:|---|
| Dubrovnik173, repair 1 | **0.231 s** | 0.241 s | 0.475 s | Single, narrow lead over five |
| Dubrovnik173, repair 4 | 0.563 s | **0.520 s** | 0.580 s | Fixed-five, modest lead |
| Venice52, repair 1 | 0.372 s | 0.356 s | **0.292 s** | Paired |
| Venice52, repair 4 | 0.262 s | **0.197 s** | 0.275 s | Fixed-five |

Times are median native first-target crossings with independently CPU-validated final states. Dubrovnik repair 4 has three repeats after the prespecified closest-comparison selection; the other rows have two. Every target was reached within its two-second cap.

The clearest local gains versus single are paired on Venice repair 1 (**1.28x**, 21.6% less time) and fixed-five on Venice repair 4 (**1.33x**, 24.7% less time). Fixed-five's later Dubrovnik lead is 7.6% less time than single; treat it as modest. Single's earlier Dubrovnik lead over fixed-five is only about 4.3% less time. No universal winner emerges, and these few repeats do not establish statistical significance.

Before the third Dubrovnik repair 4 repeat, medians were 0.593 s single, 0.557 s five, and 0.557 s paired. The third run produced 0.563, 0.520, and 0.582 s respectively, yielding the medians in the table. This ranking sensitivity is why the narrow leads should not drive a new default.

## Equal-time screen

The native budget phase allowed one second per solve, then used the last accepted CSV state at or before **0.5 seconds since CSV initialization**. That clock excludes solver initialization and differs from the native target clock above. The common cutoff prevents an iteration finishing after the cutoff from earning extra quality credit. These are equal time windows, **not equal matrix-vector budgets**.

| State | Single objective decrease | Fixed-five decrease | Paired decrease | Largest decrease |
|---|---:|---:|---:|---|
| Dubrovnik173, repair 1 | 13092 | **13677** | 10928 | Fixed-five |
| Dubrovnik173, repair 4 | 739 | **1406** | 1141 | Fixed-five |
| Venice52, repair 1 | 15929 | 18779 | **22925** | Paired |
| Venice52, repair 4 | 17012 | **17229** | 17102 | Fixed-five, small difference |

Values are median absolute objective decreases, not percentages of final error. Intermediate cutoff costs are GPU trace values; the independently CPU-audited exported state is the final endpoint, which can occur later. Accordingly the shared-target table is the stronger evidence for validated equal-quality timing.

The different winner on early Dubrovnik between a fixed-time window and a quality target is substantive: a ranking depends on where the target lies along the trajectories. A larger decrease after half a second does not imply reaching every earlier target faster.

## Where the time goes

The two-repeat target phase showed:

- Early Dubrovnik: single used 82 matrix-vector products and scored 31 candidates; fixed-five used 69 but scored 60. Despite fewer matrix-vector products, five took slightly longer. Paired used 185 and scored 87, taking about twice as long as single.
- Early Venice: paired used 219 matrix-vector products versus single's 305, with fewer rejected attempts (1 versus 3). Although it scored more candidates (60 versus 40), it reached the target faster.
- Later Venice: fixed-five used 142 matrix-vector products versus single's 200 and paired's 193, paying for 48 scored candidates versus 36 and 64 respectively. It won the measured target race.

Thus multishift can pay for its extra scoring when it saves enough subsequent linear-solver work. Paired is not consistently the best way to do that. These comparisons also reinforce that matrix-vector count alone is an incomplete cost model: candidate evaluation and other solver work matter.

## Validation and reproducibility

51 solves consumed **35.955 native solver seconds**: 24 budget runs, 24 target runs, and 3 confirmation runs. Process startup, loading, and CPU audits are additional. All final endpoint audits and monotonicity checks passed; maximum CPU relative discrepancy 2.93e-14. All 51 first-attempt damping pairs matched the protocol, and initial objectives agreed with the common CPU references within 2.00e-15 relative. All 27 target runs hit before the native deadline and passed the endpoint target check.

Artifacts: `/workspace/prism-budget-ten/` holds the frozen protocol, steps, targets, plans, per-run manifests/logs/CSV/JSONL/states/results, confirmation-selection rationale, confirmed medians, summary, provenance, and completion. All arms used `/workspace/prism-probe-skip/prism-v4`; source and solver behavior were unchanged. Eleven previous jobs remain paused. No large-scene run, Caspar run, or push occurred.

## Verdict and next step

Current local winner count is **fixed-five 2, paired 1, single 1**, with two modest margins. Current original-scene Dubrovnik173 incumbent remains **single + point repair**; earlier Ladybug1197/Trafalgar126 incumbent remains frozen paired. Do not pool these observations into a post-hoc universal winner.

The next useful test is a short original-input comparison of all three arms at the same previously established quality targets on Dubrovnik173 and Venice52. This checks whether fixed-five's promising restart behavior survives the opening trajectory and retained controller history. Run two repeats with short existing caps; promote nothing unless the original-scene time-to-quality results support it. The present evidence supports continuing work on multishift, but not another blanket relaxation of damping or a claim of superiority over Caspar.
