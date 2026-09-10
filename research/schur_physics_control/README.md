# Schur solvers, physical relaxation, and feedback control for Prism BA

Research checked through **10 September 2026**. Recommendation: first investigate a small global correction to the existing camera-block preconditioner. In parallel, use an energy/stationarity diagnostic to identify damping-induced stalls. An exact projected family of coupled damping systems is a higher-risk route back to a useful menu.

The frozen eta2 configuration remains the incumbent. **Implementation follow-up completed:** [results, target timings and curvature diagnostics](RESULTS.md), [reproduction commands](RUNNING.md). The original review below supplied the hypotheses; the new experiments did not produce a replacement for eta2. The original implementation and configuration are unchanged. Claims of novelty remain open; most of the underlying mathematical tools already have substantial prior art.

**Largest-scene extension:** [Final13682 results](LARGEST_RESULTS.md). All 12
fixed-target runs hit, with eta2/rank16 tied and no coarse activation. A
separate capped curvature probe does not show the extreme Final3068 pattern
at its sampled endpoint.

**Initialization-noise extension:** [protocol](NOISE_PROTOCOL.md),
[results and noisy convergence curves](NOISE_RESULTS.md). This separate cohort
perturbs camera poses and points while preserving all observations and initial
intrinsics; it does not replace the clean-scene target ledger above.

## What the measurements actually motivate

The latest [Schur preconditioner experiment](https://github.com/msouiai/prism-ba/blob/07d9179/research/schur_preconditioner/RESULTS.md) is the starting point:

| Comparison | Observation | Consequence |
|---|---|---|
| Fixed Muell system, native forcing | Hcc: 41 CG iterations, 131.195 ms; Gram Schur diagonal: 3 iterations, 24.350 ms, including construction | Some captured systems benefit greatly from stronger preconditioning. |
| Full Muell target, always-on Gram diagonal | 20.1% slower than Hcc | A faster captured solve need not produce faster nonlinear convergence. |
| Full Final1936 target, always-on Gram diagonal | 31.8% slower | Setup is especially costly for shallow solves. |
| Conditional Gram diagonal, after eight unfinished iterations | Muell 3.60% slower; Final1936 0.47% slower | Delayed activation alone did not produce a replacement. |

The [Muell profile discussed in the attribution handoff](https://github.com/msouiai/prism-ba/blob/8c56130/docs/agent-mail/0006-codex-to-claude.md) assigned 53.8% of kernel time to the two Schur passes. [Claude's Config S opening, measured separately](https://github.com/msouiai/prism-ba/blob/8c56130/docs/agent-mail/0002-codex-to-claude.md), assigned 71.1% to those passes. These are configuration/trajectory-specific percentages, not universal constants. At a 53.8% fraction, halving that work gives about 1.37x speedup of measured kernel time if everything else stays fixed; this is not a prediction for total wall time. Any new setup must be charged.

The working hypothesis is that weak **collective camera motions** can survive a local block preconditioner. It is not yet established that these modes dominate our target prefixes. We need a spectral/residual diagnostic before building a full multigrid implementation.

## Recent literature and applicable older foundations

| Work and date | What is relevant | Transfer to this implementation |
|---|---|---|
| Liu et al., [algebraic multilevel Schur complement preconditioning with eigenvalue deflation](https://onlinelibrary.wiley.com/doi/10.1002/nla.70018), April 2025 | Hierarchical interface decomposition, low-rank corrections, generalized eigenproblems and GPU acceleration for sparse symmetric systems. | A useful modern implementation direction. Only the publisher's abstract/reference list was accessible here; no BA performance or detailed theorem is inferred. |
| Frangella, Tropp and Udell, [Randomized Nyström Preconditioning](https://tropp.caltech.edu/papers/FTU23-Randomized-Nystrom-SIMAX.pdf), SIAM, 2023 | Low-rank preconditioning with effective-dimension guarantees for a regularized PSD matrix. | Useful algebra, but sketching the largest eigenvalues of the Schur matrix can miss its troublesome small eigenvalues. Construction costs matter. |
| Konolige and Brown, [Multigrid for Bundle Adjustment](https://arxiv.org/html/2007.01941v1), 2020 | BA-specific aggregation, near-nullspace modes and coarse corrections. The paper discusses expensive Galerkin setup and fill-in. | Closest foundation for the proposed global correction. Its results emphasize large synthetic street-view-like systems; they are not an expected speedup on our BAL suite. |
| Das, Katyan and Kumar, [A Deflation Based Fast and Robust Preconditioner for Bundle Adjustment](https://openaccess.thecvf.com/content/WACV2021/papers/Das_A_Deflation_Based_Fast_and_Robust_Preconditioner_for_Bundle_Adjustment_WACV_2021_paper.pdf), WACV 2021 | Direct prior art for deflation in BA. | A novelty constraint. Bibliographic identity verified against the [author's publication list](https://sites.google.com/iitgn.ac.in/shrutimoy/publications); detailed paper analysis remains to be completed. |
| Weber et al., [Power Bundle Adjustment](https://arxiv.org/abs/2204.12834), CVPR 2023 | An inverse Schur power-series solver. | A polynomial method is a useful control, but adding several observation passes per preconditioner application may lose on our GPU. |
| Kaneda et al., [CSS-BA](https://arxiv.org/html/2607.15652v1), July 2026 preprint, listed as accepted at ECCV 2026 | Geometry-gated camera support and a Ritz subspace for the update. | Relevant weak-geometry diagnostics. Its two reported timing cases cost approximately 2.0x normal LM and 6.8x PoBA under an equal iteration cap. It is not a convergence-speed prescription for Prism. |
| Demmel et al., [Square Root Bundle Adjustment](https://arxiv.org/html/2103.01843v1), CVPR 2021 | QR landmark marginalization, algebraically equivalent to Schur elimination, with improved numerical stability. | Relevant if cancellation limits lower precision. Their implementation still uses CG on reduced normal equations; QR does not remove all conditioning issues. Dense landmark storage ran out of memory on Final13682 in their experiment. |
| Aldana-López et al., [port-Hamiltonian distributed optimization](https://arxiv.org/html/2404.13529v1), April 2024 | Energy-based dynamics and mixed implicit discretization. | Their optimization assumptions include strong convexity and Lipschitz gradients. General nonconvex BA does not inherit unconditional convergence from this paper. Implicit local updates also have a computational cost. |
| Roulet et al., [convergence of ILQR/DDP](https://www.jmlr.org/papers/v26/22-1271.html), JMLR 2025 | Analyzes control algorithms through regularized generalized Gauss–Newton methods. | Helpful for understanding the connection, but arbitrary BAL visibility lacks the short temporal chain that makes Riccati recursion attractive. |
| Fan et al., [DABA](https://journals.sagepub.com/doi/abs/10.1177/02783649241309968), IJRR 2025; [earlier RSS formulation](https://roboticsproceedings.org/rss19/p111.pdf), 2023 | Distributed majorization-minimization with acceleration and adaptive restart. | A concrete alternative engine, especially across devices. Any objective reformulation and device-count differences require auditing before a same-objective, same-GPU comparison. |

The general lesson is a combination of inexpensive local work and a mechanism for long-range coupling. There is no verified universal replacement for Schur-PCG in these sources. Methods called “Schur preconditioners” for indefinite PDE saddle-point systems also need their matrix assumptions checked before transplanting them into SPD BA.

## 1. A global correction that preserves the champion's equations

For a frozen linearization, write the damped equations as

\[
\begin{bmatrix}B_\lambda&W\\W^T&C_\tau\end{bmatrix}
\begin{bmatrix}d_c\\d_p\end{bmatrix}
=\begin{bmatrix}b_c\\b_p\end{bmatrix},\qquad
B_\lambda=B+\lambda D_c,\quad C_\tau=C+\tau D_p.
\]

Then

\[
S=B_\lambda-WC_\tau^{-1}W^T,\qquad
b=b_c-WC_\tau^{-1}b_p.
\]

The existing Hcc preconditioner approximates this using independent camera blocks. A basis Z of collective camera motions offers a separate coarse correction. For full-rank Z and SPD S, set

\[
K=Z^TSZ,\quad Q=ZK^{-1}Z^T,
\]

\[
P^{-1}=Q+(I-QS)M^{-1}(I-SQ),
\]

where M is the incumbent SPD preconditioner. This is a standard balanced two-level construction, not a new theorem. It is symmetric positive definite and satisfies

\[
P^{-1}SZ=Z.
\]

Thus directions represented in Z receive an exact coarse correction, while the remaining error still benefits from Hcc. It does not restrict the final update to Z or change the damped BA objective. Hold it fixed within each ordinary PCG solve. A change during the solve requires a mathematically valid restart or flexible method.

**Implementation opportunity:** store Z and SZ when building K. Applying the balanced formula then needs small dense solves and camera-vector operations, without an additional Schur application each time. Constructing SZ is still real work. A dense rank-16 pair Z/SZ at 13,682 cameras and nine variables per camera occupies about 30.1 MiB in FP64; a large rank or hierarchy can increase this rapidly.

Candidate bases, in order of diagnostic value:

1. A few approximate slow modes from an already deep PCG solve, with explicit costs for retaining vectors and forming the small eigenproblem. Test them first on the identical system. Refresh SZ before reuse on another system.
2. Piecewise coherent motions on covisibility aggregates, expressed in the correct camera coordinates and damping scale. Start with a small coarse space; graph construction and aggregation are charged.
3. A hierarchy only if the first two expose enough uncorrected long-range error to justify it.

The seven similarity-gauge modes alone are insufficient: an exact objective gradient has no component along a pure gauge. Useful bases must also describe weak *relative* motions between groups. Intrinsic parameters and near-degenerate geometry complicate the spectrum further. Gauge treatment must be consistent across every arm.

This differs from the [earlier retained-menu experiment](https://github.com/msouiai/prism-ba/blob/f8e1b04/docs/retained_krylov_results.md): that prototype changed checkpoint selection and solved within a retained projected space, with substantial Dubrovnik regression. Here the coarse space preconditions the existing full solve. It still needs a fresh nonlinear target gate because inexact PCG trajectories can change.

The break-even condition is approximately

\[
T_{\rm setup}+k_1(T_{\rm mv}+T_{\rm new\,apply})
<k_0(T_{\rm mv}+T_{\rm old\,apply}).
\]

Amortization across outer iterations is allowed only with all refresh costs charged. Shallow one-to-four-step systems have little room to pay for this.

**A low-rank alternative, with an important sign.** Factor Bλ=LLᵀ and define

\[
G=L^{-1}WC_\tau^{-1}W^TL^{-T},\qquad S=L(I-G)L^T.
\]

In exact arithmetic for an SPD damped joint system, G is PSD and its eigenvalues are below one. The small eigenvalues of the normalized Schur system correspond to eigenvalues of G near one. This is the part to approximate. A PSD Nyström under-approximation obeying 0≤Ĝ≤G gives I−Ĝ≻0. If Ĝ=UΘUᵀ, its inverse is

\[
(I-\widehat G)^{-1}=I+U\,\mathrm{diag}\left(\frac{\theta_i}{1-\theta_i}\right)U^T.
\]

This BA application is our proposed adaptation, not an application of the published effective-dimension theorem without modification. PSD preservation does not guarantee useful conditioning: a sketch can miss a weak mode. Near-unit eigenvalues magnify numerical error. Ordinary FP32 rounding need not preserve the matrix inequalities. Compare rank/setup cost against the geometric/coarse approach first.

The same normalization explains power-series behavior: `(I-G)^-1 = I+G+G²+...`. Modes with eigenvalues near one require many terms. A cheap polynomial plus a few coarse modes could be useful, but every polynomial term streams observations. It should follow, rather than precede, the simpler Hcc-plus-coarse test.

## 2. The physical interpretation is exact locally

Use the unchanged pixel residual objective

\[
F(x)=\tfrac12\sum_o\|r_o(x)\|^2.
\]

| BA quantity | Physical interpretation | Limitation |
|---|---|---|
| Pixel residual energy | Potential energy of nonlinear measurement constraints | These are not ordinary distance springs between camera centers and points. |
| −Jᵀr | Generalized restoring force | Coordinate scaling matters. |
| JᵀJ | Gauss–Newton tangent stiffness | Exact stiffness also includes Σ rᵢ∇²rᵢ and may be indefinite. |
| Schur elimination | Static condensation: equilibrate internal point increments, then solve for camera increments | Equilibrates the tangent quadratic, not the original nonlinear point problem. |
| Preconditioner | A metric that changes relaxation rates of different modes | Building or applying it can cost more than the saved iterations. |

In a fixed local coordinate chart, consider overdamped motion

\[
M\dot x=-\nabla F(x).
\]

One linearly implicit Euler step using GN tangent stiffness solves

\[
(J^TJ+M/h)d=-g.
\]

This is LM with λ=1/h and damping metric M. Increasing lambda reduces the numerical time step. Coupled point and camera damping fits this interpretation; different relative block damping corresponds to different relaxation metrics. A trust-region/damping controller already acts like an adaptive time-step controller.

For a more literal mechanical system, use momentum p and fixed SPD mass M:

\[
\mathcal H(x,p)=F(x)+\tfrac12p^TM^{-1}p,
\quad\dot x=M^{-1}p,
\quad\dot p=-g-RM^{-1}p.
\]

With R PSD, its continuous-time energy satisfies

\[
\dot{\mathcal H}=-(M^{-1}p)^TR(M^{-1}p)\le0.
\]

This suggests momentum, dissipation and modal damping, but does not establish a fast discrete BA algorithm. Variable metrics/manifold coordinates require corresponding geometric terms; arbitrary numerical integration does not preserve the displayed identity. Implicit energy-stable steps can demand expensive solves. A mode with stiffness k and mass m has critical damping `2 sqrt(m k)` in the elementary scalar model; applying one damping coefficient to a broad spectrum explains why a physical reformulation still needs good preconditioning.

**Consequently the strongest connection between the two directions is multilevel relaxation:** remove local errors cheaply, then move groups of cameras collectively to correct slow global errors. Renaming LM as dynamics is not novelty; a demonstrably cheaper realization of those collective corrections could be valuable.

## 3. A control experiment tied to an observed pathology

Recent [v2 repeated runs](https://github.com/msouiai/prism-ba/blob/8c56130/docs/agent-mail/0007-codex-to-claude.md) expose a useful diagnostic target: on Final3068, eight of ten runs terminated on relative objective change, and endpoints spanned approximately 20.57% of the median cost. Logs showed damping escalations before small accepted changes. This concerns Claude's reproduced configuration, not proof that the eta2 champion has the same failure. It motivates checking the gradient before classifying the endpoint as a settled basin.

Even the scalar problem `F(x)=0.5*(x-1)^2`, starting at zero, gives a step near 10^-12 under λ=10^12. Relative objective decrease is about 2e-12 while gradient magnitude is one. Small movement can mean excessive damping rather than stationarity. In control terminology this resembles an actuator-limited stall; calling it literal integral windup would require an integral controller.

The proposed experiment should initially **log**, rather than change, these quantities:

- Undamped, scale-normalized full gradient; camera and point contributions separately. Do not use only the lambda-dependent reduced RHS as the stationarity diagnostic.
- Actual/predicted decrease for the final guarded joint step, current lambda/tau, failed attempts and time spent in linear algebra.
- True linear residual and progress at existing checkpoints.
- Residual-model defect, accumulated per track on selected diagnostic iterations, to separate nonlinear error from weak linear convergence.

A fixed geometric normalization or regularized undamped curvature scale is needed for a meaningful gradient comparison; thresholds calibrated from the damped matrix can shrink automatically as lambda grows. Gauge normalization is also required. These are diagnostics of first-order stationarity, not global optimality certificates.

The controller then has distinguishable responses:

| Evidence | Candidate response |
|---|---|
| Good model agreement, deep inner solve | Improve the preconditioner or stop the inner solve earlier if model improvement is already adequate. |
| Poor nonlinear agreement, reasonably solved linear model | Contract or correct the trial path; spending more CG on the same inaccurate model is unlikely to help. |
| Tiny accepted changes, escalating damping, substantial undamped gradient | Label a damping stall; test a bounded recovery against the incumbent rather than declare convergence. |
| Short, effective target prefix | Keep the incumbent path; new spectral setup has little value. |

The residual-energy identity provides a principled scale. For SPD A, quadratic `q(d)=0.5*dᵀAd-bᵀd`, and error e=Ad−b,

\[
q(d)-q(d_*)=\tfrac12 e^TA^{-1}e.
\]

A genuine lower eigenvalue bound m gives an upper bound `||e||²/(2m)`. The smallest observed Ritz value is generally **not** a valid lower bound on the full matrix. In consistently scaled exact GN systems, positive damping supplies a conservative bound; approximate stored operators need their own numerical checks. Clipping the step changes the relevant model calculation.

This error budget and control of forcing accuracy were already proposed in [our earlier RL/control report](https://github.com/msouiai/prism-ba/blob/f8e1b04/docs/rl_reward_control_research.md). The present contribution is a concrete audit target and its connection to stiffness/preconditioner selection. It is not a claim to have invented a new controller or rescued the previously unsuccessful learned policies.

The model-improvement route also remains grounded in [our existing residual-defect derivation](https://github.com/msouiai/prism-ba/blob/f8e1b04/docs/tr_model_research.md): for v=Jd and e=r(x⊕d)−r−v,

\[
\mathrm{pred}-\mathrm{ared}=(r+v)^Te+\tfrac12e^Te.
\]

A faithful directional residual model addresses omitted nonlinear curvature. A more accurate solution of the same GN quadratic does not. Generic geodesic acceleration and periodic point repair are already studied locally and in the literature; do not repeat them without a mechanism/cost distinction.

## 4. A mathematically valid route back to a coupled damping menu

The champion couples point damping to lambda. Consequently S(λ) and b(λ) above both vary. Ordinary common-RHS shifted CG on `A+λI` does not apply to that Schur family. Ordinary camera-block PCG also does not automatically preserve scalar-shift invariance.

There is nevertheless a useful rational structure. Freeze geometry and positive point metric Dp. For each point p,

\[
D_p^{-1/2}C_pD_p^{-1/2}=V_p\operatorname{diag}(\sigma_{pj})V_p^T.
\]

Then

\[
(C_p+\tau D_p)^{-1}=F_p\operatorname{diag}((\sigma_{pj}+\tau)^{-1})F_p^T,
\quad F_p=D_p^{-1/2}V_p.
\]

For a fixed camera basis Z, store `A_p=F_pᵀW_pᵀZ` and `v_p=F_pᵀb_p`. The **exact projected** system for each proposed lambda is

\[
T_\lambda=Z^TBZ+\lambda Z^TD_cZ
-\sum_p A_p^T\operatorname{diag}((\sigma_{pj}+\tau(\lambda))^{-1})A_p,
\]

\[
h_\lambda=Z^Tb_c
-\sum_p A_p^T\operatorname{diag}((\sigma_{pj}+\tau(\lambda))^{-1})v_p.
\]

This handles a coupled or piecewise tau(lambda) policy with the frozen metric and factors; it does not pretend that point damping is constant. Solve the small system, lift `d_c=Z y`, back-substitute points, and check the actual full residual and objective. Accepted geometry changes invalidate the numerical factors. Refresh all relevant quantities if metrics change.

“Exact projected” is not “exact full solution.” A basis good for one lambda may be bad for another. This is a projected parameter-dependent solve, not free multishift CG. Its local eigendecompositions, Z construction, projected accumulation, candidate reconstruction, residual checks and fallbacks all count.

The memory risk is substantial: A_p requires `3*r*Npoints` scalars, before other workspace; this is about 366 MiB per million points at rank 16 in FP64. Forming projected matrices also costs order `Npoints*r²` per candidate in a simple implementation. Streaming avoids stored A_p but increases computation. A small menu can still cost much more than one full well-preconditioned solve. Test this on captured deep systems only after the simpler coarse preconditioner gate.

An unreduced, consistently scaled joint system can recover a literal identity-shift family when all damping is λD with fixed D. That is a legitimate alternative, but enlarges Krylov vectors to include every point and changes the preconditioning opportunity. Different tau floors/annealing do not generally fit that single shift. This was already recognized in earlier local research; it is not a new shifted-CG discovery.

## Other ways to solve the physical/inference problem

Gaussian belief propagation is a real alternative: [Ortiz et al., CVPR 2020](https://arxiv.org/html/2003.03134v1) mapped BA to local factor messages on an IPU. Their reported advantage used different hardware from the Ceres baseline; loopy GBP has no general convergence guarantee. Per-observation block messages and scheduling would need a new GPU memory/cost analysis for our large scenes. It is more attractive as a separate incremental-mapping experiment than as the first replacement for the frozen champion.

Riccati smoothing/control methods exploit temporal separators. They can be valuable on sequence BA with bounded track spans, but photo-tourism scenes contain long-range observations. Turning those graphs into a chain either creates large separator states or changes the problem. Adding a motion prior or switching to bearing/angular residuals must be reported as an objective change, not a faster solution of the registered pixel-L2 BA problem.

Likewise, nonlinear point equilibration is physically sensible but not automatically cheap: Schur already performs its linearized version, and our periodic point-refinement experiments had mixed/negative results. A residual-defect-triggered local correction is a more specific hypothesis than unconditional periodic retriangulation.

## Minimal experiment sequence

1. **Captured-system audit:** use existing Muell outer12, Final1936 outer0 and Ladybug598 outer8 captures. Record slow-mode/residual overlap, true residual and setup-plus-solve time. Do not change the operator, forcing tolerance, RHS or precision between arms. Start with rank 8 and 16 coarse corrections and Hcc control. Count the work used to obtain an apparently favorable basis.
2. **Short nonlinear gate:** only if the first gate supports a plausible total-work benefit, run incumbent versus the best frozen candidate on Muell and Final1936, N=3, alternating order, with existing registered targets. Include all setup, refreshes and recovery in native time and record process time separately. Use Ladybug598 for transfer. The basis/rank policy must be frozen before this gate.
3. **Noise/stall gate:** N≥10 only on a finalist or a scene whose mode variation affects the decision. Audit Final3068's undamped gradient around termination before modifying stop/recovery. Reproduce the original stop and optional-window control; disabling a stop condition alone is not an algorithmic speed win.
4. **Coupled menu:** use the exact projected rational formulation only if saved operator work can pay for it; compare to both single Hcc and the coarse-preconditioned single arm at identical targets. Keep Claude's separately owned menu/PCG attribution experiment distinct.

For all performance gates, report time to the **same objective target**, hit rate, all timeout/cap/stall counts and per-run outcomes. Freeze a practical tolerance such as 1% above an independently established reference if that is the chosen quality definition. Do not pick a different target for each arm. A consistent approximately 10% gain is a useful promotion bar; isolated 1–3% slowdowns are not by themselves a rejection. Failed target hits and large regressions must remain visible. N=3 is screening evidence, not certainty about multimodal endpoints.

## Algebra verification and limits

Run `OPENBLAS_NUM_THREADS=1 python3 research/schur_physics_control/check_math.py` from the repository root. The deterministic test constructs a small camera/point sparse Jacobian; it checks Schur/joint equivalence, the normalized coupling identity, Nyström under-approximation, SPD balanced correction, exact projected coupled systems, the implicit-flow identity and the residual-energy identity.

All tested identity errors were at most **1.31e-15**. The Nyström PSD inequality held to roundoff. The example's non-shift correction was **24.35%** of the Schur operator change and its RHS changed materially, illustrating why a naive shifted-family assumption fails. These percentages describe a constructed algebra example, not a BAL scene. The script also reproduces the high-damping false-stationarity example.

Raw outputs: [math_checks.json](math_checks.json). No GPU jobs, new scene sweeps, learned-policy training or performance claims were produced by this research pass.
