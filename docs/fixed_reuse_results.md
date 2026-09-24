# Fixed-system comparison: ordinary CG versus Krylov reuse

**The confirmation gate failed.** Selective reuse won on one of four eligible fixed systems and was slower on the other three. We did not run another end-to-end confirmation or change the selective rule. The current reuse direction remains parked and off by default; reducing redundant nonlinear candidate evaluation is the next priority.

## Collection and comparison

Eight real systems were collected: the first one shallow, two eligible-depth and one near-capacity expansion encountered on each of Ladybug-49 and Ladybug-1197. Collection continued the ordinary paired-demand controller, so reuse did not choose the collection trajectory. No systems were selected by timing. Both scenes filled their quotas; the planned fallback scene was unnecessary.

Each snapshot persists the actual matrix-free operator inputs, RHS and damping metadata. Within a snapshot, all methods use the same live operator and RHS without changing nonlinear state. GPU reductions remain subject to roundoff. Source depth means the number of retained directions, capped at 64; it is not necessarily the entire original narrow CG iteration count.

Three methods were compared, N=3 rotated-order repeats after an unreported warmup of each method:

1. Ordinary narrow CG followed by ordinary wide multi-shift CG.
2. Narrow CG with capture followed by always-on reuse, with ordinary CG fallback when necessary.
3. Narrow CG with capture followed by the frozen selective rule (eligible retained depths 11–32), otherwise ordinary CG.

The narrow solve is replayed inside every timed trial, charging capture copies and their overhead. Timings also include allocation/deallocation, import, basis extension, projected checkpoint reconstruction, required residual checks and any fallback. Per-trial allocations are charged in full; production amortizes some buffers across nonlinear iterations. These are fixed linear-system timings, not end-to-end BA latency.

All five expanded systems must satisfy the snapshot's actual inherited forcing tolerance. CG is capped at 128 iterations and the retained basis at 64 vectors. Ordinary CG is also checked against its true residual, but its diagnostic-only certification time is subtracted from the comparison time; production ordinary CG does not pay that cost. The same subtraction applies on skipped/fallback CG paths. Required projected-solve verification remains charged. Total times including diagnostic certification are also retained in the raw results.

Selective history starts with an empty cooldown on each independent system. This tests the frozen depth rule, not performance across a nonlinear history. The ordinary certification gate permits 1e-8 relative numerical slack around the target; projected qualification retains its strict production threshold. No speed ratio is reported if any repeat of either compared method fails certification.

## Per-system results

Median charged milliseconds, including the narrow solve. Ordinary/selective greater than 1 favors selective. Category and outer iteration identify the saved system.

| Scene | Outer | Retained depth | Ordinary CG | Always reuse | Selective | Ordinary/selective | Selective action |
|---|---:|---:|---:|---:|---:|---:|---|
| ladybug-49 | 21 | 64 | 27.938 | 39.659 | 25.894 | 1.079× | Skip: capacity |
| ladybug-49 | 29 | 17 | 4.711 | 6.292 | 5.906 | 0.798× | Reuse |
| ladybug-49 | 35 | 20 | 4.805 | 6.747 | 6.723 | 0.715× | Reuse |
| ladybug-49 | 36 | 9 | 2.579 | 4.194 | 3.027 | 0.852× | Skip: shallow |
| ladybug-1197 | 16 | 12 | 36.972 | 45.399 | 42.506 | 0.870× | Reuse |
| ladybug-1197 | 19 | 16 | 47.277 | 35.276 | 35.338 | 1.338× | Reuse |
| ladybug-1197 | 27 | 9 | 26.646 | 23.871 | 27.594 | 0.966× | Skip: shallow |
| ladybug-1197 | 38 | 64 | 286.479 | 309.659 | 287.987 | Not certified | Skip: capacity |

The near-capacity Ladybug-1197 system failed certification for all three methods in all repeats. Its target relative residual was 0.5, while the final true residuals were around 2.6–2.7. The table shows the spent time, not a successful solution time. Limits were not increased after this result.

The apparent gain on the near-capacity Ladybug-49 system is not a reuse gain: selective skipped import and ran ordinary CG. Replayed narrow/wide solves varied around 100–102 iterations and timing varied between methods. This illustrates why small N=3 differences should not be interpreted as precise performance guarantees.

## Eligible cases: the decisive comparison

| Scene / retained depth | Selective result versus ordinary |
|---|---|
| ladybug-49 / 17 | 25.4% slower |
| ladybug-49 / 20 | 39.9% slower |
| ladybug-1197 / 12 | 15.0% slower |
| ladybug-1197 / 16 | 25.3% less time (1.34× speed ratio) |

The positive case is real evidence that reuse can help: at Ladybug-1197 depth 16, the retained basis was already sufficient, reducing charged time from 47.277 to 35.338 ms. It does not establish a reliable selection rule.

The depth-12 Ladybug-1197 case explains one failure mode. Ordinary wide CG needed 13 iterations. Reuse failed its first residual check and extended the basis to 16, requiring another verification pass. Including the narrow solve, projected reuse made 26 operator calls versus ordinary CG's 25 production calls (30 with diagnostic certification). Import/reconstruction costs then made reuse slower.

On the two small eligible systems, reuse eliminated operator calls but still lost elapsed time. Avoided products were too cheap to outweigh the charged capture, allocation, import and reconstruction work. Depth alone therefore does not determine whether reuse pays.

## Decision

The protocol required at least three eligible systems, successful certification for every ordinary/selective repeat on those systems, and a median selective speed ratio of at least 1.05 on **every** eligible system. Four eligible systems were collected; only one met the speed requirement. The gate is false, so no new end-to-end confirmation was run.

This is not a proof that Krylov recycling can never help. It is a stopping result for this implementation and depth-only rule under explicit cost accounting. Any later revival should account for operator cost and the likelihood of needing another extension/verification pass. We did not fit such a rule to these results.

## Verification and saved systems

The analytic test certified shared CG against a known diagonal operator and all nine method trials passed their residual gates. Compute Sanitizer reported zero errors. In the real comparison, 63/72 trials certified; the nine failures all belong to the one near-capacity system described above. Reported trial time totaled 4.482 s, excluding warmups, collection, builds and exports. No trials were excluded or repeated to improve the result.

All eight exported systems passed size, finite-value, index-range and camera-offset consistency checks. Every operator file is SHA-256 hashed. This validates the capture files, not an independent CPU solve of every returned vector; solver certification here uses true GPU operator residuals, with the analytic test as a separate correctness check.

Artifacts are under `/workspace/prism-fixed-reuse/`. Each `cases/<scene>/caseN.json` records dimensions, outer index, retained depth, point damping, central lambda, tolerance and shifts. Associated files are native little-endian arrays:

- `.Gp`: FP64 camera-major coupling fragments, 27 values per observation.
- `.Rf`: FP64 packed point factors, 6 values per point.
- `.Hcc`: FP64 camera blocks, 81 values per camera.
- `.E`, `.b`: FP64 diagonal scaling and RHS, 9 values per camera.
- `.cams`, `.points`: int32 camera/point indices, one per observation.
- `.coff`: int32 camera offsets, camera count plus one entries.

These are the inputs consumed by the frozen `MFPass1<9>`, `MFVinvApply`, `MFPass2<9>` and diagonal scaling kernels. Raw packing definitions remain in the frozen source. `operator-hashes.json` and `operator-validation.json` identify and validate the persisted files. The diagnostic executable, source, headers, manifests, complete timing/residual logs, protocol and summaries are also retained.

## Reproduction

The instrumentation is CLI-only, behind an off-by-default build option; ordinary solver policy is unchanged. The collector diagnostic intentionally exits once its quotas are filled and does not export a nonlinear solution endpoint. Default CLI/core builds were also checked.

```bash
cmake -S gpu -B /tmp/prism-fixed-build -DOCA_REUSE_FIXED_STUDY_BUILD=ON -DOCA_CUDA_ARCHITECTURES=89
cmake --build /tmp/prism-fixed-build --target oca_cuda test_reuse_fixed_study -j2
flock /tmp/prism_gpu.lock /tmp/prism-fixed-build/test_reuse_fixed_study
# Regenerate the report from the existing immutable artifacts:
python3 bench/summarize_fixed_reuse.py
```

`bench/fixed_reuse_study.py` performs collection in a fresh artifact directory containing `prism-frozen`. It refuses to overwrite existing logs. The broad queue remains paused; no benchmark jobs remain running.
