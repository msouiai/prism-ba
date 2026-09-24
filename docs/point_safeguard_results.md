# Pointwise safeguard: online results, 2026-09-08

**A real, repeatable improvement on Dubrovnik356, but not a universal solution to multi-shift rejection.** Whole-track point selection makes fixed single-shift 3.84x faster and fixed five-shift 1.14x faster to the specified quality target. Paired demand becomes worse. A second, mathematically stronger local safeguard also fails on Dubrovnik. Keep both implementations experimental and off by default.

## Experiment

45 short BA runs, **184.280356 seconds of native solver time**, plus kernel/math checks and compilation. No large-scene run and no Caspar rerun. RTX2000 Ada 16GB, FP64 PRISM, unshared CD9 SIMPLE_RADIAL with k2 fixed to zero, existing compact fragments=2, original eight-probe backtracking and rearm, current optimized execution flags. Each main target cell has two repeats with reversed order. Ladybug1197 target 366600, cap6s; Dubrovnik356 target754100, cap8s. Targets were fixed before this round.

All 45 returned states passed independent CPU raw-objective audits; maximum relative discrepancy **4.95e-11**. Accepted cost traces are monotonic. Caps are checked by the native solver at its existing boundaries, so return times may slightly exceed them; a crossing after the cap is not counted as a hit. Kernel test timings and CPU audit time are excluded from the native BA total.

## Mode 1: full camera, point menu {old, full}

Median native time to the same target; hits shown where no time is reportable:

| Scene | Configuration | Original | Point safeguard | Original / safeguard |
|---|---|---:|---:|---:|
| Dubrovnik356 | Fixed single | 4.751s | **1.238s** | **3.84x** |
| Dubrovnik356 | Fixed five | 1.626s | **1.422s** | **1.14x** |
| Dubrovnik356 | Paired demand | 6.909s | Miss, 0/2 | — |
| Ladybug1197 | Fixed single | 2.733s | 3.021s | 0.90x |
| Ladybug1197 | Fixed five | Miss, 0/2 | Miss, 0/2 | — |
| Ladybug1197 | Paired demand | 2.763s | 2.542s | 1.09x |

All numeric time cells have 2/2 hits. Dubrovnik single safeguard crossings were 1.2391s and 1.2371s versus 4.7699s and 4.7312s. Five-shift crossings were 1.4171s and 1.4269s versus 1.6276s and 1.6238s. This is online time-to-quality evidence, unlike the preceding offline gain ratios.

The Ladybug single result is about 10.5% slower, with zero winning safeguard proposals in either repeat. Candidate overhead is only about 0.011s; changing floating-point reduction order can amplify into different trajectories. Ladybug paired has only three winning proposals across both repeats. These small-N timing differences do not establish robust benefits or attributable regressions. Fixed five still misses its target and the safeguard wins no proposals there.

### Where the work changed

| Dubrovnik configuration | Matvecs, original → safeguard (median) | Backtracking scores, original → safeguard | Safeguard overhead |
|---|---:|---:|---:|
| Fixed single | 612.5 → 174 | 382 → 20 | 0.049s |
| Fixed five | 377 → 330 | 8 → 8 | 0.016s |
| Paired demand | 799 → 823 | 839 → 488 | 0.891s |

Backtracking scores include the extra safeguard's full-cost evaluations. In fixed single, six new candidate evaluations are included in the 20 scores. Outer rejected iterations are **zero in both Dubrovnik baseline and safeguard arms**: the large single-shift gain is from fewer shortened-step iterations and fewer failed cost trials, not from eliminating previously nonzero outer rejection counts. The paired rows terminate at different qualities and therefore describe consumed work, not equal-quality speedups.

At the paired cap, mode1 cost is approximately 776119 versus target754100. It wins 108 of 109 attempted local comparisons in each repeat. Those are proposal wins, not necessarily108 committed outer updates: budget checks and demand competition can discard a proposal. All836 logged proposals across the round were checked against the printed mixed-slope Armijo and original-cost comparison;713 won their local comparison.

### Why paired demand regressed

After outer9, mode1 paired demand retains lambda=tau=0.01953125 through the remaining committed trajectory. Every such accepted step is classified as rescued, so the existing controller does not halve the damping pair. Its improved immediate gain also avoids the demand expansion criterion; there are zero expansions. The original trajectory has unrescued steps after that first rescue, reduces the pair, and begins expanding at outer17.

This is direct trace evidence of the controller interaction, not a proof that a particular alternate damping update will fix it. It explains why reducing failed scores or maximizing one-step decrease alone is inadequate. Persistent local repair can keep the solver in an unproductive damping regime.

## Mode 2: rescued camera, point menu {rescued, full}

This exploratory refinement fixes the camera position of the original uniform rescue and includes every original rescued point in the point menu. Its exact finite-menu optimum is therefore no worse than the original rescue at that same state. Full cost and mixed-slope acceptance checks remain mandatory.

| Scene | Configuration | Mode2 target time | Result |
|---|---|---:|---|
| Dubrovnik356 | Fixed single | Miss, 0/2 | Cost about 761186 at 8s |
| Dubrovnik356 | Paired demand | Miss, 0/2 | Cost about 761491 at 8s |
| Ladybug1197 | Fixed single | 3.077s | 2/2 hits |
| Ladybug1197 | Paired demand | 2.790s | 2/2 hits |

Fresh paired controls with the same v2 binary reached the targets in 6.911s and 2.832s respectively. Single controls come from the preceding v1 screen, so small differences across those cells are exploratory. Both large Dubrovnik failures remain unambiguous. Mode2 paired wins 122/122 proposals per repeat but fails the target; a stronger per-step objective guarantee still does not guarantee faster trajectories. No further variant or large test was launched.

## Small and prospective checks

Venice52 at 40 iterations: mode1 improves four of seven proposed rescues, including retaining the original when the proposed full-camera repair is worse. Its final cost 252177 is between the measured disabled-run outcomes, so there is no convincing quality win. Dubrovnik88 at 40 iterations makes no rescue calls and shows similar runtime/quality with the flag enabled. Prospective Trafalgar126 at 3s makes one safeguard call; costs 104078 and 104054 and times 3.035s and 3.041s are inconclusive. These capped/fixed-iteration endpoints are not time-to-equal-quality claims.

A strict opt-out trajectory comparison **failed** a 1e-7 early-state tolerance: the maximum across the first 18 states was2.01e-6. The first 14 states agree to 5.18e-15. Repeating the unchanged old binary produces 0.667% final-cost variability on Venice52; repeating the unchanged new disabled binary produces 1.542%. The source review found no change to disabled arithmetic, but bitwise/complete-trajectory equivalence is not established. Retain this limitation when assessing small regressions.

## Mathematical and numerical checks

- Exact whole-track finite-menu separability verified against exhaustive2^P enumeration in 500 synthetic cases, max absolute difference 1.14e-13.
- Mixed-direction slope verified by independent central differences on a saved real failure, max relative difference 3.42e-9.
- CUDA whole-track decisions agree with independent long-double CPU projection on65 synthetic points/3136 observations, including ties, empty tracks, projection poles and nonfinite alternatives. Quarter/three-quarter keep scales also pass.
- All six saved failure directions match CPU selected steps and actual retracted-state costs; max relative GPU/CPU cost error 4.03e-14. A quarter-scale cached test has 4.12e-16 error.
- The prior NumPy offline Ladybug reconstruction selects 7 frozen points versus 8 on actual GPU-retracted coordinates. The cost discrepancy is 1.83e-9 relative; this is recorded, not silently rounded away. Actual GPU-state CPU selection agrees exactly. Other saved cases differ from prior offline costs by less than 6e-15 relative.
- CUDA memory sanitizer reports zero errors. CLI and embedding core build successfully. Configuration guards reject invalid modes, missing original backtracking, incompatible rescue and subsampled scoring.

## Caspar and novelty

The preceding [fresh Caspar comparison](short_caspar_results.md) used these same scene targets and native FP32 Caspar settings. Caspar hit neither target: Ladybug stopped at its damping limit around0.28s with CPU raw cost484812; Dubrovnik reached roughly1154072 at 8s. This round's fixed-single mode1 reaches both targets. There is **no finite measured Caspar speedup ratio**, and this round did not rerun Caspar. FP64 PRISM versus native FP32 Caspar, including Ladybug's native/CPU objective gap, remains an implementation comparison rather than an isolated algorithmic result.

Independent-set nonlinear refinement already appears in [Ceres inner iterations](https://ceres-solver.readthedocs.io/latest/nnls_solving.html#inner-iterations). Our exact finite-menu selection is not by itself a novelty claim. The demonstrated contribution here is a cheap nonlinear rescue with an online benefit on one conflicting scene, plus evidence identifying a damping-controller failure. See [the derivation](point_safeguard_math.md).

## Decision and next step

Keep mode1 as an experimental fixed-menu option; do not enable a universal default or promote mode2. Fixed single with mode1 is the best tested Dubrovnik configuration at this target, so this round strengthens the point-repair idea more than the case for a five-shift menu.

The next bounded investigation should isolate damping adaptation after an actually accepted mixed step. The full unregularized model prediction for that actual step is P=-g^T d-0.5||Jd||^2, valid algebraically for any direction; actual/P can measure model agreement when P>0. A repaired-step controller must use the actual selected point mask and camera scale, rather than a Schur-only prediction or the original full step. Test its prediction and pair evolution at saved fixed states before changing controller defaults. The present traces motivate that experiment; they do not establish an update rule or convergence guarantee.

## Reproduction and files

Artifacts: `/workspace/prism-point-safeguard/`. Frozen performance binaries `prism-v1` and `prism-v2`, matching source/header snapshots, all plans, flags, binary/data hashes, logs, CSVs, JSONL traces and exported states are retained. The final build also hardens zero-scale selection to explicitly zero an infinite direction component; it is separately frozen, without relabeling earlier performance runs.

```bash
python3 bench/point_safeguard_study.py sanity
python3 bench/point_safeguard_study.py medium
python3 bench/point_safeguard_study.py prospective
python3 bench/backtrack_investigation.py /workspace/prism-point-safeguard/medium-plan.json
python3 bench/backtrack_investigation.py /workspace/prism-point-safeguard/refinement-plan.json
python3 bench/summarize_point_safeguard.py
```

Plan generation refuses overwrite. Existing completed runs are skipped; incomplete run logs are preserved for inspection. To reproduce a fresh study, use new artifact roots in the saved plans and appropriate frozen binary paths. Source: `gpu/point_safeguard.cuh`, integration in `gpu/oca_cuda.cu`, kernel gate `gpu/test_point_safeguard.cu`, math gate `bench/check_point_safeguard_math.py`, study generator and summarizer above. Environment: `OCA_POINT_SAFEGUARD=0|1|2`; unset is off. No defaults changed, no push performed, broad paused queue retained.
