# Feedback on the bundle-adjustment research brief

**To:** the agent that proposed `research_promt.tex`

**From:** Codex, reporting experiments performed for Mo

**Date:** 11 September 2026
**Purpose:** a self-contained handoff of the suggestions, implementation choices, evidence, limitations, and recommended revisions. This is a report of completed work, not a request to repeat the entire agenda.

The original brief is preserved unchanged. Its SHA256 is
`d19870839602bf0e325e28de41d737a12ce300cf864acd5d02359063bc7cbba8`.
The committed [copy of the brief][brief] matches that hash. The eight-track
implementation and evidence are frozen at commit
`e121e914b79aa3b632f76c402f50a6aac8969344`; the subsequent BAL collective-correction
follow-up is at `78fc32e8f33f54eaf46b5298032ef7ce46d75620`. Links below point to
those commits so this file can be forwarded independently of the checkout.

## 1. Executive assessment

We followed T1 through T8 in order and honored the conditional stop rules.
**No extension earned promotion over the retained production configuration.**
The frozen Eta2 configuration remains the incumbent for this investigation;
that statement is not a fresh comparison against every configuration on master.

The strongest result is **T4: nonlinear collective corrections**. On controlled
weakly coupled reconstructions, the nonlinear path improves both time to target
and relative geometry over ordinary BA and a matched linear coarse correction.
Automatic partitions can preserve the gain, including at a larger synthetic
scale. However, two successive BAL-sample screens fail to show an end-to-end
speed improvement. We subsequently made the nonlinear coarse calculation
roughly 2–4 times cheaper using exact internal-projection invariance, yet it
still saves no subsequent fine BA iterations on the tested BAL samples.

Several other mechanisms are measurable without being useful speedups:
geodesic corrections sometimes reduce rejections; point relaxation changes
candidate rankings; robust continuation recovers one additional mixed-bridge
case; depth smoothing modestly improves low-parallax geometry; and a small
learned policy predicts local computational utility. Their additional work,
counterexamples, or lack of transfer prevents promotion.

| Track | Measured result | Supported conclusion |
|---|---|---|
| T1: projection-aware control | Correct identities and useful diagnostics; inconsistent incremental prediction | Keep instrumentation. Do not claim a validated controller or a general refutation of depth-aware control. |
| T2: curved updates | Geodesic arm 0.651x ordinary-LM speed overall; hybrid 0.970x | Iteration savings do not repay this implementation's added work. |
| T3: point relaxation before ranking | Winners change in 13–19% of menus; pre-ranking is slower than post-only polishing | Ranking mechanism exists; speed/novelty gate fails. |
| T4: nonlinear collective motion | Automatic larger synthetic cases: 3.06x/2.70x ordinary BA; real transfer remains negative | Strong conditional mechanism; no production promotion. |
| T5: information-aware continuation | One extra mixed-case recovery; false-bridge protection and slower timings | Information preservation alone is an insufficient scheduling criterion. |
| T6: temporary depth smoothing | Better median low-parallax geometry at only 0.578x speed | Qualified geometry benefit, not a convergence-speed improvement. |
| T7: spectral pruning | Filter algebra passes; no pruning threshold passes the development quality gate | A simpler existing menu is the effective control; new filters are untested. |
| T8: computation allocation | Good local scores; tree 0.861x ordinary speed on unseen rotation family | Local utility prediction is not evidence of faster complete optimization. |

All ratios in this report mean **baseline time / candidate time** unless
explicitly labeled otherwise. Larger than 1 is faster. Baselines differ by
experiment; the ratios must not be pooled into one solver ranking.

## 2. Comparison contract and evidence scope

### 2.1 Two distinct implementation levels

**Native T1 instrumentation:** we reproduced the retained nine-DOF GPU Eta2
source and instrumented it on Ladybug49, Dubrovnik88 and Venice52. This is the
only native GPU experiment in the eight-track agenda. It preserves the native
camera model, parameter conventions, and existing solver behavior.

**CPU mechanism experiments, T2–T8 and the BAL follow-up:** FP64 reference BA
with six camera pose DOFs, fixed intrinsics, shared landmark variables, and an
explicit seven-coordinate gauge: camera0 pose and point0.z are fixed. Candidate
states must have finite projections and negative observed signed depths. Every
arm within a comparison uses the same data, gauge, free variables and final
objective. Synthetic geometry is evaluated after **one global similarity
alignment**, never separate cluster alignments.

These CPU prototypes establish or challenge mechanisms. They do **not**
measure speed versus native GPU Eta2 or Caspar. The approximately 3x T4 result
must not be described as a 3x gain over either GPU solver. No production
default or original implementation was overwritten.

### 2.2 Targets, budgets, and validity

The common target form is

$$
F_{\mathrm{target}}=F_{\mathrm{ref}}+\tau(F_0-F_{\mathrm{ref}}).
$$

Synthetic references generally evaluate the generating state under the actual
noisy observations. They are feasible references, not global optima. The
sampled-real references come from a bounded ordinary-LM solve and are frozen
before comparative runs.

| Experiment | Target and budget |
|---|---|
| T2, T3, T7 | Synthetic reference, tau=1e-4; 80 attempts/2 seconds |
| T4 controlled/automatic | Synthetic reference, tau=1e-4; 2 seconds including setup and coarse work |
| T4 original real samples | Bounded reference, tau=1e-3; 2 seconds total |
| T5 | Final Cauchy reference, tau=1e-3; 60 attempts/2 seconds; count hits only at final scale |
| T6 | Synthetic original-objective reference, tau=1e-4; 48 attempts/1 second; count hits only at zero smoothing radius |
| T8 | Synthetic tau=1e-4; existing frozen real targets; 80 decisions/2 seconds |
| BAL collective follow-up | Bounded reference, tau=1e-3; 80 fine attempts/5 seconds total |

The real targets test a particular convergence regime, not convergence to an
accuracy floor. A target expressed relative to the initial gap may still be
well above the eventual minimum. We do not infer deeper-target performance
from runs stopped at the registered target.

Time includes setup, derivatives, all evaluated candidates, local/coarse
optimization, and policy features/inference where used. Primary summaries
take an N=3 median per arm and problem, then a median of paired ratios. Failed
pairs are reported explicitly rather than silently included as successes.

Synthetic point NRMSE above 0.15 is the registered coarse geometry-failure
indicator. Camera-center and orientation errors are also retained. This is a
screening threshold, not a universal reconstruction-quality definition.
Particularly in T2/T3/T7/T8, geometry is measured at target crossing, which
can precede full refinement. T5/T6 separately report a common terminal stage.
Real samples have no ground-truth geometry certificate.

### 2.3 Experimental coverage

Most controlled screens use ten development seeds and ten new held-out seeds
per setting, with three timing repetitions. The T4 partition revision uses
new held-out cohorts rather than retuning on the same reported outcomes.

The raw files contain 6,339 CPU solver runs in the eight-track agenda and 135
in the later BAL screen: **6,474 recorded solver runs, including capped or
failed runs**. These are not 6,474 independent scenes. There are additionally
1,908 T8 action replays, 90 geometry-only T4 endpoint replays, 27 frozen-real
reproduction checks, and the native T1 runs/diagnostic captures.

The measured host uses an AMD EPYC 9354, Python 3.12.3, NumPy 2.1.2, SciPy
1.16.2, and one BLAS/OpenMP thread for CPU timings. Native T1 uses an RTX 2000
Ada. Small CPU timings, repeated seeds from a few generators, and three real
scene families do not establish universal speed or population-level certainty.

## 3. T1 — Projection-aware model-error control

### Suggestion and implementation

The brief proposes that fractional depth motion distinguishes dangerous
perspective steps better than a global damping value or step norm. It first
asks for instrumentation, with a controller conditional on incremental signal.

We verified the exact identity, in the consistent BAL projection convention,

$$
\Delta\pi=\frac{J_\pi\Delta q}{1+\gamma},\qquad
\gamma=\Delta z/z,
$$

and separated perspective nonlinearity from pose-chart/rotation-point error,
radial distortion and intrinsic-update error. Prospective features use the
linearized depth motion; exact motion is used for retrospective checks. We
also measured a fresh reduced-system residual separately from the recurrence
residual and the full GN/filter residual.

### Findings

- Exact pinhole identity error is approximately 2.2e-16; the defect
  decomposition reconstructs the total to approximately 1.3e-14.
- Independent CPU trial costs agree with native costs within 2.2e-13 relative.
  Original versus generated instrumentation-off N=3 endpoints differ by at
  most 4.21e-7 relative. This is numerical agreement, not bit identity.
- Fresh and recurrence Schur residuals agree within 8.11e-13, but actual
  relative residuals range from 0.024 to 0.485, median 0.305. Eta2 deliberately
  uses loose forcing; recurrence agreement is not proof of an accurate solve.
- Across 69 native proposals, failed proposals have median nonlinear defect
  1.943 versus 0.525 for passing proposals. Their median numerical residual
  is smaller, 0.296 versus 0.351. This is association, not a causal attribution.

Incremental rejection prediction is inconsistent:

| Held-out evaluation | Baseline AUC | With prospective depth feature |
|---|---:|---:|
| Synthetic, 120 proposals | 0.99870 | 0.99935 |
| Real, Dubrovnik family held out | 0.811 | 0.795 |
| Real, Ladybug family held out | 0.708 | 0.917 |
| Real, Venice family held out | 0.820 | 0.769 |

The Ladybug fold has only two failures. The synthetic rotation subset has no
failures and cannot establish discrimination. Two real folds worsen.

### Feedback to the suggesting agent

The identities and diagnostics are useful and should remain. The conditional
controller was not justified by this screen. However, **the synthetic AUC gate
is a design limitation**: the required +0.05 gain is unattainable when the
observed baseline is already 0.99870. That makes this cohort unsuitable for a
strong claim that depth adds no information. The tiny real cohort does not
resolve the broader question either.

A follow-up should select a harder rejection regime independently of the
candidate method, then evaluate calibration, rejection recall at a fixed cost,
or net wall-clock value. It should stratify numerical solve accuracy rather
than infer that nonlinear defect is the only remaining bottleneck.

A depth-penalty assembly prototype with the required camera-point cross terms
passes tiny-system checks. We did **not** run a penalty controller,
inverse-depth optimization ablation, or native depth-control speed experiment.
Those branches remain untested, rather than refuted. [T1 report and code][t1]

## 4. T2 — Spend cached solves on curved updates

### Suggestion and implementation

We implemented the proposed order-two correction using the same fixed damped
matrix for velocity and acceleration:

$$
Av=-J^Tr,\qquad Aa=-J^Tr_{vv},\qquad
\theta'=\operatorname{Retr}(tv+\tfrac12t^2a).
$$

The analytic second derivative includes rotation-point cross terms. A
finite-difference step sweep validates it to a worst best-step error of
5.18e-8. Curve parameters 1 and 0.5 are tested under a scaled acceleration
safeguard. The ordinary candidate remains available.

Controls are ordinary LM, ordinary LM plus geodesic acceleration, one extra
OCA recursion, a second damping value lambda/3, and a deterministic rule that
chooses curvature or OCA using the already evaluated trial's defect. All
feature/evaluation work is charged. New damping refactors; new RHSs reuse
factors only at the unchanged parent/matrix.

### Findings

| Arm | Depth speed vs LM | Rotation speed vs LM | Overall paired median |
|---|---:|---:|---:|
| Geodesic correction | 0.806x | 0.635x | 0.651x |
| Extra OCA recursion | 0.938x | 1.019x | 1.003x |
| Extra lower damping | 0.850x | 1.149x | 0.928x |
| Defect-based hybrid | 0.889x | 0.975x | 0.970x |

All arms reach all twenty held-out case targets, N=3. In the depth family,
geodesic correction reduces median accepted steps from 6.5 to 5 and rejects
from 1 to 0, but remains slower. At target crossing, geometry fails on 2/20
ordinary/hybrid cases, 4/20 geodesic/OCA cases, and 1/20 lower-damping cases.

### Feedback

The distinction between numerical error, filter bias and nonlinear path error
is sound. The cached solve alone is not the relevant cost: derivatives,
candidate projection and scoring eliminate the iteration saving here.
An implementation that stops merely after counting fewer factorizations would
have reached the wrong conclusion.

We ran full closed-loop alternatives rather than the brief's separate
equal-deadline snapshot contest. Ordinary LM spends its budget on fresh
linearizations after accepted steps; this is a practical comparator, but not
an exact local action-oracle experiment. That coverage difference should be
retained when interpreting the negative result.

Geodesic acceleration and higher-order reused-factor LM are established prior
art. The failed hybrid is not a new geometric method. A justified next test
would need materially cheaper native derivatives or a preidentified expensive-
relinearization regime; neither is established here. [T2 evidence][t2]

## 5. T3 — Relax landmarks before ranking camera steps

### Suggestion and implementation

The same three-damping menu is compared with raw ranking, one/three point
steps after acceptance, one/three before ranking, and selective pre-ranking
polishing of the worst quartile of track defects. Point steps use safeguarded
3x3 GN solves, with cameras fixed and the scale gauge preserved.

Every candidate starts from an immutable parent, owns its point state, and is
ranked by the complete unchanged objective. The whole winner is committed.
A thirty-step point reference records remaining stationarity rather than
assuming a global point minimum or an exact variable-projection branch.

### Findings

| Arm | Changed winners | Speed vs raw menu |
|---|---:|---:|
| Post-acceptance, one step | Not a pre-ranking change | 0.866x |
| Post-acceptance, three steps | Not a pre-ranking change | 0.712x |
| Pre-ranking, one step | 13.3% | 0.723x |
| Pre-ranking, three steps | 16.1% | 0.456x |
| Selective pre-ranking | 18.6% | 0.495x |

Pre1 runs at 0.694x post1 speed; pre3 at 0.590x post3. Point work consumes
41.6% and 67.1% of pre1/pre3 runtime. All arms hit all targets. Geometry fails
on 3/20 raw cases versus 1/20 for each polished arm at target crossing.

### Feedback

The hypothesis that polishing can change the selected camera proposal is
supported. The stronger claim that doing it before ranking improves
convergence speed is unsupported in this implementation. The simpler
post-only control is essential and wins that comparison.

The selective prototype still projects all observations, so its negative
timing does not measure the cost of a future sparse GPU polishing kernel.
The experiment matches total caps, not a separately optimized equal number of
extra point operations between pre/post arms. Any stronger engineering claim
requires that additional comparison. Do not call a few point iterations exact
nonlinear elimination, and do not treat the local post-only implementation as
a measured Ceres benchmark. [T3 evidence][t3]

## 6. T4 — Nonlinear collective corrections

### 6.1 The mechanism that survives the controlled tests

For a cluster similarity, update its unique points and camera centers by

$$
X'=sQX+t,\qquad C'=sQC+t,\qquad R'=RQ^T.
$$

An internal observation has camera coordinates `q'=s q`, so its central
projection remains unchanged for positive scale. The nonlinear and linear
coarse arms use the same tangent basis, but only the nonlinear finite path
preserves this invariance exactly. This isolates a path effect rather than
improved accuracy in solving the same linear system.

The controlled generator has three internally well-conditioned regions with
known relative similarity perturbations and controllable bridge tracks. All
original observations are retained; each point has one owner. Cluster0 fixes
the coarse gauge, and fine BA follows the coarse stage.

### 6.2 Synthetic results and automatic partitioning

| Cohort | Nonlinear speed vs fine BA, weak/strong bridges | Speed vs matched linear coarse, weak/strong |
|---|---:|---:|
| Known clusters, 12 cameras/180 points | 1.79x / 1.53x | 1.46x / 1.21x |
| Automatic v1, 12/180 | 0.66x / 0.61x | 0.97x / 0.95x |
| Automatic v1, 30/900 | 2.57x / 2.58x | 1.23x / 1.35x |
| Automatic v2, 12/180 | 1.62x / 1.32x | 1.57x / 1.42x |
| Automatic v2, 30/900 | 3.06x / 2.70x | 1.25x / 1.35x |

Each observable setting uses ten held-out seeds, N=3, with all targets hit and
no point-NRMSE>0.15 failures. The larger v2 paired-seed bootstrap intervals are
2.70–3.24x and 2.31–2.93x against fine BA. They are conditional intervals for
these generators, not cross-host or real-population guarantees.

V1 obtains the correct camera groups but can misassign approximately 9% of
points in small problems. V2 weights point-ownership votes by initial
reprojection consistency; it does not alter BA residual weights, duplicate
landmarks or remove inconvenient observations. It was registered separately
and tested on new seeds. Camera partitions alone are insufficient: assigning
a bridge point to the wrong owner changes which finite collective motions
preserve its originally internal observations.

The relative-scale audit is also positive. Median maximum absolute relative
log-size error for fine/linear/nonlinear is 0.04552/0.01552/0.004402 with weak
bridges and 0.02640/0.007452/0.001510 with strong bridges. This post-result
geometry-only replay exactly reproduces all ninety original endpoints. Size
is measured by centered point RMS radii relative to cluster0, without fitting
each cluster separately; internal shape distortion can also affect it.

Disconnected cases hit low objective targets yet fail geometry for every
seed. Their median globally aligned point NRMSE is approximately 0.323 and
relative log-size error remains approximately 0.158. They demonstrate missing
information, not a solver-recoverable basin. [T4 report][t4], [derivation][t4math]

### 6.3 First real transfer: small connected BAL samples

The first transfer uses up to 24 greedily connected cameras and 300 points
from Ladybug49, Dubrovnik88 and Venice52, N=3. All arms reach the same frozen
target for each subproblem.

| BAL sample | Fine BA | Nonlinear coarse + BA | Paired speed |
|---|---:|---:|---:|
| Ladybug49 | 95.1 ms | 119.6 ms | 0.795x |
| Dubrovnik88 | 63.4 ms | 93.0 ms | 0.682x |
| Venice52 | 94.4 ms | 122.0 ms | 0.774x |

Linear and nonlinear coarse curves almost coincide. These small samples may
favor one internally connected region and underrepresent the intended
collective pathology, so we did a broader follow-up rather than calling this
a general real-BA refutation.

### 6.4 Broader BAL follow-up and exact bridge-only evaluation

The new samples retain all 49/88/52 cameras and 1,200 points, with every
original observation of each selected point. Three point samples per scene,
N=3, and five arms produce 135 runs. Keeping every camera still does not
preserve every original graph edge. Ten initially invalid Ladybug points are
excluded from the eligible pool; Dubrovnik/Venice have none. These remain
explicit sampled, fixed-intrinsics problems.

We implemented the exact decomposition

$$
F(T)=F_{\mathrm{internal}}(\mathrm{parent})+F_{\mathrm{bridges}}(T).
$$

Only changing bridge observations need coarse derivatives and trial evaluation.
The complete objective and depth validity are verified before returning the
coarse state. This shortcut cannot be used for the linear coarse trial: its
internal projections change at finite step length.

Equivalence checks on three controlled and three real inputs show maximum
relative matrix error below 3.6e-16, RHS error below 2.4e-15, and coarse endpoint
discrepancy below 2.4e-13. Across timed runs, the final full-cost verification
discrepancy is below 7.3e-14. All 135 targets are hit, with no invalid final
depths or recorded numerical failures.

| All-camera BAL samples | Original nonlinear8 speed vs fine | Bridge-only nonlinear8 | Selective bridge-only |
|---|---:|---:|---:|
| Ladybug49 | 0.858x | 0.909x | 0.936x |
| Dubrovnik88 | 0.848x | 0.906x | 0.923x |
| Venice52 | 0.835x | 0.884x | 0.923x |

These are medians of per-sample ratios; raw seconds from different samples
are not pooled to form a speed ratio. The optimized nonlinear arm remains
approximately 10%, 10%, and 13% slower than fine BA.

| Scene | Original coarse stage | Bridge-only coarse stage | Subsequent fine accepted steps, median |
|---|---:|---:|---:|
| Ladybug49 | 56.6 ms | 19.3 ms | 10 in either arm |
| Dubrovnik88 | 115.3 ms | 28.0 ms | 9 in either arm |
| Venice52 | 92.6 ms | 45.3 ms | 11 in either arm |

The coarse stage is roughly 2–4x cheaper, but no sampled problem saves a
subsequent fine accepted step. Fine rejects have median zero. Partitioning
still consumes about 5–7% of runtime. The simple selector skips eight of nine
samples, while paying for their partitions.

The motion audit explains why an opening coarse stage has little opportunity
here: one ordinary step removes 75–95% of initial cost, whereas eight coarse
steps remove 5–29%. Initial coarse rotations are only approximately 0.3–1.3
degrees. The largest first-step linear/nonlinear cost difference is 0.18% of
initial cost and its sign is mixed. Dubrovnik's three-way partition allocates
one group to only two cameras; Venice has 35–42% bridge observations. These
are unlike the clean, internally optimized, weakly connected synthetic
regions. [BAL follow-up report][bal], [raw results][balraw], [figure][balfig]

### Feedback

T4 remains the most defensible research lead. The controlled effect is
supported by a matched tangent-basis ablation, partition failure/recovery,
larger synthetic tests and geometry measurements. **Its native/full-BAL
performance and novelty remain unproven.**

The next hypothesis should be **late selective correction after internal
error has fallen**, with a detector and partition whose costs are charged.
It needs new held-out real samples and a preregistered tighter secondary
target. The detector must predict fine work that will be saved, not simply
identify a sparse graph or a low eigenvalue. We have not run that schedule.

The bridge-only implementation is useful engineering, but follows established
submap invariance. Local frames, finite group transforms and nonlinear coarse
corrections already have close prior art. A contribution requires a successful
space/schedule construction and real transfer, not just the Sim(3) formula.

## 7. T5 — Observability-aware robust continuation

### Suggestion and implementation

The final objective is Cauchy loss at sigma=1 pixel. Temporary stages use
sigma=32, 8, 2, 1; frozen GN weights and exact current-stage cost govern each
solve. Larger-scale stages may increase final-objective cost, which is logged.
No observations are removed, and target hits count only at the final scale.

The information controller monitors three weak nonzero collective directions
with a fixed state-unit metric. It delays a scale reduction if any loses more
than 75% of its Rayleigh information at the same current state. Artificial
damping is excluded from the observability measurement. Controls are fixed
robust scale, ordinary continuation and a residual-based schedule. Correct,
mixed, fully corrupted and disconnected bridges are all tested using known
clusters. All runs reach final sigma and receive at least 36 terminal attempts.

### Findings

| Case | Information controller versus ordinary continuation |
|---|---|
| Correct bridges | 0.945x speed; no effective schedule change |
| Mixed bridges | 10/10 scene targets versus 9/10; 0.942x speed on nine common hits |
| All-corrupted bridges | 0.442x speed; median 10.5 delays; 7.5 retained false inliers versus 6.5 |
| Disconnected | Low objective targets reached; every scene fails relative geometry |

On fully corrupted bridges, median final robust cost is 125.07 versus 114.14,
and both schedules fail geometry on 9/10 cases. Spectral/feature monitoring
consumes about 1.3–5% of runtime. Correct/mixed continuation arms have no
geometry failures under the registered threshold. [T5 evidence][t5]

### Feedback

The extra mixed-case recovery is real in this cohort and must be reported
alongside the slowdown. However, preserving information is not the same as
preserving correct information. A coherent false bridge can support a
well-conditioned wrong geometry. The mandatory counterexamples expose that
distinction.

The missing ingredient is an independent indication of bridge consistency,
not merely a more sensitive eigenvalue threshold. Automatic clustering and
large native robust runs were not tested. Existing graduated optimization is
the baseline context; this screen neither replicates nor refutes those methods.

## 8. T6 — Temporary bounded depth smoothing

### Suggestion and implementation

We used the lowest-information point direction at initialization, frozen while
differentiating every stage. Three bounded depth samples have weights
1/4, 1/2, 1/4. Radii are 0.02 or 0.10 of each point's minimum initial absolute
observed depth. A seven-sample isotropic control matches covariance trace.
No invalid sample is deleted or renormalized; the whole invalid trial fails.

Six attempts at full radius and six at half radius precede 36 attempts at
zero radius on the original objective. The ordinary control receives the same
terminal refinement and lambda reset. A two-start ordinary comparator retains
both branches' work. Low and normal parallax are tested on ten held-out seeds,
N=3, with a separate development cohort.

### Findings

At low parallax, the larger depth tube reduces median point NRMSE from
0.1100 to 0.0920 and final cost from 11.5067 to 11.4985, with the same one
geometry failure in ten scenes. Its time-to-target speed is only 0.578x
ordinary LM. The smaller tube runs at 0.523x and increases geometry failures
from one to three.

At normal parallax, both tube radii reach essentially the ordinary final cost
and geometry after identical refinement, at 0.484x and 0.423x speed. The large
isotropic control hits only 7/10 low-parallax and 5/10 normal-parallax targets;
all its final geometries fail the registered threshold. The multistart first-hit
time is near ordinary because its first branch is ordinary; that is not
evidence that paying for the second start is free. [T6 evidence][t6]

### Feedback

The explicit return to radius zero and identical refinement were decisive.
Without them, an intermediate surrogate result could have looked like an
optimization gain. The low-parallax geometry improvement deserves retention
as a qualified result, but it does not meet the convergence-speed objective.

No adaptive radius policy or native GPU smoothing kernel was tested. A future
geometry-oriented study should separate the value of initialization from the
cost of repeatedly evaluating uncertainty. ProBA's probabilistic objective
and additional variables are a different problem; this negative result is
not evidence against ProBA.

## 9. T7 — Interpret and prune OCA spectral filters

### Suggestion and implementation

For the simplified recursion with fixed D=lambda*M, the whitened response is

$$
f_{k,\lambda}(h)=\frac{1-(\lambda/(h+\lambda))^{k+1}}{h},\qquad
f_{k,\lambda}(0)=\frac{k+1}{\lambda}.
$$

Tests cover PSD/null modes, a general SPD metric and a gauge-fixed BA system.
Maximum BA recursion/closed-form error is 1.06e-14. The indexing is explicit:
depth zero is one damped solve, and deeper OCA changes the response rather
than merely refining that first damped equation.

The grid uses five damping multipliers and depths 0, 1, 3, 7: twenty candidates.
A twelve-step RHS-seeded Lanczos quadrature estimates weighted response
distances. Exact eigendecomposition is an offline diagnostic, not a proposed
production operation. Forty development and forty held-out parents are saved.

### Findings

| Pruning threshold | Mean candidates kept, development | Development quality passes | Held-out quality passes |
|---|---:|---:|---:|
| 0.01 | 18.43 / 20 | 38 / 40 | 39 / 40 |
| 0.03 | 15.20 / 20 | 38 / 40 | 38 / 40 |
| 0.10 | 7.45 / 20 | 22 / 40 | 24 / 40 |

No threshold passes the registered all-parent quality criterion, so the
deployed rule is frozen at zero pruning. Even threshold 0.01 merges held-out
steps with exact relative distance as large as 0.187.

| Complete-run menu | Paired median speed vs full twenty-candidate menu |
|---|---:|
| Five dampings, depth zero | 2.78x |
| One damping, four depths | 3.80x |
| Spectral rule frozen at no pruning | 0.847x |

The simple four-candidate menu is 1.36x faster than the simple five-candidate
menu here. All targets are reached; every menu shares three geometric failures
among twenty held-out scenes. Spectral features consume approximately 14.4%
of runtime. [T7 evidence][t7]

### Implementation warning and feedback

Changing point damping changes the Schur operator nontrivially:

$$
S(\lambda_c,\lambda_p)=H_{cc}+\lambda_cM_c-
H_{cX}(H_{XX}+\lambda_pM_X)^{-1}H_{Xc}.
$$

The explicit test shows a substantial non-scalar component. However, this
does **not** invalidate every native shifted family: the legacy menu keeps
point factors fixed while changing camera shifts within an attempt. Changes
of effective point damping across attempts invalidate the old factors/operator.
The frozen Eta2 classical-LM path requires one shift. Our full-system CPU
grid is not a matched ablation of the native five-shift implementation.

The algebraic hypothesis succeeds; the inexpensive estimate and nonlinear
quality gate do not. Future diagnostics should separate approximation error
in spectral distance from the failure of exact step similarity to predict
nonlinear outcomes. The saved exact spectra/steps permit that study. Merely
increasing Lanczos work or proposing new filters has no demonstrated cost
justification yet. PowerBA's fixed-Schur inverse expansion and the simplified
OCA response are distinct constructions, not interchangeable benchmarks.

## 10. T8 — Learn which computation to perform next

### Suggestion and implementation

We replayed six alternatives from independent parent states with a common
ordinary-LM cache: commit the ordinary step and relinearize next, extra OCA,
new lower damping, curvature, point polishing, and automatic nonlinear coarse
correction. True-cost evaluation is mandatory. Factors are reused only for
unchanged matrices. Numerical coarse failure retains the ordinary fallback
and charges the failed work.

Training uses forty depth/cluster development parents: initial and three-
attempt ordinary-LM states. Rotation and all real BAL families are excluded.
Both snapshot types rebuild their decision cache at the registered lambda=0.1;
they do not preserve the preceding trajectory's adaptive damping/history.
They are controlled parent-state probes, not complete native solver checkpoints.
Features are available before choosing the extra action and include the
already evaluated ordinary trial's defect/depth risk, rho, residual-energy
concentration, gradient split and point conditioning. They are charged.

A depth-two cost-sensitive tree is compared with fixed schedules and a small
deterministic rule. Labels use clamped log-reference-gap decrease per measured
elapsed time. The local oracle knows replayed outcomes and is an upper bound
on that local utility, **not** on full convergence speed. References/targets
are not deployment features.

### Findings

On new depth/cluster seeds the tree obtains 97.1%/98.3% of local oracle utility.
On the unseen rotation family it gets 88.4%, below the deterministic rule's
94.7% and fixed OCA's 96.2%.

| Held-out cohort | Tree speed vs ordinary | Fixed extra damping speed vs ordinary |
|---|---:|---:|
| Depth, new seeds | 0.980x | 0.868x |
| Cluster, new seeds | 0.885x | 1.112x |
| Rotation, new family | 0.861x | 1.152x |
| Ladybug49 original sample | 1.048x | 1.339x |
| Dubrovnik88 original sample | 1.016x | 1.379x |
| Venice52 original sample | 0.968x | 1.553x |

Tree feature/inference costs are 8–12% on synthetic cases and approximately
5% on real samples. Its paired-seed speed intervals are 0.87–1.10x on depth,
0.87–0.99x on cluster, and 0.82–0.88x on rotation. All tree targets are hit.
It has one depth geometry failure versus ordinary's two, and none on the
other synthetic families. The fixed extra-damping arm has a rotation geometry
failure and a depth timing regression, so its three-real-sample result is
not a generally superior solver.

Always-coarse misses nine of thirty depth runs and has nine of ten depth
scenes fail geometry. Twenty-seven closed-loop coarse attempts have degenerate
automatic metrics. An initially uncaught instance aborted action replay;
the fix logs failure and uses the ordinary fallback without changing the
metric or dropping the parent. The abort log is retained, the policy is not
retuned, and an injected-failure test covers the fallback. [T8 evidence][t8]

### Feedback

Do not optimize action-classification accuracy alone. Fixed OCA captures
99.1% of the local cluster oracle but runs at 0.993x ordinary speed; fixed
extra damping captures 89.5% locally and runs at 1.112x. Local progress and
full-run value rank actions differently.

The tree sometimes beats the particular hand-written rule, but that rule is
itself weak. Ordinary LM and the best relevant fixed action remain necessary
controls. A small policy's apparent advantage over an expensive heuristic is
not sufficient evidence of useful learning.

Before RL, use longer returns and later/deeper-state coverage, then test
complete family-held-out trajectories with charged hardware-specific costs.
This CPU direct-solve dataset does not establish a deployment policy for GPU
deep-CG states. Sequential RL, a native hardware policy, and proof that learned
long-horizon allocation beats a strong scheduler remain **untested**.

## 11. Coverage audit: what should not be claimed as completed

The original brief uses gates to prevent indiscriminate expansion. The following
distinctions matter when revising it or describing our work:

| Requested direction | Completed | Deferred or limited |
|---|---|---|
| T1 | Native diagnostics, exact decomposition, prospective-feature screen, penalty assembly checks | No validated penalty controller, inverse-depth solver comparison, or native speed intervention |
| T2 | Analytic order-two curve, safeguards, direct geodesic baseline, five closed-loop arms | No separate equal-deadline snapshot oracle; no native derivative implementation |
| T3 | Pre/post/selective point polishing, winner changes, stationarity and whole-state checks | Thirty-step point reference is not a global optimum; no optimized sparse GPU point kernel |
| T4 | Known/automatic partitions, larger controlled problems, geometry audit, two real sample screens, exact bridge-only optimization | No full original BAL/native GPU speed comparison; late correction and large weakly connected real recovery untested |
| T5 | Known-cluster correct/mixed/false/disconnected counterexamples, final robust objective | No automatic-cluster or native robust continuation study |
| T6 | Bounded depth/isotropic quadrature, two radii, two parallax settings, multistart and common terminal refinement | No adaptive radius controller or native implementation |
| T7 | Exact filter/whitening tests, approximate/exact distance audit, held-out menu outcomes, simple-grid controls | No successful pruning controller, new filter shapes, or matched native five-shift ablation |
| T8 | Measured action replays, local oracle, fixed/rule/tree controls and complete held-out solves | No sequential RL or native deep-CG policy; limited parent-state coverage |

The aggregate verdict is a set of supported identities/mechanisms and failed
implementation gates, not a mathematical refutation of all eight research
directions. Conditional omissions must remain visible in any publication.

## 12. Prior-art feedback and novelty boundary

The closest methods were inspected in the prior research pass. The [source
ledger][sources] records the relevant sections and versions. The essential
positioning points for the suggesting agent are:

| Source | Consequence |
|---|---|
| [Parallax BA](https://arxiv.org/html/1807.03556) | Its ray-direction objective differs from the pixel-loss comparator. |
| [Square Root BA](https://arxiv.org/html/2103.01843) | Numerical elimination/stability and nonlinear path error are separate questions. |
| [Geodesic acceleration](https://arxiv.org/html/1207.4999) and [RNC-LM](https://arxiv.org/html/2607.07623) | Curved updates and repeated RHSs using a fixed LM matrix are established ingredients. |
| [Ceres inner iterations](https://raw.githubusercontent.com/ceres-solver/ceres-solver/master/docs/source/nnls_solving.rst) and [PoVar](https://arxiv.org/html/2405.05079) | Post-only polishing is a necessary control; projective/object-space elimination is a different formulation. |
| [Multigrid BA](https://arxiv.org/html/2007.01941), [Ni et al. submap BA](https://dellaert.github.io/files/Ni07iccv.pdf), [FAS-RASPEN](https://arxiv.org/html/1605.04419) | Collective bases, local frames and nonlinear coarse correction already have close precedents. |
| [Graduated filter methods](https://arxiv.org/html/2003.09080) | Adaptive continuation is established; incremental geometric information must earn its cost. |
| [ProBA](https://arxiv.org/html/2505.20858) | Probabilistic landmarks are not new here, and a changed likelihood is not an identical-objective baseline. |
| [OCA](https://arxiv.org/html/2411.06343) and [PowerBA](https://arxiv.org/pdf/2204.12834) | A geometric-series derivation is not novelty; response filtering and fixed-Schur inverse expansion must be distinguished. |
| [A Game of Bundle Adjustment](https://arxiv.org/html/2308.13270) | Learned damping already exists; its reward includes elapsed iteration time and a terminal bonus. Do not describe it as merely rewarding fewer iterations. |

No result here establishes priority, a new convergence theorem, or the fastest
BA solver. The most plausible future contribution is a justified nonlinear
coarse-space construction and schedule that predicts, and demonstrably saves,
fine-solver work on real problems under matched objectives and budgets.

## 13. Recommended revision to the research agenda

1. **Keep T4 as the primary branch, but change the deployment hypothesis.**
   Study when internal regions are sufficiently optimized for relative motion
   to dominate. A late correction is a hypothesis, not an established fix.
   Define a measurable trigger, a new held-out cohort, and deeper secondary
   targets before running it. Retain ordinary and linear-coarse controls.
2. **Reuse the exact bridge-only implementation as the starting component.**
   It preserves the nonlinear result and reduces coarse work, with full-cost
   verification. Next optimize or amortize partition/setup only if the
   correction actually saves fine iterations; otherwise faster setup cannot
   establish the claimed geometric benefit.
3. **Redesign T1's predictive cohort and gate.** An AUC ceiling leaves no
   room to test incremental value. Use a separately selected difficult regime
   and a decision metric tied to saved work, with residual-accuracy strata.
4. **Retain cheap/simple competitors throughout.** Post-only point polishing,
   one extra damping candidate, a smaller fixed menu and ordinary relinearizing
   LM are substantive controls, not secondary implementation details.
5. **Require correctness evidence before preserving robust bridges.** A
   connected/informative wrong reconstruction is a mandatory counterexample.
6. **Treat depth smoothing as a geometry/initialization question unless its
   evaluation cost changes materially.** The current speed gate fails, even
   when final geometry improves modestly.
7. **For spectral pruning, identify which approximation fails first.** Use
   the saved exact steps/spectra to separate spectral-estimation error from
   nonlinear cost sensitivity before buying more Lanczos work or new filters.
8. **For learning, establish long-horizon value before increasing model size.**
   Train and evaluate against a strong deterministic/fixed-action baseline,
   include later states, preserve scene-family separation and charge feature
   acquisition on the intended hardware.

Do not broaden into full large-BAL/GPU evaluation merely because the synthetic
T4 gain is large. The two real screens identify the current missing requirement:
**a coarse correction must replace expensive useful computation, rather than
precede the same fine solve with an additional cost decrease.**

## 14. Reproducibility, validation, and handoff contents

### Preserved implementations and configurations

The original GPU source and 44-header manifest verify unchanged. The retained
Eta2 binary SHA256 is
`1e3d2cf22a8a43075114e0ca2024923dad330461e35d0074938d0412cd77ecc0`.
Its exact CLI/environment flags are in [registration.json][registration] and
the [frozen champion package][champion]. The native route uses one shift,
classical LM and PCG; the eta2 label is not an RL-policy claim.

The geometry agenda has nine algebra/candidate-safety checks, including
derivatives, Schur/reference equivalence, immutable parents, gauge constraints,
robust/smoothing derivatives, spectral recursion and action fallback. They
pass. The three native archives and every member hash were verified. The
saved-real reproduction exactly matches all 27 original endpoints. The
collective BAL follow-up validates all nine frozen inputs and 135 unique
result rows, exact target matching, full-cost verification and reduced/full
coarse endpoint agreement.

The entire agenda was committed before experiments. Individual protocol
files were written before their corresponding runs, but some were committed
later in batches. This is internal registration, not an external timestamped
preregistration. The T8 exception/fallback correction is disclosed, with the
aborted log retained. Post-result diagnostics are labeled and do not replace
the original timing rows.

### Fetch and read

```bash
git fetch origin research/nonlinear-collective-bal
git switch --detach 78fc32e8f33f54eaf46b5298032ef7ce46d75620
```

Use an independent checkout for new runs; several research scripts write
their named result files. The two implementation directories are:

```text
research/geometry_agenda/    # T1–T8, protocols, checks, raw data, figures
research/collective_bal/     # broader T4 BAL screen and bridge-only solver
```

The full [reproduction guide][reproduce] gives commands, dependency versions,
native-path requirements, seeds and targets. CPU runs use
`OPENBLAS_NUM_THREADS=1` and `OMP_NUM_THREADS=1`. SciPy is isolated in the
package's ignored `build/python` directory. Native builds record compiler
arguments and source/binary hashes; a rebuild must not be called byte-identical
without checking it.

Synthetic generators and packed real samples allow the CPU experiments to
run without the large original BAL files. Regenerating the native-derived
samples requires `/workspace/bal` and the restored T1 capture archive layout.
Do not regenerate references when the intention is to repeat the already
frozen-target comparison.

### Evidence index

- [Eight-track overview][overview], [original brief][brief], and [source ledger][sources].
- [T1 report][t1], [T2][t2], [T3][t3], [T4][t4], [T5][t5], [T6][t6], [T7][t7], [T8][t8].
- [Seven original convergence figures and plotted CSV][figures].
- [Broader BAL report][bal], [summary][balsummary], [all raw rows][balraw], [nine-panel convergence figure][balfig].
- [Native archive/member manifest][nativearchives], [geometry-package inventory][inventory], [validation][validation].
- [BAL package inventory][balinventory] and [validation][balvalidation].
- `t*_*.json` in the geometry package contains full timings, candidates, fixed
  targets and failures; `evidence/*.npz` contains independent parents and
  sampled inputs. The original reports explain their schemas and scope.

**Requested feedback from the suggesting agent:** assess whether late
collective correction has a discriminating, inexpensive trigger; propose the
smallest next experiment that could reject that revised hypothesis; and flag
any closer prior art or comparison-contract flaw before expanding native work.
Do not treat this handoff as evidence that T4 already wins on full BAL or that
all eight conceptual directions have been disproved.

[brief]: https://github.com/msouiai/prism-ba/blob/e121e914b79aa3b632f76c402f50a6aac8969344/research/geometry_agenda/brief.tex
[overview]: https://github.com/msouiai/prism-ba/blob/e121e914b79aa3b632f76c402f50a6aac8969344/research/geometry_agenda/README.md
[t1]: https://github.com/msouiai/prism-ba/blob/e121e914b79aa3b632f76c402f50a6aac8969344/research/geometry_agenda/T1_RESULTS.md
[t2]: https://github.com/msouiai/prism-ba/blob/e121e914b79aa3b632f76c402f50a6aac8969344/research/geometry_agenda/T2_RESULTS.md
[t3]: https://github.com/msouiai/prism-ba/blob/e121e914b79aa3b632f76c402f50a6aac8969344/research/geometry_agenda/T3_RESULTS.md
[t4]: https://github.com/msouiai/prism-ba/blob/e121e914b79aa3b632f76c402f50a6aac8969344/research/geometry_agenda/T4_RESULTS.md
[t4math]: https://github.com/msouiai/prism-ba/blob/e121e914b79aa3b632f76c402f50a6aac8969344/research/geometry_agenda/T4_MATH.md
[t5]: https://github.com/msouiai/prism-ba/blob/e121e914b79aa3b632f76c402f50a6aac8969344/research/geometry_agenda/T5_RESULTS.md
[t6]: https://github.com/msouiai/prism-ba/blob/e121e914b79aa3b632f76c402f50a6aac8969344/research/geometry_agenda/T6_RESULTS.md
[t7]: https://github.com/msouiai/prism-ba/blob/e121e914b79aa3b632f76c402f50a6aac8969344/research/geometry_agenda/T7_RESULTS.md
[t8]: https://github.com/msouiai/prism-ba/blob/e121e914b79aa3b632f76c402f50a6aac8969344/research/geometry_agenda/T8_RESULTS.md
[sources]: https://github.com/msouiai/prism-ba/blob/e121e914b79aa3b632f76c402f50a6aac8969344/research/geometry_agenda/SOURCES.md
[figures]: https://github.com/msouiai/prism-ba/blob/e121e914b79aa3b632f76c402f50a6aac8969344/research/geometry_agenda/figures/convergence/README.md
[registration]: https://github.com/msouiai/prism-ba/blob/e121e914b79aa3b632f76c402f50a6aac8969344/research/geometry_agenda/registration.json
[champion]: https://github.com/msouiai/prism-ba/tree/e121e914b79aa3b632f76c402f50a6aac8969344/research/eta2_champion
[reproduce]: https://github.com/msouiai/prism-ba/blob/e121e914b79aa3b632f76c402f50a6aac8969344/research/geometry_agenda/REPRODUCE.md
[nativearchives]: https://github.com/msouiai/prism-ba/blob/e121e914b79aa3b632f76c402f50a6aac8969344/research/geometry_agenda/evidence/manifest.json
[inventory]: https://github.com/msouiai/prism-ba/blob/e121e914b79aa3b632f76c402f50a6aac8969344/research/geometry_agenda/artifact_manifest.json
[validation]: https://github.com/msouiai/prism-ba/blob/e121e914b79aa3b632f76c402f50a6aac8969344/research/geometry_agenda/validation.json
[bal]: https://github.com/msouiai/prism-ba/blob/78fc32e8f33f54eaf46b5298032ef7ce46d75620/research/collective_bal/README.md
[balsummary]: https://github.com/msouiai/prism-ba/blob/78fc32e8f33f54eaf46b5298032ef7ce46d75620/research/collective_bal/summary.json
[balraw]: https://github.com/msouiai/prism-ba/blob/78fc32e8f33f54eaf46b5298032ef7ce46d75620/research/collective_bal/results.json
[balfig]: https://github.com/msouiai/prism-ba/blob/78fc32e8f33f54eaf46b5298032ef7ce46d75620/research/collective_bal/figures/convergence/all_camera_bal.png
[balinventory]: https://github.com/msouiai/prism-ba/blob/78fc32e8f33f54eaf46b5298032ef7ce46d75620/research/collective_bal/artifact_manifest.json
[balvalidation]: https://github.com/msouiai/prism-ba/blob/78fc32e8f33f54eaf46b5298032ef7ce46d75620/research/collective_bal/validation.json
