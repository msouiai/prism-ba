# Brief 12: ROS2 fails the registered Venice witness screen

The two-stage ROS2 proposal passes the algebra and linear accuracy checks but wins accepted decrease per CPU second against two coherent LM steps on only **1/3** Venice witnesses. It loses with disjoint timing-derived ranges on the other two. The registered gate requires at least two wins, so this formulation is parked; no native GPU integration is justified. Frozen Eta2 remains unchanged.

This is a full-observation, fixed-state CPU diagnostic. Its controls are one and two **fixed-chart coherent LM steps**, not native Eta2 rollouts. It makes no GPU speed, target-hit, or trajectory reliability claim. See [registration](../PROTOCOL_12.md), [pre-data interpretation](INTERPRETATION.md), [raw rows](results/rows.jsonl), and [source/input manifest](results/manifest.json).

## Complete registered results

Every cell has N=3; endpoints and decreases repeat identically within each fixed cell. CPU seconds include fresh model assembly, point QR and Schur factorization, all solves and residual corrections, stage gradients, clipping/completion and full scores. Common input loading is outside arm times and recorded in campaign elapsed time. One BLAS thread was used.

| Witness | Arm | Accepted full cost | Accepted decrease | CPU seconds, median [range] | Decrease/second [range] |
|---|---|---:|---:|---:|---:|
| V0 | one LM | 246323.514605 | 35.509977 | 2.946 [2.934, 5.735] | [6.1923, 12.1025] |
| V0 | two LM | 246322.096170 | 36.928412 | 5.889 [5.879, 5.919] | [6.2392, 6.2819] |
| V0 | ROS2 | 246323.478767 | 35.545816 | 3.294 [3.294, 3.329] | [10.6782, 10.7914] |
| V1 | one LM | 244946.804191 | 0.034862 | 2.933 [2.931, 2.951] | [0.011813, 0.011893] |
| V1 | two LM | 244946.774536 | 0.064517 | 5.868 [5.859, 5.904] | [0.010928, 0.011012] |
| V1 | ROS2 | 244946.839053 | 0, rejected | 3.340 [3.324, 3.355] | [0, 0] |
| V2 | one LM | 246402.395498 | 1.299238 | 2.936 [2.917, 2.946] | [0.441033, 0.445369] |
| V2 | two LM | 246401.457809 | 2.236927 | 5.857 [5.849, 5.899] | [0.379215, 0.382464] |
| V2 | ROS2 | 246402.833585 | 0.861151 | 3.295 [3.287, 3.305] | [0.260567, 0.262005] |

Initial scores are 246359.02458229894, 244946.83905292646 and 246403.69473567858. All matched input and initial-score checks pass. Total registered arm CPU wall is 111.974 s; campaign elapsed wall is 112.699 s.

ROS2 versus two LM has a disjoint gain/work win on V0, then two disjoint losses on V1 and V2. Against one LM, V0 has slightly more decrease but a lower median gain/work and overlapping ranges; V1 and V2 are disjoint losses. The first V0 one-LM run took 5.735 s, versus about 2.94 s subsequently. It is retained, not discarded or replaced. None of the accepted-cost differences against two LM exceeds 0.15%: ROS2 regressions are +0.0005613%, +0.00002634%, +0.0005583%. Small endpoint differences do not rescue the failed work-efficiency gate.

## What the second stage does

At V0, ROS2 obtains essentially the one-LM decrease while paying for another RHS and stage gradient. It saves a second factorization relative to two LM, which explains its sole win against that control. At V2 it obtains less decrease than even one LM. Its rho is better (1.0218 versus 0.7919), but agreement between model and true decrease does not imply greater decrease per work.

V1 exposes a direct failure. The first internal camera stage has norm 2596.57, compared with saved radius 403.17, and increases cost to 244963.797073. The fixed second solve produces camera norm 1004973.64; the combined raw direction has norm 291253.47 and cost 101192871.787833. Its full linear equations nevertheless pass the accuracy check. The final radius-feasible combination, with the ROS combined point forcing retained, has cost 244947.166893: **a true increase of 0.327840**. Its prediction is **-0.311992**, and rho is +1.050795 only because both numerator and denominator are negative. Positive prediction and true descent are mandatory, so it is correctly rejected in all three repetitions. Raw prediction is -32.827219 and raw rho is +3075128.78; this is another reason not to use rho alone as acceptance evidence.

There is a simple quadratic limit behind the low prior. With an exact nonsingular quadratic Hessian H and vanishing damping, k1 is the Newton step, k2=(1-1/gamma)k1, and the final ROS2 combination equals k1 because 2 gamma^2-4 gamma+1=0. The extra stage tends to reproduce one Newton step, not two. This is an explanatory SPD toy limit; BA's approximate GN Hessian, gauge modes and intrinsic solve regularizer prevent treating it as an identity for these witness trajectories.

## Correctness and scope

The coefficients and convention were checked against the primary [KPP ROS-2 documentation](https://kpp.readthedocs.io/en/stable/num_methods/rosenbrock-methods.html). Toy quadratic and nonlinear flows show third-order local-error decay, as required for a second-order method, including arbitrary approximate Jacobians. Fixed-chart SO(3) transport passes finite differences: left-Jacobian error 9.75e-11 and gradient error 3.80e-10. The tiny coherent Schur direction agrees with a full dense solve to 2.80e-12 relative. Combined-RHS point completion agrees exactly without clipping and passes its clipped equation check.

All 27 rows are valid. Maximum independently recomputed D-whitened full-normal residual among individual stage/LM solves is 9.39e-12; the largest ROS combination residual is 1.13e-11, below the registered 1e-10 threshold. Three total fixed-factor refinement corrections were needed, one in each V1 ROS2 repetition, and are charged. There are no nonfinite projection events. Tests and source fingerprints are in [verification](verification.json) and [manifest](results/manifest.json).

The result rejects this fixed gamma, h=1/lambda, saved-metric formulation at the prescribed witness gate. It does not rule out all Rosenbrock methods or time-integration interpretations of optimization. No post-hoc coefficient change, stage selection or line-search arm was introduced.
