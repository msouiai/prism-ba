# Eta2 wave 4 — feedback on the orthogonal-reformulation briefs

2026-09-12. Branch `research/eta2-wave4`, based on wave-3 commit `3754978`.
**Frozen Eta2 remains the champion. No wave-4 arm is promoted.**

The campaign completed **255 scored native runs**, in addition to compatibility,
memory/derivative/KKT checks and witness replays. [TABLES.md](TABLES.md) contains
all registered tail rows, including failures and conditional timing ranges.
[RESULTS.json](RESULTS.json) adds outers, rejects, retry fractions, PCG depth,
initial scores and endpoint ranges. Cohorts are kept separate throughout.

The useful survivor is a **screening signal for the Cauchy-to-L2 opening on
Final3068**, not a replacement solver. Object-space O1 has a more limited
verdict: a completed negative experiment on Venice, but an unresolved numerical
solve on Final3068. Do not report those two scopes as the same negative result.

## Protocol and baseline

- Original observations, SIMPLE_RADIAL, unshared intrinsics, k2=0. Every scored
  cost and target uses the original plain-L2 objective, independently rescored
  in FP64. No observations were dropped from scoring.
- Targets: **Final3068 = 1744796.9841897595**, **Venice52 = 243740.27**.
  Each tail arm has N=5; native budget 60 s and Eta2 outer cap 600.
- Nine practical cells: Ladybug539, Trafalgar138 and Final394, at the three
  previously registered tolerances, N=3. Native solve time includes setup,
  opening, staging, transfers and cleanup. Legacy CSV time is not the charged
  time-to-target metric.
- N=5 hit counts are screening observations. A one-hit difference does not
  establish a reliability improvement. Conditional successful-run times must
  be read with their ranges and hit counts, never in isolation.
- Original/off compatibility was checked for each derived binary. During
  scored timings the GPU was serialized and CPU compaction was stopped.
  Compatibility and numerical diagnostics have no performance claim.
- Frozen source SHA256:
  `22c18359a526526ae0a5b5109187878ab1cef33b453f6bbddc2aa92597a607d8`.
  Frozen original binary SHA256:
  `1e3d2cf22a8a43075114e0ca2024923dad330461e35d0074938d0412cd77ecc0`.
  The champion build's source plus 44 headers were verified in session.

All interventions are separate overlays. The original solver, configuration
and source manifest are unchanged. Ordinary champion storage retains its
compact FP32 fragments with FP64 state/arithmetic/scoring; it must not be
described as the coherent all-FP64 operator.

## 1. Acceptance aside: no demonstrated fix for the lottery

Fresh Final3068 observations:

| Arm | Hits | Conditional median native seconds | Range |
|---|---:|---:|---:|
| Same-binary off | 3/5 | 3.406 | 2.349–3.616 |
| rho_min = 0.001 | 4/5 | 3.472 | 2.451–4.893 |
| rho_min = 0.01 | 4/5 | 4.666 | 3.568–5.170 |
| Nonmonotone window 5 | 2/5 | 2.058 | 1.900–2.216 |

Venice was **0/5 in every arm**. The two monotone threshold variants earned
the practical panel, but all nine timing ranges overlapped the control for
both variants. Geometric-mean time ratios were **0.9923** and **1.0026**.

The nonmonotone prototype tracks the current-cost rho for radius/lambda
updates, permits acceptance against a five-state maximum, and exports the
lowest full-L2 state actually visited. Its memory and best-state behavior were
checked; it is not advertised as Ceres' full implementation or a realization
of Toint's complete convergence theorem.

**Verdict:** lowering the threshold did not eliminate misses, and the observed
3/5→4/5 count is insufficient to promote it. This does not establish that a
single rho threshold explains the E4 basin split.

Evidence: `aside-*-results.json`, `aside-validation.json`,
`aside-practical-summary.json`, `build_aside.py`.

## 2. O3 rational attribution: detects the E4 observation, fails the registered locality gate

At accept 6, the detector flags point **250233** in both recorded trajectories:
rank **4** in the hit and **2** in the miss. The problematic observation is
1512088, camera 1564. At that observation:

| Proposal | True retracted observation cost | Rational-geometry prediction | Quadratic prediction | New/old depth |
|---|---:|---:|---:|---:|
| E4 hit | 256.282 | 309.304 | 0.002932 | 0.005819 |
| E4 miss | 1794.488 | 2175.504 | 0.002931 | 0.002199 |

So rational attribution sees the failure that a local quadratic misses. It
does **not** isolate only that point: the hit direction flags 80 observations.
The full rational predicted cost differs from true retraction by approximately
−10,416 / −10,081 in the two directions. Rotation and joint-step remainder
terms remain material; this is not an exact candidate-cost evaluator.

The registered healthy screen used three independent Ladybug539 captures and
their actual accepted directions. Flag fractions across the first three accepts
were **0, 0.00105672, 0.00203770** in each capture. The latter two exceed the
**0.001** limit. This is a failure of the detector's specified sparsity gate;
it is not proof that every flagged healthy observation is a false positive.

At **all three Final3068 stop witnesses**, there were **zero detector flags and
zero denominator-bound violations**. The E4 horizon event therefore does not
explain this entire terminal-witness class.

**Verdict:** stop the proposed always-on O3 path at its registered detector
gate. An exact constrained native O3 QP was **not built or benchmarked**, and
the general polyhedral idea is not refuted. Sparse depth-bound violations and
sparse rational-model disagreement are different measurements.

Evidence: `attribution.py`, `attribution/*.json`, `attribution-gates.json`.

## 3. O4 frozen-ray reduction: the requested restricted GN replay does not remove the branch

The sensitivity trigger passed its healthy locality gate: maximum triggered
fraction **3.60655e-5**, below **1e-4**. The E4 replay then used the old camera
1564 as a frozen ray anchor, restricted point 250233 to that ray, and solved
the scalar damped GN point subproblem with the recorded camera proposal.
The scalar normal-equation residual was zero to the recorded precision.

| Quantity | Hit proposal | Miss proposal |
|---|---:|---:|
| Original point cost | 256.303 | 1794.509 |
| Restricted GN point cost | 1110.220 | 886731.005 |
| Full proposal rho after substitution | 0.484 | −14.867 |
| Anchor residual at **updated** camera | 47.12 px | 1331.71 px |

The point-cost gap grew from **1538.206** to **885620.785**, approximately
**575.75×**. A point on the old anchor's ray is not on the new camera's ray.
Reporting its old-camera residual as zero would have hidden this failure.

A separate bounded nonlinear scalar search found much better positions along
the same ray (costs approximately **2.410 / 2.495**). That is a useful diagnostic:
the ray itself has better positions, but this restricted GN back-substitution
does not find them. The finite search is neither a certified global optimum
nor a tested native policy.

**Verdict:** the registered restricted-replay gate failed; no native O4 arm.
Scope matters: cameras were held to their recorded proposal. We did not
recompute a fully coupled camera solve under a hard, moving-anchor constraint,
so this does not refute that different exact constrained formulation.

Evidence: `O4_REPLAY_PROTOCOL.md`, `ray_replay.py`, `o4-ray-replay.json`.

## 4. O5 Cauchy-to-L2: modest tail signal, substantial ordinary-target overhead

The one registered schedule used four Cauchy stages, two accepted outers each,
scale-squared multipliers **1, 4, 16, 64**, then original L2. The initial scale
was four times the median initial squared pixel residual. Each stage had an
18-attempt limit with direct L2 handover on cap/stall. Controller values persist;
objective-dependent histories and caches reset. No learned policy was used.
All ten scored opening runs completed the full schedule and entered L2.

| Scene | Off hits | O5 hits | Off conditional median | O5 conditional median |
|---|---:|---:|---:|---:|
| Final3068 | 4/5 | 5/5 | 4.590 s | 2.602 s |
| Venice52 | 0/5 | 0/5 | — | — |

Final3068 successful ranges overlap substantially: **2.948–6.591 s** versus
**1.574–6.973 s**. Median rejects fell **7→1** there, but this small cohort does
not establish that reliability improved. Venice's median endpoint improved
only about **0.162%**, still above its target.

The gated nine-cell panel found **3 faster / 6 slower / 0 overlapping ranges**,
with **1.14545× geometric-mean time to target**. The favorable cases were
Final394 at 1.005× and Trafalgar138 at 1.005× / 1.01×. The last of those was
only about 0.39% faster, despite disjoint N=3 ranges. The remaining six cells
lost approximately 16–35% by median.

**Verdict:** retain as a tail-reliability research candidate; do not promote
as a run-everywhere champion. A useful next test would be a newly registered,
larger Final3068 cohort against the frozen baseline and portfolio, with full
clocks. Do not select scenes/flags retrospectively from this panel.

Correctness includes 192 actual GPU model/track checks, maximum finite-
difference discrepancy **4.49e-8**, zero memcheck errors, and tests proving
that an intermediate robust state cannot count as an L2-stage target hit.

Evidence: `O5_PROTOCOL.md`, `run_o5.py`, `o5-*-results.json`,
`o5-practical-summary.json`, kernel/native validation manifests.

## 5. O2 projection homotopy: negative native result

Schedule **s=0, .25, .5, .75, .9, 1**, two accepted outers per stage, with an
18-attempt stage cap. Ordinary storage and the original Eta2 controller were
retained. All ten scored opening runs completed all stages and entered the
original projection objective; no incomplete-stage target counted as a hit.

| Scene | Off hits | O2 hits | Off median endpoint | O2 median endpoint |
|---|---:|---:|---:|---:|
| Final3068 | 4/5 | 1/5 | 1744674.24 | 1825568.93 |
| Venice52 | 0/5 | 0/5 | 246328.97 | 370203.57 |

The sole Final3068 success took **25.911 s**, compared with off's successful
range **1.941–5.872 s**. Venice's median endpoint was approximately **50.3%**
higher. It failed the tail gate, so no practical panel was launched.

**Verdict:** reject this schedule. The staged projection can reduce its own
objective while directing the trajectory toward a worse full-perspective
solution. Keeping distortion means s=0 is not the advertised convex problem;
interpolated signed depths also do not guarantee the absence of poles.

O2 was the independent agent's implementation. The final version passed
derivative/model/point-mask tests at all six stages, original/off N=3 checks,
memcheck, cap/target edge tests and 182 aligned attempt/work trace rows.
Gauge fractions are explicitly **unmeasured**, not reported as zero.

Evidence: `o2/HANDOFF.md`, `o2/MATH_AND_COVERAGE.md`, `run_o2.py`,
`o2-tails-results.json`, `o2/validation_manifest.json`.

## 6. O1 object-space constrained opening: implemented, useful numerical distinction

Implemented FP64 3-DOF translation / 3-DOF point matrix-free Schur products,
weighted Procrustes rotations, per-camera linear least squares in (f, f*k1),
signed depth inequalities and an exact primal active set. The first camera's
translation plus a baseline-parallel constraint fix the four-dimensional
fixed-rotation gauge. The depth condition is relative to the sweep input;
rotation updates violating initial feasibility are reverted before the QP.
Only original full-L2 descent accepts a completed sweep.

Point-local active constraints are eliminated exactly. Their correction is
not a finite penalty. The implementation supports three independent active
depth constraints per point, 32 active observations globally, 64 active-set
iterations and 1024 PCG iterations per equality solve. Unsupported ranks and
failed residual/feasibility checks explicitly abandon the sweep.

Independent dense QP/KKT comparisons, binding depth constraints, both depth
signs, multiple equality constraints, radial inversion, rotation and intrinsic
updates passed. Valid GPU steps matched dense references within approximately
**5.4e-13** relative error. A separate test confirms that the unsupported fourth
point constraint fails explicitly. This guard test is not a solved QP.

On Dubrovnik88's unscored smoke test, three valid sweeps were accepted with
active counts **18, 13, 11**, using **2632 Schur products** in total. This
already shows why a small active set does not imply a negligible solve cost:
adding/removing constraints requires additional equality solves.

On **Venice**, every k=3/5/10 opening completed all requested sweeps in all
five runs; nevertheless each arm was **0/5** at the target. Median endpoints:

| Arm | Median final L2 |
|---|---:|
| Fresh off | 247529.64 |
| k=3 | 255833.68 |
| k=5 | 252381.75 |
| k=10 | 256270.76 |

On **Final3068**, all 15 opening attempts failed the first PCG solve at its
1024-iteration limit, before a QP step was accepted. The first residual was
**0.08136**, versus the requested 1e-8 tolerance. Each restored its input and
continued with Eta2. The resulting 2/5, 2/5 and 1/5 target counts, versus off's
4/5, must **not** be attributed to a changed O1 basin: zero opening sweeps were
accepted. The extra computation and stochastic Eta2 continuation remain real
costs of this incomplete implementation.

A separately registered numerical follow-up used the true 3x3 **Schur diagonal
as preconditioner**, leaving the QP unchanged. Tiny independent checks passed.
On Venice, three valid sweeps used **104 products instead of 136** in the
reference first run; this is an N=1 work-count diagnostic, not a speed claim.
On Final3068, block/ray validation aborted before PCG with the diagnostic's
`invalid_ray_or_nonPSD_block` guard. This did not resolve the numerical obstacle;
the broad guard does not identify a particular eigenvalue or camera. No fresh
tail grid was authorized by that follow-up's success gate.

**Verdict:** native negative on Venice; **numerically unresolved on Final3068**.
Do not turn the latter into a refutation of the exact convex subproblem.
Convexity does not guarantee a well-conditioned, inexpensive GPU solve.

Evidence: `O1_PROTOCOL.md`, `o1.cuh`, `o1-kernel-validation.json`,
`o1-tails-results.json`, `O1_SCHUR_DIAGNOSTIC.md`,
`o1-schur-diagnostic.json`. O6's prerequisite was not established, so no large
SOCP or structureless opening was built.

## 7. Corrections to the mathematical and novelty premises

The [primary-source audit](literature/MATH_AND_PRIOR_ART.md) records the reading
and direct links. These corrections are substantive, independent of speed:

1. SIMPLE_RADIAL with k1 nonzero is rational with denominator powers up to
   three, not generally linear-fractional. Fixed-depth s=0 still retains cubic
   distortion. First-order camera coordinates also omit rotation and joint
   camera/point cross terms.
2. Matching an object-space surrogate's cost to pixel L2 does not match its
   gradient or make it a majorizer. For F=x²/(2z²) and frozen Q=x²/(2z0²), costs
   match at z0 while Q_z=0 and F_z=−x²/z0³. Triggs et al. explicitly warn about
   frozen projective-depth reweighting in §4.3, footnote 8.
3. Joint object-space optimization needs a scale constraint. Otherwise scene
   collapse improves its algebraic objective without improving projections.
4. LHM's pose convergence statement concerns known 3D geometry/calibration;
   it is not a global optimum guarantee for alternating BA.
5. Object-space Procrustes BA with SVD rotations and IRLS is already close
   prior art: [Fusiello and Crosilla, 2016](https://isprs-annals.copernicus.org/articles/III-3/35/2016/).
   O1 cannot claim those ingredients themselves as novel. Their depth-scale
   normalization also addresses collapse. A specific scalable constrained
   opening and a measured reliability result would need a narrower claim.
6. Known-rotation L-infinity quasiconvexity and SOCP initialization of L2 BA
   are established in [Kahl and Hartley, 2008](https://www.maths.lth.se/matematiklth/vision/publdb/reports/pdf/kahl-hartley-pami-07.pdf).
   This does not make distorted pixel L2 jointly convex.
7. High perspective Jacobian sensitivity is not a high statistical weight in
   the original L2 objective, and does not prove a zero optimal residual. A
   frozen anchor also does not enforce the ray of a moving camera.

There is no demonstrated new fastest solver or positive novelty claim from
this wave. Its durable contributions are the rational-attribution diagnostic,
the exact constrained Schur implementation and tests, clean negative staged-
objective results, and the carefully bounded O5 tail signal.

## 8. What the suggesting agent should use next

The E4 projection-pole event is real and detectable, but it does not cover the
recorded Final3068 stop witnesses. A single-cause account of all tails is too
strong. Locally valid/full-cost-decreasing surrogate openings can still finish
worse; removing a pole from the subproblem is not itself a basin guarantee.

The cheapest remaining empirical question from this campaign is whether O5's
5/5 Final3068 result survives a larger fresh cohort and competes with the frozen
portfolio after all runtime is charged. O1 needs numerical work on the convex
system before another Final3068 reliability claim; its current fallback rows
provide no such evidence. O3/O4 need a new, explicitly registered detector or
constraint formulation if revisited, rather than relabeling their failed gates.

No additional runs are implied by this feedback file. All original champion
defaults remain intact.
