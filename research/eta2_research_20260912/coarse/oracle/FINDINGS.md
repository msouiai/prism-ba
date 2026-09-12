# Brief 9 terminal coarse stopping oracle

**Close this registered terminal oracle/correction branch. None of the three
Final3068 witnesses passes the feasible-step gate.** Three complete CPU
repetitions per witness give identical gains. These are fixed-state arithmetic
repetitions, not independent optimizer hit-rate measurements.

The committed [protocol](../../PROTOCOL_09.md) requires the same-radius clipped
coarse proposal to have rho>0.1 and exceed twice the stored Eta2 gain on at
least two of three states before another nonlinear collective rollout. All
three clipped coarse proposals have positive gain and adequate rho, but all
three gain **less** than Eta2. The observed continuation count is 0/3.

| Final3068 witness | Stored Eta2 gain | Raw coarse gain | Clipped coarse gain | Clipped / Eta2 | Clipped rho |
|---|---:|---:|---:|---:|---:|
| 0 | 0.200350711 | 0.001882367 | 0.001882367 | 0.00940x | 0.99963 |
| 5 | 15.2674730 | 128.0207321 | 13.2780600 | 0.86970x | 0.44907 |
| 6 | 0.026323252 | 0.410405666 | 0.018553958 | 0.70485x | 0.28654 |

The unrestricted results are real positives and are retained: witness 5 gains
8.39 times Eta2 with rho=0.8046, and witness 6 gains 15.59 times Eta2 with
rho=0.8654. Their camera norms, however, are 49.16 and 2932.55 times the saved
radius. Conditional point back-substitution after clipping removes those
advantages. Witness 0 is already inside its radius and gives only 0.94% of
Eta2's gain. Positive unrestricted results do not satisfy this registered
feasibility rule or authorize changing the controller.

## The decrement and the original zero test

The camera-only reduced decrement is `0.5 bc^T Ac^-1 bc`. It excludes the
point-only damped elimination constant `0.5 gp^T Vlambda^-1 gp`. Their sum is
the optimum **damped quadratic** prediction for the raw restricted camera
direction with conditional points. Neither term alone is the actual full
objective decrease or the undamped GN prediction used for rho.

| Witness | Camera coarse decrement | Point-only damped constant | Raw norm / radius |
|---|---:|---:|---:|
| 0 | 9.6176770e-6 | 9.3209158e-4 | 0.04715 |
| 5 | 70.6885347 | 13.5414123 | 49.1610 |
| 6 | 0.2263421 | 0.0326271 | 2932.5484 |

The original “decrement approximately zero everywhere” kill is **not** met:
the camera decrement is positive at all three states and materially nonzero at
two. Numerical-zero thresholds were specified before running in
[IMPLEMENTATION_NOTES.md](IMPLEMENTATION_NOTES.md); no row is at that threshold.
This does not reverse the separate practical kill above. A nonzero reduced
decrement need not identify a useful feasible step or invalidate the original
stopping decision.

## Operator, precision and validation

Every repetition reconstructs the coherent FP64 Jacobian using all original
observations, SIMPLE_RADIAL, unshared intrinsics and k2=0. It retains captured
lambda, E and the point diagonal damping metric, plus the original intrinsic
solve prior. Point factors use FP64 QR. Camera memberships and the verified
native Sim(3) basis use K8 and the existing dependence threshold; effective
rank is 50 at all three states. Global similarity modes remain included with
damping, not deleted as a supposed exact nullspace. The raw direction's global
similarity fractions are 17.78%, 28.25% and 16.72%.

No dense 27,612-by-27,612 camera matrix is formed. Sparse W has 39,691,488
nonzeros; local sparse Z has 128,820; the point/coarse T matrix has about
6.54 million. Only the 50-by-50 Ac is dense. No Jacobian, state or direction
archives are written by this task; compact reports retain matrix/RHS, ranks,
input hashes and diagnostics.

All nine repetitions pass:

- Ac Cholesky and positive dense eigenvalues;
- four independent Jacobian-form product comparisons, maximum relative error
  5.20e-15;
- independent reduced-gradient comparison, maximum relative error 5.29e-15;
- full versus eliminated damped-model identity, maximum normalized discrepancy
  2.66e-15;
- full-objective initial-score agreement, maximum relative discrepancy
  7.49e-15;
- conditional point equations, maximum residual relative to conditional RHS
  6.11e-14 across raw and clipped proposals.

Ac eigenvalue ranges are 7752.200–7755.969, 11.1600–14.8221 and
9.70376–13.3661. The reduced coarse systems are well conditioned at these
strongly damped terminal states. The independent tiny captured-BAL check also
passes operator and model-identity tests before the primary runs.

This coherent fixed-state diagnostic does not change the production operator
or reclassify the original source directions as fully exact. The earlier
[retained prediction mismatches](../../analysis/retained_mismatches.json) remain
unchanged. All CPU costs are diagnostic overhead (7.8–33.9 seconds per complete
repetition); no GPU speed comparison or new endpoint has been measured.

## Deliverables

[summary.json](summary.json) contains both kill questions and the explicit
no-continuation verdict. [ledger.csv](ledger.csv) contains all 18 raw/clipped
rows. [results/](results/) retains all nine complete repetitions;
[toy.json](toy.json) is the prior tiny correctness check. [run.py](run.py) and
[report.py](report.py) reproduce the calculations and summary. The frozen Eta2
champion remains unchanged.
