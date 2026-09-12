# Wave 5 B2 results: FP32 correction solves pass the linear gate but do not preserve Eta2

## Verdict

The registered FP32-inner/FP64-residual iterative-refinement arm is **rejected**.
It is a valid solver for the frozen FP64 linear system at Eta2's forcing
tolerance, and its fast FP32 products produce several large practical-panel
speedups.  It nevertheless changes which inexact direction is returned,
changes the nonlinear trajectory by more than the registered tolerance, and
can require several times more Schur products on calm scenes.  The Muell and
tail stages were therefore not run.

The result closes a subtle loophole in the usual mixed-precision argument.
Iterative refinement preserves the fixed point when a linear system is solved
accurately.  Eta2 intentionally stops at a loose, state-dependent residual
tolerance, so many materially different directions satisfy the same linear
gate.  Bundle-adjustment acceptance and basin selection depend on which one is
returned.  A high-precision residual check alone does not preserve the
semantics of an inexact nonlinear solver.

## Registered construction

The outer system is still the frozen champion's system: its FP64 assembly,
reduced RHS, equilibration, point factor and matrix-free Schur operator are the
residual oracle.  A separate 24-value FP32 Jacobian per observation defines an
approximate projected-residual Schur operator.  Each correction uses FP32
point solves, a FP32 camera-block preconditioner, and FP32 CG vectors,
recurrences and reductions.  At most two corrections are allowed.  The FP64
operator recomputes the residual after each correction; failure to meet
`1.01 * eta * ||b||` falls back to the untouched champion PCG.  Model decrease
is recomputed with the FP64 system on the returned iterate.

The derived flag-off binary agrees with the frozen binary to
`1.30e-14` relative on the N=3 compatibility cohort.

## Integration audit

The first audit found a harness bug: a successful refinement bypassed a block
that contained both the legacy CG loop and terminal candidate scoring.  The
computed vector met the residual gate but was never scored, so a zero step was
rejected repeatedly.  That run is retained under the `integration-bug`
filenames and is excluded from the algorithm result.  Candidate scoring was
moved onto the successful-refinement path, and the audit now requires an
actual accepted descent step in addition to its linear checks.

After the fix, Ladybug49 passed:

| Check | Result |
|---|---:|
| Accepted outers | 12/12 |
| Refinement fallbacks / non-monotone residuals | 0 / 0 |
| Maximum correction sweeps | 1 |
| Target reached | yes |
| Final cost | 13,620.166 |

It also exposed the performance risk.  The active arm took 538 Schur products
and reached the target in 75.6 ms, versus 79 products and 26.4 ms for the
matched FP64 control.  Later correction solves needed 68--76 FP32 iterations
to reach an inner relative residual of 0.1.

## Practical panel

All 54 runs reached their registered target.  There were 183 active attempts,
one correction sweep per attempt, zero fallbacks, and zero non-monotone FP64
residuals.  Thus the result is not caused by failed refinement or fallback
overhead.

| Metric | Result |
|---|---:|
| Geometric-mean time-to-target ratio, active/control | 0.8603 |
| Disjoint target-time crossings | 6 faster / 2 slower / 1 overlap |
| Total FP32 inner iterations | 7,290 |
| Product-count ratios by cell | 1.07--4.40x |
| Largest absolute median endpoint movement | 0.519% |

The speed signal is real but does not satisfy the registered semantic gate.
The two Ladybug539 cells with disjoint losses were 1.65x and 1.85x slower.
The third Ladybug cell regressed by 0.351% in endpoint cost.  Trafalgar138 at
the loosest target improved by 0.519%, showing that the perturbation can also
pick a better trajectory; it is still well outside the 0.15% equivalence
band.  The arm therefore acts partly as a new trajectory policy rather than a
transparent arithmetic acceleration.

The practical geometric-mean win also includes fewer nonlinear outers on the
Final394 and Trafalgar cells.  It cannot be attributed solely to cheaper
linear algebra, since product counts rose in every cell.

## Interpretation and boundary for future mixed precision

B5 showed that a backward-stable, Gram-consistent rounded Jacobian can select
a worse tail basin.  B2 now shows that retaining the original FP64 residual
and satisfying its forcing threshold is still insufficient.  Together they
rule out two simple production paths:

1. solve a clean rounded system and rely on backward stability;
2. use that rounded system for refinement and accept any vector inside the
   champion's loose FP64 residual ball.

A future mixed-precision path must either reproduce the champion's Krylov
trajectory closely enough to preserve candidate decisions, use low precision
only inside a preconditioner while the FP64 recurrence defines every iterate,
or explicitly register the altered inexact direction as a new nonlinear
algorithm and validate its tails.  B2 is not promoted under the systems-speed
claim.

## Evidence

- `B2_PROTOCOL.md`, `b2-registration.json`, `b2-build-manifest.json`
- `b2-compatibility-summary.json`, `b2-audit-summary.json`
- `b2-audit-control-results.json`, `b2-panel-summary.json`
- `build_b2.py`, `mixed_ir.cuh`, `run_b2.py`
- Per-run manifests and traces under `evidence/b2-*`
