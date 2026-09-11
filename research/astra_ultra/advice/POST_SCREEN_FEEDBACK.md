# Independent feedback as screens complete

11 September 2026. This is a read-only advisory review of the parent's experiments. The adviser did not implement solver code or run benchmarks. Prospective constructions and their prior-art boundaries remain in [RESEARCH_DIRECTIONS.md](RESEARCH_DIRECTIONS.md); the parent's frozen protocols govern the actual screens.

## U1: a useful conditional mechanism, no promotion

Reviewed ray_protocol.md, path_summary.json, joint_paths.py, path_solver.py and check_joint_paths.py. The source uses the intended virtual pixels, actual finite trial cameras, centered per-point solve and original point damping metric. It keeps point0 on XYZ, evaluates the original objective and preserves the ordinary tangent prediction for the retractions. The moving-host construction reduces to the preceding anchored rule for a stationary host. The observed-pixel polish control is appropriately labeled non-tangent-matched, with its actual point displacement used for the GN prediction.

The reported screen has 180 runs: 12 independently generated cases, five arms and three timing repeats. Every run reached the primary target, which is 1.01 times a separately frozen feasible reference. Only four independent cases represent each family.

| Family | Virtual-ray speed vs XYZ | Relevant interpretation |
|---|---:|---|
| Depth | 1.017x | Previous anchored control is faster. |
| Joint pose | 0.798x | Same median fine accepted count; added local work is not repaid. |
| Low parallax | 1.315x | Substantive work reduction, but observed-pixel polishing is stronger. |

In the low-parallax family the virtual path reduces median accepted/rejected counts from 29/3 to 17.5/0. This is useful evidence that a finite point construction incorporating trial camera motion can replace fine work on these cases. It differs from the preceding point-only path's failure to help the earlier low-parallax cohort.

However, observed-pixel polishing reaches 1.424x ordinary speed, with 13.5 accepted and 0.5 rejected steps. The direct paired comparison is 0.923x virtual-ray speed relative to polishing. Its lower median point/camera/rotation errors also favor polishing. Moving-host median geometry is better than virtual-ray on this family, despite its smaller timing benefit. Therefore better multi-view model targeting has not supplied a new best practical update.

The original registered requirement—at least 1.10x over XYZ and both anchored controls in at least two families—fails. No deeper-target, additional-seed, BAL-transfer or native expansion follows from this screen. Do not introduce a new ray weight, a lambda multiplier, an alpha search, a host selector or a family controller after seeing these outcomes. Such choices would be new experiments and the strongest existing point-polishing control would remain necessary.

Small target-relative cost is still not a geometry certificate. In low parallax the median camera NRMSE is approximately 0.449 for XYZ, 0.233 for virtual rays and 0.136 for polishing. The new tighter objective contract makes the optimization comparison clearer, but it cannot make weak geometric information strong. Retain the continuous geometry results and per-case failures rather than interpreting all target hits as accurate reconstructions.

**Advisory decision:** close U1 under the registered gate; retain the finite-ray tangent identity and the conditional low-parallax work reduction as explanatory findings. Keep Eta2 unchanged.

## U2: source decomposition verified; the deployment cohort gate fails

Reviewed stiffness_protocol.md, stiffness.py, run_stiffness_diagnostic.py and all 36 saved parent records. The implementation has the correct sign in the perspective residual Hessian, includes the separate rotation–point term in the directional decomposition, and assembles the positive factor without modifying the original gradient or damping metric. Gauge-masked rows are used for the D-whitened trace control. The primary prediction remains the original GN prediction.

The decomposition's largest recorded relative error is approximately 6.89e-15, and the analytic positive factor agrees with dense eigendecomposition to 7.80e-16. Finite differences were tested at the 12 initial states, across five step sizes; the worst of those states' best-scale relative errors is 8.58e-8. This supports the pinhole formulas. Finite differences were not repeated at every later parent; analytic decomposition/factor checks cover all 36.

Only depth-500 and depth-503 at their initial states satisfy the registered severe-positive-excess condition. Their perspective fractions are approximately 0.975 and 0.993, so the median 0.984 clears the contribution threshold. The required prevalence and family coverage do not: there are two qualifying parents instead of four, all in one family instead of two. Thus the gate correctly returns false.

This result does **not** say perspective stiffness is absent. It dominates the omitted curvature in these two severe directions. It says the proposed intervention did not find the registered breadth of relevant difficult parents. In the diagnostic candidate comparisons, stiffness improves the trial cost relative to ordinary at both severe parents; it beats trace-matched depth damping in one and loses in the other. Across all 36 one-step comparisons, ordinary has the lowest cost on 25, trace-matched depth on nine, and stiffness on two. These are correlated parent-state observations and uncharged one-step outcomes, not solver-speed results.

No full stiffness trajectory or extra-damping sweep is required after this failed mechanism gate. No native radial/intrinsic claim follows from the pinhole identity. I found no source-level mismatch requiring a rerun.

**Advisory decision:** stop U2 at the signed-curvature/one-step diagnostic boundary. Preserve the exact factor and conditional source attribution; do not broaden the cohort or tune the severity criterion after seeing the result.

## U3: correct point credit, correct product accounting, ineffective cheap bound

Reviewed energy_protocol.md, energy_diagnostic.py, all 45 saved parent records and energy_summary.json. These are three ordinary states from each of 15 small CPU problems: 12 synthetic cases and three previously inspected BAL samples. The Schur operator, Hcc block preconditioner and PCG path are shared. This is neither native replay nor a timed complete BA comparison.

### Identities and stopping-rule implementation

The source correctly uses the point-damped C, camera-damped B and actual parent lambda in its Schur construction. The point0 gauge is removed consistently. The full physical damped-model decrease from the back-substituted step agrees with P0 plus camera gain; the maximum saved relative discrepancy is 1.91e-14. The exact remaining energy and achieved gain reconstruct the exact optimum to the asserted tolerance, and no positive bound violation is recorded.

For Nash stopping, camera gain is one half of x transpose (b plus r), so the Ceres quadratic Q equals minus twice that gain. Consequently the implemented condition k times (gain minus previous gain), divided by gain, below 0.1 is algebraically the condition in the [Ceres source](https://github.com/ceres-solver/ceres-solver/blob/master/internal/ceres/conjugate_gradients_solver.h). This compares the established stopping criterion inside the shared reference PCG; it is not a runtime comparison against the complete Ceres solver.

The fresh-residual accounting is also correct for these records. Each of the 315 rule/parent selections occurs before iteration ten and incurs one fresh exit check. There are no failed prospective checks. Therefore every recorded selected product count is exactly iteration count plus one. The code also accounts for periodic resets and failed exit checks, but those branches are not exercised in this dataset. The largest saved difference between recurrence and true relative residual is approximately 6.88e-15.

Per-iterate exact residuals, Schur factorizations, exact energy solves and dense spectral checks are diagnostic work, not free deployment operations. The report correctly avoids their use as a wall-time speed claim. Fresh validation at the hypothetical exit is included in each rule's product count.

### What the saved outcomes establish

| Rule | Total selected Schur products across 45 parents | Median products | Qualifying local opportunities |
|---|---:|---:|---:|
| Residual eta 0.5 | 114 | 2 | Baseline |
| Residual eta 0.8 | 96 | 2 | 7 |
| Nash camera quadratic | 191 | 4 | 0 |
| Exact energy, full point credit | 114 | 2 | 8 |
| Exact energy, camera credit only | 125 | 3 | 3 |
| Cheap bound, full point credit | 175 | 4 | 2 |
| Cheap bound, camera credit only | 201 | 4 | 0 |

The totals are descriptive work sums over this fixed parent set; they are not end-to-end timing predictions. The cheap full-credit rule has median paired product ratio 1.5 relative to eta0.5, even though the ratio of the separate product medians is 4/2. These are different summaries and should not be interchanged.

The offset affects decisions: adding P0 changes 11 exact-oracle stopping iterations and 19 cheap-bound stopping iterations relative to their respective no-P0 controls. Thus the mathematical credit is not an inert constant in these experiments. But its deployable benefit fails the gate. The cheap rule finds only two qualifying opportunities, depth-501 initial and Ladybug initial, rather than the required four. Both span the required depth/BAL categories and both change relative to no-P0, but insufficient qualifying count still closes the candidate.

In both favorable cheap-bound cases, eta0.8 selects the **same first PCG iterate**, with the same full step, true cost and charged products. Thus even these successes provide no incremental step-quality benefit over the simple control. All selected proposals have finite valid projections, positive cost decrease and rho above 0.1; no extra invalid proposal is hidden by the opportunity screen.

The exact full-credit oracle has eight local opportunities, yet its total selected product count equals eta0.5's 114. Do not describe those eight favorable parents as a demonstrated whole-cohort work improvement. Its lowest recorded full-decrement fraction is approximately 0.926, which satisfies the intended 0.909 guarantee. The cheap bound's lowest is approximately 0.977, consistent with conservative over-solving. None of these quadratic fractions certifies full nonlinear convergence speed or final geometry.

The summary's generic gate=true entries for eta0.8 and the expensive oracle do not trigger continuation under the registered protocol. Continuation is conditional on the cheap full-credit candidate passing; it does not. A local positive result for a known looser tolerance is not a new solver claim.

**Advisory decision:** stop U3 at the estimator gap. No tighter-bound search, Lanczos construction, new native capture, GPU port or complete trajectory expansion is justified by the registered candidate gate. I found no counting, Nash-sign or Schur-credit defect requiring another benchmark.

## Combined decision

Stopping now is consistent with all three registered gates. U1 has a conditional low-parallax work benefit but loses its general gate and strongest practical control. U2 verifies its mathematical stiffness factor but lacks the prescribed difficult cohort. U3 verifies the condensation offset but the inexpensive bound spends too much work and its two successes are matched by eta0.8. These results preserve useful mechanisms without supporting a production change or a novelty claim.

Parent clarification after final validation: depth and joint initialization families use the same generating geometry and observations for each seed. The 12 cases are four seeds in three stress families, with paired geometry across two families; they should not be treated as 12 unrelated datasets. The report states this dependence explicitly.
