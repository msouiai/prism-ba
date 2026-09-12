# Brief 10: separable rescue of the saved Final3068 proposals

**Neither extension passes the registered rescue gate.** All three reconstructed binary-control witnesses are already accepted, so there are **zero rejected binary-control opportunities** and zero additional rescues. This panel does not establish that these extensions can never rescue rejected proposals; it provides no basis for a native rollout here. The frozen Eta2 champion remains unchanged.

The protocol was committed before the grid at `64be3cad3cbaef91e827d8f18e970c15a798ef4b`: [PROTOCOL_10.md](../PROTOCOL_10.md). All 27 runs completed: three saved terminal states, three arms, N=3 CPU repetitions. These are deterministic conditional replay trials, not independent optimizer trajectories or a hit-rate estimate.

## Measured comparison

The baseline A reconstructs the **already-existing** per-track binary keep/move safeguard at the saved proposed cameras. Arm B permits fractions `{0,1/4,1/2,1}` of that same saved Euclidean point step. Arm C performs A, then one independent keep/move camera pass at the chosen points. Exact ties retain full/larger point movement and moved cameras.

| Witness | Existing binary decrease | Binary rho | Fractional decrease | Fractional rho | Additional decrease | Camera-mask gain |
|---|---:|---:|---:|---:|---:|---:|
| Final3068/0 | 0.200350722 | 0.586041 | 0.200350733 | 0.586041 | 1.14117429e-08 | 0 |
| Final3068/5 | 26.0113991 | 0.804917 | 26.3610137 | 0.682334 | 0.349614595 | 0 |
| Final3068/6 | 0.0371500125 | 0.927638 | 0.0434509669 | 0.626032 | 0.00630095431 | 0 |

Every arm is accepted under the registered full-objective rule: finite cost, positive prediction and true decrease, strict rho >0.1. A terminal FTOL witness is not necessarily a rejected nonlinear proposal; acceptance here does not mean the real solver would continue rather than honor a stopping criterion.

The existing safeguard itself matters materially on /5: the raw captured proposal decreases cost by 15.2675, while its reconstructed binary selection decreases it by 26.0114 with rho 0.8049. That 10.7439 gain is **not new work**. On /6 it raises the raw decrease from about 0.026323 to 0.037150. The new fractional extension adds only 0.349615 on /5 and 0.006301 on /6, respectively about 0.0000187% and 0.000000323% of candidate cost. Both are far below the standing 0.15% cost-verdict threshold. The /0 difference, about 1.14e-8, is below the fixed scoring-agreement budget and should be treated as unresolved.

Arm C retains **all 3,068 moved cameras on every witness and repetition**. It therefore reproduces the binary-control proposal exactly, with additional selection work and no local gain. No combination, repeated alternation, objective modification or new direction was tested.

## Verification, guarantees and accounting

Before the witness grid, independent scalar per-track/per-camera enumeration verified the selected choices. Finite-difference directional Jacobians verified full GN predictions to at most 6.04e-10 relative in the synthetic fixtures. Exact-tie tests retain full movement, including unseen points. A deliberately infinite candidate at a projection horizon is scored as infinity, not dropped, while the finite old point remains available. Evidence: [verification.json](results/verification.json).

All original scored observations and SIMPLE_RADIAL parameters are retained; k2 stays zero. The point fractions cannot exceed the saved source point displacement. Zeroing camera blocks cannot increase the diagonal-scaled camera norm. Both bounds pass on all 27 runs. Direct full scoring agrees with the sum of the selected separable block costs under the unchanged comparison budget, and every new candidate is no worse than its binary control. These are fixed-camera/point selection guarantees, not guarantees of global acceptance or better convergence speed.

The initial scores and unguarded cost/prediction agree with the immutable native captures under the original, cancellation-sensitive budgets. The reconstructed selection uses coherent CPU FP64 projection and deterministic reductions; it matches the safeguard's strict comparison policy, not necessarily its GPU warp-reduction rounding on near ties. No GPU execution or native-mask parity claim is made. All actual selected masks are hashed and fraction/camera counts retained.

Prediction is recomputed for the actual selected original-coordinate tangent, using the full original GN residual model after both masks. It is never borrowed from the unguarded step, and the point safeguard's existing benefit is never credited to the new extensions.

| Arm | Median CPU seconds per replay | Included work |
|---|---:|---|
| binary | 1.451 | Candidate selection plus direct full scoring/model audit |
| point_fractions | 2.005 | Candidate selection plus direct full scoring/model audit |
| point_then_camera | 1.942 | Candidate selection plus direct full scoring/model audit |

The complete CPU campaign took 54.30s, with 49.35s across the 27 arm evaluations. Dataset loading, input hashing and raw-source parity audits are also recorded in the manifest. One BLAS/OpenMP/MKL thread was used. These reference costs do not predict native GPU overhead or time-to-target.

All rows, hashes, choices and checks are in [rows.jsonl](results/rows.jsonl), [ledger.csv](results/ledger.csv), [summary.json](results/summary.json) and [manifest.json](results/manifest.json). There were no invalid candidate observations, no changed k2 entries, and no cheirality flips in this panel.

## Disposition

Both arms stop under the pre-registered additional-rescue criterion; no native rollout follows. The useful findings are the necessary baseline correction, the empty rejected-opportunity set, tiny additional fractional gains, and complete inactivity of the camera mask. They do not support a general claim that separable rescue has been refuted on actual rejection storms. The parent owns any subsequent research agenda; none was launched here.
