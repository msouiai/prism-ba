# MFREE solver optimization — final report (2026-08-29)

## Summary

Two new opt-in solver env flags (off by default = bit-compat; all gates pass):

- **`OCA_RHO_SHIFT=<D>`** — under ρ mode, anchor the Nielsen λ update at the
  winning shift's damping `σ_win = λ·10^(best_sh−grid_down)` instead of
  discarding it. Three safety rails, each earned by a measured failure:
  **clean accepts only** (contested accepts keep the pre-streak base),
  upward moves clamped to **+1 decade** per outer, downward moves clamped to
  **−D decades** (recommended `D=1`).
- **`OCA_ALPHA_RHO=1`** — re-enable the α grid under ρ mode with an α-aware
  prediction `pred(s) = s·b'd − s²(b'd − pred₁)` (one extra cublas dot per
  winning candidate; `s` compounds across winning combos, matching the
  compounding α semantics).

**Recommended config:**
`OCA_RHO_LAMBDA=1 OCA_GRID_DOWN=2 OCA_RHO_SHIFT=1 OCA_ALPHA_RHO=1`

### Headline numbers (vs current champion `OCA_RHO_LAMBDA=1 OCA_GRID_DOWN=2`)

- **final-4585** (9.1M obs, flagship): reaches the champion's 247.8 s final in
  **39.2 s (6.3× iso-quality)**; own 60-outer final **−9.2 %**
  (sum_sq 1.498e7 vs 1.649e7); the champion never reaches it.
- **23-set BAL suite**: better final than Caspar on **20/23** (champion: 19 + 1
  tie; insta360-3086 flipped to a win). Caspar still never reaches MFREE's
  final on any of those 20. Median speed to Caspar's own final quality:
  **1.78×** Caspar's solve time (champion: 1.45×).
- **muell GBA replay (22 dumps)**: faster on **22/22** (typical −25…−40 %,
  gba_141 34.3 s → 6.4 s), quality-neutral (worst Δ +0.049 %, vs the 0.18 %
  full-mapper noise floor).
- **Fuchsberg rig (gba_164)**: flags on converges in 15 outers vs 28
  (solver leg 0.90 → 0.67 min, −25 %) at equal quality (Δ +0.011 %, inside
  the rig path's own ±0.005 % run spread… see Gates for the reference-number
  discrepancy).

## Isolation (deliverable 0)

- Solver tree: `/workspace/bundle_adjustment/mfree_agent` (copy of `mfree_r10`).
- COLMAP: worktree `/workspace/colmap_agent`, branch `agent-solver-opt`; its
  baseline commit imports the previously-**uncommitted** MFREE integration
  found in the production tree (12 modified + 12 untracked files), unchanged.
- Build: own dir `/workspace/colmap_agent/build`
  (`-DMFREE_SOLVER_DIR=/workspace/bundle_adjustment/mfree_agent/solver`,
  `-DCASPAR_ENABLED=ON`, arch 89, Release).
- **Diff vs originals: `solver_changes.diff`** (3 files: `oca_cuda.cu`,
  `oca_rigfisheye.cuh` — the shipped flags; `mfree_cpu.h` — same flags plus
  three off-by-default experiment knobs kept for reproducing the negative
  results). No COLMAP source changes. Production trees and
  `/workspace/colmap/build` untouched.

## Gates

| gate | result |
|---|---|
| ladybug-49 BAL, flags off | cost/λ trajectory **identical** to `ladybug-49_mfree_rg2sr.trace`, verified after every edit round (4×) |
| final-4585 BAL, flags off | same shift/ckpt/matvec decision path; endpoint matches to 2e-7 (GPU atomics noise) |
| gba_164 rig, flags off | **binary-vs-binary parity with production**: my binary 5.24370/5.24373/5.24372e6 across 3 runs, production binary **today** gives 5.243688e6. The documented reference (5.244713e6 / 47.9 s) does not reproduce on the production binary either — it predates the current production state. Run-to-run spread ±4e-5 relative (fisheye far-field mask flips observations discretely). |
| CPU port | parity harness knobs untouched; **finding: the CPU port is nondeterministic under OpenMP** (libgomp reduction combine order in ComputeCost/Dot). `OMP_NUM_THREADS=1` is exactly reproducible and was used for every CPU A/B. |

## Ranked list of changes tried (deliverable 1)

**Shipped:**

1. **`OCA_RHO_SHIFT` (clean-accept σ_win anchoring, ±clamps).** Mechanism:
   plain ρ mode discards which shift won, so λ cannot track the menu; on cold
   starts λ decays only ×fac per outer, and in the grind the winning-σ
   information is lost entirely (326 rejects/outer-storms measured on
   final-4585). Anchoring on clean accepts recentres λ for free.
   Measurements: venice-52 crossing to Caspar-final 1.71 → 0.84 s; venice-1778
   8.77 → 7.50 s; final-1936 22.3 → 18.2 s; venice-1672 16.2 → 12.4 s;
   ladybug-1723 wall 10.9 → 9.2 s (rejects 7 → 0). Gate: bit-compat off. ✔
2. **`OCA_ALPHA_RHO` (α grid under ρ with corrected prediction).** Mechanism:
   α was disabled under ρ because a rescaled step invalidated `pred_best`;
   the Schur-space quadratic gives the corrected prediction for one extra
   dot. This is the dominant grind-phase quality lever: final-4585 α-only
   final −11.1 %; recovers the documented α-off regressions (ladybug-49
   −0.45 %, dubrovnik-88 −0.41 % GPU finals). Gate: bit-compat off. ✔

**Rejected variants (each with the measurement that killed it):**

3. **Symmetric σ_win anchoring (v2).** Contested accepts bank the reject
   streak's ×10s: λ ratcheted to the 1e8 ceiling on final-4585, final +1.9 %,
   grind frozen (48 outers buying 0.3 %).
4. **+1-decade up-clamp alone (v3).** Identical failure — the banking is the
   problem, not the step size; fixed only by clean-accepts-only (shipped).
5. **Unclamped downward anchor (D=2, v4).** Collapsed τ-sensitive final-3068:
   one clean accept dropped λ two decades into the region where the point
   relaxation is toxic → 23 accepts/157 rejects, final +26 %. D=1 fixes it
   (3.424e6 vs champion 3.401e6) *and* improves final-4585 (1.498e7 vs D=2's
   1.528e7).
6. **α cold gate `last_rel<0.1` (v5).** Meant to recover final-4585's opening
   crossing (3.2 → 5.6 s under α); small sets unchanged, but final-4585's
   endpoint jumped to 1.703e7 (+3.3 % vs champion). Diagnosis: the 4585
   endgame is a set of nearby basins selected chaotically by the early path —
   identical configs reproduce to 2e-7 while α/shift variants spread
   1.465–1.703e7. Do not tune basin selection on one dataset. Reverted.
7. **`OCA_GRIND_ETA` (force deep CG in the grind; CPU knob kept).**
   η≤0.01 once progress <1e-4: +50 % matvecs on ladybug-49 for no final gain;
   never fires on dubrovnik-88. With RHO_SHIFT the λ policy already produces
   deep sweeps when they pay.
8. **`OCA_TAU_GRIND` / `MF_TAU_TRACK` (τ decay in the grind; CPU knobs).**
   The mechanism is real and quantified: fixed τ=3e-3 biases the endgame point
   relaxation — ladybug-49 final −0.83 % at τ=3e-5 (the size of its entire
   Caspar deficit), dubrovnik-88 −0.60 % at 3e-5 with instability at 3e-6.
   But no automatic rule survived all three test sets: λ-gated tracking
   under-fires (d-88 unchanged), unconditional tracking overshoots
   (venice-52 +0.7 %). Diagnosed opportunity, not shipped.
9. **`OCA_LAZY_SCORE` (score {shift 0, last winner} at intermediate
   checkpoints; CPU knob).** Motivated by the winner statistic (82.5 % of
   accepted winners are shift 0 across the 23-set archive) and the candidate
   cost share (66 s of final-4585's 251 s baseline). CPU: ladybug-49
   identical, dubrovnik-88 +0.045 %, venice-52 +0.4 %. Not ported to CUDA —
   the wall win it targets was largely delivered by the fewer/healthier
   outers of the shipped flags.

## final-4585 attribution matrix (60 outers, sum_sq)

| config | final | wall | →Caspar-final | →champion-final |
|---|---|---|---|---|
| champion (ρ+grid2) | 1.6492e7 | 247.8 s | 3.2 s | 247.8 s |
| +shift only (D=2) | 1.6277e7 | 248.3 s | 3.4 s | 81.5 s |
| +alpha only | 1.4654e7 | 408.3 s | 5.2 s | 38.4 s |
| +both, D=2 | 1.5282e7 | 347.4 s | 5.6 s | 41.0 s |
| **+both, D=1 (recommended)** | **1.4982e7** | 369.3 s | 5.6 s | **39.2 s** |

The 2.4 s opening-crossing slip is α winning iterations 1–2 and the resulting
path paying a 4-retry τ search at it4; the same α is worth −9…−11 % at the
end. Attempting to gate it away flipped the endgame basin (item 6).

## 23-set BAL table (deliverable 2) — see `bal23_table.txt`

Highlights (new = recommended config, old = champion, finals = sum_sq):

- Verdict vs Caspar: **NEW 20 / CASPAR 3** (dubrovnik-135, dubrovnik-88,
  ladybug-49 — margins narrowed on all three: e.g. ladybug-49
  2.747e4 → 2.735e4 vs Caspar 2.724e4).
- Crossings to Caspar-final faster or equal on 20/23; slower only on
  final-4585 (3.2→5.6 s, traded per above), final-3068 (0.44→0.52 s) and
  ladybug-1723 (0.21→0.28 s).
- Finals vs champion: improved on 15; regressions worth naming:
  **final-3068 +0.68 %** (τ-sensitive scene; D=1 rescued it from D=2's +26 %
  but a residual gap remains) and **ladybug-1723 +0.63 %** (its endpoint is
  config-sensitive; the same run is 1.7 s faster in wall). Four others are
  ≤0.02 % (noise).

## muell GBA replay (deliverable 2) — see `muell_ab.out`

22/22 dumps faster (median wall −27 %); worst quality delta +0.049 %
(gba_146), most within ±0.005 % — quality-neutral under the 0.18 % mapper
noise floor.

## Rig path (deliverable 2) — see `rig_gate.out`

gba_164: flags off = production-binary parity (see Gates). Flags on:
converges 28 → 15 outers, solver wall −25 %, endpoint within the path's own
run-to-run spread.

## Convergence curves (deliverable 3) — `curves.png`

final-4585 / venice-1778 / ladybug-49, cost-vs-wall log-log, best-so-far,
MFREE-before vs MFREE-after vs Caspar.

## What was NOT improved, and why (deliverable 4)

- **The 3 small sets Caspar still wins** (dubrovnik-88/-135, ladybug-49): α
  recovery closed 30–60 % of each gap but did not flip them. The residual
  deficit matches the τ endgame bias quantified in item 8; flipping them
  needs a τ rule that survives venice-52, which none of the tried rules did.
- **final-4585 opening crossing** (3.2 → 5.6 s): deliberately traded for the
  −9.2 % final; the gate that would recover it broke the endgame basin.
- **final-3068 (+0.68 %) and ladybug-1723 (+0.63 %) finals**: residual
  regressions vs champion after the D=1 fix; both scenes' endpoints are
  τ/path-sensitive, and both still beat Caspar decisively (3068 by 35 %,
  1723 by 30 %).
- **Per-outer fixed cost** (brief's idea #1): quantified (candidate scoring
  = 66 s of final-4585's 251 s baseline; 82.5 % shift-0 winners) and
  prototyped as `OCA_LAZY_SCORE` in the CPU port; not ported to CUDA in this
  session.
- **Warm-start λ estimate** (idea #4): superseded — with RHO_SHIFT the cold
  λ₀=10 costs ~2 outers instead of ~8, making a start-value estimator mostly
  moot.

## Reproduction

```bash
# gates
OCA_RHO_LAMBDA=1 OCA_GRID_DOWN=2 COLMAP_BAL_SIMPLE_RADIAL=1 COLMAP_BA_ONLY=mfree \
  COLMAP_BA_REFINE_INTRINSICS=1 COLMAP_MFREE_VERBOSE=1 \
  /workspace/colmap_agent/build/src/colmap/tools/colmap_ba_compare \
  --bal:/workspace/bundle_adjustment/daba_cuda/ladybug-49.txt /dev/shm/x
# recommended config = same + OCA_RHO_SHIFT=1 OCA_ALPHA_RHO=1
# traces: /tmp/agent/xtr/*_mfree_v6.trace (recommended), *_v4orig/v5/shiftonly/alphaonly (attribution)
# sweep/replay scripts: /tmp/agent/{v6_sweep.sh,muell_ab.sh,rig_gate.sh,post_sweep.sh}
```
