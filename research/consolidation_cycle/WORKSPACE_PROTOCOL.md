# BAL workspace consolidation protocol

Registered 2026-09-14 before implementation. Scratch ownership is isolated from robust-norm arithmetic. Scope is active BAL; rig is excluded unless separately inventoried and tested.

Inventory all reachable process-global/static CUDA allocation: cost, deterministic BLAS, full-model reductions, diagnostics, handles, and manual scratch. Move supported scratch into a per-solve owner recording its CUDA device. Destruction switches devices, destroys handles before buffers, cleans partial failures, and restores the caller device.

Using identical fixed-order arithmetic: exact flag-off and enabled serial numerical/work compatibility; allocation-failure cleanup; device restoration; and two simultaneous same-GPU threads on distinct inputs/capacities matching separate serial references. Instrumentation must prove distinct owned buffers were exercised. Any remaining shared mutable CUDA state blocks a full-concurrency claim and is listed by symbol/path.

