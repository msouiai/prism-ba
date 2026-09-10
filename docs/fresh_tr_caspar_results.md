# Fresh paired PRISM TR versus Caspar FP64 and FP32

Three fresh runs per arm on five original BAL scenes, including three large scenes up to 28.99 million observations. All arms use the same frozen quality targets. Full settings and timing scopes are in the [protocol](fresh_tr_caspar_protocol.md).

| Scene | PRISM TR FP64 | Caspar FP64 | Caspar FP32 | Winner |
|---|---:|---:|---:|---|
| trafalgar-126 | 0.452 s (3/3) | Miss (0/3) | Miss (0/3) | PRISM TR FP64 |
| dubrovnik-88 | 0.713 s (3/3) | 1.291 s (3/3) | 0.974 s (3/3) | PRISM TR FP64 |
| final-1936 | 3.878 s (3/3) | 4.980 s (3/3) | 2.681 s (3/3) | Caspar FP32 |
| final-4585 | 9.350 s (3/3) | Miss (0/3) | Miss (0/3) | PRISM TR FP64 |
| final-13682 | Miss (0/3) | 16.688 s (3/3) | 2/3 certified; 8.073–8.275 s on successes | Caspar FP64 |

Complete cells show median **native time to the same quality target**, not normalized application latency. The winner column selects the fastest arm with 3/3 certified hits; a faster partially successful arm is reported separately. “Miss” means the target was not certified within that scene’s budget; it is not an observed time-to-target. Budgets are 4 s for Trafalgar/Dubrovnik, 12 s for Final1936, and 20 s for Final4585/Final13682.

Certified targets: **PRISM 12/15; Caspar FP64 9/15; Caspar FP32 8/15**.

## Interpretation

- **trafalgar-126: PRISM TR FP64 wins**; Caspar FP64 does not reach the target consistently; Caspar FP32 does not reach the target consistently.
- **dubrovnik-88: PRISM TR FP64 wins**; 1.81× faster than Caspar FP64; 1.37× faster than Caspar FP32.
- **final-1936: Caspar FP32 wins**; 1.45× faster than PRISM TR FP64; 1.86× faster than Caspar FP64.
- **final-4585: PRISM TR FP64 wins**; Caspar FP64 does not reach the target consistently; Caspar FP32 does not reach the target consistently.
- **final-13682: Caspar FP64 wins**; PRISM TR FP64 does not reach the target consistently; Caspar FP32 does not reach the target consistently.

There is no universal winner. These scenes are selected and only three repeats are available. FP32 is a substantive baseline: qualifying FP32 endpoints are judged on the same original-observation objective, so its wins cannot be dismissed merely because the arithmetic is less precise. This comparison does not demonstrate algorithmic novelty or broad superiority.

## Repeats, endpoint quality and timing scope

| Scene | Arm | Successful crossing range | Median audited endpoint | Median native return | Median process wall |
|---|---|---:|---:|---:|---:|
| trafalgar-126 | PRISM TR FP64 | 0.444–0.503 s | 104487.466827 | 0.456 s | 1.021 s |
| trafalgar-126 | Caspar FP64 | — | 104830.827678 | 4.002 s | 4.422 s |
| trafalgar-126 | Caspar FP32 | — | 105383.811268 | 4.004 s | 4.366 s |
| dubrovnik-88 | PRISM TR FP64 | 0.710–0.713 s | 358942.806676 | 0.717 s | 1.375 s |
| dubrovnik-88 | Caspar FP64 | 1.220–1.337 s | 358969.862067 | 1.291 s | 1.846 s |
| dubrovnik-88 | Caspar FP32 | 0.919–1.027 s | 358975.678309 | 0.974 s | 1.549 s |
| final-1936 | PRISM TR FP64 | 3.875–3.885 s | 5072628.897409 | 3.903 s | 7.578 s |
| final-1936 | Caspar FP64 | 4.976–4.980 s | 5072458.171542 | 4.980 s | 8.836 s |
| final-1936 | Caspar FP32 | 2.680–2.683 s | 5074598.480206 | 2.681 s | 6.151 s |
| final-4585 | PRISM TR FP64 | 9.349–9.380 s | 7419172.637435 | 9.401 s | 15.427 s |
| final-4585 | Caspar FP64 | — | 12204642.005443 | 20.005 s | 26.755 s |
| final-4585 | Caspar FP32 | — | 10637705.490914 | 20.045 s | 26.219 s |
| final-13682 | PRISM TR FP64 | — | 31646871.606401 | 22.678 s | 41.877 s |
| final-13682 | Caspar FP64 | 16.684–16.688 s | 27198720.095457 | 16.688 s | 36.123 s |
| final-13682 | Caspar FP32 | 8.073–8.275 s | 27309193.211629 | 8.073 s | 26.595 s |

Native time includes PRISM solver-local initialization but excludes its CLI upload; Caspar excludes graph setup. Process wall includes different internal CPU audit scopes and is not a normalized end-to-end comparison. Independent Python endpoint audits are outside both clocks. Comparing raw endpoint costs across successful runs is also not a fixed-budget quality comparison, since these runs stop when their target is reached.

For missed targets, audited endpoint excess over target is:

- trafalgar-126, Caspar FP64: median **0.284% above target**.
- trafalgar-126, Caspar FP32: median **0.813% above target**.
- final-4585, Caspar FP64: median **62.983% above target**.
- final-4585, Caspar FP32: median **42.058% above target**.
- final-13682, PRISM TR FP64: median **15.845% above target**.
- final-13682, Caspar FP32: median **-0.034% above target**.

Native caps are checked at solver boundaries. The largest return-time overshoot is **2.682 s**; all spent native work remains in the records. Hits still require a qualifying crossing at or before the requested cap. No speedup is inferred by dividing a cap by a successful solver’s time.

## FP32 and independent verification

All **45 exported endpoints** pass the original-observation CPU audit; maximum disagreement with the driver's CPU score (or PRISM report) is **2.88e-13**. There are **1 uncertified native hits** and **0 process/audit failures**.

FP32's final native score differs from the independently audited original-observation score by up to **0.03941%**. Its largest CPU-audited initial-cost difference from the original double input is **0.00024%**. These are precision/representation effects, separate from auditor agreement. Certification uses the audited endpoint, not the optimistic native value. Every fresh Caspar run logs and verifies its FP32 or FP64 precision.

The verifier checks all three arms occupy each paired-run position once per scene, frozen binary/source/tooling/data hashes, original input and endpoint costs, target certification, and **157** accepted TR feasibility/model-ratio decisions. Caspar generated-code provenance is pinned to COLMAP commit `ed8080bcf42ef0e42d3f5d0cd21eeff0698dfde8`; the solver code is statically linked into the recorded executables. This is the standalone backend driver with COLMAP-default solver settings, not a full COLMAP reconstruction run.

Total measured work: **359.885 native solve seconds**, **631.692 subprocess wall seconds**, across 45 runs. CPU audit time outside the subprocess is additional. No parameter retuning, input modification or replacement reruns occurred within the primary comparison. The separately labelled stopping-margin follow-up below does not replace any primary result.

## Reproduction and artifacts

`bench/fresh_tr_caspar.py` runs the frozen study and resumes only already-completed records. `bench/summarize_fresh_tr_caspar.py`, `bench/verify_fresh_tr_caspar.py`, and `bench/write_fresh_tr_caspar_report.py` reproduce the summary, verification and this report.

All protocols, copied driver sources, precision proof, executable/input hashes, run manifests, logs, CSVs, matrix states, per-run JSON, `summary.json` and `verification.json` are retained under `/workspace/prism-fresh-tr-caspar/`. Solver binaries, production defaults and older paused jobs are unchanged.

## Separate FP32 stopping-margin follow-up

The third unmodified FP32 largest-scene run stopped natively at **6.737 s**, reporting score **27316198**. Its independently audited cost was **27326967.977134**, above the effective target **27318392.358128** by **0.03139%**. It remains a failure of the primary certification criterion; the successful FP32 times above are not averaged with this optimistic stop.

After retaining that failure, three additional FP32 runs on Final13682 used one predeclared adjustment: a native stopping threshold 0.1% below the original effective target. The executable, solver settings, input, 20-second cap and original audited certification target stayed the same. This margin is an empirical screening aid, not a proven error bound or a setting validated on every scene.

The follow-up certified **3/3 targets**, with median native crossing **7.761 s** and range **7.243–8.207 s**. All three endpoints were independently re-audited. This is a supplementary FP32-only check, not a replacement paired comparison or evidence that a stricter threshold itself improves speed; floating-point trajectories varied between runs.

Additional work: **23.210 native seconds**, **78.064 subprocess seconds**. Raw records and frozen amendment are in `/workspace/prism-fresh-tr-caspar/fp32-stop-guard/`; scripts are `bench/caspar_fp32_stop_guard.py` and `bench/verify_fp32_stop_guard.py`.
