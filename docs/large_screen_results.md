# Short large-scene BA screen

One run per cell; no statistical verdict. PRISM: 20-outer cap, existing eight-probe backtracking. Caspar: FP32 default, iteration caps [200].
All jobs share the GPU lock; PRISM timeout 60 seconds, Caspar timeout 60 seconds. Unequal iteration budgets compare early progress, not equal work or full convergence.
Caspar endpoints are CPU-fp64 checked against original observations; PRISM initial costs are independently checked. PRISM final costs are its fp64 solver scores.

| Scene | Method | Status | Iterations | Seconds | Final cost | Rejects | Rescues | Rearms |
|---|---|---|---:|---:|---:|---:|---:|---:|
| final-4585 | caspar32-default-200 | completed | 200 | 13.951 | 11,035,787.515 | — | — | — |
| final-4585 | multi | completed | 20 | 11.711 | 8,492,146.726 | 0 | 17 | 0 |
| final-4585 | rearm | completed | 20 | 11.721 | 8,492,146.679 | 0 | 17 | 0 |
| final-4585 | single | completed | 20 | 8.286 | 8,842,123.085 | 0 | 13 | 0 |

## Cost-matched comparison

Conservative PRISM time to Caspar's checked endpoint. All untraced solver time is charged before crossing.
The Caspar column certifies its endpoint only, not its unknown first crossing.

| Scene | PRISM arm | PRISM seconds to Caspar endpoint | Caspar full seconds | Caspar final cost at/below PRISM endpoint? |
|---|---|---:|---:|---|
| final-4585 | rearm | 2.8774 | 13.9507 | no |
| final-4585 | multi | 2.8717 | 13.9507 | no |
| final-4585 | single | 4.5779 | 13.9507 | no |

## Interpretation

All four planned runs completed without failure or timeout, in 45.67 seconds
of summed solver time; input loading and initial CPU checks are additional.
The scene has 4,585 cameras, 1,324,582 points and 9,125,125 observations.

At the short budgets, guarded multi-shift reached 23.05% lower final cost than
Caspar FP32 in 11.71 versus 13.95 seconds. It reached Caspar's checked endpoint
cost after approximately 2.87 seconds. This is Caspar's full runtime, not its
unknown first-crossing time. Against guarded single shift, multi-shift reached
3.96% lower cost but took 11.71 versus 8.29 seconds.

All PRISM runs had zero rebuild retries. However, multi-shift needed 17
backtracking rescues in 20 outers, versus 13 for single shift. Thus the safeguard
is doing much of the acceptance work; the unscaled lambda menu is not generally
succeeding on its own. Rearming never activated, and the two multi-shift runs
had nearly identical costs and runtimes. This does not test the rearming fix's
late-iteration benefit.

One repeat and a 20-outer cap establish only an early-progress observation.
No full-convergence, statistical speedup or publication verdict follows.
No additional runs were launched, and the broad study stays paused.
All PRISM initial costs match the independent fp64 scorer within relative 1e-6;
traces are monotone and both frozen binary hashes are unchanged. These checks
are not independent final-state audits of PRISM.

Exact manifests and raw artifacts: `/workspace/prism-large`. The harnesses are
`bench/medium_screen.py`, `bench/novelty_external.py` and
`bench/summarize_medium_screen.py` (with an explicit title and manifest-derived
iteration budgets).
