# Eta2 external coverage and stopping-policy reachability

All registered runs available.

Read [FINDINGS.md](FINDINGS.md) for the completed verdict and [SAME_TARGET_LEDGER.md](SAME_TARGET_LEDGER.md) for the combined baseline table.

Available rows: {'venice': 20, 'storm': 20, 'ceres-storm': 12}. All available rows valid: True.

The original solver and champion remain unchanged. This is a coverage and stopping-policy experiment, not a new champion selection.

The matched local objective is one half the sum of squared reprojection residuals on the original observation set, with a separate focal length and k1 per camera and k2 fixed at zero (SIMPLE_RADIAL). Eta2 stores a nine-coordinate camera block but does not enable --free_k2. This is not the unrestricted two-radial-coefficient BAL model. Caspar32 solves with float data; its ranked endpoint is rescored against the original double observations, as detailed in banked/PROVENANCE.md.

## Venice52: fixed target 243740.27

The two frozen-binary arms alternate at N=10. Champion keeps its original persistent-flatness stop and 600-outer cap. The diagnostic disables OCA_FTOL, raises the outer cap to 10000 and keeps a 60-native-second allowance. Both stop at the identical target.

| Arm | N available | Valid | Hits | Median endpoint | Median native seconds | Median target seconds among hits |
|---|---:|---:|---:|---:|---:|---:|
| champion | 10 | 10 | 0 | 246,309.539651 | 1.546301 | — |
| stop_disabled | 10 | 10 | 0 | 244,929.688826 | 60.007475 | — |

The banked same-host Ceres LM runs reach this target in 4.9353 seconds median (N=3), at accepted iteration 18. Their 36.7203-second median full solve time is not time-to-target. These banked measurements are not new contemporaneous pairs.

Disabling FTOL changes stop-confirmation/backtracking interactions as well as termination. A hit establishes reachability within 1% of the stated Ceres reference; it does not establish the exact Ceres endpoint. A bounded miss does not prove mathematical unreachability.

Claude supplied six MFREE endpoint rows: plain 300-outer median 241637.513 in 30.035 seconds; deep-retry median 241619.703 in 30.104 seconds. Those are collaborator endpoint summaries without crossing traces or exported states, not locally audited target-time measurements.

## Ceres storm coverage and Eta2 fixed targets

Ceres uses the exact banked binary: LM iterative Schur / Schur-Jacobi and dogleg sparse Schur / SuiteSparse, radius 10000, eight threads, 600 iterations, 3600 process seconds, N=3 per profile and scene. Eta2 uses 60 native seconds and 600 outers, N=10. Targets are frozen after each scene has a complete Ceres endpoint stage and before any corresponding Eta2 run, at 1.01 times the lower valid profile median.

| Scene | Arm | N available | Valid | Target hits | Median endpoint | Median native seconds | Median target seconds among hits |
|---|---|---:|---:|---:|---:|---:|---:|
| final-3068 | dogleg-10000 | 3 | 3 | 2 | 1,727,521.766525 | 1,131.099964 | 1,302.742597 |
| final-3068 | lm-10000 | 3 | 3 | 0 | 2,183,295.461330 | 10.714960 | — |
| final-4585 | dogleg-10000 | 3 | 3 | 2 | 7,690,492.465609 | 2,440.845056 | 2,038.777140 |
| final-4585 | lm-10000 | 3 | 3 | 0 | 8,040,781.916690 | 66.825965 | — |
| final-3068 | champion | 10 | 10 | 8 | 1,742,918.320655 | 3.789473 | 3.692232 |
| final-4585 | champion | 10 | 10 | 10 | 7,396,331.320445 | 1.718598 | 1.696919 |

### Exploratory Venice follow-up

Two probes were registered after the first primary misses, N=3 each, 600 outers /60 seconds. These change the trajectory from initialization and do not replace the champion.

| Arm | N available | Valid | Hits | Median endpoint | Median target seconds among hits |
|---|---:|---:|---:|---:|---:|
| probe_relaxed_ftol | 3 | 3 | 0 | 246,040.002116 | — |
| probe_tighter_forcing | 3 | 3 | 0 | 257,725.345472 | — |

probe_relaxed_ftol changes FTOL to1e-7; probe_tighter_forcing disables FTOL and changes the forcing multiplier from2 to0.1. See PROBE_PROTOCOL.md.

The [combined same-target ledger](SAME_TARGET_LEDGER.md) adds every available frozen Caspar32 profile/cap, including misses and full solve times, plus Claude’s MFREE CSV and explicitly incomplete f64 aggregate provenance. Host, endpoint audit, repetition count and crossing-time upper bounds remain labeled separately.

Target times use accepted Ceres callback states, without interpolation; rejected trial objectives are excluded. Timing among successful runs is conditional when any repetitions miss. Endpoints at unlike stops are not interchangeable with matched-target convergence speed. Iteration caps and termination reasons are in runs.csv and the raw logs.

## Claim scope and evidence

The earlier Eta2 three-instance ledger supports fastest among the measured implementations on that panel. Strict endpoint domination of Caspar32 and a universal fastest-BA claim are not supported. See CLAIM_AUDIT.md for the exact table and a counterexample to strict endpoint domination.

The older paused 37/48 sweep tests different A/B/C/D configurations, not Eta2, and remains paused by explicit decision. Optional MegBA integration requires a matched objective adapter and target/state instrumentation; it was inspected, not benchmarked. See EXTERNAL_GPU_FEASIBILITY.md.

The host is RTX 2000 Ada with an AMD EPYC 9354 CPU and a 6.8-core container CPU quota. CPU and GPU measurements are serialized. Native solve seconds exclude input loading and endpoint audit; setup/process seconds remain available separately where the frozen drivers expose them.

Reproduction: PROTOCOL.md, ORDER_NOTE.md, ORDER_NOTE_2.md, run_ceres.py, run_eta2.py and run_ready_storm.py. The second ordering note lets Final3068 run once its own baseline is complete; its target rule is unchanged. Evidence: provenance/, evidence/, runs.csv, all-results.json, summary.json, storm-targets.json when registered. Verification: audit.py. Figures: plot.py. No solver-source modification is part of this experiment.
