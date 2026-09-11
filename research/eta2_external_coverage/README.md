# Eta2 external coverage and stopping-policy reachability

INCOMPLETE: measurements are still in progress.

Available rows: {'venice': 5, 'storm': 0, 'ceres-storm': 2}. All available rows valid: True.

The original solver and champion remain unchanged. This is a coverage and stopping-policy experiment, not a new champion selection.

## Venice52: fixed target 243740.27

The two frozen-binary arms alternate at N=10. Champion keeps its original persistent-flatness stop and 600-outer cap. The diagnostic disables OCA_FTOL, raises the outer cap to 10000 and keeps a 60-native-second allowance. Both stop at the identical target.

| Arm | N available | Valid | Hits | Median endpoint | Median native seconds | Median target seconds among hits |
|---|---:|---:|---:|---:|---:|---:|
| champion | 3 | 3 | 0 | 247,580.771727 | 1.311550 | — |
| stop_disabled | 2 | 2 | 0 | 244,929.606419 | 60.008840 | — |

The banked same-host Ceres LM runs reach this target in 4.9353 seconds median (N=3), at accepted iteration 18. Their 36.7203-second median full solve time is not time-to-target. These banked measurements are not new contemporaneous pairs.

Disabling FTOL changes stop-confirmation/backtracking interactions as well as termination. A hit establishes reachability within 1% of the stated Ceres reference; it does not establish the exact Ceres endpoint. A bounded miss does not prove mathematical unreachability.

Claude supplied six MFREE endpoint rows: plain 300-outer median 241637.513 in 30.035 seconds; deep-retry median 241619.703 in 30.104 seconds. Those are collaborator endpoint summaries without crossing traces or exported states, not locally audited target-time measurements.

## Ceres storm coverage and Eta2 fixed targets

Ceres uses the exact banked binary: LM iterative Schur / Schur-Jacobi and dogleg sparse Schur / SuiteSparse, radius 10000, eight threads, 600 iterations, 3600 process seconds, N=3 per profile and scene. Eta2 uses 60 native seconds and 600 outers, N=10. Targets are frozen after the complete Ceres endpoint stage and before any corresponding Eta2 run, at 1.01 times the lower valid profile median.

| Scene | Arm | N available | Valid | Target hits | Median endpoint | Median native seconds | Median target seconds among hits |
|---|---|---:|---:|---:|---:|---:|---:|
| final-3068 | dogleg-10000 | 1 | 1 | unregistered | 1,727,521.766525 | 2,003.140477 | — |
| final-3068 | lm-10000 | 1 | 1 | unregistered | 2,183,295.461330 | 11.277017 | — |

Target times use accepted Ceres callback states, without interpolation; rejected trial objectives are excluded. Timing among successful runs is conditional when any repetitions miss. Endpoints at unlike stops are not interchangeable with matched-target convergence speed. Iteration caps and termination reasons are in runs.csv and the raw logs.

## Claim scope and evidence

The earlier Eta2 three-instance ledger supports fastest among the measured implementations on that panel. Strict endpoint domination of Caspar32 and a universal fastest-BA claim are not supported. See CLAIM_AUDIT.md for the exact table and a counterexample to strict endpoint domination.

The older paused 37/48 sweep tests different A/B/C/D configurations, not Eta2, and remains paused by explicit decision. Optional MegBA integration requires a matched objective adapter and target/state instrumentation; it was inspected, not benchmarked. See EXTERNAL_GPU_FEASIBILITY.md.

The host is RTX 2000 Ada with an AMD EPYC 9354 CPU and a 6.8-core container CPU quota. CPU and GPU measurements are serialized. Native solve seconds exclude input loading and endpoint audit; setup/process seconds remain available separately where the frozen drivers expose them.

Reproduction: PROTOCOL.md, ORDER_NOTE.md, run_ceres.py, run_eta2.py. Evidence: provenance/, evidence/, runs.csv, all-results.json, summary.json, storm-targets.json when registered. Verification: audit.py. Figures: plot.py. No solver-source modification is part of this experiment.
