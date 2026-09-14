# Stage 2 code review: owned BAL scratch

Status: source-ready for compile and CPU/static validation; no GPU workload was run by the code reviewer.

The derived source is `build/owned-workspace.cu`, produced only from the current fixed-linear-edge derivative by `build_owned_workspace.py`. The transform binds one `OwnedBalWorkspace` per CLI solve or public `Solve` call. It owns fixed-order BLAS partial/output storage, deterministic and ordinary cost storage, bounded-backtrack output, count output, and block-diagnostic output. Deterministic cost is redirected through `owned_deterministic_cost.cuh`; leaving the production include in place would retain its three process-static allocations.

The public wrapper records the caller device, applies `gpu_index`, constructs the workspace on that device, and restores the caller device after dependent objects have been destroyed. Constructor failure frees every allocation completed so far. Host CSV, dump, BAL-pointer, memory-report, learning-policy, and diagnostic-once state reachable from independent BAL calls is thread-local. Full-model reduction storage remains owned by its existing per-solver object.

Static review found no remaining process-static CUDA pointer in the generated translation unit or either owned header. Remaining function statics hold immutable environment-derived configuration after C++ thread-safe initialization. Rig entry points are intentionally excluded.

The exact claim must remain narrower than whole-solver exception RAII. Numerous production CUDA allocations and cuBLAS/cuSOLVER handles are already local to an invocation and therefore do not alias across concurrent solves, but they use manual cleanup. A later CUDA exception can leak those resources; cuBLAS/cuSOLVER error macros can terminate the process. The owned workspace destructor also cannot recover resources if CUDA device discovery or switching fails during teardown. These limitations do not introduce shared scratch, but they do not satisfy the protocol's strongest cleanup wording.

Before promotion, compile from the recorded manifest and run the registered gates: exact serial reference parity, injected partial-allocation failure, caller-device restoration, and simultaneous same-GPU solves on different problem sizes. Buffer-address instrumentation must show distinct BLAS, cost, bounded, count, and diagnostic allocations for both threads. Any shared address or divergence from each thread's separate serial reference kills the concurrency claim.

Static validation completed: the builder runs, Python compilation succeeds, `git diff --check` succeeds, both owned includes appear in generated source, and a scan finds no static CUDA pointer declaration. `test_concurrent_workspace.cu` compiles with nvcc and `-Xcompiler -pthread`; it was not executed by this reviewer. Generated source SHA-256 is recorded in `OWNED_WORKSPACE_SOURCE.json`.

## Stage 3 fixed-system harness

`fused_fixed_system.cu` compiles as a resident-device replay for the Muell and Final captures. It reconstructs a stable point CSR from the captured compact2 camera-major slots, uses the same `q += 32` accumulation/tree in both arms, compares separate point Pass1 plus Vinv against a four-warps-per-block fused kernel, and times 20-product alternating arms after warmup. It includes the registered seeds/probe count, hard finite and output-error gates, sampled symmetry, exact invalid-factor zeroing, and a nonzero tiny probe.

Two reporting limits must be retained. The current printed `term_norm` is a conservative placeholder rather than separately measured `||Hcc v|| + ||W V^-1 W^T v|| + ||Sv||`; exact fused/reference equality makes the acceptance decision insensitive to this in the expected case, but the report cannot claim the registered term normalization until those terms are emitted. The baseline uses one point-owned warp per block while the fused arm packs four, so timing measures the combined point packing and fusion package rather than fusion alone.
