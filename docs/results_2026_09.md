# Prism — consolidated results, September 2026

> **⚠ CORRECTION 2026-09-05 — §1 IS SUPERSEDED. READ THIS FIRST.**
>
> An independent audit (`/workspace/agent_rev/fresh/REPORT.md`) demonstrated
> that the Caspar baselines in §1 are **fp32** on 15 of 23 scenes: the harness
> that produced them was built with `CASPAR_USE_DOUBLE:BOOL=OFF` (verified in
> `/workspace/colmap_rev/build_combo/CMakeCache.txt`), while the "10× budget"
> column is the **f64** standalone binary — two different solvers in one table.
> The auditor re-ran the missing scenes with standalone f64 at 200 and 2000
> iterations; I independently reproduced two of the flips (ladybug-1469:
> Caspar-f64 4.2558e5 in 6.9 s vs our 5.9498e5 = **we are +39.8% worse**, not
> −12.1% better; ladybug-1197: 3.6696e5 vs our 3.7737e5 = **+2.8% worse**, not
> −17.1% better).
>
> **Corrected ledger vs Caspar-f64 — the tally depends on the arm rule, so all
> three are given** (independently re-derived and reproduced in
> `/workspace/agent_rev/prec/`): single pre-registered config (block, quality
> profile, N≥3 medians) **5W / 5T / 13L, worst +65.7%**; the first audit's rule
> **5W / 6T / 12L, worst +40.1%**; best-recorded-across-quality-arms
> **9W / 6T / 8L, worst +3.0%**. What survives every rule, precision and
> budget: **final-4585 −38%** and **final-3068 −7.2% (block) / −13.8% (diag)**.
> The λ-explosion "stall class" is an fp32 artifact on **6 of its 7 scenes** —
> in f64 only final-3068 persists (insta360 is rep-dependent), though f64 is
> not stall-free (final-4585 shows a λ plateau).
>
> **fp32 is Caspar's as-published configuration** (its own paper's experiments
> are float32; the vendored generator defaults to it), so an fp32 column is
> legitimate *labelled as such* — the defect was mixing precisions within one
> table and presenting the result as the algorithmic comparison.
>
> **The broken baseline also steered our arm selection.** The diag arm was only
> ever run where block looked contested *against the fp32 baseline*. Completing
> the diag column (21/23) turns ladybug-1469 from +40% to **+1.7%**, venice-52
> to +0.23%, wins venice-1672 (−1.8%), and deepens final-3068 to −13.8%: diag
> scores **7W / 5T / 9L with no loss worse than +3.2%**. Diag, not block, is the
> defensible pre-registered default (gating cell final-4585 in progress).
>
> §1's "Prism" column is additionally a post-hoc best-of-{block,diag} selection
> made after seeing results, and the diag arm was only ever run on the scenes
> where block looked contested. A single fixed configuration scores materially
> worse. Any future table must fix one configuration in advance, or report the
> arm-selection rule as part of the method.
>
> **§3 is unaffected EXCEPT one sentence**: "beats Caspar-f64 on 21/22 dumps"
> is the same threshold inflation §1 was retracted for — the honest count at a
> ±0.01% tolerance is **10 wins / 12 ties / 0 losses** (independently recounted
> twice). The wall claims stand. Also unaffected: the N=3 end-to-end 10.5%
> pipeline / 41.6% BA-phase gain (non-BA work equal across arms to 0.7%; the
> different-trajectory confound is empirically absent), and §4's solver
> changes, with two attribution corrections: the ρ point-constant is **−1.0%**
> in the controlled same-machine A/B (the −5.2% figure subtracted across two
> different machines), and "43.6 → 2.3 ms/eval" splices a worst-case before
> against a best-case after from different configs.
>
> **§2's speed multiples are NOT yet corrected**: they were computed against
> fp32 endpoints. Recomputed against f64, a single-config Prism reaches
> Caspar-f64@200's endpoint on 11/23 scenes and f64-best on 7/23; the
> 7.6×/3.7×/2.3× crossing multiples need a fast-profile rerun before reuse.
>
> **Process rules adopted** (full text in `/workspace/agent_rev/prec/PROTOCOL.md`):
> verify the baseline's build configuration in the same session as the numbers;
> log `score_init` on every run and assert it against an independent evaluation
> of the BAL file at 1e-6 (this doubles as an fp32 fingerprint — an fp32 build
> cannot pass); pre-register ONE Prism configuration, or a selection *rule* run
> everywhere with its overhead counted; N≥3 per verdict cell with printed
> spreads, verdict only if |Δmedian| > 0.15% AND ranges are disjoint; stamp
> provenance per cell; re-run stale baselines rather than quoting them.
>
> One earlier claim in the first audit is itself **withdrawn**: the alleged
> "+0.69% lossy BAL→COLMAP conversion" is a misdiagnosis — standalone fp32,
> which involves no conversion, reproduces the harness `score_init` on every
> scene tested; the offset is fp32 *evaluation* of near-singular observations.
> The f64 baseline is sound and the corrected ledger needs no redo.

Machine unless stated: RTX 2000 Ada, 70 W (the "budget" tier). Objective:
SIMPLE_RADIAL / `--dof9 --zero_k2` (f, k1 free; k2 = 0), identical for all
solvers. Caspar = the vendored SymForce-derived GPU BA solver (arXiv
2605.30583), run standalone in both precisions.

**Standing conventions.**
1. Never write "Caspar converges to X". No Caspar run in this benchmark
   converges: 16/23 hit its 200-iteration cap while still descending, 6/23
   stall by λ-explosion, 1/23 stops early. Write "its 200-iteration default
   lands at X" or "it stalls at X".
2. Where we end lower, always report the crossing — our wall to reach *its*
   endpoint — not endpoint walls alone.
3. Tail claims need N ≥ 5. N = 3 produced a "+4% worst case" claim that N = 5
   revised to +12.8% (see `shi2` below).

---

## 1. Quality vs Caspar, 23 BAL problems

Prism = best arm under the quality profile (`OCA_FTOL=1e-5 K=8`,
`--max_iter 600`); per-scene block/diag choice. Caspar column = the better of
its 200-iteration default and, where run, a 2000-iteration budget (10×).

**15 wins / 3 ties / 5 losses** against best-of-both-budgets. Every loss is
≤ +2.6%; our wins reach −38%. On every win Caspar never reaches our endpoint
at any budget.

| scene | Caspar-200 | Caspar-2000 | Prism | Δ |
|---|---|---|---|---|
| final-4585 | 1.1035e7 | 1.1456e7 | **6.8262e6** | −38.1% |
| final-3068 | 2.6317e6 | — | **1.8121e6** | −31.1% |
| ladybug-1723 | 6.5345e5 | — | **4.5340e5** | −30.6% |
| ladybug-1197 | 4.5533e5 | — | **3.7738e5** | −17.1% |
| ladybug-1469 | 6.7672e5 | — | **5.9498e5** | −12.1% |
| venice-1672 | 2.4636e6 | — | **2.3484e6** | −4.7% |
| trafalgar-126 | 1.0666e5 | — | **1.0411e5** | −2.4% |
| trafalgar-201 | 1.1400e5 | — | **1.1134e5** | −2.3% |
| venice-52 | 2.7964e5 | — | **2.7396e5** | −2.0% |
| venice-52-noisy | 1.2840e6 | — | **1.2657e6** | −1.4% |
| ladybug-49 | 1.3618e4 | — | **1.3569e4** | −0.4% |
| venice-1778 | 2.1116e6 | 2.0181e6 | **2.0109e6** | −0.4% |
| ladybug-598 | 1.8186e5 | — | **1.8140e5** | −0.25% |
| venice-89 | 3.1050e5 | 3.0667e5 | **3.0613e5** | −0.18% |
| dubrovnik-88 | 3.5755e5 | — | **3.5734e5** | −0.06% |
| muellcontainer-90 | 2.9754e5 | 2.9691e5 | 2.9691e5 | tie |
| final-1936 | 5.0530e6 | 5.0496e6 | 5.0499e6 | tie |
| final-93 | 1.5844e5 | — | 1.5836e5 | tie |
| insta360-3086 | 1.0828e6 | — | 1.0853e6 | +0.23% |
| dubrovnik-173 | 3.7896e5 | — | 3.8011e5 | +0.30% |
| ladybug-810 | 2.2434e5 | — | 2.2584e5 | +0.67% |
| dubrovnik-135 | 4.7478e5 | 4.7414e5 | 4.8386e5 | +2.05% |
| trafalgar-257 | 1.2041e5 | 1.1632e5 | 1.1934e5 | +2.60% |

Caspar's stop mode, all 23: **16 cap-limited** (still descending at cutoff),
**6 λ-explosion stalls** (all five ladybug scenes + venice-1672: damping grows
1.8e3–1.7e5×, PCG drops to ~0–2 iterations, cost freezes), 1 early stop.
The stall class is the robustness result — it is the failure our τ-ratchet and
damping menu exist to survive.

## 2. Speed vs Caspar

Iso-quality crossings (fast profile, 70 W): dubrovnik 7.6×, venice 3.7×,
trafalgar 2.3×, final-13682 1.3× (a both-axes win on the budget card, versus
0.4× on a 4090). Prism reaches Caspar's own endpoint faster than Caspar does
on 10/23 scenes; on most of the rest Caspar's short wall is an early stall,
not speed.

**Hardware tilt.** Caspar is fp32-FLOPs-bound, Prism bandwidth-bound, so every
margin roughly doubles moving from a 4090 to the 70 W card. Quality columns are
machine-identical; only the time axis moves.

## 3. Product workload (Fuchsberg/muell)

*Per-GBA-call sweep, 22 dumps (24 → 493 cameras)*: Prism's fast profile beats
Caspar-f64's endpoint on 21/22 (1 tie) and Caspar-f32 on 22/22, reaching
Caspar-f64's endpoint in 0.5–6 s against its 3–32 s walls. The margin grows
with map size (−0.00% at 30 cameras → −1.59% at 493).

*Largest single GBA (gba_234: 8,788 cameras, 16.75M observations)*: Prism-fast
3.0012e7 / 49.7 s and Prism-all-on 3.0017e7 / 27.5 s beat Caspar-f32
(3.0037e7 / 95 s) and Caspar-f64 (3.0019e7 / 252 s) on **both** axes — up to
9.2× less wall.

*End-to-end incremental mapping, N = 3 interleaved*: **Prism 1051 s vs Caspar
1174 s (10.5% faster)**, ranges non-overlapping, maps statistically identical
(493/493 registered both, reprojection 1.1099–1.1107 px, interleaved). On the
BA phase alone Prism is **41.6% faster** (167.4 s vs 286.4 s over ~48–50 calls);
that 119 s delta accounts for essentially all of the 123 s pipeline delta.

## 4. Solver changes that produced the September gains

| change | flag | effect |
|---|---|---|
| ρ point-block constant | `OCA_RHO_PT` | final-4585 −5.2% cost at half wall; ρ was inflated, under-damping λ |
| block-reduced cost kernel | default (was opt-in) | 43.6 → 2.3 ms/eval at 29M obs |
| dead equilibration work | default | `MFDiagK` + `E` build skipped on block outers (provably unread) |
| τ-split point factor | default | O(nobs) Givens once per assembly; retries replay 3 τ rows |
| rig-path ports | default | same two fixes in the fisheye/rig solver (−52 s end-to-end) |
| CG depth cap | `OCA_CKPT_MAX=32` | with ρ fix: final-4585 1135 → 357 s at better cost |
| bug fixes | — | double-free, ~240 MB dead VRAM, per-call cudaMalloc, `final_lambda` wiring |

Storm-scene net: **7.11e6 @ 1135 s → 6.74e6 @ 357 s.**

## 5. Refuted (documented, kept default-off)

fp64 on-the-fly Jacobians (4–7× slower — validates stored fragments);
subsampled and fp32 candidate scoring (3 designs); fp32 stored fragments on
basin-sensitive scenes (2/3 reps +48%); τ warm-starting (3 variants);
polynomial congruence (quality-neutral, matvecs never repaid); per-shift
convergence pruning (menu gate already owns that regime); geometric-mean streak
rebase; learned λ selection (see §6).

## 6. The recurring finding: basin selection, not linear algebra

Three independent experiments say locally optimal choices do not survive the
trajectory:

- **Resection–intersection opening.** RI descends 34× in 2 s on final-4585
  (our solver needs 27 s to match) and ends **35% worse**. Dose-response:
  1 sweep +0.3%, 2 +16.7%, 3 +34.6%, then saturation — **the basin is committed
  within ~3 greedy sweeps**.
- **Branched rollouts.** Immediate-best λ equals horizon-best λ only 1 time in
  9; the greedy penalty is +21%/+116%/+33% in the first outers and ~0 after
  outer 10. Where greedy costs +116%, the hand-tuned ρ-anchored policy already
  picks the shift adjacent to the horizon winner.
- **Learned λ control.** A gradient-boosted ranker with genuine offline skill
  (top-2 capture 0.72 vs ≤0.29 for fixed sets) is catastrophic deployed
  (+853% worst case), reproducing the single-shift failure on exactly the scene
  where single-shift is known to be bimodal.

Corollary measured across three solvers (Caspar's fp32 PCG, our multi-shift CG,
trivial RI alternation): endpoints differ by 20–60% in inconsistent directions
per scene. Basin selection, not inner-solver sophistication, separates BA
solvers on this benchmark family.

**Late RI is the one place a perturbation helps** — and it does not generalize.
ladybug-1197 with RI at outer 20 (N=5): median −11.4%, **worst −0.27%** (its
worst run beats the champion's median), half the wall, and it removes the
champion's +25.4% lottery. The same arm at outer 40 is +8.3%/+27.6%, and on
ladybug-1723 it is +1.1% median with a **+74% worst case**. Scene- and
timing-specific; unshippable as a fixed schedule.
