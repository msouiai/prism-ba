# Guarded projected TR bottleneck: Final-13682

Fresh kernel attribution, 2026-09-09. One instrumented run of the frozen guarded projected TR binary; no algorithm changes. Raw logs, manifest, Nsight report, SQLite and CSV reports: `/workspace/prism-tr-cg-stop/bottleneck-profile/`.

## Equal-quality result (previous uninstrumented paired run)

PRISM guarded projected TR: 16.348893120 s. Caspar FP32: 7.796989882 s. Caspar FP64: 16.687824029 s. FP32 is 2.097x faster on this scene. N=1; the small FP64 difference does not establish a win. Endpoints were independently audited against original FP64 observations. FP32 used the fixed 0.1% native stopping margin; timing scopes exclude input loading and differ in solver-local setup inclusion. See `cg_stopping_results.md` for protocol.

## New instrumented attribution

The profiling run reached the target in 16.337598342 s, with seven accepted steps, zero rejections, and 160 reported Schur products. Its timing is not an additional benchmark repeat. Nsight aggregate kernel time is 16.185089286 s, including small pre/post-solve diagnostic kernels.

| GPU work | Seconds | GPU time |
|---|---:|---:|
| Schur passes 1+2 and point inverse application | 8.308 | 51.3% |
| Jacobian/block assembly | 2.499 | 15.4% |
| Point factors, diagonal preconditioner, reduced RHS | 3.086 | 19.1% |
| Full unregularized model prediction for acceptance | 1.719 | 10.6% |
| Projected dense GEMMs | 0.137 | 0.85% |
| Other kernels | 0.436 | 2.7% |

The projection basis-store kernel takes another 0.001558 s. CPU eigensolves, projection synchronization, explicit verification products and extra scoring are not included in the GEMM figure. Thus 0.85% is not the entire incremental projection cost. The aggregate GPU work already accounts for almost all elapsed solver time; CPU projected solves cannot explain the approximately 8.55 s benchmark gap. CUDA API durations include waiting on kernels and must not be added to GPU times or interpreted as transfer-only costs.

Pass 1 averages 26.12 ms (168 calls), pass 2 21.80 ms (160 calls), point inverse 2.58 ms. A representative Schur application therefore costs roughly 50.5 ms. Additional pass-1 calls serve other operations. The earlier Caspar FP32 profile measured its full joint J^T J product at 26.58 ms (168 calls). These operators differ, so this is per-operation cost attribution, not an equal-work comparison or an isolated precision experiment.

PRISM has FP32 cross-block and point-Jacobian storage, but FP64 assembly arithmetic, point factors, Schur accumulation, CG/reductions, state and full-model acceptance. Caspar FP32 has native float computation and a full joint matrix-free formulation that avoids PRISM's point-elimination setup. Both precision and formulation contribute; this profile does not separate their causal shares. PRISM's seven accepted steps and zero rejections already beat Caspar's step count, but each step is substantially more expensive.

## Implications

Prioritize an opt-in FP32 Schur operator and point-system arithmetic with FP64 reductions, explicit residual checks, and nonlinear acceptance. Test attainable target accuracy before widening scope. Assembly and point preparation are the next substantial costs. Reusing derivatives or a validated model identity could reduce the 1.72 s full-model pass while preserving an independently checked acceptance calculation. Avoid prioritizing further radius-menu tuning: projected matrix algebra is a small fraction here, and eliminating rejections offers no saving on this run.

This diagnosis is specific to the largest sampled scene; it does not explain every smaller-scene regression. No production source was changed and no paused runs were resumed.
