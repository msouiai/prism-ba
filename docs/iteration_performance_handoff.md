# Iteration-performance implementation handoff, 2026-09-10

The focused port is on `research/iteration-performance`, based on master
`15cfdf9`. Commit `5d53a3b` ports the original performance patch; `463b399`
adds cache-miss counters and the portable A/B/S gate. It preserves Config S,
retriangulation and the other current-master algorithm changes. The new
optimizations remain opt-in. This branch is separate from the eta2 candidate.

## Contents and build

- `gpu/oca_cuda.cu`: `OCA_RETRY_CACHE`, `OCA_DIAG_NORM`,
  `OCA_RHS_DIAG_CAMERA`, batched-buffer sizing, dynamically sized active list,
  and additional profiling accounting. `OCA_MULTI_RHS` already existed;
  the port fixes its capacity and exposes it in the experiment harness.
- `gpu/test_rhs_diag.cu`: CD=6/9, float/double fragment storage, empty cameras,
  invalid factors, RHS-only output, full-solve versus forward-norm diagonal.
- `bench/profile_iterations.py`, `bench/summarize_iterations.py`,
  `bench/download_bal.py`: original investigation tools. Their historical
  gates and reporting rules are not a new time-to-target protocol.
- `bench/retry_cache_gate.py`: frozen-input/binary, rotated bounded A/B/S
  runs, complete environments, independent FP64 initial score, raw CSV/logs,
  cache counters, costs, rejects, outers, cap flags and native times.

```sh
cmake -S gpu -B gpu/build-perf -DOCA_CUDA_ARCHITECTURES=89
cmake --build gpu/build-perf --target oca_cuda test_rhs_diag -j1
flock /tmp/prism_gpu.lock gpu/build-perf/test_rhs_diag
python3 bench/retry_cache_gate.py --binary gpu/build-perf/oca_cuda \
  --data /workspace/bal --out /tmp/cache-opening-new --trace
```

Local validation used the direct nvcc commands recorded in
[the manifest](iteration-performance/2026-09-10/manifest.json), not this CMake
invocation. Rebuild once, then freeze the binary throughout the gate.
The runner clears inherited solver flags: this matters because several legacy
flags (including `OCA_MULTI_RHS`) are enabled by **presence**, even value `0`.

## Cache validity and measured hit rates

The cached objects are the damped point factors, scaled Schur RHS, equilibration
and optional point prediction. They are invalidated on every assembly and when
**either** `tau_eff` or the active per-point selected floor changes. Shared,
block-scaled and polynomial-congruence paths cannot use this cache. `uu` is
scratch reused by Krylov products, not a retained RHS cache.

Config A's monotone floor can hold the effective damping fixed during some
lambda escalations. Its independent streak-dependent tau can still rise.
Config B's selected floor cannot make the other points' changing tau reusable.
Config S has no monotone-floor ratchet: its anneal is constant within an
accepted outer, but lambda escalation changes the coupled floor on retries.
Changing damping changes the Schur operator and RHS, so reusing them would
change the algorithm. Span escalation already hits the cache whenever both
key values stay fixed; no separate span exception is needed or safe.

Fresh Ladybug-1197, first 15 outers, N=3 each, RTX 2000 Ada:

| Config | Builds / hits in each repeat | Hits / all attempts | Rejects | Misses after assembly |
|---|---:|---:|---:|---:|
| A | 29 / 12 | 29.27% | 26 | 14 changed-tau |
| B | 33 / 0 | 0% | 18 | 18 changed-tau |
| S | 35 / 0 | 0% | 20 | 20 changed-tau |

All nine runs complete 15 accepted outers and reach the outer cap. Initial
cost agrees with the independent FP64 evaluator within 8.41e-12 relative.
These are opening-window rates, not full-run rates. Raw per-attempt logs and
complete run records are in [cache-15](iteration-performance/2026-09-10/cache-15/).

The retained historical logs also settle a misattribution: the old Config A
60-outer final-4585 result had **494 builds / 20 hits (3.89%)**, N=3. All 15
optimized full-run Config B logs have **zero hits**. Therefore the reported
25.35% bounded storm improvement was the **combined cache + batching +
forward-norm** arm; it was never an isolated cache improvement. Counts and
log hashes: [historical-cache-counts.json](iteration-performance/2026-09-10/historical-cache-counts.json).

## Config S opening: bounded paired result and Nsight

Same current-master port binary in both arms. Reference has no performance
flags; optimized adds `OCA_RETRY_CACHE=1 OCA_MULTI_RHS=1 OCA_DIAG_NORM=1`.
N=3, Ladybug-1197, 15 outers:

| Arm | Native seconds median [range] | Endpoint median [range] | Rejects |
|---|---:|---:|---:|
| S reference | 2.248551 [2.226267, 2.257698] | 370191.470724 [370191.079159, 370192.354604] | 20 each |
| S optimized | 2.083708 [2.062735, 2.089579] | 370191.700969 [370190.849705, 370192.042800] | 20 each |

**7.33% less bounded solve time**, disjoint observed timing ranges, overlapping
cost ranges. All runs hit the 15-outer cap; this is neither a converged-quality
result nor a fixed-quality time-to-target claim. Cache hits are zero in all
three optimized runs. Batched scoring and the diagonal path account for the
execution changes; this combined gate does not isolate their contributions.
[Raw runs](iteration-performance/2026-09-10/S-15-pair/).

One separate Nsight reference-S profile of the same opening:

| Kernel | Total GPU seconds | Kernel-time share | Calls |
|---|---:|---:|---:|
| MFPass1 | 0.867200 | 40.3% | 1313 |
| MFPass2 | 0.663597 | 30.8% | 1033 |
| MFDiagK | 0.120306 | 5.6% | 35 |
| KernelCostBlockRed | 0.118570 | 5.5% | 404 |
| MFAssemble | 0.093084 | 4.3% | 15 |
| MFPointFactorObs | 0.067648 | 3.1% | 15 |
| MFRhsPrime | 0.028213 | 1.3% | 35 |
| MFPointFactorTau | 0.010353 | 0.5% | 35 |

The old 27.2% diagonal share was a different workload. **It is not the dominant
cost in S's first 15 outers on this input.** MFPass1/2 together take 71.1%.
MFPass2's 1033 calls match the Krylov matvec count; MFPass1's additional 280
calls match candidate back-substitution. This separates the main work without
relying on the misleading `pointfactor+rhs` aggregate. It does not profile the
later hundreds of rejects reported for full runs.

The raw [Nsight report](iteration-performance/2026-09-10/S-15-nsys.nsys-rep),
[kernel table](iteration-performance/2026-09-10/S-15-nsys-kernels.csv),
command and stdout are retained. Profiling timings are not used in the N=3
paired timing result.

## Memory and numerical gates

Fresh CUDA memcheck: zero errors for the kernel gate and full-menu widths
**1, 13 and 17** on Ladybug-49 (two outers, gate disabled, batched path enabled).
The maximum fused-kernel relative discrepancy was 4.23e-14, below 1e-10.
Forward-norm diagonal checks also passed. Sanitizer-instrumented kernel
microtimings are not performance evidence.

There were TWO buffer bugs: XCU/TACC used the default `n_shifts` capacity
instead of the effective `OCA_NSHIFTS` width, so 13 could overflow device
buffers; `act[16]` separately overflowed above 16. Both are fixed. The fusion
kernel changes reduction order and remains an optional research path, excluded
from the conservative arm above.

## Next transferable gate

On the collaborator's RTX 2000 Ada, using the exact same compiled binary for
reference and optimized arms (N=3, full S flags supplied by the runner):

```sh
python3 bench/retry_cache_gate.py --binary gpu/build-perf/oca_cuda \
  --data /workspace/bal --out /tmp/S-quality-pair-new --configs S \
  --arms reference optimized --scenes ladybug-1197 final-3068 \
  --reps 3 --max-iter 600 --timeout 900
python3 bench/retry_cache_gate.py --binary gpu/build-perf/oca_cuda \
  --data /workspace/bal --out /tmp/S-storm-pair-new --configs S \
  --arms reference optimized --scenes final-4585 \
  --reps 3 --max-iter 60 --timeout 900
```

Return manifests, all logs and CSVs, including failures. The 60-outer storm
cell is intentionally bounded. For subsequent descent-rate claims, freeze
common 0.5%, 1%, 2% targets from an independently verified FP64 Caspar reference
before collecting timed runs; charge setup to both solvers and report misses.
Do not convert these endpoint-wall measurements into time-to-target speedups.
