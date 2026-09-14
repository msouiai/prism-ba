# Mathematical and statistical validation review

Reviewer: mathematical-audit agent. Started 2026-09-14 against integration
commit `07cb451b`. This file is an independent review of the integration
protocols and recorded evidence. No solver code is edited and no GPU work is
run by the reviewer. Later sections will record the next-cycle protocols and
results as they become available.

## Current reportable conclusions

The paired precision screen is a valid descriptive negative confirmation:
the already-FP32 compact champion wins some larger timing cells but loses the
tiny cell, and its universal gate fails. Complete deterministic reductions
pass tested repeatability and fail the production-speed screen. The revised
forcing helper and injected-zero-RHS fixture support a narrow correctness
fix, with point updates and scoring retained. Cost-workspace ownership passes
serial compatibility only. Fused Pass1 passes the tested native trajectory
comparison but is slower in all three pairs; the separately specified
fixed-system operator gate remains unmeasured. None of these results justifies
a new universal speed, convergence, reliability, or concurrent-solve claim.

Precision and deterministic target times are post-setup CSV iteration-phase
crossings, not cold or full-solve time to target. N=3 pairing supports the
reported descriptive screen, not a population noninferiority conclusion.
The detailed record below preserves the initial findings and later fixes.

## Initial verdict

The five recorded Ladybug49 deterministic runs support exact repeatability
of the recorded fields on that input and software/hardware configuration.
The deterministic math-off/on pair supports ordinary-path compatibility for
that one cell. They do not yet establish production overhead, target-time
improvement, GPU execution of the zero-RHS edge branch, or complete handling
of underflow in the forcing formula.

The following issues were sent to the integrator immediately, before reviewing
or running any new stage. A resolved finding should remain in this record
with its correction and evidence, rather than disappearing.

## Findings requiring correction or an explicit limitation

### V1. The forcing helper misses subnormal-square underflow

At the reviewed commit, `ForcingRatioSquared` retains the old expression
whenever both squared norms are finite and the squared previous norm is
positive. This is insufficient: squared values may be zero/subnormal and have
already lost the relative information the ratio needs.

Read-only CPU reproduction:

| Norm | Previous norm | Current helper | Ratio-first value |
|---|---|---:|---:|
| `1e-162` | `2e-162` | `0` | `0.25` |
| `2e-162` | `4e-162` | `0.3333333333333333` | `0.25` |

The first case has a zero numerator square and a nonzero subnormal denominator
square. The second has two subnormal squares with inadequate precision.
Require safe normal-range squares before preserving the old arithmetic;
otherwise use the ratio-first path. Add both cases to the test. Existing
`1e-200` tests only exercise the easier case where both squares become zero.

### V2. Nonfinite previous norm bypasses validation

The generated patch calls `ForcingRatioSquared` only inside
`if (prev_bnorm>0)`. A NaN previous norm makes that comparison false, so the
helper's nonfinite check is never reached. If the enabled contract promises
explicit failure on nonfinite norms, validate both norms before the history
branch. A finite nonpositive history sentinel can retain its existing meaning.
Test the call-site behavior, not only the helper in isolation.

### V3. Zero-RHS bypass has broader scope than the registered solver path

`audit_zero_rhs` currently depends on the flag and norm, without requiring
classical single-shift supported PCG. It also bypasses the block containing
the PCG configuration checks. The guard should be scoped to the supported
path, or invalid combinations should fail explicitly before bypassing PCG.
Only the classical `Score` call was patched to zero depth; other modes retain
their prior depth logic. An inactive branch in a normal BAL run does not test
these cases.

The scalar cancellation fixture proves that zero reduced camera RHS can
coexist with a nonzero point correction. It does not exercise the generated
CUDA control flow. A GPU test should demonstrate that the edge branch fires,
reports zero camera iterations and no false curvature event, then retains
point back-substitution/scoring. Such a test must be separately labeled if
it is a generated synthetic system rather than a normal BAL input.

### V4. Precision options name different implementation paths

The frozen Eta2 source already declares `using Fragment = float` near line
9090. Its champion uses `OCA_COMPACT_FRAGMENTS=2`. The public
`use_fp32_fragments` / CLI `--mf-fp32` chooses the separate `Gp32/Gc32/Bo32`
path; compact fragments reject that setting, and multiple champion safeguards
also reject `mf_fp32`.

Therefore an Eta2 FP32/FP64 experiment must use matched compile-time
`Fragment=float` versus `Fragment=double` derivatives, preserving layout,
flags, and solver policy, as D3 did. Flipping the public Boolean and disabling
compact storage would conflate precision, layout, and supported policies.
An API-default experiment in a different production tree needs its own pinned
source/configuration and a distinct label. A result that FP32 is preferable
does not constitute a new FP32 promotion for the already-float frozen champion.

### V5. The overhead gate was not evaluated by the lightweight summary

The original `PROTOCOL.md` includes a greater-than-1% wall-regression kill.
`run_lightweight.py` computes repeatability and compatibility only. It has five
deterministic runs and one unordered run per math flag, with differing work
counts and no balanced same-build deterministic-off/on cohort. The summary's
`passed=true` therefore cannot mean every registered gate passed.

Preserve the valid reproducibility pass, explicitly mark overhead as unmeasured,
and register a fresh balanced timing comparison. Do not infer a kernel-overhead
effect from different nonlinear trajectories. A fixed captured operator with
identical inputs/work isolates arithmetic overhead; full native runs measure
the combined effects of overhead and changed trajectories. Both can be useful
if labeled correctly.

### V6. Report and provenance discrepancies

At the reviewed commit, `IMPLEMENTATION_RESULTS.md` has a mistyped endpoint
hash and says zero rejects. The actual five deterministic rows all record:

* endpoint SHA256:
  `2d9fe14cd02cab1b30d515c78cb8b36d60d9d8c476430aeb82c5d75224b62733`;
* 40 accepts, **1 reject**, 765 products, 0 negative-curvature events;
* native final cost `13577.990349846`;
* independent audit cost `13577.99034984601`.

The two archived unordered math rows use binary hash `09ed96c...`, while the
implementation report lists final math binary `7f75da...`. These are different
build cohorts and must be distinguished. The final deterministic compatibility
pair does use the same combined binary hash `bb9f8cca...` in both arms.

The reviewer independently confirmed that all nine summary rows equal their
respective stored `result.json`, and that every listed deterministic numerical
field has one unique value across the five repeats. Thus the repetition claim
is supported despite the prose errors. The summary's `accepted_cost_hash`
actually hashes CSV cost rows; retain that exact definition rather than
assuming it includes every inner candidate or unrounded cost. Endpoint-byte
identity is stronger evidence for the final state.

### V7. Current smoke timing is not time-to-target

The lightweight harness sets a fixed 40-outer cap and records `solve_seconds`;
it does not set a target or record first crossing. Its timings are fixed-cap
solve wall. The report correctly refrains from claiming that the single
math-off/on timing pair is a speed improvement. Preserve this distinction in
all later summaries.

### V8. Inherited deterministic norm can turn invalid/nonzero data into zero

Further call-chain review found a material interaction in
`eta2_wave6/deterministic_blas.cuh`. `PrismW6Dnrm2` computes `sqrt(dot(x,x))`
rather than a scaled sum of squares. Its host path uses
`sqrt(std::max(0.0,value))`; the device path uses `sqrt(fmax(value,0.0))`.
Both turn a NaN dot result into zero in the written argument ordering.

Consequences for the combined mathematical patch:

* `x=[NaN]` may yield `nb=0`, bypassing the helper's nonfinite rejection and
  entering the exact-zero solve branch.
* `x=[1e-200]` yields a zero squared norm although the vector is nonzero.
* `x=[1e200]` yields an infinite squared norm although its true norm is finite.

The existing pure helper tests start after this conversion and cannot catch
it. This is an inherited diagnostic norm limitation, but the new zero-RHS
bypass must not rely on a zero result as proof of an all-zero vector under
that norm. At minimum preserve NaNs and verify actual all-zero data before
skipping the solve. A preferable exceptional-magnitude fallback uses a
deterministic scaled sum of squares, preserving ordinary-range arithmetic if
compatibility is required. The actual GPU host/device-pointer norm wrappers
and their zero-guard interaction need synthetic tests for NaN, Inf, `1e-200`,
and `1e200`. This finding was sent immediately to both integration and code
auditors. Until fixed or precisely scoped away, the combined build's claimed
nonfinite/underflow protection is incomplete.

### V9. CSV crossing excludes setup and has limited time resolution

Call-chain review shows `CsvOpen` at frozen source line 9493, after substantial
solver allocation/setup. `RESULT solve_seconds` instead surrounds the complete
solver call. The CSV's `wall_s` uses four decimal places. Consequently the
runner's `target_seconds` is a post-setup iteration-phase first crossing,
rounded to 0.0001 seconds. It is a consistent inherited comparison metric,
but it does not charge all initialization or represent cold end-to-end latency.
Report it with that definition and show `native_seconds` beside it. When a
run terminates at its first target crossing, native wall includes setup and
return/cleanup and is a useful complete returned-solve measure. Do not silently
mix it with CSV crossing or full-process time.

## Required validity checks for the next cycle

### FP32 versus FP64

* Pin source, build, complete effective flags, input bytes, initial state,
  target, caps, and timing definition. Log actual fragment scalar width.
* Use identical deterministic perturbed inputs per pair for a paired mechanism
  test; alternate or preregister randomized arm order. Distinct input seeds,
  rather than repeated identical deterministic runs, supply the sampling units.
* Distinguish the deterministic input-shell estimand from native arithmetic
  run-to-run reliability. Deterministic overhead can interact with precision;
  it is not automatically the production precision speed ratio.
* Report all four hit-pair counts, absolute hit-rate difference, and all-run
  charged wall. Double-hit target times are conditional descriptive quantities.
* N=3 or N=5 can screen a large regression; it cannot generally establish
  15-point reliability non-inferiority on a basin-sensitive scene. Keep the
  registered uncertainty/decision rule and report inconclusive when warranted.
* Existing D3 scores may motivate the experiment; do not reuse their seeds as
  fresh confirmatory observations or pool changed configurations silently.

### Deterministic overhead

* Compare the same executable and precision with the determinism flag off/on,
  recording order and fresh repeats. Specify any warm-up before inspecting
  scores and include or exclude it consistently.
* Full solve wall includes nonlinear work changes. Report products, accepted
  outers, rejected attempts, and endpoint quality beside time.
* Do not treat repeated exact deterministic trajectories as independent basin
  outcomes. They can provide repeated wall-time observations under a fixed
  trajectory, subject to environmental correlation.
* A statement about a 1% difference needs resolution below that effect size;
  raw nonoverlap from a tiny convenience sample is not a confidence interval.

### Fused point-owned Pass1 and point solve

The mathematical object is `u_j=Vlambda_j^{-1} sum_i W_ij^T v_i` with the
existing scaling, ordering map, factors, and masks. Preserve the point solve
convention (`Rf` triangular factor rather than an arbitrary symmetric inverse),
camera-major/point-major slot mapping, and shared cross-block values.

Use fixed captured systems with unchanged inputs. Compare point accumulations,
point outputs, and final Schur actions separately; test zero/single/many-view
tracks, repeated camera entries if permitted, long tracks, padding, and a
poorly conditioned point. A fixed epsilon on `||Afused-Aref||/||Aref||` alone
is unreliable near Schur cancellation. Also use an absolute error normalized
by the norms of the contributing terms or a justified backward-error bound.
The denominator must have a stated nonzero floor. Test symmetry via independent
vectors and energy consistency with the same stored operator; nonnegative
curvature alone does not prove action equivalence.

Exact same-order fusion can demand bitwise point outputs. Reordered reductions
need explicitly registered numerical tolerances; passing them does not prove
bit-identical outer trajectories at Eta2's loose forcing threshold. Compare
native target outcomes only after the fixed-system identity gate passes.

### Time-to-target

Freeze a common original-objective target before scoring. The first accepted
state at or below target defines crossing; compare common units and charge
all solver work up to that event. A terminal low cost cannot retroactively
supply a crossing time that was never recorded. Independently rescore exported
endpoints; if crossing is within the audit uncertainty of the threshold, retain
the ambiguity or audit that crossing state.

Misses stay in denominators. Report hit counts and a fixed-deadline metric or
charged all-run wall beside conditional successful-run time. Never average a
failed cap as if it were an observed crossing. Do not equate a lower endpoint
at a fixed cap with faster time to the same quality. Production/rig and BAL
results require separate complete configuration identities.

## Next-cycle review status

At this initial review, the next-cycle precision, overhead, fused-operator,
and target-time preregistrations were not yet present. No approval of those
unseen designs or results is implied by the valid lightweight repeatability
finding above.

## Next-cycle protocol review

The four protocols subsequently appeared as
`FP32_CONFIRMATION_PROTOCOL.md`, `DETERMINISM_OVERHEAD_PROTOCOL.md`,
`FUSED_PASS1_PROTOCOL.md`, and `WORKSPACE_PROTOCOL.md`.

### Precision confirmation: valid pairing, limited inferential scope

The precision protocol correctly uses matched deterministic B6v7 derivatives,
new PCG64 input seeds, common input bytes per pair, alternating arm order,
unchanged objective/flags, independent endpoint audit, and distinct rig scope.
The registered binary identities are FP32 `c4d67e7a...` and FP64 `2b3fca01...`.
Its three scenes/targets are Ladybug49/13591.568354279514,
Final3068/1744796.9841897595, and Final4585/7075838.613048037.
This is a useful fresh descriptive confirmation of the already-FP32 scientific
configuration, not a new public API-default experiment.

The N=3 rule allowing at most one lost hit is a descriptive screen. It neither
supersedes D3 nor establishes a 15-point population non-inferiority margin.
The runner must not turn absence of double-hit pairs into a passing timing
gate: the reviewed expression `(ratio is None or ratio>=0.98)` does that.
Missing target-time evidence is unmeasured/inconclusive. Also, if the intended
criterion is FP32/FP64 time at most 1.02, its exact reciprocal is
FP64/FP32 at least `1/1.02`, approximately 0.980392; 0.98 permits a 2.0408%
regression. Both points were sent before interpreting the new results.

The registration should be immutable on resume. The reviewed function writes
it unconditionally; scripts should assert that an existing registration is
identical and refuse source/binary/protocol mismatches. Include perturbation
and runner hashes. The per-row native manifests already retain full effective
flags/CLI; preserve them and link their identities in the summary.

### Determinism overhead: target-time gate may be unobservable

The protocol separates measurement-instrument value from production-speed
promotion and plans alternating N=3 runs. Before timing, pin the exact same
binary, fragment type, complete flags, targets, caps, and any warm-up. A
missing double-hit pair cannot estimate a deterministic/unordered target-time
ratio. The unperturbed D0 Final3068 trajectory historically missed its target;
if it also misses here, report hit counts and charged wall rather than
inventing the tax to an unattained target. Full-run comparisons include
different nonlinear work and therefore do not isolate kernel overhead.

### Fused operator: original numerical gate is underspecified

The written phrase "relative error ... within the existing true-residual
tolerance" is insufficient for operator equivalence. Eta2's forcing tolerance
can be 0.5, which would allow an unusably inaccurate operator if interpreted
literally. Register numerical constants and the exact normalization before
inspecting outputs. A defensible gate compares both relative action error
away from cancellation and absolute action error normalized by the
contributing upper/cross/damping term norms, with a stated absolute floor.
Point accumulation, factor application, and final Schur action need separate
reports. Include symmetry bilinear checks and explicit expected behavior on
invalid factors; NaN comparisons must never silently pass. The integrator was
notified before fused implementation/timing results were reviewed.

### Workspace ownership: correctness scope

The RAII/cross-device protocol is an engineering correctness experiment.
Serial deterministic identity and concurrent independent solves are reasonable
gates, but changing only cost scratch cannot establish thread safety of other
function-static workspaces (the deterministic BLAS workspace is also static).
Report which buffers are isolated and which execution modes the concurrency
claim covers. No mathematical speed inference follows from ownership alone.

## Corrections observed in progress

The integrator's current uncommitted helper now keeps direct-square arithmetic
only when both squares are `FP_NORMAL`, fixing V1 at the source level, and adds
a test for `(1e-162,2e-162)`. The generated patch now validates both norm-history
values before the history branch, retains configuration validation before
skipping PCG, and scopes the zero guard to the supported classical single-shift
path. These address V2/V3 in source; a fresh build/test identity is still needed.

For V8, the patch now copies the reduced RHS to CPU and uses a checked
`std::hypot` accumulation whenever the inherited norm is zero or nonfinite.
Thus NaN entries are rejected and a tiny nonzero RHS is not mistaken for
exact zero. This is an exceptional branch, not an always-on transfer. It
does not make every other deterministic norm/dot robust at extreme magnitude:
a positive finite but quantized `sqrt(dot)` result may still be inaccurate,
and later CG dot products can overflow/underflow. State the protection as
safe zero-RHS classification and forcing arithmetic, not a proof that the
entire solver supports arbitrary-magnitude inputs. Actual generated-path GPU
tests remain needed for the new branch.

The reviewer independently compiled and ran the revised pure C++ helper test
with `g++ -std=c++17 -Wall -Wextra -pedantic -O2`; it passed. This is CPU-only
validation and does not establish GPU branch execution.

The fused protocol was subsequently amended to explicit `1e-12` point-output,
term-normalized Schur-action, and symmetry bounds, with exact agreement on
invalid-factor zeroing. This resolves the original ambiguity with the loose
PCG forcing tolerance for the stated captured-system screen. It remains an
empirical arithmetic tolerance, not a universal forward-error theorem for
arbitrarily conditioned point systems.

## Precision confirmation: completed independent result review

All 18 rows are now present. The reviewer independently checked current binary
SHA256 against every row manifest, the paired input identities, and every
hit/first-crossing calculation from the saved CSV plus independently audited
endpoint cost. All checks passed. The source specialization changes were also
inspected: the FP64 build templates the point/preconditioner fragment arguments
and changes the stored scalar type, retaining the formulas and solver settings.

| Scene | FP32 / FP64 hits | Double-hit pairs | FP64/FP32 CSV target-time ratio | All-run native-wall ratio median |
|---|---:|---:|---:|---:|
| Ladybug49 | 3/3 / 3/3 | 3 | median 0.7658610 | 0.7271842 |
| Final3068 | 2/3 / 2/3 | 1 | single observed ratio 1.7802239 | 1.7785054 |
| Final4585 | 3/3 / 3/3 | 3 | median 1.3669340 | 1.3645485 |

Final3068 has one both-hit pair, one FP32-only hit, and one FP64-only hit.
Its absolute sampled hit difference is zero, and the 1.7802 conditional timing
comes from **one pair**. Final4585's ratios are 1.6968, 0.7474, and 1.3669:
one paired trajectory favors FP64. Ladybug's three pairs all favor FP64.
Maximum independent endpoint relative error is `2.376149111008765e-14`.

The corrected summary reports `passed=false`, as required by the Ladybug
regression against the all-scene FP32 screen. This is a valid descriptive
negative confirmation result. It does not establish that FP64 should replace
the frozen FP32 champion, nor that the original production API default should
change. Precision affects nonlinear work as well as storage: Final3068 median
products are 353 versus 524, and Final4585 155 versus 169. The result cannot be
attributed to memory bandwidth alone. Repeated deterministic-trajectory costs
remain conditional on this instrument and the selected input shell.

The original precision protocol hash observed during review was
`2ce300896f3a7f7c18eea61f536d98bf43cd93270ecc90f8f16c56fca7c21b65`;
the actual row manifests uniformly contain the amended hash
`815f5e660e7b517f6f0d10315f7bd55bc82174be5638615e0d8ebbc8ca4a0e74`.
The amendment clarified existing-FP32 scope, the reciprocal 2% threshold,
and missing timing evidence. The integrator was asked to preserve an explicit
amendment timing/history rather than describing both texts as one unchanged
preregistration. No numerical run-setting mismatch was found among the 18
recorded rows.

## Deterministic overhead: completed independent result review

All 12 rows are present. The reviewer independently checked binary/input
identities, first-crossing/hit calculations, and complete effective flag maps.
Within each pair, flags differ only by the determinism selection and expected
output paths. All checks passed. Each scene's three fixed-order runs has one
unique endpoint, cost-trace hash, decision hash, cost, product count, and
rejection count.

| Scene | Fixed / unordered hits | Double hits | Fixed/unordered target ratio | All-run native ratio median |
|---|---:|---:|---:|---:|
| Final3068 | 0/3 / 2/3 | 0 | unmeasured | 4.0281845 |
| Final4585 | 3/3 / 3/3 | 3 | median 1.5007520 | 1.4980188 |

The production-speed gate correctly fails. Final3068's 4.028 ratio is not the
tax to a common attained target: all fixed runs miss and the trajectories
perform different work (fixed median 472 products/121 outers, unordered
295/62). Final4585 provides observed same-target timing: fixed is slower in
all three pairs, with target ratios 1.50075, 1.12158, and 1.65298. Its fixed
median work is 115 products/19 outers versus unordered 165/25, so the
operational regression occurs despite fewer products. No kernel-only overhead
factor follows from these native trajectories.

The valid claim is exact repeatability on the tested cases and substantial
observed native latency cost. Preserve the fixed path as an opt-in measurement
instrument. Neither N=3 unordered hit rates nor three repeats of one fixed
trajectory establish population reliability. The fresh data nevertheless
plainly fail the registered operational screen without requiring an uncertain
small-effect significance claim.

## Fused and workspace source review before test results

The initial `AuditFusedPass1Vinv` preserves the deterministic baseline's
original-observation CSR lookup, `obs2cslot` mapping, per-lane `q+=32` summation,
and warp shuffle tree. It invokes the same `MFVinv` triangular-factor solve and
duplicates the same invalid-diagonal zeroing condition. Four point-owned warps
per block have uniform point validity within each warp, so the early return
does not partially deactivate a participating warp. This supports expecting
bitwise point outputs; it does not substitute for the GPU gate. The initial
patch leaves `Kv`'s unconditional `cudaMemset(tacc)` in place, so its original
claim to remove the clear is not yet implemented. The integrator was notified.

The generated fused binary also contains optional mathematical/workspace
branches. Hold their flags fixed across fusion off/on arms. A change in several
flags is a combination experiment, not a one-factor fusion ablation.

The initial workspace patch changes only the legacy `ComputeCost` scalar.
When `OCA_W6_DETERMINISTIC=1`, `ComputeCost` returns early into
`PrismW6DeterministicCost`, which still owns static partial/output/capacity
storage. Consequently a serial deterministic workspace-off/on test does not
exercise the newly owned scalar, and concurrent deterministic solves still
share cost scratch. The deterministic BLAS workspace is separately static too.
This confound was sent immediately to both implementer and code reviewer.
Either cover deterministic cost ownership as well, or state/test the narrower
legacy-cost scope. Pointer-use instrumentation or an equivalent direct check
must show that the ownership path under test was actually exercised.

The next source revision moves fused eligibility validation before `Kv`'s
dispatch and skips clearing only after the flag has passed that validation.
This addresses a transient implementation hazard identified during review:
the initial clear-removal patch could otherwise have sent unsupported JIT or
legacy-FP32 atomic paths through an uncleared accumulator without reaching the
late guard. These source corrections precede any fused result reviewed here.

The workspace revision now supplies an audit-local deterministic-cost header
using the per-solve partial and scalar buffers when enabled, including device
and capacity checks. This removes the vacuous deterministic-cost test issue
for that path. The serial `WORKSPACE_RESULTS.json` pair uses one binary
`7792c643...`, differs only in the workspace flag, and exactly matches all nine
registered numerical fields and the original Ladybug49 endpoint SHA256.
This is valid serial compatibility evidence. Its one wall-time pair does not
establish overhead, and its `passed=true` means the serial gate; the protocol's
concurrent smoke and broader ownership checks require separate evidence.

## Revalidation provenance warning

During later helper revalidation, the lightweight harness reused its original
output names and overwrote the initial tracked `LIGHTWEIGHT_RESULTS.json` and
the `evidence/code-fixed`, `math-off`, `math-on`, and `combined*` rows with fresh
runs. The original cohort remains recoverable from commit `07cb451b`, to which
this review's initial findings are explicitly tied. The integrator was asked
to preserve or restore that cohort and place new-build revalidation in a
distinct folder/summary, with binary hashes and cohort labels. In particular,
the claim that the first unordered compatibility attempt still lives at the
same `evidence/math-off` and `math-on` paths is no longer true while those files
hold the fresh revalidation runs. New runs may be valid, but they are new
observations and must not silently replace the provenance of earlier claims.

The initial tracked lightweight cohort was subsequently restored, so its
original commit-bound rows and timing are again available at the original
paths. Any claims about newer binaries should still identify their separate
revalidation evidence rather than inheriting that cohort's binary identity.

## Zero-RHS GPU control-flow fixture

`test_zero_rhs_gpu.py` and `ZERO_RHS_GPU_RESULTS.json` now provide a real CUDA
branch exercise. The fixture explicitly overwrites the reduced RHS with zero
under `OCA_AUDIT_ZERO_RHS_FIXTURE`; it does not claim that Ladybug naturally
has this reduced system. The result uses math binary `d88ed9ea...` and records:

* 95 zero-depth diagnostic events;
* zero Schur products and zero negative-curvature events;
* 17 accepted outer updates, with full original-objective cost falling from
  `850912.4606413026` to independently audited `48246.89873233432`;
* endpoint audit relative error `2.4129078735772728e-15`.

The saved trace confirms that ordinary full-model scoring and acceptance run
after the bypass. This supplies the previously missing integrated evidence
that point updates are retained instead of treating zero reduced RHS as full
stationarity. It is a synthetic RHS-injection correctness test, not a valid
timing/convergence comparison with the original BA algorithm or a frequency
estimate for this edge case. The reviewer suggested additionally asserting
`matvecs==0` and a nontrivial accepted cost decrease in the test, since its
initial pass condition checks only a positive event count and zero curvature
events. The observed rows already satisfy those stronger conditions.

Together with the revised scalar CPU tests and ordinary-path compatibility,
this supports the narrowly stated zero-RHS/forcing robustness improvement.
The earlier caveat about general extreme-magnitude CG arithmetic remains;
this is not arbitrary-scale numerical robustness for the entire solver.

The fixture was subsequently rerun under the same math binary and overwrote
the uncommitted first row. The retained `ZERO_RHS_GPU_RESULTS.json` has 92
zero-depth events, 16 accepts, 76 rejects, zero products and zero curvature
events, with the same audited endpoint cost. Its pass condition now also
requires zero products, accepted point updates and a cost decrease. The
earlier 95-event/17-accept observation above is historical; it is not the
retained row's count. Since the fixture does not enable deterministic
reductions, such repeated control-flow counts need not be identical. This
does not change its narrow correctness interpretation, but the final report
must use the retained row's counts and must not combine the two runs.

## Fused native smoke: independently checked negative result

`FUSED_PASS1_RESULTS.json` records six rows from binary
`77d211fc43cb84ce75c9f2515339da1a5d0c0d363e74711d79b49b7d418df161`.
The reviewer checked each saved result against its summary row, current binary
and input hashes, recomputed every accepted-cost and decision hash from the
CSV/stdout, checked RESULT timings, and recomputed all pairwise ratios.
The pairs alternate off/on order and differ only in the fused flag; the math
and workspace flags are absent in both arms. All nine numerical fields agree
exactly, including the original Ladybug49 endpoint and 765 Schur products.
The maximum recorded independent endpoint audit error is
`6.698301282731748e-16`.

| Pair | Unfused solve wall (s) | Fused solve wall (s) | Fused/unfused |
|---|---:|---:|---:|
| 0 | 0.341838 | 0.442384 | 1.2941334784 |
| 1 | 0.335854 | 0.432923 | 1.2890214200 |
| 2 | 0.327986 | 0.439374 | 1.3396120566 |

The median paired native ratio is `1.2941334784313039`. These runs have the
same work and provide a valid descriptive operational rejection under the
2% smoke kill threshold. They do not isolate product time, and three repeats
of one deterministic trajectory do not constitute independent input coverage.
Exact endpoint/decision agreement also does not replace direct operator
tests on invalid factors, long tracks and the archived system.

The registered protocol requires the archived/synthetic operator gate and a
5% product gain before native cells. That gate was not completed before this
Ladybug smoke. The reviewer notified the integrator that the run order is a
protocol deviation. It should be called an out-of-sequence compatibility/kill
smoke, not completion of the registered fixed-system validation or evidence
that its numerical tolerances passed. The explicit
`fixed_capture_product_timing_measured=false` and
`promotion_gate_passed=false` in the summary correctly prevent promotion.
No further GPU work is required merely to turn this clear negative smoke into
a broader performance claim; retaining it with the deviation is sufficient.

## Remaining provenance and claim boundaries

`FP32_PROTOCOL_AMENDMENT.md` now documents the interrupted lock preflight and
states that interpretive/summary clarifications preceded the first numerical
result. This resolves the previously unacknowledged protocol revision. The
initial observed protocol hash was
`2ce300896f3a7f7c18eea61f536d98bf43cd93270ecc90f8f16c56fca7c21b65`;
all scored manifests and the registration use
`815f5e660e7b517f6f0d10315f7bd55bc82174be5638615e0d8ebbc8ca4a0e74`.
No change to numerical scenes, seeds, perturbations, targets, caps, binary
arms or order was found in the reviewed scored cohort.

The workspace protocol now explicitly limits this prototype to cost scratch
and defers the concurrent test while BLAS and other scratch remain static.
That is an honest reduced scope and a negative result for complete workspace
promotion, not a concurrency pass. Its one exact serial pair is sufficient
for the stated compatibility observation only.

The build manifests hash generated CUDA sources and binaries but initially
omit changing audit-local headers. The reviewer requested explicit hashes of
`linear_edge_math.h`, `deterministic_cost.cuh`, `fused_pass1.cuh`, and the build
recipe so a later header edit cannot silently alter the meaning of a source
hash. Older manifests must remain tied to their original builds; later
dependency provenance should not be presented as if recorded before the run.

The final implementation report must replace the initial “overhead remains
unmeasured” decision with the measured failed gate, distinguish initial and
revised math binaries, and use retained fixture counts. The retained baseline
may remain the operational choice for this panel; this experiment does not
prove that one precision/reduction choice is universally fastest.

The final consistency pass found one assertion defect in the strengthened
zero-RHS fixture: `final_cost < audit_cost || final_cost < initial_cost`
can report a decrease from endpoint rescoring roundoff alone. The reviewer
requested comparing the independently audited endpoint directly with the
initial objective, with a meaningful strict margin. The retained fixture
already decreases by hundreds of thousands, so correcting this predicate
does not require a new GPU run or change the recorded scientific outcome.
The review also requested explicit initial-versus-current binary labels in
the implementation report and replacing an unsupported universal “fastest”
claim with the operational decision to retain the existing baseline.
