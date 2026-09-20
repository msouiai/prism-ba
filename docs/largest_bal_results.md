# Largest BAL scaling screen — 2026-09-07

Follow-up: [compact FP64 fragment storage](compact_fragment_results.md) resolves the memory failure on the same GPU; the original failed runs below remain retained.

The frozen PRISM FP64 configurations both exceed the RTX 2000 Ada 16 GB memory
capacity on final-13682. Caspar FP32 completes the short budget successfully.
This is a memory scalability failure for the tested PRISM implementation; it
provides no PRISM convergence or speed comparison on this scene.

Dataset: 13,682 cameras, 4,456,117 points, 28,987,644 observations, downloaded
from the [official BAL Final collection](https://grail.cs.washington.edu/projects/bal/final.html).
SHA256: `76ef34416fdca524b1ec6755b62ab33cba15c8b5b830b5ff38369c8cd609d736`. Local data: `/workspace/bal/final-13682.txt`.

One run per method, 30-second native solve budget, 180-second process timeout.
Same frozen binaries and rearm-only selection as [fixed-policy validation](fixed_policy_validation.md).
No retuning, no solver changes, batching/progressive depth off. GPU runs serialized.

| Method | Outcome | Native solve time | CPU FP64 final objective |
|---|---|---:|---:|
| Selected guarded multi + rearm | CUDA out of memory | unavailable | unavailable |
| Guarded single | CUDA out of memory | unavailable | unavailable |
| Caspar FP32 default | completed budget | 30.513 s | 25,211,022.492 |

Caspar completed 47 iterations (32 accepted,
15 rejected). Its CPU-scored float-converted initial state
cost 1,126,372,083.920, giving 97.762%
objective reduction. GPU samples observed 5,786 MiB while Caspar ran (sampling,
not an allocator-certified peak). Setup took 2.508 s;
full driver process including parsing/checks took 49.234 s.
The solve overshot the budget by 0.513 s; the late
candidate was discarded by the budget guard. Exit code 0 is success of the
process; the solver stopped on budget, not established convergence.

## Memory finding

Both PRISM errors report the generic allocation helper at frozen source line
8896, so logs do not identify the exact failing buffer. Inspection shows shared
`Gp`, `Gc`, and `Bo` allocations of `(27 + 27 + 6) * nobs * sizeof(double)`:
**12.958 GiB** before state, input,
point factors, and other scratch. These allocations precede the menu-specific
buffers and exist for both one and five shifts. Reducing the menu alone does
not make the tested implementation fit. Each process loaded the dataset before
failing; neither produced an endpoint. Failed process times are retained in raw
results and are not reported as optimization runtimes.

A targeted follow-up is to reduce these per-observation buffers through
compaction/recomputation/chunking, then repeat this identical screen. An FP32
storage path would be a separate numerical configuration; the current
`--mf-fp32` path disables the full-step guard and cannot silently substitute for
the selected guarded policy. No memory rewrite or additional runs were attempted
in this final short test.

## Interpretation limits and artifacts

N=1 is a scaling screen, not a variance study. PRISM FP64 raw-z projection and
Caspar FP32 epsilon-guarded projection differ, as documented in the prior report.
Caspar native final cost 25,207,814.000 differs from the common raw-z
CPU audit by 0.01273%; its initial quantization gap
is 0.000243%. Precision/projection differences
do not erase the observed practical memory failure but prevent an algorithm-only
comparison. We cannot claim PRISM beats Caspar on the largest BAL dataset.

All manifests, logs, stderr, results, GPU samples, protocol, and completion record
are under `/workspace/prism-largest/`. The generalized
`bench/validation_study.py` accepts custom repeat count, budget, and process timeout
for budget screens; existing defaults remain unchanged. Python compilation and
`git diff --check` pass. The broader queue remains paused; changes are local.
