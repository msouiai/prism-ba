# Wave 5 B5 results: square-root Schur is exact, but changes the tail basin

## Verdict

The Jacobian-consistent projected Schur operator is numerically sound and its
cost is modest, but it is **rejected as a production change**.  It preserved
the practical panel and Muell work counts, then selected a consistently worse
trajectory on both registered tail scenes.  Per the preregistered rule, B2 is
not stacked on this B5 arm.

The implementation remains useful as an audit/reference path.  It establishes
that the sum-of-squares matrix-free form can exactly reproduce the conventional
Schur action while eliminating algebraically negative curvature, and it uses
24 rather than 33 FP32 values per observation.

## Configuration and audit

The frozen Eta2 source and flags are unchanged.  The active arm stores one
camera-major FP32 `2 x 12` Jacobian for each observation and derives `Hcc`,
`Cdiag`, both gradients, the point factor, reduced RHS, diagonal, scoring
back-substitution, and Schur products from that same rounded Jacobian.  All
contractions, point solves, CG recurrences, state updates, and cost evaluations
remain FP64.

The flag-off derived binary matched the frozen binary to `5.66e-14` relative
on the compatibility cohort.  At the Ladybug49 audit direction:

| Check | Relative error |
|---|---:|
| Projected-residual action vs literal `Hcc*v - Jc^T Jp*u` | `1.795e-15` |
| `v^T S v` vs nonnegative sum of squares | `5.908e-15` |

The audited curvature was positive (`25860.6128919`): observation-square term
`24223.9513373`, point-damping term `1636.66064598`, and intrinsic term
`0.0009086754`.  This passes the registered `1e-5` action and `1e-8` curvature
thresholds by many orders of magnitude.

## Practical panel and Muell

All 54 practical-panel runs reached their registered target.  Each active arm
used exactly the same number of products, outers, and rejects as its control.
Endpoint changes were below `0.0015%` in every cell.  The geometric-mean
time-to-target ratio was `1.0152`, a 1.52% slowdown.  The deepest Trafalgar
cell was 5.74% faster; the three Final394 cells were 3.22--4.59% slower.

On Muell, N=3 without profiling:

| Arm | Hits | Median target time | Range | Products | Median endpoint |
|---|---:|---:|---:|---:|---:|
| Frozen-form control | 3/3 | 4.2175 s | 4.2131--4.2195 | 980 | 1,946,467.175 |
| Consistent square-root | 3/3 | 4.4938 s | 4.4925--4.5065 | 980 | 1,946,467.163 |

The time ratio is `1.0655`, with disjoint ranges and indistinguishable quality.
Profiling attributes the difference as follows:

| Muell phase | Control | Square-root | Change |
|---|---:|---:|---:|
| Assembly | 0.735 s | 0.695 s | -5.4% |
| Point factor + RHS | 0.242 s | 0.254 s | +5.0% |
| Krylov | 3.052 s | 3.361 s | +10.1% |
| Candidate path | 0.044 s | 0.042 s | -4.5% |

The 27.3% fragment-storage reduction helps assembly, but reconstructing the
projected residual costs enough arithmetic to make each Krylov product slower.

## Tail gate

| Scene | Control | Square-root | Endpoint change | Main mechanism |
|---|---:|---:|---:|---|
| Final3068 | 2/5 hits, median 1,811,645.65 | 0/5, median 1,907,939.81 | +5.32% | 52→105 outers, 11→23 rejects, 298→327 products |
| Venice52 | 0/5, median 246,333.88 | 0/5, median 247,550.49 | +0.494% | active path collapses to one repeatable worse endpoint |

Final3068 is a decisive hit-rate regression, and both endpoint changes exceed
the registered 0.15% threshold.  More repetitions cannot promote this arm.

## Interpretation

The first-state action audit rules out an algebra error: the projected and
literal Schur forms agree to FP64 rounding.  The practical panel and Muell
also show identical nonlinear work.  The tail failure therefore comes from
the changed linearisation perturbation: rounding `J` once and then forming its
Gram blocks is not the same perturbed problem as rounding `Jc^T Jp` while
retaining FP64 camera and point blocks.  On the two basin-sensitive scenes,
that tiny but persistent difference changes the accepted trajectory.

This is evidence against treating backward stability alone as a BA performance
criterion.  A Gram-consistent operator has cleaner curvature but does not
preserve the basin behavior of the frozen solver.  Iterative refinement on top
of this exact arm would improve the solution of the *same changed linear
system* and cannot, by itself, recover the frozen trajectory.  Any further B2
test must compute its outer residual from the frozen FP64 linearisation and use
low precision only as an inner correction engine; otherwise it inherits this
registered failure.

## Evidence

- `B5_PROTOCOL.md`, `b5-registration.json`, `b5-build-manifest.json`
- `b5-compatibility-summary.json`, `b5-audit-summary.json`
- `b5-panel-summary.json`, `b5-profile-summary.json`
- `b5-muell-summary.json`, `b5-tails-summary.json`
- Per-run manifests, logs, traces, curves, audited state hashes under
  `evidence/b5-*`

