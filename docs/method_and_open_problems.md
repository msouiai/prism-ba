# Prism: method, measured laws, and the open problem

A self-contained brief for someone (or some agent) picking this up cold.
Everything here is measured unless marked as conjecture. Where a claim was
retracted, the retraction is stated rather than the claim deleted.

---

## 1. The problem

Bundle adjustment: minimise `F(x) = ½ Σ_obs ‖r_obs(x)‖²` over camera
parameters (6-DoF pose + intrinsics) and 3D point positions. Two-block
structure: each residual couples exactly one camera and one point, so the
Gauss-Newton normal equations partition as

```
[ H_cc  H_cp ] [dx_c]   [b_c]
[ H_pc  V    ] [dx_p] = [b_p]
```

with `V` block-diagonal (3×3 per point). Eliminating points gives the Schur
complement `S = H_cc − H_cp V⁻¹ H_pc`, dense in the camera block.

Levenberg–Marquardt adds damping. **The damping is where our whole story
lives** (§6), so state it precisely: we damp the camera block with `λ` and the
point block with a separate `τ`, i.e. we solve

```
(S(τ) + λ D_c) dx_c = b′(τ),    S(τ) = H_cc − H_cp (V + τ D_p)⁻¹ H_pc
```

Caspar (our baseline, arXiv 2605.30583) instead damps **every** block with one
relative multiplier.

## 2. Our method

- **Matrix-free Schur.** `S` is never formed. One matvec = Pass1 (scatter
  `Wᵀv` to points) → VinvApply (apply `(V+τD)⁻¹` via a cached augmented-Givens
  QR factor, 6 doubles/point) → Pass2 (gather `Wu` back to cameras). Per-obs
  Jacobian fragments (27 doubles) are stored once per assembly; recomputing
  them on the fly in fp64 was measured 4–7× *slower* (bandwidth beats FLOPs on
  modern cards), so stored fragments are the validated design.
- **Multi-shift CG.** One Krylov sweep solves `(S + σ_l I)x = b` for `L = 5`
  shifts simultaneously via a ζ-recurrence (Frommer–Glässner; verified
  term-for-term against the code). `σ_l = λ·10^(l−grid_down)`, so the menu
  spans two decades below and two above the current λ. Shift-invariance holds
  because **τ is frozen within an outer iteration** — that is what makes
  `S(τ)` one fixed operator that the σ's shift.
- **Candidate scoring.** Iterates are snapshotted at CG depths
  {8,16,32,64,128}; each (shift, depth) candidate is evaluated by the **true
  nonlinear cost** (2 full observation passes). The winner sets the step and
  anchors the next λ (ρ-gated Nielsen). This is the expensive part: 27–45% of
  wall.
- **Preconditioners.** Jacobi (`diag`) or a block-congruence
  `L⁻¹SL⁻ᵀ` (shift-preserving, so the menu survives). Block is a *basin
  selector*: far better on some scenes, catastrophic on others.
- **Outer policy.** Eisenstat–Walker forcing; on reject an inner retry ladder
  escalates λ ×10 and (for the 9-DoF path) ratchets τ, reusing the assembly;
  persistent-flatness stopping (`OCA_FTOL`, `OCA_FTOL_K`).
- fp64 throughout; fp32 fragment storage is optional and basin-unsafe (§5).

## 3. Measured cost model (RTX 4090, final-13682, 29M obs unless noted)

| phase | share |
|---|---|
| candidate evaluation | 27–45% of wall (45% on storm scenes) |
| point factor + rhs | 32% |
| Krylov (matvecs) | 10.8% on storm scenes, 41.9% on venice |
| assembly | 2.5% |
| host/sync slack | 3.5–13% |

Storm scenes spend **78% of wall in retries** (final-4585: 2,333 retries per
313 accepts). 79% of candidate evaluations on such scenes occur on attempts
where nothing can be accepted. Krylov is *not* the bottleneck where the
solver struggles — a fact that kills most obvious "optimise the CG" ideas.

## 4. Empirical laws (the useful part)

1. **Selection-perturbation law.** Changing *which* candidates are evaluated
   is safe; changing *how* any candidate is scored derails the trajectory.
   Subsampled scoring (3 designs), fp32 scoring, and even reordering the
   evaluation with an order-independent tie-break all failed, +11% to +380%.
2. **The basin is committed in the first ~3–5 accepted outers.** Three
   independent measurements: an RI (resection–intersection) opening shows a
   monotone dose-response (1 sweep +0.3%, 2 +16.7%, 3 +34.6%, then saturation);
   branched rollouts show immediate-best λ equals horizon-best λ only 1 time in
   9, with the greedy penalty huge early (+21/+116/+33% at outers 0/2/5) and
   ~0 after outer 10; cross-restart tests show Caspar restarted from our
   outer-5 state converges to *our* endpoint, and from our outer-1 state ends
   +89% worse than from scratch.
3. **One-step labels are broken in both directions.** For λ they undervalue
   looseness (the horizon winner sits ~1 decade looser); for CG depth they
   *overvalue* depth. A one-step *oracle* scores 0.35 top-2 capture where a
   horizon-trained model reaches 0.537 — the label's ceiling is below the
   model's floor.
4. **Basin lottery is scene-specific and large.** Branch-level noise on
   ladybug-1197: median 12.7%, p95 81.5%. venice-52 and final-3068 are
   ~0.00%. **N = 3 is not enough for a tail claim** — it has twice produced
   claims that N = 5 overturned.
5. **Process traps that have cost us real time.** Unknown `OCA_*` env vars are
   *silently ignored*, so a stale binary turns an A/B into
   champion-vs-champion. Baseline build configuration must be verified in the
   same session as the numbers (see §7).

## 5. Refuted — do not re-propose without new evidence

fp64 on-the-fly Jacobians (4–7× slower); subsampled and fp32 candidate
scoring; fp32 stored fragments on basin-sensitive scenes (2/3 reps +48%);
τ warm-starting (3 variants); polynomial congruence preconditioning
(quality-neutral, matvecs never repaid — PoBA's own Fig. 2 agrees);
per-shift convergence pruning (menu gate already covers it); geometric-mean
streak rebase; learned decisiveness gating (analytic gate wins out-of-scene);
learned grid centering (45% of winners sit at the grid edge); one-step
supervised λ selection (offline top-2 capture 0.72 → +846% deployed worst
case); learned EW forcing; marginal-value-per-matvec stopping (fires 0/3,522);
per-attempt learned depth; cross-attempt Krylov reuse.

## 6. What actually worked, and why

| change | effect | mechanism |
|---|---|---|
| ρ point-block constant (`OCA_RHO_PT`) | −1.0% cost, damps reject storms | ρ's denominator omitted ½·b_pᵀ(V+τD)⁻¹b_p, inflating ρ and under-damping λ |
| block-reduced cost kernel (default) | 43.6 → 2.3 ms/eval at 29M obs | a single global `atomicAdd` was serialising millions of threads |
| τ-split point factor (default) | retries replay 3 Givens rows instead of an O(nobs) sweep | τ enters only the 3 trailing augmentation rows; R is row-order invariant |
| dead-work deletion (default) | −11–15% of storm wall | `MFDiagK` + equilibration build a vector never read on the block path |
| streak depth cap (`OCA_STREAK_CKPT=8`) | identical endpoint, −18.6% wall | streak sweeps must seed at the worst-conditioned shift so EW never fires, yet streak-ending accepts win at depth ≤8 in 91–94% |
| **uniform damping floor (`OCA_TAU_LAM=c`)** | 9W/9T/4L vs Caspar-f64, worst loss +0.44% (22 scenes, N=2–3) | fixes the damping asymmetry of §1 |
| **monotone floor (`OCA_TAU_LAM_RATCHET=1`)** | strictly better again, and removes the per-scene flag — see §7.3 | the floor can never follow λ back up into the storm |

Note the pattern: **every survivor is a mechanism fix or a regime-gated
integer rule on a signal that is already free. Nothing model-shaped has ever
survived deployment here.**

## 7. The open problem

### 7.1 What we found
Against **f64** Caspar we were losing an entire scene class (ladybug, several
venice). Diagnosis, in order:

- Our finisher is not at fault: handed Caspar's converged ladybug solution,
  Prism improves it by 0.01–0.02%. Both endpoints are mutual local minima.
- Forensics on our outer-1 retry ladder: it ends in a point relaxation with
  **frozen cameras** (λ→1e5, τ≈1e-3) that flings thin-track points out of the
  scene — max ‖ΔX‖ = 2.4e4 against a scene radius of ~83, on a scene where 48%
  of points have only 2 observations. The whole endpoint gap lives in ~200
  points; the top 10 carry 54% of it.
- **Root cause = the §1 asymmetry.** We damp cameras with λ but points with a
  static τ = 1e-7, so *every* menu candidate contains an effectively undamped
  point half-step. The λ menu cannot see this because all five candidates
  share the defect.
- A 12-arm single-factor ablation confirms it: **only the τ family moves the
  endpoint.** Menu width, CG depth, grid span, λ₀, ρ-gating, classic-LM,
  λ-floor and stopping are all null or worse. The parts of the solver that got
  the most tuning contribute essentially nothing to basin selection.

### 7.2 The fix and its cost
`OCA_TAU_LAM=c` floors `τ ≥ c·λ` (c = 1 reproduces Caspar's uniform damping;
self-annealing as λ decays). Measured, diag arm, N = 2–3, vs Caspar-f64:
**9 wins / 9 ties / 4 losses across 22 scenes, worst loss +0.44%** — versus
the pre-registered block config's 5W/5T/13L with a +65.7% worst case.

### 7.3 The conflict, and how it was resolved

`final-4585` is the one scene that **rewards the asymmetry**. The requirements
looked incompatible, and under any λ-tracking floor they are:

| policy | final-4585 | ladybug-1197 | ladybug-1723 | venice-52 |
|---|---|---|---|---|
| floor off (champion) | best (−41% vs Caspar) | +3.0% | +1.4% | +0.2% |
| floor, `K=1` (one outer) | **−42%, best ever** | +9.3% | +5.3% | +2.2% |
| floor, `K=3` / unlimited | +55% vs our champion (4,667-reject storm) | +0.02% | +0.23% | **−1.91%** |

Two resolution attempts failed, informatively:

- **A-priori predictors: refuted.** obs/pt, 2-obs fraction, initial cost/obs,
  pt/cam, obs/cam and the outer-1 signature were all measured; none separates
  final-4585. That class is identifiable only by behaviour.
- **Runtime discriminator (`OCA_TAU_LAM_AUTO`, reject-to-accept ratio): fires
  too late.** The ratio *does* separate the regimes (2.8 on ladybug vs 7.9 on
  final-4585) and correctly leaves the ladybug fix intact, but it trips at
  outer 6–8, by which time the basin is committed — final-4585 still ends at
  1.06e7. This is §4.2 applying symmetrically: any trigger that waits for a
  storm signature is already too late.

**What worked: a MONOTONE floor** (`OCA_TAU_LAM_RATCHET=1`),
`τ_floor ← min(τ_floor, c·λ)`. Diagnosis: with the plain coupling τ collapses
back down *together with* λ after every recentre, so the toxic point
relaxation is re-probed again and again — that is the 4,667-reject signature.
The ladybug class only needs the floor **high early**; once the basin is
chosen it does not care. A floor that can never rise again satisfies both.

Measured, N=3, vs Caspar-f64:

| scene | ratchet | plain coupling |
|---|---|---|
| final-4585 | **−6.38%** (deterministic, no storm) | +55% vs our champion |
| ladybug-1197 | +0.02% | +0.02% |
| ladybug-1723 | **+0.13%** | +0.23% |
| ladybug-1469 | **+0.27%** | +0.44% |
| venice-52 | **−2.26%** | −1.91% |

So the ratchet is **strictly better than the plain coupling on every scene the
coupling helps**, and it removes the need for a per-scene flag: one uniform
configuration (diag + `OCA_TAU_LAM=1 OCA_TAU_LAM_RATCHET=1`) wins or ties
everywhere tested. That matters beyond the numbers — a pre-registered single
config is what makes the ledger legitimate (§8.4); best-of-arms is not a
result.

Cost: it leaves our own final-4585 margin on the table (−6.4% where `K=1`
reaches −42%). A full 23-scene N=3 ledger with this single config is the
current measurement in flight.

### 7.4 The open question now

**Can the τ decision be made by SELECTION rather than by POLICY?**

Motivation from the pattern in §6: every *policy* we have tried fails to
generalise across scene classes, while **true-cost candidate selection has
never failed** — it is the one mechanism in this solver that reliably picks
the right thing per scene, per outer, with no tuning.

Concretely: during the early outers, score the winning step's point half with
**both** τ values (floored and static) and let the existing accept gate
choose. On the ladybug class the damped point half should win; on final-4585
the undamped one should. This needs no discriminator and no flag, and it is a
candidate-**set** change, which §4.1 permits (scoring inputs stay exact).

Implementation notes for whoever takes it: the τ-split point factor
(`MFPointFactorObs` / `MFPointFactorTau`) already makes a second τ cheap — the
O(nobs) Givens sweep is shared and only the 3 trailing augmentation rows are
replayed, so an alternative point half costs one extra `MFPointFactorTau` +
`MFVinvApply`/`MFBackSub` + one cost evaluation. Gate it to the first few
outers (the commitment window of §4.2) so the extra evaluation is negligible.
Caveat to check: strictly, τ changes `S(τ)` and therefore the camera step too,
so re-solving only the point half yields a *different valid candidate*, not
"the step the unfloored solve would have produced". That is legitimate — any
step is a legal candidate and the true-cost gate decides — but the report
should not claim it is equivalent to an unfloored solve.

Secondary open items, in priority order:
1. Product workload under the new config (muell end-to-end + the 22-dump GBA
   sweep). The mechanism is about thin-track points and street/rig scenes are
   exactly that regime; this is also the result class that has survived every
   audit.
2. Recompute the §2 speed/crossing multiples against f64 — they are currently
   computed against fp32 endpoints and are knowingly stale.
3. Whether the ratchet also subsumes `OCA_RHO_PT` and the storm policy
   (`OCA_CKPT_MAX=32`), which were tuned against the pre-ratchet dynamics.

## 8. Standing methodological rules

1. Never claim a baseline "converges" without checking: no Caspar run in this
   benchmark does (16/23 hit an iteration cap, 6/23 stall by λ-explosion).
2. **Verify the baseline's build configuration in the same session as the
   numbers.** Our 23-scene headline was invalid for months because the
   baseline was fp32 on 15/23 scenes while we ran fp64. fp32 is Caspar's
   *as-published* configuration, so an fp32 column is legitimate — but it must
   be labelled and never mixed with f64 cells in one table.
3. Log `score_init` and assert it against an independent evaluation of the
   input file at 1e-6. This doubles as an fp32 fingerprint.
4. Pre-register **one** configuration, or a selection *rule* run everywhere
   with its overhead counted. Best-of-arms chosen after seeing results is not
   a result.
5. N ≥ 3 per verdict cell, N ≥ 5 for tail claims; report medians *and* worst
   cases with spreads; a verdict requires |Δmedian| > 0.15% **and** disjoint
   ranges.
6. Report crossings in both directions, not endpoint walls alone.
