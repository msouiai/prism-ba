# Eta2 wave 2: feedback to the proposing agent

**Frozen Eta2 remains the global winner.** The strongest positive finding is a
cheaper explanation of the Venice accurate-opening result: tighter early CG plus
rejecting oversized directions works with the ordinary storage path. Neither
radius fitting nor geodesic acceleration became a general improvement, despite
real gains at individual witnesses. Bounded plateau escalation rescued 0/5
observed Final3068 stopping witnesses.

This report covers the W1–W10 brief pasted into the conversation, following the
568-run first wave. It does **not** silently substitute for the differently
numbered `ba_wave2_local_clocks.tex`: that document is absent from the local
filesystem and fetched origin/master. Its W9.0/W10/W11/W15f/P3 arms need the
actual text before an implementation can be claimed to follow their protocol.

## Experimental record

Source/configuration: the frozen
[`champion.json`](../eta2_champion/champion.json),
[`source_manifest.json`](../eta2_champion/source_manifest.json), and
[`theory_and_novelty.md`](../eta2_champion/docs/theory_and_novelty.md).
The source SHA256 is
`22c18359a526526ae0a5b5109187878ab1cef33b453f6bbddc2aa92597a607d8`;
the original binary SHA256 is
`1e3d2cf22a8a43075114e0ca2024923dad330461e35d0074938d0412cd77ecc0`.
Source and 44 headers were checked in-session before comparisons. All changes
are opt-in derived builds; the original algorithm/defaults remain unchanged.

Every scored run retains the same observations, plain L2 SIMPLE_RADIAL,
unshared intrinsics and k2=0. The frozen solver uses double state, arithmetic
and scoring with compact FP32 fragments; the coherent FP64 operator is a separate
reference path. Endpoint cost is independently recomputed in FP64.
Native wall includes per-attempt telemetry and extra solves. No robustness loss,
observation dropping, learned component or cross-iteration Krylov reuse was used.
Repetitions and fixed targets were registered before the relevant scores.

There are 401 scored native runs and 24 compatibility runs in this wave, plus
the fixed-state calculations and 21 additional composition diagnostic runs.

The complete numerical ledger is **[NUMBERS.md](NUMBERS.md)**, with every run in
**[metrics.csv](metrics.csv)** and machine-readable aggregates in
**[summary.json](summary.json)**. These include time to target, hit counts,
endpoint cost, initial score, rejects, retry wall and PCG/outer. N=3 empirical
disjoint ranges are the registered descriptive timing criterion, not confidence
intervals. Fresh tail cohorts are kept separate; their different control hit
counts are evidence against casually pooling small samples.

## W1/W4: the raw step is mostly a camera-outlier problem

All seven original captures were decomposed, along with three complete fresh
Venice trajectories per opening arm and three next-solve reconstructions at
each of the five original failed static-damping Venice endpoints. Reconstruction
uses the recorded terminal lambda/radius and state, with fresh forcing history;
it is not the exact historical last attempted solve.

| Original witness | Raw/R | Gauge fraction of squared norm | Top-five-camera fraction |
|---|---:|---:|---:|
| Venice0 |0.118|0.141%|99.9986%|
| Venice1 |6.990|0.363%|99.999997%|
| Venice2 |0.571|0.148%|99.99995%|
| Final3068/0 |39.30|0.0000045%|99.52%|
| Final3068/5 |498.67|0.0489%|98.63%|
| Final3068/6 |632476|0.0000399%|96.52%|

The reconstructed static-damping endpoints all give raw/R about 428.26, gauge
about 0.174%, and top-five fraction about99.9999%. Thus the old425-ratio failure
survives reconstruction and is not predominantly a global gauge motion.
Opening trajectories do sometimes have gauge fractions around31%; they never
cross the proposed 50% priority trigger. We did not run a gauge-projected solver
and do not claim every gauge-handling strategy is refuted.

K8 captures about53% of the raw norm at several Venice states, but that includes
clusters isolating the exceptional cameras. It is not evidence that a distributed
long-wavelength mode dominates. Norm fraction is also not model-decrease fraction:
at one static endpoint the local-cluster and remainder allocations are about
−933,084 and +934,292, with large cancellation. Every decomposition retains the
cross terms and the point-only offset. See `witness/` and
`composition/*/decomposition.json`.

Two mathematical qualifications to the brief were registered before testing:

1. With fixed point damping and scaling, the reduced system is
   `A(lambda)=S_tau+lambda I`, its RHS is fixed, and an SPD exact solution has
   monotonically decreasing norm as lambda increases. Coupled tau=lambda changes
   both the matrix and RHS: camera-step norm need not be monotone. A checked toy
   supplies a counterexample. The coupled root controller is consequently a
   safeguarded heuristic, not an exact camera-radius Moré–Sorensen solver.
2. Point damping supplies gauge curvature as well as injecting the reduced RHS
   component. For a joint gauge vector, its Schur contribution includes
   `n_p^T [V − V V_tau^-1 V] n_p`, in addition to camera damping. The RHS identity
   in the brief was checked; omitting this curvature term gives an incomplete
   mechanism. Dropping camera gauge followed by damped point completion is not
   an exactly objective-invariant joint similarity transformation.

## W2/W3: opening attribution succeeds; permanent radius fitting does not

Fresh Venice N=5, target 243740.27:

| Arm | Hits |
|---|---:|
| Matched off |0/5|
| lambda0=1 /10 /100 |0/5 /0/5 /2/5|
| Disable interior lambda reduction permanently |0/5|
| Disable it for first 3 accepts |0/5|
| One lambda×16 at outer1 |0/5|
| eta0.05 first 3 accepts, ordinary clipping/storage |0/5|
| eta0.05 + reject oversized, ordinary storage |**5/5**|
| Full coherent accurate opening |**5/5**|

The ordinary-storage successful-hit median was0.3130 s versus0.3754 s for the
coherent reference in this cohort. Coherent FP64 workspace is therefore not
necessary for this Venice benefit. Forcing alone fails, and cheap lambda-only
interventions do not reproduce it reliably. This rejects the strong claim that
an arbitrary early lambda increase alone explains the benefit. It does not prove
lambda history is irrelevant to the successful interaction.

Both successful arms were expanded under the registered rule. On Final3068,
target 1744796.9841897595, the fresh N=5 counts were off4/5, ordinary-storage
forcing/rejection4/5, coherent opening3/5. On all nine practical cells, N=3:

| Arm | Disjoint faster / slower / overlap | Geometric mean time/control |
|---|---:|---:|
| Ordinary-storage forcing + oversized rejection |4 /4 /1|1.0285|
| Coherent accurate opening |0 /7 /2|1.4942|

The cheaper opening is a real narrow candidate and a useful attribution result;
the mixed panel prevents a universal promotion. No scene-specific selection rule
has been validated. The complete ranges and crossings in both directions are in
the ledger.

Radius fitting did improve several coherent witness directions. At Final/5,
clipped decrease15.2779 becomes22.9322 with coupled damping or16.2424 with frozen
tau. At Final/6,0.026373 becomes0.030420/0.028592. But Final/0 goes backwards:
0.200351 becomes0.175360/0.177377. Venice1 improves from0.034862 to0.117524/0.122268.
Independent full-normal residuals for these exported root directions are below
1e-8; nonlinear scores agree. Witness gains are not an artifact of a wrong sign
or uncertified reference solve.

Native kappa2, eight-update safeguarded root fitting then failed the rollout:

| Native root arm | Venice hits | Final3068 hits | Nine-cell time/control |
|---|---:|---:|---:|
| Fresh off |0/5|2/5|1|
| Coupled |0/5|0/5|1.1808|
| Frozen tau, factors/RHS cached within outer |0/5|1/5|1.2121|
| Opening-only coupled |0/5|2/5|0.9993|

Coupled and frozen arms have zero disjoint timing wins and two disjoint losses
each; the other seven ranges overlap. Their median times are slower on 6/9 and
5/9 cells respectively. Opening-only fitting never fires on the two tail scenes:
the cheap opening solve does not expose an oversized direction.

This tests fresh PCG re-solves, including frozen-tau caching. **A five-shift
secular root-finder was not implemented**, so this is not a measurement of its
potential iteration-sharing savings. Free interpolation between approximate
shift solutions would also require checking the interpolated solve/step. Do not
call every exact trust-region or shifted-root method refuted by these rows.

## W5: analytic geodesic arithmetic is usable; global acceleration loses

The original finite-difference directional RHS produced independent full-normal
relative errors up to 0.00809 at Final/6. We retained that failed audit and replaced
the derivative with an analytic one for the actual retraction. With
`R(alpha)=exp(alpha*omega)R`, additive translation and points:

```
Y'  = omega × (R X) + delta_t + R delta_X
Y'' = omega × [omega × (R X)] + 2 omega × (R delta_X)
```

The projective division and SIMPLE_RADIAL expression are then differentiated
twice, including focal/distortion mixed terms. Independent full-normal residuals
fall to5.46e-11,6.40e-9,3.82e-10 and1.64e-9 at Venice0/Final0/5/6. The analytic
version retains the useful witness gains: Final/5 decrease15.2779→18.5850;
Final/6 about 0.02637→0.03513; Venice0 about35.510→36.40. Final/0 is effectively
unchanged. No extra finite-difference residual evaluation is needed.

The native second RHS, Schur product, point completion and physical camera sign
were independently checked on a dense toy (relative discrepancies below 2e-15),
with zero memcheck errors. Native second CG is deliberately inexact, eta=0.5,
and independently recomputes its reduced residual before accepting the correction.
Both candidate acceptance and the controller use the actual corrected step.

Nonetheless, on fresh native N=5, Venice stays 0/5 and the median endpoint is
253431 versus247550 for off, about 2.4% worse. Final3068 is 3/5 versus 4/5, with
conditional median times4.6313 versus 4.1414 s and overlapping ranges. This is a
small observed hit-count difference, not a significant probability estimate.
On the practical panel the arm wins all three Trafalgar138 tolerance cells,
loses all six Ladybug539/Final394 cells, and has geometric mean time ratio1.1195.

The guard is not simply disabling the method: Venice admits 808/985 corrections,
with 768 winning and ultimately accepted; Final admits 94/363, with 41 winning
and ultimately accepted. Better local proposals can still select a worse later
trajectory. The derivative, independent auditing and second-RHS implementation
are reusable research assets; the always-on policy is not the new champion.
See `geodesic_analytic/`, `geodesic_native_validation/`, and the native ledger.

This is established geodesic-acceleration prior art, adapted to the existing
Schur machinery, not a new acceleration theorem. Primary references are
[Transtrum & Sethna](https://arxiv.org/abs/1201.5885) and
[GSL nonlinear least squares](https://www.gnu.org/software/gsl/doc/html/nls.html).

## W6: a pole matters, but the tested safeguards do not yet give a solver win

The local Ladybug1197 point 47270 replay exactly reproduces the documented
two-observation point-Newton explosion. Scores below are conditional track scores
at the prescribed camera move, not whole-problem timing or endpoint comparisons.

| Point completion | Track cost | Minimum depth ratio | Local descent |
|---|---:|---:|---|
| Point-Newton |9.1199e10|0.007197|No|
| Ordinary GN |214.31|1.0983|Yes|
| Newton + fixed shadow barrier |8.6917e10|0.007250|No|
| Pole-bounded rational ray search |1230.49|0.6615|Yes|

The barrier uses a signed-depth ratio (valid Snavely depths may be negative),
fixed `mu=.01*(2F/nobs)`, gradient plus rank-one model Hessian, and true pixel
cost for scoring. That coefficient fails its first gate, so the162-row chart
expansion was not run. This does not refute all barrier schedules. The ray search
prevents this explosion, but ordinary GN is already better on this point; that
repair alone does not establish a production advantage. Its rational objective
is exact, while the bounded numerical minimizer is not a certified global1-D solve.

Per-camera first-order depth bounds were also screened at all seven witnesses,
N=3. They change zero cameras at six witnesses and one at Final/6. Removing the
global ball and relying on these bounds admits bad full proposals, including
cost increases about219 and205307 at Final/0 and/5. Depth preservation does not
control exceptional focal/translation/distortion directions. This rejects that
specific replacement for the ball, not every per-camera globalization method.

## W8: delaying the intervention until stopping still fails its witness gate

The registered arm waits for the champion's actual stopping decision, retaining
current lambda/radius/state. It allows one coupled radius-fitting outer and two
analytic geodesic outers, resumes baseline only on meaningful progress, and never
restarts from the input or restores earlier controller state.

Fresh N=5 tail cohorts give Venice 0/5 for both arms and Final3068 3/5 for both.
To satisfy the conditional miss-witness gate, the Final arm was extended under
its pre-registered rule:18 total on-runs produced 13 fast target hits and five
above-target stopping witnesses. **None of the five witnesses was rescued.**
All 18 runs are retained, including fast successes; the five conditional witnesses
are not used as an independent hit-rate denominator. The practical expansion is
killed by the specified 0/5 rule. One Venice continuation did gain 0.64% after its
old stop, but it still missed the target. No portfolio-reliability gain is claimed.

## Scope, reproducibility and remaining ideas

- W1 is complete for the stated witness and trajectory sets, subject to the
  explicitly labelled next-solve reconstruction and snapshot-retention limits.
- W2a/b and native frozen-tau fresh solves, W3 attribution, W5 analytic/native
  tests, W6 conditional tests and W8 stopping gate are measured above.
- W4 projection did not meet the priority trigger; it was not run.
- Frozen-tau multi-shift root sharing, W7 adaptive point radii, W9 consistent
  FP32 production and W10 angular shadow models remain untested. They are not
  added to a negative-results list. The latter three were lower-priority or
  conditional items in the supplied sequence.
- No new Caspar, MFREE or largest-BAL head-to-head was run in this wave. These
  measurements do not strengthen an external SOTA claim by themselves.

The strongest feedback for the next design is to distinguish **few-camera
intrinsic/pose ambiguity** from global gauge or broad cluster motion, and to
retain the accurate-opening interaction as a narrow measured result. Simply
making a coherent solve more exact, fitting its norm to the old radius, or adding
a locally useful second-order correction does not establish a faster trajectory.

Every builder/protocol and the compact raw traces are in this directory. Large
exports are indexed by their manifests. Storage pressure required lossless
repacking of historical exports (`storage_compression.json`,
`storage_xor_archives.json`, decoder `lossless_float_archive.py`). Historical raw
paths listed there require restoration before old consumers can use them.
For new full-trajectory diagnostics, all camera vectors and scalar/model series
are retained, but full point states/diagonals are retained only at the first,
largest-ratio and last attempt. All original member hashes remain; hashes cannot
reconstruct omitted bytes. See [SNAPSHOT_RETENTION_ADDENDUM.md](SNAPSHOT_RETENTION_ADDENDUM.md).
Scored endpoint exports remain preserved and independently audited.

Figures: [native convergence](figures/venice_convergence.png),
[all nine practical cells](figures/practical_time_ratios.png),
[lambda/radius trajectories](figures/venice_controller_trajectories.png).
PDF versions are alongside the PNGs. Interpret diagnostic-trajectory wall only
as diagnostic wall; snapshot IO is not used as a production speed measurement.
