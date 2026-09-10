# Thirty steps: nonlinear error and pointwise rescue

Completed 2026-09-08. **The useful new result is a pointwise nonlinear safeguard, supported by fixed-state measurements but not yet an online speedup.** On three Dubrovnik captures, freezing just 1–3 problematic points allows a full-camera candidate with substantially more immediate reduction than global backtracking. A broader per-point scale menu improves all six captured states. The local two-variable curvature model itself failed its promotion gate.

[Mathematical derivations and exact separability bounds](local_curvature_math.md). Evidence root: `/workspace/prism-local-curvature/`. Five short instrumented BA runs took **18.640 seconds of native solver time**. They produced six failed-direction captures from three scenes. The fixed-state study contains 188 cached full-objective samples, plus derivative, Hessian-reference, mixed-step reconstruction and pointwise-menu evaluations. These offline CPU measurements are not GPU timing comparisons.

## What was frozen and measured

The initial scenes were Venice-52, Dubrovnik-356 and Ladybug-1197. Capture failed-direction calls 1, 8 and 16 where available during at most 40 iterations/8 seconds, using paired demand and the original backtracking controller with the existing subspace audit only. No new step is accepted by the capture feature. All state matrices and failed directions are retained exactly.

Fit radii `.5`, `.125` and `.03125` were declared before measurements; `.125` is primary. Local models use the full objective at camera-only, point-only and joint steps, together with the known gradient. Four interior validation points per radius are excluded from fitting. The first capture per scene is exploratory, while later captures test the same frozen formulas. There is only one Ladybug capture; no independence across captures from a shared trajectory is assumed.

The original comparison is the first full-objective Armijo success among the eight dyadic uniform steps. Every model proposal is evaluated on all observations. No objective subsampling or changed robust loss is used.

## Local curvature: better prediction is not enough

At radius 1/8:

| Scene | Captures | Median GN prediction error | Median local-secant error | Coupled proposal beats original rescue |
|---|---:|---:|---:|---:|
| Dubrovnik-356 | 3 | 0.7105 | **0.0453** | 2/3 |
| Venice-52 | 2 | 0.0329 | **0.00357** | 0/2 |
| Ladybug-1197 | 1 | **0.0249** | 0.4075 | 0/1 |

Errors are absolute objective-change prediction errors normalized by the magnitude of the local linear term, with denominator at least one. They are not relative errors in total BA cost.

All six primary-radius proposals pass Armijo. On the later Dubrovnik captures, their immediate reductions improve by approximately 1.30× and 5.51× over the original rescue. But on Venice and Ladybug, the original rescue takes a larger useful step than the fixed 1/8 box permits. The local model therefore failed the predeclared requirement of beating the original rescue on at least 60% of captures in every scene. No online secant policy or large run followed.

Radius sensitivity matters. On Ladybug, local interpolation at radius .5 was very inaccurate and its proposed step failed Armijo. Reducing the radius improves its predictive accuracy, but the measured secant model remains worse than GN on this capture. True-curvature references formed from analytic-gradient differences distinguish finite-radius interpolation errors from GN's omitted residual-curvature term. The two reference difference scales agree within `4.47e-7` in normalized matrix norm. The late Venice reference Hessian is indefinite; the other five are positive definite. This is not a setting in which enforcing positive semidefinite GN curvature always describes the actual local model.

## What causes the large full-step error?

The ten largest positive observation-level GN prediction errors account for:

- **99.87%, 99.95% and 99.98%** of the positive full-step error on the three Dubrovnik captures.
- Approximately 95.96% and 96.51% on Venice.
- Approximately 96.72% on Ladybug.

These percentages concern positive model-underprediction contributions, not total objective cost. Ten observations can belong to the same point, so subsequent choices must aggregate by complete point tracks.

Venice has 6 and 11 full-step endpoint depth-sign changes, and its point-only paths have poles within the unit interval. Dubrovnik has no endpoint sign changes and no point-only pole in that interval. Equal endpoint signs do not prove the joint camera–point path contains no intermediate pole. The measurements nevertheless show that one simple endpoint-depth condition cannot explain all the sampled failures.

The error concentration motivated an additional recorded diagnostic: optimize each point's true track cost while holding the candidate cameras fixed. This uses the exact separability of the original objective, rather than fitting another global curvature penalty.

## Pointwise nonlinear rescue

For each candidate camera scale, independently choose each 3D point's scale from a finite menu by summing **all observations of that point**. The larger diagnostic uses camera scales `{original alpha,1}` and point scales `{0,alpha/2,alpha,.5,1}`. Retain the original accepted rescue unless a reconstructed mixed step passes Armijo and has lower cost.

The minimal diagnostic fixes full camera motion and lets each point either stay put or take its full step. The table shows **immediate cost-reduction ratios**, not time-to-quality speedups:

| Capture | Original rescue alpha | Zero/full point safeguard | Larger per-point menu | Points frozen by zero/full when selected |
|---|---:|---:|---:|---:|
| Dubrovnik, call 1 | 0.5 | **3.39×** | 3.53× | 1 / 226,730 |
| Dubrovnik, call 8 | 0.0625 | **6.74×** | 7.90× | 3 / 226,730 |
| Dubrovnik, call 16 | 0.0078125 | **98.97×** | 102.57× | 2 / 226,730 |
| Ladybug, call 1 | 0.5 | **1.27×** | 1.40× | 7 / 126,327 |
| Venice, call 1 | 0.25 | **2.64×** | 2.92× | 8 / 64,053 |
| Venice, call 8 | 0.25 | Original retained | **1.36×** | — |

The largest ratio starts from a tiny original reduction: on late Dubrovnik, the original rescue reduces cost by **59.27**, zero/full by **5,865.70**, and the larger menu by **6,078.80**. This is a substantial absolute improvement at that state, but it does not imply a 99× solver speedup.

With full camera motion, the larger-menu Dubrovnik candidates leave all but 1, 7 and 3 points at their full point step. This is concrete evidence that globally shrinking every point and camera can be unnecessarily restrictive on these directions. It does not establish that every failed shift menu has the same cause.

The zero/full candidate on late Venice passes Armijo but is worse than the original rescue. Retaining the original is therefore essential. The larger menu improves that capture only with the original camera scale, 0.25, rather than full camera motion.

Adding a midpoint `{0,.5,1}` makes little difference on Dubrovnik and early Venice, but improves Ladybug's ratio from 1.27× to 1.40×. It still does not beat the original rescue on late Venice with full camera motion. The two-option version is the clearest next implementation candidate because it retains most of the observed benefit at lower work cost.

## Work cost and scope of the guarantee

The large diagnostic menu uses 8–10 full observation-equivalent point-cost evaluations across two camera scales, before reuse/fusion. That is too much work to assume profitable from local objective gains alone. The zero/full candidate needs two track-cost values per point at one camera state. A GPU kernel could share camera/projection work and reduce complete track costs, but no such optimized kernel or rollout is implemented in this round.

The pointwise minimum cannot be worse than any feasible uniform point choice **at the same camera state**. Comparing with the saved original rescue adds a same-state actual-cost safeguard. This is an exact finite-menu separability statement. It is not a claim of faster convergence, a globally optimal BA step, a novel coordinate-optimization principle, or superiority to Caspar.

An online implementation should first retain the original rescue, compare the zero/full candidate against it, and keep the better valid step. Immediately accepting a merely Armijo-valid pointwise candidate would discard the protection demonstrated necessary by late Venice.

## Validation and limitations

- Five normal BA runs all pass independent exported-state CPU objective audits; maximum relative discrepancy `2.31e-12`.
- Six saved states and rejected full steps are reconstructed independently on CPU. Maximum relative state error is `1.48e-12`; full-step cost error is `2.12e-9`.
- Independent analytic directional coefficients agree with GPU coefficients within `4.52e-10`. A Venice finite-difference check at `1e-6`/`1e-7` had errors up to `7.38e-5` due to numerical sensitivity; its failed check and subsequent independent analytic audit are retained. We did not loosen the analytic threshold or report every finite-difference test as passing.
- The indefinite box solver passes 2,000 tests, including 1,389 indefinite cases, with 5.2 million grid comparisons and maximum projected KKT residual `5.56e-17`.
- True-Hessian references use analytic-gradient central differences at two scales, with convergence and symmetry checks.
- Every mixed per-point candidate is reconstructed independently and checked against its track-cost sum, with relative discrepancy below `1e-9`; every selected replacement satisfies the full projected-slope Armijo condition.
- The prospective Trafalgar-126 run had no failed-direction captures in 80 iterations. The predeclared Dubrovnik-88 fallback also had none before it stopped at 48 iterations. These are inactive controls, **not independent new-scene validation of the pointwise proposal**. We did not keep searching for a favorable scene.
- CLI and core builds pass. The new C++ code only exports diagnostic states/directions; numerical GPU kernels remain unchanged. Audit-only mode and exclusive-file guards pass, including verification that an existing capture is not overwritten.
- Stage commands, flags, binary/data hashes, raw states/directions, cost curves, derivative checks, model fits, per-point scale arrays and protocol amendments are retained. Final hashes are in `provenance.json`.
- Broad jobs remain paused; defaults remain unchanged. No GitHub publication, new Caspar comparison or time-to-quality speed claim was made.

The pointwise idea was investigated after seeing error concentration. Its six-state results are exploratory and reuse the captured data; the minimal-menu ablation is not a fresh independent confirmation. The original secant gate remains failed.

## Code and reproduction

- `gpu/subspace_capture.cuh`: exclusive raw state/direction export, enabled by `OCA_SUBSPACE_CAPTURE` only with subspace audit mode 3.
- `bench/local_curvature_model.py`: independent BAL path evaluation, analytic directional derivatives and indefinite box minimization.
- `bench/measure_local_curvature.py`, `bench/reference_local_hessian.py`: fixed-state curves, secant models and true-curvature references.
- `bench/pointwise_rescue_diagnostic.py`, `bench/minimal_pointwise_diagnostic.py`: whole-track nonlinear menu minimization and independently reconstructed candidates.

The frozen capture plans can be run through `bench/backtrack_investigation.py` into a new output root with new capture prefixes. Existing capture files are intentionally protected against overwrite. Use `bench/measure_local_curvature.py /workspace/prism-local-curvature` and the associated summary/audit scripts to inspect retained captures; completed measurement files are skipped.

## Thirty-step ledger

| Steps | Completed work |
|---|---|
| 1–4 | Prior failure retained; primary GN context checked; curvature identifiability and exact projection/retraction path derived. |
| 5–10 | True versus GN Hessian; three-cost secant fit and truncation limits; indefinite box solve and independent tests. |
| 11–16 | Raw captures; CPU state/full-step/derivative audits; frozen radii and held-out validation grid; model errors by radius. |
| 17–19 | Depth crossings, point-only poles, observation-level error concentration and camera/point/cross effects measured. |
| 20–25 | Coupled secant, GN and scalar comparisons; original-rescue gain comparisons across scenes; promotion gate rejected. |
| 26–27 | Later-capture radius/true-curvature checks; prospective scene and predeclared fallback attempted and identified as inactive. |
| 28 | Recorded pointwise nonlinear diagnostic and minimal-menu work ablation; exact whole-track separability and fallback bounds checked. |
| 29–30 | Provenance/build/compatibility/paused-process audits and complete mathematical/results reporting. |

## Recommendation

Implement the zero/full per-point safeguard on GPU, retain and compare against the original rescue, and test actual time to equal quality on the contradictory medium cases. This has a clearer mathematical basis and stronger fixed-state evidence than another global lambda or step-scale rule. Require an online gain after the additional track-cost pass before considering a large run or publication claims.
