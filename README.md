# Prism — one Krylov sweep, a spectrum of damped solutions

*(working name during development: MFREE)*

GPU (CUDA) and CPU implementations of a matrix-free Levenberg–Marquardt bundle
adjuster. The name is the mechanism — like a prism splitting one beam into a
spectrum, the solver splits a single Krylov sweep into solutions for an entire
spectrum of damping values — **multi-shift CG with a ζ-recurrence**, the
candidate steps scored by true nonlinear cost.

## Layout

- `gpu/` — the CUDA solver (`oca_cuda.cu`, BAL/dof9 path; `oca_rigfisheye.cuh`,
  rig-fisheye CD=14 path), generated Jacobian kernels, core tests, and the CPU
  reference header used by the bit-compat gates (`mfree_cpu.h`).
  Snapshot of the `mfree_combo` research tree, 2026-09-01.
- `cpu/` — standalone instrumented CPU port (`mfree_cpu_instr.h`) with a
  minimal driver (`cpu_drv.cc`). Used for prototyping (the block-congruence
  preconditioner was built here first) and for CPU-vs-GPU parity checks.
- `docs/` — the cumulative results compendium (`ba_report.pdf`) and its
  generator (`mkreport.py`; regenerates every table from raw solver traces).

## Solver architecture (GPU)

Two-block BA: Schur-complement point elimination with an augmented Givens-QR
point factor (conditioning κ(V)^½, not κ(V)), matrix-free S·v as
Pass1 → V⁻¹-apply → Pass2 over CSR indexing, multi-shift CG over the damping
menu σ_l = λ·10^(l−grid_down), checkpointed candidate extraction, and a
per-camera block-congruence preconditioner (L⁻¹SL⁻ᵀ + σI — the shift survives
as σI, so the shared Krylov space and the menu survive preconditioning).

## Environment flags (all default-off, bit-compatible)

| flag | validated setting | effect |
|---|---|---|
| `OCA_RHO_LAMBDA` + `OCA_GRID_DOWN=2` + `OCA_RHO_SHIFT` + `OCA_ALPHA_RHO` | on (cold solves) | ρ-gated λ policy v3 + two-sided menu |
| `OCA_BLOCKEQ` | on | block-congruence preconditioner (9×9 per camera; 6×6/3×3 reduced space under shared intrinsics) |
| `OCA_BLOCK_CM` | 1 | atomics-free camera-major factor build |
| `OCA_MENU_GATE` | 1e-2 | skip scoring degenerate menus (gates on ζ-recurrence predictions; canonical order preserved) |
| `OCA_FTOL` / `OCA_FTOL_K` | 5e-5 / 5 | persistent relative-decrease stop |
| `OCA_CKPT_MAX` | 32 (cold) | cap CG checkpoint depth |
| `OCA_NSHIFTS` | 5 (default) | menu width; 1 = classical LM (research knob) |
| `OCA_LAM_FLOOR` | 8 (default) | damping-floor decades below λ₀ (diagnostic knob) |
| `OCA_FORCE_UNSHARED` | research only | disable calibration groups (BAL benchmarking) |

## Headline results (details and caveats in `docs/ba_report.pdf`)

- vs **Caspar** (GPU baseline), 23 BAL problems: better final on 16/23, median
  4.5× faster to Caspar's own final where ahead; muell mapper end-to-end at
  parity with 29% less time in global BA; 4/4 monocular Fuchsberg conversions
  won (1.1–2.8× crossings, endpoint wins with the ftol stop).
- vs **CPU Ceres**: 6.7× end-to-end on the muell sequence; ~2× faster to equal
  quality on BAL (~20× on the large sets). Ceres' converged minima are only
  ~0.3% better in median — and Ceres lands in bad basins too (+274% on
  ladybug-598).
- The λ menu buys ~0% endpoint quality; its value is time-to-quality (2×) and
  basin stability (single-shift is bimodal). Keep L=5.
- Known variance case: ladybug-1723 is chaotic under block scaling (21.6%
  spread from a 1e-15 input perturbation; diagonal path is bit-stable there).

## Provenance

Extracted from the COLMAP-adjacent research trees (`mfree_r10` → `mfree_combo`)
on the lambda workstation. The integration shim into COLMAP
(`--BundleAdjustment.backend MFREE` / `--Mapper.ba_global_backend MFREE`) lives
in the COLMAP tree, not here.
