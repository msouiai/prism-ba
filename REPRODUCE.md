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

## 8. Open problems worth your time

1. **Why does final-3068 prefer a *global* floor** while every other scene
   prefers the conditioning-gated one? It implies its flight-risk points are
   well-conditioned, which contradicts the mechanism everywhere else. We have
   forensics for why scenes fail *without* the floor and none for why one fails
   *with* it. This is the biggest hole.
2. **Re-triangulation repair (untested).** On a ladybug endpoint, reset the
   ~200 gap-carrying points by closed-form midpoint/DLT from the current
   cameras and run the finisher. If the endpoint recovers, a periodic
   "re-triangulate degenerate points" pass is a regime-free fix needing no
   signal, no threshold and no per-scene decision.
3. **Damp only the weak direction.** The augmented-Givens factor accepts
   arbitrary rows, so appending one row `√μ_p·uᵀ` (u = the weak eigenvector, or
   for 2-view points the ray bisector, free from geometry) damps *only* the
   ill-conditioned direction and leaves the well-constrained ones untouched.
   Most principled version of the fix; μ_p has a closed form from a per-point
   trust radius.
4. **Cheirality / depth-bound guard on candidates** — a feasibility
   constraint, not a scoring change, that would catch a point fling at the
   moment it happens on any scene.

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

**The pattern across all of them:** changes to the *damping mechanism* survive;
changes to *candidate scheduling* do not. Every scheduling idea that looked
good offline was swamped by trajectory chaos in deployment. Weigh that prior
before building anything model-shaped.
