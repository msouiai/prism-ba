# Ultra-effort Astra research: joint paths, perspective stiffness, Schur stopping

**Verdict: retain Eta2.** A fresh GPT-6 Astra adviser ran at the highest available
reasoning effort, **ultra**, using the user's requested prompt. Its three new
hypotheses were implemented and tested under registered gates. None justified
promotion or a fastest-solver/novelty claim.

There is a useful new mechanism result: a finite joint virtual-ray update is
**1.315× faster than ordinary XYZ BA on four low-parallax synthetic cases**,
reducing median accepted iterations 29→17.5 and rejects 3→0. But conventional
observed-pixel point polishing is 1.424× faster on those same cases and gives
better median geometry. The virtual-ray method also regresses on joint-pose
initializations. This is a bounded positive result with a stronger established
control, not a new champion.

Branch `research/astra-ultra-ba` starts from
`d988b59a3b63a488ffd95c6ab3cc1cd672e2aa6e`. Original Eta2, native solver sources,
and every preceding research implementation remain unchanged. **No new GPU
benchmark or Caspar comparison was run in this round.**

## Adviser and test contract

- [Requested prompt/model/effort](USER_REQUEST.md).
- [Full prospective research brief](advice/RESEARCH_DIRECTIONS.md): derivations,
  primary sources, controls and stop rules.
- [Independent post-screen review](advice/POST_SCREEN_FEEDBACK.md).
- [Frozen shared test contract](TEST_CONTRACT.md), [inputs/references](cases.json),
  [machine-readable decisions](decisions.json).

The three proposals deliberately address different parts of BA: the finite
camera/point path; the tangent-system curvature; and the amount of work spent
solving the Schur system. They do not repeat the previous late-coarse-insertion
or retained-basis experiments.

New synthetic problems use eight cameras on an orbit looking toward the scene,
120 points, five views per point and 0.2 px observation noise. Four seeds are
tested in depth-error, joint-pose-error and low-parallax families. Depth and
joint families share the generating geometry/observations for a given seed,
but have different initialization errors; these are paired stress cases, not
twelve unrelated datasets. Low parallax reduces the orbit baseline. Camera
orientations vary across views, addressing a limitation of the previous round.

References were frozen before candidates by bounded ordinary LM from generating
truth. The primary target is **1.01× the feasible reference cost**, independent
of initialization-error magnitude. It is not a certified global optimum.
Secondary 1.001× targets were frozen but not run after primary gates failed.
All arms preserve original pixel L2, fixed intrinsics, camera0 pose/point0.z
gauge and full signed-depth checks. CPU timing is serialized with one BLAS and
OpenMP thread. N=3 repeats measure timing, not three independent reconstructions.

The three previously used packed 24-camera/300-point BAL samples are retained
only for U3 frozen-system diagnostics. They are development evidence, not new
held-out scenes or full-BAL convergence runs.

## U1 — intersect rays for the model's predicted pixels

Protocol: [ray_protocol.md](ray_protocol.md). Implementation:
[joint_paths.py](joint_paths.py), [path_solver.py](path_solver.py).

Ordinary LM supplies camera and point tangents. Keep its actual finite camera
trial. For each observation form the parent normalized prediction u and its
linear change du, then a **virtual target u+alpha du**. These targets are not
the measured pixels. At the trial camera, intersect the virtual rays with one
3×3 solve per point, regularized toward the original linear point endpoint
using the current lambda and original point damping metric.

The centered local system is

    (sum A'A + lambda Dp) correction = sum A'(b - A Xlinear),
    Xtrial = Xlinear + correction.

Because the original linear point endpoint satisfies the moving virtual rays
to first order, the correction is O(alpha²): the same physical LM tangent is
preserved. The rays need not intersect exactly. This is a weighted algebraic
fit, not exact minimization of pixel error or an exact residual geodesic.

Controls are ordinary XYZ; the old fixed-world-host radial inverse-depth path;
a radial inverse-depth path carried with its actual moving host camera; and
one safeguarded GN polishing step targeting **observed** pixels. The last
control is intentionally not tangent matched, so its prediction uses its
actual physical point displacement. All of its local line-search/evaluation
cost is included. Point0 stays XYZ in both new retractions.

**180 complete CPU runs:** 12 cases × 5 arms × N=3, with identical 160-attempt/3-second caps.
Every run reached its primary target. No projective fallback was triggered in
these benchmark trajectories.

| Family | Old anchored | Moving host | Virtual rays | Observed-pixel polish |
|---|---:|---:|---:|---:|
| Depth error |1.136×|1.123×|1.017×|0.852×|
| Joint pose error |0.960×|0.950×|0.798×|0.666×|
| Low parallax |1.055×|1.063×|**1.315×**|**1.424×**|

Each entry is the median of per-case ratios of N=3 median times against XYZ.
Ratios of pooled medians need not match these numbers. The old anchored path
wins the depth cohort; XYZ wins joint pose; observed polishing wins low
parallax. No proposed path wins across two families under the registered gate.

Low-parallax accepted/rejected medians:

| Method | Accepted | Rejected | Point NRMSE | Camera NRMSE |
|---|---:|---:|---:|---:|
| XYZ |29|3|0.114|0.449|
| Old anchored |27.5|3|0.116|0.436|
| Moving host |26.5|2|0.077|0.142|
| Virtual rays |17.5|0|0.085|0.233|
| Observed polishing |13.5|0.5|0.075|0.136|

Geometry uses one global similarity shared by cameras and points. The low
baseline remains weakly constrained: even the truth-started reference has
median camera NRMSE 0.274. Thus tight equal pixel costs still do not imply equal
or accurate geometry. Neither new retraction introduces a registered severe
geometry regression relative to XYZ, but this is not a successful-reconstruction
claim for every case.

### Did the joint model actually improve?

A separate frozen-parent audit at k=0,2,4 evaluates 432 candidates across
joint/point-only motion and six paths, including an undamped virtual-ray oracle
used only diagnostically. No new path coefficient was fitted to those results.

| Family | XYZ joint relative defect | Virtual-ray joint defect | Fraction of XYZ defect in the local point subspace |
|---|---:|---:|---:|
| Depth |0.135|0.068|0.909|
| Joint pose |0.059|0.047|0.327|
| Low parallax |0.127|0.086|0.849|

These are medians across 12 parents per family. The final column projects the
defect onto a linear point-correction subspace at the actual trial cameras;
it is not a bound on all finite point corrections. Joint-pose defects are
mostly outside that local point subspace, helping explain why more point work
does not save fine iterations there.

Observed polishing has a *larger* defect relative to the original solved-tangent
prediction in low parallax, yet converges faster. It optimizes measured pixels,
not fidelity to that prediction. Better model agreement alone is therefore
not the relevant performance objective.

**Decision:** stop full-run expansion. The new map has a measurable narrow
mechanism benefit, but its closest practical control is stronger. No BAL
transfer, held-out-seed expansion or native port is warranted by this gate.

Evidence: [path_results.json](path_results.json), [path_summary.json](path_summary.json),
[ray_checks.json](ray_checks.json), [ray_diagnostics.json](ray_diagnostics.json),
and 60 saved endpoints in `evidence/path-*.npz`.

## U2 — perspective curvature as residual-dependent stiffness

Protocol: [stiffness_protocol.md](stiffness_protocol.md). Implementation:
[stiffness.py](stiffness.py).

The mechanics analogy is that a residual acts like existing stress, so changing
its force direction introduces geometric stiffness beyond GN. It is an analogy,
not a physical spring model for camera measurements.

For a pinhole observation with a=Jq'r, e=[0,0,1] and signed depth z, the missing
projection curvature is exactly

    Kq = -(a e' + e a') / z.

It has rank at most 2. Its positive part is rank 1 and can be factored analytically
into one zero-residual observation row. This gives a positive step penalty
without changing gradient, original GN damping or observation incidence. The
original GN prediction and controller remain unchanged; the augmented prediction
is only diagnostic.

Perspective is not the entire residual Hessian. The exact additional pose term
contains omega×(omega×RX)+2omega×R dX. We verified its signed contraction plus
the perspective term against the existing analytic residual second derivative
and finite differences. Dense eigendecomposition also confirmed the analytic
positive factor. Trace matching to a scalar fractional-depth penalty uses the
same gauge-masked D-whitened coordinates.

**36 frozen ordinary parents** were screened. The gate required at least 4
parents across 2 families with positive missing curvature at least as large as
GN curvature, and a median perspective contribution of at least50%.

Only **2 parents qualified**, both initial depth-error cases. Their missing/GN
ratios were 1.056 and 1.022; perspective supplied 97.5% and 99.3% of that missing
curvature. The source is identifiable in those two states, but the intended
multi-family severe-stiffness cohort was absent.

One stiffness step and one trace-matched depth-penalty step were still computed
at every parent to validate the implementation: 72 augmented proposals, with
gradient and original damping checked unchanged. On the two qualifying states,
stiffness beats the depth control once and loses once. This is not runtime or
full-convergence evidence.

**Decision:** mechanism gate failed; no full stiffness trajectories or extra
damping-menu sweep. This does not establish that native terminal stalls lack
residual curvature: those states, radial terms and variable intrinsics were not
tested here.

Evidence: [stiffness_diagnostic.json](stiffness_diagnostic.json).

## U3 — credit the model decrease already bought by point elimination

Protocol: [energy_protocol.md](energy_protocol.md). Implementation:
[energy_diagnostic.py](energy_diagnostic.py).

Exact point back-substitution contributes a constant decrease
P0=0.5 gp'C^-1gp. At camera iterate x, the achieved full damped-model decrease is

    P = P0 + b'x - 0.5 x'Sx.

Its missing decrease is epsilon=0.5 r'S^-1r. Including P0 may therefore permit
less camera work for the same fraction of full predicted improvement.
The exact epsilon is an expensive diagnostic oracle. The cheap bound
U=0.5 r'(lambda Dc)^-1r follows from S>=lambda Dc for the actual damped GN
blocks and gauge. Stopping at U<=0.1P guarantees at least 90.9% of optimal
*damped-quadratic* decrease in exact arithmetic, not nonlinear progress.

We tested 45 frozen systems: three ordinary parents from each synthetic/BAL
sample. All rules share the same block-camera PCG trajectory, initial iterate,
and exact point back-substitution. The full-model identity agrees with physical
camera/point evaluation to maximum relative error 1.91e-14, with no recorded
upper-bound violation. Fresh residuals validate every prospective exit.

Controls are eta 0.5/0.8, the established Nash relative camera-quadratic progress
criterion, and exact/cheap energy rules with and without P0. The Nash formula
was checked against the [Ceres CG source](https://github.com/ceres-solver/ceres-solver/blob/master/internal/ceres/conjugate_gradients_solver.h),
using fixed tolerance 0.1. All 315 selected exits occurred before iteration 10 and
used one fresh exit-check product, so charged products are k+1. Per-iterate
oracle instrumentation is separate and cannot be advertised as free.

| Stopping rule | Total products over 45 parents | Median products | Qualifying local opportunities |
|---|---:|---:|---:|
| Residual eta 0.5 |114|2|baseline|
| Residual eta 0.8 |96|2|7|
| Nash camera progress |191|4|0|
| Exact-energy oracle, full credit |114|2|8|
| Exact-energy oracle, camera only |125|3|3|
| Cheap bound, full credit |175|4|2|
| Cheap bound, camera only |201|4|0|

An opportunity means at least 20% fewer charged products than eta 0.5 while
retaining at least 90% of its positive actual cost decrease. No arm introduced
an invalid proposal where the ordinary proposal was valid. The exact-energy
rows exclude their oracle factor/solve overhead and are **not deployable speed
comparisons**. Even the full-credit oracle has no aggregate product saving over
eta 0.5 across the entire cohort despite eight favorable local cases.

Including P0 changes 11 oracle and 19 cheap-bound stopping indices: the mathematical
offset has a measurable effect. But the cheap full-credit rule meets the local
gate on only 2 parents, below the required 4. Its two favorable exits are exactly
the same k=1steps already selected by eta 0.8. The practical issue is the
conservatism of the error bound, not a missing accounting identity.

**Decision:** stop at this estimator gap. No extra Krylov estimator, bound
tuning, complete PCG trajectories or native replay was used to rescue it.
Eta0.8's local savings also do not establish faster nonlinear convergence;
that would require its own common-target trajectory comparison.

Evidence: [energy_results.json](energy_results.json), [energy_summary.json](energy_summary.json).

## Prior art, novelty and what remains useful

The [advisory brief](advice/RESEARCH_DIRECTIONS.md) gives fuller source context.
Moving-anchor inverse-depth BA is explicit in
[Strasdat's thesis, Appendix B.5](https://www.doc.ic.ac.uk/~ajd/Publications/strasdat_phd2012.pdf)
and the [g2o implementation](https://github.com/RainerKuemmerle/g2o/blob/master/g2o/types/sba/edge_project_psi2uv.cpp).
Finite projection/retraction and geodesic corrections also have established
ancestry; the new virtual target rule has not demonstrated superiority over
observed-point polishing.

Projected-Hessian methods are established in mechanics, and
[Pitfalls of Projection](https://arxiv.org/html/2311.14526) documents reasons that
unconditional Hessian projection can be harmful. The rank-one BA factor here is
an exact local construction, not proof of a new useful Newton solver.

Inexact Schur solves and quadratic stopping are established, including
[Bundle Adjustment in the Large](https://homes.cs.washington.edu/~sagarwal/bal.pdf).
The contribution tested here was specifically the point-condensation offset,
not generic energy-based stopping. A broad claim of geometry-aware updates
preserving pixel loss is also insufficient given adjacent work such as
[CSS-BA](https://arxiv.org/html/2607.15652).

The best retained result is explanatory: a same-tangent finite map can reduce
joint model defect and save iterations in low parallax, yet direct optimization
of measured pixels can be faster while departing farther from the original
prediction. Likewise, exact quadratic-credit accounting can change stopping
indices without a useful inexpensive error certificate. These delimit future
hypotheses; none supports a general fastest-BA or publication-priority claim.

## Reproduction and preservation

Use the preceding pinned CPU reference environment; setup details are in
`research/geometry_agenda/README.md`. Run in a fresh checkout to retain archived
JSON measurements: drivers replace their named local outputs. No new dataset
downloads are needed. All old solver/research source hashes are protected by
the validation script.

```bash
OPENBLAS_NUM_THREADS=1 python3 research/astra_ultra/prepare_cases.py
OPENBLAS_NUM_THREADS=1 python3 research/astra_ultra/check_joint_paths.py
OPENBLAS_NUM_THREADS=1 python3 research/astra_ultra/run_paths.py
OPENBLAS_NUM_THREADS=1 python3 research/astra_ultra/ray_diagnostics.py
OPENBLAS_NUM_THREADS=1 python3 research/astra_ultra/run_stiffness_diagnostic.py
OPENBLAS_NUM_THREADS=1 python3 research/astra_ultra/energy_diagnostic.py
OPENBLAS_NUM_THREADS=1 python3 research/astra_ultra/summarize_gates.py
OPENBLAS_NUM_THREADS=1 python3 research/astra_ultra/plot_results.py
OPENBLAS_NUM_THREADS=1 python3 research/astra_ultra/validate_results.py
```

The package includes source, registered contracts, frozen cases, references,
raw traces, endpoints, advisory notes, figures, validation and a SHA256 inventory.
No original algorithm was overwritten or merged onto master.
