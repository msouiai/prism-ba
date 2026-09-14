# Prism / Eta2 code improvement audit

Date: 2026-09-14  
Scope: frozen Eta2 source under `research/eta2_champion/source`, Wave-5/Wave-6 evidence, and the 2026-09-14 collaborator note. No GPU workload was run and no solver source was changed.

## Executive ranking

| Rank | Change | Expected value | Risk |
|---:|---|---|---|
| 1 | Port Wave-6's complete fixed-order reduction path into the production solver/workspace | High scientific/debug value; negligible steady-state cost for cost scoring | Low-medium |
| 2 | Make FP32 fragments the BAL default and a measured/explicit rig choice | 21--33% BAL wall reduction in the independent N=3 panel; 12--28% on two rig sizes, neutral at 20.8M observations | Low-medium |
| 3 | Replace process-global CUDA scratch with per-solve/per-device workspace ownership | Removes a real concurrency and multi-GPU correctness defect; enables safe embedding | Medium |
| 4 | Fuse point-owned Pass1 with the 3x3 point solve, using the existing point CSR | Up to part of the 53.19% Krylov share and removes a full `tacc` round trip plus atomics/launch per product | Medium-high |
| 5 | Convert the active champion configuration from environment-variable control to an immutable typed plan | Prevents configuration bleed and makes manifests/API behavior trustworthy | Medium |
| 6 | Capture only stable, scalar-free kernel chains with CUDA Graphs after ranks 1--4 | Ceiling is in the measured 18.27% unaccounted bucket; likely low-single-digit total wall | Medium-high |

Ranks 1--3 should be implemented first. Rank 4 is the best new kernel experiment. Rank 6 is deliberately last: Wave 6 shows that the linear products, rather than scalar synchronization, dominate this GPU.

## 1. Port the complete deterministic reduction path, not only the cost finalizer

**Evidence and mechanism.** The production cost kernel still writes one FP64 atomic per block at `prism_eta2.cu:243-287`; its menu variant does the same at `prism_eta2.cu:296-328`. The rig clone repeats it at `headers/oca_rigfisheye.cuh:168-188`. The full-step model also ends in two cross-block atomics at `headers/full_step_model.cuh:4-16`. Thus the block reduction removed the serialization bottleneck but retained schedule-dependent cross-block addition.

The complete solution already exists as an experimental result. Wave-6 D0v3 fixed normal assembly, Schur accumulation, nonlinear cost, full-model sums, cuBLAS reductions, reduced RHS, and accepted point-step paths, producing identical endpoint hashes and decision traces in 5/5 repetitions on both Venice52 and Final3068 (`research/eta2_wave6/D0_RESULTS.md`). Port that workspace-backed implementation rather than adding an isolated second pass only to `KernelCostBlockRed`; otherwise `ComputeCost` becomes deterministic while other trajectory inputs remain variable.

Claude independently measured the cost-only two-pass form below 0.01 ms at panel scale. The first pass should write `partial[blockIdx.x]`; one fixed-order block should reduce exactly `GridSize(nobs)` entries. Carry the same contract through `KernelCostMenu`, bounded scoring where applicable, rig scoring, and `MFDirectFullModel`.

**Predicted ceiling.** Runtime speedup is approximately zero beyond noise because block-reduced cost is already fast (43.6 to 2.3 ms at 29M observations is already captured at `prism_eta2.cu:2879-2888`). The payoff is exact paired trajectories and drastically cheaper diagnosis. Extra cost should remain under 0.01 ms/evaluation at current sizes, subject to local measurement.

**Minimal ablation.** Build production control and complete-D0 port from the same source. On Ladybug49 and Dubrovnik356, run N=5 identical inputs and compare accepted-cost sequences, normalized decision traces, endpoint bytes, target result, products, rejects, and wall. Then run the registered deterministic perturbation pairs on Final3068 to verify common-random-number behavior. Include both plain and bounded/menu scoring paths even if the champion uses one shift.

**Compatibility requirement.** Flag-off must reproduce the current block-reduced path. Flag-on need not match its endpoint bitwise because fixing addition order selects a trajectory, but independently rescored costs must agree within the existing FP64 audit tolerance. Do not claim determinism until all D0v3 reductions, not merely cost, are active.

**Kill criterion.** Kill production promotion if repeated flag-on runs differ in any numerical trace field, if the independent cost audit exceeds the existing tolerance, or if stable-panel target time regresses by more than 1% after subtracting normal run-to-run timing spread.

## 2. Default BAL to FP32 fragments; keep the rig choice explicit until broader coverage

**Evidence and mechanism.** Both public option structs default `use_fp32_fragments` to false (`headers/oca_core.h:87` and `:215`). The implementation then allocates two 27-value fragment copies plus six point values per observation in either float or double (`prism_eta2.cu:9152-9156`; rig at `headers/oca_rigfisheye.cuh:533-542`). Every Schur product streams the fragments in `MFPass1` and `MFPass2` (`prism_eta2.cu:1391-1398`, `:1522-1539`, and calls at `:10095-10110`). This is the measured memory-roofline path.

Wave-6 D3 is decisive against FP64 as a reliability mechanism: FP64 won only 8 of 18 discordant Final3068 pairs, was slower on all 15 double hits, and had a 1.634x median target-time ratio (`research/eta2_wave6/D3_RESULTS.md`). Claude's independent post-cost-kernel N=3 panel gives FP32 wall changes of -21% to -33% on six non-tiny BAL scenes with endpoints inside each scene's spread; Ladybug49 is effectively neutral (-2%, endpoint +0.007%). Corrected rig N=3 results are -12% at 1.5M observations, -28% at 4.5M, and -0.1% at 20.8M, with matching quality.

**Predicted ceiling.** 21--33% total BAL wall on the measured panel, consistent with the 1.2165--2.2189 FP64/FP32 target ratios in D3. Rig ceiling is 0--28% in current evidence. Memory drops by about `30 * nobs * 4` bytes for the two 27-value and one six-value stores: roughly 3.5 GiB at 29M observations. Exact allocation savings should be reported from `OCA_MEMREPORT` rather than inferred in release notes.

**Minimal ablation.** No broad discovery sweep is needed. Re-run N=3 paired, alternating-order medians on one tiny BAL, Dubrovnik135/356, Final3068 with deterministic perturbation pairing, and one largest BAL; use common targets and independent FP64 endpoint rescoring. For rig, retain explicit selection and test one small, one medium, and `gba_230` before changing its default.

**Compatibility requirement.** State, accumulation, point factors, Krylov scalars, actual-cost acceptance, and endpoint audit remain FP64. The typed option must be recorded in result/build metadata. Preserve FP64 fragments as a diagnostic mode for precision forensics.

**Kill criterion.** Reject the BAL default only if it loses more than 2% target wall on any stable scene, changes a stable endpoint beyond that scene's measured numerical spread, or reduces paired Final3068 hit rate beyond the existing 15-point non-inferiority margin. Keep rig FP64 by default if any N=3 cell regresses more than 2%; otherwise a size-independent FP32 default is supported by current evidence.

## 3. Give every solve its own CUDA workspace and device affinity

**Evidence and mechanism.** `ComputeCost` owns a function-static device pointer (`prism_eta2.cu:2871-2895`); stride cost and cheirality repeat the pattern (`:2959-2969`, `:2999-3004`), and bounded cost owns a static `Result*` (`:2914-2933`). The block-Cholesky diagnostics add static device pointers at `:10048-10053` and `:10071-10078`. These objects are neither keyed by CUDA device nor protected against concurrent calls. Two host threads can memset and accumulate into the same scalar, and switching `gpu_index` can reuse a pointer allocated on another device. This contradicts the embeddable API surface and its `gpu_index` option (`headers/oca_core.h:112`, `:232`). The static `once` flags also suppress per-solve diagnostics after the first process invocation.

Move persistent scalars, partial arrays, reduction scratch, and diagnostics into an RAII `SolverWorkspace` constructed after selecting the device. Thread it through cost/model calls, or make it an explicitly owned reusable context. Record the device ordinal; reject use after a device mismatch. This also centralizes allocations now scattered through `SolveMFreeShiftedCG` (`prism_eta2.cu:9103-9183`) and the rig clone (`headers/oca_rigfisheye.cuh:533-564`).

**Predicted ceiling.** Serial wall is neutral. It removes data races and invalid-device-pointer failures and permits concurrent independent solves. Reusing a context may shave setup allocation time, but that is secondary and must not be marketed without measurement.

**Minimal ablation.** CPU-thread harness with two simultaneous solves on one GPU and, where available, one solve per GPU. Compare each against its serial reference using the deterministic build. Run under compute-sanitizer racecheck/initcheck if supported, without timing claims.

**Compatibility requirement.** A single serial solve must preserve the selected reduction order and numerical trace exactly. Workspace lifetime must outlive all enqueued kernels; destruction must occur on the owning device after completion. The API must remain exception-safe across partial allocation failure.

**Kill criterion.** Do not merge a reusable-context design if serial flag-off traces move, if any allocation remains process-global, or if cross-device destruction/use can occur. A simpler per-call RAII workspace is preferable if caching complicates ownership.

## 4. Fuse point-owned `W^T v` accumulation with the point solve

**Evidence and mechanism.** Each operator application currently clears `tacc`, launches observation-owned `MFPass1`, performs three atomics per observation, launches `MFVinvApply`, then runs camera-owned `MFPass2` (`prism_eta2.cu:10095-10110`). Yet the solver already has a stable point-to-observation CSR constructed once (`:2668-2695`). One block or warp per point can traverse its complete track in stable order, accumulate the three components in FP64, immediately apply the local 3x3 inverse factor, and write `uu`. This removes global atomics, the `tacc` zero/write/read traffic, and one kernel boundary. It also supplies the point-owned deterministic Pass1 component D0v3 needed.

Track lengths are irregular, so use a hybrid dispatch: warp-per-point for ordinary tracks and block-per-point for long tracks, with an offsets-derived class built during indexing. Preserve the existing camera-owned Pass2. Do not fuse across Pass2: it requires the completed point result and has a different camera-major ownership pattern.

**Predicted ceiling.** Krylov accounts for 53.19% of native wall in the 27-run profile, but fragment streams remain dominant. A realistic total-wall goal is 3--10%; the absolute ceiling is below the full cost of Pass1 plus `MFVinvApply`, not 53%. FP32 reduces the bandwidth available to save, so evaluate this after rank 2.

**Minimal ablation.** Fixed captured systems only: Ladybug598, both Muell captures, Final1936, plus a synthetic long-track stress case. Compare operator output against the current path in FP64 norm and, under fixed reduction order, byte equality where mathematically identical. Measure product time, achieved bandwidth, occupancy, and track-length tail; only then open a native N=3 stable-panel gate.

**Compatibility requirement.** Same invalid-factor behavior as `MFVinvApply` (`prism_eta2.cu:1507-1512`), FP64 accumulation for float fragments, stable within-track order, all shared-intrinsics and rig index mappings honored, and an unchanged explicit true-residual audit.

**Kill criterion.** Stop if fixed-system product time improves less than 5% on both hard Muell captures, if any stable native cell loses more than 2% wall, or if numerical error exceeds the existing explicit-residual tolerance. Do not tune the nonlinear controller to rescue a kernel-induced trajectory change.

## 5. Replace environment-controlled champion behavior with an immutable typed plan

**Evidence and mechanism.** The public API exposes typed `Options`, but core behavior still depends on dozens of `getenv` calls. Several are function-static and therefore capture the first process value forever, including cost reduction (`prism_eta2.cu:2883-2884`), block preconditioning and switch thresholds (`:9105-9128`), tau splitting (`:9184`), and damping settings (`:9365-9371`). Environment variables are process-global, cannot represent two differently configured concurrent solves, are difficult to validate, and can make a result manifest disagree with actual behavior after a library has already been called.

Parse legacy environment variables once at the CLI boundary into a `SolverPlan`. The library path should construct the same immutable plan solely from typed options. Pass it by const reference and print/hash the complete plan at entry. Separate research-only switches from the supported plan so dead experimental branches cannot silently activate in production.

**Predicted ceiling.** No intended speedup. This is correctness, reproducibility, maintainability, and testability work; it also makes rank 3's concurrent API meaningful.

**Minimal ablation.** Golden configuration tests: each supported legacy environment configuration and equivalent typed plan must emit the same normalized plan hash and deterministic numerical trace. Add a two-thread test with different options and no environment mutation.

**Compatibility requirement.** CLI environment behavior remains available through translation, with precedence specified once. Champion JSON must map to one versioned plan hash. Unknown or incompatible fields fail closed before allocation.

**Kill criterion.** Do not remove an environment route until archived commands can be translated exactly. Reject any plan design that retains hidden function-static configuration or makes the champion hash incomplete.

## 6. Graph stable kernel chains only after kernel work is reduced

**Evidence and mechanism.** The profile attributes 18.27% to controller, allocation, launch, transfer, and timer gaps, while Krylov is 53.19% (`docs/eta2_formulation_novelty_results.tex:235`). A matvec is a stable chain of memset, Pass1, point solve, and Pass2 (`prism_eta2.cu:10095-10110`); preparation also has stable chains around point factor/RHS (`:9944-10033`). Capture those chains into per-shape CUDA Graphs inside the workspace. Update scalar and pointer parameters between launches. Keep branchy candidate selection and host cost decisions outside the graph.

**Predicted ceiling.** Absolute total-wall ceiling is 18.27%, but that bucket includes work graphs cannot remove. Expect low-single-digit gains on large scenes and potentially more on tiny, many-outer cases. D14 showed that halving scalar reduction phases produced no crossover because products dominate, so this is not a priority over product traffic.

**Minimal ablation.** Measure launch/API time with Nsight Systems on Ladybug49, Trafalgar138, and Muell before capture. Proceed only where launch gaps exceed 5% of target wall. Compare N=10 alternating runs because expected effects are small.

**Compatibility requirement.** Graph and eager paths must share the same kernels and reduction order; topology/shape, device, precision, shared-intrinsics mapping, and workspace addresses are graph-cache keys. Numerical traces must be exact under the deterministic build.

**Kill criterion.** Stop if launch gaps are below 5%, graph replay improves total target time by less than 2%, or graph parameter management adds any trajectory/configuration ambiguity.

## Closed or low-priority ideas that should not be reopened unchanged

- Do not promote FP64 fragments for reliability or build high-plus-low fragments solely for continuity: D3 rejected that premise and measured a 1.63x median penalty.
- Do not replace PCG with native GMRES(8) or periodic restart-8 unchanged. Their fixed-system wins became 1.330x and 1.456x native slowdowns and lost Muell targets (`D13_NATIVE_RESULTS.md`, `D13B_PERIODIC_PCG_RESULTS.md`).
- Do not revisit one-reduction Chronopoulos--Gear PCG on this single GPU. D14 found no hard-system crossover and 30--49% slowdowns on shallow systems.
- Do not build the q=3 visibility subgraph or randomized Nyström correction unchanged. D11's formation/analysis cost and D12's extra products dominate their algebraic signal.
- Do not enable JIT Jacobian recomputation, subsampled scoring, bounded backtracking, batch menu scoring, or compact FP64 fragments merely because code exists. They are experimental branches and either target the disabled multi-shift menu or need their own current FP32 single-shift profile.
- Do not treat terminal triangulation, terminal block Gauss--Seidel, robust opening, early restart prediction, or periodic point repair as open production levers without a new mechanism. Wave-6 D9 and D22--D24, plus the established Final4585 repair failure, close those current forms.
- Do not infer that host scalar synchronization is a large remaining lever. D14 directly measured the opposite on this architecture.

## Recommended implementation order

1. Extract the full D0v3 fixed-reduction workspace into the active source and validate exact repeatability.
2. Make all scratch/configuration per solve (or per explicitly owned context), then add concurrency tests.
3. Promote FP32 fragments on BAL after the small confirmation panel; retain FP64 diagnostic mode and make rig selection explicit pending broader scene coverage.
4. Prototype point-owned fused Pass1 plus point solve on fixed captured systems.
5. Consolidate the supported configuration into a versioned plan while retaining a CLI environment translator.
6. Profile launch gaps after the preceding changes and graph only chains that retain a measured ceiling.

This sequence keeps trajectory diagnosis reliable before changing the fastest numerical storage path, fixes an API correctness issue before enabling concurrent use, and requires fixed-system evidence before exposing a new operator kernel to nonlinear basin selection.
