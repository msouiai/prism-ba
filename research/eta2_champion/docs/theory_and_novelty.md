# Eta2: theory, implementation, and contribution boundary

Assessment: 2026-09-12. This note describes the **frozen Eta2 research champion**, not every algorithm in the Prism repository. The configuration is [champion.json](../champion.json), the implementation is [prism_eta2.cu](../source/prism_eta2.cu), and the build inputs are pinned by [source_manifest.json](../source_manifest.json). Literature coverage is focused, not an exhaustive priority search.

**The algorithm is radius-controlled, inexact Levenberg–Marquardt (LM), with matrix-free Schur elimination, camera-block PCG, nonlinear step safeguards, and persistent numerical damping recovery.** Its central design choice is to spend relatively little work solving each local quadratic model, then check and repair the proposed nonlinear step. The strongest current contribution is the measured solver design and numerical diagnosis. A new general optimization theorem, or an independently novel curvature-sizing rule with a demonstrated speed advantage, has not been established.

The champion uses **one damping candidate**. It does not use the multi-shift menu, a learned RL policy, periodic retriangulation, cross-iteration Krylov reuse, or the subsequent depth/pair-restoration probes. `OCA_CAMERA_TR=0` disables an older TR implementation; `OCA_ATTR_RADIUS=1` enables the radius controller described here.

## 1. The objective and local model

For cameras \(c\), landmarks \(p\), and the fixed observation set \(\mathcal O\), the measured objective is

\[
F(c,p)=\tfrac12\sum_{(i,j)\in\mathcal O}\|r_{ij}(c_i,p_j)\|^2.
\]

Experiments use the same original pixel observations and SIMPLE_RADIAL projection, with unshared camera intrinsics and \(k_2=0\). Camera updates use the implementation's rotation retraction; landmarks use additive updates. No robust-loss or observation-selection change is hidden in the objective.

Write \(J=[J_c\ J_p]\), \(g_c=J_c^Tr\), and \(g_p=J_p^Tr\). Define

\[
U=J_c^TJ_c+Q_{\rm intr},\qquad V=J_p^TJ_p,\qquad W=J_c^TJ_p.
\]

Here \(Q_{\rm intr}\) is the implementation's nonnegative intrinsic diagonal regularizer. It regularizes the **linear solve**, and is not an extra term in the scored reprojection objective. Camera and point normal blocks are block diagonal before elimination, because an observation connects one camera and one landmark.

The ideal coupled LM equations are

\[
\begin{bmatrix}
U+\lambda D_c&W\\
W^T&V+\lambda D_p
\end{bmatrix}
\begin{bmatrix}d_c\\d_p\end{bmatrix}
=-\begin{bmatrix}g_c\\g_p\end{bmatrix}.
\]

The champion couples point damping to camera damping: \(\tau=\lambda\). On positive active coordinates, \(D_c=\operatorname{diag}(U)\). Each point's diagonal uses the normal diagonal with a floor of \(10^{-3}\) times its block mean; code also handles zero and tiny blocks. This protects poorly constrained point directions. Coupled diagonal damping itself is standard LM, not an invention of this solver.

These equations describe the ideal arithmetic. Stored camera blocks, cross blocks, and point factors do not necessarily form one exactly consistent Gram matrix after mixed-precision rounding; that distinction matters in section 5.

### Trust-region formulation and exact classification

The classical scaled Gauss--Newton trust-region problem at state \(x_k\) is

\[
\min_d\;g_k^Td+\tfrac12 d^TJ_k^TJ_kd
\quad\text{subject to}\quad
\|D_k^{1/2}d\|\le\Delta_k.
\]

For an exact solution, a multiplier \(\mu\ge0\) satisfies

\[
(J_k^TJ_k+\mu D_k)d=-g_k,
\qquad
\mu\bigl(\|D_k^{1/2}d\|-\Delta_k\bigr)=0.
\]

In that reference problem, damping is the dual multiplier selected so that the solution itself obeys the radius. Eta2 instead approximately solves its damped reduced system,

\[
\|b_\lambda-A_\lambda z_\lambda\|\le\eta_k\|b_\lambda\|,
\]

then applies a camera-space projection

\[
\widehat z=z_\lambda\min(1,R_k/\|z_\lambda\|),
\qquad \widehat d_c=E\widehat z,
\]

recomputes the point step from \(\widehat d_c\), and may further modify the point proposal through its safeguarded candidate policy. The radius therefore bounds scaled camera motion rather than a single norm of the joint camera--point step. The persistent \(\lambda\) is controller state and is not chosen to satisfy the classical complementarity equation above.

Eta2 is consequently a **radius-controlled inexact LM method with trust-region acceptance**. Calling it “trust-region-flavoured LM” is also accurate. Calling it an exact classical trust-region solver is not: it does not solve the constrained joint quadratic, Moré--Sorensen system, or Steihaug--Toint subproblem. The gain ratio is evaluated on the actual modified candidate, which supplies the trust-region globalisation described in section 3.

## 2. Eliminate points and solve cameras only as accurately as needed

Let \(V_\lambda=V+\lambda D_p\) and \(E=D_c^{-1/2}\), with the implementation's fallback on zero coordinates. Substitution gives

\[
A_\lambda z=b_\lambda,\qquad
A_\lambda=E(U-WV_\lambda^{-1}W^T)E+\lambda I,
\]

\[
b_\lambda=-E(g_c-WV_\lambda^{-1}g_p),\quad
d_c=Ez,\quad d_p=-V_\lambda^{-1}(g_p+W^Td_c).
\]

Products with \(A_\lambda\) traverse observations and apply small point solves; the full reduced camera matrix is not materialized. The preconditioner is freshly factored **camera-block Jacobi**,

\[
M_i=E_iU_iE_i+\lambda I.
\]

It is not the block diagonal of the complete Schur complement. The code factors 9-by-9 camera blocks, including the masked intrinsic coordinate, with numerical safeguards. See [pcg_camera.cuh](../source/headers/pcg_camera.cuh).

Implicit Schur products, block preconditioning, and inexact linear solves are established BA techniques; [Agarwal et al., *Bundle Adjustment in the Large*](https://www.microsoft.com/en-us/research/wp-content/uploads/2010/10/Agarwal-ECCV10.pdf) is a direct predecessor.

### What “Eta2” means

Let \(n_k=\|b_k\|\). The baseline forcing value is

\[
\bar\eta_k=\min\left(0.5,\;0.9(n_k/n_{\rm prev})^2\right),
\qquad
\eta_k=\operatorname{clip}_{[10^{-12},\,0.5]}(2\bar\eta_k).
\]

The first attempt uses 0.5. PCG tests the residual against \(\eta_k\|b_k\|\), subject to its iteration cap and numerical checks. On reported residual convergence, it recomputes the true residual and requires agreement within the implemented 1.01 tolerance factor.

**Eta2 multiplies an adaptive tolerance by two, capped at 0.5. It does not set the tolerance to 2.** The previous norm is from a previous solve attempt, whose damping and scaling may differ. This is an [Eisenstat–Walker-inspired forcing schedule](https://users.wpi.edu/~walker/Papers/forcing_terms,SISC_17,1996,16-32.pdf), not a direct application of that paper's convergence theorem. The fixed multiplier is implemented in [rl_actor.h](../source/headers/rl_actor.h), but no learned actor is enabled.

The rationale is economical: an inaccurate nonlinear model rarely warrants an expensive, highly accurate linear solution. Whether the resulting direction is useful must still be checked against the nonlinear objective.

## 3. Radius control and honest prediction of the modified step

The scaled camera direction is clipped before point back-substitution:

\[
z\leftarrow z\min(1,R/\|z\|).
\]

The first radius is initialized from the first finite, nonzero raw camera norm, with a fallback of 1. Points are then recovered using the clipped camera step. This is **not** uniform scaling of the full camera-plus-point direction, and radial clipping of a PCG result is not an exact trust-region subproblem solution.

For the actual proposed full step \(d\), including any subsequent safeguard, the solver evaluates

\[
\operatorname{pred}(d)=-g^Td-\tfrac12\|Jd\|^2,
\qquad
\rho=\frac{F(x)-F(\operatorname{Retract}(x,d))}{\operatorname{pred}(d)}.
\]

The directional Jacobian is evaluated directly at the current state in [full_step_model.cuh](../source/headers/full_step_model.cuh). This avoids identities that assume the original damped linear equations were solved exactly, or that still describe an unmodified step. Damping and intrinsic solve regularizers are excluded from this prediction of the original objective.

Acceptance requires a finite improving candidate, positive prediction, \(\rho>0.1\), and a camera norm within the radius. The radius shrinks by four when \(\rho<0.25\), and doubles when \(\rho>0.75\) and the step uses at least 80% of the radius. A rejection forces shrinkage if the ordinary rule would not shrink. The main damping update is

\[
\lambda_{\rm next}=\lambda(R/R_{\rm next})^2.
\]

An accepted interior step with \(\rho\ge0.25\) can additionally reduce damping to \(0.1\lambda\); bounds and the numerical floor also apply. Thus \(\lambda R^2\) is preserved by the main update only, not by every transition. This is a controller convention, not a derivation of an exact trust-region dual multiplier.

Trust ratios and scaled LM/TR methods are established: see [Ceres' nonlinear least-squares documentation](https://ceres-solver.readthedocs.io/latest/nnls_solving.html) and, specifically for combinations of damping, inexact solves, and explicit scaled trust regions in BA, [Qu's 2018 master's thesis](https://cvai.cit.tum.de/_media/members/demmeln/qu2018msc.pdf), chapter 3.3. We do not claim this entire algorithmic family as new.

## 4. Nonlinear rescue exploits BA's point separability

After sufficient accepted progress, an eligible failed descent proposal can be backtracked at \(\alpha=1/2,1/4,\ldots,1/256\). Trials reuse the computed full direction, and require true-cost descent and an Armijo bound with coefficient \(10^{-4}\). They do not each require another Schur solve.

The same rescue branch also tests a different candidate. Hold the failed proposal's camera state \(c^+\) fixed. For each landmark, compare its **whole-track nonlinear cost** at its old and proposed positions, and select the cheaper one:

\[
\tilde p_j\in\arg\min_{q\in\{p_j,p_j+d_j\}}F_j(c^+,q).
\]

Because tracks separate at fixed cameras,

\[
F(c^+,\tilde p)=\sum_j\min\{F_j(c^+,p_j),F_j(c^+,p_j+d_j)\}.
\]

**Guarantee:** in exact arithmetic, this finds the best of all \(2^{n_p}\) binary keep/move combinations with linear work in the observations. Its cost is no worse than moving every point or keeping every point **at that same proposed camera state**. It need not improve the original state \((c,p)\), so the solver still applies global descent, Armijo, and full-model ratio checks.

The implementation uses one warp per point, keeps the proposed point on ties, and preserves each complete observation track. See [point_safeguard.cuh](../source/headers/point_safeguard.cuh). This is discrete conditional selection; it does not retriangulate points or optimize their coordinates to convergence.

The identity follows from familiar separability, and continuous point refinement/inner iterations are already used in BA, including [Ceres](https://ceres-solver.readthedocs.io/latest/nnls_solving.html). The candidate contribution is this inexpensive nonlinear rescue policy and its integration with the approximate camera solve. Priority for that exact policy has not been established.

## 5. Numerical Schur curvature and persistent recovery

In the consistent, positively damped ideal system, the Schur complement is positive definite on active coordinates. A negative computed Rayleigh quotient can instead arise from cancellation and inconsistent rounding. [Demmel et al., *Square Root Bundle Adjustment*](https://www.usenko.net/pdf/demmel2021rootba.pdf), section 6.4, already identifies numerical indefiniteness in Schur-based BA; the general pathology is not new.

Eta2 stores compact cross blocks and point rows in FP32 while important accumulation, point factorization, and CG operations use FP64. Guarded point Cholesky and QR fallback improve the point solve, but do not make all stored blocks a coherent full-precision Gram matrix.

For a Krylov search direction \(v\), the curvature check trips when \(v^TA_\lambda v\) is not greater than \(10^{-14}v^Tv\). For a finite quotient \(q=v^TA_\lambda v/(v^Tv)\), the recovery uses

\[
\lambda'=
\operatorname{clip}_{[10^{-14},\,10^{16}]}
\bigl(4\max\{\lambda,\lambda-q\}\bigr).
\]

It retains the new lower damping bound across outer iterations, rebuilds the damped point factors, reduced RHS, and preconditioner, and restarts CG. The unchanged state can reuse assembled blocks. Old Krylov iterates are not reused with the changed operator.

### The precise mathematical guarantee

Freeze the stored blocks and camera scaling, assume \(D_p\succeq0\), and assume \(V_\lambda\succ0\) over the interval. For \(\lambda'\ge\lambda\),

\[
\begin{aligned}
A_{\lambda'}-A_\lambda
&=EW(V_\lambda^{-1}-V_{\lambda'}^{-1})W^TE
+(\lambda'-\lambda)I\\
&\succeq(\lambda'-\lambda)I.
\end{aligned}
\]

Consequently the **same direction** satisfies \(q(\lambda')\ge q(\lambda)+\lambda'-\lambda\). This bound does not require \(U,W,V\) to be a coherent Gram matrix. It explains why sufficiently increasing coupled damping can repair an observed direction. The derivative is

\[
q'(\lambda)=1+\frac{u^TD_pu}{v^Tv}\ge1,
\qquad u=V_\lambda^{-1}W^TEv.
\]

These are standard matrix identities, not new theorems. They do not certify every direction, cover arbitrary factorization error, or guarantee nonlinear convergence. The implemented cap can also limit the repair.

Our specific precision diagnosis is stronger than an observed CG warning. At three captured Venice states, changing only the cross blocks from FP32 to FP64 changed negative Rayleigh quotients, about \(-0.56\) to \(-2.57\) times \(10^{-9}\), into positive values of \(3.43\) to \(4.28\) times \(10^{-8}\). Two ill-conditioned, two-observation tracks dominated the error; point-factor precision alone did not fix it. All 18 delivered states from the other solver had positive audited operators under the registered common damping. These are different trajectories, so both findings can hold. See the [completed precision audit](../../eta2_pair_precision/FINDINGS.md).

To see the amplification mechanism, hold an upper-triangular point factor \(T\) fixed, with \(V_\lambda=T^TT\). Define

\[
a=T^{-T}W_{64}^TEv/\|v\|,\qquad
e=T^{-T}(W_{32}-W_{64})^TEv/\|v\|.
\]

Then the cross-rounding contribution obeys

\[
q_{32}-q_{64}=-2a^Te-\|e\|^2.
\]

An ill-conditioned point solve can amplify small cross-block errors. This diagnosis concerns the **numerical damped Gauss–Newton operator**, not a negative eigenvalue of the true nonlinear Hessian. Eta2 does not add the residual-Hessian term \(\sum_i r_i\nabla^2r_i\).

## 6. Algorithm and stopping policy

The following summarizes the enabled path; exact guards and caps remain in the pinned source.

```text
Initialize state, lambda = 0.1, numerical floor, and controller history.
Until target, budget, or stopping policy ends the run:
    Assemble/reuse blocks for the current state; set point damping = lambda.
    Form point factors, scaled reduced RHS, and camera-block preconditioner.
    Run single-shift PCG with the Eta2 forcing tolerance.
    If a recoverable curvature cutoff occurs:
        increase and retain the damping floor; rebuild and restart.
    Clip the scaled camera direction; back-substitute the point direction.
    Score the true objective.
    If the failed proposal is eligible for rescue:
        try backtracking and the per-track old/full point selection.
    Evaluate the full GN prediction for the actual selected step.
    Apply global acceptance checks; update state only on acceptance.
    Update radius, damping, and progress/stop-confirmation history.
```

The frozen small-decrease rule is \(10^{-5}\) over eight consecutive weak/flat outers, with rejected outers counting as flat. A proposed stop after previous backtracking rescue is confirmed with backtracking disabled. Meaningful ordinary progress can rearm rescue. This is a finite-budget stopping policy, not a stationarity certificate; the observed Final3068 misses demonstrate the distinction.

As a control interpretation, \((\lambda,R)\) and the retained numerical floor are controller state; model agreement, step norm, and directional curvature supply feedback. This interpretation helps explain the interactions but does not establish a Lyapunov or closed-loop stability theorem.

One structural limitation is especially relevant to recent experiments. If the camera step is scaled by \(\alpha\),

\[
d_p(\alpha)=-V_\lambda^{-1}g_p
-\alpha V_\lambda^{-1}W^Td_c^{\rm raw}.
\]

Shrinking cameras does not eliminate the point-only offset. Also, an old radius is expressed in an old scaling metric. Restoring an old scalar \((\lambda,R)\) pair therefore need not reconstruct a useful step at a later state.

## 7. What is established, distinctive, and still unproven?

| Ingredient or claim | Status |
|---|---|
| LM, Schur elimination, PCG, diagonal/block scaling, inexact forcing | Established foundations; not standalone novelty claims. |
| Radius control and actual/predicted reduction | Established family. Eta2's clipping and update policy are a specific heuristic, not an exact TR solver. |
| Per-track old/full nonlinear point selection | Precisely specified inexpensive safeguard with a separability guarantee; exact-policy priority remains unverified. |
| Full-model prediction after clipping or point selection | Correctness-critical integration; evaluating the actual candidate is not itself a new optimization principle. |
| Persistent coupled numerical damping recovery | Mathematically motivated implementation with measured recovery behavior. Incremental superiority of curvature magnitude over a simple retained floor is unproven. |
| Compact storage, diagonal normalization, buffer/work reuse | Systems contributions that reduce work or memory; benefits depend on which operations a configuration actually reuses. |
| The complete frozen solver | Strong measured time-to-quality results against the tested baselines; no universal fastest-BA claim. |
| Multi-shift and learned damping | Disabled in this champion. Its wins cannot be attributed to either. |

In particular, retry-cache benefits cannot be assumed when point damping changes with lambda. An enabled flag does not establish saved work: the frozen classical-LM path even computes a Schur diagonal contribution before clearing it to form its camera-only scaling. Likewise, the Eta2 forcing selection evaluated a combined global initialization/tolerance configuration, not a clean one-factor tolerance ablation on every scene.

The [six-scene selection report](rl_sustained_results.md) measured a 1.1633x geometric-mean improvement over its incumbent. On Final13682 at the registered primary target, native medians were 3.239s for Eta2, 7.084s for Caspar FP32, and 14.973s for Caspar FP64. The incremental improvement over the incumbent shrank substantially at a tighter target. The [153-run frozen comparison](speed_novelty_results.md) found Eta2 fastest among evaluated configurations in all nine scene/tolerance cells, with 27/27 target hits. Numerical recovery was inactive before those practical targets, so those speed wins do not demonstrate a benefit from curvature sizing.

The latest [pair-restoration/precision campaign](../../eta2_pair_precision/FINDINGS.md) did not produce a replacement champion: restoring controller state rescued none of the actual Final3068 stop witnesses; all Venice arms remained 0/10 at the registered target. FP64 cross blocks removed all ten measured de-clipping curvature truncations, but all ten resulting proposals still failed nonlinear acceptance. Linear accuracy and nonlinear usefulness are separate requirements.

## 8. A separate scheduler combination with MFREE

The collaborator's 2026-09-12 report combines frozen solvers: run Eta2; if it misses the registered target, run MFREE-deep afresh from the original input. It is not a modification of either inner algorithm. Algorithm portfolios are an established idea; see [Gomes and Selman, *Algorithm Portfolios*](https://www.cs.cornell.edu/selman/papers/pdf/01.aij.portfolios.pdf).

Reported Final3068 target: **1,744,796.9841897595**. The composition uses the older [8/10 Eta2 ledger batch](../../eta2_external_coverage/SAME_TARGET_LEDGER.md), not the later 6/10 precision-campaign batch.

| Reported cascade quantity | Value |
|---|---:|
| Hits | 9/10 |
| Fallbacks consumed / rescued | 2 / 1 |
| Total wall: median / mean / p90 | 3.84s / 6.59s / 18.1s |
| Fresh MFREE-deep pool | 7/12 |
| Pooled MFREE-deep observations, including previous 5/10 | 12/22 |

**Provenance:** these cascade quantities are collaborator-reported. The new fallback rows and run-to-fallback assignment were not found in the local `collab/results` snapshot when this note was written; only the earlier MFREE CSV was present. Consequently this note does not certify their composition or add them to the machine-readable verified ledger. Reported total times sum work on two separate, similarly configured GPUs; they are not a direct single-host scheduler measurement. The all-run wall median is distinct from a successful-run target-crossing median.

Let \(p_E\) denote Eta2's hit probability. Without assuming independence,

\[
P(\text{cascade hit})=p_E+(1-p_E)
P(\text{MFREE hit}\mid\text{Eta2 miss}).
\]

The sequential work is \(T_E+\mathbf1_{\{\text{Eta2 miss}\}}T_M\). A fresh fallback prevents state reuse; probabilistic independence remains an assumption, not a consequence of a fixed input alone. Nine successes out of ten are observed outcomes, not an established 90% population reliability. This small composition is encouraging evidence for complementary trajectories while preserving the fast path.

## 9. Defensible paper framing

> We present a safeguarded inexact GPU bundle-adjustment implementation that combines camera-radius control, nonlinear per-track point selection, and persistent regularization for numerical Schur failures. Fixed-target experiments characterize its convergence speed and failure modes against the measured baselines. Operator audits isolate cross-block rounding on ill-conditioned tracks as a cause of spurious curvature.

This supports a numerical optimization/systems contribution. Claiming a fundamentally new trust-region method, a proven superior curvature law, multishift-driven speedups, or the world's fastest BA solver would exceed the current evidence. A broader novelty claim needs a matched ingredient ablation showing incremental benefit and comparison with the closest relevant implementations, including stable square-root BA. The present theory note supplies the exact mechanism and its proof boundaries; the linked reports supply the measurements.
