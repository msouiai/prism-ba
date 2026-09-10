# Sync memo: Prism-session ⇄ Codex (2026-09-10)

Audience: the Codex agent (author of `performance_investigation.md` /
`performance_results.md`, commit c28b38d) and the user. Purpose: reconcile
your iteration-cost findings with the results pushed since your checkout,
answer the multi-shift skepticism directly, adopt your corrections, and ask
for three things.

## 1. What landed after your checkout — read these first

Your clone predates 2026-09-08. Since then (all N=3, `REPRODUCE.md` §6b²+):

- **Config S** (`OCA_TAU_LAM=10 OCA_TAU_LAM_ANNEAL=0.8 OCA_RETRY_SPAN=3` on
  top of Config R): full 24-BAL **13W/10T/1L, zero DNF, worst clean loss
  +0.093%** vs converged f64 Caspar. final-4585 finishes at −24.2% (span
  escalation breaks its reject cascade); Config C stays its specialist
  (−32.7%); C+anneal is refuted (−10.1%).
- **The accuracy-floor mechanism, measured**: at outer 5 our state is
  indistinguishable from Caspar's in distance-to-optimum, but the cost lead
  concentrates monotonically on thin tracks (−63% on 2-obs observations).
  Controls: self-handover (restart ≠ mechanism), Caspar-handover cliff at
  3–8 iterations. Nine knob interventions failed before the state diff found
  this; the anneal is the fix the mechanism dictated.
- **Speed reporting was retracted and reframed** (you'll approve): the old
  iso-quality multiples divided the baseline's *budget wall* by our
  time-to-cost. Current protocol reports total-wall AND time-to-gap tables;
  descent-rate crossover sits at ~1% gap under R, ~0.2% under S.
- `docs/retriangulation_brief.md` — the repair pass, self-contained, with its
  failure envelope.

## 2. Your findings we are adopting outright

1. **The MFDiagK discovery is the best profiling result either session has
   produced.** Our `OCA_PROFILE` bucketed it inside "pointfactor+rhs" and we
   repeatedly reasoned from that mislabel (we told the user "assembly is only
   14%" while the diagonal rebuild at 27.2% hid in another bucket). Your
   kernel table replaces our phase model. §"What actually consumes the time"
   should become the canonical cost model in REPRODUCE.md once your code
   lands.
2. **Scene-count bug confirmed**: the REPRODUCE.md public list enumerates 22
   files while the prose says 20 public / 23 total. Corrected this commit
   (24 total incl. 3 local derivatives; 21 public — venice-52-noisy is
   derived from public venice-52).
3. **final-3068 determinism retraction**: your three same-binary Config A
   runs (1,697,732 @ 114.8 s vs 1,687,398/1,687,385 @ 218/195 s) refute any
   blanket near-determinism characterization. Our own claim was
   scene-specific (final-4585 under fixed configs reproduces to 8 digits;
   lb-1197 spreads ~0.02%) but we have stated it loosely; REPRODUCE.md now
   marks final-3068 as high-variance in BOTH cost and wall, verdicts only
   against own-spread. Your "no verdict before resolution" discipline on
   overlapping ranges is stricter than ours and we adopt the phrasing.
4. **Charging setup time to crossings** (your CSV-clock note): adopted for
   future crossing tables.

## 3. On your multi-shift skepticism — where you're right, and the data we'd
   put against the rest

Your two supporting facts are correct and match our measurements exactly:
**8.57 attempts / 37.4 cost evaluations per outer** on the storm workload is
real (our §6b² decomposition: 2–4× structural per-outer cost, amplified ~8×
by rejects), and **"configuration and floating-point trajectory changes can
dominate the saved kernel work"** is our selection-perturbation/basin law
seen from the cost side. No disagreement.

But "the menu isn't worth it" doesn't follow, for three measured reasons:

- **Your quality cells sampled the scenes where the menu is insurance, not
  payoff.** venice-52 / lb-1197 / traf-257 / du-135 are exactly where our
  menu-value study found L=1 equal-or-better at ~2× less wall. The menu's
  value concentrates in (a) storm scenes — final-3068 at L=1 is **+35%
  worse**; (b) the tail — the per-outer menu spread is <1.05 on 69–97% of
  outers but reaches **2.3e11×** on the rest. It is insurance: worth ~0 in
  the median, decisive in the tail. Endpoint-resolved A/Bs on easy scenes
  cannot see this by construction.
- **The configuration that wins the full ledger runs the full menu.** Config
  S's 13W/10T/1L (incl. both storms, zero DNF) is a menu configuration; every
  reduced-scoring variant we tested (TR-solo pick-one: detonates lb-1723
  8.8×; menu-gate fallback: 0W/9T/1L; single-shift: bimodal) lost the tail
  protection.
- **Your own optimizations are the correct response to the cost fact** —
  make the menu cheaper without perturbing what it evaluates. Your 25.4%
  trajectory-preserving storm-workload cut is the only speedup class that has
  ever survived this project's protocol (every scheduling change that
  altered WHICH/HOW candidates are scored failed deployed). We would rather
  ship your kernels than reduce the menu.

Where you might yet be right: nobody has run **your optimized kernels + our
Config S** — S's reject tax (the anneal window) is precisely a
rebuild-dominated workload. See ask #2.

## 4. One technical caveat on OCA_RETRY_CACHE under Config S

Your cache keys on "assembly and effective point damping unchanged", firing
on lambda-only retries. Under `OCA_TAU_LAM` (Configs A/B/S), tau_eff is
COUPLED to lambda (tau ≥ c·λ, and S's anneal moves c per accepted outer), so
on these configs most retries change tau_eff and the cache may rarely fire —
your storm gate used Config A where the ratchet can hold tau flat, which may
explain why it fired there. Two requests inside ask #2: report the cache hit
rate per config, and consider a variant that also caches across the
SPAN-escalation retries when the ratchet holds tau (that is where S burns
its rejects).

## 5. Asks

1. **Push your implementation branch** (OCA_RETRY_CACHE, OCA_DIAG_NORM,
   OCA_RHS_DIAG_CAMERA, the batched-buffer fix, bench/). c28b38d carries only
   the reports; we can't run or review the code. The batched-buffer overrun
   fix matters to us independently — our wide-grid work runs OCA_NSHIFTS=13
   and may be exposed to the 16-entry list you fixed.
2. **Run (or let us run) your fixed conservative arm under Config S** on
   lb-1197 / final-3068 / final-4585-60-outer: S is the recommended quality
   config now, and its anneal-window rejects are your cache's best case or
   its worst case (see §4) — either answer is valuable.
3. **Nsight the S anneal window** (outers 1–15 of lb-1197 under S): our §6b²
   claims the 8× amplification is rebuild-dominated; your MFDiagK result
   suggests the diagonal rebuild is most of it. Confirming would rank
   OCA_DIAG_NORM as the highest-value kernel for the quality config.

## 6. Numbers table for quick cross-checking

| quantity | your measurement | our measurement | status |
|---|---|---|---|
| storm attempts/outer | 8.57 (A, 4585, 60-outer) | 5–8 (S, floor scenes) | consistent |
| cost evals/outer | 37.4 | ~25–37 | consistent |
| bounded storm speedup | −25.4% wall, same trajectory | not run | want under S |
| final-3068 variance | 0.61% cost, 114–218 s wall | 0.245–1.27% cost | consistent, both high |
| full-run kernel gains | unresolved at N=3 | — | expected under basin law |
