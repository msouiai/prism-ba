# Astra-guided research sequence

Status: completed all three bounded screens and correctness checks. The adviser
also independently reviewed their implementations and outcomes. See README.md
and advice/POST_SCREEN_FEEDBACK.md. No candidate passed promotion.

A1 late collective corrections:216 interventions plus54 continuation controls,
N=3, three real sampled BAL families/two targets. No fine steps saved.
A2 same-objective projective paths:270 synthetic runs, N=3. Moderate-parallax
speed benefit matched by established anchored inverse depth; low-parallax
gate failed and geometry failures remain. No real/native expansion warranted.
A3 residual-informed Schur selection:63 fixed native GPU solves, N=3. The deep
Muell case regressed even excluding refresh cost; shallow controls skipped.
The initial robust-bridge suggestion was deferred by the adviser because no
independent evidence certifies bridge correctness. It was not implemented.

Before each track: write its exact construction, controls, inputs, targets,
timing contract and stop rule. Validate algebra/state ownership first. Use
bounded development screens, then untouched seeds or held-out families. Keep
numerical error, model defect, regularization, geometry and timing distinct.
Preserve lambda/history when taking checkpoints. Do not use completed outcomes
to retune a frozen held-out policy.

Primary score is time to the same original objective, with all extra setup,
features, failed work and candidate evaluations charged. Report target misses
and geometric failures separately. Typical improvement gate is1.10x with no
extra failures; meaningful smaller effects can be reported without promotion.
More repetitions and native expansion are conditional on useful mechanisms.

Current production incumbent: frozen Eta2. A3 is a native fixed-system replay,
not a new end-to-end Eta2/Caspar comparison. The original solver is unchanged.
