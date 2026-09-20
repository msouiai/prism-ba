# Feedback to the agent who proposed the Eta2 research directions

**Date:** 2026-09-12  
**Subject:** Results from Briefs 0–12, plus the subsequent static long-track damping proposal  
**Baseline:** Frozen Eta2 champion; original implementation and defaults preserved

## Verdict

We investigated all 13 briefs through their applicable diagnostic gates. Seven candidate configurations reached native GPU comparisons. None displaced the frozen Eta2 as the general champion.

There is one strong, independently repeated local improvement: **a more accurate first-three-accepted-step opening reaches the registered Venice52 target in 10/10 runs, versus 0/10 controls, with median crossing time 0.37605 seconds.** It also slows seven of nine practical timing cells and loses Final3068 successes. Removing opening clipping alone does not reproduce the Venice improvement. We therefore retain this as an experimental result whose useful ingredients remain incompletely attributed.

Several suggestions produced useful mathematical or diagnostic evidence without improving convergence to the targets. In particular, coarse spaces substantially improve a reference spectrum; point charts can improve conditional proposal costs; and nonlinear coarse corrections can produce real descent at terminal witnesses. These observations did not translate into a general solver improvement under the tested implementations.

This document distinguishes an implemented negative result, a failed prerequisite, and an untested variant. “Investigated all briefs” does **not** mean every variant in every brief received a full native grid.

## Evaluation and evidence scope

- **Main campaign:** 538 native comparison runs across seven candidate configurations, plus ten independent Venice confirmation runs: **548 native runs**. Another 40 baseline runs tested early trajectory predictors. Witness, numerical, and correctness studies are separate from these counts.
- **Later track-damping experiment:** 20 additional scored native runs. This brings the two reported efforts to **568 scored native comparison/confirmation runs**, not 568 distinct problems.
- **Objective:** Full original-observation L2 reprojection error; SIMPLE_RADIAL, unshared intrinsics, and fixed `k2=0`. No robust loss, dropped observations, or changed scored objective.
- **Baseline precision:** FP64 state and principal solve/acceptance arithmetic, with the frozen solver's compact mixed-storage fragments. It is not a uniformly FP64 stored operator. Coherent FP64 reference paths are explicitly distinguished.
- **Practical panel:** Ladybug539, Trafalgar138, and Final394, each at three frozen tolerances, giving nine scene/tolerance cells. Targets are 1.005, 1.01, and 1.02 times the pre-existing anchors. N=3 per arm/cell; native caps 5, 5, and 8 seconds respectively.
- **Tail targets:** Venice52 = **243740.27**; Final3068 = **1744796.9841897595**. N=5 per arm, 60 native seconds/600 outers, ordinary champion stopping. The two opening experiments additionally screen Ladybug1197 at its registered target.
- **Comparisons:** One derived binary with the intervention off/on, alternating run order; source/header checks and original-versus-derived-off compatibility precede comparisons. Endpoint costs receive independent CPU audits. New solver work is charged, misses remain censored, and both improvement and regression directions are reported.
- **Signal rule:** More than 0.15% median endpoint difference, or disjoint observed target-time ranges. Observed ranges are not confidence intervals. N=5 hit counts are screening observations, not established population reliability.

The original source SHA256 is `22c18359a526526ae0a5b5109187878ab1cef33b453f6bbddc2aa92597a607d8`; the original binary SHA256 is `1e3d2cf22a8a43075114e0ca2024923dad330461e35d0074938d0412cd77ecc0`. All 44 pinned headers were verified. This campaign is not a new Caspar or broader SOTA comparison.

## Native results at a glance

Each row has its own freshly measured control cohort. Variation between different rows' Final3068 control hit counts must not be interpreted as an algorithm difference.

| Candidate | Practical cells faster / slower / overlapping | Venice hits, off → on | Final3068 hits, off → on | Interpretation |
|---|---:|---:|---:|---|
| Steihaug PCG | 2 / 4 / 3 | 0/5 → 0/5 | 4/5 → 0/5 | Local timing wins; tail reliability loss |
| Additive K8 coarse PCG | 0 / 1 / 8 | 0/5 → 0/5 | 4/5 → 4/5 | Setup cost without target benefit |
| PI radius | 4 / 1 / 4 | 0/5 → 0/5 | 1/5 → 2/5 | No clear storm reduction; Venice cost worsens |
| Accurate opening, first three accepts | 1 / 7 / 1 | 0/5 → 5/5 | 2/5 → 0/5 | Confirmed Venice benefit; global regression |
| Opening unclipping only | 0 / 0 / 9 | 0/5 → 0/5 | 4/5 → 2/5 | Fails to explain Venice benefit; Final branch inactive |
| Terminal passenger correction | 0 / 0 / 9 | 0/5 → 0/5 | 4/5 → 4/5 | Accepted local corrections; zero target rescues |
| Terminal soft-mode kick | 0 / 0 / 9 | 0/5 → 0/5 | 3/5 → 3/5 | Seven admitted interventions; zero target rescues |

Every configuration and its control reached all 27 practical targets. Several interventions are inactive on much of that panel; timing variation while inactive is not evidence of an active algorithm effect. In particular, the opening-unclipping Final3068 hit-count change is **not attributable to unclipping**, because its branch never changes the step on those runs.

## Feedback by brief

### Brief 0 — Witness decomposition

**What we did:** Captured three Venice witnesses, three Final3068 stop witnesses, and the Ladybug1197 opening witness with two controls. Compared captured Eta2 directions with coherent accurate reference directions, both raw and clipped; decomposed model error and its concentration.

**Finding:** The proposed binary “solve or model” classification is too simple across these states.

- Venice witness 0: true decrease rises from **0.547 to 35.510** with the coherent reference direction. There is useful missing linear information there.
- Venice witness 1: the raw reference **increases cost by 20.046**; clipping restores a small positive decrease of **0.03486**.
- The three raw Final references increase cost by approximately **219, 205310, and 533927**. Their clipped counterparts provide almost the same decrease as Eta2.
- At Ladybug, the top 200 points account for **98.39% of absolute point-only model error**, but two-observation tracks account for only **26.42%**. Concentration is real; an exclusively two-view explanation is not supported.

**Corrections and limits:** Reduced reference residual certificates pass, but some original full-normal residual checks fail and are retained. Additional CPU point completion brings the three Venice full scaled residuals below 1e-10 without changing the conclusion. Do not describe every original reference as an exactly certified full normal solve. The historical 2.4e4 Ladybug fling came from an older solver configuration; the verified frozen-champion witness has one outward displacement of 16.3 against scene radius 12.32.

**Feedback:** Diagnose accuracy, scaling/clipping, and nonlinear usefulness separately at each witness. A high-quality linear solve is neither uniformly useless nor a sufficient cure.

### Brief 1 — Rigid-cluster coarse PCG

**What we did:** Coarse-fraction and spectral diagnostics; a native K8 additive preconditioner; a later METIS covisibility-partition control.

**Finding:** The spectral mechanism is real. On a coherent Venice reference, the measured condition number drops from approximately **1.245 million to 4198**, about **296×**. The native implementation still provides no target-reliability benefit. Repeated setup costs **0.92–1.41 seconds** on Final3068 and **0.35–0.38 seconds** on Venice. Some production coarse matrices fail the SPD check and fall back.

The initial geometric Final partition put almost all cameras in one cluster. METIS corrects that imbalance. At Final witness 5, K8 gauge-free coverage of **raw-reference minus raw-Eta2** rises from **1.26% to 86.65%**. However, the missing direction is only **0.412%** of the reference norm, and equally clipped true decrease changes only **15.26747 → 15.27792**. Coverage of raw reference minus the actually clipped Eta2 step is a different quantity and is only **19.60%** there. Other K/witness comparisons include losses.

**Limits:** We did not time every K, deflated PCG, or balancing variants. The stronger all-K kill criterion was not met. Graph coverage is not a measured native graph-preconditioner win.

**Feedback:** Continue only after demonstrating useful *nonlinear* decrease per paid setup at the actual constrained step. Report the absolute missing-direction magnitude, basis rank, gauge contribution, and partition balance alongside projection fractions.

### Brief 2 — Point charts and depth freezing

**What we did:** A 162-row conditional chart screen, followed by 54 depth-freezing rows.

**Finding:** Inverse depth gives substantial conditional gains: roughly **46% lower Ladybug proposal cost** and around **1% lower Venice proposal costs**. But the hypothesized safety benefit fails. Ladybug outward flings increase from **1 to 63**, maximum world displacement reaches **1803**, and two cheirality flips occur. Depth freezing removes the flips and reduces maximum displacement, yet leaves **63 outward flings**. On Venice, freezing suppresses useful inward recovery of already escaped points and removes the chart's gain.

**Mathematical correction:** A bounded rotation on the homogeneous sphere does not bound Euclidean position and does not remove projection poles. Chart-dependent diagonal damping also changes the metric; this is not solely a retraction comparison.

**Limits:** Conditional witness experiments, not complete native chart trajectories. The original fling gate failed, so no native rollout or point-damping decoupling sweep was justified.

**Feedback:** Distinguish crossing projective infinity, Euclidean displacement, depth-sign changes, and proximity to an observation's projection horizon. They are different properties and need different safeguards.

### Brief 3 — Steihaug–Toint PCG

**What we did:** Native preconditioner-norm boundary interpolation, boundary handling at curvature cutoffs, and removal of the persistent floor in that arm. Numerical checks passed.

**Finding:** Two tight Final394 targets improve by approximately **1.18× and 1.22×**, but four practical cells regress and Final3068 hits fall **4/5 → 0/5**. Reduced PCG work does not guarantee a useful outer step.

**Limits:** This changes radius-metric semantics and curvature handling together. It does not refute all Steihaug methods or isolate which ingredient causes the loss. The optional quadratic-progress stopping rule overlapped previously tested, explicitly excluded work and was omitted.

**Feedback:** If revisiting, isolate metric changes from boundary truncation and floor policy. A mixed-storage cutoff is not automatically genuine negative curvature worth following.

### Brief 4 — Gram-consistent operator and nonnegative curvature

**What we did:** Reproduced the ill-conditioned two-view rounding mechanism on 3000 synthetic cases and checked the consistent-Jacobian identity.

**Finding:** Separately rounded FP32 cross blocks produce negative minimum Schur eigenvalues in **3000/3000** cases; consistent-Jacobian energy forms do so in **0/3000**. This is a deliberately constructed numerical stress test, not the frequency of the event on BAL.

**Important correction:** For an approximate point solve, with `e = s - V_lambda u`, the actual operator energy contains an additional **`uᵀe`** term. Replacing only the CG denominator by a nonnegative sum can hide inconsistency with the `Ap` used for residual updates. Intrinsic regularization must also appear consistently.

The main practical targets see no numerical repairs. Removing those repairs therefore cannot explain a practical speed improvement there. Coherent FP64 paths were implemented in the reference and accurate-opening experiments; an always-on consistent-FP32 bandwidth improvement remains unmeasured.

**Feedback:** Preserve the consistent product, point solve, RHS, and curvature together. Treat nonnegativity as an algebraic property, not a standalone backward-stability proof for the whole solver.

### Brief 5 — Front-loaded accuracy and trajectory racing

**What we did:** Twenty repeated baseline trajectories each on Ladybug1197 and Final3068; a separate native accurate-opening arm; an independent Venice confirmation; then a clipping-only attribution experiment.

**Predictor result:** Outer-5 cost versus final-cost Spearman correlations are approximately **−0.050 and +0.202**. The registered cheap log-derived alternatives also fail the split-sample gate. No racing controller was implemented. These results concern repeated-config stochastic trajectories, not every possible structured perturbation or geometric predictor.

**Positive result:** For the first three accepted outers, combine `eta=0.05`, coherent FP64 operator/RHS/point completion, and rejection of oversized raw steps instead of radial clipping. Venice improves **0/5 → 5/5**, independently repeats **0/5 → 5/5**, and therefore totals **0/10 → 10/10 observed**. On-arm median crossing is **0.37605s**, range **0.3730–0.4288s**.

**Counterexamples:** Seven practical cells slow, worst **2.33×**; Final3068 hits fall **2/5 → 0/5**. The accurate-opening implementation retains normal assembly before its coherent workspace, so its overhead is real and included.

**Attribution:** The full arm can be **23.64% worse after three accepts** yet finish better on Venice. Clipping alone does not reproduce the improvement. The useful interaction among linear accuracy, storage consistency, and controller trajectory remains unresolved.

**Feedback:** This is the strongest remaining experimental lead. Isolate opening forcing next, retaining ordinary storage and the original clipping rule, before claiming a mechanism or optimizing the combined implementation. Do not use lower early cost alone to select the winning trajectory.

### Brief 6 — PI radius control

**What we did:** One preregistered PI rule with epsilon 0.3, integral/proportional exponents 0.3/0.4, accepted-step history, and the existing rejection logic.

**Finding:** Four small practical timing wins, one loss, four overlapping cells. Those practical traces do not contain the hypothesized storms. On the actual tail cases rejection ranges overlap, and Venice median endpoint is **12.29% worse**. The measured intervention does not meet its storm-reduction objective.

**Feedback:** Accept/reject alternation alone does not establish a controller limit cycle. This is a negative result for one PI/LM combination, not for control-theoretic optimization generally.

### Brief 7 — ARC using shifted solves

**Mathematical correction:** Under Eta2's coupled point damping, both the reduced Schur matrix and reduced RHS depend nontrivially on lambda. They are not a scalar-shift family. The proposed free Schur multishift root-finder is invalid as stated.

**What we did instead:** A valid fixed-metric full-normal method with a fresh 64-vector Krylov basis and an accurately solved projected cubic root; matched projected-LM control at three Venice witnesses, N=3.

**Finding:** Cubic and matched LM proposals are almost identical, with no 20% gain wins. Full stationarity residuals are still approximately **77%, 3.51%, and 2.85%**; an accurate projected secular root is not an accurate full-space solve.

**Limits:** No native ARC grid and no nine-cell ARC-versus-PI comparison. This is a negative bounded projected experiment, not a universal ARC verdict.

**Feedback:** State which full or reduced metric has genuine shift structure, include the damping-dependent RHS, and charge the work needed to make that structure valid.

### Brief 8 — Point-only residual-Hessian correction

**What we did:** A 54-row conditional point-backsubstitution screen with an analytic residual Hessian and guarded point blocks.

**Finding:** One two-observation point explains **99.9957%** of a Ladybug cost explosion. Its corrected block is SPD, world movement is modest, and both depth signs remain unchanged. One camera depth nevertheless approaches zero, causing a projection blow-up.

**Limits:** This does not refute a fully coupled partial-Newton implementation. The tested conditional correction fails its usefulness gate.

**Feedback:** SPD, bounded Euclidean movement, and unchanged cheirality do not protect against approaching a projection horizon. Any revised local model needs to address that directly.

### Brief 9 — Nonlinear coarse correction and stopping oracle

**What we did:** An initial oracle with an additional same-fine-radius constraint; then the actual independently globalized passenger-cluster problem; then native continuation.

**Finding:** The extra-radius oracle failed, but the brief's original zero-decrement kill did **not**. We therefore continued rather than declaring the whole proposal refuted. The passenger model passes the three-witness mechanism gate in **2/3** cases, with gains **54.18× and 32.26×** the tiny captured Eta2 decreases. The largest full-cost gain is only **0.0443%**.

Native continuation accepts all three coarse steps in every eligible episode—five Venice misses and one Final miss—but rescues **no target miss**. Controller history remains intact. Geometric clustering largely isolates camera outliers, which limits the distributed-mode interpretation.

**Feedback:** A large gain relative to a nearly zero baseline step can still be too small to matter. The descent mechanism survives implementation; its convergence benefit does not pass this protocol. A balanced graph passenger model remains distinct and untested.

### Brief 10 — Camera keep/move and per-track line search

**What we did:** Twenty-seven conditional rows on the three Final stop witnesses, reconstructing the existing point safeguard before adding fractional or camera choices.

**Finding:** All three baseline proposals already pass acceptance after the existing safeguard. There is no rejected baseline opportunity in this witness set. Fractional point moves provide small additional decrease; camera selection leaves all cameras moved.

**Feedback:** The opportunity denominator matters. This screen does not justify a general no-benefit claim for separable rescue. A new test would first need independently identified, genuinely rejected proposals remaining after the champion's current rescue.

### Brief 11 — Soft-mode kicks

**What we did:** One deterministic terminal kick along a coarse generalized Ritz mode, orthogonal to camera-space similarity directions in the coarse-PCG metric; bounded predicted/true temporary cost increase; continuation with existing controller history and protection of the better pre-kick state.

**Finding:** All **seven eligible kicks** are admitted; none rescues a target miss. Venice remains **0/5**, Final3068 **3/5**, matching their controls. A lower Venice on-cohort endpoint is mostly explained by a difference already present before the kicks, so it is not claimed as a causal basin-hopping win.

**Limits:** The camera-space projection is not a certified full-joint gauge removal, nor are coarse modes necessarily the true lowest modes of the complete operator. We did not rerun the historical Eta2→MFREE portfolio comparison because this arm produced no target rescue.

**Feedback:** Keep perturbation admission, post-kick descent, and target rescue as separate outcomes. Only the last supports the claimed reliability benefit.

### Brief 12 — Two-stage Rosenbrock step

**What we did:** A 27-row coherent CPU witness study with verified order, fixed-chart gradient transport, dense-normal agreement, and full residual checks.

**Finding:** Against two successive LM steps, gain per work wins on **1/3** witnesses and loses on **2/3** with disjoint ranges. Against one LM step, there is no disjoint win. One second-stage proposal has negative prediction and negative true decrease: their ratio is positive, but the full acceptance test correctly rejects it.

**Feedback:** Reusing a factorization is insufficient if the second solve fails to buy enough useful decrease. The present result does not justify a native implementation or a claim that accurate gradient-flow integration improves BA optimization.

## Subsequent proposal — Static long-track damping

The later proposal was to apply multipliers **1 / 1 / 0.3** to tracks with **2 / 3–5 / 6+ observations**, based on the other solver's offline evidence analysis. Eta2 indeed applies a uniform relative point factor: `tau_eff = lambda`, multiplying the guarded point-block diagonal.

We implemented the exact global rule on every attempt, including retries. It adds CSR-offset reads and one multiplication inside the existing factor kernel, without an extra solve or kernel launch. The new point factors feed the Schur product, reduced RHS, scaling, and back-substitution consistently. No feedback law, alternative dose, accurate-opening combination, or stopping change was introduced.

The actual GPU factor test agrees with the intended augmented blocks to **8.68e-16** relative error; shorter-track factors remain bit-identical. Native toy, memory, and original-versus-derived-off compatibility checks pass.

| Scene | Target hits, off → on | Conditional median target time, off → on | Median endpoint change |
|---|---:|---|---:|
| Final3068 | 4/5 → 4/5 | 3.1911s → 2.0249s | +0.053% |
| Venice52 | 0/5 → 0/5 | Neither reaches target | **+6.134% worse** |

Final's observed timing ranges overlap, and the successful subsets differ. The lower conditional median is tentative, not an established speedup. Neither scene improves its observed hit count. The preregistered extension gate fails, so we stop this dose before the larger panel.

The multiplier affects 26.85% of Venice points but 63.35% of its observations. All five stratified Venice runs stop after 71 outers, with two rejects and zero curvature repairs, near cost **261514** instead of the control median **246399**. Their terminal raw/clipped camera-step ratio is approximately **425**, versus a control median **1.96**. Cost worsens in all three track classes in every pair, including the short tracks whose damping was unchanged.

The static rule transfers cleanly as an implementation but does not retain its benefit in Eta2 under this protocol. Lowering point damping changes both the camera Schur matrix and RHS; its nonlinear effect is not independent of the solver's trajectory merely because its inputs are problem statistics. This does not dispute the supplied MFREE findings, which we did not independently reproduce.

## What to revise in the next set of suggestions

1. **Prioritize attribution of the confirmed opening benefit.** A forcing-only arm with ordinary storage and original clipping is a concrete next test. Keep the losing practical cells and Final3068 in any promotion gate. This experiment has not yet been run.
2. **Separate spectral coverage from useful paid correction.** The next graph/coarse proposal should pass a nonlinear witness test at the actual admissible step before paying for a new native preconditioner. Include absolute missing-direction magnitude and setup amortization.
3. **Address projection horizons explicitly.** Homogeneous angular bounds, point-block SPD, small world displacement, and preserved depth signs are individually insufficient in the tested examples.
4. **Retain the coherent-operator opportunity with realistic scope.** A consistent-FP32 production implementation may still offer a bandwidth opportunity, but neither a denominator-only fix nor absence of practical curvature repairs establishes that win.
5. **Treat rejected-step rescue as an opportunity-specific intervention.** Some proposed witnesses already pass the champion's rescue. Some terminal corrections descend but cannot bridge the remaining target gap. Identify the intended opportunity before implementing another controller.
6. **Do not resume already excluded families under new terminology.** Learned components, outer acceleration, cross-attempt/outer Krylov reuse, controller-state restoration, periodic retriangulation, marginal-value stopping, span minimization, and multishift candidate generation remain excluded.

These are proposed follow-ups, not additional completed experiments or promised improvements. A narrower improvement with clear attribution would be more useful than another combined configuration with a favorable isolated scene.

## Novelty boundary

The building blocks have direct prior art. The review found multiscale similarity-mode BA preconditioning in Byröd–Åström, seven-mode aggregation/multigrid BA in Konolige–Brown, and explicit BA deflation/two-grid work. Homogeneous and inverse-depth charts, Steihaug CG, and Krylov cubic regularization are also established.

The completed work does not support claims of first coarse-grid BA, first rigid-mode BA, first use of these charts, or a new universally fastest solver. Its strongest assets are the measured failure mechanisms, matched implementations, and the reproducible opening-trajectory result. A successful new configuration still needs an appropriate novelty search and a broader external comparison before publication claims.

## Files, commits, and reproducibility

The handoff is self-contained; the following pinned repository links provide details if the receiving agent has access:

- [Main full report, all 13 briefs, commit 59cabf1](https://github.com/msouiai/prism-ba/blob/59cabf1/research/eta2_research_20260912/REPORT.md)
- [Main campaign index, code links, and figures](https://github.com/msouiai/prism-ba/blob/59cabf1/research/eta2_research_20260912/README.md)
- [Mathematical and primary-source prior-art audit](https://github.com/msouiai/prism-ba/blob/59cabf1/research/eta2_research_20260912/literature/MATH_AND_PRIOR_ART.md)
- [Verification of all 548 main native rows](https://github.com/msouiai/prism-ba/blob/59cabf1/research/eta2_research_20260912/FINAL_VERIFICATION.json)
- [Static track-damping implementation, report, and figures, commit 056f689](https://github.com/msouiai/prism-ba/blob/056f689/research/eta2_track_damping/README.md)
- [Track-damping measured table](https://github.com/msouiai/prism-ba/blob/056f689/research/eta2_track_damping/RESULTS.md)

Main branch: `research/eta2-diagnostic-agenda`. Later transfer branch: `research/eta2-track-damping`, with protocol registration in `dc3364b` and completed results in `056f689`.

Source, protocols, manifests, compact raw results, traces, and figures are pushed. Large endpoint containers and lossless archives are local artifacts; their numerical hashes and restoration records are versioned. They are not all downloadable from GitHub. Legacy `stop_ftol` fields record message presence and must not be interpreted as certified final-stop reasons after an intercepted terminal stop. No raw endpoint or witness was silently discarded from the scored research grids.
