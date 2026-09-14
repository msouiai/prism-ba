# Assembly and reusable-context cycle protocol

Registered 2026-09-14 before measurement. Base is production champion commit `d3d42dcb803f104424a3343364cac414a7ab7342`; frozen Eta2 and archived B6v7 files are never edited. Derived sources import the archived B6v7 recipe and overlay by recorded hashes.

## Stage 1: phase attribution

Run compile-time-FP32 compact2 unordered B6v7 on Muell-gba146 and Final13682 with fixed three-outer work. Use CUDA events on one stream for residual/projection derivatives, compact fragment writes, camera normal accumulation, point normal accumulation, point factorization, reduced RHS, transfer/synchronization, and other observable solver phases. Instrumentation must not change kernel arithmetic or dependencies. Collect one attributed run and at least three uninstrumented complete-call timings per scene; profiled results are attribution only. Record source, binary, input, configuration and output hashes, launch counts, and independently rescore endpoints in FP64. Production timing remains unordered. Exact flag-off compatibility uses separately named baseline/current binaries on the identical fixed-order W6 measurement substrate; unordered reruns cannot establish exactness.

Separately time binary startup, BAL parse, host index construction, CUDA allocation, H2D upload, solve, state D2H/output, and teardown where boundaries can be isolated without changing work. Unknown or inseparable time remains explicitly unclassified.

## Stage 2: one assembly candidate

Select exactly one candidate only after Stage 1. Before source edits, record the measured denominator, predicted Amdahl ceiling, expected affected launches/bytes, fixed microbenchmark, and kill criterion. Candidate choices are reuse/fusion of projection intermediates, removal of dead single-shift writes, or owner-based reduction. The 5% gate applies to median assembly microtime on both scenes over at least three alternating repetitions. Passing it opens native complete-solve time-to-target testing; it is not itself a production speed win and cannot open Caspar. Finite outputs, exact fixed fragment/operator agreement where arithmetic order is preserved, and current fixed-order flags-off equality are also required.

## Stage 3: reusable context

Prototype a reusable uploaded BAL problem/context API without modifying frozen entry points. Separate one-time parse/index/allocation/H2D construction from state upload/reset, solve, state download/output, context destruction, and cold process wall. Every timed cold and warm call resets numerical state and controller history to the identical hashed initial condition; no Jacobian, damping factor, residual, or LM history may carry across calls unless separately labeled. Compare cold-first and warm-reuse calls, alternating independent contexts where applicable, N>=3, at registered reuse count K=5. Require numerical/work equality on a fixed-order compatibility substrate and independent FP64 rescoring; unordered production runs provide timing only. Report construction, warm marginal, destruction, retained bytes and break-even reuse count. Production pass requires at least 5% median improvement on both scenes for `(create + K*(reset/upload + solve + download/output) + destroy)/K` versus the same complete cold-call boundary. Only that amortized pass may open Caspar.

## Stage 4: ownership and concurrency

Extend the solve-owned workspace to all active BAL handles, manual allocations, and exception exits. Rig is included only after a complete separate inventory and tests. Test allocation failures at multiple construction and solve points, handle-before-buffer destruction, owner-device cleanup and caller-device restoration. The same-GPU two-thread test uses distinct inputs/capacities, a start barrier, event or host evidence of overlap, distinct owned addresses, and exact agreement with serial references.

## Stage 5 and conditional comparison

Package the already validated linear-edge change as its own clean commit with focused tests and default-off behavior. Run Caspar comparisons only if Stage 2 or Stage 3 produces a production speed improvement that passes its gate. Then use same-host time-to-target on available Muell, Fuchsberg and Final13682 inputs/binaries, paired N>=3, preserving misses and FP64 endpoint audits. Absence of a compatible Caspar binary or scene is reported rather than substituted.
