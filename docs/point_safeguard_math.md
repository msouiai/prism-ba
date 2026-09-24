# Whole-track point safeguard

For cameras C and points X, plain BAL least squares is F(C,X)=sum_p F_p(C,X_p), with F_p summing **all** observations of point p. Fix the failed proposal's camera state C+=Retract(C,d_c). Set b_p in {0,1} and X_p+=X_p+b_p d_p. Then

    min_{b in {0,1}^P} F(C+, X+b*d)
      = sum_p min(F_p(C+,X_p), F_p(C+,X_p+d_p)).

This is exact finite-set optimization despite nonlinear projection. The 2^P combinations need only two track scores per point. The GPU uses one warp per point and existing point-to-observation CSR. It holds no point-cost arrays. Ties retain full steps; unseen points also retain them. Nonfinite track scores are mapped to infinity. If neither alternative is finite, the full objective check rejects the resulting proposal.

With g_c=J_c^T r and g_p=J_p^T r at the current state, the derivative at zero along the selected direction is

    s = g_c^T d_c + sum_p b_p g_p^T d_p.

The finite-menu optimum does not guarantee s<0, nor improvement over current cameras or an original uniformly shortened step. We require finite s<0, finite F_new<F_current, and Armijo F_new <= F_current+1e-4*s. The existing uniform backtrack is evaluated first, and the new candidate replaces it only if its fully evaluated cost is strictly lower. Therefore, at a **fixed input state and selected failed direction**, the combined policy cannot accept a worse objective than the original successful rescue (up to floating-point evaluation). An unaccepted candidate does not alter the retained step. If no points change selection, the known failed full step is not rescored.

This is not a guarantee of faster optimization, fewer future rejections, global convergence, or a better state after a fixed time. The next linearization and damping history change after accepting a different step. In particular, rescued steps retain the existing damping controller behavior. The guarantee is local to one decision, not an ordering between later trajectories.

Compared with a per-observation mask, a whole-track choice remains a valid single 3D point shared by every observing camera. Compared with changing Schur point damping, the selection is a nonlinear post-solve safeguard: no claim is made that it solves a newly regularized normal equation or preserves Krylov recurrence identities. General block-coordinate finite-menu separability is established mathematics; potential novelty would be its useful integration with multi-shift BA and demonstrated runtime benefit, which needs evidence.

Scope: opt-in OCA_POINT_SAFEGUARD=1, FP64 CD9 unshared plain L2, original backtracking, no other experimental rescue/point-feedback/full-rho/replay. Fixed single, fixed multi and paired demand are supported. All ordinary defaults remain unchanged. Persistent extra allocation is one 8-byte counter; temporary work reuses existing buffers, with a second retraction and full cost evaluation only when a changed selection has negative slope.

## Related method and scope of a novelty claim

Ceres describes independent-set nonlinear inner iterations, motivated by Ruhe and Wedin's Algorithm II, which refine disjoint parameter blocks after a full trust-region step. Its documentation explicitly notes extra per-iteration work and that contributions may diminish. This supports testing time to quality rather than just immediate decrease. Our two-choice failed-step rescue is narrower than a nonlinear point minimization and does not inherit an algorithm-level convergence theorem from those methods. Independent point refinement itself is therefore not a sufficient novelty claim. Source: [Ceres inner iterations](https://ceres-solver.readthedocs.io/latest/nnls_solving.html#inner-iterations), accessed 2026-09-08.

## Baseline-camera refinement (mode 2)

When the original rescue succeeds at uniform scale alpha, fix cameras at Retract(C,alpha*d_c) and select each point from {X_p+alpha*d_p, X_p+d_p}. This finite menu contains the complete original rescued state. Thus its exact minimum has cost at most F_original_rescue, before any Armijo or slope check. The mixed derivative becomes alpha*g_c^T*d_c + sum_p b_p*g_p^T*d_p for b_p in {alpha,1}. We retain the explicit cost comparison and Armijo check to handle floating-point effects and changed slopes. If the original rescue fails, mode 2 skips its proposal. Unlike mode 1, it may need a cost evaluation even if every point chooses full, since the camera scale changed from the failed full step.

The conditional-set inclusion guarantee is stronger than mode 1's guarantee relative only to the full-camera state. It still does not compare subsequent trajectories, and can still be slower after changing the next linearization. No claim is made that every point is individually minimized over continuous 3D coordinates.
