# mfree_r10/solver — 9-DOF-camera port of the matrix-free solver

Round 10. This is `mfree_r9/solver/oca_cuda.cu` plus the free-intrinsics port:
per-camera focal length and radial distortion join the optimization state, so
the solver can be benchmarked like-for-like against Caspar and Ceres running
their native problem (round 9 compared everyone at fixed intrinsics only).

## What changed vs round 9

- `gen_grad12.py` → `bal_grad12_generated.cuh`: sympy codegen of the
  per-residual gradient over 12 parameters
  `[dw(3), dt(3), df, dk1, dk2 | dX(3)]`. Grad-only (Gauss-Newton) on purpose:
  the full 144-entry Hessian would defeat the register-budget DCE that round 9
  measured. FD-validated by `validate_grad12.py` (400 random states × 12
  columns × 2 rows, worst rel err 1.3e-6 = central-difference truncation, via
  a numpy twin generated from the *same* CSE pool as the CUDA header).
- All `MF*` kernels and `SolveMFreeShiftedCG` are now templated on the
  camera-block dimension `CD ∈ {6, 9}`. `CD=6` is round 9 bit-for-bit modulo
  atomicAdd order (venice-1672 regression: max 1.25e-11 rel drift over 15
  iterations vs the r9 trace, iter-0 already differing at 2e-15 → recompile
  noise, not algorithm).
- `DeviceState.intr`: mutable intrinsics laid out `[f(ncam)|k1(ncam)|k2(ncam)]`
  so the existing cost/diagnostics kernels take the three pointers unchanged.
  Null in every 6-DOF solver — the other 24 algos are untouched.
- 9-DOF retraction: pose part unchanged (Exp(dw)·R), intrinsics additive.
- `DumpBalState` writes the refined intrinsics when the state owns them, so
  `score_bal.py` scores 9-DOF dumps with the true final model.

## New flags

| flag | effect |
|---|---|
| `--dof9` | free f and k1 per camera (Caspar's SIMPLE_RADIAL merged focal_and_extra block; principal point fixed). mfree_shifted_cg only. |
| `--free_k2` | with `--dof9`: also free k2 (full 9-DOF, Ceres-on-BAL convention) |
| `--zero_k2` | zero every k2 at load, so the objective matches the harness's `COLMAP_BAL_SIMPLE_RADIAL` model exactly (measured median |k2/k1| ≈ 2e-7) |
| `--intr-damp W` | weight of the absolute intrinsics damping (default 1.0; 0 disables) |
| `--equil-floor E` | per-camera-block relative floor on the equilibrated diagonal. **Default 0 everywhere** (was 1e-12 at dof9 — see the audit note below); 6-DOF 0 = round-9 bit-compat |
| `--tau-persist {0,1}` | dof9 only, **default 0**: tau-memory experiment (two variants), kept for future work after failing its gates — both were worse than the shipped reset-to-base policy on the very problems they targeted (see round10/STATUS.md addendum). `OCA_LM_CLASSIC=1` similarly disables the lambda unwind, diagnostic only. |
| `--lm-inner-retry N` | max LM retries inside one outer iteration, dof9 only (default 8). A rejected step leaves the state — and the whole assembly — unchanged, so a retry reuses it and only redoes point-factor/rhs/equilibration/CG at the escalated λ and τ. `0` restores round-9 behaviour, where every reject spends an outer iteration. Forced to 0 at CD=6. |

k2 masking is exact, not approximate: with `--dof9` alone the dk2 Jacobian
column is multiplied by 0 in assembly, so the gradient, all Gauss-Newton
products, and hence every CG iterate are identically zero in that coordinate.

## Design notes

- **Equilibration is load-bearing at 9 DOF.** The camera block now mixes
  units spanning ~9 orders of magnitude (rotation ~O(1), focal ~O(10³) px,
  k2 ~O(10⁻⁶)). The existing Jacobi equilibration (`--precond equil`, default)
  non-dimensionalizes the block; the CG shift is applied *after* scaling, so
  camera damping is scale-invariant with no per-scene tuning. Measured on
  trafalgar-257 `--dof9`: equil off → final cost 161,052 in 3.60 s; equil on →
  118,288 in 1.81 s (36% worse quality AND 2× slower without it).
- **Relative damping cannot regularize null directions — two absolute
  mechanisms were required.** (1) The intrinsics columns can be near-null
  (H_k1k1 ~ Σ(f·r²·x̂)² ≈ 0 for a camera whose observations cluster near the
  image centre); unregularized, final-4585 drove one camera's k1 from ~1e-6 to
  9.8e11 through such a direction. `KernelDampIntr9` adds 1/σ² curvature with
  physical scales σ_f = f/2, σ_k1 = 1/r̄²_c, σ_k2 = 1/r̄⁴_c. (2) The outer λ
  ratchet only damped the CAMERA system; the point back-substitution V⁻¹b_p is
  damped by the fixed τ_pt, so a state where that step is toxic could never be
  escaped (measured: a candidate with |x_c|=1.8e-3 evaluating 2000× worse than
  the current cost, 113 consecutive rejects). For CD=9,
  τ_eff = τ_pt·max(1, λ/λ₀) restores the classic LM limit (λ→∞ ⇒ whole step→0
  ⇒ eventual acceptance). CD=6 keeps round-9 behaviour exactly.
- Memory/flops: `Gp`/`Gc` go 18 → 27 values per observation (×1.5), `Hcc`
  36 → 81 per camera. Measured end-to-end 60-iteration overhead vs CD=6:
  1.07–1.66× depending on scene.
- Caspar cannot represent the k2 column at all (`CreateCasparAdapter`
  supports SimpleRadial/Pinhole only), so the Caspar-matched benchmark mode is
  `--dof9 --zero_k2`; `--free_k2` exists for Ceres-convention comparisons.

## Audit changes (2026-08-22, later session)

Three defects were found after the original author's session ended. See
`BA_RESEARCH_HISTORY/round10/STATUS.md` for the full audit.

1. **`equil_floor` dof9 default 1e-12 → 0.** The floor collapsed the Krylov
   solve at CD=9: final-3068 ran at 1.1 matvecs/outer with 16/61 accepts and
   cost 4.65M; with 0 it runs 28.3 matvecs/outer, 61/61 accepts, cost 1.71M.
   It also did not help final-4585, the scene it was added for. The flag
   remains, so the old behaviour is `--equil-floor 1e-12`.
2. **λ ratchet (CD=9).** A reject multiplied `lam_cam` by 10 and an accept only
   halved it, so any scene that rejects drifted upward without bound: on
   final-4585 a 3-reject/1-accept cycle netted λ ×500, carrying λ from 3.9e-2
   to 4.8e34 by iteration 61 with `cg_it` pinned at 0. Since the accept that
   ends such a streak is won by the τ ratchet and not by the λ escalation, an
   accept now unwinds λ to its pre-streak value instead of banking it.
3. **τ ratchet starts on the first reject, not the second.** λ damps only the
   camera block and τ only the point block, so a reject that escalates λ alone
   leaves the point relaxation — the toxic half on final-4585 — untouched.
4. **Rejects no longer spend an outer iteration** (`--lm-inner-retry`, default
   8). final-4585 was burning 35 of 61 iterations on rejects, each one paying
   for a full re-assembly of a Hessian that had not changed. The retry reuses
   the assembly: `MFDiagHcc` only reads `Hcc`, λ enters solely through
   `shifts[]`, and τ enters only via `MFPointFactor`, so nothing upstream of
   the point factor depends on either.

Effect on final-4585 (`--dof9`, τ_pt 1e-1, 60 iterations):

| build | accepts/rejects | matvecs/outer | cost | medA | wall |
|---|---|---|---|---|---|
| as inherited | 21 / 40 | 1.4 | 13,092,853 | 0.847 | 26.1 s |
| + λ unwind | 21 / 40 | 6.8 | 12,424,367 | 0.810 | 33.6 s |
| + τ from first reject | 26 / 35 | 14.0 | 11,027,410 | 0.707 | 46.6 s |
| + inner retry | **61 / 148** | **59.5** | **10,343,722** | **0.675** | 157.4 s |

The last row costs 3.4× the wall-clock for 60 iterations, so it must be judged
at matched wall-clock rather than matched iterations. It dominates there too —
cost at 10/20/30 s is 11,577,876 / 11,112,847 / 11,061,041 vs 11,882,009 /
11,132,314 / 11,066,413 without retry — and reaches Caspar's delivered cost in
33.4 s vs 36.4 s. Beyond 46.6 s the no-retry run has spent its 60 iterations
and stops improving, while the retry run keeps descending to 10.26M.

All four changes are CD=9-only; CD=6 is untouched. On scenes that never reject
(ladybug-598, trafalgar-257, venice-1778, final-3068 at 9 DOF) the retry branch
never executes and results are unchanged.

## Two consumers, one core (2026-08-23)

`oca_cuda.cu` now builds twice from a single source:

| target | what it is | contains |
|---|---|---|
| `oca_core` | embeddable static library, the only supported embedding API (`oca_core.h`) | kernels, `SolveMFreeShiftedCG`, LM policy |
| `oca_cuda` | the research CLI | the above **plus** BAL IO, the other 24 algorithms, benchmarking |

`main()` is compiled out of the library by `-DOCA_CORE_LIBRARY`. This is
deliberately **not** a fork: round 10 found four defects in the LM policy
(equil floor, λ ratchet, τ timing, reject burn), and a copied solver would have
had to rediscover each one. COLMAP consumes `oca_core` at whatever revision
`MFREE_SOLVER_DIR` points at, exactly the way it vendors Caspar at a pinned
revision, so production can hold still while the sandbox moves.

Two consequences worth knowing:

- **`CUDA_CHECK` throws instead of calling `std::exit`.** Embedded in COLMAP, a
  CUDA OOM must surface as a failed `Solve()` the caller can fall back from,
  not take the whole reconstruction process down. The CLI catches it in
  `main()` and returns 1, so `oca_cuda`'s observable behaviour is unchanged.
- **Problem indexing is built by shared helpers** (`BuildPointObsCSR`,
  `BuildMFreeIndex`) rather than inline in `main()`. When it lived only in
  `main()` the core ran the matrix-free kernels against null index pointers —
  caught immediately by the gate below.

### Gate: the core must reproduce the CLI

```
./run_core_gate.sh /path/to/problem.txt [reps]
```

Runs both wrappers `reps` times each at 6 and 9 DoF and prints the two spreads.
Compare **distributions, not single runs**: atomicAdd ordering moves a single
60-iteration result by up to ~1e-2 relative, and dubrovnik-142 at 9 DoF is
bimodal (round 9 trap #7). Measured on dubrovnik-142 — CLI 9-DoF
{603390, 610394, 610395} vs core {610407, 603556, 610393}; CLI 6-DoF
{3143773, 3143846, 3143700} vs core {3143711, 3143682, 3143674}. Same modes,
overlapping ranges: PASS.

## Round 11: shared intrinsics (2026-08-23)

COLMAP shares one camera across many images; the solver's camera block carries
one intrinsics triple PER POSE. Rather than re-index every kernel, sharing is
imposed as a **linear constraint**.

Let `B` map the reduced space `[6*ncam poses | 3*ncalib calibrations]` into the
full 9-per-camera space, copying each group's intrinsics out to every pose in
it. The constrained Gauss-Newton system is exactly `(B^T S B) y = B^T b`, so a
matvec becomes broadcast -> existing `S` -> reduce (`MFCalibBroadcast` /
`MFCalibReduce`). **No numerical kernel changed.** The step in the full space is
`B y`, so poses sharing a calibration receive identical intrinsics updates and
cannot drift apart -- the constraint is exact, not an averaging fixup.

API: set `Problem::calibration_index` (one group per camera) and
`num_calibrations`. Leave it null for independent intrinsics; the CLI's
`--dof9` does, so that path is bit-for-bit unaffected. Cameras in a group must
start from identical `focal/k1/k2` -- `Solve()` rejects the problem otherwise,
since which member the caller reads back would otherwise matter.

The preconditioner stays diagonal: `B^T diag(S) B` sums each group's entries.
That misses cross-camera terms within a group, but those live in the Schur
complement, which is never formed -- the unshared path already approximates the
diagonal the same way, so sharing costs no extra accuracy here.

### Gates, and one that was not enough

1. Unshared path unchanged (`run_core_gate.sh`).
2. **Identity map through the reduced path** must match the unshared path.
3. **Group size >= 2** must behave sanely.

Gate 2 alone is insufficient and nearly let a serious bug ship: at `m == 1`
`n_c == n_cf`, so every reduced/full length mix-up is invisible. Two
`cudaMemset` calls cleared only the reduced length on the FULL-space
accumulators `bc` (camera gradient) and `corr` (Schur rhs correction), which
`MFAssemble`/`MFRhsPrime` atomicAdd into at 9-per-camera offsets; the stale tail
compounded every outer iteration. Failure appeared at `m == 2` with full force
-- immediately, not gradually, which is what distinguished a length bug from a
conditioning problem. Fixed cost on dubrovnik-142 at 36 groups: 7.86e14 ->
1.16e9.

Any future work here must test `m >= 2`, not just the identity map.

## Build

```
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j
```

Builds `oca_core`, `oca_cuda` and `test_oca_core`. When added via
`add_subdirectory` from another project only `oca_core` is built.

## Regression gates

1. CD=6 `mfree_shifted_cg` on venice-1672 must track
   `BA_RESEARCH_HISTORY/round9/bench/traces/venice-1672__mfree_fp64.csv`
   to ~1e-11 relative **for the first 15 iterations only**. Beyond that the
   gate is meaningless: measured over 62 iterations, two runs of the *same*
   binary diverge by 1.25e-2 — more than the r9-vs-r10 drift of 4.19e-3 — so
   atomicAdd nondeterminism swamps any regression the gate could detect.
   (The original README stated ~1e-11 without the 15-iteration qualifier it
   was actually validated under.) For a full-length check, compare
   distributions over replicates, not single traces.
2. `validate_grad12.py` must PASS (no GPU needed).

Benchmark driver: `BA_RESEARCH_HISTORY/round10/bench/bench10.sh`.
