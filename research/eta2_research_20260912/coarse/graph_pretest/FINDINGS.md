# Balanced covisibility coarse-space pre-test

**The graph K8 basis captures a substantial missing camera component at Final3068 witness5 that the geometric K8 basis misses.** This is an economical subspace-coverage result, not a solver, speed, endpoint or target-hit improvement. The existing raw reference direction still fails the nonlinear objective, and its clipped improvement remains tiny.

Protocol: `../../PROTOCOL_01_GRAPH.md`, completed on all three registered Final3068 captures, K8/32/128, three saved arithmetic/reference repetitions per cell. All repeats agree at displayed precision. Original states, directions and geometric reports were preserved; every recomputed geometric legacy fraction matches the earlier report within 1e-11. No GPU or optimizer was run.

## Main comparison

Entries are **projected norm / missing-direction norm**, not squared energy fractions. Primary denominator includes every scaled camera coordinate, including intrinsic coordinates that the rigid basis cannot represent. Here the missing direction is raw certified-reduced reference minus raw Eta2, in captured z=E^-1 dc coordinates. The table uses the explicit intersection with the complement of the seven global similarity modes.

| Witness | Missing norm | K | Geometric gauge-free coverage | Graph gauge-free coverage |
|---|---:|---:|---:|---:|
| Final0 | 2.1083e-10† | 8 | 0.786% | 31.348%† |
| Final0 | 2.1083e-10† | 32 | 48.585% | 53.873%† |
| Final0 | 2.1083e-10† | 128 | 68.684% | 63.672%† |
| Final5 | 0.138977 | 8 | 1.258% | **86.647%** |
| Final5 | 0.138977 | 32 | 94.215% | 92.021% |
| Final5 | 0.138977 | 128 | 95.142% | 92.750% |
| Final6 | 0.122983 | 8 | 1.698% | 12.414% |
| Final6 | 0.122983 | 32 | 13.151% | 17.299% |
| Final6 | 0.122983 | 128 | 31.175% | 41.300% |

†Final0's raw difference is negligible in practical terms and numerically sensitive. Its fraction cannot count as evidence of unresolved useful work. Its equally clipped difference is only 5.3646e-12. The original machine-epsilon null threshold is retained, and a separate 1e-7*max(reference-norm,1) sensitivity disclosure makes this limitation explicit. Final6's equally clipped difference 1.9374e-7 is also marked sensitive; its raw difference is not.

Both directions of change are retained: graph K8 is substantially better on Final5; geometric K32/K128 remains better there. Graph K128 is also worse on Final0, whose ratio is not meaningful evidence. Larger K is not an automatic improvement over the previous basis.

Before removing global similarity, Final5 K8 total coverage is 86.872% graph versus 12.584% geometric; the gauge-free comparison remains 86.647% versus 1.258%, so the new signal is not simply global gauge motion. Its secondary extrinsic-only gauge-free fraction is 88.690%, close to the primary 86.647%. All total/legacy gauge-removed/explicit gauge-free/full-camera/extrinsic-only results and all three direction definitions are retained in `results/`.

## Matched-radius and nonlinear qualification

At Final5, graph K8 captures 86.753% of the equally clipped missing direction, versus 1.101% geometric. However, that missing norm is only 0.00027865 at radius 0.067605: about 0.412% of the radius. Likewise the raw missing norm 0.138977 is about 0.412% of the reference norm 33.70965. Good relative coverage does not mean the baseline lacks a large fraction of its step.

The immutable native witness rows already give the corresponding nonlinear evidence: the raw reference **increases** objective by 205,309.55; the equally clipped reference improves the decrease only from 15.26747 to 15.27792. These are the original witness scores, not new scores of graph-based proposals. The saved full point step has separate accuracy qualifications; reduced residual certification must not be relabeled full-normal exactness.

The other definition, raw reference minus the **actually clipped** Eta2 step, is dominated by the clipping difference. Its Final5 graph K8 gauge-free coverage is 19.598%, below 25%, versus 7.637% geometric. This distinction matters: the high 86.65% number concerns inner-solve error before clipping, not all direction loss from radius truncation.

The user's roughly 25% pre-test is passed by meaningful missing directions, especially Final5 at K8, and Final6 at K128. It supports proposing a graph-space model-usefulness test. It does not justify a native timing arm on its own while ignoring that a near-reference direction was already nonlinearly unhelpful. The previous geometric negative must remain scoped to its actual basis; the graph positive must remain scoped to coverage.

## What changed in the partition

The original BAL has 3,068 cameras, 310,854 points and 1,653,812 observations. All incidences are distinct here. The exact integer covisibility graph contains 989,046 undirected edges with total weight 28,340,354, one connected component and zero isolates. Thus this scene has no disconnected-component similarity ambiguity beyond the seven reported global geometric modes.

| Requested K | Graph cluster size range | Graph rank | First-anchor cross observations | Weighted edge cut | Partition CPU seconds |
|---|---:|---:|---:|---:|---:|
| 8 | 372–395 | 56 | 505,519 | 12,921,728 | 0.0799 |
| 32 | 92–98 | 224 | 874,532 | 22,152,048 | 0.1761 |
| 128 | 23–24 | 896 | 1,138,949 | 26,555,441 | 0.6939 |

Graph labels depend only on original incidence and are identical across all witnesses. The K8 geometric partition instead contains a 3,058-camera group, six singleton groups and a four-camera group; its rank is 50. Its first-anchor cross-observation count is 395 at Final5 and 582 at Final0/6. This explains why the old K8 nonlinear passenger/coarse test involved only a tiny set of connecting observations. Balanced graph K8 addresses genuinely distributed groups, although balancing also increases the cut substantially. This is not evidence that every balanced cluster boundary is a physically soft mode.

Each point's anchor for the observation count is its first observation in original BAL order. Weighted edge cut counts shared-point camera pairs and is a different quantity. Counts of all observations on multicluster tracks are also stored separately.

## Verification, cost and reproduction

Synthetic tests establish exact integer shared-point counts including duplicate incidences, weighted cut, deterministic same-seed partition, disconnected/isolated handling, and gauge-free projector equivalence to an independent dense null-space construction. Maximum dense-projector discrepancy was 1.68e-15; idempotence and gauge errors were below 2.77e-15. On real witnesses, all graph blocks retained seven modes and seven global constraints were removed. Maximum basis finite-difference/closed-form discrepancy was 1.67e-11; maximum global containment error was 7.05e-11.

The exact graph required 23.75MB of CSR storage and 0.3343s construction time. The complete diagnostic, including all three partitions, file loading/hashing, all nine graph/geometric cell pairs and reference projections, took 5.113s on one CPU thread, with peak RSS 414,448KiB. These are diagnostic setup costs, not native solver speed results. Any later native use must charge graph construction and partition overhead.

Dependency/API provenance is in `dependencies/`; source/protocol/input hashes are in `results/manifest.json`, graph/labels in `results/graph.json`, and compact comparisons in `results/summary.json`. The pinned wheel is isolated under campaign `build/deps`; no system package changed.

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python3 research/eta2_research_20260912/coarse/graph_pretest/test_core.py
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python3 research/eta2_research_20260912/coarse/graph_pretest/run.py
```

The runner refuses to overwrite existing results. No new native graph-coarse arm has been implemented or launched.
