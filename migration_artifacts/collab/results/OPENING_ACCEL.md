# Attacking Caspar's opening advantage (2026-08-30)

Goal: shrink the window where Caspar's cost curve sits below MFREE's, **without
giving up end residual**.

## 1. Where the advantage actually is

Lead window = last moment Caspar's best-so-far is below MFREE's, per dataset
(v6 config, 23 sets):

- median **0.64 s**, median 14.5% of MFREE's run
- but **100% of the run** on the 3 sets Caspar wins (dubrovnik-135/-88,
  ladybug-49), and 20–64% on dubrovnik-173, insta360-3086, final-1936,
  venice-1672
- smallest on the big wins (final-4585: 1.5%, ladybug-1469: 2.1%)

## 2. Mechanism (measured, not assumed)

MFREE's **first step is better than Caspar's first step** — dubrovnik-135:
1.095e7 → 1.607e6 in one outer, versus Caspar 1.265e7 → 3.540e6. Caspar wins
the opening purely on **iteration throughput**: 0.02–0.05 s per iteration
against MFREE's 0.04–0.66 s per outer, so it completes 6–10 iterations while
MFREE completes one or two.

Per-outer wall tracks candidate-evaluation count almost linearly:

| dubrovnik-135 outer | cg_it | ckpts fired | ≈ cand evals | wall |
|---|---|---|---|---|
| 2 | 11 | 1 | 5 | 0.06 s |
| 3 | 61 | 3 | 15 | 0.15 s |
| 4 | 128 | 5 (+α) | 33 | 0.26 s |
| 5 | 0 | 0 (+α) | 13 | 0.04 s |

Phase split (venice-1672, per outer): assembly 165 ms, point factor + rhs
70 ms, Krylov 232 ms, candidates 111 ms. So the expensive early outers are
**Krylov- and candidate-dominated**, and the fixed (non-Krylov) part is ~60%
of an outer.

## 3. What was tried

| change | lead window | end residual | verdict |
|---|---|---|---|
| fp32 fragments | −9% (5.57→5.08 s on final-4585) | +1.9% on f-4585 | **no** — wrong lever, and hurts small sets (venice-52 lead 0.84→1.03 s) |
| α grid 8→4 combos (`OCA_ALPHA_CROSS`) | **worse**: insta360 10.73→19.11 s | +0.2…0.4% | **no** — cheaper α buys worse steps, which costs more outers than it saves |
| candidate pruning (`OCA_CAND_PRUNE`) | −1…−14% on 4 sets | neutral to −0.35% | promising |
| + cold-phase CG depth cap 32 (`OCA_CKPT_OPEN`) | −14…−31% (venice-1672 crossing 12.44→9.32 s) | ≤0.01% on 4 sets | promising |
| both, full 23-set sweep | total lead **−16%**, 20/23 improved | median 0.000%, **but f-3068 +14.9%, f-4585 +2.0%** | **blocked** |
| + guard (disarm on any reject, cold = rel>0.1) | −2% only | f-3068 still +11%, new +6.8% on ladybug-1197 | **no** — kills the benefit, keeps the risk |

**Pruning rule** (justified from the archive before building it): at an
intermediate checkpoint score only shift 0 and the previous outer's winner;
guarantee one full shift menu at the depth CG actually stops at. Across 1340
accepted outers, 82.5% of winners are shift 0, 87.5% sit at the deepest fired
checkpoint, and only **2.1%** are at an intermediate checkpoint with a shift
that is neither 0 nor the previous winner.

## 3b. What repeated runs say (the single-run table above is not trustworthy)

Every row in §3 is a single run per config. Re-running with N=3–4 per config
changes the conclusions, so the table above should be read as hypothesis
generation only:

| dataset | config | n | lead window (median [min–max]) | final (median [min–max]) |
|---|---|---|---|---|
| dubrovnik-135 | base | 4 | 4.20 s [4.06–4.54] | 9.571814e5 [9.56915–9.57228e5] |
| | accel, guarded | 4 | 3.93 s [3.80–4.20] | 9.573071e5 [9.57162–9.57558e5] |
| | **accel, unguarded** | 3 | **3.38 s [3.30–3.44]** | **9.579108e5 [9.57877–9.58196e5]** |
| venice-1672 | base | 4 | 7.86 s [7.86–7.86] | 4.482177e6 [4.46907–4.48742e6] |
| | accel, guarded | 4 | 8.15 s [8.15–8.15] | 4.476897e6 [4.47498–4.48128e6] |
| | **accel, unguarded** | 3 | **5.39 s [5.39–5.39]** | **4.502146e6 [4.50214–4.50215e6]** |
| insta360-3086 | base | 4 | 10.87 s [10.38–12.12] | 2.166082e6 |
| | accel, guarded | 4 | 11.49 s [11.29–11.61] | 2.166127e6 |

Conclusions that survive repetition:

1. **The unguarded accelerators really do shrink the opening**: −20%
   (dubrovnik-135) and −31% (venice-1672), reproducibly, with near-zero
   run-to-run spread in the lead window itself.
2. **They are not free.** The final-cost distributions do **not overlap** with
   the baseline on either set: +0.076% on dubrovnik-135 (base max 9.57228e5 <
   accel min 9.57877e5) and +0.44% on venice-1672 (base max 4.48742e6 <
   accel min 4.50214e6). The 23-set single-run sweep reported a median
   endpoint change of 0.000%, which was sampling noise, not neutrality.
3. **The guarded variant preserves quality but delivers nothing** (−6% and
   +4% on the two sets). Guarding removes the mechanism along with the risk.

So the honest trade is: **roughly a quarter of the opening window for roughly
a tenth to half a percent of end residual.** That does not meet a strict
"keep the end residual" bar, which is why the flags stay default-off.

## 4. On the endpoint spread — correcting an earlier overstatement

I first read the final-3068 spread (1.71e6 / 2.15e6 / 2.15e6) as an
early-stopping bug. Six-run distributions say otherwise:

| protocol | outers | finals |
|---|---|---|
| default stopping | 56, 8, 14, 60, 60, 23 | 5× ~2.149e6, 1× 1.708e6 |
| stopping disabled | all 60 | 5× ~2.150e6, 1× 1.888e6 |
| default + `OCA_STOP_WINDOW=10` | 28, 19, 54, 60, 37, 15 | 5× ~2.150e6, 1× 1.764e6 |

The iteration count varies wildly, but the **endpoint does not follow it**:
the run that stopped at 8 outers reached 2.1507e6 versus 2.1491e6 for a
60-outer run — 0.07%. The stopping rule is doing its job; stopping early on
this scene costs essentially nothing.

The real variance is **basin selection**: ~1 run in 6 finds a materially
better basin (1.71–1.89e6 versus 2.15e6, ~18–21% better), decided by
atomics-level differences in the opening. `OCA_STOP_WINDOW` (a windowed
version of both stopping rules) is implemented and default-off, but shows **no
measurable quality benefit** and is not recommended.

Practical consequence: **final-3068 cannot be used for single-run endpoint
A/B at all**, and the v6 reference value used throughout §3 (1.7119e6) was a
draw from that good tail — which is what produced the phantom "+14.9%
regression".

## 4b. Original (now superseded) framing of the measurement problem

Three **identical** runs of the same binary and config on final-3068:

```
1.711612e+06 (60 iterations)
2.150488e+06 (14 iterations)
2.150341e+06 (13 iterations)
```

A **26% endpoint spread from run-to-run noise alone.** Mechanism: GPU atomics
make the trajectory diverge in the 7th digit (dubrovnik-135 diverges from
itself at iteration 4), and on reject-prone scenes that flips whether
`max_consecutive_failures` (default 3) fires — so the solve stops at iteration
13 or runs to 60.

Consequences:
1. The "+14.9% regression on final-3068" that blocked the accelerators is
   **within this noise** and cannot be attributed to the change from
   single-run data. Neither can it be dismissed. The experiment is
   underpowered, not the change disproven.
2. The reproducibility ladder is: ladybug-49 bit-identical across runs (a
   valid bit-gate); dubrovnik-135 ±0.04%; final-3068 ±26%.
3. ~~This is also a production bug.~~ **Superseded by §4**: the endpoint does
   not track the iteration count, so the stopping rule is not the cause. The
   spread is basin selection.

## 5. What shipped: setup cost (provably trajectory-neutral)

The crossing methodology normalises to each solver's first logged iteration
and so hides setup. Measured from the wrapper's "BA options" line to the first
outer: **MFREE 0.48–0.74 s vs Caspar 0.06–0.08 s.**

Breakdown (`OCA_PROFILE` now also reports setup phases):

| phase | dubrovnik-135 | insta360-3086 | final-4585 |
|---|---|---|---|
| upload + index build | 180.3 ms | 289.9 ms | **1055.6 ms** |
| initial diagnostics | 9.3 ms | 26.4 ms | 202.5 ms |
| initial cost | 0.9 ms | 2.5 ms | 14.4 ms |

Index building dominated, and it was two `std::stable_sort` comparison sorts
over all observations with random-access comparators — but both key on an
integer dense in `[0, npt)` / `[0, ncam)`, where a **stable counting sort** is
O(n) and produces *identical* output (placing observations in increasing
original index within each bucket is exactly stability). Every downstream
index, atomicAdd order and trajectory bit is therefore unchanged.

| | before | after |
|---|---|---|
| dubrovnik-135 | 180.3 ms | 152.2 ms (−16%) |
| insta360-3086 | 289.9 ms | 184.7 ms (−36%) |
| final-4585 | 1055.6 ms | **511.0 ms (−52%)** |

Gate: ladybug-49 champion config **bit-identical** to the archived trace after
the change. (Larger sets cannot be bit-gated — see §4 — but the counting sort
is identical by construction, and would have broken ladybug-49 if it were not.)

That is 0.54 s of pure latency removed from every final-4585 solve, before any
optimisation step runs, at zero quality risk.

## 5b. Integration + muell replay (22 dumps, 3 repetitions each)

`fast_opening` is now a first-class option rather than two experiment env
flags: `MFreeBundleAdjustmentOptions::fast_opening` /
`fast_opening_depth`, CLI `--BundleAdjustmentMFree.fast_opening`, env
`COLMAP_MFREE_FAST_OPENING`, and `oca::Options::fast_opening` in the core API.
Default **off**. The `OCA_OPEN_REL` gate now defaults to 0 (no
relative-progress restriction) because that is the configuration that
delivers; the reject guard alone protects the sensitive scenes. Gates: the
champion config stays bit-identical with the option off, and the option
reproduces the equivalent env flags.

Tested on the muell GBA dumps -- the **warm, in-mapper regime**, where the
brief notes that GBAs persist λ and skip the opening entirely. Three runs per
dump per mode, per-dump medians:

- **wall: median +2.0%**, faster on 9/22, slower on 13/22, against a baseline
  whose own run-to-run wall spread is a median 4.9%
- **quality: median −0.0004%**, worst +0.0042%, best **−0.121%** (gba_146)
- per-dump effects are real but bidirectional: gba_141 −29.5%, gba_121 +49.6%

So on warm solves `fast_opening` is a **wash on time and neutral on quality**.
That is the expected result, not a disappointment: there is no opening left to
accelerate once λ is warm-started, so capping CG depth just trades candidate
evaluations for extra outers.

**Where it applies:** cold solves (BAL-style, or the first GBA of a session),
where it buys 20-31% of the lead window for +0.08…+0.44% final cost. It should
stay off for in-mapper replays.

## 6. Recommendation

1. **Take the counting sort** — the only change here that provably cannot move
   the endpoint, and worth 0.54 s of pure latency on every final-4585 solve.
2. **`fast_opening` is integrated as an opt-in mode, default off.** It works
   (−20…−31% of the opening on cold solves, reproducibly) but costs
   +0.08…+0.44% end residual, reproducibly, and is a wash on warm in-mapper
   solves (muell: median +2.0% wall, quality neutral). Enable it per-call for
   cold, latency-sensitive solves; leave it off elsewhere.
3. **Do not ship `OCA_STOP_WINDOW`** — no measurable benefit.
4. **Adopt repeated-run protocol for this suite.** Single-run lead-window and
   endpoint comparisons are unreliable: dubrovnik-135 ±0.03%, insta360 lead
   ±8%, final-3068 bimodal at ±18%. Anything below ~0.5% on one run is not a
   result. This invalidates parts of the earlier single-run sweeps in this
   project, not only mine.

Flags added (all default-off, gates pass with them off):
`OCA_CAND_PRUNE`, `OCA_CKPT_OPEN=<depth>`, `OCA_OPEN_REL=<rel>`,
`OCA_ALPHA_CROSS` (measured harmful — kept only to reproduce the negative).
