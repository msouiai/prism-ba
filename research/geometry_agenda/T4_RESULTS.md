# T4: supported controlled mechanism; real transfer failed

The exact similarity update and its native-chart tangent pass invariant,
derivative, gauge and immutable-parent tests. The controlled result supports
the finite-path mechanism described in [T4_MATH.md](T4_MATH.md), including its
close prior-art limitations. It does not establish a new fastest BA solver.

| Cohort | Nonlinear / fine speed, weak / strong bridges | Nonlinear / matched linear speed |
|---|---:|---:|
| Known clusters, held-out 100–109, 12 cams/180 pts | 1.79x / 1.53x | 1.46x / 1.21x |
| Automatic v1, 200–209, 12/180 | 0.66x / 0.61x | 0.97x / 0.95x |
| Automatic v1, 200–209, 30/900 | 2.57x / 2.58x | 1.23x / 1.35x |
| Automatic v2, 300–309, 12/180 | 1.62x / 1.32x | 1.57x / 1.42x |
| Automatic v2, 300–309, 30/900 | 3.06x / 2.70x | 1.25x / 1.35x |

Every observable row hits on all ten seeds, N=3, with no point-NRMSE>0.15 cases.
The automatic v1 camera partition is correct, but up to 9% of small-problem
points follow the wrong cluster; with ten local views per point instead of
four, that assignment defect almost disappears. V2 weights point ownership
votes by initial reprojection consistency, without changing BA residual
weights or dropping observations. It recovers the generating partitions on
the new synthetic cohort. This revision has a separate pre-result protocol.

All disconnected held-out cases reach a low objective yet fail relative
geometry recovery (median globally aligned point NRMSE 0.323). Their coarse
systems have no relative information. They do not count as recovery successes.

## Sampled real transfer

The preregistered small fixed-intrinsics samples from Ladybug49, Dubrovnik88
and Venice52 all reach their separately frozen targets, N=3. Automatic v2
nonlinear/fine speeds are **0.795x, 0.682x, 0.774x**, respectively. The nonlinear
and linear coarse curves nearly coincide. These inputs do not demonstrate the
coordinated-region pathology for which the synthetic method helps; paying
eight opening coarse steps mainly adds overhead. All final projections remain
in the valid domain. Packed inputs and exact original indices are preserved.

**Verdict:** retain a reproducible conditional mechanism and useful synthetic
benchmark. Stop automatic promotion: the real-scene gate fails. Eta2 remains
the native GPU incumbent. This does not refute collective methods on large
weakly connected real reconstructions; a decisive future test would first
identify such geometry independently, then charge detection/partition work
in a matched native comparison. Do not select a real test by measured gains.

## Reproduction

A post-result, geometry-only replay additionally measures relative cluster
size using centered point RMS radii, relative to cluster0, without independently
aligning any cluster. All ninety endpoints exactly reproduce their original
costs. Median maximum absolute log-scale error for fine/linear/nonlinear is
0.04552/0.01552/0.004402 on weak bridges and
0.02640/0.007452/0.001510 on strong bridges. Disconnected arms all remain at
0.1583. This size diagnostic can also reflect internal distortion; it is not
a separately fitted similarity. See `t4_relative_scale_audit.json` and
`audit_cluster_scale.py`. Original timing rows were not replaced.

`check_collective.py`; `run_t4.py --split development|held_out`;
`run_t4_transfer.py --size small|larger`; then append `--confidence` for the
separately registered v2, or `--confidence --development` for its development
screen. `run_t4_real.py` freezes feasible reference targets before its paired
runs. All `t4_*.json` files retain curves, candidates, eigenvalues, timings,
failures, partition agreement and single-global-alignment geometry. CPU timings
include setup; no GPU speed comparison or unchanged 9-DOF objective is claimed.
