# What the Schur curvature repair can contribute

Assessment date: 2026-09-10. This is a focused primary-source comparison, not an exhaustive novelty or patent search. Experimental conclusions belong in the associated frozen-panel report.

## Closest established ideas

| Prior work | Established contribution relevant here | Consequence for Prism's claim |
|---|---|---|
| [Bundle Adjustment in the Large, Agarwal et al.](https://www.microsoft.com/en-us/research/wp-content/uploads/2010/10/Agarwal-ECCV10.pdf) | Inexact Newton and implicit Schur/CG for large BA | Matrix-free Schur and inexact solves are established foundations. |
| [Square Root Bundle Adjustment, Demmel et al.](https://cvg.cit.tum.de/_media/spezial/bib/demmel2021rootba.pdf) | QR/nullspace landmark marginalization improves numerical stability and enables accurate FP32 BA | Stable low-precision BA is established research. Roundoff-induced Schur indefiniteness and extra damping are explicitly discussed in section 6.4. |
| [Ceres 2.2 CG implementation](https://raw.githubusercontent.com/ceres-solver/ceres-solver/2.2.0/internal/ceres/conjugate_gradients_solver.h) | Detects nonpositive directional curvature and stops CG; also contains quadratic-model stopping and residual replacement | Detecting negative curvature, monitoring the quadratic model and interrupting CG are not novel alone. |
| [Ceres 2.2 LM implementation](https://raw.githubusercontent.com/ceres-solver/ceres-solver/2.2.0/internal/ceres/levenberg_marquardt_strategy.cc) | Uses diagonal damping and adjusts the trust radius after accepted/rejected steps | Increasing regularization after unsuccessful steps is a baseline, not a new algorithmic family. |
| [Caspar](https://arxiv.org/html/2605.30583v1) | Symbolic residuals and differentiation generate optimized CUDA; expression scheduling and memory layout are central contributions | A substantial systems contribution can stand on its own. Caspar's contribution is more than merely running LM on a GPU. |

The Ceres source inspection does not establish how every numerical failure propagates through every solver configuration, nor that its behavior equals our simple-times-four control. The control isolates one choice in Prism, not the entire Ceres algorithm.

## Precise mechanism and its mathematical scope

For frozen stored blocks and fixed camera scaling, write the reduced operator as

\[
A(\lambda)=E\left[B-W(C+\lambda D_p)^{-1}W^T\right]E+\lambda I.
\]

Assume the point blocks are positive definite over the damping interval and the damping matrix is positive semidefinite. For \(\lambda'\geq\lambda\), monotonicity of the inverse gives

\[
A(\lambda')-A(\lambda)\succeq(\lambda'-\lambda)I.
\]

This bound still applies when the frozen stored camera and cross blocks are not a coherent exact Gram matrix. For a failed direction with \(q=p^TA(\lambda)p/(p^Tp)\leq0\), increasing damping sufficiently makes that direction positive in exact arithmetic. Prism uses \(\lambda'=4\max(\lambda,\lambda-q)\), subject to implementation bounds. It rebuilds point factors and the reduced right-hand side, discards the old Krylov basis, and retains a lower damping bound across outer iterations.

This is a directional argument for a frozen operator. It is not an all-directions SPD certificate, a floating-point error bound, or a nonlinear convergence theorem. The inequality follows from standard matrix algebra; the potential contribution is the diagnosed implementation pathology and the effective recovery design.

The times-four baseline already satisfies the same sufficient directional condition when \(q+3\lambda>0\). The point contribution can improve curvature by more than this conservative bound. With \(u=(C+\lambda D_p)^{-1}W^TEp\),

\[
q'(\lambda)=1+\frac{u^TD_pu}{p^Tp}\geq1.
\]

These facts explain why a persistent simple floor can match a curvature-sized repair. They also make an outcome interpretable: if most failures satisfy the simple bound, a speed advantage from curvature magnitude should not be expected. A stronger future experiment could select fixed-state failures by this ratio before comparing repair rules, while retaining a separate untouched evaluation panel.

## Contribution boundary

A defensible candidate contribution is **directional-curvature-driven, persistent coupled damping recovery in a mixed-storage matrix-free GPU BA solver**, supported by evidence of the numerical failure and by time-to-quality ablations. The current frozen champion also includes radius control, point safeguards, compact storage and inexact solves; improvement of the complete solver cannot automatically be attributed to curvature repair.

Prism's repair addresses spurious indefiniteness in the numerical Gauss–Newton/Schur operator. It does not incorporate the missing residual-Hessian term in the nonlinear objective. The learned curvature-feature controller and the residual-quartic prototype are separate experiments and are not enabled in the champion.

The existing Ladybug-1723 ablation found retained-times-four and curvature-sized repair overlapping in timing; it did not show a general incremental advantage for curvature magnitude. See `schur_recovery_results.md`. The new experiment freezes the stronger eta2 champion and tests new instances at multiple practical tolerances. Its result must determine the claim; publication wording must not assume a positive ablation in advance.

Remaining broader speed comparisons include contemporary GPU Ceres configurations and other GPU BA implementations; square-root BA is also a relevant stability baseline. This short panel adds Ceres CPU LM/Dogleg and new instances, but does not establish global fastest-solver status or cross-hardware dominance.
