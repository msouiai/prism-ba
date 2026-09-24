# Student's-t robust kernel: CUDA port (2026-08-30)

Ports the EM-adaptive Student's-t IRLS kernel from the CPU reference port to
the GPU solver, and exposes it through the COLMAP backend. Huber and Cauchy
came along for free (same weight plumbing). The multi-shift machinery is
untouched: the kernel only reweights the assembly, so the solver sees an
ordinary weighted Gauss-Newton system and the λ menu still costs one matvec
stream.

## What changed

**Solver (`oca_cuda.cu`, `oca_core.h`)**
- `OcaRho` / `OcaRobustW` — device+host IRLS kernels, formula-identical to the
  CPU port's `RobustRho`/`RobustW` (0 = L2, 1 = Huber, 2 = Cauchy, 3 = t).
- `KernelCost` takes `(rk, rk_a2)` and applies ρ; `ComputeCost` forwards them.
  Both default to L2, so every other solver in the file is untouched.
- `MFAssemble` takes `(rk, rk_a2)` and applies `sqrt(w)` to the residual **and**
  the Jacobian rows, after the `r2acc` accumulation (which is the geometric
  radius and independent of weighting) — same ordering as the CPU port.
- `KernelResidSq` — per-observation |r|², a verbatim copy of `KernelCost`'s
  body so the scale can never be estimated from a re-derived projection.
- `KernelTEMSum` — one EM M-step accumulation `Σ u_i s_i`,
  `u_i = (ν+2)/(ν+s_i/σ²)`.
- `RobustUpdateScale` (host lambda in `SolveMFreeShiftedCG`): auto-inits σ from
  the residual median (`median ≈ 1.386σ²`) when no σ₀ is given, then runs 3 EM
  sweeps. Called once before the initial cost and once per **assembly**, so the
  scale is frozen across a candidate menu and across assembly-reusing inner
  retries — one consistent objective per outer, which candidate scoring
  requires. Mirrors the CPU port exactly.
- `oca::Options` gains `robust_kernel`, `robust_scale2`, `robust_nu`.
- Under a robust kernel, `Result::initial_cost`/`final_cost` are taken from the
  solver's own log (the robust objective) instead of the surrounding bare
  `ComputeCost` calls, which are L2.

**COLMAP integration**
- `MFreeBundleAdjustmentOptions`: `robust_kernel`, `robust_scale_px`,
  `robust_nu` (pixels in, squared scale computed in the wrapper).
- `colmap_ba_compare`: `COLMAP_MFREE_KERNEL=huber:<px> | cauchy:<px> |
  studentt:<ν>[:<σ₀px>]`.
- `mfree_cpu_test`: `MF_KERNEL` now configures **both** legs, so the GPU kernel
  is gated against the validated CPU one on the same problem; `MF_DUMP_BAL_GPU`
  writes the GPU endpoint for external scoring.

**Rig / fisheye path (`oca_rigfisheye.cuh`) — ported 2026-08-30**
- `RFCostKernel` applies ρ; `RFAssemble` applies `sqrt(w)` to the residual and
  Jacobian rows of ACTIVE observations only (the inactive branch already
  returns with zeroed fragments, so mask semantics are untouched).
- `RFResidSqKernel` / `RFTEMSum` mirror the CD=9 pair with one rig-specific
  difference: **inactive observations are marked `-1` and excluded from the
  scale fit**, not folded in as zero residuals. Counting 27k masked
  observations (gba_164) as `s = 0` would drag σ toward zero and silently turn
  the kernel into a hard outlier filter.
- `RigFisheyeOptions` gains the same three fields; the COLMAP rig site maps
  them; `SolveRigFisheye` carries them with L2 defaults.

**Everything stays optional.** Every kernel on both paths is off unless asked
for: `robust_kernel = 0` is the default in `Options`, `RigFisheyeOptions` and
`MFreeBundleAdjustmentOptions`; the solver signatures default `rk = 0`; and
with it off both paths are byte-for-byte the pre-existing L2 solver (gates
below). ν is a free parameter (`robust_nu`), so the whole t family is
available rather than one hard-coded tail weight, and σ can be pinned
(`robust_scale_px`) or estimated (0).

**Exposed as CLI options too** (needed for `bundle_adjuster`, which the rig
path uses): `--BundleAdjustmentMFree.robust_kernel|robust_scale_px|robust_nu`.

## Gates

| gate | result |
|---|---|
| ladybug-49, kernel off | cost/λ trajectory **bit-identical** to the champion trace, re-verified after the wrapper edits |
| GPU↔CPU parity, `studentt:4`, venice-52+outliers | **ALL PASS** — T1 initial cost 5.6e-15, T3a bit-parity iters 0–1 = 1.8e-14, T3b/T3c/T4a/T4b within tolerance (same atomics-divergence-then-reconverge signature as L2) |
| rig gba_164, kernel off (after the rig port) | 5.243732e6 / 57.6 s / 28 iters — inside the path's measured ±4e-5 spread (5.243677–5.243732e6 across this binary and production's 5.243688e6) |
| ladybug-49 kernel off, after the rig port | still bit-identical |
| GPU vs CPU endpoint quality | clean-L2 within 0.6%, median and inlier rate identical (table below) |

## Quality — controlled contamination

venice-52 with 10% gross outliers injected (30–300 px), **scored on the clean
90% only**, 60 outers:

| kernel | clean-L2 (GPU) | clean med \|r\| (GPU) | clean <2px (GPU) | clean-L2 (CPU ref) |
|---|---|---|---|---|
| L2 | 2.3621e8 | 6.6440 px | 22.83% | 2.3700e8 |
| Cauchy(2px) | 9.5791e5 | 0.2976 px | 97.40% | 9.6098e5 |
| **t, ν=4, σ̂ auto** | 1.1640e6 | **0.2585 px** | 96.56% | 1.1570e6 |

The t kernel matches a hand-tuned Cauchy with **no scale hyperparameter**, and
the GPU reproduces the CPU reference.

## Quality — natural outliers (venice-1778, no injection)

| kernel | median \|r\| | inliers <2px | inlier-L2 | total sum_sq |
|---|---|---|---|---|
| L2 | 0.4396 px | 96.29% | 2.1884e6 | 4.0417e6 |
| t, ν=4 | **0.3143 px** | 94.98% | **1.5645e6** | 5.9740e8 |

Read this honestly: the t kernel fits the bulk substantially better (median
−28%, inlier-L2 −28%) by **abandoning ~1.3% more observations** to large
residuals — which is what a heavy-tailed model is supposed to do, and why the
total sum_sq explodes (it is dominated by the abandoned tail). Whether those
65k observations are genuine outliers is a data question, not a solver
question; on a pipeline that culls outliers between solves this is the desired
division of labour, but **total-L2 is not a valid comparison metric here** —
score robust runs on inlier-L2 only.

## Cost

- **Runtime:** venice-1778, assembly 9.876 s → 11.238 s over 60 outers =
  **+22.7 ms/outer** (+13.8% of assembly, ~2% of the outer). That is the EM
  pass: 1 residual kernel + 3 reductions. The rest of the wall difference
  (65 → 73 s) is trajectory, not overhead — a different objective takes a
  different path.
- **Memory:** final-4585 (9.1M obs) peak 5,120 → 5,190 MiB = **+70 MiB**,
  exactly the `nobs × 8 B` residual buffer.

## Rig / fisheye results (gba_164, 1560 images, 4.6M obs)

Scored on the written model; `inlier-L2` at 2 px is the comparable metric.

| run | iters | wall | accepts/rejects | median \|r\| | inliers <2px | inlier-L2 |
|---|---|---|---|---|---|---|
| input (before BA) | — | — | — | 0.6676 px | 92.84% | 3.0598e6 |
| L2 (default stop) | 28 | 57.6 s | 28 / 18 | 0.6627 px | 93.11% | 3.0479e6 |
| L2, budget-matched | 60 | 233.6 s | 43 / 233 | 0.6627 px | 93.11% | 3.0478e6 |
| **t, ν=4, σ̂ auto** | 60 | **116.9 s** | **60 / 0** | **0.5625 px** | 91.86% | **2.5182e6** |

The budget-matched row is the one that matters: given the same 60 iterations,
L2 gains *nothing* over its 28-iteration stopping point (median and inlier-L2
identical to 4 digits) while spending 234 s and 233 rejected steps. The t
kernel reaches a **15% better median and 17% better inlier-L2 in half that
wall with zero rejects**. So the improvement is not "more iterations" — L2 has
converged and cannot get there.

Same caveat as the BAL path, stated plainly: the inlier fraction drops
93.11% → 91.86%, i.e. ~57k observations move beyond 2 px. The rig's far-field
mask also releases slightly more observations (inactive 26,913 → 26,471... in
fact *fewer* stay masked, 26,471 vs 26,913, so the geometry improved enough to
bring some rim observations back inside the valid cone). Total sum_sq is not a
valid cross-kernel metric here and is reported only for completeness.

## Incidental finding

On final-4585 — the suite's only reject-storm dataset (190 rejects under L2
with the current λ policy) — the t kernel converges with **0 rejects** in 60
accepted outers (97.8 s). The rig path now shows the same pattern
independently: 233 rejects under budget-matched L2 versus 0 under the t
kernel. The heavy-tailed observations that produce the toxic point relaxation
get downweighted, so the τ-escalation ladder never fires. Two datasets on two
different code paths is worth investigating as a general property of the
robust weighting, though it is not yet established as one.

## Artifacts

- `solver_changes.diff` (adds the kernel; `mfree_r10` untouched)
- `colmap_changes.diff` (wrapper, driver env, test harness)
- Runs: `/tmp/agent/parity_t4.log`, `/tmp/agent/gpu_v52o_*.log`,
  `/tmp/agent/xtr/venice-1778_prof_{off,studentt}.trace`,
  `/tmp/agent/xtr/final-4585_studentt.trace`
- Scorers: `/tmp/agent/inlier_l2.py` (BAL), `/tmp/agent/inlier_model.py` (COLMAP model)

## Reproduce

```bash
# parity gate (GPU vs CPU, robust kernel active)
MF_KERNEL=studentt:4 MF_RHO=1 OCA_GRID_DOWN=2 OCA_RHO_SHIFT=1 OCA_ALPHA_RHO=1 \
  mfree_cpu_test /tmp/agent/venice-52-outliers.txt 12

# end-to-end through the benchmark driver
COLMAP_MFREE_KERNEL=studentt:4 OCA_RHO_LAMBDA=1 OCA_GRID_DOWN=2 \
  OCA_RHO_SHIFT=1 OCA_ALPHA_RHO=1 COLMAP_BAL_SIMPLE_RADIAL=1 \
  COLMAP_BA_ONLY=mfree COLMAP_BA_REFINE_INTRINSICS=1 \
  colmap_ba_compare --bal:<file> <outdir>
```
