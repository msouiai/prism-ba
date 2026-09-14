# Agent-audit implementation results

Date: 2026-09-14  
Branch: `research/agent-audit-integration`  
Base: `edbc88770e7d40082b6e39c947cfd0f67e31ca6c`

## Outcome

The current winner is the complete fixed-order reduction path selected by
`OCA_W6_DETERMINISTIC=1`.  On the new Ladybug49 gate, all five runs produced
one accepted-cost hash, one normalized decision hash, one endpoint SHA256, and
one tuple of iterations, accepts, rejects, products, and curvature events.
The endpoint SHA256 was
`2d9fe14cd02c02b1ea58aed22e618f500730c596f24099355d852e59dbd567cc`.
The exact audited endpoint was `13577.990349846` after 40 accepted outers, 765
Schur products, zero rejects, and zero negative-curvature events.  Solve wall
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

## Implemented derivatives

`build_candidates.py` produces three independent binaries from reversible
source transformations:

| Arm | Base | Enabled behavior |
|---|---|---|
| `code` | Wave-5 B6v7 | complete Wave-6 fixed-order path, selected only by `OCA_W6_DETERMINISTIC=1` |
| `math` | Wave-5 B6v7 | robust forcing arithmetic and exact-zero RHS handling, selected only by `OCA_AUDIT_LINEAR_EDGES=1` |
| `combined` | fixed-order derivative | both selectable changes |

The frozen Eta2 champion, B6v7 sources, configuration files, and defaults were
not edited.  With flags absent, all added branches are inactive.  The generated
binaries compiled with CUDA `sm_89`; their hashes were:

- code: `c4d67e7aa233533a3b3294307d07bc0b032974897e9936bce5fe5cfae67fdb64`
- math: `7f75da1f5e9dea3541d4810b57c3daf9d0087a97cd5a3b8e1391cdaa4c592c88`
- combined: `bb9f8cca3e30d5d9ced2665e2dc931c683dcfd4f7a37203d788add2510581bed`

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

The code candidate passes its scientific repeatability gate and remains the
highest-value compatible improvement.  It should stay opt-in until its overhead
is measured on a stable production panel.  The math candidate is accepted as a
correct edge-case fix, with zero observed effect on the ordinary BAL smoke cell.
It should not be advertised as a general convergence or speed improvement.

The code audit's second-ranked FP32-fragment promotion has the larger production
speed ceiling (21--33% on the reported BAL panel), but it was not selected here
because the requested paired integration first needed a deterministic measuring
substrate.  Rig FP32 remains scene-dependent and should retain an explicit choice.

Machine-readable results are in `LIGHTWEIGHT_RESULTS.json`; the preregistration,
build recipe, pure helper/test, and serialized GPU harness are stored beside this
report.
