# Three new, bounded bundle-adjustment hypotheses

Research advice, 11 September 2026. This document proposes experiments; it reports no new benchmark results. The adviser read the earlier eight-track report, the Astra follow-up and its independent review, and the Schur/physical-control results. Implementation and serial timing belong to the parent agent. The frozen Eta2 champion must remain unchanged.

**Priority:** test a finite joint camera–point retraction first; investigate a residual-derived perspective stiffness only if its directional diagnostic supports the mechanism; use a point-condensation-aware stopping rule as the separate, lower-cost linear-work question. These change, respectively, the finite path, the tangent system, and the amount of linear solution work. They do not revive the rejected coarse-insertion schedule or retained Krylov basis.

The original request was:

> i am performing bundle adjustment experiment and need guidance in which direction i could research to do something novel. give me some ideas i can ask an agent to try out. even rough directions in which the agent can research in. can be methods from physics other modeling of the problem (math optiimization etc) you name it.

The formulas below are proposed constructions and derivations, not claims of publication priority. Each has substantial established ingredients. A useful research contribution needs an incremental result over its closest inexpensive control, at identical original pixel-objective targets.

## Shared experiment contract

Use the parent's new eight-camera/120-point view-diverse depth, joint-pose and low-parallax cases, initially four seeds per family (500-series), and the three unchanged packed BAL development samples. Do not call the previously used real scene families held out. Synthetic reference values should be frozen from a bounded ordinary solve started at the generating truth; primary and secondary targets are 1.01 and 1.001 times that feasible reference. Neither reference is asserted globally optimal. Keep complete geometry errors after one global similarity alongside the pixel cost.

CPU tests retain fixed intrinsics, the same six camera tangent coordinates, camera0 pose/point0.z gauge, physical damping metric, original pixel loss, validity checks, and LM acceptance thresholds. Count preparation, all candidate evaluations, local solves, failed trials and fallback work. N=3 timings are timing repeats, not additional independent scenes. A new GPU implementation is conditional on a useful bounded screen; existing native captures can answer read-only algebra/mechanism questions earlier.

Suggested promotion screen for a full-run candidate: reach every target reached by the strongest applicable control within the identical cap; median paired time-to-primary-target speedup at least 1.10 over that control; save accepted/rejected fine work, rather than only alter one noisy timing; no synthetic family with median speedup below 0.95; and no material increase in gross geometric failures. Evaluate the secondary target separately. These are inexpensive research gates, not significance tests or a claim of universal speed. The parent's registered protocol, once frozen, owns final numerical gates and caps.

## 1. Project the LM prediction through the actual trial cameras

**Hypothesis.** The previous projective point path removed much of the fixed-camera defect while camera motion restored it. After taking the ordinary camera tangent, intersect rays for the *pixels the linear model predicted*, using the actual finite camera poses. This produces a same-tangent finite point path that treats rotation–point interaction without another global solve.

### Construction

For observation (i,j), use the existing convention

\[
q_{ij}=R_iX_j+t_i,\quad z_{ij}=q_{ij,3}<0,\quad
u_{ij}=\pi(q_{ij})=-q_{ij,1:2}/z_{ij}.
\]

The ordinary LM solve supplies \(d_i=(\omega_i,v_i)\) and \(p_j\). Its physical camera-space tangent is

\[
\dot q_{ij}=\omega_i\times(R_iX_j)+v_i+R_ip_j,
\quad \dot u_{ij}=D\pi(q_{ij})\dot q_{ij}.
\]

Keep the existing camera trial \(R_i^+=\exp(\alpha[\omega_i]_\times)R_i\), \(t_i^+=t_i+\alpha v_i\). Define *virtual* image targets

\[
u_{ij}^{\mathrm{v}}=u_{ij}+\alpha\dot u_{ij},\qquad
L(u)=\begin{bmatrix}1&0&u_1\\0&1&u_2\end{bmatrix}.
\]

These targets are current predictions plus their linear changes; they are not the measured observations. Form

\[
A_{ij}=\frac{f_i}{z_{ij}}L(u_{ij}^{\mathrm{v}})R_i^+,
\qquad
b_{ij}=-\frac{f_i}{z_{ij}}L(u_{ij}^{\mathrm{v}})t_i^+.
\]

With \(X_j^{\mathrm{lin}}=X_j+\alpha p_j\), solve one 3-by-3 system per point:

\[
\left(\sum_i A_{ij}^TA_{ij}+\lambda D_{p,j}\right)\xi_j
=\sum_i A_{ij}^T\left(b_{ij}-A_{ij}X_j^{\mathrm{lin}}\right),
\quad X_j^+=X_j^{\mathrm{lin}}+\xi_j.
\]

Here \(D_{p,j}\) is the original positive diagonal LM point metric and \(\lambda\) is the current ordinary LM damping. This centered formulation avoids a subtraction of large world coordinates. Reuse the ordinary solved tangent for the original GN prediction and LM acceptance. Evaluate the full original objective at the candidate.

**Why this preserves the tangent.** The identity \(L(u)q=0\) and its derivative give \(\dot Lq+L\dot q=0\). Therefore \(A(\alpha)X^{\mathrm{lin}}-b(\alpha)=O(\alpha^2)\). Positive damping makes the local system smoothly invertible, so \(\xi=O(\alpha^2)\); the returned physical point tangent is precisely \(p_j\). This remains true even when the actual objective includes a smooth radial-distortion map, though the virtual-ray finite target only models the pinhole part.

The rays generally do not have a common exact intersection. The method minimizes their weighted algebraic inconsistency plus a local correction penalty. It is **not** an exact projection in the full pixel metric, an exact residual geodesic, an optimal triangulator, or an exact reduced-objective solve. In particular, it can overfit the tangent prediction when that prediction itself is poor.

### Essential moving-host control

For each track select its first observing camera a, with no anchor search. Let

\[
q_a=R_aX+t_a,\quad \dot q_a=\omega_a\times(R_aX)+v_a+R_ap,
\quad h_a=\frac{q_a^T\dot q_a}{q_a^Tq_a}.
\]

Set \(q_a^+=q_a+\alpha\dot q_a/(1-\alpha h_a)\), then
\(X^+=(R_a^+)^T(q_a^+-t_a^+)\). Its physical tangent is also p. When the anchor camera is fixed, this exactly recovers the preceding radial anchored point path. Thus it isolates the value of transporting the point with the moving host. It is closely related to established anchored inverse-depth/bearing representations and is a required control, not a proposed novelty result.

Use XYZ for point0 in both new paths. If the moving-host denominator is below 0.25 or nonfinite, use XYZ for that point. The main virtual-ray system has positive \(\lambda D_p\); a linear-algebra/nonfinite failure falls back to XYZ and is charged. An **undamped diagnostic only** may use \(\lambda=0\), with fallback if the extremal eigenvalue ratio of \(D_p^{-1/2}A^TAD_p^{-1/2}\) is at most \(10^{-10}\). Do not turn undamped damping choices into a full-run sweep after seeing results.

### Closest prior art and distinguishing claim

- General tangent-step-and-projection retractions are established by [Absil and Malick, 2012](https://sites.uclouvain.be/absil/2010.038). Their framework motivates the construction; it does not by itself make this weighted BA map a second-order Riemannian retraction.
- Moving-anchor BA is explicit in [Strasdat's thesis, Appendix B.5](https://www.doc.ic.ac.uk/~ajd/Publications/strasdat_phd2012.pdf), and in the [g2o anchored inverse-depth implementation](https://github.com/RainerKuemmerle/g2o/blob/master/g2o/types/sba/edge_project_psi2uv.cpp). Merely updating landmarks relative to an optimized host is old.
- [PoVar, ECCV 2024](https://arxiv.org/html/2405.05079), builds on variable projection and object-space formulations. The proposed virtual-ray map keeps metric cameras, the original pixel objective and the already computed physical tangent; its local targets move with that tangent. It does not optimize a replacement object-space objective to convergence.
- [Geodesic acceleration](https://arxiv.org/abs/1207.4999) already corrects nonlinear least-squares steps using residual curvature. Here the testable computational distinction is one finite per-track ray solve using actual camera motion, with no global second-derivative correction solve. A Taylor expansion may overlap with block-restricted acceleration; do not claim wholly unrelated mathematical ancestry.

The possible contribution is a practical finite multiview map that beats both moving-host inverse depth and observed-pixel point polishing at equal pixel targets. If moving-host alone ties or wins, the result supports existing anchored modeling.

### Fixed test and stop

At ordinary frozen parents k=0,2,4, measure \(\|r(x^+)-r(x)-Jd\|/\|Jd\|\), point-only and joint motion, and the ratio of actual to predicted decrease. Test tangent agreement at shrinking alpha, zero-step identity, point0 gauge, parent immutability, and exact agreement of moving-host/fixed-anchor formulas for zero host motion. Report the fraction of the defect removable with the cameras fixed: an arbitrary camera error cannot always be repaired by points.

The five full-run arms are ordinary XYZ, the previous fixed-anchor point path, moving-host radial path, virtual rays with current lambda, and one safeguarded GN step of **observed-pixel** point polishing. The last control is intentionally not tangent matched: compute its GN prediction using its actual physical point displacement, and charge its line search/evaluations.

Close this branch if the virtual-ray path cannot improve joint defect or downstream fine work over moving-host, if the strongest cheap control ties its complete runtime, or if low-parallax conditioning/geometry makes the finite correction unreliable. Better one-trial cost alone is insufficient. Radially distorted BAL is labeled transfer evidence; pinhole finite-path identities must not be claimed there.

Agent prompt: “Implement the same-tangent virtual predicted-ray retraction above, one current-lambda 3-by-3 solve per landmark. Compare it to XYZ, previous anchored inverse depth, actual moving-host anchored inverse depth, and one observed-pixel polishing step. Prove tangent/gauge/immutability properties, freeze targets before comparison, charge all work, and stop if improved joint-model fidelity does not save full time to identical pixel targets.”

## 2. Add only the analytically identifiable positive perspective stiffness

**Hypothesis.** Some severe stalls are caused by omitted positive residual curvature, so scalar damping shrinks many useful directions to protect a small number of stiff ones. A residual-dependent, rank-one observation factor might add the missing directional resistance at essentially ordinary BA assembly cost.

The mechanics analogy is geometric stiffness from existing stress: GN accounts for the first-order change of observations, while residual-weighted second derivatives describe how the direction of their force changes. This is an analogy and a useful decomposition, not an assertion that BA observations are physical springs.

### Exact pinhole decomposition

For one observation let \(r=f\pi(q)-y\), \(J_q=fD\pi(q)\), \(a=J_q^Tr\), and \(e=(0,0,1)^T\). Differentiating the perspective denominator gives

\[
K_q=\sum_{\ell=1}^{2}r_\ell\nabla_q^2r_\ell
=-\frac{ae^T+ea^T}{z}.
\]

This is rank at most two. Its nonzero eigenvalues are the two values
\(-(a_3+\|a\|)/z\) and \(-(a_3-\|a\|)/z\). Generically one is positive and one negative. A small symmetric eigensystem is a sufficient CPU reference; an analytic factor can follow only after correctness is established.

For the physical observation tangent define

\[
G=[-[RX]_\times\; I\; R],\quad \dot q=Gd.
\]

The **whole** residual-curvature contribution along the ordinary pose/point path is

\[
\underbrace{\dot q^TK_q\dot q}_{k_{\rm perspective}}
+\underbrace{a^T\left[\omega\times(\omega\times RX)
+2\omega\times(Rp)\right]}_{k_{\rm pose}}.
\]

The second term includes rotation–point coupling. Therefore a perspective-only factor is not the true joint Hessian. Radial distortion and varying intrinsics require additional terms; the formula is exact for the registered fixed-intrinsics pinhole cohort.

If the positive part is \((K_q)_+=\kappa vv^T\), append one zero-residual pseudo-row \(\sqrt\kappa\,v^TG\). Summing these factors produces

\[
K_+=\sum G^T(K_q)_+G\succeq0,\qquad
(J^TJ+K_++\lambda D)d=-J^Tr.
\]

Gradient, damping D, gauge and sparse camera–point incidence remain unchanged. There is no extra global solve after the tangent is computed. The factor vanishes at exact zero residual.

For the primary test use the original GN prediction and the existing rho controller in every arm. Interpret Kplus as a **curvature-informed positive step penalty**, not an exact Newton model. Log the augmented-curvature prediction as a diagnostic only. This isolates the changed step direction from a simultaneous new acceptance law.

### Why this is not a rerun of earlier curvature experiments

The geodesic experiment changed a finite path using another global right-hand side. This experiment changes the tangent operator through a residual-derived local factor. The earlier fractional-depth penalty depends on the depth Jacobian alone; this factor depends on the signed pixel residual and a mixed screen/depth direction. Whether that extra direction matters is an empirical question, and a matched fractional-depth penalty is mandatory.

Projected Newton and elementwise Hessian filtering are established. [Longva et al., “Pitfalls of Projection”](https://arxiv.org/html/2311.14526) demonstrates that unconditional projection can slow convergence and lose affine invariance. [Fernández-Fernández et al., “Progressively Projected Newton's Method”](https://arxiv.org/html/2505.21013) studies selective projection in dynamics. These results argue for a narrow stiffness hypothesis, not for importing every finite-element Hessian filter. The possible BA contribution is the analytic low-rank residual factor and a validated regime where it repays its cost; generic eigenvalue clipping is not new.

### Fixed mechanism gate before full runs

Use ordinary frozen parents k=0,2,4 from the shared cases. For their ordinary LM tangents compute

\[
k_{\rm GN}=\|Jd\|^2,\quad
k_{\rm total}=\sum(k_{\rm perspective}+k_{\rm pose}).
\]

Verify the decomposition against a stable directional second derivative at multiple finite-difference scales. Select severe-stiffness parents by the predeclared condition \(k_{\rm total}/k_{\rm GN}\ge1\), i.e. true curvature at least twice GN along that direction. Require at least four such parents across at least two synthetic families, and median \(k_{\rm perspective}/k_{\rm total}\ge0.5\). Retain signed components and absolute magnitudes: cancellation can make this ratio exceed one. If the qualifying cohort is absent or the contribution threshold fails, stop full stiffness runs; the sampled mechanism was not supported. Do not manufacture a new harder cohort after seeing that result.

If the gate passes, compare one Kplus candidate with ordinary LM, a fractional-depth penalty \(\beta\sum a_z a_z^T\) whose trace is matched to Kplus in the original D-whitened coordinates, and the existing one-extra-damping alternative. The depth row is \(a_z=e^TG/z\); keep gauge-masked columns in the trace calculation. Recompute both factors and matching from the current state, charge their costs, and introduce no coefficient sweep.

Close if the factor merely behaves like scalar depth damping, if pose/radial/intrinsic curvature dominates, or if positive-part over-regularization costs more fine steps near the target. A native terminal stall can motivate a later separate regime only after a capture supports the same source decomposition. A pinhole synthetic result does not establish the cause of a native nine-DOF stall.

Agent prompt: “Verify the exact rank-two perspective residual Hessian and the separate pose-curvature contraction. At frozen ordinary parents, test whether perspective explains the registered severe positive curvature. Only if that gate passes, assemble its positive part as one zero-residual observation row and compare identical-target runtime with trace-matched depth damping, extra scalar damping and ordinary LM. Preserve the original GN prediction and frozen production solver.”

## 3. Stop Schur work according to the full damped-model decrease

**Hypothesis.** A camera-relative residual criterion can demand substantial camera work even when exact point elimination already supplies most of the full predicted improvement. Keep the ordinary PCG method/preconditioner and account for the constant model decrease hidden by Schur condensation when deciding to stop.

This is independent of the two curvature constructions. It changes neither a nonlinear chart nor a preconditioner, and it retains no historical directions. The previous finding that projected energy capture and Euclidean residual convergence rank methods differently motivates inspecting the stopping contract directly.

### Derivation

Write the damped quadratic with constant term removed as

\[
m(c,p)=g_c^Tc+g_p^Tp+\tfrac12c^TBc+c^TEp+\tfrac12p^TCp,
\]

where B and C include their current physical LM diagonal damping. Exact point back-substitution gives

\[
p(c)=-C^{-1}(g_p+E^Tc),\quad
S=B-EC^{-1}E^T,\quad b=-g_c+EC^{-1}g_p,
\]

\[
m(c,p(c))=-P_0-b^Tc+\tfrac12c^TSc,
\qquad P_0=\tfrac12g_p^TC^{-1}g_p.
\]

For current PCG iterate \(c_k\) and true residual \(r_k=b-Sc_k\), the achieved full damped-model decrease is

\[
P_k=P_0+b^Tc_k-\tfrac12c_k^TSc_k.
\]

The missing decrease to the exact full damped solve is exactly

\[
\varepsilon_k=\tfrac12r_k^TS^{-1}r_k.
\]

Thus a certified bound \(U_k\ge\varepsilon_k\) with \(U_k\le0.1P_k\) ensures at least \(1/1.1=90.9\%\) of the optimal full damped quadratic decrease. It says nothing by itself about actual nonlinear decrease. Keep complete pixel-objective acceptance and evaluate full time to the common targets.

For a PSD original GN matrix and positive point damping,

\[
S\succeq\lambda D_c,\qquad
U_k^{\rm diag}=\tfrac12r_k^T(\lambda D_c)^{-1}r_k
\ge\varepsilon_k.
\]

The inequality follows because the undamped-camera/point-damped block matrix is PSD and its Schur complement is PSD. It must be derived in the *actual* normalized coordinates before using it on native captures. A native additive safeguard or different shift convention must be included exactly. An estimated minimum eigenvalue or Ritz value is not automatically a valid lower spectral bound.

The diagonal upper bound can become useless as lambda tends to zero. That is an explicit failure possibility. [Meurant and Tichý](https://arxiv.org/abs/2209.14601) analyze Gauss–Radau energy bounds and sensitivity to spectral underestimates. Such bounds are a future option only after evidence that useful early stopping exists; do not pay for more Lanczos or GPU work to rescue the initial screen.

### Prior art and minimum comparisons

Inexact Schur/LM solves already underpin [Agarwal et al., “Bundle Adjustment in the Large”](https://homes.cs.washington.edu/~sagarwal/bal.pdf). Quadratic-progress stopping is also established: the [Ceres implementation](https://github.com/ceres-solver/ceres-solver/blob/master/internal/ceres/conjugate_gradients_solver.h) uses the Nash–Sofer criterion based on the relative consecutive decrease of the solved quadratic. Neither generic energy stopping nor looser forcing is novel.

The precise question here is whether **including P0**, which is constant in the camera quadratic, changes useful stopping decisions enough to save time without worse nonlinear convergence. Compare:

1. Existing residual eta=0.5 and a fixed looser eta=0.8.
2. Established Ceres/Nash camera-quadratic stopping, with one predeclared tolerance.
3. The same energy rule with and without P0.

A gain over eta=0.5 alone is insufficient if eta=0.8 or the existing Q criterion achieves it. The spectral certificate and condensation offset require separate ablation; they are distinct ingredients.

### Fixed inexpensive screen and stop

On the small frozen CPU parents, factor S only as a diagnostic oracle. Run unchanged PCG to its ordinary threshold/cap and retain P0, per-iterate true residuals, quadratic decrease, exact epsilon and the cheap upper bound. Compare earliest eligible stopping indices after at least one iteration; the expensive exact-S energy rule is labeled an oracle and excluded from deployable speed claims. One full original-objective evaluation at each arm's selected step distinguishes an attractive quadratic decrease from a usable nonlinear proposal.

An initial opportunity gate is at least 20% fewer Schur products on at least four parents spanning two families, with the selected true-cost decrease at least 90% of the ordinary selected decrease on those parents and no new invalid proposal among ordinary-valid parents. This is only a local gate. If including P0 produces no difference from omitting it, the condensation hypothesis fails. If the exact oracle helps but the diagonal bound never stops earlier, report an accuracy-estimation gap and stop this round. Do not tune the constant after examining failures.

Only a successful cheap rule earns complete CPU PCG trajectories at the same final pixel targets; include the existing residual and Ceres-style controls in those runs. Native fixed-capture replay is useful only where gp, C, the true camera damping and normalization are recoverable. A reduced Schur matrix and b alone do not recover P0. Missing full block data is a scope limit, not permission to fabricate an offset or compare unequal full objectives.

This is not an identical-linear-residual benchmark: the stopping condition intentionally changes. The final identical pixel objective is the relevant end-to-end contract. Preserve and report actual linear residuals, achieved quadratic fractions, total products and rejection counts so the tradeoff remains visible.

Agent prompt: “With unchanged Schur PCG, derive and verify the full quadratic decrement including the point-condensation constant P0. Screen an exact-energy oracle and the lambda-Dc upper bound against fixed eta0.5/0.8, Ceres Q stopping and an energy rule omitting P0. Stop if no cheap rule saves substantive Schur work or if saved linear work harms full identical-pixel-target convergence.”

## What would count as a new result

The three potential claims are deliberately narrow: finite virtual-ray reconstruction beyond a moving-host chart; useful rank-one perspective stiffness beyond matched depth damping; or a useful condensation offset beyond established quadratic stopping. Any may fail. The selected constructions are different experiments from the preceding negative studies, but a limited literature search cannot establish their priority.

One recent adjacent paper deserves a note: [CSS-BA, July 2026](https://arxiv.org/html/2607.15652), already restricts Schur-LM search directions using geometry and predicted-gain camera scoring while retaining the original objective. Therefore “geometry-aware BA updates with unchanged objective” is not itself a novelty statement. None of the three proposals above is a request to reproduce its camera-support search.

Retain negative results with their specific tested boundaries. Do not turn an explanatory identity, a local defect reduction, a linearly cheaper step or a small objective difference into a fastest-BA claim. A useful next implementation has to replace useful fine computation under the same pixel targets.
