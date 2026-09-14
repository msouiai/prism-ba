# Assembly/context cycle: mathematical and statistical review

Reviewer: mathematical-audit agent. Active tree:
`/workspace/prism-ba-assembly-context`, branch
`research/assembly-context-cycle`, base
`d3d42dcb803f104424a3343364cac414a7ab7342`.
No solver code is edited and no GPU workload is run by the reviewer.
This is a new review; completed prior-cycle findings remain on the
`research/agent-audit-consolidation` branch at `e91a5a95`.

## Current status

The initial protocols at commit `faae2661` have been reviewed. Their overall
sequence and measurement separation are appropriate, subject to the gate
refinements recorded below. No candidate or timing result has been accepted
in this cycle. Protocol revisions, findings and measured results will be
appended with their provenance.

## Timing and identity rules

Keep four quantities separate: assembly microtime on identical captured
inputs; complete returned solve time at fixed outer work; fresh-process time
including work outside the solve; and first crossing of a fixed objective
target. A speedup in one is not automatically a speedup in another.

Pin actual B6v7 generated source, binary, build recipe, headers and effective
flags. This clean production base includes the frozen champion, but B6v7's
archived overlay and implementation are separate inputs. The known overlay
SHA256 is `53ba1cae00a42d3e84f40250a9a2362e5f8e58000157637c4d8050af2689961a`.
Every scored row should identify input/state hashes, source/binary/config,
objective definition, clock boundary and actual work/stop reason.

For timing, use at least three paired repetitions, fixed warmup/repetition
counts and alternating or preregistered randomized arm order. Preserve all
attempts, failures and individual ratios. A ratio of arm medians and a median
of paired ratios differ; state which is reported. N=3 is a descriptive screen,
not a population reliability or noninferiority certificate. Profiled runs
support attribution, while unprofiled runs support latency claims.

The previous cycle's phase shares covered the first three outer iterations.
They motivate an opening-workload investigation but do not identify later
hard-outer or full time-to-target bottlenecks. Define the new workload and
ceiling before looking at candidate results. For fixed work, an eliminated
phase fraction f has ideal overall speedup bound 1/(1-f); optimizing only part
of assembly has a smaller ceiling than eliminating all measured assembly.

## Dead writes and arithmetic equivalence

A removed store must be dead over the complete supported control flow,
including first use, retry/rejection, stopping, diagnostics, alternative
options and any later warm-context call. A value that is unused in one
benchmark can still initialize memory read by a later path. Scope the change
to a proved configuration instead of extrapolating to unsupported modes.

Pure dead-write elimination should preserve every live numerical output.
Compare the assembly's live blocks/gradients/fragments and full resulting
operator action on identical captured state, layout, precision, robust loss,
weights and damping. If a fusion changes operation grouping, FMA behavior or
reduction order, exact output equality may no longer be expected; register
explicit tolerances and separately test deterministic repeatability.

Require finite expected-finite outputs and metrics explicitly. Report errors
per output family with meaningful scale-relative denominators; an absolute
`+1` floor alone can hide an incorrect tiny output. A sampled action check is
not an operator-norm or nonlinear convergence certificate. A correct Schur
matrix with a mismatched reduced RHS is not an equivalent linear solve.

## Reused context semantics

State whether each warm call resets numerical state and LM/controller history
to the same initial condition, or intentionally continues the previous solve.
Only the reset case directly compares fresh versus reused setup for identical
work. Continuation is a different workload and must be labeled and targeted
separately.

Parsing, immutable observation topology and symbolic structure can be reusable
without making residuals, Jacobians, robust weights, numeric factors or LM
history reusable. State/camera/intrinsic/options changes need explicit cache
invalidation. Check rejected attempts and exception paths, not only successful
calls. A repeated solve that accidentally inherits damping, radius, forcing
history, cost/stopping counters or stale numerical buffers can change both
work and endpoint while appearing faster.

Report context creation, state upload/reset, returned solve and output costs
separately where measured. If reporting amortized latency for K uses, include
creation/K and declare K. Keep complete cold-process wall as a separate
quantity. Exact reset-mode trace comparisons need fixed arithmetic in both
arms; independent unordered runs cannot identify a context-induced change.

## Concurrency evidence

Use distinct inputs/capacities and separate serial references. A construction
barrier can demonstrate that both contexts are alive concurrently; an overlap
record can substantiate overlapping host calls. Neither by itself proves
simultaneous GPU kernel execution. State precisely which concurrency property
is claimed and which CUDA streams/devices/options were exercised.

Allocation-time pointer separation proves ownership separation for those
allocations, not execution of every diagnostic path. Failure tests must
distinguish workspace-construction cleanup from all later solver allocations
and handles. Scope remains the tested BAL paths unless rig, exceptional exits
and any claimed cross-device use are separately inventoried and validated.

## Target runs and conditional Caspar comparison

Freeze the original objective, initial state, target value, cap, stopping
conditions, accepted-cost audit and clock before collecting target data.
Log first objective crossing on the stated clock; a terminal cost at an
arbitrary iteration is not time to target. If only a final endpoint/time is
available, report a bound or complete-run latency, not an invented crossing.

Any Caspar comparison requires the same host/GPU and identical optimization
problem, input/initial state and audited target. Reprojection conventions,
intrinsic degrees of freedom, distortion masks and robust objective must
match. Do not compare one solver's phase/iteration clock to another's process
or complete-solve clock. Record solver setup/output boundaries and whether
reuse is included. Independently rescore both endpoints against the same
objective, preserve censored/nonhit runs, and summarize timing only on the
declared paired target-hit set. Do not call a timing cell passed when no
paired common hit exists.

The conditional Caspar stage should open only after its preregistered
candidate/quality gates; a later comparator run must not retroactively define
the winning target or scene. No new GPU work is requested by this review.

## Initial protocol review at faae2661

Initial SHA256 identities:

* `PROTOCOL.md`:
  `3d11588b26b5e7b05b132557ecc3e3ccc09204429cf977b3b2c2c820c8009f3a`.
* `INSTRUMENTATION_PROTOCOL.md`:
  `fa009f36f2dba8458e332d65231e7cf3a39af0234b41986d0134976a3844b3f9`.

The detailed instrumentation protocol correctly brackets native launch
boundaries and labels a split replay as diagnostic and non-additive. Those
rules should govern the general Stage 1 wording: derivatives, fragment writes
and normal accumulation occur within monolithic `MFAssemble` and cannot be
separated by native launch-boundary events. A native whole-kernel duration
and split-replay component durations answer different questions.

Stage 2 appropriately requires selecting only one candidate after attribution
and preregistering its denominator, ceiling and kill gate before source edits.
The candidate registration must state whether the five-percent threshold
applies to assembly microtime or complete fixed-outer solve wall. A microtime
gain can open an end-to-end validation step, but cannot itself establish a
production-speed win or justify a Caspar speed claim.

Two gate refinements were sent to the integrator before timing:

1. The instrumentation protocol's exact flag-off trajectory claim and Stage
   3's exact reset/work comparison need an identical fixed-order measurement
   substrate. Independent unordered production runs do not isolate a change.
   Keep unordered production timings and deterministic compatibility as
   separately named experiments.
2. Stage 3 must define its production-speed criterion before opening the
   conditional comparison: baseline clock, intended reuse count K (or an
   explicitly break-even-only conclusion), included construction/reset/output
   costs and a numeric gain threshold on both scenes. A faster warm marginal
   call does not establish an amortized gain after context construction.

The initial Stage 3 reset semantics are otherwise explicit and appropriate:
state/controller history return to the same hashed initial condition, and
numeric caches are not implicitly reused. Stage 4 now requests a start
barrier plus evidence of overlap, addressing the previous cycle's limited
two-thread smoke. Its resulting claim must still distinguish overlapping
host calls from simultaneous GPU kernel execution and keep rig excluded
until separately validated.

The code review identifies `Bo` as live in the selected tau-split point-factor
path, and `Cdiag`, `bc` and `bp` as live in the single-shift solver. Single
shift alone is therefore not a valid proof that these writes can be removed.
Any dead-write candidate needs its own whole-path dataflow proof and live
output/operator/RHS checks, as specified above.

## Protocol amendment review before Stage 1 results

The amended `PROTOCOL.md` SHA256 is
`83922563847048ea6837d0a04f2c7a1ec535709804f4f5e192db5c33b2588d9d`.
It resolves the initial gate ambiguities: exact compatibility uses a separate
identical fixed-order substrate; the Stage 2 five-percent gate applies only
to assembly microtime and opens native time-to-target validation; Stage 3
fixes K=5 and includes construction, reset/upload, solve, download/output
and destruction in the amortized comparison, with a five-percent threshold
on both scenes. These definitions permit Stage 1 to proceed.

Before any Stage 2 native target validation, its candidate registration
must also freeze the native production-speed threshold, target, cap and
clock. The assembly gate cannot supply these retrospectively. Stage 3's
amortized gate can support repeated identical-reset fixed-work service
latency on its registered boundary; any subsequent time-to-target claim
still needs the explicit first-crossing evidence described above.

No performance result has yet been reviewed for this cycle. The reviewer
will continue through the full cycle, including conditional comparison
eligibility and the scope of any skipped stages.

## Projection-sharing equivalence boundary

Inspection of archived `MFAssemble` and `bal_grad12_generated.cuh` shows
that the generated residual outputs and the residual used for assembly are
algebraically equal but have different floating-point evaluation graphs.
Assembly computes `xq=-Px/Pz`, `yq=-Py/Pz`, then
`r2=xq*xq+yq*yq`, `dist=1+k1*r2+k2*r2*r2`, and
`rx=f*dist*xq-u`. The generated helper expresses radius through
`(Px*Px+Py*Py)/Pz^2`, the quartic through
`(Px*Px+Py*Py)^2/Pz^4`, and its residual through
`-u-(dist*f/Pz)*Px` with its own expression ordering.

Consequently, substituting the currently discarded generated residual
outputs for assembly residuals cannot be justified as preserving arithmetic
order. It also changes residual-based robust weights, RHS accumulation and
the cost/controller trajectory when applicable. Sharing identical
camera-space intermediates is a narrower possible transformation; preserve
the current radius, residual and weighting graphs if claiming exact live
outputs, and inspect compiler-generated code before attributing a cost to
apparently duplicated expressions. A deliberate arithmetic change instead
needs a preregistered finite-output, operator/RHS and objective-tolerance
gate. This note constrains later selection; it does not select an additional
candidate before Stage 1.

## Initial native-instrumentation implementation review

The initial `build_native_timing.py` records events 0--3 only when
`need_assembly` is true, but sums events 0--8 at every factor rebuild. If
a rejected attempt reuses assembly, the repeated sum would count the prior
assembly again and include intervening Krylov/candidate work in the
pre-factor interval. The integrator was alerted before measurements. A
general implementation should keep separate assembly and factor chains;
a deliberately narrow three-accept experiment must instead verify and
enforce zero rejections and matching assembly/factor counts before using
these intervals. Factor-cache reuse also requires explicit accounting.

The assembly interval also brackets `RobustUpdateScale` before the
`MFAssemble` launch. The registered nonrobust configuration may make that
call inert; the report must establish that fact or label the interval
accordingly. Instrumented event-chain timings remain attribution data,
separate from the uninstrumented timing distribution.

## First native cohort and evidence-integrity issue

The first completed summary contained one profile and three controls per
scene. Both profiles recorded three assembly/factor event chains; all eight
runs reported three accepts, zero rejects and zero negative-curvature
events, with seven products on Muell and sixteen on Final13682. Thus the
retry omission did not affect this specific cohort.

The first-cohort values observed by this reviewer were:

| Scene | Profile solve seconds | Profile assembly milliseconds | Three uninstrumented solve seconds | Median solve seconds |
|---|---:|---:|---|---:|
| Muell-gba146 | 0.225094 | 139.119938 | 0.227277, 0.303546, 0.229508 | 0.229508 |
| Final13682 | 2.265744 | 884.435333 | 2.261072, 2.275268, 2.254657 | 2.261072 |

Using each profile's own native-solve denominator gives assembly shares
61.8053% and 39.0351%; eliminating the entire assembly interval at unchanged
work would be only an ideal fixed-work Amdahl ceiling. Covered event-chain
sums are 153.188130 ms and 1121.855234 ms; they do not cover all of Solve.
The slower Muell control is part of the registered N=3 and cannot be dropped
as a post hoc outlier.

While validating the completed summary, the reviewer detected that the
same per-run paths were being overwritten by a second cohort adding
`OCA_SETUP_PHASE_PROFILE` to reported configuration and recording setup
lines. For example, the original Muell profile was replaced by a
0.245302-second profile and its three controls were also replaced. The
summary still contained original rows, so equality of summary rows with
their saved `result.json`, logs and state hashes failed. The integrator and
parent were alerted immediately. This is an evidence-integrity blocker
until cohorts, identities and any unrecoverable original artifacts are
explicitly accounted for; rewriting the summary alone does not restore
the original N=3 evidence.

At detection, the current generated source was
`9382e91f4f4afb104b8f4bcd6a09d1992aafb9884360a5c196ec9c98c23c7000`
and its current binary was
`88d375a7a4f72c9fb02460fc466023144779ad156e509763ba46d69b4cb0002a`.
The control binary was
`b1b125b55a5d4ff1415fd379a8fee269609f42dffe9409fe0f9b831e41629799`.
These hashes matched their current manifest and summary at that check;
they do not remedy overwritten run artifacts. Source inspection also
shows that setup profiling is controlled by `OCA_NATIVE_PHASE_PROFILE`;
`OCA_SETUP_PHASE_PROFILE` itself is not read by the generated source.
