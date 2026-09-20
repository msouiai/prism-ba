# Thirty math-led steps: point damping and full-model prediction

Completed 2026-09-07. **The useful result is a corrected model prediction, with promising single-shift gains on two medium scenes. The proposed point-damping feedback failed. Neither result establishes a general multi-shift advantage.** Defaults remain unchanged.

Derivations: [point damping and full-model mathematics](point_trust_math.md). Local evidence, frozen binaries, plans, CSV traces, exported states and CPU audits: `/workspace/prism-point-trust/`. This round contains 31 BA runs, 103.684 seconds of native solver time, 18 target runs and 12 hits. Failures are retained. Maximum independent exported-state relative objective discrepancy: `6.55e-12`.

## What the mathematics changed

1. With separate camera and point damping, increasing camera lambda without bound leaves the point-only relaxation nonzero. A larger camera-lambda menu therefore does not necessarily shrink the full step enough to make it acceptable.
2. Uniformly shrinking a step is generally not equivalent to changing one damping scalar. The required scalar depends on the active eigenvalues.
3. A conditional point trust-region root can be computed cheaply and accurately, but its guarantee holds with the camera forcing fixed. Re-solving the coupled system, changing the camera metric or moving to the next nonlinear state breaks that guarantee. Explicit dense counterexamples demonstrate this gap.
4. The rho controller needs the full, unregularized GN prediction for the actual step: `-rᵀJd - 0.5||Jd||²`. A reduced, regularized prediction with an eliminated-point constant is generally a different quantity. Mixed camera/point scaling also changes the cross term. Direct evaluation avoids reliance on exact CG solves or a damping-energy shortcut.

The standard LM context is described in [Ceres' documentation](https://ceres-solver.readthedocs.io/latest/nnls_solving.html) and §3.2 of [Madsen, Nielsen and Tingleff (2004)](https://www2.imm.dtu.dk/pubdb/edoc/imm3215.pdf). The block derivations and counterexamples here are independently checked; no novelty claim is made for standard trust-region or model-reduction formulas.

## Rejected experiment: carry conditional point damping to the next state

Three arms were frozen before timing: original paired-demand baseline, Rayleigh feedback and a bounded scalar-root feedback. All used the original finite backtracking schedule, FP64, unshared 9-parameter cameras, L2, compact fragments 2 and paired demand mode 2. After an accepted backtracked rescue, feedback used the accepted alpha to initialize the next point damping. This transfer was explicitly a heuristic, not an exact full BA trust-region solve.

The root uses at most 12 bisections, with spectral brackets derived from the implemented metric. It needs only a 24-byte persistent scalar buffer. Changing point damping invalidates the cached point factor; the associated Schur system/RHS must change. The accepted rescue scale is saved and restored with narrow/wide fallback.

| Scene and evaluation | Original | Rayleigh feedback | Root feedback |
|---|---:|---:|---:|
| Ladybug-49, cost after 40 iterations | 13,568.691 | 13,568.690 | 13,568.692 |
| Venice-52, cost after 40 iterations | 253,515.039 | 248,683.110 | 248,457.857 |
| Dubrovnik-356, time to cost ≤754,100 | **6.887 s** | Miss at 12 s | Miss at 12 s |
| Dubrovnik-356, returned cost | 754,099.118 | 1,209,277.261 | 1,202,756.206 |
| Ladybug-1197, time to cost ≤366,600 | **2.160 s** | Miss at 6 s | Miss at 6 s |
| Ladybug-1197, returned cost | 366,571.319 | 366,889.075 | 366,616.208 |

Each screen cell is one run. Ladybug-49 had no rescue updates, so its timing variation cannot establish a feedback benefit. Venice improved locally, but both medium equal-quality targets failed for both feedback arms. The near miss on Ladybug does not redeem the large Dubrovnik regression.

Diagnostic-only root evaluation satisfied the requested conditional contraction in all 21 valid rescue proposals. Rayleigh's achieved contraction divided by the requested alpha had median 2.719 on Dubrovnik and 0.520 on Venice: the approximation errs in opposite directions. The root therefore fixes the conditional calculation, but not the transfer to a new coupled BA state.

On Dubrovnik, the active root arm spent only 0.110 of its 12.032 seconds in its 159 norm kernels, yet ended far above the target. Its failure is mainly the optimization trajectory, not bisection overhead. It performed 16 damping updates; the Rayleigh arm performed 18. Reducing backtracking work did not compensate for the poorer trajectory.

A held-out Trafalgar-126 40-iteration check used two baseline/root pairs in reversed order. None activated feedback. Median costs were 104,180.626 and 104,167.378, respectively. This is an inactive control, **not independent confirmation of the active failure**. The original large-run gate failed, so no large run was launched and no additional feedback factors were tuned.

## Amended experiment: direct full-GN prediction

After the medium failures, `amendment.json` redirected the remaining implementation/ablation steps to the independently derived prediction discrepancy. `OCA_FULL_MODEL_RHO=1` computes the actual step's full GN prediction before retraction and substitutes it into the existing accepted-step Nielsen camera-damping update. Other behavior remains: relative-gain overrides, pre-rejection lambda rebasing, and freezing lambda after a rescued step. This is not textbook LM replacing the whole controller.

The test uses **fixed-menu mode**, because paired-demand mode subsequently controls the damping pair and would overwrite this update. It compares one and five shifts, with point feedback off, original backtracking and otherwise matching flags. Thus the following baseline is different from the paired-demand baseline above; the tables must not be combined into an attribution claim.

| Scene | Shifts | Original prediction | Direct full prediction | Equal-quality speedup |
|---|---:|---:|---:|---:|
| Dubrovnik-356, target 754,100 | 1 | 4.730 s | **1.430 s** | **3.31×** |
| Ladybug-1197, target 366,600 | 1 | 3.137 s | **2.605 s** | **1.20×** |
| Dubrovnik-356, target 754,100 | 5 | 1.618 s | 1.646 s | 0.983×; essentially tied |
| Ladybug-1197, target 366,600 | 5 | Miss at 6 s | Miss at 6 s | Undefined |

Single-shift rows are medians of two runs per arm, with the second comparison reversing execution order. Every single-shift run hit its target. Five-shift rows are one run per arm. Time means the native clock at the first qualifying accepted state, including initialization and the added prediction work, before cleanup. Iteration-boundary budgets can overshoot slightly; late/missing crossings are misses.

For single-shift Dubrovnik, median matvecs fell from 609 to 147 and scored candidates from 558.5 to 147. For Ladybug, matvecs fell from 1,686.5 to 1,273.5 and scores from 321 to 273. These runs had zero rejected attempts in both arms: the improvement is trajectory/work reduction, not a measured retry reduction.

For five-shift Ladybug, rejected attempts fell from 33 to 22, but final cost worsened from 367,005.792 to 367,823.284. This again shows why rejection counts alone cannot select a solver. Five-shift Dubrovnik's 1.7% timing regression is too small, with one run, to treat as a meaningful failure.

The direct pass costs a median 0.152 seconds on single-shift Dubrovnik and 0.117 seconds on Ladybug, included in the totals. It has only a 16-byte persistent reduction buffer, but streams the observation Jacobians and is not free.

On the first corrected single-shift trajectories, the median direct/old prediction ratio, restricting to positive old predictions, was 24.35 on Dubrovnik and 3.43 on Ladybug. Some old predictions were nonpositive; they are explicitly excluded from these ratios in `summary.json`. These are diagnostics along corrected trajectories, not matched-step distributions across baseline runs. No direct predictions were nonpositive in the tested cells.

**Selection:** reject the next-state conditional point feedback. Keep direct full prediction as an opt-in candidate for further validation. Its best fixed-menu single-shift Dubrovnik time also beats this round's fixed-five baseline, but its Ladybug time does not beat the separate paired-demand baseline. Two medium scenes and two repeats do not justify a universal default change, large-scene conclusion, Caspar comparison or publication claim.

## Checks and reproducibility

- 200 dense block systems: full-model identity maximum relative error `1.91e-14`; all conditional monotonicity/bracket checks pass.
- 500 coupled counterexample systems: conditional roots violated the coupled contraction in 2 cases with a fixed camera metric and 5 with camera re-equilibration. Worst re-equilibrated contraction was 0.315 for a requested 0.125. Seeds and the worst system are retained.
- Point GPU test: 12 tau/alpha combinations, 259 points, partial blocks, anisotropy, rank deficiency, zero blocks/steps and invalid/capped requests; root agrees with independent CPU bisection to better than 1%. Maximum normalized contraction discrepancy `8.89e-16`.
- Full-model GPU test: 12 independent CPU finite-difference cases covering k2 masking and independently scaled/zero camera and point halves; maximum normalized discrepancy `3.81e-10`.
- Both GPU tests: Compute Sanitizer zero errors. CLI and core library build successfully. Eigen is optional for these tests, not a CLI/core dependency.
- Unsupported unsplit point feedback and paired-demand full-model prediction fail explicitly. Every BA run passes an independent exported-state CPU objective check, monotonic accepted-cost check and bounded backtracking accounting check.
- Source/binary/data hashes, commands and flags are retained per run; final artifact hashes are in `provenance.json`. Point study uses frozen `prism-v1`; prediction ablation uses frozen `prism-v2`. The latter includes a source-only preservation of off-path rho behavior after the unit kernel test; the tested prediction kernel is identical to the frozen benchmark kernel.
- All 11 original broad-queue processes remain paused, verified by PID and process start time. No new large scene, broad queue restart or GitHub publication was performed.

Reproduce the host math and summarize retained runs:

```sh
python3 bench/point_trust_math.py
python3 bench/point_trust_coupling_gap.py
python3 bench/summarize_point_trust.py /workspace/prism-point-trust
```

Build the optional GPU tests through the existing GPU CMake project with Eigen installed, using targets `test_point_trust` and `test_full_step_model`. Stage plans can be passed to `bench/backtrack_investigation.py`; it skips completed results and refuses to overwrite incomplete logged runs. For a fresh replication, copy the desired plan to a new output root and update its binary path. Data paths are the local BAL scene files under `/workspace/bal/`.

## Thirty-step ledger

| Steps | Completed work |
|---|---|
| 1–5 | Primary LM references; block/Schur derivation; camera-damping limit; actual metric floors; full/reduced prediction identity. |
| 6–10 | Scaling counterexample; conditional trust-region formulation; monotone root/brackets; Rayleigh approximation; dense checks. |
| 11–15 | GPU metrics/root; independent CPU comparison; numerical edge cases; memory checks. |
| 16–20 | Opt-in feedback and fallback-alpha integration; BA diagnostics; approximation/overhead measurements; cache/compatibility review; frozen screen. |
| 21–25 | Small inactive and contradictory cases; both medium targets; explicit rejection of both feedback candidates. |
| 26 | Held-out small control, recorded as inactive rather than evidence of an active mechanism. |
| 27–28 | Gate prevented a large run. Recorded amendment: direct full-model implementation/validation, single/five factorial, reversed-order single-shift confirmation. |
| 29–30 | CPU/provenance/budget/build audits, paused queue verification, derivation and complete results report. |

## Next mathematical step

First validate the corrected prediction on one predeclared larger scene against both the best existing fixed-menu and paired-demand controls. Then optimize its extra pass only if the quality benefit transfers: accumulate the required `rᵀJd` and `||Jd||²` where the actual candidate's observation-direction products are already available, retaining the independent direct implementation as an oracle.

For multi-shift specifically, derive candidate selection and damping updates from the same full-space model/metric before adding another policy. If point damping must change, account explicitly for the changed Schur operator and RHS. The conditional counterexample rules out treating a point-only norm root as a universally valid coupled radius update. A fully coupled trust-region method needs either coupled norm evaluations or a proved approximation bound; the cheap conditional feedback tested here supplies neither.
