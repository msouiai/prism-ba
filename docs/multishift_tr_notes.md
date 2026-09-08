# Multi-shift CG as a trust-region engine: literature mapping and design notes

2026-09-08. Research pass over TR/Krylov methods, triggered by the OCA_TRUST_SOLO
result (+0.505% -> +0.368% on ladybug-1197, the first native movement on the
accuracy floor).

## 1. Where our solver sits in the literature

**GLTR** (Gould, Lucidi, Roma, Toint 1999; convergence sharpened in
arXiv:1908.02674 and Springer ACM 2024): solve the TR subproblem *exactly
within the Krylov subspace* via the Lanczos tridiagonal and a secular equation
in lambda. One basis serves every radius. Our multi-shift sweep is a
DISCRETISATION of the same object: L points on the regularisation path
lambda -> x(lambda), from one Krylov process. GLTR gets the whole path but
must store/regenerate the basis; we get L points with O(1) vectors per shift
and never store the basis. `xnp[l]` (per-shift step norms, already computed)
is the sampled version of GLTR's ||y(lambda)||.

**ARC_qK** (Dussault & Orban, Math. Programming 2023, arXiv:2103.16659) is the
closest published relative to our architecture, independently arrived at:
Lanczos-CG with shifts, ONE operator-vector product per iteration regardless
of the number of shifts (their Algorithm 3.1 = our zeta-recurrence sweep in
Lanczos form). Differences that matter, feature by feature:

| | ARC_qK | Prism |
|---|---|---|
| grid | **31 shifts, 10^-15..10^15** — the whole half-line | 5 shifts, lambda*1e-2..1e2 |
| per-shift extras | x_i, p_i vectors + scalars | same (xs[l], ps[l]) |
| step selection | secular condition alpha*lambda_i = \|\|d_i\|\| — model only, ONE f-eval | TRUE COST over all (shift x depth) — 25 evals |
| unsuccessful step | **walk UP the precomputed ladder** — zero extra solves | escalate lambda, FULL re-solve per retry |
| per-shift negcurv | sign of gamma_j per shift, free; i+ = smallest PD shift; interrupt below | Steihaug test on the SEED truncates the whole sweep |
| per-shift stop | freeze shift when \|\|r_i\|\| (free, = sigma_j) meets inexactness | OCA_SHIFT_PRUNE (refuted for wall, but their freeze saves the CG axpys, ours only skipped scoring — different economics) |

**Blockwise-ARC** (arXiv:2608.22129, Aug 2026): single shift from a cubic
secular equation, but two transferable facts: (a) the shift bounds the
effective condition number — kappa_eff <= 2 + O(lambda_1/sqrt(M||g||)) — so
the REQUIRED Krylov depth per shift is predictable in advance,
L = O(sqrt(kappa_eff) ln(1/eps)); heavily-damped shifts need shallow sweeps.
(b) exact-subspace cubic step via the tridiagonal preserves the O(eps^-3/2)
complexity proof even matrix-free.

**Lin/O'Malley/Vesselinov 2016** (already in the notes): GKL/LSQR subspace
recycled across damping values — the same observation from the least-squares
side; we measured their extraction losing to multi-shift CG per iteration.

## 2. What this buys us, mapped to MEASURED problems

1. **Rejects are re-solves only because our grid is narrow.** The reject
   investigation concluded rejects are GENUINE: no candidate in
   [lambda*1e-2, lambda*1e2] improves. ARC_qK's answer is a grid spanning the
   half-line: an "unsuccessful step" walks up the precomputed ladder at zero
   solve cost, and the ladder cannot run out. Extra shifts cost only 2 vectors
   (n_c each) + a few BLAS-1 ops per CG iteration — on our problems n_c ~ 40K
   floats vs matvecs touching 9-17M observations, i.e. ~free. final-4585 pays
   197 re-solves in 40 outers; a wide grid converts most of that to walking.

2. **The adaptive-menu-size question dissolves under TR selection.** With
   OCA_TRUST_SOLO the number of SCORED candidates is 1 per checkpoint
   regardless of grid width: the radius picks the shift (largest step inside
   Delta — norms are monotone in sigma, so it is a bracketing scan over
   xnp[]). So: **grid width is decoupled from scoring cost.** Width, the
   expensive-looking knob, is cheap; scoring, the cheap-looking knob, is
   expensive (2 observation passes each). Wide sweep, narrow scoring.
   The menu-flatness data (69-97% flat) says scoring diversity rarely pays;
   the tail (2.3e11x) says the GRID must stay wide for insurance. This
   assignment satisfies both.

3. **Per-shift negative curvature (their gamma-sign test) fixes a measured
   defect for free.** Our menus show nfin < 5 (mean 3.67/5 on ladybug-1469):
   small shifts on an indefinite S produce garbage candidates that we either
   score wastefully or skip via isfinite. ARC_qK's i+ floor identifies the
   smallest PD shift from the recurrence scalars alone and considers nothing
   below it. Also protects the seed: our Steihaug test truncates the WHOLE
   sweep on seed negcurv even when every damped shift is fine.

4. **GLTR-continuous lambda is available later if the grid quantisation ever
   binds:** reconstruct the Lanczos tridiagonal from CG scalars (standard
   alpha/beta relation, free), solve the secular equation for lambda*(Delta),
   score the bracketing pair. Candidate-SET change; scores untouched.

## 3. Refuted-overlap warnings (do not re-buy these)

- Per-shift convergence pruning as a WALL saver: refuted (OCA_SHIFT_PRUNE).
  ARC_qK freeze differs only in saving the axpys; on GPU those are ~free, so
  do not expect wall from it.
- Menu-gate fallback (score the rest when the gated seed fails): refuted
  0W/9T/1L — gated rejects are genuine. The wide grid attacks the same
  problem from the solve side instead of the scoring side.
- One-sided widening DOWN (more aggressive shifts) is contraindicated by the
  opening result: our opening is already too greedy. Widen UP only.

## 4. The experiment this note motivates (running as `wtr`)

Config R + `OCA_NSHIFTS=13 OCA_GRID_DOWN=2` (grid lambda*1e-2..1e10)
+ `OCA_TRUST=1 OCA_RHO_PT=1 OCA_TRUST_SOLO=1` (radius picks, one score).
Three-way against Config R and against 5-shift TR_SOLO: does WIDTH add
anything beyond TR selection? Watch: reject counts (should collapse if 2. is
right), the two win-scenes (insurance check), and outer counts (TR_SOLO runs
~2x more outers; the wide ladder may cut that by never wasting an outer on a
hopeless window).
