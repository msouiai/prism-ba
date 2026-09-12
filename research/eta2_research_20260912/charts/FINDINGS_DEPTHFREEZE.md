# Brief 2(c): registered thin-track depth-freezing witness test

This report covers the single rule registered in [PROTOCOL_02C.md](../PROTOCOL_02C.md), commit `f8d25e36ea3bb59d3e316a0422ed166bdd5788c4`. The frozen Eta2 champion remains the baseline. This experiment is a CPU conditional point solve at captured camera directions; it does not measure solver endpoint reliability or GPU time-to-target.

The rule freezes the inverse-depth increment when maximum initial parallax is below one degree, or a two-observation track's undamped FP64 Euclidean point-normal condition number is at least `1e8`, or there are fewer than two observations. A nonpositive minimum eigenvalue counts as infinite condition number. The first original-order observation supplies the frozen anchor. Both bearing coordinates remain active. Lambda and the three-coordinate diagonal/trace damping remain identical to the earlier inverse-depth test. There is no depth release, observation removal, objective change, threshold tuning or damping sweep.

Nine captured states, two prescribed camera directions and three CPU repetitions give **54 new runs / 18 configurations**. The protocol's phrase “54 new cells” is interpreted by that explicit factorial design. Historical Euclidean and plain-ID controls remain immutable; their files and all input/source hashes are recorded in [results_depthfreeze/manifest.json](results_depthfreeze/manifest.json).

## Implementation and verification

`reference.py` adds an optional, default-off boolean mask. Frozen points solve the 2x2 bearing principal block of the same damped 3x3 system; free points solve all three coordinates. Prediction uses the actual selected chart tangent, including zero inverse-depth increments on frozen points. It does not substitute Euclidean displacement for a finite inverse-depth retraction.

The numerical default path is bit-identical to the committed pre-freeze reference for all three synthetic chart controls and the actual Venice/0 plain-ID conditional step. An all-false mask is also bit-identical. Mixed and all-frozen constraints match independent augmented least-squares solves to `1.48e-15`; frozen inverse-depth increments are exactly zero. The earlier analytic-Jacobian and independent scoring checks still pass. Evidence: [verification.json](results_depthfreeze/verification.json) and [reference_reverification.json](results_depthfreeze/reference_reverification.json).

A constrained point has a nonzero depth-equation residual in general: that is its Lagrange reaction. Reported solve residuals certify active bearing equations for frozen tracks and all three equations for free tracks. The depth reaction norm is recorded separately, rather than mistaken for failed linear convergence or hidden in a full-system certificate.

## Results

The complete table and original gate are recorded in [ledger.csv](results_depthfreeze/ledger.csv) and [summary.json](results_depthfreeze/summary.json). Compact individual rows are [rows.jsonl](results_depthfreeze/rows.jsonl).

**KILLED: the registered rule fails the original Ladybug outward-movement gate and the two-family improvement gate.** All 54 runs completed with valid scores and unchanged initial-score tolerances. The tau-floor-removal sweep is stopped; no native rollout or release experiment follows.

| Primary state | Frozen-ID cost | Change vs Euclidean | Change vs plain ID | rho | Inward / outward large moves |
|---|---:|---:|---:|---:|---:|
| venice-52 / 0 | 246,358.49 | +0.00000613% | +1.04583% | 0.78147 | 0 / 0 |
| venice-52 / 1 | 244,946.82 | +0.00000227% | +0.96582% | 0.33160 | 0 / 0 |
| venice-52 / 2 | 246,402.76 | +0.00000760% | +1.05166% | 0.70387 | 0 / 0 |
| final-3068 / 0 | 1,831,858.82 | -0.00000007% | +0.00000% | 0.58859 | 0 / 0 |
| final-3068 / 5 | 1,866,190.06 | +0.00642499% | +0.00063% | -0.70329 | 0 / 0 |
| final-3068 / 6 | 1,951,874.38 | -0.00029291% | +0.00070% | 0.78371 | 0 / 0 |
| ladybug-1197 / 0 | 1,109,795.17 | -45.97435862% | +0.02625% | 0.91474 | 29 / 63 |

**Venice:** freezing about 0.78% of points removes every one of the plain-ID 9/10/9 large inward recoveries. Candidate costs increase by 2,549.83, 2,343.12 and 2,564.36 versus plain ID, erasing its roughly 1% improvement and returning to almost exactly the Euclidean costs. The new large-movement counts and cheirality-flip counts are zero. This is a clean adverse mechanism result: the same low-parallax depth coordinate supports both escaped-point recovery and the motion being suppressed.

**Ladybug:** all three captures retain **63 outward large moves**, unchanged from plain ID and far above the Euclidean control's one. The rule freezes only 79 of 126,327 points. Importantly, **one of the frozen points itself still moves outward by more than the scene radius**; fixing depth does not bound its bearing move. The maximum displacement does improve, from about 1,803 under plain ID to **178.04**, but this remains above the Euclidean 16.30 and does not satisfy the registered count-based cure. Inward large moves fall from 35 to 29. Cheirality flips fall from two front-to-behind observations to zero. These narrower benefits are retained rather than hidden by the negative verdict.

Ladybug's candidate objective remains 45.97% lower than Euclidean, with rho 0.91474. That is only one primary state/family; the two additional Ladybug captures are repeat controls, not extra families or independent optimization runs. It cannot override the explicit fling kill.

**Final3068:** the /5 candidate remains a real rejection: its cost increases from the current state by **104.63**, with rho **−0.70329**. This is worse than plain ID's 92.92 increase and Euclidean's 15.27 decrease. The relative endpoint-scale difference is small, but the failed local proposal is still recorded. State /6 improves the current objective by 5.74 versus Euclidean's 0.0263, while losing part of plain ID's 19.34 decrease; its relative cost change is below the registered significance threshold. State /0 remains effectively neutral.

The clipped-reference camera directions reproduce the same signs: Venice recovery disappears, Final3068/5 rejects, and Ladybug retains the 63 outward moves with a 23.394% conditional cost improvement versus its Euclidean control. There are no >0.15% primary candidate-cost regressions versus Euclidean, but no two-family gains and no Ladybug count cure either.

The two-observation Gram-normal eigensolver reports two nonpositive minimum eigenvalues at Venice/1 and none elsewhere. They are recorded as numerical nonpositive cases and frozen, not interpreted as true negative curvature of a Gram matrix. No capture contains a fewer-than-two-observation track or undefined geometric parallax.

All frozen rho increments are exactly zero. The largest active-equation relative residual is **2.88e-16**; maximum relative initial-score discrepancy is **3.59e-12**. No candidate has an exactly infinite point or invalid projection.

The grid took **120.23s** elapsed: candidate assembly/solve/scoring totaled **82.17s** and mask construction **31.64s**. Mask setup was 1.33–1.34s per Venice state, 6.55–6.59s per Final3068 state and 2.62–2.64s per Ladybug state; these CPU costs do not predict GPU overhead.

## Accounting and limits

Every candidate scores all original SIMPLE_RADIAL observations with unshared intrinsics and `k2=0`, including negative depth. Initial-score agreement uses the previously registered tolerance unchanged. Camera directions are the same `eta2-0.step` and `exact_clip-0.step` as the plain-chart grid. A reduced-reference certificate on the latter's source does not become a full-normal certificate by reusing it here.

Mask geometry and condition checks are recomputed once per captured state, then reused across its fixed directions and repetitions. Their actual setup cost is recorded, and each candidate also reports its time plus the full, unamortized mask-construction cost. Assembly, linear solve and scoring/diagnostics are timed separately. This one-thread NumPy reference is not a GPU implementation or an isolated performance comparison with the champion.

The scene radius is the maximum camera-center distance from their arithmetic mean. “Large movement” means point displacement exceeding that radius; “outward” additionally means increased distance from that camera-center mean. This distinction is necessary because Venice's plain-ID large moves were useful inward recovery of escaped points. Fixing inverse depth does not mathematically bound changes in the bearing coordinates or their induced Euclidean movement.

## Remaining bounded experiments, proposals only

If this registered rule fails, its tau-floor-removal sweep stops. Neither this test nor plain-ID objective gains authorize lowering damping or promoting a chart into the native solver.

A narrow Brief 8 pre-test would evaluate the points-only residual-Hessian correction at the Ladybug opening witnesses, where the prior decomposition actually identifies substantial point model error. Keep the captured cameras and lambda fixed, compare true/model decrease against coherent Euclidean GN, and record every indefinite point block and its pre-registered GN fallback. Final3068 raw-reference failure is camera-dominated, so a points-only Newton change should not be sold as its established cure.

Alternatively, Brief 10's per-track fractions `{0, 1/4, 1/2, 1}` along the existing Euclidean point direction have a useful fixed-camera guarantee: choosing each track's least true cost cannot score worse than its existing `{0,1}` binary selection, and fractional Euclidean moves cannot exceed the full proposed displacement. That guarantee does not promise global acceptance, speed, or zero flings, and selected-point prediction must still be recomputed correctly. It is a distinct bounded line search, not periodic retriangulation. Neither proposal has been implemented or run here; the parent owns the remaining research agenda.
