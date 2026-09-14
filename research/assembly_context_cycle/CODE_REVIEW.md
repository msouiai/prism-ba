# Assembly and reusable-context code review

## Measurement boundaries

The native B6v7 assembly is one monolithic `MFAssemble` launch at archived generated-source lines 9786--9792. CUDA events can honestly bracket the preceding clears, the complete `MFAssemble`, optional intrinsics damping, point-factor/RHS preparation, reduced-RHS accumulation, equilibration, and explicit transfers. Every event pair must be recorded on the same stream as the measured kernels and the terminal event synchronized once before reading elapsed times. Per-phase `cudaDeviceSynchronize` calls would add gaps and make the labels overlap host/runtime latency.

Projection/derivatives, compact writes, camera/point normal accumulation, and `bc`/`bp` accumulation cannot be separated by launch-boundary events. They occur inside the same kernel at archived B6v7 lines 1232--1277. A split-kernel replay is therefore diagnostic: it changes global traffic, cache reuse, launch count, and atomic scheduling. Its phase times must not be added or presented as a decomposition of native `MFAssemble` wall.

Outside `Solve`, report BAL parsing, stable point/camera index construction, allocation, and H2D upload as host-wall categories. In the public wrapper, uploads occur at lines 12858--12869 and 12904--12916, while `BuildPointObsCSR` and `BuildMFreeIndex` run at 12873--12874. CUDA event time alone excludes CPU index construction and pageable-host staging overhead; use host steady-clock intervals with an explicit synchronization at the end of the H2D category.

## Assembly opportunities

`MFAssemble` computes `Px`, `Py`, `Pz`, normalized coordinates, distortion, and residuals at lines 1239--1245. The CD9 branch then calls `BalResidualGrad12` with the original state at lines 1252--1255; generated derivative code recomputes the same projection chain. Returning projection intermediates and residuals from one generated routine, or accepting precomputed intermediates, removes duplicate divides and distortion arithmetic. Compatibility requires preserving the current generated derivative operation order and the residual values used by robust weighting and `r2acc`; a source rewrite that merely uses algebraically equivalent expressions can change every downstream atomic trajectory.

In compact2, `fragment_o2slot` is `obs2cslot`, `Gc` is absent, and `Gp` is the sole camera-major fragment array. The `if (Gc)` store at line 1275 is dynamically dead but compiler-eliminable after specialization. `Bo` writes at line 1276 remain live: the tau-split point-factor path consumes observation rows to build `R0f` after each assembly. `Cdiag`, `bc`, and `bp` are live in the selected single-shift path. No write should be removed based only on the single-shift setting; shift count changes solve reuse, not assembly data dependencies.

The best first optimization target is a CD9/compact2/classical specialized assembly kernel that removes runtime-null branches and shares projection intermediates with derivative generation while preserving FP32 fragment casts and FP64 normal/RHS accumulation. Keep the generic kernel as the flag-off reference. Gate eligibility on exactly CD9, compact2, unshared intrinsics, classical LM, compile-time float fragments, and the same robust/radius options supported by the specialized body. Reject unsupported combinations before clearing outputs or dispatching.

## Reusable context and ownership scope

A reusable context can retain topology-derived point/camera CSR, permutation maps, and capacity-sized device buffers across calls. State, observations, intrinsics, solver counters, streams, handles, and output logs must remain call-owned or explicitly serialized. Reuse is valid only when dimensions and topology hashes match; pointer identity is insufficient because callers can mutate index arrays in place. Context destruction must switch to its owner device, destroy handles/events before buffers, synchronize only its own stream where possible, and restore the caller device.

The prior workspace work establishes distinct active-BAL scratch for concurrent solves and partial-construction cleanup. It does not provide whole-solver exception RAII: many local CUDA allocations and cuBLAS/cuSOLVER handles still use manual cleanup, and rig paths remain excluded. A reusable context must not broaden the concurrency claim until those resources and all mutable host reporting state are either context-owned, call-owned, or thread-local, with a same-GPU two-thread test using distinct contexts.
