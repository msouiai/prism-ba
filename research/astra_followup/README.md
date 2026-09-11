# Astra-guided bundle-adjustment experiments

**Verdict: retain the frozen Eta2 champion.** The requested GPT-6 Astra agent,
at high reasoning effort, proposed three bounded directions. We implemented
and tested each. None earned promotion or a new solver-novelty claim.

The one measured speed benefit was a projective point path on moderate-parallax
depth-error cases: **1.16–1.18× versus ordinary XYZ updates**. Established
anchored inverse depth matches the proposed multi-view rule, and the benefit
does not transfer to the intended low-parallax cohort. This is useful mechanism
evidence, not a new fastest-BA result.

Work is isolated on `research/astra-guided-ba`, based on
`78fc32e8f33f54eaf46b5298032ef7ce46d75620`. Original solver files and the frozen
Eta2 configuration were not edited. These experiments do not update the
Caspar comparison ledger.

## What Astra suggested

The full [advisory brief](advice/RESEARCH_DIRECTIONS.md) includes mathematical
constructions, primary sources, stop rules and copyable research prompts.
[USER_REQUEST.md](USER_REQUEST.md) preserves the requested prompt/model/effort.

1. **Late nonlinear collective correction:** after ordinary BA reduces local
   error, insert one or two coordinated Sim3 corrections between regions. First
   test whether an insertion-time oracle can save subsequent fine work; only
   then build a progress-per-second trigger.
2. **Projective point retraction:** keep the existing tangent solve but change
   its finite path to cancel shared perspective-depth curvature, using the
   original pixel objective and damping metric.
3. **Residual-informed Schur enrichment:** choose retained modes by their
   current projected error energy in the preconditioner metric, rather than
   simply retaining the smallest Euclidean eigenvalues.

A fourth preliminary idea, consistency-aware robust bridge continuation, was
deferred. The current experiment has no independent correspondence evidence
that would distinguish useful weak bridges from geometrically consistent false
bridges. Repeating the earlier observability-only controller would not answer
that identifiability problem.

The adviser subsequently performed an independent read-only review of the
implementation and outcomes; see [POST_SCREEN_FEEDBACK.md](advice/POST_SCREEN_FEEDBACK.md).
It found no correctness defect requiring a rerun and recommended closing all
three promotion branches under their registered gates.

## A1 — late collective correction

Protocol: [late_protocol.md](late_protocol.md). Ordinary LM checkpoints preserve
geometry, the next lambda, counters and gauge at accepted steps2/4/8. Resume
after one/two nonlinear bridge-only coarse iterations, matched linear coarse
iterations, or no intervention. All partition construction, trial evaluations,
full-objective verification and downstream fine work are charged. Nonlinear and
linear arms share the existing coarse diagonal damping; it is not advertised
as the inherited full fine metric P'DP.

We reused one packed24-camera/300-point sample from each of Ladybug49,
Dubrovnik88 and Venice52. These are previously inspected development problems,
not independent held-out scene families. Both targets use the existing feasible
reference: F_target=F_ref+tau(F_initial-F_ref), tau=1e-3 and1e-5. F_ref is not
claimed to be the global optimum.

There are **216 interventions and54 continuation controls**, N=3, plus six
baseline trajectories. Every intervention reduced the coarse-stage cost.
Every resumed run reached its target. **None saved even one fine accepted
step**, and every resumed tail had zero rejected fine attempts.

| BAL sample | Best nonlinear speedup, tau1e-3 | Best nonlinear speedup, tau1e-5 | Fine steps saved |
|---|---:|---:|---:|
| Ladybug49 |0.919×|0.962×|0|
| Dubrovnik88 |0.888×|0.941×|0|
| Venice52 |0.915×|0.925×|0|

These are deliberately optimistic, **hindsight best** insertion/budget choices
per scene and target. Times are **composed full times**: one common measured
ordinary prefix plus each independently timed intervention/continuation tail.
They are not three uninterrupted full-run timings. The underlying ordinary
accepted counts were13/26,9/21 and12/14 at the two targets respectively.

No-op resumption was subsequently checked for exact equality of all endpoint
arrays and lambda, not just equal cost. Two known-partition weak-cluster
positive controls confirmed that the bridge solver does reduce cost and improve
geometry while preserving its parent. Those are correctness controls, not
positive real-BAL speed evidence.

**Decision:** stop this schedule family before learning a trigger. A lower
immediate cost did not replace useful fine work. This does not refute all
nonlinear multilevel methods or all possible partitions.

Evidence: [late_oracle.json](late_oracle.json), [late_summary.json](late_summary.json),
[late_checks.json](late_checks.json), checkpoint NPZs in `evidence/`.

## A2 — change the point path, preserve the tangent

Protocol: [chart_protocol.md](chart_protocol.md). Implementation:
[projective_paths.py](projective_paths.py).

For the ordinary physical point tangent dX, use

    X_trial = X + alpha*dX / (1-alpha*h).

The anchored control chooses h=(X-C_anchor)'dX/||X-C_anchor||². Astra's candidate
chooses h=mean_i(R_i[2,:]/z_i)'dX over the point's observing cameras. Camera
retraction, the Euclidean linear solve, damping, prediction and acceptance
controller remain the same. A projective denominator below0.25 falls back to
XYZ per point; point0 always keeps its Euclidean path to preserve its fixed z.
Every trial uses the full unchanged pixel cost and observed-depth checks.

For fixed cameras and pinhole projection, gamma_i=R_i[2,:]dX/z_i gives the exact
pixel-displacement denominator1+alpha(gamma_i-h). Choosing the mean cancels the
common depth component. The identity does not cover simultaneous pose motion
or radial distortion. No extra linear solve or always-on alternate trial is
introduced.

Tests: ten new seeds per family, six cameras/80 points, N=3, **270 runs** total.
Low-parallax and moderate-parallax cases differ by camera-baseline multiplier
0.08 versus1. A rotation-error family is the negative control. Fixed targets
are F_truth+1e-4(F_initial-F_truth), frozen before arm comparisons. Each run has
the same80-attempt/2-second cap. All feature construction is included in time.

| Family | XYZ accepted/rejected, median | Anchored speedup vs XYZ | Mean-view speedup vs XYZ | Mean-view vs anchored |
|---|---:|---:|---:|---:|
| Low parallax, depth error |12/0|0.966×|0.969×|1.003×|
| Moderate parallax, depth error |8/1|1.177×|1.164×|1.001×|
| Rotation error |5/0|0.970×|0.968×|1.002×|

Speedups are medians of per-seed ratios of N=3 median runtimes, not ratios of
pooled runtime medians. Moderate-parallax projective arms reduced median
accepted steps to5.5 and rejects to0. Every arm reached every cost target.
No near-pole fallback was needed in these benchmark runs; an explicit algebra
test exercised that safeguard separately.

**Cost hits were not geometry recovery.** Using one common global similarity,
the registered failure thresholds were point or camera NRMSE>0.2, or median
rotation error>5degrees. All30 low-parallax runs per arm failed both point and
camera thresholds. All30 moderate-parallax runs per arm failed the camera
threshold; none failed its point threshold. Rotation-family failures were24/30
for XYZ and18/30 for each projective arm. These thresholds do not hide the
continuous errors, which are retained in the raw data and summaries.
N=3 repeats measure timing at deterministic endpoints; each family contains
ten independent generated cases, not thirty independent geometry trials.

In the moderate family, median point NRMSE was0.113 XYZ,0.129 anchored and0.122
mean-view; camera NRMSE was0.506,0.604 and0.561 respectively. The cost target
can still be9.47 times the truth-reference cost there, and47.18 times it in the
rotation cohort. This is an early convergence/initialization screen, not a
terminal-quality study. Alignment correctness was independently checked on a
known global similarity.

**Why the point-only algebra does not yield a universal BA gain.** A post-screen
diagnostic used seeds200/205 at original and accepted-step2/4 states; it did
not tune a controller. Median relative linearization defects were:

| Family and motion | XYZ | Anchored | Mean-view |
|---|---:|---:|---:|
| Low-parallax, point-only |0.0720|0.00114|0.000583|
| Low-parallax, joint camera+point |0.0800|0.0922|0.0922|
| Moderate-parallax, point-only |0.330|0.0319|0.00670|
| Moderate-parallax, joint camera+point |0.333|0.0809|0.0801|

The mean-view path noticeably improves the isolated point model, yet camera
motion dominates the remaining joint defect and makes its full-run results
nearly identical to anchored inverse depth.

**Decision:** no promotion and no real/native expansion under the registered
low-parallax gate. The moderate speed effect supports an established point
parameterization, not novelty of the mean-view selector. Deeper targets,
different camera geometry or a joint-motion construction would be separately
registered experiments, not repairs to a successful general result.

Evidence: [chart_results.json](chart_results.json), [chart_summary.json](chart_summary.json),
[chart_targets.json](chart_targets.json), [chart_checks.json](chart_checks.json),
[chart_defects.json](chart_defects.json), `evidence/chart-*.npz` endpoints.

## A3 — spend Schur effort on modes carrying current error

Protocol: [schur_protocol.md](schur_protocol.md). Implementation:
[residual_fixed.cu](residual_fixed.cu), reusing the existing fixed-system harness,
frozen matrix-free kernels and balanced coarse inverse. Unlike A1/A2, this is
an **actual GPU fixed-system experiment**, on an RTX2000 Ada. It is not a full
nonlinear solver or Caspar race.

With retained history V, current S and the actual safeguarded preconditioner
M=L L', solve

    V'SV y = theta V'MV y; z=Vy; w=(z'b)^2/theta.

Select rank2/4 by largest current w, versus old previous-system Euclidean Ritz
selection and current generalized smallest-theta selection. Use the same
balanced inverse Q+(I-QS)M^-1(I-SQ). All arms start at zero with a fixed
preconditioner; there is no mid-recurrence change. A restart at this starting
point is the plain-PCG control itself.

For generalized selection the entire32-column history is refreshed. All32
Schur products, CPU eigensystems, transfers and current setup are charged.
The previous solve's last32 normalized directions are generated once per
repetition; its common acquisition cost is reported separately. In Muell that
previous solve reaches its128-iteration cap without satisfying its forcing
test. This preserves the earlier recycling-study history source rather than
selecting a favorable new history.

**Muell outer12, N=3, identical captured eta=0.5 and true-residual gate:**

| Arm | Setup+solve wall ms | PCG iterations | Total Schur products | Speedup vs plain |
|---|---:|---:|---:|---:|
| Plain PCG |131.8|41|42|1.000×|
| Old Euclidean rank2 |178.1|53|56|0.740×|
| Old Euclidean rank4 |184.4|53|58|0.715×|
| Current generalized theta rank2 |290.5|53|86|0.454×|
| Current generalized theta rank4 |273.9|53|86|0.481×|
| Current residual energy rank2 |273.0|53|86|0.483×|
| Current residual energy rank4 |260.8|49|82|0.505×|

Residual rank4 helps relative to other recycled arms, but even its **158.6ms
solve alone** exceeds plain PCG's131.6ms solve. Saving refresh overhead would
therefore not rescue this tested basis. True relative residuals were0.4973
plain and0.4946 energy-rank4, both meeting the same0.5 criterion.

Ladybug598 outer8 has only two prior PCG iterations; Final1936 outer0 has no
history. The >=16 prior-depth gate skipped enrichment in both. They retained
plain iteration/product counts and approximately unchanged runtimes. Across
three systems, seven arms and N=3, all **63 runs** passed the common residual
test. The deep-arm CUDA memcheck reported zero errors.

**Scope caveat from Astra's review:** V is reused in the previous study's
normalized coordinates. Preserving the same physical camera tangent across
new diagonal normalization would require V_current=diag(E_previous/E_current)
V_previous. That transport was not applied. Muell's ratio range is0.98555–1.01197;
Ladybug's larger change is irrelevant to this run because enrichment skips.
Current S, M, refreshed SZ and residual tests remain correct, so the benchmark
is valid preconditioning of the current system; it does not test every
physically transported history. [schur_coordinate_audit.json](schur_coordinate_audit.json)
records this distinction and verifies the transport identity algebraically.

**Decision:** close this basis/selection route at the fixed-system gate. Do not
interpret it as a general rejection of deflation or stronger BA preconditioners.

Evidence: [schur_results.json](schur_results.json), [schur_summary.json](schur_summary.json),
[schur_math_checks.json](schur_math_checks.json), [schur_inputs.json](schur_inputs.json),
build manifest and `evidence/schur-*.log`. Capture hashes are checked before use.
Sanitizer timings are diagnostics and excluded from performance summaries.

## Novelty and next research boundary

Submap/coarse refinement has close precedent in
[Ni, Steedly and Dellaert, ICCV2007](https://dellaert.github.io/files/Ni07iccv.pdf).
Inverse-depth modeling is established in
[Montiel, Civera and Davison, RSS2006](https://www.roboticsproceedings.org/rss02/p11.pdf).
Deflation already has explicit
[BA prior art, Das et al., WACV2021](https://openaccess.thecvf.com/content/WACV2021/papers/Das_A_Deflation_Based_Fast_and_Robust_Preconditioner_for_Bundle_Adjustment_WACV_2021_paper.pdf).
The advisory brief discusses those overlaps in more detail. Publication priority
for the precise mean-view rule has not been established, and the current
experiment supplies no incremental full-BA performance claim for it.

The most informative new direction is to understand **joint camera-point
curvature**: why removing the common depth denominator greatly improves the
point-only model while the coupled BA path retains most of its defect. A future
method needs to target that coupled error and beat anchored inverse depth at
equal pixel targets and meaningful geometry. That is a proposed next research
question, not an implemented or validated improvement.

## Reproduction and artifacts

Run from the repository root. The CPU reference uses the prior experiment's
isolated SciPy installation; see `research/geometry_agenda/README.md` for setup.
One BLAS/OpenMP thread and serial timing were used.

```bash
OPENBLAS_NUM_THREADS=1 python3 research/astra_followup/check_late.py
OPENBLAS_NUM_THREADS=1 python3 research/astra_followup/check_projective.py
OPENBLAS_NUM_THREADS=1 python3 research/astra_followup/check_schur.py
OPENBLAS_NUM_THREADS=1 python3 research/astra_followup/run_late_oracle.py
OPENBLAS_NUM_THREADS=1 python3 research/astra_followup/run_chart.py
OPENBLAS_NUM_THREADS=1 python3 research/astra_followup/chart_diagnostics.py
OPENBLAS_NUM_THREADS=1 python3 research/astra_followup/build_schur.py
OPENBLAS_NUM_THREADS=1 python3 research/astra_followup/run_schur.py
OPENBLAS_NUM_THREADS=1 python3 research/astra_followup/schur_coordinate_audit.py
OPENBLAS_NUM_THREADS=1 python3 research/astra_followup/plot_summary.py
OPENBLAS_NUM_THREADS=1 python3 research/astra_followup/validate_results.py
```

The GPU runner expects the existing `/workspace/prism-schur-physics` captures
listed in `schur_inputs.json`; this package deliberately does not duplicate
their large W arrays. Sources for original capture generation remain in
`research/schur_physics_control/`. It obtains `/tmp/prism_gpu.lock` before replay.
Build artifacts are ignored; raw summaries, compact endpoints, immutable
checkpoints, diagnostic logs, advice and a SHA256 artifact inventory are kept.
Rerunning drivers replaces their named local outputs, so use a fresh checkout
to retain the archived measurements unchanged.
