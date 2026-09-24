# Extended damping pilot — frozen before collection

Continue the initial pilot without changing the general incumbent. Host
2237c6528e79, RTX 2000 Ada; all timings compared on this host. Initial lambda
is 0.1 in every arm, including baseline. This is not the older Muell run
whose omitted CLI flag implied lambda 10.

1. Scout baseline trajectories on Ladybug-598, Dubrovnik-135 and Venice-89,
   at most 80 outers / 3 native seconds each. Select checkpoints using only
   previous CG depth and accepted boundaries, never intervention outcomes.
   Per scene: boundaries 1 and 3, plus the first two accepted boundaries
   with previous depth >=64, separated by at least three outers. If absent,
   use the two deepest available accepted boundaries (same separation),
   explicitly disclose any missing depth coverage. No test scene training.
2. At each checkpoint branch one action {-1,0,+1} in log10 damping, then
   resume the unchanged controller for 12 outers, N=3, maximum 3 native
   seconds each. The original pilot used four outers. Compare causal cost
   AUC at the common minimum elapsed duration of that state's nine branches;
   also report endpoint progress and CG work. Shorter convergence/stall is
   disclosed. Reward is baseline-minus-action normalized cost AUC.
3. Fit the same 64-feature ridge advantage model, regularization 10,
   bias regularization 0.01. Report leave-one-whole-family-out returns.
   Fit a final model regardless of sign for an explicitly diagnostic test;
   do not treat a failed family check as successful validation.
4. Freeze model bytes before complete solves. Compare baseline, previous
   learned model, extended learned model, fixed opening decay (-1 decade at
   boundaries 1 and 2), and the previous CG-cap work rule. N=3, rotated arm
   ordering, inference included, detailed logging disabled. Use the original
   fixed targets on Trafalgar-126, Final-1936 and Muell-gba146. These were
   already observed in research; they are transfer diagnostics, not pristine
   held-out recordings. No parameters tuned on this comparison.
5. Promotion requires all targets 3/3, positive family-held-out average,
   median scene speedup >=1.10, and no scene >5% slower. Otherwise retain
   incumbent. No Caspar expansion for a failed candidate.

Total study budget <=600 native seconds, serialized GPU, independent FP64
endpoint audits, no replacement of prior evidence. Additional correctness
smokes must pass before experimental decisions are interpreted. Raw data in
`/tmp/prism-rl-damping-extended`; compact evidence copied to `/workspace`.

## Coverage amendment, before any action branches

Initial scouts found depth 128 on Ladybug-598, but only 32 on Dubrovnik-135
and 13 on Venice-89. Scout Dubrovnik-356 and Venice-951 under the same caps;
replace the smaller scene in that family only if the larger one provides
depth >=64. Otherwise retain the original fallback rule. This choice uses
baseline depth only and does not inspect learned/action returns.
