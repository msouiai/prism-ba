# Independent post-screen feedback

11 September 2026. Reviewed the three summary files, raw JSON/logs, protocols, A1 checkpoint/intervention code, A2 retraction/runner/algebra checks, and A3 selection/reused PCG kernels. Performed read-only aggregation of existing records and normalization vectors. No benchmarks or implementation edits were performed.

**Recommendation: close all three promotion branches after the pending algebra/artifact checks.** No result justifies a new controller, native full-scene expansion, additional chart tuning, or a larger basis search. The negative conclusions should remain specific to the tested schedules, paths, retained spaces and convergence targets.

## A1: the intended late-stage question was tested

The saved fine lambda is resumed, accepted states invalidate the Jacobian, and no-op continuation reproduces the baseline endpoint and fine-step count. The coarse stages were active: all 216 actual interventions reduced their parent cost, with no recorded intervention failure. Every resumed tail has zero rejected fine steps; none saves an accepted fine step. This supports the practical conclusion that these interventions precede the same useful fine computation rather than replacing it.

Correct the run count in prose: there are **270 resumed runs = 216 coarse interventions + 54 continuation controls**, plus the six baseline trajectories. Calling all 270 “coarse splices” overstates the intervention count.

The reported full time is composed from one measured common baseline prefix and three repetitions of each tail. Call this “composed full time” or “shared-prefix time-to-target,” not three independent uninterrupted end-to-end timings. Tail ratios and unchanged work counts support the verdict independently. A cap reset on resumption is immaterial here because the recorded full times are far below the three-second cap.

The screen uses the earlier 24-camera/300-point samples. It does not establish a result for the later all-camera/1,200-point samples, full BAL, or GPU Eta2. Reusing these real scene families is appropriately development evidence. The proposed new synthetic positive controls were not part of the registered execution protocol; disclose that coverage difference rather than implying they ran. Existing invariance validation and the observed active cost decreases make another positive-control benchmark unnecessary for this narrow stop decision.

No decrement trigger is justified: even hindsight choice among these insertion times and budgets loses. This is not a mathematical upper bound over all possible partitions, schedules or submap algorithms.

## A2: correct path comparison; known geometry explains the useful result

The source implements the proposed first-order-matched projective retraction, refreshes chart vectors only after accepted changes, uses the original Euclidean prediction and fine damping rule, preserves the point0 gauge, and evaluates the complete original objective. The existing checks verify the fixed-camera pinhole identity, explicit anchored chart equivalence, tangent agreement, exact XYZ baseline, immutability and pole fallback. I found no source-level mismatch that invalidates this comparison.

The intended low-parallax speed gate fails. The moderate-parallax gain is real screening evidence for a different finite point path, but mean-view ties the anchored inverse-depth control. Consequently it supplies no measured incremental value for the new chart-selection rule. A modest work-count reduction is more persuasive than millisecond timing alone, but it still does not establish better reconstruction.

The geometry summary needs component-specific interpretation. At one endpoint per seed, all ten low-parallax cases fail both point and camera NRMSE thresholds for every arm. In the moderate cohort, **no case exceeds point NRMSE 0.2; all ten fail the camera threshold**. Rotation has eight camera failures for XYZ versus six for either projective path, with one point failure per arm. Repetitions of a deterministic endpoint are timing repetitions, not independent geometry trials.

The fixed cost targets differ substantially in strictness relative to the generating-state feasible cost. Read-only target/reference ratios are:

| Family | Minimum | Median | Maximum |
|---|---:|---:|---:|
| Low parallax | 1.10 | 1.24 | 1.55 |
| Moderate parallax | 2.49 | 4.69 | 9.47 |
| Rotation | 4.72 | 17.58 | 47.18 |

Thus target hits cannot be called recovery, convergence to the noise floor, stationary minima, or evidence that the final geometry is irrecoverable. The globally aligned endpoint errors are valid at the tested stopping point. No additional terminal solve is needed to close the speed/novelty branch; deeper refinement would answer a separately registered geometry question.

The generator's mostly aligned camera axes also limit how differently the two chart choices can behave. This is a coverage limitation, not a reason to retune the failed screen. A new diverse-view generator would be a new research experiment, not a corrective rerun required by these results.

## A3: selection improved one comparator, but did not remove the bottleneck

Current generalized selection uses the actual post-safeguard factor M=LL^T, current S and b, and a fixed balanced preconditioner. I checked the reused factor kernel: it writes a zero-filled lower-triangular L, so the host multiplication L(L^T V) constructs the intended metric. Current solves share the same fresh true-residual threshold. Full-basis refresh of all 32 columns is honestly included in setup.

The decisive observation is that energy rank4 still takes approximately 158.6 ms / 49 CG **after excluding all setup**, versus plain approximately 131.8 ms / 41 CG. Faster basis construction alone cannot rescue this fixed basis and PCG path. The 49-versus-53 improvement over alternative recycled selectors is not a reason to reopen a method which remains slower than plain PCG.

The mode logs reinforce the limited interpretation: rank2 already captures about 99.97% of the quadratic decrement available *inside the retained 32-dimensional space*. That percentage is not a fraction of full-system error and does not imply a favorable current residual trajectory under the loose Euclidean residual stopping rule. The purported oracle is an expensive current-system selection diagnostic, not an optimal basis or an upper bound on achievable PCG speed.

One additional coordinate-scope caveat should be retained. The predecessor basis is stored in normalized camera coordinates and reused directly. Preservation of a physical tangent across a changed diagonal normalization would require V_current=diag(E_previous/E_current)V_previous, in addition to any applicable pose-chart transport. The current implementation does not do this. It remains a valid current-system preconditioner because SZ/K are freshly computed, but it tests untransported normalized history. The read-only normalization ratio range is 0.98555–1.01197 on Muell and 0.66995–1.43544 on Ladybug; Ladybug's gate skips. These sizes do not establish that transport would be irrelevant, nor do they justify another benchmark by themselves.

All three matrices are previous development captures, and only Muell exercises the active selector. Predecessor history acquisition is separate and comes from a capped unsuccessful 128-iteration solve; that fact is disclosed. The result is not a full nonlinear solver comparison or a fresh Eta2-versus-Caspar measurement.

## What remains before closing

Finish the already planned algebra/artifact checks, preserve the count/timing/coordinate limitations above, and report no promotion. A compact diagnostic of saved data is sufficient; no additional timed run is requested. In particular, do not rescue the agenda by choosing a new chart family after seeing the moderate result or by advertising a cheap four-column implementation of a selector that refreshed 32 columns.

The strongest retained findings are explanatory: late cost reduction need not save later fine work; inexpensive inverse-depth paths can improve one target regime without a new selector advantage; and large projected decrement capture can coexist with slower residual convergence. These are useful restrictions on the next genuinely different hypothesis.
