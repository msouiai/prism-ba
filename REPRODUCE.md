# Reproduce Prism's BAL results from scratch

You are picking this up on a clean machine with no context. This file is the
task. Read `docs/method_and_open_problems.md` first (method + measured laws),
then `docs/results_2026_09.md` (results, including two retractions you must not
undo). This file tells you how to rebuild the numbers yourself.

**Read the retractions before you trust any older number.** Two headline
claims were wrong and were corrected in place: the benchmark baseline was
accidentally fp32 on 15/23 scenes, and the speed multiples derived from it are
withdrawn. Do not resurrect them.

---

## 0. What this solver is, in three sentences

Matrix-free Levenberg–Marquardt bundle adjustment on the GPU. The Schur
complement is never formed; a **multi-shift CG with a ζ-recurrence** solves
`(S + σ_l I)x = b` for L=5 damping values in ONE Krylov sweep, iterates are
snapshotted at CG depths {8,16,32,64,128}, and every (shift, depth) candidate
is scored by the **true nonlinear cost**. The winner sets the step and anchors
the next λ.

The most important empirical result is not about the menu: it is that
**basin selection dominates everything**, and that the point/camera damping
ratio — not the search — decides which basin you land in (§7 of the method
doc).

## 1. Environment

- Linux, CUDA 12.x, a CUDA GPU. Development was on an RTX 2000 Ada (70 W) and
  an RTX 4090. **Absolute walls are not comparable across GPUs; ratios are.**
- `cmake >= 3.20`, a C++17 compiler, `cublas` + `cusolver`.
- Set your architecture: the CMake default is `OCA_CUDA_ARCHITECTURES=89`
  (Ada). Use 86 for Ampere, 90 for Hopper, etc.

```bash
git clone <this repo> prism && cd prism/gpu
cmake -B build -DOCA_CUDA_ARCHITECTURES=<your arch>
cmake --build build -j
./build/oca_cuda --help        # sanity
```

## 2. Data

The 23 BAL problems are public. Base URL:
`https://grail.cs.washington.edu/projects/bal/data/<family>/problem-<N>-<pts>-pre.txt.bz2`

Families/sizes used here: `ladybug` (49, 598, 810, 1197, 1469, 1723),
`trafalgar` (126, 201, 257), `dubrovnik` (88, 135, 173, 356), `venice`
(52, 89, 1672, 1778), `final` (93, 1936, 3068, 4585, 13682).
Decompress to plain `.txt`; the CLI reads the standard BAL format.
(`venice-52-noisy`, `muellcontainer-90` and `insta360-3086` are local
derivatives — skip them if you only have public data; the ledger is still
meaningful on the remaining 20.)

## 3. The objective — get this identical or nothing else matters

All runs use `--dof9 --zero_k2`: 9 parameters per camera (6-DoF pose + f + k1 +
k2) with **k2 held at 0**, i.e. SIMPLE_RADIAL. Cost is `0.5 * Σ ‖r‖²`.
If you compare against another solver, verify its cost convention and its
**build configuration** before comparing (see §7 rule 2 — this is the mistake
that invalidated months of our numbers).

## 4. The two configurations to reproduce

Profiles (the difference is only the stopping rule and iteration budget):

```bash
COMMON="OCA_FORCE_UNSHARED=1 OCA_RHO_LAMBDA=1 OCA_GRID_DOWN=2 \
        OCA_RHO_SHIFT=1 OCA_ALPHA_RHO=1 OCA_MENU_GATE=1e-2 \
        COLMAP_MFREE_VERBOSE=1"
FAST="$COMMON OCA_FTOL=5e-5 OCA_FTOL_K=5"                     # + no --max_iter
QUALITY="$COMMON OCA_FTOL=1e-5 OCA_FTOL_K=8"                  # + --max_iter 600
```

**Config A — "robust" (best worst case):**
```bash
env $QUALITY OCA_TAU_LAM=1 OCA_TAU_LAM_RATCHET=1 \
  ./build/oca_cuda --problem <bal.txt> --algo mfree_shifted_cg \
                   --dof9 --zero_k2 --max_iter 600
```

**Config B — "lowest total residual":** add
`OCA_TAU_LAM_COND=0.2 OCA_RETRY_SPAN=3`.

**Config R — "parameter-free":** `$QUALITY` plus `OCA_RETRI=5` and **none** of
the four damping flags. Reproduce this one first — it is the simplest thing in
the repo that works, and on six of seven scenes it matches or beats A and B
(§6b). It does not survive final-4585.

Note there is **no `OCA_BLOCKEQ`**: the diagonal (Jacobi) preconditioner is the
pre-registered arm. The block-congruence preconditioner is a basin selector —
far better on some scenes, catastrophic on others — and selecting it per scene
after seeing results is exactly the methodological error §7 rule 4 forbids.

## 5. What each flag does and why it exists

| flag | what | why |
|---|---|---|
| `OCA_TAU_LAM=c` | floor the point damping at `τ ≥ c·λ` | We damp cameras with λ but points with a static τ, so every candidate carries an effectively **undamped point half-step**. On tracks with near-parallel rays that step is a near-null direction of the cost: the point flies out of the scene while the residual barely moves. This is the root cause of an entire scene class of losses. |
| `OCA_TAU_LAM_RATCHET=1` | the floor may only ever decrease | Without it τ follows λ back up during a storm and re-probes the toxic relaxation (measured: 4,667 rejects on final-4585). |
| `OCA_TAU_LAM_COND=t` | apply the floor only to points whose undamped block is ill-conditioned (min/max of the `R0f` diagonal `< t`) | Track **length** is the wrong statistic — a 2-view point at 30° is safe, a 5-view point on a straight vehicle track at 0.5° is not. Free: `R0f` is the undamped factor the τ-split already computes. |
| `OCA_RETRY_SPAN=k` | from the k-th reject of a streak, escalate λ by the **menu span** not ×10 | A rejected attempt scored the whole menu, so it refuted damping up to λ·10². Escalating ×10 re-tests 4 of 5 already-refuted shifts. Cuts rejects 1.5–8×. |
| `OCA_STREAK_CKPT=8` | cap CG depth during reject streaks | Streak sweeps must seed at the worst-conditioned shift so the forcing test never fires, yet streak-ending accepts win at depth ≤8 in 91–94%. Verified identical endpoint at −18.6% wall on dubrovnik-356. |
| `OCA_RETRI=k` | every `k` accepted outers, **re-triangulate every point** in closed form from the current cameras (DLT normal equations `Σ(I − dᵢdᵢᵀ)x = Σ(I − dᵢdᵢᵀ)cᵢ`, 3×3 Cholesky), keeping the reset only if that point's own reprojection cost improves | The damping flags *prevent* points from being flung out; this *repairs* the ones that already were, and needs no threshold, no signal and no per-scene decision. On six of seven scenes it matches or beats the whole four-flag damping stack — see §6b. Cost is one extra scatter+solve per fired outer, ~1% of wall. |

## 6. Numbers to reproduce (70 W RTX 2000 Ada, N=3 medians)

Baseline for the Δ column is standalone **f64** Caspar, best of its 200- and
2000-iteration budgets. If you do not have Caspar, reproduce the Prism columns
and the A-vs-B comparison; those are self-contained.

| scene | Config A | Config B |
|---|---|---|
| final-4585 | −6.4% | **−44.0%** |
| final-3068 | **−14.6%** | −14.3% (with `RETRY_SPAN=3`) |
| venice-52 | −2.2% | −6.7% |
| venice-1672 | −2.1% | −3.0% |
| dubrovnik-135 | −2.6% | −1.9% |
| ladybug family | +0.02…+0.27% | +0.20…+0.93% |
| **record** | **10W / 10T / 3L**, worst +0.27%, Σδ −29.2 | **9W / 10T / 4L**, worst +0.92%, **Σδ −66.7** |

Config B is the **recommended default**: it is the only configuration that
gets both storm scenes (final-4585 −43.8% AND final-3068 −14.1%), removes 2.3x
the total residual of A, and all four of its losses are below 1%. Config A has
a tighter tail (worst +0.27%) and suits worst-case-sensitive deployment. Both
are single pre-registered configs — no per-scene flags.

**Speed, stated honestly:** we are **2–36× slower** than f64 Caspar at its
default budget and win quality nearly everywhere; it never reaches our endpoint
even at 10× budget. Per outer iteration we cost 3–10× Caspar's per-iteration
cost, and that ratio tracks the reject count. We do **not** lose on iteration
count.

## 6b. Config R — the parameter-free alternative (reproduce this first)

Add **only** `OCA_RETRI=5` to `$QUALITY`, with **none** of the four damping
flags. One mechanism, no thresholds, nothing to tune per scene. N=3 medians,
same frozen binary and profile as the Config C column:

| scene | plain | Config R (repair) | Δ vs plain | Δ vs Config C | wall C → R |
|---|---|---|---|---|---|
| venice-52 | 260 409 | 241 684 | **−7.19%** | **−5.21%** | 32.2 → 28.0 s |
| dubrovnik-135 | 483 865 | 458 738 | **−5.19%** | **−1.35%** | 15.2 → **3.7 s** |
| ladybug-1197 | 377 389 | 368 096 | **−2.46%** | +0.13% | 33.6 → **9.7 s** |
| ladybug-598 | 181 403 | 179 842 | **−0.86%** | **−0.27%** | 2.7 → 2.9 s |
| final-3068 | 1 690 831 | 1 677 853 | **−0.77%** | **−1.23%** | 100 → 188 s |
| ladybug-1469 | 431 819 | 429 514 | **−0.53%** | +0.22% | 31.2 → **10.9 s** |
| final-4585 | 6 722 008 (1/3 within 3000 s) | **DNF 0/3** | — | — | 511 s → ∞ |

Read this table twice. **One parameter-free geometric pass matches or beats
four tuned damping knobs on six of seven scenes** — better on four, within
0.22% on two — and gets there in 3–4× less wall on three of them. Prefer it
unless you are on a storm-class problem.

**The exception.** On final-4585 the damping stack is load-bearing: repair
alone does not terminate inside 50 minutes, and the repair costs quality
rather than adding it.

**CORRECTED 2026-09-07 — the size of that cost was overstated 3x.** The
original "+15.1%" was measured with `OCA_FTOL_K=8`, which stopped the repair
arm early on a flat patch at outer 27 while the control ran to 65. Re-measured
with `OCA_FTOL_K=40` (both arms hitting the 600-outer cap, so neither is
stopping-rule limited):

| arm | FTOL_K=8 | FTOL_K=40, 600 outers |
|---|---|---|
| no repair | 6 660 346 | **6 422 700** |
| repair + `OCA_RETRI_MAXDROP=0.10` | 7 549 351 | 6 514 124 (+1.42%) |
| repair | 7 712 443 | 6 711 551 (**+4.50%**) |

So the real cost is **+4.50%**, not +15.1%. The lesson generalises past this
flag: **any A/B in which the two arms stop at different outer counts is
partly measuring the stopping rule.** Check outer counts before believing an
endpoint gap (§7 rule 9).

**`OCA_RETRI_MAXDROP` is a diagnostic, not a recommendation — do not ship it.**
It confirmed the re-initialisation story (the outer-5 firing on final-4585
resets 35% of the cloud for a 36.8% cost cut) but fails as a rule:

| scene | outer-5 drop | refusing it |
|---|---|---|
| final-4585 | 36.8% | helps (+4.50% -> +1.42%) but still loses to repair-off |
| **final-3068** | **13.9%** | **hurts (+0.235%)** — that firing was beneficial |
| venice-52 | 3.5% | never fires |
| ladybug-598 | 1.7% | never fires |

The harmful/helpful boundary therefore lies between **13.9% and 36.8%** — a
factor of 2.6, not the order of magnitude that a 10% threshold assumed. The
threshold was set before final-3068 was measured, and is wrong. A drop-size
discriminator may still exist, but it is not cleanly separable at any value
tested, and on final-4585 even a correct refusal does not beat simply leaving
the repair off.

**Recommendation:** repair by default; the damping stack for storm-class
problems (many cameras, heavy reject streaks). The two mechanisms are
complements, not substitutes — thin-track scenes have points that were
*displaced* and want them *repaired*; storm scenes have points that were
*under-damped during the search* and want them *damped*. Do not stack them
blindly: on final-4585 the combination is worse than either.

## 6c. The full ledger — 51 problems, three families (2026-09-08)

Single pre-registered Config R throughout, N=3, both solvers on their own
**solve** clock with data loading excluded for each.

**BAL, 24 problems:** **11W / 6T / 6L (+1 DNF)**, worst loss **+1.13%**,
Σδ −69.0%. Wins: all three trafalgar (−0.17 to −0.50%), all four venice
(venice-52 −7.12%), dubrovnik-135 −3.25%, **dubrovnik-356 −38.20%**,
final-3068 −15.20%, ladybug-598 −0.07%. Losses: ladybug-49/810/1197/1469/1723
(+0.07 to +1.13%) and dubrovnik-173 (+1.04%). final-4585 DNFs under Config R —
the honest cost of a single configuration; Config C solves it, but reporting
that would be best-of-arms.

**muell, 22 production GBA snapshots** (24→493 cameras, 30K→314K obs): every
one a **quality tie** (median delta −0.0000%), **median 31× less wall**.

**fuchsberg, 5 dumps** (526→8,788 cameras, 1.08M→**16.75M obs**, the largest
problems here): ties within **+0.077%**, **median 12.1× less wall**, and the
ratio is flat from 3M obs upward (11.9 / 10.7 / 12.5 / 12.1×).

### The catch: wall ratio and descent rate disagree, and both are real

| | muell | fuchsberg |
|---|---|---|
| total wall (Caspar/Prism) | **31×** | **12.1×** |
| time to a 1% gap | 1.08× | **0.54×** |
| time to a 0.1% gap | **2.62×** | 1.01× |

**Caspar reaches coarse accuracy faster; we reach tight accuracy faster; and
our rate advantage erodes with scale** (decisive at 1.08M obs, marginal at
3.21M, absent at 14.3M). Its huge total walls are mostly spent *after* it
stops improving — on fuchs_126 it reaches a 0.1% gap in 1.2 s and then spends
~15 s crawling to 0.03%.

**RETRACTED: the iso-quality speedups reported before 2026-09-08.** Figures
like "7.1× on muell" and "10.1× on fuchs_126" divided Caspar's **total budget
wall** by our time-to-that-cost, which credits us for its final crawl instead
of measuring descent. Report the pair — total wall AND the descent-rate table
— never one alone. Also note total-wall ratios depend on the baseline's
budget: Caspar's 2000-iteration default is wasteful on warm problems, which
is most of muell's 31×.

## 7. Protocol — these rules were each learned by getting burned

1. **N ≥ 3 per verdict cell, N ≥ 5 for any tail/worst-case claim.** N=3 has
   twice produced claims that N=5 overturned. Judge a cell against **its own
   measured spread**, not a flat threshold: venice-52 has ~0.2% run-to-run
   spread, ladybug-1197's branch noise is 12.7% median / 81.5% p95, while
   venice-52-noisy and final-93 are ~0.00%.
2. **Verify the baseline's build configuration in the same session as the
   numbers.** Our benchmark compared fp64 Prism against an **fp32** baseline
   for months. Assert the baseline's reported initial cost against your own
   `0.5·Σ‖r‖²` of the input file at 1e-6 — an fp32 build cannot pass that.
3. **Verify a flag is live in the binary you are testing.** Unknown `OCA_*`
   env vars are **silently ignored**; a stale binary turns an A/B into
   champion-vs-champion and the basin lottery makes the noise look like a
   result. `strings ./build/oca_cuda | grep ^OCA_TAU_LAM_COND` or look for an
   activation line in the output.
4. **Pre-register ONE configuration** (or a selection *rule* applied
   everywhere with its overhead counted). Best-of-arms picked after seeing
   results is not a result.
5. **Never rebuild a binary an experiment is using.** Copy it
   (`cp build/oca_cuda /tmp/frozen`) and run the sweep from the copy.
6. **Report crossings in both directions**, not endpoint walls alone: your
   wall to reach the baseline's endpoint, and the baseline's wall to reach
   yours (or "never").
7. Serialise GPU work: wrap every run in `flock /tmp/prism_gpu.lock -c '...'`.
8. **A flag that never executes is still not inert if it allocates.**
   `OCA_RETRI_MAXDROP` was verified never to fire on ladybug-1469
   (`REFUSED=0`) and still moved the endpoint −0.084% against a 0.016% spread;
   two more scenes moved likewise. Cause: the extra `cudaMalloc` for its
   snapshot buffer shifts every later allocation, reordering atomic
   accumulations in the reduction kernels. Different rounding, amplified by
   basin sensitivity. So an A/B whose treatment allocates extra memory is
   **not** a clean comparison, and "the code path never ran" does not prove
   neutrality. Allocate unconditionally (both arms) when you need a real
   control, and judge such deltas against the scene's spread, never as exact
   equality.
9. **Record the outer count next to every endpoint, and distrust any gap
   between arms that stopped at different counts.** `OCA_FTOL_K=8` inflated a
   measured penalty 3x (+4.50% reported as +15.1%) by cutting one arm off at
   outer 27 while the other ran to 65. A stopping rule tuned offline interacts
   with whatever the intervention does to the trajectory, so it is never a
   neutral part of the harness.

## 8. Open problems worth your time

0. **THE ACCURACY FLOOR — the highest-value open problem.** Every remaining
   loss in the project is the same phenomenon: we descend fast, then settle
   just above the optimum on problems where the baseline converges cleanly.
   Four of five ladybug scenes lose by **+0.07% to +1.13%**, dubrovnik-173 by
   +1.04%, and fuchs_230 by +0.050% — all far outside their own spreads
   (0.001–0.06%). One mechanism causes every loss on the 51-problem ledger.
   Fixing it turns 11W/6L into something much stronger and converts the
   large-fuchsberg ties into wins. Related: the descent-rate crossover in §6c
   says the same thing from the other side — our advantage is *late* descent,
   so whatever stops us short is what caps the whole method.
1. **Why does the repair destroy final-4585** (+15.1% on top of Config C, and
   the plain solver + repair does not terminate at all) when it is a strict
   local improvement at the moment it fires? The pass cannot raise the
   objective — it is gated per point on that point's own reprojection cost —
   yet the endpoint worsens. This is the purest instance of the project's
   central law (local improvement and final quality are near-uncorrelated) and
   the cleanest available experiment on basin selection: the intervention is
   known, dated, and localised to specific points.
2. **Why does final-3068 prefer a *global* floor** while every other scene
   prefers the conditioning-gated one? It implies its flight-risk points are
   well-conditioned, which contradicts the mechanism everywhere else. We have
   forensics for why scenes fail *without* the floor and none for why one fails
   *with* it. This is the biggest hole.
3. **Damp only the weak direction.** The augmented-Givens factor accepts
   arbitrary rows, so appending one row `√μ_p·uᵀ` (u = the weak eigenvector, or
   for 2-view points the ray bisector, free from geometry) damps *only* the
   ill-conditioned direction and leaves the well-constrained ones untouched.
   Most principled version of the fix; μ_p has a closed form from a per-point
   trust radius.
4. **Cheirality / depth-bound guard on candidates** — a feasibility
   constraint, not a scoring change, that would catch a point fling at the
   moment it happens on any scene.
5. **Repair without the reset.** The repair works by *discarding* a point's
   accumulated position. A gentler version — blend toward the DLT estimate, or
   apply it only to points whose `R0f` block is ill-conditioned — might keep
   the six-scene win and lose the final-4585 catastrophe. Untested.

## 9. Things already refuted — do not spend GPU on these

fp64 on-the-fly Jacobians (4–7× slower than stored fragments); subsampled or
fp32 candidate scoring (3 designs; **any** perturbation of scoring inputs
derails the trajectory); fp32 stored fragments on basin-sensitive scenes;
τ warm-starting (3 variants); polynomial congruence preconditioning; per-shift
convergence pruning; geometric-mean streak rebase; learned decisiveness
gating; learned grid centering; one-step supervised λ selection (offline top-2
capture 0.72 → +846% deployed worst case); learned forcing sequences;
marginal-value-per-matvec stopping; per-attempt learned depth; cross-attempt
Krylov reuse; the doomed-attempt lever (skipping hopeless attempts just makes
the retry ladder add rungs); two-way menu re-arm.

Also refuted, 2026-09-07: **the menu-gate fallback**
(`OCA_MENU_GATE_FALLBACK`, score the remaining shifts when the gated seed
candidate fails instead of paying a full re-solve). The *mechanism* behind it
is real and verified: `OCA_MENU_GATE=1e-2` — which is in the recommended
config — collapses the menu to a single shift, and on dubrovnik-135's 64
rejected attempts the split is perfectly bimodal (every retry-0 attempt scored
1 shift at lambda~1e-6, every retry>=1 scored all 5), so **45% of rejects
happen with the menu switched off**. Restoring the missing candidates
nonetheless rescues none of them: 10-problem ledger **0W/9T/1L**, total
rejects **193 -> 196**. A promising single-run smoke test (56->49 rejects) did
not survive N=3 (54->60).

The conclusion that matters is the negative one: **gated rejects are genuine.**
At the lambda the solver is standing on, no candidate across four decades of
damping improves the cost — so the reject rate is a **lambda-policy problem,
not a menu problem**, and the multi-shift machinery is not being cheated.
(Related: the grid ceiling binds on only 34% of full-menu rejects, so widening
the grid is also a minority fix.)

Also refuted, 2026-09-07: **iterating the alpha line search**
(`OCA_ALPHA_ITER=k`, repeat the `{0.7,1,1.4}` pass while it keeps paying).
Motivated by a real measurement -- the winning alpha sits at or past the grid
boundary on 71-100% of the outers where alpha wins, so one pass is genuinely
under-ranged -- and refuted anyway: **0W/5T/1L**, and the single clean loss
(ladybug-598 +0.47%, deterministic over 3 reps, spread 0.01%) is on the scene
with the *largest* alpha improvement tail (3.08x). The boundary is
load-bearing: it acts as an implicit trust region. The flag stays in-tree
defaulting to 1 (exactly the old behaviour).

**The pattern across all of them:** changes to the *damping mechanism* survive;
changes to *candidate scheduling* do not. Every scheduling idea that looked
good offline was swamped by trajectory chaos in deployment. Weigh that prior
before building anything model-shaped.

**The deeper law, now with three independent confirmations.** Every mechanism
that strictly improves the per-outer objective either does nothing or hurts
the endpoint:

| mechanism | local guarantee | endpoint |
|---|---|---|
| re-triangulation repair | per-point cost-gated; cannot raise the objective | **+15.1%** on final-4585 |
| iterated alpha search | true-cost gated every round; cannot pick a worse step | **+0.47%** on ladybug-598 |
| one-step supervised lambda | offline top-2 capture 0.72 | catastrophic deployed tails |

The reason is structural: the accept gate is **already greedy-optimal**, so
additional greediness cannot improve the greedy objective -- it can only change
**basin selection**, which is uncorrelated with local descent. Before building
anything that makes a step locally better, ask what it does to basin choice,
because that is the only channel through which it can act.
