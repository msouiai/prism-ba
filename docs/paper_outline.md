# Paper outline — "Prism: matrix-free multi-shift bundle adjustment on the GPU"

Working skeleton, 2026-09-09. Every number cited here exists at N=3 in
REPRODUCE.md / agent_rev/ unless marked (N=1). Numbers vs converged f64
Caspar unless stated.

## 1. Introduction
- GPU BA baselines (Caspar/SymForce line) are fast per iteration but stall on
  a measurable problem class; CPU Ceres is robust but slow. Claim: a
  matrix-free multi-shift LM that evaluates a damping MENU by true nonlinear
  cost closes the quality gap and, with one damping schedule, the remaining
  accuracy floor — while staying within small wall multiples.
- Contributions:
  C1. Multi-shift Schur-free LM: L shifted systems per Krylov sweep,
      (shift x depth) candidates scored by TRUE cost. (Prior art honestly:
      Frommer-Glassner recurrences; ARC_qK same-architecture for cubic reg;
      Lin/O'Malley/Vesselinov recycling for LM least squares. Ours: the
      true-cost menu, shift-preserving preconditioning, BA-scale GPU.)
  C2. An empirical law with three independent confirmations: mechanisms that
      strictly improve the per-outer objective do not improve endpoints —
      the accept gate is already greedy-optimal; the only open channel is
      basin selection, decided in outers ~1-8.
  C3. The accuracy floor: measured mechanism (thin-track over-fitting in the
      opening; state-diff + self-handover + cross-handover controls) and its
      fix (annealed point-damping floor = per-point trust region), closing
      every clean-reference loss to <= +0.01%.
  C4. A measurement methodology that survived its own failures: five recorded
      retractions with causes (fp32 baseline; budget-wall speedups; stopping-
      rule confound; allocation non-inertness; crashed-baseline reference).

## 2. Method
- Two-block matrix-free Schur (Pass1 -> (V+tau D)^-1 via augmented Givens ->
  Pass2); stored fp64 Jacobian fragments (on-the-fly refuted 4-7x).
- Multi-shift CG, zeta recurrence; sigma_l = lambda*10^(l-2); checkpoints
  {8..128}; true-cost scoring; rho-gated Nielsen lambda; retry ladder.
- Preconditioning that PRESERVES shift structure (Jacobi arm pre-registered;
  block-congruence as basin selector, reported but not selected per scene).
- The repair pass (OCA_RETRI): closed-form DLT reset, per-point cost gated.
- Config S: tau >= c*lambda annealed (c=10, gamma=0.8) + span escalation.
  Present as: an explicit per-point trust region on the point block, annealed
  to zero — the TR that works, vs TR-as-step-selection which does not (§6).

## 3. The central law (the paper's spine)
- Table: repair (+4.5% endpoint despite per-point gating), iterated alpha
  (+0.47% despite true-cost gating), one-step supervised lambda
  (catastrophic tails), opening greed (lower cost at outer 5 -> worse
  endpoint; the purest instance).
- Basin commitment window: handover dose-response cliff at 3-8 iterations
  (dubrovnik-173 flips +0.79% -> -0.02% between N=2 and N=3).
- Consequence for algorithm design: candidate-SET changes safe,
  scoring-perturbation changes derail; damping-mechanism changes survive,
  scheduling changes do not (catalogue in §8).

## 4. The accuracy floor: mechanism
- The loss class: 5 scenes, +0.07..+1.13%, spreads 0.001-0.06%.
- Ruled out: stopping (7-20x iterations closes median 5%), basin
  reachability (warm-start from Caspar descends BELOW it: finisher wins),
  restart protocol (self-handover = cold).
- The measurement: state-diff at outer 5 — indistinguishable in
  distance-to-optimum; cost lead concentrated monotonically on thin tracks
  (-63% on 2-obs tracks). Interpretation: static tau lets the opening
  over-fit fragile points against immature cameras; basin committed.
- Nine failed interventions (trust-region selection, phase gates, menu
  damping, rho recalibration, lambda floors...) — the knob-guessing record
  that motivates measuring states, not tuning parameters.

## 5. The fix and its price
- Config S table (11 scenes, N=3): five wins over converged Caspar, worst
  clean loss +0.14% (lb-1723; the rest <= +0.01%); final-3068 keeps -15%; final-4585 keeps Config C.
- The price, decomposed: iterations FEWER than Caspar (23 vs 67 to 0.5%);
  per-outer 2-4x structural (scoring) amplified ~8x by anneal-window rejects;
  rejects INTRINSIC (thin-only floor does not remove them); SPAN=3 the one
  free lever (-23%).
- Descent-rate crossover moves 1% -> 0.2% gap: the explicit cost of the
  basin. Profiles: R = speed (crossover 1%, production walls 7-31x under
  Caspar's converged budget), S = quality (floor closed). [Wide-grid middle
  profile if reps confirm: N=1 shows 3.3x wall cut at +0.19pp, and
  final-3068 -15.2 -> -17.3%.]

## 6. Trust region done right and wrong (the TR section)
- TR-as-selection (GLTR-lite over the menu): helps exactly one scene,
  detonates another (8.8x); wide grid mitigates; REFUTED as a candidate.
- TR-as-point-damping (Config S): the version that works. Connect: the
  alpha-boundary lesson (removing an accidental trust region hurt).
- ARC_qK comparison: same sweep architecture; their ladder-walk retries are
  INERT here because the true-cost menu already plays that role; their grid
  width transfers (NSHIFTS=13) and is where the benefit lives.

## 7. Evaluation
- 24-BAL ledger (R: 11W/6T/6L worst +1.13; S: to be re-run full-set —
  panel projects worst clean loss ~0). Speed honestly: two frames
  (converged-target walls; descent-rate crossover tables). Production
  workloads: muell 22 ties at 31x wall; fuchsberg 5 ties to 16.75M obs at
  12x wall (ratios vs Caspar's converged budget; crossover caveat printed
  with every table). final-13682 pending. Reproducibility: dose-response,
  spreads, frozen binaries, pre-registration.

## 8. Refutation catalogue + methodology (the reviewers' section)
- ~30 refuted ideas grouped; the five retractions with causes; protocol
  rules 1-9 (baseline build check, outer-count check, allocation
  non-inertness, crashed-baseline check, N>=3 + own-spread verdicts...).

## 9. Limitations
- Storm class needs Config C (final-4585 DNF under R/S; wide-grid rescue
  pending); per-outer cost structurally 2-4x Caspar; monocular BAL only
  (rig geometry untested under S); single-GPU walls; lb-1723 baseline crash.

## Open experiments feeding this draft
- [ ] Full 24-BAL under S; [ ] muell/fuchsberg walls under S;
- [ ] wide-grid reps (final-3068, S-middle profile); [x] final-4585 rescue: REFUTED (2 reps DNF, ~1900 rejects — even sigma=lam*1e10 fails on storm outers);
- [x] final-13682: EXCEEDS 16GB VRAM here (OOM at assembly; ran on 24GB 4090 historically); Caspar@2000 itself crashes exit=2 at this scale, @200 = 2.405e7/337s is the only clean baseline this card produces.
- [x] lb-1723 clean reference: Caspar clean at budgets 100-400 (best 447363@400), CRASHES >=800 (diag 4e8-2e9). Config S = +0.135% vs clean ref -> headline corrected to 'worst clean loss +0.14%'.
- [ ] S+C composition.
