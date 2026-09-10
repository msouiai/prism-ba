# Current PRISM versus Caspar: quality-dependent verdict

Timing clarification from the [menu ablation audit](menu_caspar_ablation_results.md): this study’s PRISM harness enabled `OCA_LEARN_LOG`, which adds a blocking norm per scored candidate. These historical times include that instrumentation; they are not logging-free solver timings. The new ablation separates timing runs from diagnostic logging. No historical raw results are replaced.

2026-09-08. **PRISM wins strict-target reliability on these three scenes, but Caspar FP64 is faster on Ladybug at a target 1% looser.** The result supports a speed/quality tradeoff, not a universal PRISM speedup. The main PRISM candidate below is the previously frozen early-restart rule, not a per-scene best-of-arms selection.

## Verified comparison

Original Ladybug1197, Dubrovnik173, and Venice52 inputs; SIMPLE_RADIAL, fixed principal point, k2 zero, all original observations and independent CPU endpoint costs. PRISM uses frozen v7 and point repair. Three PRISM arms—fixed-five, paired, early restart—were fixed before runs. Caspar uses the vendored COLMAP-generated backend directly, not the full COLMAP reconstruction pipeline, with driver default settings: PCG maximum20, initial diagonal1, diagonal-down factor0.333333, relative CG tolerance1e-4. The alternative paper settings were not selected.

Caspar FP64 is the precision-matched baseline. FP32 is a separate labelled comparison and must not be mixed into the FP64 column. Two repeats per arm, reverse scene/arm order on repeat2, interleaved across solvers. Native caps: six seconds on Ladybug/Dubrovnik, four on Venice. The original strict targets were fixed before the runs.

## Strict targets: all PRISM configurations reported

| Scene / target | PRISM fixed-five | PRISM paired | PRISM restart rule | Caspar FP64 | Caspar FP32 |
|---|---:|---:|---:|---:|---:|
| Ladybug1197 / 366600 | Miss (0/2) | 3.051 s (2/2) | 2.911 s (2/2) | Miss (0/2) | Miss (0/2) |
| Dubrovnik173 / 375358.183521 | 2.299 s (2/2) | 4.891 s (2/2) | 2.554 s (2/2) | Miss (0/2) | Miss (0/2) |
| Venice52 / 252000 | 2.345 s (2/2) | 2.589 s (2/2) | 2.362 s (2/2) | Miss (0/2) | Miss (0/2) |

Values are median native first-target crossings. Restart times charge the entire abandoned first solve. A target hit also requires the exported final state to satisfy the same target under independent CPU scoring. PRISM paired and the frozen restart rule each reached6/6 strict targets; fixed-five reached4/6. Neither Caspar precision reached a strict target in this screen.

The restart rule's small Ladybug timing lead over paired in this particular pair of repeats is not evidence that doing extra work is intrinsically faster. The independent paired trajectories vary; earlier matched tests found paired faster there. Fixed-five remains the practical low-overhead contender on Dubrovnik/Venice, while the restart candidate avoids its Ladybug failure in this development set.

### How close was Caspar?

| Scene | FP64 median final CPU cost | Above strict target | FP32 median final CPU cost | Above strict target |
|---|---:|---:|---:|---:|
| Ladybug1197 | 366926.49 | 0.089% | 484812.71 | 32.25% |
| Dubrovnik173 | 377407.28 | 0.546% | 378143.36 | 0.742% |
| Venice52 | 273110.27 | 8.38% | 278636.93 | 10.57% |

FP64 runs reached the native cap. FP32 Ladybug stopped at the diagonal exit condition after about0.283 seconds; the other FP32 runs reached their caps. Near-target Ladybug/Dubrovnik misses must not be described as large quality failures. Because those crossings were not observed, **no finite equal-quality speed ratio against Caspar is reported for the strict targets**.

## Sensitivity: targets exactly 1% looser

After observing the first strict FP64 results, an explicitly exploratory sensitivity check was frozen: multiply each original target by1.01, compare only the already frozen PRISM restart rule against Caspar FP64, retain the same caps, and run two repeats. This check is post-observation, not part of the original predeclared screen. It does not replace or retune the strict targets.

| Scene / relaxed target | PRISM restart | Caspar FP64 | Native-time verdict |
|---|---:|---:|---|
| Ladybug1197 / 370266 | 1.098 s (2/2) | **0.637 s (2/2)** | Caspar 1.72x as fast |
| Dubrovnik173 / 379111.765356 | **1.775 s (2/2)** | 3.323 s (2/2) | PRISM 1.87x as fast |
| Venice52 / 254520 | **1.487 s (2/2)** | Miss (0/2) | PRISM alone reaches target |

This changes the Ladybug verdict materially: Caspar quickly reaches a slightly looser objective, then makes slow progress toward the strict target. On Dubrovnik, PRISM wins the measured looser target race as well as strict-target reliability. Venice remains the strongest quality separation in this sample. These are objective thresholds, not externally measured reconstruction accuracy.

## Timing boundaries and process overhead

The table ratios above are explicitly **native solver-time ratios**. Caspar's graph allocation/index construction occurs before its native solve clock; its median setup in the relaxed runs was0.234 seconds Ladybug,0.257 Dubrovnik,0.203 Venice. PRISM's target clock includes its solver-local setup, but both programs also do work outside their native clocks. Do not interpret these ratios as fully normalized end-to-end pipeline speedups.

Measured relaxed-run process wall through returned/exported endpoints:

| Scene | PRISM restart wall | Caspar FP64 wall |
|---|---:|---:|
| Ladybug1197 | 3.027 s | 1.351 s |
| Dubrovnik173 | 2.717 s | 4.065 s |
| Venice52 | 2.123 s | 4.539 s, target missed |

The Ladybug restart pays for two launches and loads. Caspar wall also includes its in-driver CPU diagnostic checks, whereas the independent PRISM endpoint audits occur afterward. Thus wall values are useful operational measurements, but not perfectly identical instrumentation boundaries. Their winner ordering here agrees with the native relaxed-target comparison. Native caps are not strict process-wall deadlines.

## Precision and objective checks

The pinned generated backend corresponds to COLMAP commit `ed8080bcf42ef0e42d3f5d0cd21eeff0698dfde8`. Verified488 FP64 generated source files against the retained manifest; the sole existing solver-source difference was the checked initial-score assignment, verified exactly. The cached FP64 archive was copied; only its host solver object was replaced with initial-score/budget instrumentation. All241 other archive members were verified byte-for-byte unchanged. Upstream compiled kernel options, including `--use_fast_math`, were retained.

The checked FP64 driver is derived from the checked FP32 driver with double state/factor types, preserving the camera mapping and driver parameters. Binary symbols confirm float versus double `SetPointNodesFromStackedHost` interfaces. Constructor parameter templates alone would not establish precision, because the FP32 backend accepts converted parameter objects. An FP64 smoke run passed independent exported-state auditing before comparisons.

All FP64 initial native scores agreed with the independent original-input reference within1.40e-11 relative; initial CPU diagnostic scores within4.01e-11. The maximum external CPU endpoint discrepancy against the driver-reported CPU cost across both phases was1.18e-10. These checks distinguish state-export correctness from native-scoring agreement.

FP32 Ladybug's native score differed from the raw-depth CPU endpoint objective by about6.08%; FP32 Venice's maximum gap was about0.0192%, and Dubrovnik's below1e-6 relative. Therefore FP32 native scores are not substituted for audited objective values. This screen does not isolate the source of that FP32 scoring discrepancy or justify generalizing it to every Caspar configuration.

Budget instrumentation only stops work before an iteration or before committing an over-budget candidate. Target instrumentation uses Caspar's native score exit threshold, but a native crossing counts only if its exported CPU-audited endpoint also qualifies. No damping, CG, or kernel tuning was performed after outcomes were observed.

## Cost, artifacts, and reproduction

The strict and relaxed phases contain42 pipelines and46 solver stages, totaling **135.827 native solver seconds**. An additional one-iteration FP64 smoke solve took about0.015 seconds. All exported endpoints in the comparisons passed independent CPU audits; native best-cost traces were checked for monotonicity. Binary/data/state hashes, precision symbols, kernel-archive verification, initial scores, exit reasons, stage budgets, and raw traces are retained. Eleven old jobs remain paused. No PRISM default change or push occurred.

Artifacts are under `/workspace/prism-caspar-current/`; `relaxed/` contains the separate sensitivity study. Main files: `PROTOCOL.md`, `plan.json`, `results.json`, `summary.json`, `precision-proof.json`, `archive-proof.json`, `smoke-audit.json`, `provenance.json`, and `completion.json`. The source additions are `bench/current_caspar_comparison.py` and `bench/caspar/caspar_bal64_checked.cc`.

`bench/caspar/CMakeLists.txt` now exposes `CASPAR_DRIVER_CHECKED_DOUBLE=ON` for rebuilding the checked FP64 target/export driver against generated/f64. It is mutually exclusive with `CASPAR_DRIVER_FLOAT`. Configuration of that target was checked; this benchmark reused the verified cached kernels to avoid rebuilding them. The exact benchmark host source/object and archive are retained in `build64/`.

## Verdict

**PRISM is competitive and has a meaningful tighter-target advantage on this small selected sample, especially Venice. Caspar remains strong for a looser Ladybug objective.** The targets and scenes come from the existing PRISM investigation, and there are only two repeats per arm. These results are not a universal superiority claim, a new publication verdict, or a replacement for the earlier precision-related retractions.

The next decisive study should freeze multiple objective levels before running additional scenes and compare full time-quality curves with explicitly aligned timing scopes. Keep FP64 and FP32 columns separate, and keep the PRISM rule fixed rather than reporting an oracle best-of-configurations result.
