# Three bounded BA research directions

Advisory brief, 11 September 2026. No solver runs or implementation edits were performed for this brief. Read together with `docs/research_brief_feedback_2026-09-11.md`, `research/collective_bal/README.md`, and `research/schur_physics_control/RESULTS.md`.

**Recommendation:** first falsify late collective correction with a small insertion-time oracle; then test a projective point retraction that requires no additional linear solve. Keep residual-informed Schur enrichment as a diagnostic unless it clears the earlier recycling failures. None is currently a demonstrated novel solver.

The ideas address distinct errors: collective correction changes the directions and finite paths available to nonlinear optimization; projective retraction changes the finite path while preserving the tangent step; Schur enrichment reduces numerical error in a fixed quadratic. A gain in one category does not establish a gain in another.

## 1. Late collective motion: does the right computation become useful later?

**Hypothesis.** Ordinary BA first removes internal region error. Relative region motion may then account for enough remaining progress that one or two exact finite Sim3 corrections replace several fine steps. Earlier opening-stage failures do not test this stage-dependent hypothesis. The existing bridge-only solver is the starting component.

**Established ingredients and possible contribution.** Submap base frames, separator optimization, and alternating internal/global refinement already appear in [Ni, Steedly and Dellaert, ICCV 2007](https://dellaert.github.io/files/Ni07iccv.pdf), especially Sections 3.1–3.4. Linear collective modes and aggregation are established in [Konolige and Brown, 2020](https://arxiv.org/html/2007.01941). A plausible contribution would be a predictive, inexpensive criterion for when finite collective motion replaces useful fine computation on real BA, together with an explanatory failure boundary. Moving clusters by Sim3 or inserting a fixed late stage alone is not an adequate novelty claim.

**Smallest falsifiable experiment.** Use one preselected packed sample from each of Ladybug, Dubrovnik and Venice, plus two new weak-cluster synthetic seeds as positive controls. These previously inspected real families are development data, even if a point subset is new.

1. Run ordinary LM to the already frozen target and a stricter registered secondary target. Save immutable accepted-step snapshots at k = 2, 4, 8 when those states occur before target crossing. Save the complete optimizer state: lambda, any point damping, radius/controller state, counters, gauge and metric conventions.
2. From each snapshot, splice either one or two bridge-only coarse iterations, then resume ordinary LM. Compare finite nonlinear and matched linear coarse paths using the same partition, tangent basis, candidate scales, coarse budget, and continuation state. The linear path needs full objective evaluation; it cannot use the nonlinear invariance shortcut.
3. Include no-op resume to prove that checkpointing reproduces the uninterrupted trajectory. Include ordinary continuation as the meaningful alternative use of the available time. The unmodified fine solver already buys fresh useful fine computation; an extra dummy computation is not a matched baseline.
4. Count partition/setup, detection, all trial evaluations, full-cost verification, and downstream fine computation. Record total time to target and remaining fine work, not just immediate coarse cost reduction. A reduction in the number of fine steps is useful evidence but not mandatory if other expensive fine work is measurably eliminated.

Use F_target = F_ref + tau(F_0-F_ref), tau = 1e-3 and 1e-5, with the same independently frozen F_ref for every arm. A 1e-7 target is diagnostic only after checking that reference quality and numerical accuracy make it meaningful. A tighter tau approaches the feasible reference; it does not by itself certify proximity to an optimum. If a new reference is necessary, freeze it as a separately registered follow-up and retain the old target results.

**First stop rule.** One timing repetition is enough for the initial mechanism rejection screen. Stop this schedule family if none of the tried late insertions saves downstream useful fine computation on at least two real scene families. If there are work savings, repeat the relevant comparisons three times; do not select a winner from one noisy millisecond measurement. Failure rejects the tested insertion times, budgets and partitions, not every possible nonlinear hierarchy.

**Trigger to test only after the oracle leaves a margin.** Let g and H = J^T J be the full gradient and GN matrix, D the actual current damping metric, A = H + lambda D, and P the full camera-and-point tangent basis of the finite cluster action. With the gauge removed,

    gc = P^T g, Ac = P^T A P,
    Dc = 0.5 gc^T Ac^(-1) gc,
    Df = -(g^T d + 0.5 d^T A d).

Dc is the best reduction of the *same damped quadratic* in the coarse space; Df is the corresponding reduction of the available fine step. If d is inexact, Dc/Df can exceed one. Do not clamp it or call it an explained fraction. Reject undefined/nonpositive denominators. These are computation features, not certificates of actual nonlinear progress.

A provisional live rule is k >= 2 and Dc/Tc > 1.25 Df/Tf, with at most one activation per run. Tc and Tf must be past measured costs or costs frozen on development data, not future held-out runtimes. Computing this feature after an ordinary solve has already paid for that solve; use it to schedule the subsequent action and charge its acquisition. Also compare the simpler best fixed insertion time. A selector which merely learns iteration number has no demonstrated benefit over that control.

The existing coarse code uses its own diagonal damping. A strict decrement comparison requires inherited P^T D P, including cross terms and the full point contribution. Alternatively, use the inherited metric only for a clearly labeled diagnostic; do not silently identify the native coarse step with that diagnostic minimizer. Recompute derivatives after any accepted geometry change. Never reuse old factors as if the state were unchanged.

**Compute and promotion gate.** Initial real oracle: 3 cases × (baseline + 3 insertion times × 2 budgets × 2 paths) = at most 39 trajectories before no-op checks; 10 seconds per trajectory is a cap, not a timing prediction. Omit snapshots after target crossing. Add small positive controls separately. Allow at most 15 CPU minutes for this stage. If it passes, freeze one live rule and test nine new packed subsets at N=3 against ordinary LM and the best fixed schedule, keeping the prior scene-family limitation explicit. Require at least 1.10× paired-median total-time improvement, no additional target misses, and no >20% scene-family slowdown. If nonlinear and matched linear paths tie, the evidence supports scheduling/coarse computation, not a special finite-path advantage.

**Agent prompt:** “Test late bridge-only Sim3 insertion at accepted steps 2/4/8 with one/two coarse iterations. Preserve complete LM state and verify no-op resume. Compare nonlinear, matched linear, and uninterrupted fine continuation. Stop before designing a trigger unless the best tested insertion saves subsequent useful fine work on at least two real families. Keep deeper targets and all overhead explicit.”

## 2. Projective point paths: cancel depth curvature without buying another solve

This is second in practical priority, despite being track3 in the initial shortlist.

**Hypothesis.** In low-parallax tracks, much of perspective nonlinearity is a depth mode shared across views. A per-point projective path can remove that common denominator term while retaining exactly the existing Euclidean tangent step. This avoids the extra directional derivatives and right-hand sides that made T2 expensive; it also leaves the original objective unchanged, unlike temporary smoothing.

Inverse-depth representations are established. [Montiel, Civera and Davison, RSS 2006](https://www.roboticsproceedings.org/rss02/p11.pdf), equations 5 and 7–12 and Section III-A, provide the ray/inverse-depth model and analyze projection linearity. The older [ParallaxBA manuscript](https://opus.lib.uts.edu.au/bitstream/10453/35549/1/ParallaxAngleParametrization_IJRR_20140825.pdf) is also important prior art. Do not generalize the changed observation-ray objective of [2018 manifold Parallax BA](https://arxiv.org/html/1807.03556) to every earlier parallax parameterization. Parameterization alone is not new.

**Candidate A: anchored inverse-depth control.** At the immutable parent, choose a fixed anchor a equal to one observing camera's current center. Set l = ||X-a|| and n = (X-a)/l. Hold a fixed while constructing the trial, even though that camera itself may move. For the existing ordinary point tangent dX and step scale alpha, use

    X_trial = X + alpha dX / (1 - alpha n^T dX/l).

This is the finite update obtained by taking an additive tangent step in the local chart X = a + (n+u e1+v e2)/rho, with rho = 1/l and e1,e2 perpendicular to n. Its derivative at alpha=0 is dX. No additional linear solve is required.

If implementing explicit chart variables, transform the original full damping metric by the chart Jacobian T: D_chart = T^T D T. The metric-matched linearized chart step then reproduces the Euclidean physical tangent. A new diagonal damping rule confounds finite-path and regularization effects. The direct retraction formula avoids that complication.

**Candidate B: choose the chart using every observing camera.** For a point with observed parent camera coordinates q_i = R_i(X-C_i), z_i = e3^T q_i, define

    v = mean_i (R_i^T e3 / z_i),
    h = v^T dX,
    X_trial = X + alpha dX / (1 - alpha h).

For fixed cameras and pinhole projection, define gamma_i = e3^T R_i dX/z_i. Direct substitution gives the exact identity

    pi_i(X_trial)-pi_i(X)
      = alpha Jpi_i R_i dX / [1 + alpha(gamma_i-h)].

Ordinary Euclidean motion has denominator 1+alpha gamma_i. The proposed mean-v choice minimizes sum_i(gamma_i-h)^2 over a shared scalar h. Thus it cancels the common component of the depth denominators; this algebraic fact does not imply minimum reprojection defect, safe projections, or improved full BA convergence. An energy-weighted choice is a later hypothesis, not something to tune in the initial screen.

The identity is exact for point-only motion under central pinhole projection. Simultaneous camera rotations/translations and radial distortion introduce additional terms. Keep the actual pose update and full camera model in every trial evaluation. A plausible research contribution would be a useful multi-view chart-selection rule with a matched-tangent explanation and a measured benefit over standard anchored inverse depth. This search did not establish publication priority for the mean-v rule.

**Construction and safeguards.** Use the same LM solve, alpha menu and acceptance/controller rules as the comparator. Keep point0 on the ordinary Euclidean path so its fixed z gauge is preserved. Require a finite positive projective denominator and the original observed-depth/full-cost validity checks. To avoid a near-pole implementation artifact, register a denominator margin, e.g. 1-alpha h >= 0.25; if it fails, use the ordinary point path at that alpha and report fallback counts. This is a defined candidate safeguard, not a theorem. Freeze v or a at the parent and do not recompute it separately for candidate alpha values. Do not fix the anchor observation to zero residual or reduce a landmark to one DOF.

First test all eligible tracks. If a selective control is desired, register a cheap geometry-only condition before results, for example maximum angle to the first observing ray <2 degrees, computed in one pass over track observations. Treat it as a practical parallax proxy, not the maximum pairwise angle. Recomputing such a condition has a real cost.

**Smallest falsifiable experiment.** Ten new low-parallax synthetic seeds and ten moderate-parallax controls, with depth-dominated initialization errors and unchanged observations. Include a rotation-dominated negative-control family before claiming generality. Compare ordinary XYZ, anchored inverse-depth retraction, and the mean-v retraction. An algebra-only linearized chart endpoint must equal XYZ. A conventional explicit inverse-depth solver can be a later practical baseline, but its damping metric differences must be reported.

Use tau=1e-4, the same geometry gauge and target, at most 80 attempts/2 seconds per arm, and N=3 after an initial correctness screen. Count feature reductions and all fallbacks; preserve full final objective and one global similarity alignment for synthetic geometry. Add the three packed real development probes only after the synthetic mechanism passes. No extra solve or extra always-on trial is necessary for this first replacement-path test.

**Stop rule and budget.** Algebra checks must verify the pinhole identity and first-order tangent agreement on several step sizes, plus parent immutability and the fixed gauge. Stop if the method buys only lower point-only defect but no full-run speed or geometry benefit, or if improvements disappear against anchored inverse depth. Require 1.10× paired-median time-to-target gain in the intended low-parallax cohort without more target/geometry failures; otherwise classify any geometry gain as a separate initialization result. At most 15 CPU minutes and <100 MB of saved trajectories are sufficient for the first screen; cap dense per-observation histories.

**Agent prompt:** “Keep the ordinary BA linear solve. Replace its point update by dX/(1-h), first with anchored inverse-depth h and then with h equal to the mean observed fractional depth derivative. Derive and verify the exact fixed-camera denominator identity. Compare identical tangents, damping and final pixel loss on low-parallax/depth-error and rotation controls. Charge the track reduction and stop if anchored inverse depth explains all benefit.”

## 3. Residual-informed Schur enrichment: only modes still carrying error deserve work

**Hypothesis.** The previous recycled basis failed partly because its Euclidean eigenvalue ranking did not match either the current preconditioner metric or the current right-hand side. The surviving question is whether a tiny current-residual-relevant basis can remove enough unfinished quadratic work to pay for refresh. This is more specific than trying recycling again.

**Local prior negative that must be retained.** `research/schur_physics_control/RESULTS.md` already tested previous-solve Euclidean Ritz rank8/16 with current SZ refresh, balanced SPD preconditioning, and prior-CG-depth >=16 activation. Muell outer12 worsened from 41 CG / 131.9 ms to 87 CG / 305.8 ms at rank8 and 49 CG / 209.3 ms at rank16. Full native targets also failed promotion. The largest-scene and noisy extensions often never activated the method. T7's spectral menu pruning is a different experiment; this native recycling result is the relevant comparator.

Deflation in BA is established in [Das, Katyan and Kumar, WACV 2021](https://openaccess.thecvf.com/content/WACV2021/papers/Das_A_Deflation_Based_Fast_and_Robust_Preconditioner_for_Bundle_Adjustment_WACV_2021_paper.pdf). Their abstract and introduction describe deflating large Hessian eigenvalues. General near-nullspace coarse construction is also covered by the multigrid paper cited above. The potential contribution is an inexpensive BA-specific residual/metric selection and its computational break-even test; generalized Ritz extraction and balanced preconditioning themselves are standard.

**Exact diagnostic construction.** At a fixed current SPD Schur system Sd=b, let M be the incumbent SPD block preconditioner, V a retained physical-camera basis, and r=b-Sd the freshly computed current residual. Form

    K = V^T S V, G = V^T M V,
    K y_j = theta_j G y_j,
    z_j = V y_j, z_j^T M z_j = 1,
    w_j = (z_j^T r)^2 / theta_j.

Remove rank-deficient directions and require positive current theta. The generalized Ritz vectors are mutually S-orthogonal, so w_j/2 is their individual projected quadratic reduction. A low eigenvalue with negligible z_j^T r is not useful for this right-hand side. No observed Ritz value supplies a lower spectral bound for the full S.

Compare ranks 2 and 4 selected by largest w with (i) old Euclidean-small-eigenvalue selection, (ii) smallest generalized theta, (iii) ordinary continuation of PCG, and (iv) rank-matched geometric modes if already available. The full retained-basis diagnostic is an oracle with all refresh/setup charged; selecting after looking at held-out future convergence is not a live algorithm.

For a selected basis Z, set Q=Z(Z^T S Z)^(-1)Z^T and use the already implemented balanced inverse

    P_inv = Q + (I-QS) M^(-1) (I-SQ).

Keep it fixed within a PCG recurrence. An in-solve activation must restart from the current iterate with a fresh residual, or use a justified flexible scheme. Compare against a restart-only control, since discarding conjugacy can itself hurt. Refresh SZ and K when damping, geometry or robust weights change; coupled point damping changes both the Schur matrix and RHS.

**Cheaper live variant, only after a positive oracle.** Retain at most four previous generalized modes chosen using their previous eigenvalues and the current residual overlap. Refresh only these four SZ columns. Compute the exact current projected decrement 0.5 (Z^T r)^T (Z^T S Z)^(-1)(Z^T r) before deciding to activate. Previous-mode selection is an approximation; its benefit must be checked on the current system. Do not pay 16 current products and advertise rank4 setup cost.

**Smallest falsifiable experiment and gate.** Start with existing fixed captures and saved predecessor directions, including the known deep Muell case and shallow controls. If missing data make a capture impossible to reproduce, generate only a small reference capture; do not rerun a large native suite just to acquire an attractive basis. Use exactly the same operator, RHS, precision, initial iterate, true residual stopping rule and damping in every arm. Report total Schur products including refresh/verification as well as setup-plus-solve time. CPU direct-solve BA cannot validate a PCG speed claim; if using packed CPU problems, use the same PCG solver in all arms.

Stop if even the current-system oracle fails to beat old Ritz and plain PCG after charging refresh, or if gains require more setup products than are saved. Advance only for a reproducible >=1.10× setup-plus-solve improvement on the deep case with no shallow-case overhead beyond a cheap skip. Then test multiple later systems and complete nonlinear trajectories before any native promotion claim. A better linear solve alone is insufficient: Eta2 intentionally uses loose forcing.

Allocate <=15 CPU minutes for bounded diagnostic matrices and small eigensystems, ranks <=4 for the prospective live method, and no native port until the gate passes. Additional storage for Z and SZ is 2*n_camera_dof*r*8 bytes in FP64, excluding the existing system and retained diagnostic history. Avoid large matrix downloads.

**Agent prompt:** “Audit the previous failed Euclidean Ritz recycling. On frozen current Schur systems, select rank2/4 generalized modes by present residual energy and compare to old Ritz, smallest generalized modes, and uninterrupted/restart-only PCG. Include every refresh product and the unchanged true residual gate. Stop at this diagnostic unless setup-adjusted savings survive.”

## Common reporting contract

These proposed CPU mechanism tests are not Eta2/Caspar GPU comparisons. Preserve the production incumbent. Use the unchanged observations, loss, intrinsics, gauge and final feasibility checks within each comparison; do not silently replace pixel L2 by bearing loss, add priors, drop difficult tracks, or fix anchor residuals. Report target misses and all regressions. Existing real families are development evidence; new subsets are not independent scene families.

Use one BLAS/OpenMP thread and serialize timed work. Register seeds, target definitions and the finite candidate set before experiments. Save compact endpoints and selected diagnostics, not all dense intermediate matrices. The three initial stages need no new dataset or GPU allocation and can be bounded to roughly 45 CPU minutes of capped solver/diagnostic work; these are budget limits, not measured runtime estimates.

The fourth initial suggestion, consistency-gated robust bridge continuation, is deferred. With only the same questionable bridge residuals, residual information and connectivity cannot certify correspondence correctness. A usable experiment would need held-out tracks or independent alternate cycles, and globally consistent false bridges remain an identifiability counterexample. There is no justification to preserve bridges using observability alone again.
