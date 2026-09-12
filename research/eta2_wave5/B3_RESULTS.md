# B3 Schur-Jacobi results

The registered phase switch is rejected as a production change.  Replacing
Eta2's camera-block `Hcc` preconditioner with the diagonal blocks of the Schur
complement after `lambda <= 1e-3` reduced matrix-vector products on selected
cells, but it was 1.6% slower in geometric-mean practical-panel target time,
made Muell 21.3% slower, and reduced the Final3068 target hit rate from 4/5 to
1/5.  Randomized Nystrom was therefore not built on top of this arm.

## Configuration and controls

The frozen champion uses explicit 9x9 camera-block PCG.  The active derived
binary leaves that preconditioner unchanged through the opening and then sets
the existing `PrismPcg::schur` selector permanently when the accepted camera
damping reaches `1e-3`.  It does not change the forcing rule or the Schur-block
formula.  The disabled derived binary agrees with the frozen champion to
`1.1e-15` relative endpoint cost.  Source, binary, inputs, registration, and
protocol hashes are recorded in `b3-build-manifest.json` and
`b3-registration.json`.

An earlier registration using `OCA_BLOCKEQ` is preserved as
`b3-registration-invalid-blockeq.json`.  Its smoke test was stopped by the
solver's configuration guard before producing an outcome because BLOCKEQ is a
different congruence-coordinate preconditioner and is incompatible with the
champion's explicit PCG.  No result from that invalid arm entered the verdict.

## Practical time-to-target panel

All 54 paired runs reached their registered targets.  Values below are N=3
medians; an asterisk marks disjoint target-time ranges.

| Cell | Off time (s) | Schur time (s) | Time delta | Products off -> Schur |
|---|---:|---:|---:|---:|
| Final394 1.005 | 0.2412 | 0.2067 | -14.3%* | 135 -> 90 |
| Final394 1.01 | 0.1711 | 0.1710 | -0.1% | 86 -> 68 |
| Final394 1.02 | 0.1271 | 0.1468 | +15.5%* | 50 -> 59 |
| Ladybug539 1.005 | 0.0866 | 0.1246 | +43.9%* | 52 -> 72 |
| Ladybug539 1.01 | 0.0621 | 0.0908 | +46.2%* | 42 -> 64 |
| Ladybug539 1.02 | 0.0592 | 0.0576 | -2.7% | 42 -> 35 |
| Trafalgar138 1.005 | 0.3066 | 0.2035 | -33.6%* | 594 -> 337 |
| Trafalgar138 1.01 | 0.2302 | 0.1902 | -17.4%* | 462 -> 310 |
| Trafalgar138 1.02 | 0.1265 | 0.1316 | +4.0%* | 232 -> 203 |

The geometric mean of the nine target-time ratios is `1.0162`.  The useful
signal is real but conditional: on the two deeper Trafalgar targets the Schur
blocks save 33--43% of products and 17--34% of time, while on Ladybug they
change the inexact trajectory so that both product count and wall rise by
roughly 40--50%.  Even within one scene the sign changes with target depth.

## Muell and tail gates

On Muell (N=3), the off arm reached the target in 4.2207 s with 980 products,
16 outers, and no rejection.  The Schur arm took 5.1186 s, 1149 products,
17 outers, and one rejection: `+21.3%` time and `+17.2%` products.  Its endpoint
was slightly lower, but target time is the registered metric.

On Final3068 (N=5), the hit rate fell from 4/5 to 1/5.  The off arm's successful
target crossings had median 3.2767 s (range 3.0865--3.8098); the one Schur hit
took 6.6855 s.  Median endpoint cost regressed 10.90% and median rejects rose
from 5 to 12.  On Venice52 both arms remained 0/5, while the Schur median
endpoint regressed 2.57% and native wall rose from 1.416 to 1.948 s.

## Mechanism and decision

The fixed-system result that motivated B3 remains valid: on Muell outer 12,
Schur-Jacobi reduced one frozen solve from 41 to 3 iterations and from 131.2 to
24.4 ms.  The native result shows why that is insufficient.  Changing the
preconditioner changes the finite-iteration direction under Eta2's forcing
rule.  That changes accepted outer steps, damping, rejection history, stopping,
and basin selection.  Product reduction can therefore coexist with worse
time-to-target or a lost target.

The production gate fails on speed, Muell, and both tails.  A randomized
Nystrom layer would add sketch matvecs to a base preconditioner that already
destabilizes the nonlinear trajectory, so its required amortization and
quality premises are absent.  The Trafalgar rows remain useful evidence for a
future preconditioner whose activation is selected by an in-run spectral
quantity and whose nonlinear step is held equivalent; they do not justify a
scene-specific production switch.

Raw results are in `b3v2-panel-results.json`, `b3v2-muell-results.json`, and
`b3v2-tails-results.json`; compact summaries are the corresponding
`b3-*-summary.json` files.
