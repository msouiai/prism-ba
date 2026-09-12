# Brief 2: registered conditional point-chart witness pre-test

**The original bounded-chart/fling-cure hypothesis is KILLED for both homogeneous S3 and plain frozen-anchor inverse depth.** The user's original fling criterion takes precedence over the later objective-fidelity screen. Inverse depth passes that subsidiary objective screen and S3 does not, but neither result authorizes a plain-chart native rollout. Improved pixel objective does not imply bounded Euclidean movement or correct cheirality.

The [protocol](../PROTOCOL_02_PRETEST.md) was registered at commit `304f991` before running any BAL chart comparison. The grid completed **162/162 valid CPU diagnostics**: nine captured states, two fixed camera directions, three charts and three repetitions per cell. Seven states are primary witnesses; the additional two Ladybug captures are repeat controls. Every score-init check passed. Every candidate retained all original SIMPLE_RADIAL observations, unshared intrinsics and `k2=0`. No GPU rollout, damping sweep, depth freezing, anchor search or solver promotion occurred.

Inputs and frozen build/configuration verification are pinned in [results/manifest.json](results/manifest.json). Raw compact rows are in [results/rows.jsonl](results/rows.jsonl), all 54 cells in [results/ledger.csv](results/ledger.csv), and gates in [results/summary.json](results/summary.json). The camera sources are always `eta2-0.step` and `exact_clip-0.step`; repeated CPU trials use those same fixed directions. The reference-camera certificate applies to its source reduced solve, with full-normal accuracy qualified by [Brief 0](../analysis/FINDINGS.md).

## Primary camera direction: same captured Eta2 cameras

Percent changes compare the chart's full candidate objective with the **FP64 Euclidean conditional point solve at identical cameras**, rather than changing both point precision and chart at once. Negative is better. N=3 repetitions per cell; CPU numerical values are identical within each cell.

| Primary state | Euclidean cost | S3 cost change | Inverse-depth cost change | Inverse-depth rho |
|---|---:|---:|---:|---:|
| Venice / 0 | 246,358.48 | −0.97951% | **−1.03500%** | 0.98236 |
| Venice / 1 | 244,946.81 | −0.94104% | **−0.95658%** | 0.98556 |
| Venice / 2 | 246,402.74 | −0.97452% | **−1.04071%** | 0.98061 |
| Final3068 / 0 | 1,831,858.82 | +0.00000033% | −0.00000187% | 0.62460 |
| Final3068 / 5 | 1,866,070.17 | **+10.26678%** | +0.00579765% | **−0.57904** |
| Final3068 / 6 | 1,951,880.10 | +0.02045365% | −0.00098973% | 0.92502 |
| Ladybug1197 / 0 | 2,054,200.83 | −2.48349% | **−45.98854%** | 0.91474 |

Inverse depth passes the subsidiary objective-fidelity gate: four primary wins greater than 0.15%, spanning Venice and Ladybug, with positive prediction and rho above 0.1; no primary cost regression exceeds 0.15%. S3 fails because Final3068/5 regresses 10.27%. The original fling-cure kill criterion overrides this screen, so **do not promote or launch plain native inverse depth**. The `always_on_witness_gate_passed` field in the numerical summary refers only to its explicitly stated objective screen, not permission or an overall promotion verdict.

**Final3068/5 is still a real local acceptance failure for inverse depth.** Euclidean decreases the current objective by 15.27; inverse depth increases it by 92.92, despite predicting a decrease of 160.47. The small percentage change against an objective of 1.87M does not make that proposal acceptable. Final3068/6 is a weaker local improvement: decrease rises from 0.0263 to 19.3447, but the relative candidate-cost change remains far below 0.15%. Final3068/0 is essentially neutral.

On Venice/1, the hypothetical inverse-depth candidate is 242,603.70, below the registered 243,740.27 target. Venice/0 and /2 remain above it at 243,808.66 and 243,838.40. These are conditional fixed-state outcomes, not a target-hit-rate experiment or measured time-to-target.

On Ladybug, inverse depth reduces the point-only model error from 1.526M to 0.209M at the same captured cameras. Its full candidate cost falls from 2.054M to 1.110M. The two independently captured Ladybug controls reproduce the −45.99% result; this remains an opening-step comparison rather than an endpoint or basin-reliability result.

## Secondary camera direction

The clipped reference-camera arm preserves the qualitative results. Inverse depth improves the three Venice candidates by 0.95682–1.04153%, improves Ladybug by 23.40863% (2,002,780.50 to 1,533,957.05), is essentially neutral on Final3068/0, rejects on /5, and gives a small improvement on /6. S3 again regresses Final3068/5 by about 10.27%. Thus the chart result is not explained solely by one inexact camera direction, although the magnitude of the Ladybug gain depends on the camera direction.

## What the large point movements actually mean

The registered “fling” count is `||delta X|| > max_i ||C_i-mean(C)||`, not an outward-distance test. Descriptive replay of the **same registered cells**, with no changed configuration, distinguishes movement toward and away from the camera-center mean. Its code and rows are in [results/displacement_forensics.py](results/displacement_forensics.py) and [results/displacement_forensics_v2.json](results/displacement_forensics_v2.json).

On Venice, the apparent increase in large movements is recovery of already escaped points:

| State | Euclidean large moves, inward/outward | Inverse-depth large moves, inward/outward | Maximum old distance | Maximum new ID distance |
|---|---:|---:|---:|---:|
| Venice / 0 | 0 / 3 | 9 / 0 | 1.62M | 81.26 |
| Venice / 1 | 0 / 4 | 10 / 0 | 9.91M | 431.56 |
| Venice / 2 | 0 / 4 | 9 / 0 | 1.55M | 152.74 |

Those few inward-moving tracks account for **99.96–99.98% of the inverse-depth candidate-cost improvement** over Euclidean. This is the clearest mechanism result: the Euclidean conditional model leaves several previously escaped points far away, while the alternative chart/damping metric can bring them back with large, useful changes in world coordinates. S3 also recovers these escaped points but has its own Final3068 counterexample.

Ladybug tells a different story. All three controls have one outward large movement under Euclidean, compared with 98 large inverse-depth moves: 35 inward and **63 outward**, with maximum displacement about 1,803 versus 16.30. S3 has 46 large moves, evenly split inward/outward, maximum about 3,583. The historical 2.4e4 fling was absent in the frozen control, but the new charts certainly do not eliminate outward large motion. Under the original brief's fling-cure criterion, **that hypothesis is refuted**. Passing the separately registered objective-fidelity gate does not resurrect it or justify removing the point-damping floor.

The objective also retains its cheirality ambiguity. Inverse depth changes some points from behind to in front and some the opposite way. Venice/1 has 16 behind-to-front observation flips and two front-to-behind flips; Ladybug has two front-to-behind flips in each control. No cheirality penalty or hidden rejection rule was added. There were no exactly infinite candidate points and no invalid candidate projections in the registered grid.

The Final3068 camera-center radius is itself about 10.4M at these stop witnesses. Its zero threshold-crossing count therefore coexists with point movements up to millions of coordinate units. Report the radius and maximum movement alongside counts; zero is not a boundedness certificate.

## Accuracy, overhead and attribution limits

- All 162 score-init comparisons passed the fixed budget; the maximum relative discrepancy against the independent Euclidean CPU initial score was 1.69e-11. No scored observations were omitted.
- The largest reported relative residual of the conditional point normal solve was 2.01e-11. This verifies the computed chart systems, not exact nonlinear minimization or every per-point backward error.
- The grid used one BLAS/OpenMP/MKL thread per process and charged assembly/setup, linear solve, scoring/diagnostics, and campaign setup/I/O. The registered calls totaled 232.21 CPU wall seconds; campaign elapsed time was 261.06 seconds. These are implementation diagnostics, not GPU overhead estimates or solver-speed comparisons. A short descriptive forensic replay overlapped a portion of the grid; therefore do not use these CPU ranges as isolated timing benchmarks.
- Diagonal Marquardt damping changes physical metric under a coordinate change. The measured intervention is **chart plus chart-coordinate damping plus its finite retraction**, not a pure nonlinear-retraction ablation. A future pullback-metric ablation would be a distinct experiment.
- Spherical normalization and inverse depth have substantial prior art; [README.md](README.md) records the exact overlap. The current contribution is measured failure/recovery mechanism and an integration candidate, not invention of homogeneous or inverse-depth BA.

## Next allowed branch: Brief 2(c), proposal only

The next distinct user-proposed experiment is **depth-frozen thin tracks**, not deployment of plain inverse depth. A simple globally fixed screening rule is: freeze the inverse-depth increment for tracks with maximum initial parallax below one degree, or for two-observation tracks whose undamped FP64 Euclidean point normal block has condition number at least `1e8`. Tracks with fewer than two observations are also depth-unobservable and can be treated as frozen. The two bearing coordinates remain active, with all their observations retained. A nonpositive minimum eigenvalue counts as infinite condition number; report these numerical cases separately.

For the first fixed-state test, apply that same rule at every witness with **no release** and compare against both the Euclidean control and the plain ID rows already recorded. This isolates whether depth freezing actually reduces the Ladybug outward moves. A later full-solver experiment could separately register a monotone global release latch when lambda first falls below `1e-3`, after which depths remain free. That proposed release is not active in this pre-test and has not been selected by a sweep.

There is a predictable tradeoff to test honestly: Venice's already escaped points have low parallax and need a depth change to return. Freezing them may remove exactly the 99.96–99.98% recovery mechanism identified above. No threshold can be called successful before that loss is measured. Fixing inverse depth also does not mathematically prevent large lateral world motion from a large bearing update. Continue reporting actual inward/outward movement, cheirality, full model agreement and objective changes; do not replace the original kill criterion with the objective screen again.

If a depth-frozen variant later clears its own protocol, the relevant native integration anchors would be `ScoreTail` around line 10332, camera clipping around line 11272, the point safeguard around line 11494, and strict full-model scoring around line 11613. Conditional point solving after the original camera solve remains a hybrid proposal, because those cameras were solved with the Euclidean point model. A selected chart's prediction must use `J_ID delta_ID`, not `J_X (X_new-X_old)`. Chart backtracking, old/full selection and candidate swaps must retain the corresponding chart increment/provenance. Exactly infinite points also need an explicitly registered native representability policy. These are implementation requirements, not an implemented candidate.

A per-track minimum of old/Euclidean/ID candidates is another distinct possible policy with a fixed-camera separability guarantee, but it is not the user-requested depth-freezing test and has not been authorized by these results. No rescue variant, native rollout, depth freezing or tau sweep was implemented here.
