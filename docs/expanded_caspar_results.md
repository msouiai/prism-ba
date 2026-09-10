# Expanded frozen PRISM versus Caspar FP64 comparison

Timing clarification from the [menu ablation audit](menu_caspar_ablation_results.md): this study’s PRISM harness enabled `OCA_LEARN_LOG`, which adds a blocking norm per scored candidate. These historical times include that instrumentation; they are not logging-free solver timings. The new ablation separates timing runs from diagnostic logging. No historical raw results are replaced.

2026-09-08. Twelve additional local BAL problems; all local instances absent from the preceding nine-scene comparison. This is a local census extension, not independent random recordings. Related BAL variants can overlap. Earlier results use different target protocols and are not pooled into a single speed headline.

Measurement target hits: **PRISM 75/108; Caspar FP64 38/108**. Across 36 scene/target cells: PRISM wins 25, Caspar wins 8, and 3 are unresolved. These cells are not independent scenes.

PRISM's clearest advantage is loose/medium target reachability under these short budgets. PRISM reaches all three repeats on11/12 loose targets and10/12 medium targets, but0/12 tight targets; Caspar reaches7/12,4/12,and1/12 respectively. Tight-target consistency is weak, and references essentially equal to the best pilot endpoint can make certification sensitive to timing and roundoff. Of the nine scene/target cells both methods hit3/3, PRISM is faster in five and Caspar in four. The conditional speed intervals below include parity, and removing a family can reverse the aggregate direction. These results do not establish a general average speed advantage.

The largest problem, Final13682, favors Caspar:8/9 certified hits versus PRISM0/9. PRISM's median tight-run endpoint cost is about11.8% higher. Caspar's one tight miss is only about2e-14 relative above the reference. Ladybug49's PRISM tight misses are also tiny in objective. Zero PRISM restarts occurred, so this batch evaluates fixed-five behavior and does not demonstrate an active recovery benefit.

[Performance profiles](figures/expanded_caspar_profiles.png) · [PDF](figures/expanded_caspar_profiles.pdf)

## Protocol

Both solvers, settings and original inputs are frozen. PRISM v7 is the early-restart candidate with point safeguard and compact FP64 storage. Caspar is the previously precision-verified FP64 COLMAP-generated backend with unchanged driver defaults; it is not full COLMAP reconstruction. Both optimize the same SIMPLE_RADIAL objective, k2 zero, original observations. Every valid endpoint is independently CPU-audited.

One equal-budget calibration run per arm and scene establishes reference = minimum audited endpoint across both arms. Calibration runs do not enter measured timings. Three frozen targets are reference ×1.02 (loose), ×1.005 (medium), ×1.0 (tight). References are short-budget outcomes, not known optima, and can reflect a lucky calibration trajectory. No threshold was adjusted after measurement.

Three repeats per arm/target; seeded scene and target permutation, alternating arm order. Native caps by observation count: <1M four seconds, <3M eight, <6M twelve, otherwise twenty. Process safety timeout180 seconds accommodates data loading/export. Calibration failures remain visible and mark an arm unavailable; measurement failures are retained without retries. Full machine-readable protocol and raw runs are under `/workspace/prism-caspar-expanded/`.

## Results by target level

| Level | PRISM certified hits | Caspar certified hits | PRISM wins | Caspar wins | Ties | Unresolved |
|---|---:|---:|---:|---:|---:|---:|
| loose | 33/36 | 21/36 | 8 | 4 | 0 | 0 |
| medium | 31/36 | 12/36 | 10 | 2 | 0 | 0 |
| tight | 11/36 | 5/36 | 7 | 2 | 0 | 3 |

## Scene family summary

Wins are scene/target cells, combining speed when both consistently hit and reliability otherwise. Related problem variants within a family are not independent recordings.

| Family | Problems | PRISM wins | Caspar wins | Ties | Unresolved |
|---|---:|---:|---:|---:|---:|
| dubrovnik | 2 | 3 | 2 | 0 | 1 |
| final | 5 | 10 | 4 | 0 | 1 |
| ladybug | 1 | 1 | 2 | 0 | 0 |
| trafalgar | 1 | 3 | 0 | 0 | 0 |
| venice | 3 | 8 | 0 | 0 | 1 |

## All time-to-quality results

Times are median native certified stopping-event crossings, shown only when all three repeats hit. Rank hit count first; both3/3 then compare median. Within5% is a descriptive tie. Equal partial success is unresolved. No finite speed ratio for capped misses.

| Scene | Level / target | PRISM hits; seconds | Caspar hits; seconds | Verdict |
|---|---|---:|---:|---|
| ladybug-49 | loose / 13840.00679 | 3/3; 0.094 | 3/3; 0.069 | Caspar 1.37× as fast |
| ladybug-49 | medium / 13636.47728 | 3/3; 0.118 | 3/3; 0.264 | PRISM 2.23× as fast |
| ladybug-49 | tight / 13568.63411 | 0/3; — | 3/3; 3.047 | Caspar (reliability) |
| trafalgar-126 | loose / 106094.4541 | 3/3; 0.276 | 3/3; 1.005 | PRISM 3.64× as fast |
| trafalgar-126 | medium / 104534.2415 | 3/3; 1.237 | 0/3; — | PRISM (reliability) |
| trafalgar-126 | tight / 104014.1707 | 1/3; — | 0/3; — | PRISM (reliability) |
| dubrovnik-88 | loose / 364362.1785 | 3/3; 0.786 | 3/3; 0.319 | Caspar 2.46× as fast |
| dubrovnik-88 | medium / 359003.9111 | 3/3; 2.282 | 3/3; 1.244 | Caspar 1.83× as fast |
| dubrovnik-88 | tight / 357217.822 | 0/3; — | 0/3; — | unresolved |
| dubrovnik-356 | loose / 731175.6635 | 3/3; 1.485 | 0/3; — | PRISM (reliability) |
| dubrovnik-356 | medium / 720423.0802 | 3/3; 4.080 | 0/3; — | PRISM (reliability) |
| dubrovnik-356 | tight / 716838.8858 | 2/3; — | 0/3; — | PRISM (reliability) |
| final-871 | loose / 1972550.51 | 3/3; 3.695 | 3/3; 5.499 | PRISM 1.49× as fast |
| final-871 | medium / 1943542.415 | 3/3; 4.895 | 0/3; — | PRISM (reliability) |
| final-871 | tight / 1933873.049 | 0/3; — | 0/3; — | unresolved |
| final-3068 | loose / 1837450.187 | 3/3; 3.899 | 0/3; — | PRISM (reliability) |
| final-3068 | medium / 1810428.861 | 3/3; 4.661 | 0/3; — | PRISM (reliability) |
| final-3068 | tight / 1801421.752 | 2/3; — | 0/3; — | PRISM (reliability) |
| venice-951 | loose / 2039357.652 | 3/3; 9.005 | 3/3; 9.755 | PRISM 1.08× as fast |
| venice-951 | medium / 2009367.098 | 3/3; 10.593 | 0/3; — | PRISM (reliability) |
| venice-951 | tight / 1999370.247 | 2/3; — | 0/3; — | PRISM (reliability) |
| venice-1672 | loose / 2597056.213 | 3/3; 11.457 | 0/3; — | PRISM (reliability) |
| venice-1672 | medium / 2558864.21 | 3/3; 11.636 | 0/3; — | PRISM (reliability) |
| venice-1672 | tight / 2546133.543 | 0/3; — | 0/3; — | unresolved |
| venice-1778 | loose / 2120172.595 | 3/3; 6.393 | 0/3; — | PRISM (reliability) |
| venice-1778 | medium / 2088993.586 | 3/3; 8.342 | 0/3; — | PRISM (reliability) |
| venice-1778 | tight / 2078600.583 | 1/3; — | 0/3; — | PRISM (reliability) |
| final-1936 | loose / 5150683.315 | 3/3; 3.572 | 3/3; 2.258 | Caspar 1.58× as fast |
| final-1936 | medium / 5074937.973 | 3/3; 3.566 | 3/3; 4.979 | PRISM 1.40× as fast |
| final-1936 | tight / 5049689.525 | 2/3; — | 0/3; — | PRISM (reliability) |
| final-4585 | loose / 7600042.864 | 3/3; 15.043 | 0/3; — | PRISM (reliability) |
| final-4585 | medium / 7488277.528 | 1/3; — | 0/3; — | PRISM (reliability) |
| final-4585 | tight / 7451022.416 | 1/3; — | 0/3; — | PRISM (reliability) |
| final-13682 | loose / 27726129.83 | 0/3; — | 3/3; 14.972 | Caspar (reliability) |
| final-13682 | medium / 27318392.63 | 0/3; — | 3/3; 16.690 | Caspar (reliability) |
| final-13682 | tight / 27182480.23 | 0/3; — | 2/3; — | Caspar (reliability) |

## Size of target misses

The frozen PRISM hook certifies only objective <= target*(1-1e-8), an inward rounding safety margin. Caspar uses its nominal native threshold followed by the CPU endpoint check. This conservative asymmetry can matter for tight references essentially equal to a calibration endpoint. A PRISM state can meet the nominal CPU target without emitting a target-stop event; such a run remains an uncertified miss here. Do not interpret these borderline misses as objective inferiority or claim the stopping event is the mathematical earliest nominal threshold crossing. No solver hooks or thresholds were changed after outcomes.

A strict miss can be numerically tiny or caused by a boundary crossing just after the cap. Report its size before interpreting it as a quality failure. Gaps below use missed runs only. Positive means worse objective than target; negative means the returned endpoint meets the nominal target without a certified stopping event, for example because of the safety margin. No late crossing event was recorded in this batch.

| Scene | Level | Arm | Hits | Median gap among missed runs |
|---|---|---|---:|---:|
| ladybug-49 | tight | restart | 0/3 | 0.000181188% |
| trafalgar-126 | medium | caspar64 | 0/3 | 0.250883% |
| trafalgar-126 | tight | restart | 1/3 | 0.0877317% |
| trafalgar-126 | tight | caspar64 | 0/3 | 0.730776% |
| dubrovnik-88 | tight | restart | 0/3 | 0.203536% |
| dubrovnik-88 | tight | caspar64 | 0/3 | 0.00211749% |
| dubrovnik-356 | loose | caspar64 | 0/3 | 63.9874% |
| dubrovnik-356 | medium | caspar64 | 0/3 | 66.435% |
| dubrovnik-356 | tight | restart | 2/3 | 0.00556139% |
| dubrovnik-356 | tight | caspar64 | 0/3 | 67.2671% |
| final-871 | medium | caspar64 | 0/3 | 0.828046% |
| final-871 | tight | restart | 0/3 | 0.0700587% |
| final-871 | tight | caspar64 | 0/3 | 1.33319% |
| final-3068 | loose | caspar64 | 0/3 | 7.61982% |
| final-3068 | medium | caspar64 | 0/3 | 9.22608% |
| final-3068 | tight | restart | 2/3 | 1.08139% |
| final-3068 | tight | caspar64 | 0/3 | 9.77221% |
| venice-951 | medium | caspar64 | 0/3 | 0.799727% |
| venice-951 | tight | restart | 2/3 | 0.0513223% |
| venice-951 | tight | caspar64 | 0/3 | 1.85832% |
| venice-1672 | loose | caspar64 | 0/3 | 3.70973% |
| venice-1672 | medium | caspar64 | 0/3 | 5.25751% |
| venice-1672 | tight | restart | 0/3 | 0.0105743% |
| venice-1672 | tight | caspar64 | 0/3 | 5.78394% |
| venice-1778 | loose | caspar64 | 0/3 | 3.99122% |
| venice-1778 | medium | caspar64 | 0/3 | 5.54354% |
| venice-1778 | tight | restart | 1/3 | 0.00746956% |
| venice-1778 | tight | caspar64 | 0/3 | 6.0711% |
| final-1936 | tight | restart | 2/3 | -9.49084e-08% |
| final-1936 | tight | caspar64 | 0/3 | 0.170967% |
| final-4585 | loose | caspar64 | 0/3 | 60.5865% |
| final-4585 | medium | restart | 1/3 | 0.0807866% |
| final-4585 | medium | caspar64 | 0/3 | 62.9833% |
| final-4585 | tight | restart | 1/3 | 0.162361% |
| final-4585 | tight | caspar64 | 0/3 | 63.7982% |
| final-13682 | loose | restart | 0/3 | 9.60732% |
| final-13682 | medium | restart | 0/3 | 11.2433% |
| final-13682 | tight | restart | 0/3 | 11.7995% |
| final-13682 | tight | caspar64 | 2/3 | 2.30926e-12% |

## How stable is the signal?

The following ratios include **only scenes where both arms hit all three times at the specified level**; censored scenes are excluded, so these cannot replace the reliability table. Each eligible scene has equal weight. A ratio greater than1 favors PRISM. The 95% bootstrap ranges resample scene-level log ratios10,000 times (fixed seed). They describe this selected sample; they are not population confidence guarantees because scenes are convenience-selected and related within families. N3 also leaves timing uncertainty.

| Target | Eligible scenes /12 | Geometric mean Caspar/PRISM | Descriptive bootstrap range | Leave-one-family-out range |
|---|---:|---:|---:|---:|
| loose | 6/12 | 1.02 | 0.60–1.80 | 0.79–1.22 |
| medium | 3/12 | 1.19 | 0.55–2.23 | 0.87–1.77 |

Family sensitivity excludes each eligible family in turn, not each repeat. If this changes the direction or ranges include1, the aggregate speed verdict remains fragile. Even consistent sample results do not establish performance on unrelated capture domains. A solver comparison also does not isolate the contribution of multi-shift from point repair, damping policy, and other configuration differences.

## Costs, variability, and process wall

Median endpoint costs and measured wall seconds include valid runs even when targets are missed. Crossing ranges include successful repeats only and must be read with the hit counts above.

| Scene | Level | PRISM cost | Caspar cost | PRISM crossing range | Caspar crossing range | PRISM wall | Caspar wall |
|---|---|---:|---:|---:|---:|---:|---:|
| ladybug-49 | loose | 13803.383 | 13799.733 | 0.087–0.095 | 0.061–0.070 | 0.560 | 0.444 |
| ladybug-49 | medium | 13630.306 | 13631.957 | 0.117–0.126 | 0.251–0.267 | 0.577 | 0.558 |
| ladybug-49 | tight | 13568.659 | 13568.634 | — | 2.370–3.409 | 0.753 | 3.360 |
| trafalgar-126 | loose | 105820.049 | 106087.982 | 0.274–0.284 | 0.960–1.016 | 0.833 | 1.380 |
| trafalgar-126 | medium | 104511.551 | 104796.500 | 0.824–1.810 | — | 1.802 | 4.425 |
| trafalgar-126 | tight | 104029.593 | 104774.281 | 3.628–3.628 | — | 4.177 | 4.390 |
| dubrovnik-88 | loose | 363941.563 | 363984.148 | 0.782–0.788 | 0.319–0.339 | 1.488 | 0.880 |
| dubrovnik-88 | medium | 359000.951 | 358851.472 | 2.273–2.285 | 1.221–1.363 | 2.945 | 1.799 |
| dubrovnik-88 | tight | 357944.890 | 357225.386 | — | — | 4.679 | 4.566 |
| dubrovnik-356 | loose | 729396.400 | 1199035.796 | 1.484–1.563 | — | 2.758 | 9.252 |
| dubrovnik-356 | medium | 719261.803 | 1199035.796 | 4.067–4.188 | — | 5.325 | 9.172 |
| dubrovnik-356 | tight | 716698.053 | 1199035.796 | 4.318–5.979 | — | 7.270 | 9.191 |
| final-871 | loose | 1949607.986 | 1968399.648 | 3.675–3.698 | 5.495–5.501 | 5.973 | 7.869 |
| final-871 | medium | 1940561.778 | 1959635.847 | 4.879–5.190 | — | 7.244 | 10.447 |
| final-871 | tight | 1935227.896 | 1959655.297 | — | — | 10.964 | 10.383 |
| final-3068 | loose | 1822317.190 | 1977460.496 | 3.369–3.922 | — | 5.470 | 4.718 |
| final-3068 | medium | 1809693.016 | 1977460.495 | 4.618–5.212 | — | 6.191 | 4.782 |
| final-3068 | tight | 1800157.205 | 1977460.496 | 5.598–6.036 | — | 7.670 | 4.675 |
| venice-951 | loose | 2021599.134 | 2037011.792 | 7.626–9.049 | 8.729–10.418 | 11.903 | 12.715 |
| venice-951 | medium | 2003689.142 | 2025436.550 | 9.185–10.644 | — | 13.660 | 15.115 |
| venice-951 | tight | 1999359.515 | 2036524.856 | 10.814–10.859 | — | 13.920 | 14.947 |
| venice-1672 | loose | 2565335.000 | 2693399.942 | 11.436–11.505 | — | 15.274 | 16.119 |
| venice-1672 | medium | 2546133.053 | 2693396.633 | 11.620–11.676 | — | 15.420 | 15.857 |
| venice-1672 | tight | 2546402.779 | 2693400.350 | — | — | 17.324 | 16.053 |
| venice-1778 | loose | 2100214.815 | 2204793.326 | 6.389–6.437 | — | 10.154 | 15.992 |
| venice-1778 | medium | 2086626.232 | 2204797.706 | 8.311–8.641 | — | 12.233 | 15.978 |
| venice-1778 | tight | 2078730.486 | 2204794.458 | 10.622–10.622 | — | 15.969 | 15.943 |
| final-1936 | loose | 5064074.146 | 5128764.581 | 3.559–3.577 | 2.257–2.260 | 7.204 | 5.968 |
| final-1936 | medium | 5064072.552 | 5072458.172 | 3.561–3.614 | 4.978–4.982 | 7.197 | 8.685 |
| final-1936 | tight | 5049689.458 | 5058322.804 | 11.597–11.631 | — | 15.374 | 16.301 |
| final-4585 | loose | 7534108.331 | 12204642.005 | 14.562–15.066 | — | 21.233 | 26.588 |
| final-4585 | medium | 7494325.718 | 12204642.005 | 16.897–16.897 | — | 26.660 | 26.630 |
| final-4585 | tight | 7452109.784 | 12204642.005 | 16.936–16.936 | — | 26.547 | 26.424 |
| final-13682 | loose | 30389867.880 | 27580841.408 | — | 14.971–14.982 | 43.187 | 35.305 |
| final-13682 | medium | 30389867.880 | 27198720.095 | — | 16.687–16.690 | 43.580 | 37.491 |
| final-13682 | tight | 30389867.880 | 27182480.230 | — | 18.406–18.410 | 42.948 | 39.014 |

Caspar graph setup is outside its native clock; PRISM includes solver-local setup. Process wall also has different diagnostic boundaries: Caspar includes in-driver CPU checks while PRISM independent CPU endpoint audits occur afterward. Native ratios are not fully normalized end-to-end pipeline speedups. All abandoned PRISM restart native work is charged. Native caps can overrun at in-flight solver boundaries; hits still require crossings within cap.

PRISM measurement restarts: 0/108. Valid measurement stages: 216; calibration stages: 24. Measurement native time: 1819.045s; calibration native time: 251.826s; measurement process wall: 2664.790s. These totals omit outer orchestration and independent audit overhead.

## Failures and verification

All calibration and measurement pipelines returned valid, independently audited states.

Checked 240 binary/data manifests against frozen hashes, unchanged PRISM source snapshot, retained best-state hashes, cumulative stage time, and Caspar accepted-cost monotonicity. Maximum endpoint relative audit discrepancy 1.14e-09; maximum Caspar initial/reference discrepancy 3.7e-11; maximum Caspar native/CPU endpoint gap 2.58e-08. All11 older jobs remain paused.

Before valid calibration, target0 was rejected by both drivers before optimization. Those invalid harness invocations are retained in `invalid-zero-target/`; the corrected effectively unreachable positive target1e-100 preserves the intended full-budget calibration. No valid solve outcome informed that correction.

CPU preparation uses an optional content-addressed cache of the original observations and initial score. Creation checks bit-for-bit array equality; reloads check full input, array, and scorer-source hashes. Endpoint scoring is unchanged and cache work is outside both reported timing windows. The first six uncached measurements are retained; the archived original plan differs only by the added cache-location field. No targets or solver settings changed.

Reproduce with `python3 bench/expanded_caspar_screen.py`, then `python3 bench/summarize_expanded_caspar.py /workspace/prism-caspar-expanded`. Existing records are retained on resume. Artifacts include `PROTOCOL.md`, `protocol.json`, `calibration.json`, `measurement-plan.json`, `results.json`, `summary.json`, `verification.json`, and all per-run traces/states/manifests.
