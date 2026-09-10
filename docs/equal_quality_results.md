# Time to equal quality — 2026-09-07

Actual first accepted target-crossing times for the four frozen PRISM variants.
This replaces inference from fixed-budget endpoint costs with shared quality
thresholds and fresh N=3 repeats. All use the compact FP64 mode2 layout and the
same existing alpha/backtracking/rearm settings. No Caspar reruns here.

Targets were frozen before runs: the lowest median CPU cost among the four
previous demand-screen arms, rounded upward to the next 100. Every method
must reach the same threshold on a scene. N=3, rotated/reversed method order;
normal convergence stops remain enabled. A method stopping above target is a
miss, even if its budget is unused. A crossing after the cap is also a miss.

| Scene | Common CPU cost target | Native time cap |
|---|---:|---:|
| ladybug-1197 | 366,600 | 6 s |
| venice-52 | 252,000 | 8 s |
| dubrovnik-356 | 723,500 | 16 s |

## Target crossing speed

Seconds are medians only when all three repeats reached the target within the
cap. Speedup = baseline median / method median (>1 is faster). No ratio is
reported when either method has a miss; misses are not replaced by cap times
or dropped to manufacture a successful-run median speedup.

| Scene | Method | Hits | Median crossing s | Successful crossing range s | Speedup vs fixed multi | Speedup vs single |
|---|---|---:|---:|---:|---:|---:|
| ladybug-1197 | single | 3/3 | 3.8956 | 2.7438–4.6682 | — | 1.000× |
| ladybug-1197 | multi | 0/3 | — | — | — | — |
| ladybug-1197 | demand | 3/3 | 2.3279 | 2.2484–2.4808 | — | 1.673× |
| ladybug-1197 | pair | 3/3 | 2.8365 | 2.0132–3.1287 | — | 1.373× |
| venice-52 | single | 0/3 | — | — | — | — |
| venice-52 | multi | 2/3 | — | 4.9166–5.6486 | — | — |
| venice-52 | demand | 0/3 | — | — | — | — |
| venice-52 | pair | 2/3 | — | 2.5253–2.9540 | — | — |
| dubrovnik-356 | single | 0/3 | — | — | — | — |
| dubrovnik-356 | multi | 2/3 | — | 3.5378–3.5435 | — | — |
| dubrovnik-356 | demand | 0/3 | — | — | — | — |
| dubrovnik-356 | pair | 0/3 | — | — | — | — |

A successful range for a partially successful arm is descriptive only; its
median and speedup remain unreported. Three repeats remain a small screen,
not a confidence interval or a claim of universal superiority. Discrete
accepted steps may overshoot a quality threshold downward; that is legitimate
attainment of at least the common requested quality.

## Every run, including misses

| Scene | Arm | Rep | Hit | Crossing s | Final CPU cost | Solve including cleanup s | Stop |
|---|---|---:|---|---:|---:|---:|---|
| dubrovnik-356 | demand | 1 | False | — | 750,474.615 | 16.0799 | budget |
| dubrovnik-356 | demand | 2 | False | — | 750,493.230 | 16.1018 | budget |
| dubrovnik-356 | demand | 3 | False | — | 750,474.666 | 16.0960 | budget |
| dubrovnik-356 | multi | 1 | False | — | 725,831.915 | 16.2545 | budget |
| dubrovnik-356 | multi | 2 | True | 3.5378 | 718,748.917 | 3.5479 | target |
| dubrovnik-356 | multi | 3 | True | 3.5435 | 718,174.389 | 3.5699 | target |
| dubrovnik-356 | pair | 1 | False | — | 751,399.385 | 16.0201 | budget |
| dubrovnik-356 | pair | 2 | False | — | 751,399.385 | 16.0438 | budget |
| dubrovnik-356 | pair | 3 | False | — | 751,399.385 | 16.1284 | budget |
| dubrovnik-356 | single | 1 | False | — | 745,136.036 | 16.2712 | budget |
| dubrovnik-356 | single | 2 | False | — | 744,262.105 | 16.0903 | budget |
| dubrovnik-356 | single | 3 | False | — | 744,304.881 | 16.2009 | budget |
| ladybug-1197 | demand | 1 | True | 2.4808 | 366,576.133 | 2.4870 | target |
| ladybug-1197 | demand | 2 | True | 2.2484 | 366,592.589 | 2.2634 | target |
| ladybug-1197 | demand | 3 | True | 2.3279 | 366,557.398 | 2.3344 | target |
| ladybug-1197 | multi | 1 | False | — | 367,130.559 | 6.0766 | budget |
| ladybug-1197 | multi | 2 | False | — | 367,004.616 | 6.4637 | budget |
| ladybug-1197 | multi | 3 | False | — | 367,001.619 | 6.1416 | budget |
| ladybug-1197 | pair | 1 | True | 2.0132 | 366,575.395 | 2.0196 | target |
| ladybug-1197 | pair | 2 | True | 2.8365 | 366,583.488 | 2.8429 | target |
| ladybug-1197 | pair | 3 | True | 3.1287 | 366,568.173 | 3.1359 | target |
| ladybug-1197 | single | 1 | True | 3.8956 | 366,563.461 | 3.9017 | target |
| ladybug-1197 | single | 2 | True | 2.7438 | 366,595.440 | 3.1897 | target |
| ladybug-1197 | single | 3 | True | 4.6682 | 366,590.478 | 4.6998 | target |
| venice-52 | demand | 1 | False | — | 266,028.742 | 8.0086 | budget |
| venice-52 | demand | 2 | False | — | 267,417.101 | 8.1169 | budget |
| venice-52 | demand | 3 | False | — | 269,208.071 | 8.0187 | budget |
| venice-52 | multi | 1 | True | 4.9166 | 251,941.581 | 4.9258 | target |
| venice-52 | multi | 2 | True | 5.6486 | 251,928.634 | 5.6537 | target |
| venice-52 | multi | 3 | False | — | 258,614.977 | 8.4296 | budget |
| venice-52 | pair | 1 | True | 2.5253 | 251,721.395 | 2.5544 | target |
| venice-52 | pair | 2 | True | 2.9540 | 251,522.266 | 2.9889 | target |
| venice-52 | pair | 3 | False | — | 252,015.772 | 8.0658 | budget |
| venice-52 | single | 1 | False | — | 256,873.848 | 8.1086 | budget |
| venice-52 | single | 2 | False | — | 257,548.684 | 8.0080 | budget |
| venice-52 | single | 3 | False | — | 255,778.950 | 8.1300 | budget |

## Measurement and checks

The only new solver change is opt-in `OCA_TARGET_COST`. It checks initial and
accepted states, stops at objective <= target*(1-1e-8), and records time from
native solver entry before cleanup/state export. The inward margin protects
against threshold rounding. A separate CPU evaluator verifies the exact
exported state is <= the common target and agrees with the reported GPU
objective within 1e-7 relative. Earlier accepted trace states are checked to
be above the internal threshold; all traces are finite and monotone. State,
input and frozen binary hashes are retained. This is native solve time, not
parsing/CPU-audit/end-to-end latency.

A saved narrow fallback computed before a deadline may commit after expanded
work finishes late; if its actual crossing time exceeds the cap, this study
counts it as a miss. No late expanded candidate is credited.

CLI/core builds pass. Hook smoke tests cover an already-satisfied initial
state, first crossing during a solve, and a missed target under a time cap,
with CPU checks and earlier-trace checks. Feature-off smoke cost agrees with
the previous frozen solver within the declared 1% atomic-order trajectory
screen (observed difference about 0.00015%). No algorithm parameters were tuned.

The selected target is based on prior observations, so this is follow-up
validation on previously investigated scenes, not held-out generalization.
No speedup is inferred from unequal endpoint quality or nominal time budgets.
All runs and misses remain in the summary. Broader runs remain paused;
solver/controller defaults are unchanged and nothing has been pushed.

Artifacts: `/workspace/prism-equal-quality/` (protocol, targets, frozen source
and binary, manifests, logs, traces, exact states, result rows and summary).
Driver: `bench/equal_quality_screen.py`; report: `bench/summarize_equal_quality.py`.
The controller implementation and prior fixed-budget ablation are documented
in [demand-menu results](demand_menu_results.md).
