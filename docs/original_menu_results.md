# Original-input validation: fixed-five leads the two-scene screen

2026-09-08. **Current winner in this matched original-input screen is fixed-five + point repair on both Dubrovnik173 and Venice52.** It reached both targets in both repeats. This updates the local incumbent ledger, not the default or the broader Caspar verdict.

## Protocol

Same frozen `/workspace/prism-probe-skip/prism-v4` binary for single, fixed-five, and frozen paired; point safeguard mode 1 for every arm; split and repair feedback disabled. Original BAL inputs, original COMMON profile including tau/lambda coupling, and default starting damping were restored. Dubrovnik173 target 375358.1835212728, native cap 6 seconds. Venice52 target 252000, native cap 4 seconds. Two repeats with reversed scene and arm order on repeat 2. Targets and protocol were frozen before runs.

## Time to equal quality

| Scene | Single + repair | Fixed-five + repair | Frozen paired + repair | Current winner |
|---|---:|---:|---:|---|
| Dubrovnik173 | 2.560 s (2/2) | **2.356 s (2/2)** | 3.745 s (2/2) | Fixed-five |
| Venice52 | Miss (0/2) | **2.230 s (2/2)** | 2.558 s (2/2) | Fixed-five |

Values are median native first-target-crossing times, with independently CPU-audited exported endpoints. Single Venice returned at 4.107 seconds median after an in-progress iteration, with cost 254820.88, above the 252000 target. No finite equal-quality ratio against that missing crossing is reported.

On Dubrovnik, fixed-five took 8.0% less time than single (1.09x speedup) and 37.1% less than paired (1.59x). On Venice, it took 12.8% less time than paired (1.15x). These are descriptive two-repeat measurements. Dubrovnik's margin over single is modest, although five was faster in both repeats.

Individual crossings:

- Dubrovnik single: 2.556, 2.563 s; five: 2.254, 2.457 s; paired: 4.896, 2.594 s.
- Venice five: 2.145, 2.315 s; paired: 2.556, 2.559 s; single missed both caps.

Paired's substantial Dubrovnik variability remains material. Do not extrapolate its median slowdown into a universal penalty. Similarly, historical single Dubrovnik timings near 2.36 seconds were from different runs; this table uses simultaneous matched-profile controls instead of mixing phases.

## Work and rejection

| Scene / arm | Median matvecs | Median backtracking evaluations | Median scored candidates |
|---|---:|---:|---:|
| Dubrovnik single | 1096.5 | 46 | 215 |
| Dubrovnik five | 1091 | 25 | 250 |
| Dubrovnik paired | 1648.5 | 56.5 | 373 |
| Venice single, target missed | 3513.5 | 26.5 | 475.5 |
| Venice five | 1770.5 | 13 | 461 |
| Venice paired | 1971.5 | 20 | 500 |

All runs recorded zero outer rejections, although backtracking trials still occurred. Fixed-five reduced backtracking work in both scenes. On Dubrovnik its matrix-vector work was essentially the same as single, while it scored more candidates; total timing is therefore not explained by matrix-vector count alone. On Venice it needed less matrix-vector and candidate-scoring work than paired. This is consistent with the menu sometimes paying for itself through improved progress.

## Validation and artifacts

12 solves consumed **35.254 native solver seconds**. Every independent CPU endpoint audit and monotonic-cost check passed; maximum relative endpoint discrepancy 2.64e-15. Binary/data hashes and exported-state hashes are retained, and original coupling/default initialization flags were verified in every manifest. Eleven older jobs remain paused. No source algorithm change, default change, large-scene run, Caspar run, or push occurred.

Artifacts: `/workspace/prism-original-menu/` contains the frozen protocol and plan, per-run logs/manifests/traces/states/results, `summarize.py`, `summary.json`, `provenance.json`, and `completion.json`.

## Winner ledger and next step

**Fixed-five + point repair is now the leading candidate for these two original scenes.** It is not a universal winner: earlier Ladybug1197 testing found fixed-five target misses, and that counterexample has not been overturned. The present test also did not include the experimental split arm, so its conclusions concern the three configurations listed.

Next, run one short matched counterexample check on Ladybug1197 against frozen paired using its existing target. If fixed-five still fails there, retain scene-specific evidence and investigate an inexpensive online switching rule; do not simply replace the default with fixed-five because it won these two cases. A new Caspar comparison is warranted only after choosing a fixed configuration or a genuinely specified selection rule.
