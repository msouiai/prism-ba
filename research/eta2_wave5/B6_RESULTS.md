# B6: batching PCG reductions and vector updates

## Verdict

The combined implementation is a real practical-panel latency win, but is not
promoted because it changes floating-point vector-update order and the
Final3068 tail cohort follows a slower trajectory.  A second, dots-only
ablation is required before deciding whether the synchronization optimization
can be retained without the trajectory perturbation.

## Frozen intervention

`OCA_W5_CG_BATCH=1` makes two changes inside the champion PCG loop:

1. each pair of independent FP64 cuBLAS dot products writes results to device
   memory and is returned by one 16-byte copy, replacing two host-result calls;
2. the two `x/r` updates and the scale-plus-add `p` update are fused into one
   kernel each.

The operator, preconditioner, forcing rule, controller, candidates, and scored
objective are unchanged.  The inactive derived binary matches the frozen
champion to `4.7e-15` relative endpoint error over the N=3 compatibility gate.

## Practical panel

All 54 rows reached their fixed targets.  Median Schur-product counts were
identical in every cell.  The geometric-mean target-time ratio was **0.9638**,
or a **3.62% speedup**.  Seven of nine cells had timing ranges disjoint in the
active arm's favour; no cell had a disjoint slowdown.

| Cell | Active/control target time | Products, off/on |
|---|---:|---:|
| final-394, 1.005 | 0.991 | 135 / 135 |
| final-394, 1.01 | 0.993 | 86 / 86 |
| final-394, 1.02 | 0.996 | 50 / 50 |
| ladybug-539, 1.005 | 0.881 | 52 / 52 |
| ladybug-539, 1.01 | 1.039 | 42 / 42 |
| ladybug-539, 1.02 | 0.940 | 42 / 42 |
| trafalgar-138, 1.005 | 0.905 | 594 / 594 |
| trafalgar-138, 1.01 | 0.967 | 462 / 462 |
| trafalgar-138, 1.02 | 0.971 | 232 / 232 |

The profile supports a synchronization/launch mechanism.  At the strict
Trafalgar target, Krylov time fell from 0.242 to 0.232 seconds with the same
594 products.  On Muell it fell only from 3.051 to 3.033 seconds with the same
980 products: large Schur products amortise launch latency, so the benefit is
mainly in small and medium systems.

## Larger and tail scenes

Muell retained 3/3 hits and 980 products.  Its median target time moved from
4.2175 to 4.2098 seconds, a small 0.18% improvement.

Venice retained 0/5 hits.  Median endpoint was effectively unchanged
(`246345.32` control, `246335.39` active), with both arms sampling multiple
known trajectory modes.

Final3068 retained 3/5 hits, but conditional median target time moved from
2.746 to 3.930 seconds.  The ranges overlap (`2.233--3.758` versus
`2.808--4.012` seconds), so N=5 does not establish a timing regression, but
the 43% median shift violates the intended systems-only behavior.  The fused
`p = z + beta*p` kernel also changes a two-rounding scale-plus-add into a
compiler-eligible fused multiply-add.  On this basin-sensitive scene that is
enough reason not to promote the combined arm.

## Next ablation

Retain only device-result dot batching and restore all three cuBLAS vector
updates exactly.  It should keep most of the synchronization benefit while
preserving the vector recurrence and its rounding points.  This is registered
and measured as B6v2 rather than selecting a mode from the completed B6 data.

