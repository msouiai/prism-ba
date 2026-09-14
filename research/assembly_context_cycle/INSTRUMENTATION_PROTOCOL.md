# Assembly/setup instrumentation protocol

Derive from archived B6v7 source SHA-256 `c04bb4ed1a7fcbb6dcae5c9d016189612f854d91e92c34155a66114be62e23bb`; do not alter frozen sources.

Native launch-boundary events use one CUDA stream and non-overlapping pairs for clears, whole `MFAssemble`, optional intrinsics damping, point factor/RHS solve, reduced-RHS accumulation, and equilibration. Record all boundaries without intermediate device synchronization, synchronize the final event once, and report both phase sum and enclosing chain time. Report host-wall parse, topology/index construction, allocation, H2D, D2H, and startup separately; synchronize at transfer category endpoints.

A separate captured-state split replay may measure projection/derivatives, compact writes, camera normals/RHS, and point normals/RHS. Mark every result diagnostic and non-additive with native wall. Validate all split outputs against native buffers using finite checks and absolute/relative norms before interpreting timings.

Compile-time and runtime configuration is fixed to the registered B6v7 gated arm: CD9, compile-time float fragments, compact2, classical LM, one shift, unshared intrinsics, preparation fusion, camera RHS, and minimum-camera gate 128. Profiling is opt-in and flag-off must retain the archived numerical trajectory.
