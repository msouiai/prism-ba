# Assembly/context cycle: mathematical and statistical review

Reviewer: mathematical-audit agent. Active tree:
`/workspace/prism-ba-assembly-context`, branch
`research/assembly-context-cycle`, base
`d3d42dcb803f104424a3343364cac414a7ab7342`.
No solver code is edited and no GPU workload is run by the reviewer.
This is a new review; completed prior-cycle findings remain on the
`research/agent-audit-consolidation` branch at `e91a5a95`.

## Current status

Protocol review is pending their creation. No candidate or timing result has
been accepted in this cycle. This preflight records the acceptance boundaries
before evidence is collected; protocol revisions, findings and measured
results will be appended with their provenance.

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
