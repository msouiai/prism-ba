# D2 result: the opening is scale-ambiguous and contains finite jumps

## Registered verdict

Neither scene passes the cross-dose gate, so this experiment does **not**
establish a positive mathematical finite-time Lyapunov exponent for Eta2's
opening.  The `1e-12` cohorts meet the positive/sensitive thresholds, but the
matching `1e-10` directions are unresolved and their fixed outer-5 exponents
do not agree within 25%.

| Scene | Dose | N | median A10 | A10 range | median gamma5 | median gamma10 | Global decision splits | Class |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Venice-52 | 1e-12 | 8 | 2,973.7 | 2,209.0--4,371.3 | 0.992 | 0.800 | 0/8 | positive |
| Venice-52 | 1e-10 | 4 | 28.0 | 18.7--44.4 | 0.463 | 0.333 | 0/4 | unresolved |
| Final3068 | 1e-12 | 8 | 24,317.4 | 8,127.2--46,675.2 | 0.679 | 1.009 | 4/8 | positive |
| Final3068 | 1e-10 | 4 | 274.3 | 156.2--831.3 | -0.216 | 0.560 | 4/4 | unresolved |

The compact-state instrument passed its own gate first.  On each scene,
dump-off and two dump-on ten-outer runs had identical endpoint hashes,
accepted-cost hashes, decision hashes, costs, and work counts.

## Mechanism visible in the scale dependence

Amplification changes by roughly the inverse perturbation dose, while the
absolute terminal separation barely changes.  Venice's median residual-space
distance at outer 10 is `0.00655` for `1e-12` and `0.00610` for `1e-10`.
Final3068's is `153.1` and `133.0`.  This is inconsistent with a clean linear
regime in which A(k) should be dose-independent.  It is consistent with both
doses eventually crossing a discontinuity or numerical quantisation boundary
that creates a finite state jump.

Final3068 gives the clearest chronology.  For the larger dose the median map
contracts through outer 6 (`A6=0.319`), then jumps to `A7=94.5`.  All four
directions change a global accept/reject decision by outer 7--9.  The smaller
dose also contracts through outer 3; four of eight directions later change a
global decision.  By outer 10 both doses have reached a similar absolute
separation.

Venice has no global accept/reject or CG-depth split through ten outers, yet
the separation settles at the same finite scale.  Its point-safeguard
aggregate first differs by one frozen point in several directions at outer 6,
after amplification has already begun.  A finer scale ladder and a hash of
discrete per-track choices are needed to distinguish FP32 fragment
quantisation from an unlogged local selection boundary.

## Consequence

Controller work is not justified by a positive-FTLE claim.  The evidence
instead prioritises localisation of the finite jump.  A registered scale
ladder should test whether `||delta r_k||` plateaus as epsilon decreases, and
an FP64-fragment audit should test whether the discontinuity belongs to the
mixed-precision linearisation.  If Final3068's jump remains tied to the
acceptance threshold after that isolation, soft/filter acceptance is the
categorical-map follow-up.  Venice needs the local decision source identified
before choosing its intervention.

Machine-readable evidence is in `d2-registration.json`,
`d2-instrument-validation.json`, `d2-results.json`, and `d2-summary.json`.
