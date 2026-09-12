# B6v7 Final3068 non-inferiority result

## Verdict

B6v7 passes the preregistered hit-rate non-inferiority gate and becomes the
wave-5 optimized Eta2 candidate.  At the fixed Final3068 target, the size-gated
camera reduction reaches 100/150 times and dots-only reaches 89/150 times.  The
one-sided 95% Newcombe-Wilson lower bound for `p_gated - p_dots` is -0.01826,
above the registered -0.15 margin.

This establishes non-inferiority at that margin.  It does not establish equal
hit probabilities or superiority: the point estimate is +7.33 percentage
points, while the two-sided Fisher exact test is `p=0.2317`.

## Registered execution

The protocol, binary and original N=20-per-arm rows were hashed and committed
before execution.  The run added 130 fresh rows per arm, alternated arm order,
used no early stop and produced 300/300 valid endpoints with zero nonzero return
codes.  Every source directory and `(arm, repetition)` identifier is unique.

| Metric | Dots | Gated | Gated change |
|---|---:|---:|---:|
| Hits | 89/150 | 100/150 | +7.33 points |
| Hit-rate Wilson 95% | 51.33--66.87% | 58.79--73.71% | — |
| Conditional target median | 3.6685 s | 3.2694 s | **-10.88%** |
| Conditional target range | 1.510--11.087 s | 1.106--6.445 s | — |
| Native wall mean, all runs | 3.7779 s | 3.4234 s | **-9.38%** |
| Native wall median, all runs | 3.5525 s | 3.2859 s | **-7.50%** |
| Endpoint median | 1,743,746.77 | 1,743,660.24 | -0.00496% |
| Products, median | 298.5 | 305.5 | +2.35% |
| Outers, median | 61.0 | 64.5 | +5.74% |
| Rejects, median | 8.0 | 6.0 | -25.0% |

The gated arm is faster despite slightly more median products and outers.  This
is consistent with the fixed-cell attribution: its camera-owned preparation
reduces the Muell point-factor plus RHS bucket from 0.241 to 0.074 s.  Products
and outers on Final3068 are trajectory outcomes, so they are descriptive rather
than isolated kernel-speed evidence.

## Statistical audit

The registered statistic uses one-sided Wilson component bounds with
`z=1.6448536269514722` and Newcombe's difference construction.  The computed
lower bound is -0.018262.  An independent Wald sanity calculation gives
-0.018102, agreeing to 0.016 percentage points.  The result is well separated
from the -0.15 decision boundary.

The initial N=10 and N=20 cohorts pointed in opposite directions.  The final
cohort demonstrates why the larger design was necessary: a scene with a
discrete basin lottery cannot be judged by a handful of endpoints.  Venice's
path-identical N=10 arms also differed by 0.496% at the median, an independent
same-distribution warning against small-sample endpoint claims.

## Decision and scope

The optimized candidate consists of the frozen Eta2 algorithm plus:

1. B6v2 batching of independent FP64 CG dot-result transfers;
2. B6v4 fusion of point factor construction with the first point solve, direct
   equilibration from `H_cc`, and fused reduced-RHS finalization;
3. B6v6 camera-owned, fixed-tree reduced-RHS accumulation without the dead
   Schur diagonal;
4. B6v7 activation of items 2--3 only when `ncam >= 128`.

The threshold is registered for the 22-SM RTX 2000 Ada.  It should be calibrated
from occupancy on another GPU before a cross-hardware production claim.  The
algorithmic Eta2 champion and all original source artifacts remain unchanged.

Evidence: `B6V7_EXTENSION_PROTOCOL.md`, `run_b6v7_extension.py`,
`b6v7-extension-results.json`, `b6v7-extension-summary.json`, and the original
pooled rows in `b6v7-final-pooled-results.json`.
