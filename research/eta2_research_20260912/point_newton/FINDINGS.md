# Brief 8: point-only Newton correction fails the witness gate

**Killed under the registered conditional-point protocol.** The analytic
Hessian correction produces a severe Ladybug1197 rejection with both saved
camera directions. Frozen Eta2 remains the champion; no native point-Newton
implementation or GPU rollout is justified by this screen.

The [protocol](../PROTOCOL_08.md) was committed at `ddf798c` before execution.
All **54/54 CPU rows** completed: nine captured states, two prescribed camera
directions, and N=3 repetitions. The seven primary states and two Ladybug
repeat controls are unchanged. Original observations, SIMPLE_RADIAL,
unshared intrinsics and k2=0 were retained. Every initial cost matched its
immutable Euclidean control exactly in this reference implementation.

## Results at the captured Eta2 cameras

Negative cost changes are better. These are conditional proposal costs at a
fixed witness, not endpoint or time-to-target measurements.

| Primary witness | Euclidean cost | Point-Newton cost | Relative cost change | Hybrid rho |
|---|---:|---:|---:|---:|
| Venice / 0 | 246358.477564 | 246358.476650 | −0.000000371% | 0.78642 |
| Venice / 1 | 244946.812039 | 244946.812361 | +0.000000132% | 0.38189 |
| Venice / 2 | 246402.737815 | 246402.737498 | −0.000000129% | 0.70805 |
| Final3068 / 0 | 1831858.817636 | 1831858.817637 | approximately zero | 0.58604 |
| Final3068 / 5 | 1866070.168567 | 1866060.168365 | −0.000535896% | 0.62687 |
| Final3068 / 6 | 1951880.100806 | 1951880.083042 | −0.000000910% | 0.78779 |
| Ladybug1197 / 0 | **2054200.828830** | **91203259267.8596** | **44,398 times the control cost** | **−10189.263** |

The exact-clipped camera arm also fails on Ladybug: cost goes from
2,002,780.50 to **60,410,335.05**, about 30.16 times the control, with hybrid
rho −6.498. All three independently captured Ladybug states reproduce both
failures; each fixed-state CPU cell is numerically identical across its three
repetitions. This is not a basin-noise or hit-rate estimate.

The modest positive Final3068 result is retained rather than hidden:
at witness /5 the true decrease rises from 15.27 to 25.27 and model agreement
improves from rho 0.2664 to 0.6269. At /6 it rises from 0.0263 to 0.0441.
Both cost changes remain far below the standing 0.15% verdict threshold.
Venice changes are negligible; the largest absolute relative change across
its two camera arms is a **+0.0000905% regression** at Venice0/exact-clipped.
No meaningful registered cost win offsets the Ladybug failure.

## The failure is a projective-domain problem, despite an SPD point block

The [unchanged-candidate forensic replay](results/failure_forensics.json)
reproduced the registered Ladybug0/Eta2 cost exactly. A single two-observation
point, **47270**, contributes **99.9957%** of the candidate's total cost.
Its two cameras are 346 and 354.

| Diagnostic for this point | Measurement |
|---|---:|
| Full track cost before the proposal | 12837.22 |
| Full track cost after the proposal | 91199338038.26 |
| Damped Dp-whitened eigenvalues | 0.01328, 1.09248, 2.25532 |
| Minimum/maximum eigenvalue ratio | 0.005887, well above the registered 1e-12 gate |
| Point movement / camera-center scene radius | 1.9883 / 12.3227 |
| Depth in camera 346 | −0.88984 → −0.06877 |
| Depth in camera 354 | −0.82916 → −0.005967 |
| Maximum normalized bearing norm after the step | 74.77 |

The point passes the SPD gate, moves less than the scene-radius threshold,
and **does not change depth sign in either observation**. Its finite step
approaches the perspective horizon, where reprojection and radial distortion
grow sharply. The quadratic Hessian at the old point remains a local model;
its positive definiteness is no guarantee that a full step remains in a
region where that model is accurate. Consequently a sign-flip check or the
registered large-displacement check would not catch this dominant failure.

The point-only nonlinear cost of that track is already 90.790B with cameras
held at their old values, so the dominant failure is indeed in the point
proposal. The full primary Ladybug candidate also has five point-induced
cheirality flips elsewhere, but those flips do not explain its dominant
track. The registered large-move count stays at one outward move, compared
with one for the Euclidean control; a count-only fling diagnostic misses
the main damage here.

## Fallback and accuracy

Only **3 of 126,327 Ladybug points** fall back to GN: **0.002375%** of points,
covering seven observations (**0.001242%**). The undamped V+N block is
indefinite at 78 points (**0.061745%**), covering 249 observations
(**0.044170%**). These differ because the existing positive damping makes
most raw indefinite blocks pass the damped SPD test. No nonfinite blocks
occur. Venice and Final3068 have **zero damped fallbacks**.

Thus the protocol's “fallback above 5%” kill does **not** fire. The independent
Ladybug model-agreement/acceptance and >0.15% regression kills do fire.
Fallback dominance or failure to solve the selected blocks is not the
explanation: the largest point normal relative residual is 1.10e-11 and
the largest per-point normwise backward error is **1.95e-16**.

Before witnesses, 64 synthetic projection tests checked the analytic
residual-Hessian contraction against differentiated analytic gradients:
maximum relative error **7.33e-10**. The full objective Hessian check was
**1.03e-9**. Zero residual recovers the Euclidean GN blocks, damping and
direction exactly, and selected fallback blocks recover the exact GN
solution. Details are in [verification.json](verification.json).

The active hybrid prediction was evaluated as specified,
`pred_hybrid = pred_GN - 0.5 sum dp^T N_active dp`, with N omitted at every
fallback point. Ladybug's GN and hybrid predictions are 7.518M and 8.950M,
respectively, while its actual decrease is **negative 91.195B**. Improving
the derivative order does not make this large finite point step useful.

## Camera prediction-only variant

All nine already recorded raw reference Final3068 proposals (three states
times three reference solves) increase the true objective. At the three
states their decreases are approximately −218.76, −205309.55 and −533926.62.
Changing prediction alone cannot change the mandatory strict descent test.
The [algebraic kill](camera_prediction_kill.json) records every supporting
row and source hash; no relabelled ratio or extra GPU test is counted as
algorithmic progress.

## Artifacts and scope

[results/manifest.json](results/manifest.json) pins the configuration, frozen
source/header verification, every witness/input, implementation and retained
Euclidean controls. [rows.jsonl](results/rows.jsonl) retains all 54 trials;
[ledger.csv](results/ledger.csv) reports all 18 N=3 cells, both directions
of change, costs, predictions, residuals, fallback and displacement.
[summary.json](results/summary.json) applies the registered gates.

The registered diagnostic calls totaled **118.05 CPU seconds**; the serial
campaign took **123.07 seconds**, plus one short descriptive forensic replay.
The CPU process used one BLAS/OpenMP/MKL thread while the parent campaign
could run unrelated native GPU work. These are implementation work records,
not isolated hardware speed comparisons or GPU overhead estimates.

This rejects the specified **conditional** point-Newton proposal. It does
not prove that every full joint Newton method or a separately designed
point trust-region scheme fails. A native joint implementation would also
need to handle a separate issue: SPD point blocks alone do not certify an
SPD full hybrid Hessian or Schur complement. Analytic Hessians and partial Newton models
are established ideas; the useful result here is the measured mechanism:
an accurately solved, comfortably SPD point model can produce a disastrous
finite projection step without a large world-space displacement or depth-sign
change. No native rollout or broad novelty claim follows from this test.
