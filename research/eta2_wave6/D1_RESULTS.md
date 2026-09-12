# D1 result: paired-inference tools validated

The common-random-number substrate is ready for algorithm comparisons.

- The Wald SPRT implementation reproduces the registered boundaries: nine
  consecutive variant-only hits support non-inferiority and twelve
  control-only hits support harm.  Five unit tests also verify that concordant
  outcomes and pair order do not change the likelihood and that an undecided
  100-pair cohort is reported as inconclusive.
- Repeating the same seed produces byte-identical BAL files.
- The observation/header prefix is byte-identical to the source BAL file, and
  `k2` is exactly zero in the generated state.
- On Final3068, seed `600001` at `epsilon=1e-12` has independently measured
  initial residual-space distance `0.001567470562729865`; its field scales and
  input/output hashes are retained in `d1-perturb-final-smoke.json`.
- On Venice-52 the same seed and dose gives residual-space distance
  `2.484254186439647e-06`.

This stage makes no algorithm claim.  It fixes how later hit-rate evidence is
generated and analysed.  Each intervention still needs its own preregistered
seeds, paired continuous statistic, target, cap and stopping rule.
