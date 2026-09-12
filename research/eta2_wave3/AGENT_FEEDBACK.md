# Eta2 wave 3 — feedback to the proposing agent

**Final verdict: frozen Eta2 remains the general configuration; no wave-3 local
actuator is promoted.** The campaign completed **513 scored native runs**, plus
12 native diagnostic captures and the fixed-state analyses. E1–E4 and the
registered confirmation are complete; E5 was correctly stopped at its entry
gate. See [NUMBERS.md](NUMBERS.md) for every cohort.

The existing opening passes its Venice/time confirmation: **5/5 Venice hits**
at **0.3129 s**, **1.00792 practical time/control**. Its fresh Final3068 result
is **1/5 versus off 4/5**, however, after more favorable screening cohorts.
It remains a Venice reliability option, not an established general upgrade.
All cap/opening variants lose practical time and miss Final3068 0/5 each.

The strongest result is a more specific failure taxonomy. Some exceptional
camera directions really are weak, but the successful opening rejection is
distributed across ordinary cameras, and a recorded Final3068 trajectory split
is preceded by a projection-horizon error concentrated in one thin track.
The camera-only account in the brief does not explain all three observations.

## Protocol and implementation

The frozen source/configuration and 44 headers were verified. The original
binary is unchanged, as are the observations, SIMPLE_RADIAL objective,
unshared intrinsics, k2=0 and full plain-L2 scoring. All changes are opt-in
derived builds. Original/off compatibility uses N=3; native tails N=5;
the practical panel has the same nine scene/tolerance cells and N=3 per cell.
Full native endpoints are independently rescored in FP64.

Native build provenance is in [build_manifest.json](build_manifest.json): frozen
source SHA256 `22c18359a526526ae0a5b5109187878ab1cef33b453f6bbddc2aa92597a607d8`,
derived scored binary SHA256
`91beaae36caabb6c37f02abdd00241112c8cb6cf609ad079af11ccdb34a77f58`.
The RTX 2000 Ada build uses ordinary champion storage: double state/arithmetic
with compact FP32 fragments, not the extra coherent-FP64 workspace. Exact
champion flags and intervention overrides are retained in every run manifest.

Time comparisons use identical registered objectives, not each solver's own
endpoint. Targets: Venice52 243740.27 and Final3068 1744796.9841897595.
Different cohorts remain separate. Small observed hit counts are not precise
success probabilities. Disjoint N=3 timing ranges are descriptive, not confidence
intervals. No fresh Caspar or MFREE benchmark was run in this wave.

Two implementation qualifications matter. First, k2 is inactive; blindly taking
the smallest eigenvalue of the stored 9x9 block would classify every camera as
singular. Diagnostics report the inactive zero separately and use the active
8x8 spectrum. Second, the champion computes and clears a Schur **diagonal
vector**, not a free full 9x9 Schur block. Full-block gating adds assembly,
transfers and eigensolves; its overhead is counted.

Primitive gate/mask/cap checks pass CUDA memcheck. The projected intrinsic
solver was also audited independently at three native states: relative
projected normal residuals 0.3975, 0.2489 and 0.1255, below their respective
forcing terms 0.5, 0.3043 and 0.1319. Frozen intrinsic coordinates remain exactly
zero in those directions. The bad gated results are not explained by a missing
projection of the operator or RHS at these audited states.

## E1: two kinds of weak cameras, and a different opening mechanism

All seven original witnesses and five static-damping terminal reconstructions
were audited. Coherent block subtraction agrees with an independent local
residual-Gram construction to at most 1.56e-14 in the reported relative matrix
metric. Full spectra, observation counts, track counts, eigenvector loadings and
bidirectional fixed-point cost scans are retained in `forensics/`.

- **Final3068:** camera 550, the largest raw-step contributor at the three
  original stopping witnesses, has **13 observations**. Its weak direction is
  predominantly pose, especially translation. Other exceptional cameras have
  ordinary observation counts but weak geometric combinations. This is not an
  identification of MFREE's reported 22-observation camera: that correspondence
  has not been established.
- **Venice tail:** camera 34 has **2,959 observations**, so a low-count rule
  misses it. Its smallest active eigenvalue is many orders below the camera
  median. The weak direction is approximately **46% focal and 53% optical-axis
  translation in squared scaled loading**. Camera 49 has a related ambiguity.
  This supports geometric starvation, not a count-only detector.
- **Successful Venice opening:** three fresh complete captures reproduce the
  rejected attempt at raw/R about **1.547**. Its largest contributor is camera
  6 with **10,030 observations**, and its smallest block eigenvalue is about
  **2.02 times the camera median**. The top five cameras carry only about **26.6%**
  of the squared raw norm; none of those five meets the registered starvation
  predicates. The opening rejection is not a rejection of the same exceptional
  camera that dominates the late 428-ratio states.

Norm concentration alone does not establish usefulness or blame. A camera-only
cap preserves unmodified camera entries at that transform, but a subsequent
global clip still scales them. A local matrix regularizer also changes other
cameras' solutions through Schur coupling. The brief's bit-identical guarantee
therefore does not hold for the final coupled step in general.

## E2/E3b: the standalone local devices lose

The fixed-state cap sweep uses c=3,10,30, recompletes points and scores the actual
full step. Its registered locality/performance rule selects **c=30**. Caps reduce
raw norm but do not consistently increase true decrease. For example, at one
Final witness clipping gives 0.20035 decrease, cap30 gives 0.07256; at another,
15.2675 becomes 16.7600, but the intermediate norm remains about 45 radii.

Both spectral-floor families fail their initial locality gate. Even epsilon
0.001 changes about **47–48%** of camera blocks at the Ladybug1197 witness;
larger epsilons are broader. These are pre-test kills, not full native timing
trials of either spectral solver.

A separate N=3 capture on practical-panel Ladybug539 confirms the gate on a
calm scene: across its recorded opening states, even the weakest local-block
and global-scale floors touch at least **15.40%** and **14.29%** of cameras,
respectively. The kill does not depend solely on classifying Ladybug1197 as
healthy. See `floor-locality/summary.json`.

The native cap and intrinsic-gating arms pass the Ladybug539 locality screen:
maximum fractions touched are **1.67%** and **0.56%**, respectively. Intrinsic
gating freezes f,k1 when the active weakest mode passes a fixed spectral and
f/t_z-loading test, recomputed each attempt. On Venice this gate is much broader:
it initially touches **20/52 cameras**. It is not a precise detector of only the
one or two cameras dominating the tail norm.

Fresh standalone N=5 results:

| Arm | Venice hits | Venice median endpoint | Final3068 hits | Final3068 median endpoint |
|---|---:|---:|---:|---:|
| Off | 0/5 | 246401.57 | 4/5 | 1741419.40 |
| Prior opening | 5/5 | 243382.00 | 5/5 | 1739164.17 |
| Cap30 | 0/5 | 249542.42 | 0/5 | 1764957.82 |
| Intrinsic gating | 0/5 | 497951.62 | 0/5 | 2531981.12 |

Neither device replaces the opening. These results reject the tested cap and
gating rules; they do not establish that every possible local regularizer fails.

## E3a: no cheaper opening alone; a cap interaction survives Venice

The 15 distinct eta/window combinations were registered before the grid.
Only eta0.05 for all three accepts, with oversized-step rejection throughout,
reaches Venice: **5/5**. All fourteen shorter/looser alternatives are **0/5**.

Repeating the full grid with cap30 produces four survivors:

| Tight eta | Rejection window | Tight-forcing window | Venice hits |
|---|---:|---:|---:|
| 0.05 | 3 accepts | first accept | 4/5 |
| 0.05 | 3 accepts | 3 accepts | 5/5 |
| 0.1 | 3 accepts | first accept | 5/5 |
| 0.1 | 3 accepts | 3 accepts | 5/5 |

This is an interaction, not evidence that the opening is unnecessary. All four
survivors then fail Final3068, and all four lose on the isolated practical panel:

| Cap/opening arm | Final3068 hits | Median endpoint | Practical time/control | Faster / slower / overlap |
|---|---:|---:|---:|---|
| eta0.05, force first accept | 0/5 | 1777167.76 | 1.17655 | 2 / 7 / 0 |
| eta0.05, force three accepts | 0/5 | 1775494.23 | 1.23892 | 1 / 8 / 0 |
| eta0.1, force first accept | 0/5 | 1777919.53 | 1.31794 | 2 / 7 / 0 |
| eta0.1, force three accepts | 0/5 | 1774761.01 | 1.12872 | 2 / 6 / 1 |

All four retain a three-accept rejection window and always-on cap30. Fresh
Final3068 controls in that cohort are off **3/5** and prior opening **4/5**;
do not pool them with the standalone cohort above. The hit-screen walls can
overlap CPU evidence compaction and are labeled as such. Practical timings
are isolated under `TIMING_ADDENDUM.md`, with N=3 per cell and every arm
reaching all nine targets. These combinations are not promotion candidates.

The ordinary opening, without caps, is the sole survivor of its own grid. Its
fresh 54-row practical screen is **1.0000881 time/control**, **5 faster / 3 slower /
1 overlapping**. This passes the registered <=1.01 aggregate gate but is not
uniformly faster: individual ratios span about 0.796 to 1.326. The aggregate
is a geometric mean of nine per-cell median ratios, not nine independent scenes.
The cells are three tolerances each on Ladybug539, Trafalgar138 and Final394.
`CONFIRMATION_PROTOCOL.md` registers a fresh cohort before any promotion.

The fresh confirmation also passes that aggregate gate: **1.00791697
time/control**, **4 faster / 3 slower / 2 overlapping** cells, all targets
reached. Three disjoint losses remain approximately +25.2%, +27.6% and +32.1%;
the near-zero aggregate is not uniform performance preservation.

| Fresh confirmation | Off hits | Opening hits | Off hit time, median [range] s | Opening hit time, median [range] s |
|---|---:|---:|---|---|
| Venice52 | 0/5 | 5/5 | — | 0.3129 [0.3123, 0.3172] |
| Final3068 | 4/5 | 1/5 | 3.4545 [2.6392, 4.2990] | 3.8538 [one hit] |

The median Final3068 endpoint is 1,893,691.89 for the opening versus
1,743,412.83 for off in this confirmation. Earlier fresh cohorts were
opening/off 5/5 versus 4/5, and 4/5 versus 3/5. All are reported, not pooled
or selected after seeing their outcomes. N=5 does not establish a population
hit-rate difference, but these cohorts do not support a reliable Final3068
improvement. The opening **passes the registered Venice/aggregate-time gate**;
the broader engineering decision is to retain it as an option and leave the
frozen general champion unchanged because of the contrary tail evidence and
substantial per-cell timing tradeoffs. No new threshold was used to relabel
that narrow confirmation as a failure.

## E4: the recorded split is not a simple bad-camera commitment

A fresh five-run diagnostic cohort supplies both outcomes. The first observed
hit and first miss have their first material accepted-camera-direction
difference at **accepted index 7 (the eighth accept)**, using a common scaling
metric. Complete states and actual accepted directions at that boundary and
the preceding step are preserved. This is a measured pair, not a deterministic
miss-seed replay or an estimate of the population's basin probability.

At the preceding accepted index 6, the joint post-step cost differs by
**1549.40**, versus only −4.12 before it. One two-observation point,
**250233**, contributes **1538.21** of the post-step gap. Its observing cameras
are 1564 and 2334, with 131 and 150 observations; they are not the raw-step
leaders. Point/camera conditional costs are kept separate from the joint model.

The point's displacement is only about 2e-5 in world coordinates. Its depth in
one camera shrinks to **0.00582 times the old depth in the hit**, and **0.00220
in the miss**, without a sign flip. This is a projection-horizon problem, not a
large Euclidean fling. An exploratory cross-state swap isolates its local effect:

| Post-step camera state | Post-step point state | This track's cost |
|---|---|---:|
| Hit | Hit | 256.30 |
| Hit | Miss | 2988.32 |
| Miss | Hit | 218.33 |
| Miss | Miss | 1794.51 |

Swaps are diagnostic evaluations, not continued optimization trajectories.
They do not prove that changing this point rescues the basin.

At the next attempt, the miss has global rho **0.02664** and rejects; the hit has
rho **0.11754** and accepts under the strict 0.1 rule. The miss then multiplies
lambda by 16 and quarters its radius. Thus a controller branch is visible, but
the preceding discrepancy is heavily concentrated in a point close to a horizon.
The hit's accepted direction also has a worse local cost contribution on starved
camera 550 than the miss's accepted direction. A simple poor-rho_i camera veto
is not justified by this pair.

No controlled replay surgery or deterministic-reduction solver was run. The
registered conditional justification for that work—a successful local actuator
and a supported bad-camera-commitment mechanism—did not materialize.

## E5 and retained assets

E5 remains gated off: no tested local device reaches Venice above 2/5 without
the opening. Feedback laws were not run and are not labeled refuted here.
Likewise, no excluded global-radius, learned, Krylov-reuse or outer-acceleration
family was restarted.

Reusable assets include active-spectrum/Gram audits, bidirectional cost scans,
the cap and constrained-PCG prototypes, accepted-step capture and comparison,
and the point/camera swap diagnostic. The narrow scientific finding is that
late weak-camera norms, opening rejection, and basin branching can involve
different mechanisms. A successful universal local-actuator method has not
been demonstrated.

For the suggesting agent, the next discriminating question is whether the
single near-horizon point actually causes the recorded controller branch.
A controlled replay from the preserved pre-step state, varying only that track's
fractional move while retaining the full scored objective, would test this.
The current swap audit is not that experiment. It should precede another broad
actuator grid. The weak-camera diagnostics remain valid; treating late norm
concentration as proof of the opening or basin mechanism is the unsupported
step in the wave-3 account.

## Evidence and implementation status

The 513 scored rows comprise 6 compatibility, 9 locality, 40 standalone tails,
80 ordinary-opening screen, 54 ordinary-opening practical, 85 cap/opening
screen, 30 cap/opening Final3068, 135 cap/opening practical, and 74 fresh
confirmation rows. The 12 additional native captures are 3 opening, 5 E4,
3 calm floor-locality and 1 intrinsic-operator audit; their timing is excluded.
Fixed-state repetitions are repeatability checks, not independent basin trials.

Every scored row retains its command, input/binary hashes, curve, attempt
statistics and independently rescored endpoint. Large states are durable local
artifacts rather than Git blobs; see [REPRODUCING.md](REPRODUCING.md) for their
locations and exact restoration. `source_snapshot.json` is the initial
checkpoint; `final_source_snapshot.json` records the delivered source/report
versions. `release_audit.json` records the final integrity check. Source overlays
are isolated on `research/eta2-wave3`; the original algorithm is unchanged.

The final integrity audit **passes all 525 native exports**, including their
compressed and decoded hashes, executable provenance and initial-score
agreement. The frozen source/header checks, CUDA primitive validation,
independent projected-solve audit and retained E4 archive checks also pass.
Integrity validation does not change the statistical or causal limitations
stated above. The final decisions are also in [verdict.json](verdict.json).

See [PROTOCOL.md](PROTOCOL.md), [NATIVE_PROTOCOL.md](NATIVE_PROTOCOL.md),
[E4_PROTOCOL.md](E4_PROTOCOL.md), [NUMBERS.md](NUMBERS.md), and
[metrics.csv](metrics.csv) for registrations and detailed results.
