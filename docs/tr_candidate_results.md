# Confirmed improving candidate: TR-one with recurrence scoring

**TR-one with recurrence-based candidate scoring is the current candidate.** A fresh five-repeat comparison improves all three scene medians, wins **14/15 paired runs**, and reaches **15/15 frozen quality targets**, as does the baseline. No scene-specific selection rule or controller retuning is used.

## Confirmatory results

Native time to the same target; fresh paired controls, N5. Smaller scenes have a four-second budget, Final1936 eight seconds. Arm and scene order reverse in even repeats. Both arms use the same binary; only `OCA_TR_RECURRENCE` changes. No profiler, candidate learning log or curvature audit is enabled in these timed runs.

| Scene | Original TR-one | Recurrence TR-one | Speedup | Time reduction | Paired wins |
|---|---:|---:|---:|---:|---:|
| Trafalgar126 | 0.451366 s | **0.437046 s** | 1.033× | 3.17% | 4/5 |
| Dubrovnik88 | 0.874473 s | **0.716603 s** | 1.220× | 18.05% | 5/5 |
| Final1936 | 4.027661 s | **3.864734 s** | 1.042× | 4.05% | 5/5 |

Timing ranges (baseline → candidate): Trafalgar 0.449–0.622 → 0.435–0.577 s; Dubrovnik 0.741–0.917 → 0.710–0.838 s; Final1936 4.014–4.152 → 3.859–3.877 s. The small Trafalgar gain has overlap and one paired regression; it is not a claim that every run is faster. Final1936 was not used to choose these recent radius modifications, though it has appeared in older repository benchmarks. Three scenes do not establish universal superiority.

Frozen targets: Trafalgar 104534.24152926281; Dubrovnik 359003.9111293723; Final1936 5074937.9725361075, each with the same existing 1e-8 inward margin. These are native solver clocks, not full application wall clocks. Full process times and exact endpoint costs are retained. There is **no new Caspar comparison** in this study; these speedups are against the corrected TR-one incumbent.

The earlier N3 development comparison also improved both small-scene medians: Trafalgar 0.488 → 0.436 s and Dubrovnik 0.876 → 0.718 s, but won only 2/3 pairs on each. That result triggered the fresh confirmation rather than an immediate winner claim.

## What changed and why this is still TR

The existing corrected camera trust-region controller is retained: one active radius, a finite bank of shifted/depth candidates plus a Cauchy candidate, reduced-model ranking, true nonlinear cost and full unregularized GN prediction for acceptance, radius adjustment, cached rejected-state direction reuse, and point safeguards. The winning configuration uses **one shift**. It is an approximate camera-space TR algorithm with separate point handling, not an exact full-space joint TR solve.

Previously, ranking each saved CG candidate applied the Schur operator again to obtain its quadratic curvature. At a CG snapshot,

```
(S + sigma I)x = b - r_sigma
xᵀSx = bᵀx - sigma*||x||² - xᵀr_sigma.
```

For shifted CG, use its stored residual collinearity `r_sigma = zeta_sigma*r_seed`. Compute curvature using vector reductions and the recursive residual instead of another Schur matvec. The identity is exact in exact arithmetic; recursive residual drift in floating point is explicitly audited. This is an implementation optimization of the TR scoring step, not a new convergence theorem or a claim of novelty for the residual identity.

All actual nonlinear cost and full GN acceptance evaluations remain. Cauchy construction retains its explicit operator evaluations. Accepted-step quality is not inferred from the recursive residual. The controller, damping-placement rules, point handling, checkpoint ladder, and stopping targets are unchanged.

Median candidate matvecs avoided per confirmed run: **43 Trafalgar, 28 Dubrovnik, 12 Final1936**. Total matvec medians: 933 → 890, 622 → 481, and 191 → 179. Avoided candidate applications are a subset of those totals, not additional savings to add again. Dubrovnik's total-work difference exceeds direct scoring savings because realized nonlinear/CG trajectories differ. GPU reductions and tiny ranking differences can change trajectories; the full observed 18% gain cannot be attributed solely to removing 28 matvecs.

## Validation

Four audit runs capped at 16 iterations cover widths1 and5 on both small scenes; a fifth, capped at 16 iterations or eight seconds, covers Final1936/width1. Every saved CG curvature is compared with an explicit Schur operator evaluation before running its associated timed study. **632 comparisons pass**, maximum relative discrepancy **5.03e-10**, against the frozen 1e-7 failure threshold. Five-shift numerical validity is checked; five-shift performance is not promoted by this result.

**47 exported endpoints** from the development and confirmation studies pass independent CPU cost audits against original BAL observations, maximum relative discrepancy **1.89e-14**. Verification also checks source/header/binary/data hashes, initial/final CSV costs, monotonic accepted costs, actual camera feasibility and rho, and absence of timing instrumentation in performance runs. All timed baseline/candidate runs have zero nonlinear rejections.

The recurrence studies use **72.590 native solve seconds** and **132.707 subprocess wall seconds** total, including the five instrumented audit runs. Build time and independent Python audits are outside these clocks. The prior negative experiments remain in their separate budgets and logs.

## Reproducible packaged candidate

Build and run from the repository:

```bash
python bench/build_tr_candidate.py
python bench/run_tr_candidate.py \
  --problem /workspace/bal/trafalgar-126.txt \
  --target 104534.24152926281 \
  --seconds 4 \
  --output /workspace/tr-candidate-run
```

The build defaults to CUDA `sm_89`; `--arch` and `--output` can be specified. It reads `gpu/oca_cuda.cu` and `gpu/tr_candidate.patch`, verifies the base hash, snapshots repository headers and produces an isolated executable. It does not require the earlier experimental source directories. The run helper supplies the frozen flags, strips inherited experimental solver flags, writes a manifest/log/CSV/exact state, and refuses to overwrite results. Add `--audit-model` to validate curvature explicitly; that is diagnostic overhead and should not be used for production timing.

The packaged source matches the timed source except for a metadata-vector sizing guard, which protects other shift-count CLI configurations. Its one/five-shift values and arithmetic formulas are unchanged. The packaged binary passes its own three-scene audit: three independently checked endpoints and 108 additional explicit curvature comparisons (maximum 4.13e-11). These diagnostic runs use 9.723 native seconds and are not included in the timing table. Packaged binary SHA256: `936a02425902ee5d0b2d7f09e2f738b53ab32c2b6076bfe0e48972f1e699f222`. Production defaults and `gpu/oca_cuda.cu` remain unchanged.

Files:

- `gpu/tr_candidate.patch`, `gpu/tr_recurrence_score.inc`: complete TR overlay and new scoring logic.
- `bench/build_tr_candidate.py`, `bench/run_tr_candidate.py`, `bench/validate_tr_candidate.py`: build, frozen run configuration and packaged validation.
- `bench/build_tr_recurrence.py`, `bench/tr_recurrence_study.py`, `bench/tr_recurrence_confirmation.py`, `bench/verify_tr_recurrence.py`: original experiment and independent verification.
- `/workspace/prism-tr-recurrence/`: frozen timed binary/source, headers, protocols, all raw runs, `verification.json`, `annotated-results.json`.
- `/workspace/prism-tr-candidate/`: standalone build, manifest, executable and packaged validation.

## Research path and remaining limits

The earlier [adaptive radius experiments](adaptive_radius_results.md) tried residual-controlled projected solves, persistent ray search, initial-only expansion and separate point damping. None improved both scenes consistently. The subsequent [joint TR and depth/width studies](joint_tr_research_log.md) also split the scenes or regressed. These failed variants are retained; the winner was not chosen by silently excluding unsuccessful runs.

The recurrence optimization meets the present objective of a clear, measured improving TR candidate. It does not establish that five radii are better than one, make the joint TR variant a winner, or prove algorithmic novelty/publication readiness. The appropriate next validation is broader untouched scenes and a fresh matched Caspar comparison, with this configuration frozen.
