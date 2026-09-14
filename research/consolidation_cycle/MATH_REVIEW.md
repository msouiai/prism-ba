# Consolidation cycle: mathematical and statistical review

Reviewer: mathematical-audit agent. Started 2026-09-14. The active branch is
`research/agent-audit-consolidation`, now based on production champion commit
`d3d42dcb803f104424a3343364cac414a7ab7342`. Initial protocols named the prior
integration commit `24a33349fb02b554aa8718dcf612af57915d18a8`; that base was
corrected before tests. The completed prior-cycle review remains in
`research/agent_audits/MATH_VALIDATION_REVIEW.md` on the integration branch at
`24a33349`, not in this clean production branch. The reviewer does not edit
solver code or run GPU workloads.

## Current verdict

The new CPU suite, independently audited injected-zero-RHS GPU fixture and
fresh deterministic comparison on the current sources pass their narrow
correctness/compatibility gates. The historical-evidence claim in extraction
commit `114c2b92` was incorrect; it has now been replaced by actual current
measurements and the reporting blocker is resolved. Compatibility is shown
on the tested Ladybug49 configuration, not universally across inputs.
No new fixed-system fusion, workspace concurrency or profiling result has
yet been reviewed. Findings and corrections are preserved below.

Initial protocol hashes:

| Protocol | SHA256 |
|---|---|
| Linear edges | `8b4c6f14eb2c6e7770ea4d1681df086daa804d81f7c13c84d6de4f6ff86ab7e1` |
| Workspace | `19b8a99b1d95f9fecacfabec3b2b1fc95c561cc75664622948d8520e044dbf82` |
| Fused fixed | `d4e0b5954f669234446d9fb653816fd16706e1817130f7e77fbc254b8e731a52` |
| Profile | `ca87351fb8504c936293ceb5a3de3bc1be36e5b3b4ca0e60364d60302fe6cc09` |

## Pre-run review transferred from the integration tree

The previous cycle supports a narrow exact-zero/forcing correctness fix, exact
tested deterministic trajectories, serial cost-workspace compatibility and a
negative fused native smoke. It does not already pass the new scaled-norm,
full-workspace, fixed-system operator or profiling gates.

Ownership and arithmetic changes must be distinguished. A new norm algorithm
or reduction tree can move nonlinear trajectories independently of workspace
ownership. An exact ownership ablation needs identical arithmetic in both
arms. A combination experiment is valid if explicitly identified as such.

The prior host fallback repairs zero or nonfinite returned norms but not every
positive quantized norm. A read-only CPU example verifies:

| Singleton vector | `sqrt(x*x)` | Stable norm | Relative error |
|---|---:|---:|---:|
| `1e-162` | `0` | `1e-162` | -100% |
| `1.6e-162` | `2.2227587494850775e-162` | `1.6e-162` | +38.9224% |
| `1e-160` | `9.99994433575849e-161` | `1e-160` | -0.0005566424% |
| `1e200` | infinity | `1e200` | overflow |

This does not refute the previous narrow zero-classification fix. It is a
discriminating requirement for the newly proposed broader robust-norm claim.
Mixed exponents, normal/subnormal boundaries, NaN/Inf and both BLAS pointer
modes need explicit coverage wherever the implementation supports them.

An external inbox correction at 07:36 UTC supersedes Claude's earlier
gba_230 +7% FP32 observation. His N=3 note reports -0.1% (5.42 versus 5.41
seconds per iteration), with unchanged endpoint. This is externally reported
evidence, not an independently validated run in this cycle. It does not
change the compact-fragment results from the prior cycle; references to +7%
should identify it as superseded.

## P1. Representability and forcing semantics

The linear protocol initially demands a finite scaled norm for every reduced
RHS and a forcing ratio without overflow or underflow. Those universal
requirements are impossible in FP64. Finite vector entries can have a norm
larger than `DBL_MAX`, and a mathematically positive squared norm ratio can
be smaller than the least representable subnormal.

Define the contract instead: finite accurate norm when representable, exact
all-zero classification, explicit NaN/Inf rejection and explicit handling of
unrepresentable norms. For the forcing controller, the relevant quantity is
the final capped eta. A ratio above the cap threshold can safely saturate
before squaring; a true ratio below representable precision may round to zero
without changing the correctly rounded capped eta. Distinguish these cases
from losing a moderate ratio by separately underflowing both norm squares.
In particular, finite pairs `(1e-200, 2e-200)` and `(1e200, 2e200)` must
retain the mathematical squared ratio 0.25, while extreme unequal pairs
exercise mathematically legitimate saturation or vanishing eta.

Zero reduced camera RHS does not imply full nonlinear stationarity. Retain
point back-substitution and full objective scoring. The GPU fixture should
continue to assert zero camera products/iterations, no false curvature event,
accepted point motion and independently audited cost at least 1.0 below the
initial objective. Synthetic RHS injection must remain labeled as such.

## P2. Exact trace and ownership gates need a named substrate

The original linear/workspace protocols demand exact trace comparison without
naming the deterministic measurement substrate. Independent unordered runs
can differ even with the same binary, so such a comparison cannot isolate
flag effects. Pin the exact baseline/configuration and hold complete fixed
reductions constant on both sides of a trace-equivalence gate. The clean
math-only deliverable may be validated with separately generated deterministic
instrumentation; that instrumentation need not be part of the extracted
production change.

For ownership, hold norm/reduction arithmetic fixed while changing ownership.
If a scaled norm is introduced simultaneously, label the combination and add
an ownership-only comparison before claiming bitwise preservation by the
refactor itself.

The two concurrent inputs should be distinct, preferably with different
allocation capacities, and each should have its own serial reference. Shared
scratch can accidentally return correct values when both threads compute the
same numbers. Set global environment/configuration before thread creation;
concurrent `setenv` changes are not a valid way to select per-solve arms.

Two-thread exact outcomes are a useful smoke, not an exhaustive proof of no
races. Name the tested BAL mode, device(s), streams and flags. The protocol
correctly excludes rig pending its own inventory and tests. Any still-active
shared mutable CUDA scratch or handles block the corresponding full-path
concurrency claim, even if the selected smoke happens to pass.

## P3. Fused fixed-system metrics and preregistration

The protocol correctly holds captured arrays, vectors, layout, precision,
damping, equilibration, stream and flags fixed. It correctly separates point
output `u` from bare Schur action `Sv` and avoids calling sampled actions an
operator-norm certificate. Frozen `Kv` computes bare Schur action; `KvS`
adds equilibration/congruence and the shifted PCG operator adds damping
elsewhere. Report which coordinates and operator are compared.

Before timing, define the following in a hashed registration:

* Exact captures, outer/attempt and damping, hashes, probe seeds/counts and
  vector normalization.
* Separate point and Schur denominators. A suitable Schur action diagnostic
  includes `||Sv_ref|| + ||Hcc*v|| + ||W*u_ref||`; the point diagnostic uses
  `||u_ref||`. Preserve the registered absolute-floor error criterion and
  additionally report scale-relative errors without the `+1` floor.
* A numeric tiny-fixture relative threshold. “No material relative anomaly”
  leaves the decision discretionary after observing data. Zero-reference
  vectors need explicit absolute/exact-zero treatment, not division by zero.
* A normalized sampled symmetry defect, for example
  `|v^T S w - w^T S v| / (||v||*||Sw|| + ||w||*||Sv||)`, with explicit
  zero-denominator behavior and an acceptance threshold.
* Warmups, repetition count and product-batch count; alternate the arms and
  retain individual paired measurements rather than only a median.

Require finite entries in every expected-finite output and finite error
metrics explicitly. `if (error > tolerance)` alone can let NaN pass, and
`sqrt(max(0,dot))` can hide it. Invalid-factor fixtures must have an explicit
expected-output contract; the existing invalid-diagonal path should agree
exactly on zero outputs. Source similarity and matching native endpoints do
not replace these direct operator checks.

The five-percent gain on both captures and prohibition on opening native
cells before the fixed gate are clear. Respect this sequence, unlike the
documented out-of-sequence smoke in the prior cycle.

## P4. Capture selection and profiling attribution

“Largest feasible BAL” requires a frozen descending scene order and a
memory-only fallback criterion before looking at performance. Record each
feasibility decision and do not choose the largest scene with a favorable
timing. Selection, input hashes and capture outer/attempt should be fixed
before scoring a candidate.

The profile protocol properly limits profiled native runs to phase shares and
call counts, and requires unprofiled timings plus endpoint rescoring for wall
claims. It still needs pinned stopping/work conditions: target, cap and
maximum iterations, or a fixed captured workload. These can be stored in a
machine-readable registration instead of long prose.

Native solve wall, CSV iteration-phase target crossing and profiler duration
are different clocks. CSV crossing excludes setup before its timer. Summed
GPU-kernel duration is not elapsed solve wall when operations overlap or host
gaps occur. Kernel replay/profiling can alter clocks and cache behavior; use
identical resident captured inputs/work for attribution and unprofiled runs
for operational latency. A phase share bounds only the speedup available from
removing that measured phase under fixed work; it does not certify a new
solver's time to target after its trajectory changes.

## Results and final validation

Pending. The reviewer has requested the above refinements before interpreting
any new results.

## Protocol amendments and clean-base verification

The amended linear protocol now scopes finite norm accuracy to representable
values and explicitly rejects unrepresentable norms. It specifies capped
forcing arithmetic and an identical deterministic trace substrate. The
workspace protocol now fixes arithmetic across arms and requires distinct
concurrent inputs/capacities and separate serial references. These address
the initial P1/P2 protocol issues; implementation and results still need review.

The amended fusion protocol supplies seeds 1701/1702/1703 with four vectors
each, a descending memory-feasibility order (Final13682, Final4585, Final1936),
finite-output assertions, relative error <=1e-10 on nonzero tiny fixtures,
and frozen capture manifests before timing. Its first amendment still omits
an acceptance threshold for symmetry and uses the potentially cancelling
denominator `|x^T S y|+|y^T S x|`. The reviewer requested a 1e-12 threshold
with vector-norm term normalization and explicit zero-denominator handling.
The reviewer also requested naming atomic versus fixed-CSR baseline Pass1,
using unambiguous cross-block `W` notation (code `E` means equilibration),
and a point-output scale based on `||u_ref||` rather than mixing it with the
raw input magnitude `||W^T v||`.

The amended profile protocol now names fixed targets/caps and distinguishes
CSV crossings from full returned solve wall. However, the clean production
branch lacks `research/eta2_wave5/optimized_candidate.json`; simply invoking
the champion flags is not enough to identify B6v7. The reviewer requested
explicit hashes of its generated source/build recipe and effective overlay,
including archived source paths if used. The archived overlay SHA256 is
`53ba1cae00a42d3e84f40250a9a2362e5f8e58000157637c4d8050af2689961a`.

Read-only verification shows the clean branch and prior integration tree
share the frozen source SHA256
`22c18359a526526ae0a5b5109187878ab1cef33b453f6bbddc2aa92597a607d8`
and champion manifest SHA256
`6d37583e5ee802233f034cb3b034d9ef91fdfaabcb27c16a259bdd18d265d251`.
Thus the base change does not alter those frozen inputs; the B6v7 provenance
must still be supplied separately.

The next protocol revision resolves the remaining fused definitions: its
reference is fixed-order point-CSR Pass1, point scale is `||u_ref||`, the
cross term uses `W V^-1 W^T`, and sampled symmetry uses the cancellation-safe
vector-norm denominator with threshold 1e-12 and explicit zero handling.
Consequently its timing is a comparison against the deterministic CSR chain,
not against production's atomic observation kernel. The profile protocol now
requires importing/hashing B6v7 generated source, build recipe and full flag
overlay, and rejects a frozen-champion-only build for that stage. These
protocol definitions are acceptable; their actual manifests remain to be
checked before results are interpreted.

## Initial math-only source review

The new `ScaledFiniteNorm` uses a sequential scaled sum-of-squares state and
tracks `all_zero` from vector entries separately from the floating norm.
It rejects nonfinite entries and a nonfinite reconstructed norm. The
moderate ratio is preserved when both direct squares are normal; the
exceptional path forms a ratio before squaring, allowing mathematically
extreme ratios to saturate the caller's capped eta. The exact-zero bypass
remains restricted to classical, unshared CD9 single-shift PCG with all
configuration validation before bypass, and the classical score depth is zero.

The reviewer independently compiled and ran `test_linear_edge_math.cpp` with
`g++ -std=c++17 -Wall -Wextra -pedantic -O2`; it passed. This is CPU evidence,
not an integrated CUDA branch test. The reviewer requested adding the still
missing unequal forcing extremes, invalid previous-history values, sentinel
history and explicit `all_zero=false` assertions for tiny vectors. Retaining
the prior dense cancellation fixture would preserve the direct mathematical
certificate that zero camera RHS can coexist with a nonzero point step.

Unlike the prior exceptional-only fallback, the new enabled path copies and
recomputes every reduced RHS norm on the host. It therefore adds a host
transfer/synchronization on every enabled attempt and can change ordinary
last bits. An exact flag-off baseline claim can still be tested, and the
safe forcing-ratio expression can preserve arithmetic, but the prior ordinary
math-off/on trajectory-parity observation must not be attributed to this new
always-scaled norm without evidence.

The initial builder also includes the runtime RHS-clobbering
`OCA_AUDIT_ZERO_RHS_FIXTURE` hook. The requested deliverable exposes only the
linear-edge option; the reviewer requested placing the synthetic hook behind
a fixture-only compile define or in a separately generated test binary.
This leaves the correctness experiment available without adding the fixture
control to the extracted solver change.

The builder revision now places that hook behind
`PRISM_LINEAR_EDGE_TEST_FIXTURE`, with a separate `--fixture` build, so the
ordinary delivered binary has no runtime RHS-injection control. The expanded
CPU test covers unequal forcing extremes, invalid previous norms, zero
history, tiny nonzero classification and the dense reduced-RHS cancellation
fixture. The reviewer recompiled and reran it successfully with the same
warning-enabled C++ command.

Before the initial CUDA fixture run, review of `run_zero_rhs_fixture.py`
found that it checked only native cost and deleted the endpoint without the
independent FP64 audit required by the protocol. The integrator was notified
immediately to rescore first, assert a finite audited decrease of at least
1.0, retain endpoint hash and native-versus-audited error, and record full
command/effective flags before deleting the state. That initial runner does
not yet satisfy the audit gate; a native cost decrease alone is insufficient.

Read-only comparison also confirms that every duplicated file under this
clean tree's `gpu/` and frozen `source/headers/` include directories currently
has identical content. The extra include path therefore does not presently
change those frozen header definitions; include provenance should remain
bound to the build's base and hashes.

## First CUDA fixture and invalid parity cohort

The revised fixture runner now performs the independent audit before deleting
the state. `ZERO_RHS_FIXTURE_RESULTS.json` from fixture binary
`be0d3374b4160305009bce20e4fd81c67a35ad3bb3e98f68b583bd0e9a5d5347`
records 90 zero-depth events, 18 accepted point-only updates, 72 rejects,
zero Schur products and zero negative-curvature events. Native cost is
`48246.8987323341`; independently audited cost is `48246.89873233431`, versus
initial `850912.4606413026`, with relative audit difference
`4.373395520858807e-15`. The endpoint SHA256 is
`dcc2c977a821e418b04f9d854774edbe184c336908cbd49964d1cd14861a2a33`.

The reviewer independently checked current binary/input/source/helper hashes
against the result/build manifests, parsed the zero-depth and work counters
from stdout and recomputed the audit-difference scalar. The saved state is
already deleted, so the reviewer verifies the audit harness and its retained
record rather than rerunning the endpoint audit. This is a valid synthetic
control-flow correctness result. It is not a normal BA convergence/speed
result or evidence of a natural exact-zero event's frequency.

`FLAG_OFF_RESULTS.json` is not the protocol's parity gate. Its runner invokes
the ordinary frozen champion and ordinary math derivative with champion
flags, without deterministic instrumentation. Costs already differ at the
initial row: `850912.4606413029` versus `850912.4606413026`, before the math
branch can be exercised. The recorded false cost/decision/endpoint equality
therefore cannot attribute a regression to the new inactive branch. The
integrator was notified immediately to preserve this diagnostic cohort and
complete the registered comparison on identical deterministic instrumentation
of both sources. Changing the protocol to accept stochastic traces would not
repair the intended exact gate.

The ordinary generated source/binary `c8be5fc5...` also predates the fixture
compile guard: it still includes the unguarded runtime injection hook, unlike
the newer fixture source. The current builder is corrected, but the ordinary
binary must be rebuilt and validated before delivery. Preserve old build/result
hashes as historical cohort provenance rather than claiming the corrected
source was what those old runs executed.

## Extraction-report blocker at 114c2b92

The ordinary binary has now been rebuilt as
`422ba229969fe3b466edc97baff5e89a0cb7299864ffe9c2b91c8447c47361f6`,
and its source manifest distinguishes it from the older unordered cohort.
The production/test-fixture separation is correctly described.

However, `LINEAR_EDGES_RESULTS.md` at extraction commit `114c2b92` says that
the fixed-order gate was already validated for “this same patch” in commit
`24a33349`, and that the extraction preserves the validated helper semantics.
That equivalence is false. The old implementation used exceptional-only host
`hypot` fallback after a returned zero/nonfinite norm; the new implementation
always uses scaled sum-of-squares and separately tracks elementwise zero.
The original lightweight compatibility cohort was older still, preceding
later subnormal/history corrections. The prior review explicitly distinguishes
those cohorts and never certifies the new source from their hashes.

Historical parity is useful context, not completion of the current registered
gate. The integrator must remove the false equivalence claim and either run
the stated same-substrate comparison on the current source or explicitly
mark its parity gate unmet and the extraction unvalidated. The reviewed
protocol says a gate failure blocks extraction; substituting old evidence
after the unordered comparison cannot satisfy it. This blocker was sent to
the implementer, root and code reviewer immediately. The valid CPU and
synthetic zero-RHS evidence remain valid independently of this reporting defect.

## Current-source deterministic parity: blocker resolved

The integrator subsequently built two fresh binaries using the same archived
B6v7/W6 fixed-order instrumentation, then applied the current math transform
to one source. This is the required fresh comparison, not reused historical
evidence. The reviewer verified:

* The archived deterministic builder reproduces the saved baseline CUDA
  source exactly in a read-only regeneration.
* `build_linear_edges.derive(baseline)` reproduces the saved current CUDA
  source exactly; `derive()` also reproduces the clean ordinary source.
* Both saved CUDA source and binary hashes match `FIXED_PARITY_BUILD.json`.
* All three saved CSV cost arrays match the rows in
  `FIXED_PARITY_RESULTS.json`; all nine registered fields are exactly equal.
* All retained audit costs are finite, with native/audit relative difference
  `6.698301282731748e-16` in each row.

| Arm | Source SHA256 | Binary SHA256 |
|---|---|---|
| Fixed baseline | `46ad1d3f68e7dfb14b82d6cbf27affc7a5c961d2c50edec7929647b7d9c3744c` | `c3060718b9b80a2cc1491fbccf84aa0d4a5d675aacbe9a66bbc7842798c8a1d2` |
| Fixed current math | `7803add49953e7fc1efe12bd5356347defc37b49b0dcddcfb48123efe8b26ed0` | `68c07c5da56008193aae9cca73c63a57b00097364fcf330d7eb604ed5a7b833d` |

The current helper SHA256 is
`32761954fcc56ac3324b80340df37e75e30425149301123a85cce39a2a4f0fd2`;
the source-transform builder SHA256 is
`139e2f70ed0dcc46bff9aff659a85bbf9ed79810a3d12fedadb9e67be58951d3`.
The builder was generalized to accept either ordinary or already-instrumented
source text; the read-only regeneration shows that this generalization does
not change the existing clean-source output.

Baseline, current flag-off and current flag-on each have 41 CSV costs
(initial plus 40 accepted outers), 129 recorded decision lines, 40 iterations,
40 accepts, one reject, 765 Schur products and zero negative-curvature events.
All reach native cost `13577.990349846`, audited cost `13577.99034984601`,
and endpoint SHA256
`2d9fe14cd02cab1b30d515c78cb8b36d60d9d8c476430aeb82c5d75224b62733`.
The raw decision arrays are retained in the result; the harness does not retain
complete stdout or endpoint files for reviewer-side replay of every field.

This closes the registered current-source compatibility gate on this input.
It does not imply that sequential scaled norms are bit-identical to the old
norm for arbitrary inputs, that ordinary trajectories are universally equal,
or that the enabled host transfer is free. The earlier source-level caution
about these possible effects remains valid; the new measured cell simply
shows no effect on its registered fields.

`LINEAR_EDGES_RESULTS.md` now describes this current-source comparison instead
of claiming historical validation of the same patch. The reviewer requested
completing provenance links from result to input/command/effective flags and
build-manifest hash, and from build to current helper/builder and archived
instrumentation/header hashes. Those metadata additions do not require a
new GPU run; they must identify any hashes collected retrospectively.
