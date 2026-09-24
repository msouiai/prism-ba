# Comparing the fixed Prism configurations with COLMAP Caspar

This comparison uses the two fixed Prism Config A arms from the retry investigation: the execution-optimized reference, and that same configuration with guarded full-step backtracking. It does not select a different Prism configuration for each scene.

## Verdict at the tested budgets

Guarded Prism achieves a resolved lower final cost than Caspar-f64 at 2,000 iterations on Venice-52, final-3068, and final-4585. Ladybug-1197 is not a resolved quality difference. This is a comparison against fixed COLMAP solver defaults, not a search for Caspar’s best tuning.

| Scene | Guarded Prism median cost | Caspar 2,000 median cost | Prism cost change | Guarded / Caspar solver seconds |
|---|---:|---:|---:|---:|
| venice-52 | 248,721 | 261,915 | -5.04% | 31.199 / 44.785 |
| ladybug-1197 | 366,097 | 366,244 | -0.04% | 25.936 / 56.534 |
| final-3068 | 1,696,154 | 1,977,460 | -14.23% | 260.499 / 3.204 |
| final-4585 | 8,217,450 | 11,456,040 | -28.27% | 51.274 / 310.845 |

**The largest-scene retry improvement matters.** Guarded Prism reaches Caspar’s 11.456-million median final objective in at most **2.874 solver seconds in every repeat**, using conservative timing bounds. Caspar’s 2,000-iteration runs take about **310.845 seconds** and never reach guarded Prism’s 8.217-million median endpoint. Guarded Prism finishes its 60-outers stress test in 51.274 seconds. The reference Prism arm remains at 12.109 million within that same 60-outer budget, worse than extended-budget Caspar; the guarded controller changes this comparison substantially.

**Venice favors Prism at matched quality.** All guarded runs reach Caspar’s median endpoint in at most 2.119 seconds; reference Prism does so in at most 4.993 seconds. Caspar never reaches either Prism median endpoint within 2,000 iterations. Guarded Prism’s endpoint runtime range overlaps Caspar’s, so endpoint medians alone should not be presented as an across-repeat timing win.

**The fast final-3068 Caspar exit is not comparable solution quality.** All six Caspar runs hit the damping-exit threshold, reporting iteration index 40 and cost 1.977 million. Both Prism arms reach that cost within about three seconds and continue to approximately 1.69 million. The original Prism controller remains faster to its own endpoint here: 164.171 seconds versus the guarded arm’s 260.499 seconds, with no resolved quality difference between those Prism arms. Guarded Prism remains opt-in.

**Ladybug has no resolved quality winner.** Caspar reaches the reference Prism median objective in about 21.4–22.6 solver seconds. Its extended 56.534-second endpoint runtime includes continued refinement and should not be treated as time required for reference-Prism quality. Guarded Prism’s median final cost is only 0.04% below extended Caspar’s, below the protocol’s 0.15% quality threshold.

All 24 Caspar runs passed independent initial and final objective checks. Maximum relative errors were 3.71e-11 initially and 3.81e-12 finally. The matched-cost table retains all repetitions, all unreachable targets, both Caspar budgets, and graph-setup-inclusive bounds. Prism controls were reused from earlier runs rather than interleaved with Caspar, and the largest scene uses a bounded 60-outer Prism run, not a full convergence comparison.

## Method

Caspar is the backend vendored by COLMAP at commit `ed8080bcf42ef0e42d3f5d0cd21eeff0698dfde8`, built from its generated f64 sources. COLMAP's normal default is fp32, so this is explicitly a controlled fp64 comparison, not a claim about stock fp32 throughput. The backend is called through a standalone BAL adapter, avoiding changes to observations or the loss from reconstructing a COLMAP database. See the pinned [COLMAP build configuration](https://github.com/colmap/colmap/blob/ed8080bcf42ef0e42d3f5d0cd21eeff0698dfde8/src/thirdparty/CMakeLists.txt) and [Caspar options](https://github.com/colmap/colmap/blob/ed8080bcf42ef0e42d3f5d0cd21eeff0698dfde8/src/colmap/estimators/bundle_adjustment_caspar.h).

Both algorithms minimize `0.5 sum ||residual||²` over every BAL observation, using SIMPLE_RADIAL with a separate focal length and k1 per camera, fixed principal point (0,0), and k2=0. Caspar receives the equivalent camera convention: `R_colmap = diag(1,-1,-1) R_BAL`, flipped translation, and pixels `(u,-v)`. There is no robust loss or track filtering.

Caspar settings follow COLMAP defaults: PCG cap 20, relative error exit 1e-4, initial damping 1, damping minimum 1e-12, up factor 2, down factor 0.333333, and damping exit threshold 1,000. The 200-iteration default and 2,000-iteration extended budget are separate fixed arms; every repeat of both is retained. The optional historical `paper` profile is not used.

Prism uses Config A from `REPRODUCE.md`, plus `OCA_RETRY_CACHE=1`, `OCA_MULTI_RHS=1`, and `OCA_DIAG_NORM=1`. The guarded arm additionally sets `OCA_MENU_BACKTRACK=8`. Both run `--algo mfree_shifted_cg --dof9 --zero_k2`, with a 600-outer budget for Venice-52, Ladybug-1197, and final-3068. The final-4585 comparison uses the prior **60-outer stress-test budget only**. An outer iteration is not equal work between these algorithms.

All results use the RTX 2000 Ada 16 GB GPU, driver 580.126.09, CUDA 12.8.93, Release builds, and sm_89. Caspar retains upstream's `--use_fast_math` build option. GPU runs are serialized through `/tmp/prism_gpu.lock`, and the executable is frozen and hashed before measurement. Three repeats are collected per cell. Ranges are observed sample ranges, not tail estimates.

The Prism controls are the complete retained N=3 results from `/workspace/prism-retries/v4-quality-A` and `/workspace/prism-retries/v4-A60`. Caspar was collected subsequently, not interleaved with those controls. Binary hashes, data hashes, parameters, and control provenance are recorded in the manifests. This is a three-scene full-budget comparison plus one bounded stress test, not the entire reproduction dataset suite.

## Timing and validation

Endpoint runtime alone can reward an early stop at poor quality. The results therefore include both endpoint tables and time to each fixed arm's median final objective. Crossings use exact costs with no tie tolerance, keep missing crossings visible, and charge all untraced solver overhead before the crossing. Caspar crossings are also shown with graph construction/upload/index setup added. File parsing is excluded. Prism's solver clock includes its internal workspace preparation; these are solver benchmarks rather than end-to-end application timings.

Initial objective values are checked against an independent NumPy BAL implementation at relative tolerance 1e-6. Every Caspar run also copies the final state back to the CPU and checks its objective with a separate projection loop at the same tolerance, outside timing. A failed check aborts the run rather than generating a timing claim.

The pinned generated solver declares an `initial_score` result field without assigning it. CMake instruments a build-local copy with that assignment immediately after the existing initial evaluation. This is the only change to generated solver source. Existing verbose iteration records provide accurate internal timestamps and full-precision scores. The pinned solver also never updates its logged `step_accepted` field; the driver infers acceptance from cost decreases. Neither logging correction changes solver decisions. The final damping-exit attempt can occur before iteration logging, so trace length is not reported as a total attempt count.

A quality difference is resolved only if the median difference exceeds 0.15% and the observed ranges are disjoint, following the existing protocol. An iteration-cap exit is not convergence; a damping-threshold exit is also not a proof of convergence. No settings were tuned on individual scenes in this comparison.

## Artifacts

- [Full numerical results and crossings](caspar_comparison_results.md)
- [All 48 per-run endpoints as JSON](caspar_comparison_endpoints.json)
- [Build and reproduction instructions](../bench/caspar/README.md)
- [Caspar measurement harness](../bench/compare_caspar.py)
- [Result summarizer](../bench/summarize_caspar.py)
- Raw logs and per-run JSON: `/workspace/caspar-comparison/runs`
- Frozen executable: `/workspace/caspar-comparison/caspar-f64`
- Source and build provenance: `/workspace/caspar-comparison/source-provenance.json`

