# B6v7: occupancy-gated deterministic preparation

## Interim verdict

The fixed `ncam >= 128` dispatch preserves B6v6's speed and makes Venice52
execute the dots-only path exactly.  It is **8.66% faster** than dots-only on
the nine-cell panel and **4.05% faster** on Muell, with identical stable-cell
work.  The preregistered pooled Final3068 screen is 11/20 hits for gated versus
12/20 for dots.  Because the protocol required no lower pooled hit count, this
one-run deficit prevents immediate promotion and triggers a separately
registered non-inferiority cohort.

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

## Next registered decision

The stable speed evidence is already sufficient.  The remaining decision is a
Final3068 hit-rate non-inferiority test.  A new protocol pools the existing 20
runs per arm, adds 80 per arm without early stopping, and tests a predeclared
15-percentage-point margin using a one-sided 95% Newcombe-Wilson interval.
Until that cohort completes, B6v7 remains the fastest research candidate and
the frozen champion remains unchanged.

Compact evidence: `B6V7_PROTOCOL.md`, `b6v7-registration.json`,
`b6v7-panel-summary.json`, `b6v7-muell-summary.json`,
`b6v7-tails-summary.json`, and `b6v7-final-pooled-summary.json`.
