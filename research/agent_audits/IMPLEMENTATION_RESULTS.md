# Agent-audit implementation results

Date: 2026-09-14  
Branch: `research/agent-audit-integration`  
Base: `edbc88770e7d40082b6e39c947cfd0f67e31ca6c`

## Outcome

The initial reproducibility winner is the complete fixed-order reduction path
selected by `OCA_W6_DETERMINISTIC=1`; the follow-up wall gate below rejects it
as a production-speed winner. On the new Ladybug49 gate, all five runs produced
one accepted-cost hash, one normalized decision hash, one endpoint SHA256, and
one tuple of iterations, accepts, rejects, products, and curvature events.
The endpoint SHA256 was
`2d9fe14cd02cab1b30d515c78cb8b36d60d9d8c476430aeb82c5d75224b62733`.
The exact audited endpoint was `13577.990349846` after 40 accepted outers, 765
Schur products, one reject, and zero negative-curvature events.  Solve wall
had median 0.334197 s and range 0.330383--0.336927 s.

This is a reproducibility improvement, not a speed winner.  The deterministic
path deliberately replaces multiple fast unordered reductions, and the tiny
cell is not suitable for a production overhead estimate.  Existing Wave-6 D0v3
evidence supplies the larger gate: 5/5 exact endpoint, trajectory, decision,
and work-count agreement on both Venice52 and Final3068.  That prior result also
records 2.505--2.538 s and 13.235--13.292 s native ranges respectively.

The mathematical change also passes its registered gate.  Under
`OCA_AUDIT_LINEAR_EDGES=1`, exceptional-magnitude Eisenstat-Walker ratios avoid
`Inf/Inf` and `0/0`, nonfinite norms fail explicitly, and an exact-zero reduced
camera RHS skips PCG while retaining point back-substitution and scoring.  The
dense cancellation fixture returns the exact joint damped step `(dc,dp)=(0,-1)`.
Ordinary-scale flag-off and flag-on runs were exactly identical when evaluated
on the fixed-order substrate.  The BAL cell did not encounter the new edge
branch, so its measured trajectory effect is zero; no BAL speed claim is made.

## Initial cohort and implemented derivatives

The initial cohort covered code, math and combined derivatives. The final
`build_candidates.py` produces five binaries from reversible
source transformations:

| Arm | Base | Enabled behavior |
|---|---|---|
| `code` | Wave-5 B6v7 | complete Wave-6 fixed-order path, selected only by `OCA_W6_DETERMINISTIC=1` |
| `math` | Wave-5 B6v7 | robust forcing arithmetic and exact-zero RHS handling, selected only by `OCA_AUDIT_LINEAR_EDGES=1` |
| `combined` | fixed-order derivative | both selectable changes |
| `workspace` | combined derivative | per-solve BAL nonlinear-cost workspace, selected only by `OCA_AUDIT_WORKSPACE=1` |
| `fused` | workspace derivative | point-owned fused Pass1/solve, selected only by `OCA_AUDIT_FUSED_PASS1=1` |

The frozen Eta2 champion, B6v7 sources, configuration files, and defaults were
not edited.  With flags absent, all added branches are inactive.  The generated
binaries compiled with CUDA `sm_89`; their hashes were:

- code: `c4d67e7aa233533a3b3294307d07bc0b032974897e9936bce5fe5cfae67fdb64`
- initial math test cohort: `09ed96c99da9b179867150a0343495dbb72e7b7e11f1bd287454060e5f28db54`
- current math fixture: `d88ed9ea623f58f97314afce24205e74e9dca73e9feb71dd250b6487efdc985c`
- initial combined cohort: `bb9f8cca3e30d5d9ced2665e2dc931c683dcfd4f7a37203d788add2510581bed`
- workspace: `7792c643eda1e7c5dd296fc8518001d9231727e7f1e1b4c331661b568186c5c0`
- fused: `77d211fc43cb84ce75c9f2515339da1a5d0c0d363e74711d79b49b7d418df161`

## Validation

The pure C++ test covers safe-range parity, large and tiny finite norms,
zero/nonzero RHS classification, NaN/Inf rejection, and the cancellation
fixture.  It passes under `g++ -std=c++17 -Wall -Wextra -pedantic`.

The GPU harness serialized access through `/tmp/prism_gpu.lock` and independently
rescored every temporary endpoint in FP64 before deleting it.  Maximum native
versus independent relative cost error was `2.42e-15`.  The combined build with
the math flag off and on had exact equality in every registered numerical field.
The combined math-on arm also matched the code-only deterministic arm exactly.
A single timing pair was 2.47% faster with the math flag enabled, but the branch
did not fire and the sample is too small to interpret as an effect.

The first compatibility attempt compared two ordinary unordered runs and saw
different late trajectories.  That is expected from the production reductions
and cannot isolate a math-flag effect.  The gate was corrected by comparing the
math flag off/on on the deterministic substrate, as the audit requires.  Raw
logs from the first attempt remain in `evidence/math-off` and `evidence/math-on`;
the final machine-readable summary records the valid deterministic comparison.

## Decision and limits

The code candidate passes its scientific repeatability gate. Its follow-up
paired wall-overhead gate failed, so it is not a production winner and must
stay opt-in as a diagnostic instrument.
The math candidate is accepted as a
correct edge-case fix, with zero observed effect on the ordinary BAL smoke cell.
It should not be advertised as a general convergence or speed improvement.

The incoming 21--33% observation concerned the legacy/API precision discussion,
but frozen Eta2 already uses compile-time FP32 compact fragments. The matched
compact-layout follow-up below found a tiny-scene reversal and medium/large
benefits, so it does not justify changing the incompatible public option or any
rig default.

Machine-readable results are in `LIGHTWEIGHT_RESULTS.json`; the preregistration,
build recipe, pure helper/test, and serialized GPU harness are stored beside this
report.

## Follow-up sequence

### Compile-time compact fragment precision

The N=3 paired perturbation confirmation failed its universal screen because the
tiny cell favored FP64. These are CSV iteration-phase crossing times; setup
before the CSV clock is excluded. Native solve wall is retained in every row.

| Scene | FP32 hits | FP64 hits | FP32 target range (s) | FP64 target range (s) | median FP64/FP32 |
|---|---:|---:|---:|---:|---:|
| Ladybug49 | 3/3 | 3/3 | 0.1323--0.1472 | 0.1014--0.1015 | 0.7659 |
| Final3068 | 2/3 | 2/3 | 8.2352--10.2008 | 13.0143--14.6605 | 1.7802 (one double hit) |
| Final4585 | 3/3 | 3/3 | 10.3147--14.8540 | 11.1021--18.6119 | 1.3669 |

Final3068 had one discordance in each direction. Final4585 was the largest
preregistered and tested precision cell, not a measured maximum feasible size.
Maximum independent endpoint audit error was `2.38e-14`. Together with Wave-6
D3, the result supports FP32 compact fragments on medium/large BAL work but does
not support a universal tiny-scene speed claim. The experiment did not change
the public `use_fp32_fragments` option and made no rig recommendation.

### Deterministic-path wall tax

The production-speed gate failed. On Final4585 all three pairs hit and the
deterministic/unordered target-time ratios were 1.5008, 1.1216 and 1.6530
(median 1.5008); native-wall median ratio was 1.4980. On Final3068 the fixed
path hit 0/3 and unordered hit 2/3, so target-time overhead is unmeasured. Its
descriptive native-wall ratio was 4.028 median, but this mixes the arithmetic
tax with a different trajectory and work count. The fixed arm remained exactly
repeatable in every registered numerical field. Complete determinism is an
experimental instrument, not a production-speed winner.

### Linear-solve edge corrections

Review found that the original helper still mishandled numerator-only square
underflow and that deterministic `sqrt(dot(x,x))` can collapse a nonzero tiny
vector or NaN to zero. The implementation now retains direct squared arithmetic
only when both squares are normal; exceptional norms copy the reduced RHS once
and compute a stable finite `hypot` norm before zero classification. It validates
current and previous norms and performs PCG mode validation before bypass.

An injected-RHS CUDA correctness fixture exercised the actual branch: 92
zero-depth events, zero Schur products, zero curvature events, 16 accepted
point-only updates, and objective reduction from 850912.46 to 48246.90. This is
a synthetic control-flow certificate, not a naturally observed BAL edge or a
speed result.

### Per-solve CUDA cost workspace

The default-off `OCA_AUDIT_WORKSPACE` prototype gives nonlinear cost scalar,
deterministic partials and deterministic output explicit per-solve/per-device
RAII ownership. It records the owning device, checks use on that device,
synchronizes before free and restores the prior device. Ladybug49 workspace
off/on runs were exact in all nine registered numerical fields and the on log
confirmed the owned 125-block cost path.

This stage is negative for complete concurrency: deterministic BLAS dot/norm
scratch and other historical diagnostic statics remain process-global. A
two-thread deterministic safety claim would therefore be false, so the broader
workspace promotion stopped after the serial gate.

### Point-owned fused Pass1 plus point solve

The default-off prototype uses four point-owned warps per block, the existing
point CSR and `obs2cslot`, FP64 accumulation, the same shuffle tree and the same
3x3 solve/invalid-factor behavior. It removes the intermediate `tacc` clear,
write and read for eligible CD9 unshared compact2 products.

Before the required archived fixed-system timing was available, three
alternating Ladybug49 pairs were run as an out-of-sequence compatibility/kill
smoke. This is a documented protocol deviation and does not pass the registered
fixed-system equivalence gate. The pairs were bit-identical in all trajectory, work
and endpoint fields across 765 products. The fused/control solve ratios were
1.2941, 1.2890 and 1.3396 (median 1.2941), breaching the registered 2% native
kill criterion. The archived fixed-system isolated product timing was not
completed, so its 5% product gate is unmeasured and no broader native panel was
opened. The prototype is retained as a negative result.

## Final decision

Retain the existing unordered, compile-time FP32 compact B6v7 path as the
production baseline; this campaign did not run a full unordered precision
factorial and the tiny deterministic cell favored FP64. The new math edge correction is accepted
as default-off correctness work. Complete determinism passes reproducibility
but carries a roughly 50% target-time tax on the evaluable large cell. The
workspace refactor is incomplete for concurrency, and fused Pass1 failed its
lightweight native wall gate. None of these changes is promoted to the frozen
Eta2 champion or defaults.
