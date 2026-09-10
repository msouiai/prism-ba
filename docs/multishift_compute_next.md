# Next steps for multi-shift computation

Two diagnostic phase profiles, 2026-09-07, final-4585, 20 outers, one/five shifts,
eight-probe backtracking, existing cache + multi-RHS scoring + forward-norm
diagonal enabled. Frozen `coverage-v2-frozen`; coverage/rearming disabled.
`OCA_PROFILE=1 OCA_PROF_SCORE=1` add synchronization: these are phase diagnostics,
not new unprofiled speed verdicts. Both completed within the 60-second process
cap; raw commands, hashes and logs are in `/workspace/prism-compute`.

| Quantity | Single shift | Five shifts |
|---|---:|---:|
| Matvecs | 139 | 249 |
| Krylov seconds | 3.074 | 5.516 |
| Krylov ms per matvec | 22.115 | 22.153 |
| Menu cost evaluations | 23 | 140 |
| Candidate seconds | 0.399 | 1.491 |
| Assembly seconds | 2.154 | 2.157 |
| Point factor/RHS seconds | 2.051 | 2.057 |
| Alpha-grid seconds | 0.303 | 0.130 |
| Backtracking seconds | 0.195 | 0.294 |
| Profiled solver seconds | 8.798 | 11.727 |

On this workload, per-Krylov-iteration costs are nearly equal. The five-shift
run takes 79% more matvecs on its different trajectory. Its Krylov phase is
47% of wall, assembly+factor/RHS 36%, and menu scoring 13%. Other costs and
profiling overhead explain the remainder. This is not a fixed-operator causal
ablation or evidence that vector overhead is negligible on every scene.

## Priority 1: adapt Krylov work, not just scoring

The five-shift seed is lambda/100, while the standalone seed is lambda. The
least-damped system can keep the shared sweep alive after the central candidate
has enough accuracy. The existing adaptive-menu feature primarily changes which
candidates are scored; it still carries all five shifts in the shared sweep.

A focused next prototype should obtain a central candidate to its declared
accuracy, evaluate the currently useful alternatives, and continue the Krylov
sweep only when the candidate/model evidence justifies further work. A bounded
full-step backtracking probe before committing to a much deeper sweep is also
worth isolating: 17 of the large run's 20 steps already needed backtracking.
This is an algorithm change, with an explicit quality/work tradeoff, not an
execution-only shortcut or an invitation to blindly cap every solve at depth 8.
Keep descent/curvature safeguards and assess 1%, 3%, 5% quality crossings.

Separately, the saved-state rejection evidence supports remembering the
successful lambda/tau pair and expanding the camera range at fixed tau before
rebuilding point factors. Basis recycling for additional shifts is prior art.
Changing point tau changes both the Schur operator and RHS, so the existing
scalar-shift recurrence cannot be reused unchanged across arbitrary tau values.
See [the rejection investigation](rejection_research.md).

## Priority 2: complete batching of candidate evaluation

`MFPass1Multi` already shares the expensive fragment stream across candidates;
do not propose enabling it as a new optimization. The tail still performs
point back-substitution, step copying, retraction and true-cost evaluation for
each shift separately. The measured per-candidate breakdown is approximately
4.8 ms in amortized pass1/back-substitution, 0.6 ms copying/negation, 0.5 ms
retraction and 4.7 ms cost evaluation. Shared lift overhead is also charged to
the candidate phase.

A fused or batched full-cost path could reuse observation topology and reduce
materialization/launch overhead. First benchmark fixed candidate directions,
verify each fp64 cost and candidate ordering, and then run nonlinear tests.
Even halving the entire measured candidate phase saves only about 6% of this
profiled solve if everything else stays fixed. Objective evaluation alone has
a still smaller ceiling. Any larger gain would also need less total work.

## Priority 3: reduce CG synchronization and freeze converged shifts

The current CG loop returns pAp, pp and the new residual norm to host scalars
through three cuBLAS dot products per iteration. [NVIDIA documents](https://docs.nvidia.com/cuda/cublas/index.html#scalar-parameters)
that host-pointer scalar-result operations block, while device-pointer results
can execute asynchronously. Device-side scalar recurrences and combined
reductions could reduce synchronization/launch overhead. Preserve the existing
curvature and residual stopping semantics; simply delaying checks changes the
algorithm and must be evaluated separately.

This needs a kernel/launch-level profile before substantial work: the measured
large-case iteration rate is already almost identical for one/five shifts.
`OCA_MENU_FUSE` already exists and an earlier Venice diagnostic found no useful
wall improvement; it is not the first optimization to repeat.

A converged shifted system should also stop receiving updates that can underflow
zeta to zero and later divide 0/0. The existing shift-prune option skips repeated
scoring but does not freeze the recurrence. Validate a freeze rule against true
residuals and independently solved fixed systems, including late snapshots.
The earlier 2048-depth audit exposed nonfinites; recent production-depth traces
did not. Do not attribute current runtime/rejections to unobserved NaNs.

## Keep the next experiments small and diagnostic

* Use fixed-state/linear-system tests to separate implementation cost from changed
  nonlinear trajectories. Include the known failing Ladybug state and Dubrovnik,
  which contradicted the candidate-coverage improvement.
* Compare progressive depth against the exact existing multi-shift configuration;
  retain guarded single shift as the practical baseline. Evaluate quality bands,
  all scoring, matvecs, retries and final cost together.
* Test rearming at a checkpoint around convergence confirmation, preserving both
  the BA state and controller history. A BAL state dump alone resets the latter.
  Recent 20/40-outer runs never activated rearming and cannot validate that fix.
* Use the short final-4585 case only as a transfer check after the smaller cases.
  Do not restart the broad sweep yet, combine unisolated changes, or claim novelty
  from speedups in already-known Krylov recycling machinery.

No solver code or defaults changed in the original profiling pass described above.
The subsequent implementation and bounded experiments are recorded in
[the compute results](multishift_compute_results.md). Progressive depth, cost
batching and state/controller replay now have opt-in prototypes; the measured
kernel profile did not justify a larger device-side CG rewrite. Defaults remain
unchanged.
