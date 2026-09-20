# Frozen RL damping pilot protocol

2026-09-09. User authorized implementation after the literature review.

Baseline: frozen coupled-radius numerical-guard LM from
`/workspace/prism-model-followup/candidate`, SHA-256
`117773562d33949cdbfdc27905d1f23a2cc1faedb7f77c3e619c17caa50a86dc`.
Use its selected flags and explicitly `--lam0 0.1` in every paired run.
This is the metadata configuration, not the earlier Muell command that used 10.

The isolated derivative adds accepted-boundary checkpoint continuation,
history/telemetry, and actions -1/0/+1 multiplying the baseline's nominal next
lambda by 0.1/1/10. Point damping remains coupled. Apply one intervention at
the restored boundary, then continue the baseline. Numerical repair, radius,
acceptance, retry rules, and linear tolerances are unchanged.

Before data collection, test original versus derivative off, action zero,
checkpoint continuation, mismatched-checkpoint rejection, and effective
nonzero actions. Require finite telemetry and original-observation FP64 cost
agreement within 1e-7 relative. Judge continued-trajectory deviations against
same-binary repeats, not assumed bitwise determinism of CUDA atomics.

Training families: Ladybug-49, Dubrovnik-88, Venice-52. Eight intended
checkpoints per scene, before outer indices 1 through 8, captured with their
complete boundary state. If stopping makes a checkpoint unavailable, report
it rather than manufacture or silently substitute it. Geometry-only resets
are not admissible counterfactuals.

First screen: three actions, four subsequent outer iterations, all from the
same checkpoint bytes. Repeat all arms N=3 to quantify label noise, alternating
action order. Native compute ceiling 600 seconds over pilot GPU solves;
process startup, builds, checkpoint I/O and audits tracked separately.

The short-rollout comparison uses a common elapsed-time horizon per checkpoint:
the minimum measured rollout duration across the action/repeat set. Compare
the area under each right-continuous accepted-cost curve up to that horizon,
normalized by the checkpoint cost and duration. Lower is better. Include the
initial cost before the first accept; do not credit an accepted state before
the work that produced it. Also report equal-time endpoint progress, rejects,
matvecs and effective action. This is a development reward; final promotion
requires time to an independently fixed quality target.

Signal gate: report baseline versus per-state hindsight winner, and between-
action separation relative to baseline repeat spread. A hindsight winner is
an optimistic diagnostic. Fit a compact regularized action-value model only
if at least six available checkpoints across at least two families show a
non-baseline median advantage larger than the baseline's min-max spread.
Evaluate prediction by leaving entire families out. Compare against the best
constant action and a deterministic work-aware rule. Do not call this small
cross-validation a population-wide generalization result.

If the model has positive held-out-family aggregate advantage over baseline
and the best constant action, freeze it for N>=3 complete solves on
Trafalgar-126 and Final-1936 plus Muell transfer. Those are unseen for fitting,
but already used in research; none is a pristine new recording. Compare
same-binary baseline and a simple work-aware controller before a fresh Caspar
extension. Use existing targets; report certified hits and native time with
feature/inference overhead. Require a useful approximately 10% panel speedup
without losing reliable hits to promote. Otherwise retain the incumbent and
report the negative result. Full RL policy iteration is conditional on this
pilot; one-step regression is not labelled full RL.
