# Code implementation review: workspace ownership and fused point operator

Date: 2026-09-14  
Scope: implementation guidance and patch review for `/tmp/prism-ba-agent-integration`. No GPU workload was run. Solver implementation remains untouched by this reviewer.

## A. Per-solve, per-device RAII workspace

### Defects the design must eliminate

The embeddable wrapper already has `DeviceArena` (`prism_eta2.cu:12703-12715`), but it covers only wrapper allocations. The active nonlinear solver allocates a second large set manually (`:9103-9183`) and frees it only on the normal exit path. A `CUDA_CHECK`, `cublasCreate`, policy validation, or other exception after those allocations leaks them. The rig clone has the same manual lifetime (`headers/oca_rigfisheye.cuh:533-564`, cleanup at `:911-919`).

Several scratch objects are process-global rather than solve-owned:

- cost scalar: `prism_eta2.cu:2876-2895`;
- bounded-cost result: `:2921-2933`;
- stride-cost scalar: `:2961-2969`;
- cheirality count: `:2999-3004`;
- block-Cholesky diagnostic counters: `:10048-10053`, `:10071-10078`;
- Wave-6 deterministic cost partials/output: `eta2_wave6/deterministic_cost.cuh:56-75`;
- Wave-6 fixed dot/norm workspace: `eta2_wave6/deterministic_blas.cuh:40-64`.

These buffers race when two host threads call `Solve`, and they are not keyed by CUDA device or stream. The static destructors in the Wave-6 workspace can also call `cudaFree` while a different device is current or while CUDA runtime teardown is underway. A mutex would serialize independent solves and would not repair device affinity; `thread_local` would still need device keys and has teardown hazards. Use explicit ownership.

### Recommended object model

Use three small layers rather than one untyped arena:

1. `ScopedCudaDevice` captures `cudaGetDevice(&previous)` before any allocation, validates/selects `gpu_index`, and restores `previous` in a `noexcept` destructor. It must be declared before all device-owning objects, so it is destroyed last.
2. `DeviceBuffer<T>` is move-only, records `{T* ptr, size_t capacity, int device}`, grows explicitly, and frees on its recorded device. Its destructor must never throw. An internal temporary device switch is acceptable for cleanup; preserve and restore the caller's current device. Log cleanup failure only through a nonthrowing hook.
3. `SolverWorkspace` owns all scalar/reduction scratch and the active solver's scratch vectors. At minimum it must own `cost_output`, `cost_partials`, `bounded_result`, `stride_cost`, `cheirality_count`, `full_model_sums`, `blas_partials`, `blas_output`, and both block-factor diagnostic counters. It records `device`, `stream`, maximum observation/vector capacities, and whether a call is in flight.

Suggested interface shape:

```cpp
struct SolverWorkspace {
  explicit SolverWorkspace(int device, cudaStream_t stream = nullptr);
  SolverWorkspace(const SolverWorkspace&) = delete;
  SolverWorkspace& operator=(const SolverWorkspace&) = delete;
  SolverWorkspace(SolverWorkspace&&) = delete; // pointers are captured by closures
  ~SolverWorkspace() noexcept;

  void ReserveCost(int nobs);
  void ReserveVector(int n);
  void CheckDeviceAndStream() const;
  // typed DeviceBuffer members
};
```

Pass `SolverWorkspace&` explicitly to `ComputeCost`, `ComputeBacktrackCost`, `ComputeCostStride`, `CountCheiralityViolations`, `PrismFullModel`, and deterministic BLAS wrappers. For the first integration, create exactly one workspace inside each public `Solve`/`SolveRigFisheye` after `ScopedCudaDevice`, and pass it down to the selected nonlinear solve. Do not expose reusable contexts publicly until single-call ownership is complete.

`cublasHandle_t` and `cusolverDnHandle_t` also belong to the solve context. Wrap each in a move-disabled, nonthrowing RAII holder and bind it to the workspace stream. Destroy handles before buffers and buffers before restoring the previous device.

### Ownership hazards to check in review

- **Destruction order:** C++ destroys in reverse declaration order. Required order is handles -> buffers/states/index -> device restore. Declare `ScopedCudaDevice device_guard; SolverWorkspace ws; ...` in that order.
- **Wrong-device cleanup:** `Solve` currently changes the calling thread's device at `:12794` and `:12968` and never restores it. The guard must restore it on success and every exception path.
- **Outstanding work:** workspace destruction must occur only after all work using it is complete. Existing blocking D2H cost copies and final `cudaDeviceSynchronize` provide this today. If streams become asynchronous, record/synchronize an event before resize or destruction; never free/grow a buffer still referenced by a graph or kernel.
- **Aliasing across reductions:** one `blas_output` cannot back two concurrently enqueued reductions whose consumers overlap. Current host-pointer dot/norm calls synchronize, but device-pointer mode may not. Either give each in-flight reduction a slot or document/enforce one-at-a-time use on one stream.
- **Norm semantics:** do not preserve Wave-6's `sqrt(dot(x,x))` implementation blindly. `deterministic_blas.cuh:36-38` uses device `fmax(input,0)` and `:91-92` uses host `std::max(0,value)`; both can map a NaN sum to zero depending on operand order. Squaring can also underflow a nonzero vector to exact zero or overflow a finite vector to infinity. That is observably different from robust `cublasDnrm2` scaling and becomes a correctness bug when zero norm means convergence. Use a fixed-order scaled sum-of-squares reduction (LAPACK `lassq` state: scale and ssq), explicitly propagate any NaN, and distinguish “all input elements exactly zero” from “computed norm rounded to zero.” If exact ordinary-trajectory compatibility with D0 is required, use the robust path at least for exceptional exponent ranges and document the dispatch.
- **Capacity growth:** never `cudaFree` old partials before prior kernels finish. Reserve maximum blocks once from `nobs` and maximum vector length at solve entry.
- **Zero sizes:** public validation rejects empty problems, but helpers should still avoid zero-block launches. Keep this invariant explicit.
- **Exception safety:** push a raw pointer into an arena only after successful allocation, as current `DeviceArena::Alloc` does. Prefer typed members so an exception cannot occur between `cudaMalloc` and ownership registration.
- **Diagnostics:** replace process-static `once` flags with per-workspace/per-solve booleans. Each solve should report its own fallback count when requested.
- **Configuration:** workspace size/type is determined by the immutable solve plan. Do not read environment variables during reserve or destruction.

### Exact compatibility invariants

For a serial solve on one device and the same configuration:

1. Kernel launch order, block geometry, stream, reduction tree, and precision remain unchanged.
2. Workspace refactoring alone must produce byte-identical accepted costs, decisions, endpoint state, products, outers, rejects, target status, and stop reason under the deterministic path.
3. Current block-reduced flag-off behavior must remain numerically identical too; changing buffer addresses is allowed, changing arithmetic is not.
4. `gpu_index=-1` must use the device current on entry and leave it current on return. An explicit `gpu_index` must be selected for the call and the prior device restored afterward.
5. Every device pointer must be allocated and freed on its recorded device. No process-global CUDA pointer may remain in the supported solve path.
6. BAL and rig calls may execute concurrently without sharing writable device or host scratch.
7. Result reporting and robust-objective semantics at `:12924-12932` remain unchanged.
8. Dot/norm wrappers preserve BLAS exceptional-value semantics: NaN never becomes zero, a finite nonzero vector is never classified as exactly zero due to squared underflow, and overflow is avoided when the true norm is representable.

### Focused non-GPU and GPU tests for the implementer

The reviewer will not run GPU work. The implementation should add/run:

- compile-only/static search gate: no `static T*` CUDA scratch remains in active BAL, rig, deterministic cost/model/BLAS paths;
- RAII unit test with an injected allocator failing on allocation N: all preceding allocations are released, handle destruction is called, and the previous device is restored;
- serial deterministic Ladybug49 N=5 exact trace/hash gate;
- two host threads, same GPU, independent Ladybug49 solves; each equals its serial reference;
- two GPUs where available, one solve per GPU, with devices intentionally reversed between thread creation and call; each equals serial and each thread's previous device is restored;
- robust and plain cost calls interleaved between two workspaces to catch scalar aliasing;
- deterministic norm fixtures containing NaN, Inf, all-zero, `DBL_MIN`/subnormal, `DBL_MAX`, and mixed exponents; compare classification and finite values against `cublasDnrm2` or a long-double/scaled CPU oracle;
- compute-sanitizer initcheck/racecheck on the two-thread small problem.

Kill the refactor if any serial deterministic field moves, any active static CUDA scratch survives, or cleanup depends on the current device coincidentally matching the allocation device.

## B. Point-owned fused `MFPass1` plus 3x3 point solve

### Baseline and exact fusion boundary

The active operator currently does:

```text
memset(tacc)
MFPass1: observation threads -> 3 atomicAdds per observation
MFVinvApply: one thread per point reads tacc and Rf -> uu
MFPass2: one block per camera reads uu -> w
```

See `prism_eta2.cu:10095-10110`, `MFPass1` at `:1391-1398`, `MFVinvApply` at `:1507-1512`, and camera-owned `MFPass2` at `:1522-1539`. The point CSR already exists at `:2668-2695`.

Fuse only the first two stages. A point-owned kernel traverses all observations for one point, accumulates its three `W^T v` values in FP64, performs the same fixed warp reduction, calls the exact existing `MFVinv(Rf + 6*p, total, out)`, and writes `uu[3*p:3*p+3]`. This removes the `tacc` memset/write/read and one launch. Keep `MFPass2` separate because every camera may read many completed point outputs and its camera ownership is already contention-free.

The closest correct starting point is `eta2_wave6/deterministic_mfree.cuh:86-102`. Extend it to apply `MFVinv` after lane 0 obtains the three totals. Do not start from observation-owned `MFPass1` and attempt warp aggregation by point: adjacent observations are not guaranteed to share a point in every fragment layout.

### Fragment/index mapping invariants

The CSR's `order[q]` is an original observation index. The fragment lookup depends on storage:

- separate point-major `Gp/Gp32`: use `slot = p.obs2pslot[o]` (legacy branch only; this is not how the frozen compact Eta2 champion obtains FP32 fragments);
- compact camera-major store (`compact_mode==2`): use `slot = p.obs2cslot[o]`;
- compact mode 1: use the exact point-to-storage permutation already built for that mode; do not assume original order;
- rig: verify its `mf_scam/mf_spt` construction before reuse; the reduced camera vector requires image/full-camera index before rig reduction, not frame index.

Pass an explicit `original_to_fragment_slot` pointer into the fused kernel. Avoid mode-dependent pointer guessing inside device code. The camera index used for `v + CD*c` must correspond to the full camera space consumed by `MFPass2`.

### Mapping irregular track lengths

Start with **multiple fixed warps per block**, not one 32-thread block per point. One warp per point is deterministic and simple, but a 32-thread block can hit the resident-block limit before filling the SM's warp slots. Use 4 or 8 warps per 128/256-thread block:

```cpp
warp = threadIdx.x >> 5;
lane = threadIdx.x & 31;
p = blockIdx.x * WARPS_PER_BLOCK + warp;
for (q = offsets[p] + lane; q < offsets[p+1]; q += 32) { ... }
```

Each warp owns exactly one point and needs no shared memory. The five shuffle offsets define a fixed reduction tree. Empty tracks write zero when the factor is valid, matching zeroed `tacc`; invalid factors write zero exactly as current `MFVinvApply` does.

Do not add a long-track CTA kernel in the first patch. It changes the reduction tree by track class, needs a point-ID queue, and makes compatibility harder. First profile degree buckets. If tracks with degree >=256 consume a material fraction of Pass1 time, a second deterministic block-per-long-point kernel can be tested. Its classification must be topology-only and fixed at index construction; long and ordinary point lists must be disjoint and exhaustive. Use a fixed 256-thread tree, never atomics. Because its arithmetic tree differs, require tolerance equality to the old fixed path and exact repeatability within the new path.

### Exact arithmetic and behavior invariants

1. Convert each fragment element to `Scalar` before multiply; accumulate products and lane totals in FP64 for both FP32 and FP64 fragment storage.
2. Preserve loop nesting: observation slot outer, point component, then camera component in ascending `i`. Compiler flags and FMA behavior must match the baseline build.
3. Use the same five `__shfl_down_sync(0xffffffffu, ..., 16/8/4/2/1)` reductions as D0v3. All 32 lanes must participate, including points with fewer than 32 observations.
4. Apply exactly `MFVinv`; do not rederive the triangular solve. Test `Rp[0]`, `Rp[3]`, `Rp[5]` with the same predicates before division and write three zeros on failure.
5. The fused output is `uu`; do not retain a stale `tacc` consumer in the operator path. `tacc` remains needed by back-substitution/candidate paths unless those are separately converted.
6. Preserve shared-intrinsics broadcast semantics: the input `v` to the fused kernel is the full camera vector `vf`, exactly as at `:10094-10110`.
7. Preserve `MFPass2`, subsequent `Reduce`, `st.matvecs`, explicit residual checks, and curvature decisions unchanged.
8. Gate narrowly at first to the actual champion layout: CD=9, unshared intrinsics, single shift, non-JIT, `using Fragment=float` (`prism_eta2.cu:9090`), and compact camera-major mode 2. This path reads `Gp` through `p.obs2cslot`; it is distinct from the legacy `mf_fp32/Gp32` option branch. Expand only after each layout has a mapping test.

### Precision-path naming warning

Do not implement the audit's earlier shorthand “turn on `use_fp32_fragments` for Eta2” as a public-option default flip. The frozen source already compiles its active `Fragment` alias as float at `prism_eta2.cu:9090`, while the runtime `mf_fp32` option allocates the separate `Gp32/Gc32/Bo32` path at `:9152-9156`. The guard at `:9083` rejects that runtime branch for the camera-TR/mixed-storage experiment, and compact storage rejects it at `:9144-9146`. Wave-6 D3 compares matched derived binaries in which the compile-time `Fragment` alias changes; it does not validate flipping the public boolean inside the frozen champion configuration.

Therefore keep precision work separate from this fused-kernel patch. Implement fusion first for the existing compact2 `Fragment=float` champion. If the public API's legacy branch is later re-gated, test it in its own supported solver configuration and describe it as a separate path. Any integration patch that merely changes `Options::use_fp32_fragments` from false to true for Eta2 should be rejected.

### Focused tests and kill criteria

Host-side index test (no GPU required): for random dense camera/point IDs and adversarial degree distributions `{0,1,2,31,32,33,255,256,257}`, prove every CSR original observation maps to the expected fragment slot exactly once.

GPU tests for the implementer:

1. Kernel microtest with synthetic fragments and well-conditioned/invalid `Rf`; compare fused `uu` to current `MFPass1 + MFVinvApply` in FP64 norm. Include NaN/zero diagonal guards.
2. Deterministic repeat test: N=20 fused calls must be byte-identical.
3. Fixed captures: Final1936, Ladybug598, Muell outer 11 and 12. Compare `Kv`, true residual, convergence flag, products, and median product time after warmup.
4. Native stable panel only after a >=5% fixed-product gain on at least one hard Muell capture. Require N=3 alternating order and unchanged target/work outcomes before tail scenes.
5. Nsight Compute counters: fragment bytes, atomic transactions (should become zero for Pass1), occupancy, achieved bandwidth, and warp execution efficiency by track-degree bucket.

Kill the fused path if neither hard Muell capture improves product time by 5%, if `Kv` error breaches the existing explicit-residual tolerance, if any invalid factor yields nonzero/nonfinite output, or if a stable native cell loses more than 2% wall. Do not change forcing, damping, stopping, or target logic to compensate for a changed reduction trajectory.

## Patch-review checklist

When implementation patches appear, review in this order:

1. `git diff --check` and confirm only intended source/tests changed.
2. Search active paths for remaining static device pointers and manual `cudaMalloc/cudaFree` pairs.
3. Trace declaration/destruction order from public wrapper through nonlinear solve and all exception exits.
4. Trace every fused-kernel index for each enabled fragment layout from assembly write slot to fused read slot.
5. Confirm the fused kernel writes every `uu` element, including empty/invalid points, so removal of `cudaMemset(tacc)` cannot expose stale data.
6. Confirm deterministic tree geometry is fixed and no atomic remains in fused Pass1.
7. Inspect test assertions for numerical outcomes and device restoration, not only process success.

## Final generated-source review (2026-09-14)

Reviewed `build/workspace.cu`, `build/fused.cu`, `deterministic_cost.cuh`, `fused_pass1.cuh`, and their transforms in `build_candidates.py`. `git diff --check` passes.

### Workspace verdict: acceptable for the registered narrow cost-scratch experiment

The public BAL wrapper declares `AuditScopedCudaDevice` before `AuditCudaWorkspace` and `DeviceArena` (`build/workspace.cu:12937-12945`). Reverse destruction therefore frees arena allocations, switches/frees workspace allocations on their owner device, and only then restores the entry device. This ordering is correct on success and exception unwinding. `AuditCudaWorkspace::Init` records the current device, and its destructor temporarily selects the owner and restores the then-current device (`:2660-2668`). If the second allocation fails, `cost` is already owned and `partials==nullptr` remains safe to free.

Both ordinary and deterministic nonlinear cost use the solve-owned buffers when the flag is active. Ordinary `ComputeCost` selects `p.audit_cost_scratch` and checks the current device (`:2915-2926`). The shadow `deterministic_cost.cuh:56-90` selects both workspace partial/output pointers and checks device plus capacity before launch. This closes the earlier bypass defect.

Scope must remain precise: this prototype makes **BAL nonlinear cost scratch** solve-owned. It does not make the whole solver concurrency-safe. Deterministic BLAS scratch remains process-static; stride cost, bounded cost, cheirality, full-model sums, block-factor counters, manual inner-solver allocations, and the rig wrapper remain outside this patch. The rig public wrapper still changes device without an `AuditScopedCudaDevice` at `build/workspace.cu:13114`. Do not report “per-solve workspace” or “multi-GPU safe” without the word `cost`, and do not use full concurrent deterministic trajectories as a safety proof while the BLAS workspace remains shared.

The destructor's unconditional `cudaDeviceSynchronize` is acceptable at solve teardown for this experiment but should not survive unchanged in a reusable production workspace; synchronization belongs to the owning stream/event contract. CUDA errors in the nonthrowing destructor are currently ignored, which is appropriate for unwinding but should feed diagnostics in production.

Required scoring assertions: flag-off exact trace; flag-on exact serial trace; pointer instrumentation proving deterministic and ordinary cost launches receive the `DeviceProblem` workspace addresses; entry device restored after success and injected failure. A two-thread test may safely target repeated cost evaluation with separate workspaces, but it must not claim whole-solver race freedom.

### Fused verdict: source-correct and ready for the registered fixed-system gate

Eligibility is now validated before `Kv` (`build/fused.cu:10197-10199`), so unsupported JIT, legacy `mf_fp32`, shared-intrinsics, non-CD9, or non-compact2 configurations throw before the code conditionally skips `tacc` clear. This fixes the stale-accumulation defect in the earlier transform.

`AuditFusedPass1Vinv` uses four warps per 128-thread block, one warp per point (`fused_pass1.cuh:11-14`). It traverses the point CSR as `q += 32`, maps original observation to the camera-major compact fragment through `obs2cslot`, accumulates in `Scalar`, uses the same fixed warp tree, applies the existing `MFVinv`, and duplicates the exact invalid-diagonal zero behavior (`:14-24`). The launch uses `GridSize(npt,4)` and passes the correct compact2 map (`build/fused.cu:10219-10220`). `MFPass2` remains unchanged. For eligible calls, `tacc` is neither cleared nor consumed in the operator; `uu` is written for every point, including empty and invalid tracks.

The fused build includes workspace and math overlays. Isolation therefore requires `OCA_AUDIT_FUSED_PASS1=1` in both compared arms only as appropriate, with `OCA_AUDIT_WORKSPACE` and `OCA_AUDIT_LINEAR_EDGES` held identically. Compare against the complete deterministic Pass1 path, since atomics would confound output attribution.

Bitwise `uu` equality is a reasonable expected diagnostic because each point retains the same per-lane observation sequence, shuffle tree, scalar products, and `MFVinv` body. Promotion should still use the registered explicit-residual tolerance rather than depend solely on bit equality, because kernel-boundary/compiler scheduling is not a mathematical identity guarantee.

No source blocker remains before fixed-system scoring. Production promotion remains conditional on the registered >=5% hard-capture product-time gain and native stable-cell gates.
