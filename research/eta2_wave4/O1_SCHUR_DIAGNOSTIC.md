# O1 numerical follow-up, registered during the unchanged v1 cohort

Trigger: Final3068's opening fails PCG's 1024-iteration / 1e-8 residual gate
before a single QP step is accepted (first recorded relative residual 0.08136).
The v1 k=3/5/10 scores and binary remain frozen. Their fallback outcomes do not
establish O1 basin selection. A numerical follow-up is warranted before calling
this a failure of the object-space formulation.

One isolated change: precondition the O1 translation Schur solve with its true
3x3 camera diagonal S_ii=U_i-sum_j W_ij V_j^+ W_ij^T, instead of U_i. The QP,
ray/weight/rotation rules, signed constraints, gauge and every solver tolerance
and limit are unchanged. No damping or regularizer is added to the operator;
the same checked block pseudoinverse is used only in the preconditioner.
When active constraints add PSD terms, this base preconditioner stays fixed;
their exact correction remains in the operator. Duplicate camera/point edges
would require aggregating W first; detect and disallow them for this prototype.

First repeat the tiny independent QP, rotation and intrinsics tests with this
variant, plus one unscored initial-state Final3068 and Venice diagnostic using
k=3 and one following Eta2 outer. All opening cost is still timed/logged, but
these N=1 diagnostics are not performance or tail-rate evidence.

If Final3068 still has no valid accepted QP opening, stop: report a numerical
limit, without refuting the exact convex problem. If the first QP becomes valid
and is accepted on the original L2 objective, preregister a fresh off/k=3 N=5
tail cohort on this binary. k=3 is fixed now as the least expensive requested
opening; no retuning of k after the diagnostic. The practical panel requires
observed Final3068 hit improvement with no opposite-tail loss.
