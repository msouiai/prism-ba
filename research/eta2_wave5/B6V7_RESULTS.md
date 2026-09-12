# B6v7: occupancy-gated deterministic preparation

## Final verdict

The fixed `ncam >= 128` dispatch preserves B6v6's speed and makes Venice52
execute the dots-only path exactly.  It is **8.66% faster** than dots-only on
the nine-cell panel and **4.05% faster** on Muell, with identical stable-cell
work.  The fixed N=150-per-arm Final3068 extension establishes hit-rate
non-inferiority at the preregistered 15-point margin: gated records 100/150
hits versus 89/150, and the one-sided 95% lower bound on the difference is
-1.83 percentage points.  B6v7 is promoted as the **wave-5 optimized Eta2
candidate**.  The frozen scientific champion remains untouched.

## Rule and compatibility

The runtime rule reads only the camera count.  At 128 or more cameras it uses
B6v6's fixed camera-major RHS reduction and dead-diagonal pruning; below 128 it
executes the dots-only preparation.  The threshold was registered from the
22-SM GPU occupancy calculation before the new rows.  Venice52 therefore
takes the control path, while Final3068, Muell and all nine panel cells take the
active path.

The derived dots arm matches the frozen champion to `5.55e-15` relative in the
N=3 compatibility gate.

## Stable speed gates

All 54 panel runs reach their fixed targets.  Every cell retains identical
median products, outers and rejects; endpoint movements are below 0.15%.

| Cohort | Dots median | Gated median | Ratio | Range result |
|---|---:|---:|---:|---|
| Nine-cell geometric mean | — | — | **0.9134** | 9/9 disjoint faster |
| Muell | 4.2006 s | 4.0303 s | **0.9595** | disjoint faster |

The panel result is a fresh cohort and is consistent with B6v6's 0.9177 ratio.
Muell keeps 980 products, 16 outers and zero rejects in every run.

## Tail screen

The fresh N=10 Final3068 draw reverses the preceding B6v6 draw:

| Cohort | Dots | Gated | Conditional target-time median |
|---|---:|---:|---:|
| Fresh B6v7 | 9/10 | 5/10 | 3.419 / 3.511 s |
| Preregistered pooled B6v6+B6v7 | 12/20 | 11/20 | 3.596 / 3.052 s |

The pooled hit-rate difference is -5 percentage points.  It is neither a
meaningful detected loss nor an equivalence result at N=20; it simply fails the
deliberately strict “no lower count” screen.

On Venice52 both arms are path-identical by construction and both score 0/10.
Their independently sampled median endpoints nevertheless differ by 0.496%,
with strongly overlapping ranges.  This is direct evidence that an N=10
median can manufacture an apparent endpoint regression even when the code path
is identical.  Those rows are a same-distribution calibration, not evidence
for or against the gated kernel.

## Final non-inferiority result

The separately committed extension protocol pooled the existing 20 runs per
arm and added 130 fresh runs per arm without early stopping.

| Metric | Dots | Gated |
|---|---:|---:|
| Target hits | 89/150 (59.33%) | **100/150 (66.67%)** |
| Two-sided Wilson 95% interval | 51.33--66.87% | 58.79--73.71% |
| Conditional target-time median | 3.669 s | **3.269 s** |
| All-run native wall mean | 3.778 s | **3.423 s** |
| All-run native wall median | 3.552 s | **3.286 s** |
| Endpoint median | 1,743,746.77 | 1,743,660.24 |
| Products / outers / rejects, median | 298.5 / 61 / 8 | 305.5 / 64.5 / 6 |

The hit-rate point estimate favors gated by 7.33 points, but superiority is not
established (two-sided Fisher `p=0.2317`).  The registered one-sided
Newcombe-Wilson lower bound is -1.826 points, which clears the -15-point margin.
Conditional crossing time is 10.88% lower and mean wall over all runs, including
misses, is 9.38% lower.  Median endpoint movement is -0.00496%.

The final summarizer initially stopped after all 300 valid runs because the
older rows name the work field `matvecs`, not `products`.  Correcting that key
normalization produced the table without rerunning or changing any score.

Compact evidence: `B6V7_PROTOCOL.md`, `b6v7-registration.json`,
`b6v7-panel-summary.json`, `b6v7-muell-summary.json`,
`b6v7-tails-summary.json`, `b6v7-final-pooled-summary.json`,
`B6V7_EXTENSION_PROTOCOL.md`, and `b6v7-extension-summary.json`.
