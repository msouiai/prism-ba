# D15 result: count-gated camera prior is causal but too weak to promote

## Verdict

The sparse gate works, and the local prior can rescue a bad Final3068
trajectory, but the registered evidence does not promote it.  In the strongest
common-random-number test, D15 produced one variant-only target hit, zero
control-only hits, 13 double hits, and 10 double misses across 24 deterministic
perturbation pairs.  The directional SPRT stopped inconclusive at its cap
(`LLR=0.336`, boundaries `+-2.944`); the exact one-sided paired probability is
`p=0.5`.  The frozen Eta2 champion remains the scientific winner.

The result is still mechanistically useful.  All 12 no-activation pairs are
bit-identical between arms.  Twelve difficult pairs activate the prior; one is
causally rescued, while eleven retain their original hit/miss classification.
Thus the count/ratio test is a precise detector of this failure family, but a
dose-one quadratic prior usually does not change the basin.

## Fixed-state gate

The immutable gate selects at most the bottom one percent of cameras by unique
track count, also requiring count below one quarter of the scene median.  On
Final3068 it selects 31 of 3068 cameras, including camera 550 (13 unique tracks
against median 314.5).  The prior raises only the selected cameras' scaled
Schur eigenvalues to the median healthy-camera spectral scale.

At the two archived high-ratio terminal witnesses, dose one:

| Witness | Baseline decrease | D15 decrease | Gain | Baseline rho | D15 rho | Healthy-step retention |
|---|---:|---:|---:|---:|---:|---:|
| 5 | 15.2675 | 16.3521 | +7.10% | 0.2664 | 0.2852 | 100.011% |
| 6 | 0.026323 | 0.028030 | +6.48% | 0.2674 | 0.2843 | 100.015% |

The benign witness changes by only +0.0196% in decrease.  Replay errors pass
the registered full-objective and direction checks.  Stronger diagnostic doses
improve the two hard witness steps more, but dose one was the preregistered
smallest passing finite dose; no stronger dose was selected post hoc.

## Ordinary native screen

The derived-off binary matches the frozen parent to roughly `1e-15` relative
on the compatibility cell.  Fresh Final3068 runs gave 7/10 hits under D15 and
5/10 under the champion, but this independent-cohort difference is weak
(one-sided Fisher exact `p=0.325`).  D15's successful-run target median was
4.605 s versus 3.196 s for the champion.

Venice52 was correctly outside the count-starvation gate: D15 activated in
0/5 runs, both arms hit 0/5, and the median endpoint delta was +0.0046%, far
inside the measured basin floor.  Across the nine practical cells, all 54
runs hit and D15 activated zero times.  Three cells had small disjoint timing
penalties from the prototype's host-side trigger measurement, below the
registered five-cell kill threshold.

## Deterministic paired confirmation

Seeds 660000--660023 used byte-identical `epsilon=1e-12` field perturbations in
both arms.  The derived-off compatibility check was exact in endpoint SHA256,
accepted-cost strings, normalized decision trace, hit, outer, rejection, and
Schur-product counts.

| Quantity | Control | D15 |
|---|---:|---:|
| Target hits | 13/24 | 14/24 |
| Variant-only / control-only hits | 1 | 0 |
| Activated pairs | — | 12/24 |
| Total prior activations | — | 233 |
| Double-hit target-time ratio | — | 1.0018 median |

The sole rescue is seed 660008: control stops at 1.78990M, while three late
prior activations reach 1.74400M.  Most activated misses receive 13--30 prior
applications and remain misses.  One double-hit trajectory receives a single
activation and stays below target but ends 0.863% higher.  These observations
motivate testing the limiting local actuator—drop the selected cameras from
the step before global radius clipping—rather than raising the prior dose.

## Mathematical interpretation

The effective-resistance study found that unique track count is sufficient to
identify the known count-starved camera.  D15 shows how to turn that graph
quantity into a sparse Gaussian information prior in the reduced Schur space.
The gate touches one percent of cameras and preserves healthy-camera motion,
so it avoids the 47%-activation failure of the earlier block-spectral floor.

The limitation is the actuator.  A finite prior reduces the starved component
but leaves it large enough to dominate the global radius on most difficult
states.  The subsequent radial clip still suppresses healthy cameras.  This
explains why fixed-step rho improves reliably while native basin outcomes move
rarely.  The count gate is retained; the finite dose-one prior is not promoted.

Machine-readable evidence: `d15-count-prior-summary.json`,
`d15-final3068-summary.json`, `d15-venice52-summary.json`,
`d15-panel-summary.json`, `d15-paired-summary.json`, and the two registered
protocols.  Source derivations and manifests are under `d15_count_prior/`.
