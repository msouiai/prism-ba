# Trust-region convergence speed and better local models for bundle adjustment

The most useful next work is to reduce the cost of obtaining an acceptable BA step and to measure where its residual linearization fails. Increasing the number of radii, demanding a more accurate solution of every quadratic subproblem, or replacing the entire Gauss–Newton Hessian is not supported by the current measurements. There is also a benchmark provenance error: the recent Ladybug-1723 comparison used the original five-shift camera-TR prototype, not the corrected one-shift implementation or either later optimized candidate.

This assessment uses the retained local sources, experiment manifests and traces, and primary literature checked through September 9, 2026. New calculations below are retrospective trace analysis and small CPU algebra checks. They do not constitute new GPU measurements or evidence of a new solver speedup. The full computed evidence is in [tr_model_research_evidence.json](tr_model_research_evidence.json), reproduced by [analyze_tr_model_research.py](../bench/analyze_tr_model_research.py).

**The comparison needs a correction before further algorithmic attribution.**

The executable used for the recent Ladybug experiment was `/workspace/prism-camera-tr/prism-tr`, SHA256 `4f3fe8ae01b457c63e9d1dc3dacded1df78c1464c4212c18916273d72b5de3ef`. Its adjacent source requires five shifts, calls `tr->Add` for every shift at a checkpoint, and lacks the later accepted-interior-step damping correction. Calling that run “corrected TR-one” was incorrect. A five-shift guard is not an operator detail that leaves a one-shift policy intact: those additional directions are actually generated and scored.

The corrected one-shift executable is under `/workspace/prism-camera-tr-interior/`; later work adds recurrence scoring, FP32 fragment storage, faster assembly and point preparation, camera-block PCG, and removal of unnecessary projected solves. The newest coupled-radius candidate is separately identified by [selected_candidate.json](/workspace/prism-controller-attribution/selected_candidate.json), with its executable archived in `artifacts.tar.gz`. Its policy uses one terminal PCG direction and coupled damping rather than the original multishift candidate bank. This is a different algorithm/configuration as well as a faster implementation.

Consequently, the Ladybug experiment establishes useful behavior of the original camera-radius prototype relative to its own control. It does not measure the present champion against Caspar. The following older, but directly paired, three-repeat results for the optimized no-projection TR candidate remain relevant:

| Scene | Optimized TR median [range], s | Caspar FP32 median [range], s | Interpretation at the recorded target |
|---|---:|---:|---|
| Final-1936 | 1.554 [1.552, 1.556] | 3.238 [3.233, 3.243] | TR 2.08× faster |
| Final-13682 | 6.896 [6.895, 6.901] | 8.346 [7.797, 8.349] | TR 1.21× faster |
| Final-4585 | 2.324 [2.324, 2.362] | 0/3 hits in 20 s | No finite speed ratio |
| Trafalgar-126 | 0.217 [0.195, 0.221] | 0/3 hits in 4 s | Re-evaluate at a 1%-tolerant target |

These numbers were recomputed from `/workspace/prism-lm-point-rescue/caspar-pairs/results.json`; their protocol and recorded endpoint audits are described in [point rescue and fresh Caspar results](lm_point_rescue_results.md). They are solver-native clocks, excluding input loading, with Caspar graph setup outside its native clock. The old target thresholds are not automatically the right thresholds for a new 1%-equivalence benchmark. In particular, the Trafalgar Caspar endpoints are only approximately 0.8% above the old target and cannot fairly be treated as materially worse quality under the newly chosen tolerance. Final-4585's approximately 42% target gap is a different case.

The later coupled-radius candidate reduced three-repeat target medians from 1.551 to 0.870 s on Final-1936, 2.317 to 2.096 s on Final-4585, and 6.920 to 4.268 s on Final-13682, while slowing Trafalgar from 0.198 to 0.271 s. Those were comparisons against another Prism configuration, without fresh Caspar runs. They must not be turned into a new paired Caspar speedup by combining separate batches. See [controller attribution](controller_attribution_results.md).

**The relevant slowdown occurs before the target, not during the last fraction of a percent.**

For Ladybug-1723, the existing threshold of 452,676 is approximately 1% above the measured Caspar FP64 median endpoint. Extracting the prefix of each retained full-run trace gives:

| Quantity at cost ≤452,676 | Original five-shift camera TR | Caspar FP64 |
|---|---:|---:|
| Native crossing median [range], s | 2.376 [2.370, 2.382] | 1.403 [1.389, 1.406] |
| Accepted steps, every repeat | 16 | 29 |
| Rejected attempts before crossing, every repeat | 1 | 7 |
| Reported cumulative Schur products | 1,077–1,080 | Different joint operator; not comparable counts |
| Accepted TR steps on radius boundary | 3 | Not applicable |
| Median accepted TR gain ratio | 0.815 | Not the same acceptance policy |

The slower solver already takes fewer accepted steps and rejects less. This directly contradicts a diagnosis that excessive rejections explain this particular time-to-target gap. Average charged time per accepted step, including other work, is approximately 149 ms for the old TR configuration versus 48 ms for Caspar. This ratio is descriptive rather than an isolated per-kernel comparison, but identifies the right direction for investigation.

The familiar 208→5 rejection count concerned complete runs through their stopping conditions. Much of that work occurs after the practical target has been attained. Likewise, comparing roughly 20 s of Prism refinement with 5.4 s from Caspar's default 200-iteration cap mixed endpoint quality and termination rules: the Caspar driver defaults to 200 iterations, not a certified common convergence condition. The intermediate Ladybug target states were not exported for independent scoring; their crossings remain trace-based measurements, not newly audited target certificates.

**Existing profiles distinguish expensive linear algebra from an inadequate model.**

On an earlier guarded projected-TR run of Final-13682, the recorded GPU attribution was:

| Work | GPU seconds | Share |
|---|---:|---:|
| Schur products including point inverse application | 8.308 | 51.3% |
| Point factors, diagonal and reduced RHS | 3.086 | 19.1% |
| Jacobian/block assembly | 2.499 | 15.4% |
| Full unregularized GN prediction | 1.719 | 10.6% |
| Projected dense matrix products | 0.137 | 0.85% |

This trajectory had seven accepted steps and zero rejections. Removing every rejection would save nothing. Eliminating the measured projected dense products alone would save less than 1% of GPU work; that number excludes other projection costs and is not a bound on all projection overhead. The earlier [bottleneck report](guarded_tr_bottleneck.md) carefully makes this distinction.

The two Schur passes plus point inverse cost approximately 50.5 ms per application on that large captured problem. Earlier Caspar FP32 profiles measured about 26.6 ms for its joint normal-equation product. Precision and formulation both differ, so this is not proof that Schur is intrinsically twice as slow. It explains why a lower iteration count need not imply lower elapsed time. The Caspar paper describes direct normal-equation PCG with node-block Jacobi preconditioning, symbolic simplification, reduced register pressure, memory-layout optimization and kernel fusion; it does not rely on Schur elimination.[^caspar]

Some of this work has already been addressed locally. Guarded point factorization and fused RHS/diagonal reduced a recorded point-preparation phase from 3.113 to 1.288 s. Camera-Hessian block PCG reduced a large-scene product count from 160 to 43, and target time from 12.530 to 6.905 s. These are precisely the execution improvements missing from the old Ladybug binary. See [point preparation](point_preparation_results.md) and [camera PCG](camera_pcg_results.md). A fresh profile of the current selected executable is still required before assigning percentages to its remaining bottleneck.

**The mathematical distinction: solving the quadratic better versus making it more faithful.**

In local coordinates for the implemented retraction, let

\[
F(x)=\tfrac12\|r(x)\|^2,\qquad
m(d)=F(x)+g^Td+\tfrac12d^TH_{GN}d,
\quad g=J^Tr,\quad H_{GN}=J^TJ.
\]

The exact Hessian of the residual objective in those coordinates is

\[
\nabla^2F=J^TJ+\sum_i r_i\nabla^2r_i.
\]

Gauss–Newton omits residual curvature. Damping and a trust radius can reduce exposure to that omission; they do not estimate it. Large residuals alone also do not prove the omission is dominant: the directional curvature can be small, and many accepted steps in the Ladybug prefix already have reasonable gain ratios.

There are at least four distinguishable reasons for bad progress: a poor solution of the current linear/quadratic problem; nonlinear residual curvature; point/camera coupling or inconsistent model prediction after changing the step; and numerical error from precision, derivatives or stale data. Each suggests a different remedy. An accurately solved but badly predictive quadratic needs a better model or a shorter step. A good model with an inaccurate linear solution needs preconditioning or more useful Krylov directions. A prediction that omits changed point increments needs an accounting correction, not a new TR algorithm.

Define the measured residual defect of the actual proposed step as

\[
v=Jd,\qquad e=r(x\oplus d)-r(x)-v.
\]

The following identity exactly separates prediction from actual decrease:

\[
\mathrm{pred}-\mathrm{ared}=(r+v)^Te+\tfrac12\|e\|^2.
\]

This identity applies to the same residual definition, observation set, retraction and final proposed increment on both sides. It can be accumulated by whole point tracks to identify whether a small subset accounts for most of the model error. It is more informative than rejection counts, and it does not require a residual Hessian. Simultaneously logging the linear residual or TR KKT residual distinguishes model error from an inadequate subproblem solution.

The CPU checks reproduce this identity to a maximum scaled error of 9.77e-15 on 100 random examples. This checks algebra, not whether real BA defects concentrate on any particular track class. Existing aggregate logs do not contain the per-track information needed to establish that empirical claim.

**Why BA makes camera-only damping structurally incomplete.**

Write the normal equations in camera and point blocks, with cross block W and damped point block \(C_\tau=C+\tau D_p\). Back-substitution gives

\[
d_p(d_c)=-C_\tau^{-1}g_p-C_\tau^{-1}W^Td_c=a+Kd_c.
\]

Shrinking the camera direction to zero leaves the point-only component \(a\). Thus shrinking the camera radius, or increasing only camera damping, does not make the full increment approach zero. This is especially consequential for weak depth directions, where the point inverse can amplify an otherwise modest forcing. A dense example in the accompanying checks has camera norm 8.83e-13 after camera damping reaches 1e12, while point norm remains 0.09736, agreeing with the point-only limit.

This mechanism was already derived and tested in [point-trust results](point_trust_results.md). It is a design constraint for a new method, not a discovery that warrants repeating failed damping sweeps. The later coupled-radius candidate is relevant because rejected attempts can increase both camera and point damping.

With coupled LM damping, elimination yields

\[
S(\lambda)=B+\lambda D_c-W(C+\lambda D_p)^{-1}W^T,
\qquad b(\lambda)=-g_c+W(C+\lambda D_p)^{-1}g_p.
\]

Neither the operator nor the right-hand side is generally a fixed Schur system plus a scalar shift. This is the central limitation on ordinary multishift reuse in the reduced camera system. Maintaining exact shift invariance by freezing point damping changes which family of joint BA steps is being explored.

**What the trust-region literature offers, and its limits here.**

| Research direction | Relevant result | Consequence for Prism |
|---|---|---|
| Inexact Newton and practical LM | Eisenstat–Walker ties inner accuracy to nonlinear progress; Ceres supports inexact LM and model-progress stopping.[^forcing][^ceres] | Control total inner work. A universal short CG cap is not justified. |
| GLTR / trlib | Krylov projection solves radius subproblems; trlib explicitly supports reentry with a new radius.[^gltr] | Reuse a basis within a frozen linearization. This reuse itself is established prior art. |
| Recent GLTR theory | Feng–Wu (2025) analyzes convergence of the subproblem solution and multiplier.[^feng] | A tiny projected residual is not automatically a small full-space residual. |
| Extended Krylov / TREK | Al Daas–Gould, first posted 2025, exploits a low-dimensional family of regularized solutions with matrix and inverse actions.[^trek] | Attractive when inverse actions are cheap; not a free improvement for a matrix-free Schur system. |
| Directional higher-order corrections | Transtrum–Sethna derives geodesic acceleration; a July 2026 RNC-LM preprint extends corrections along a curve.[^geodesic][^rnc] | Improve the proposed path without forming all residual Hessians, but charge extra solves. |
| Nonlinear elimination | Ceres inner iterations and PoVar motivate optimizing separable blocks conditionally.[^ceres][^povar] | Points are a natural local correction target; periodic DLT and exact pixel-error minimization are different operations. |
| Geometry-sensitive directions | July 2026 CSS-BA restricts the Schur search subspace using geometric support.[^css] | Geometry can guide which directions to trust. Its evidence is not a demonstration of faster GPU Prism. |
| Stable elimination | Square Root BA uses QR nullspace marginalization and supports accurate single-precision experiments.[^rootba] | Precision changes should preserve a coherent residual model; conversion to float alone is insufficient. |

The 2026 RNC-LM and CSS-BA papers are recent preprints, not replicated BA speed results for this implementation. PoVar's initialization-free experiments use an object/projective formulation; that evidence cannot be transferred directly to the fixed calibrated pixel-L2 objective. For TREK, replacing inverse actions with approximate preconditioning would require its own residual and cost analysis. None of these methods removes the need to evaluate the actual BA objective.

Our previous tests also supply constraints: adaptive projected radii and persistent quadratic ray expansion lost; a two-dimensional camera/point split TR lost both development scenes; truncating all solves to depth 64 split the scenes; nonlinear point refinement spent 6.6–8.9 s on rescue work and still missed Final-4585. A proposed method must address why those costs or trajectories would change. See [adaptive-radius rollouts](adaptive_radius_results.md), [joint-TR research](joint_tr_research_log.md), and [point refinement](lm_point_rescue_results.md).

**Proposal 1: fit the residual along a failed direction, not just its quadratic cost.**

This is the first model-improvement experiment I would implement. After an ordinary finite trial produces a poor gain ratio, retain its defect \(e\) and approximate residuals along the same complete joint direction by

\[
\widehat r(\alpha)=r+\alpha v+\alpha^2 e,\qquad 0\leq\alpha\leq1.
\]

It matches the residual at zero and at the evaluated trial, and matches the first derivative at zero. It is a residual interpolant, not a certified second-order Taylor expansion. Its squared norm is the inexpensive quartic

\[
\widehat F(\alpha)=\tfrac12r^Tr+\alpha r^Tv
 +\alpha^2(\tfrac12v^Tv+r^Te)
 +\alpha^3v^Te+\tfrac12\alpha^4e^Te.
\]

Solve its scalar cubic derivative, retain real roots inside [0,1], and compare their values with the endpoints. Use the best nonzero candidate for one real objective evaluation. Retain the original true-cost and sufficient-decrease checks; fall back to the incumbent rescue if it fails. No new large linear system is required. Only three additional defect dot products are needed beyond ordinary model coefficients, although obtaining them still requires reading or recomputing the relevant residual data. They could be accumulated in a fused diagnostic/acceptance pass rather than stored in new observation-sized arrays.

The important difference from the previously unsuccessful ray search is that the latter minimized the original quadratic along saved camera rays and could expand them. This proposal learns the finite residual error from a real trial and initially only contracts one fixed joint direction. It does not add a permanent bank of radius candidates. It should activate only where failed-trial/backtracking cost can pay for it; Ladybug's single rejection before the target makes it a poor primary speed showcase.

The path must remain \(x\oplus(\alpha d)\), with any point mask fixed. Recomputing points as \(a+\alpha Kd_c\) while scaling cameras does not return to the current state at alpha zero and invalidates these coefficients. If a point safeguard subsequently changes the candidate, its final model prediction must be reevaluated. Nonfinite or near-pole trials should use the existing fallback, not fit a quartic to invalid values. The proposed interpolant has no error bound between zero and one; real scoring is indispensable.

The algebra checks agree between polynomial and direct residual-model evaluation within 6.50e-16. A useful next diagnostic is whether it predicts a successful backtracking scale on retained failed BA directions more accurately than the GN quadratic, at lower total cost than the existing eight-probe search. Success on a constructed polynomial alone establishes no performance benefit.

**Proposal 2: use perspective geometry to decide where a local model can be trusted.**

For an affine camera-space path \(q(\alpha)=q+\alpha\delta q\), ignoring distortion temporarily, write \(u=\delta q_z/q_z\). Perspective division gives the exact relationship

\[
\Delta\pi_{\mathrm{actual}}(\alpha)
=\frac{\Delta\pi_{\mathrm{linear}}(\alpha)}{1+\alpha u},
\qquad
\frac{\|\Delta\pi_{\mathrm{actual}}-\Delta\pi_{\mathrm{linear}}\|}
{\|\Delta\pi_{\mathrm{linear}}\|}
=\frac{|\alpha u|}{|1+\alpha u|}.
\]

A point moving halfway toward the camera plane can therefore have 100% relative error in the predicted projection displacement; at a 90% depth decrease the error is 900%. A camera-parameter norm does not directly bound either quantity. The accompanying perspective examples verify these figures. This calculation concerns an affine camera-space path without radial distortion; it is not a guarantee for rotating cameras or the complete SIMPLE_RADIAL residual.

My BA-specific extension is to aggregate depth-change and residual-defect diagnostics by track. For tracks responsible for large model error, fit the small residual curve or perform one bounded point-only correction using existing point factors. Do not shrink the whole camera trajectory because of the single worst observation, and do not drop inconvenient observations from the acceptance objective. A single point is shared across its observations, so any correction must choose one consistent point increment for the entire track.

A closer approximation can retain the perspective denominator in a one-dimensional surrogate instead of Taylor-expanding it. With fixed cameras, point motion is affine in camera coordinates, making this especially convenient for conditional point corrections; radial distortion can also be evaluated directly along that ray. Under joint motion, approximate camera-space motion to second order and keep projection nonlinear. This moves approximation effort toward the actual perspective singularity rather than adding arbitrary damping levels.

This direction is deliberately different from all-point DLT resets. A reset can decrease immediate cost while changing the subsequent basin; the recorded Final-4585 result already illustrates that problem. Selective local correction should have a strict work budget and be judged by later time-to-target, not by its immediate cost drop. Its advantage over the previously failed point-refinement kernel remains a hypothesis: selectivity and reuse must offset their own overhead.

**Proposal 3: keep an inexpensive full joint operator as a serious alternative to Schur.**

For fixed SPD block metric D, joint regularization is

\[
(H+\lambda D)d=-g.
\]

With \(z=D^{1/2}d\), it becomes

\[
(D^{-1/2}HD^{-1/2}+\lambda I)z=-D^{-1/2}g.
\]

Unlike the eliminated system with lambda-dependent point blocks, this is an exact scalar-shift family in a frozen linearization. It permits a shared joint Krylov space to represent a continuous range of damping/radius choices without freezing point damping. The algebra checks verify both the transformed solve and ordinary block elimination against the dense joint solve to approximately 2.4e-15 relative error.

This suggests a controlled engineering experiment: first compare joint and Schur operator/PCG work for the identical damped quadratic and the same residual criterion. Only then try the joint backend with the inexpensive coupled-radius controller. Reuse block preconditioning and FP64 scoring. Select one regularized candidate initially; do not immediately create five joint solutions merely because shift invariance is available.

The tradeoff is substantial. The joint vector includes all point coordinates; it can require more iterations and a much larger basis. Additional arbitrary preconditioning transforms the shift into \(\lambda M^{-1/2}DM^{-1/2}\), which is not generally scalar. Choosing the preconditioner to coincide with the TR metric restores that property but changes the geometry relative to another incumbent. Joint scalar-shift invariance is an algebraic opportunity, not proof of lower runtime. Caspar's success makes testing the formulation reasonable; it does not make adopting it novel.

**Proposal 4: pay for linear accuracy only while it improves useful model reduction.**

The appropriate forcing tolerance depends on conditioning, radius activity, the quality of the nonlinear model, and how close the requested target is. Repeatedly solving a stale local approximation much more accurately than its observed defect is unproductive. Conversely, a cheap inaccurate direction can increase the total number of outer steps. The earlier depth-64 tests and explicit residual captures show both failure modes.

One diagnostic policy would compare incremental quadratic improvement per extra Schur product with the measured prediction error from prior accepted steps. A more conservative certificate, when a lower eigenvalue bound mu>0 of a damped SPD quadratic is available, is

\[
q(d)-q(d_*)\leq\frac{\|Ad+g\|^2}{2\mu}.
\]

On a convex radius-constrained quadratic, the support gap
\(\nabla q(d)^Td+R\|\nabla q(d)\|\) supplies another upper bound for Euclidean radius R. Neither bound is automatically useful for a nearly singular or numerically indefinite operator, and neither measures nonlinear model error. The measured defect is itself only a heuristic predictor for the next state.

The proposed distinction is operational: grow the Krylov solve when the linear model is inadequate; shorten or improve the nonlinear path when the quadratic is solved well but predicts badly. A bounded forcing policy plus existing residual verification is a better first test than globally tightening or loosening CG. This application follows established inexact-solve principles, not a new convergence theorem.[^forcing]

**When to consider a genuinely better quadratic Hessian.**

If defect diagnostics implicate persistent curvature rather than step length, a structured correction to \(J^TJ\) is possible. In consistent local coordinates, the gradient difference minus the integrated GN contribution approximately measures the omitted curvature action. Using the two endpoint Jacobians as a trapezoidal estimate suggests

\[
y_c=g_{k+1}-g_k-\tfrac12(H_{GN,k}+H_{GN,k+1})s_k.
\]

A limited-memory structured secant update could fit this action while retaining analytic GN blocks. Transport between camera tangent spaces and current scaling must be handled correctly. The endpoint average is an approximation to the GN integral, not an exact residual-Hessian observation. Updates can be indefinite and dense in effect; safeguarding and extra products can erase the benefit. Structured quasi-Newton NLS is established prior art.[^secant] I would rank this below the scalar residual-curve experiment.

Geodesic acceleration offers a different correction:

\[
a=-(J^TJ+\lambda D)^{-1}J^T r''[d,d],\qquad
d_{\mathrm{corrected}}=d+\tfrac12a.
\]

It changes the step using directional curvature rather than replacing the GN Hessian.[^geodesic] Reusing a factorization can make that attractive for direct solvers. In this matrix-free GPU implementation, an additional global right-hand side can require another expensive iterative solve; it is not free. A point-block approximation can use cached 3x3 factors, but then loses the full coupled interpretation and must be tested as a bounded heuristic. The July 2026 higher-order work strengthens the motivation for exploring curved paths, not a claim that its reported speedups transfer to BA.[^rnc]

**The TR × Student-t observation does not establish redundancy.**

Both mechanisms may suppress bad proposals, but they act on different objects. A radius changes permissible steps for a fixed objective. Student-t changes residual influence and generally changes both the objective and its local curvature. Robust BA using Student-t predates this investigation.[^student]

There are concrete counter-scenarios to the proposed “they should not stack” prediction: geometrically difficult but consistent observations can need radius control even after robustification, while a few mismatches can remain harmful even under cautious L2 steps. Fewer rejections under a changed loss can also reflect a changed acceptance test rather than a repaired approximation to the original L2 problem. The local T-kernel report itself records cases where total L2 increases substantially while robust or inlier metrics improve.

A factorial experiment is still appropriate, but the interaction is unknown. Freeze the evaluation observations and target once; freeze Student-t scale within each trial/retry comparison; charge weight/scale updates; and evaluate all four arms using the same externally scored quantity. If the aim is unchanged all-observation L2 convergence, a robust objective cannot silently substitute for it. A robust-to-L2 continuation or robust proposal with L2 acceptance would be a separately specified experiment.

**A bounded experiment order, focused on useful convergence.**

1. Freeze the actual optimized executable/configuration and measure it against Caspar FP64 and FP32. Use Ladybug-1723, Dubrovnik-88 or Trafalgar-126, and Final-1936 as a small initial panel. Their known behavior differs; no scene-specific best-arm selection. Use a fixed reference cost per scene and primary target 1.01 times that reference, with 1.005 and 1.02 sensitivity levels declared before the candidate runs.
2. Run three alternating repetitions per configuration, with fresh target-stopping state exports and independent FP64 scoring. Keep nonlinear traces separate from heavily instrumented profiles. Treat missed targets as censored; report all repeats, ranges, target hit counts and geometric-mean time ratios over jointly reached targets alongside misses. Do not count repeated executions as additional independent scenes.
3. At a small number of captured good and failed states, measure true linear residual, gain ratio, residual defect by track, depth-change statistics, and actual candidate cost. This identifies which of subproblem accuracy, residual curvature, or local point motion is limiting.
4. Test the residual-curve contraction on those failed directions before integrating a new controller. Give it one additional real score, retain fallback, and measure whether it saves scoring or a new Krylov sweep. Test selective point correction only if the defect is concentrated enough to justify it.
5. If accepted steps still dominate the target clock, compare joint versus Schur products at fixed damping, then consider the full coupled controller. Only expand to Final-4585 and Final-13682 after the small/medium evidence supports a plausible cost saving.

The selection criterion is lower time to the same useful accuracy, with sub-1% endpoint differences treated as equivalent under the chosen convention. Minor median regressions on one scene should not automatically veto a substantial cross-scene gain, but tail slowdowns and target misses remain visible. There is no justification for polishing the last 0.2% of error and presenting those additional seconds as necessary convergence work.

**Research judgment.** The strongest near-term engineering direction is the already successful one-shift, block-preconditioned, coupled controller with correct benchmark provenance. The strongest new model experiment is to use measured residual defects to choose a better bounded trial path, adding selective point treatment where perspective curvature demands it. Full joint Krylov solves provide a mathematically cleaner route to shared damping exploration than freezing point damping in Schur space. Novelty, if any, would need to lie in the specific BA-aware model-error diagnostics, path construction and measurable reduction in work; generic TR, multishift reuse, robust weighting, variable projection and geodesic acceleration are established ideas.

**Sources and reproducible local evidence**

[^caspar]: Emil Martens, Aaron Miller, Matias Varnum and Annette Stahl. [Caspar: CUDA Accelerator for Symbolic Programming with Adaptive Reordering](https://arxiv.org/html/2605.30583v1), May 2026, especially Sections III–V. The paper's release and hardware results are distinct from the locally pinned backend.
[^forcing]: Stanley C. Eisenstat and Homer F. Walker. [Choosing the Forcing Terms in an Inexact Newton Method](https://users.wpi.edu/~walker/Papers/forcing_terms%2CSISC_17%2C1996%2C16-32.pdf), SIAM Journal on Scientific Computing 17(1), 1996.
[^ceres]: Ceres Solver documentation. [Solving Non-linear Least Squares](https://ceres-solver.readthedocs.io/latest/nnls_solving.html), sections on LM, iterative solvers, trust regions and inner iterations; accessed September 2026.
[^gltr]: Felix Lenders, Christian Kirches and Andreas Potschka. [trlib: A vector-free implementation of the GLTR method for iterative solution of the trust region problem](https://arxiv.org/html/1611.04718v2), revised August 2017, especially Sections 3 and 4.7–4.8; builds on Gould et al. (1999).
[^feng]: Bo Feng and Gang Wu. [On convergence of the generalized Lanczos trust-region method for trust-region subproblems](https://doi.org/10.1007/s10444-024-10217-5), Advances in Computational Mathematics 51, article 4, January 2025.
[^trek]: Hussam Al Daas and Nicholas I. M. Gould. [Extended-Krylov-subspace methods for trust-region and norm-regularization subproblems](https://arxiv.org/abs/2511.11135), first posted November 2025; full-text versions 1 and 3 consulted for inverse-action requirements.
[^geodesic]: Mark K. Transtrum and James P. Sethna. [Geodesic acceleration and the small-curvature approximation for nonlinear least squares](https://arxiv.org/html/1207.4999v1), 2012, especially equations 11–13.
[^rnc]: Jianing Liu and Dong H. Zhang. [Higher-Order Geometric Updates for Levenberg–Marquardt Method via Riemann Normal Coordinates](https://arxiv.org/html/2607.07623v1), July 2026 preprint. Its experimental applications are not a GPU BAL comparison.
[^povar]: Simon Weber, Je Hyeong Hong and Daniel Cremers. [Power Variable Projection for Initialization-Free Large-Scale Bundle Adjustment](https://www.ecva.net/papers/eccv_2024/papers_ECCV/papers/02034.pdf), ECCV 2024; [expanded text](https://arxiv.org/html/2405.05079v2).
[^css]: Ayano Kaneda, Takafumi Taketomi, Shugo Yamaguchi and Shigeo Morishima. [CSS-BA: Gate-Guided Column Space Search for Bundle Adjustment](https://arxiv.org/html/2607.15652v1), July 2026 preprint.
[^rootba]: Nikolaus Demmel, Christiane Sommer, Daniel Cremers and Vladyslav Usenko. [Square Root Bundle Adjustment for Large-Scale Reconstruction](https://arxiv.org/abs/2103.01843), 2021.
[^secant]: Graciela Croceri, Gonzalo Pizarro and Graciela Sottosanto. [An Adaptive Nonmonotone Trust Region Method Based on a Structured Quasi Newton Equation for the Nonlinear Least Squares Problem](https://sedici.unlp.edu.ar/handle/10915/135159), Electronic Journal of SADIO 16, 2017. Cited as structured-secant prior art, not as the source of the particular endpoint-average proposal above.
[^student]: Aleksandr Y. Aravkin, Michael Styer, Zachary Moratto, Ara Nefian and Michael Broxton. [Student's T Robust Bundle Adjustment Algorithm](https://arxiv.org/abs/1111.1400), 2011 preprint / ICIP 2012.

Local primary records include `/workspace/prism-camera-tr/source-tr.cu`, the corresponding original binary and Ladybug logs, `/workspace/prism-camera-tr-interior/protocol.json`, the retained Caspar driver `bench/caspar/caspar_bal64_checked.cc`, `/workspace/prism-lm-point-rescue/caspar-pairs/results.json`, and `/workspace/prism-controller-attribution/selected_candidate.json`. Earlier study reports preserve recorded independent endpoint audits; this assessment re-read results and source, and did not re-audit every archived state. Source and binary hashes for the Ladybug comparison and the new CPU checks are recorded in the companion evidence JSON.
