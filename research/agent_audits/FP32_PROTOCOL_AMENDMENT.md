# FP32 protocol amendment

An initial launcher invocation created a row manifest and then blocked before
any solver process or score because an outer `flock /tmp/prism_gpu.lock`
deadlocked with the native runner's own lock. It was interrupted. The initial
protocol SHA256 began `2ce30089`; the abandoned preflight did not retain a
complete registration artifact.

Before the first numerical result, the protocol and summary logic were amended
to state that this confirms the already-FP32 compile-time compact-fragment
choice, exclude rig explicitly, require a double hit for an evaluable timing
cell, use the exact reciprocal 2% bound `1/1.02`, and describe the N=3 hit rule
as descriptive. The registered numerical scenes, seeds, epsilon, targets, caps,
binary arms and alternating order did not change. The final protocol SHA256 is
`815f5e660e7b517f6f0d10315f7bd55bc82174be5638615e0d8ebbc8ca4a0e74`;
the frozen registration and scored manifests carry that authoritative hash;
the abandoned preflight produced no result row.
