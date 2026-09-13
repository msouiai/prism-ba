# D20 fixed-state result: quotient one locally unobservable camera mode

Registered by `D20_SLOPPY_QUOTIENT_PROTOCOL.md`.  This is the fixed-state gate;
the native convergence experiment is registered separately and remains pending.

## Verdict at the fixed-state gate

**Advance to the native Venice52 gate.**  All preregistered requirements pass
on all five checksum-pinned terminal states.  The frozen Eta2 champion remains
the current winner until the native tail and no-regression gates pass.

The D18 gate selects camera 34 alone in 5/5 states.  An independent direct-Gram
reconstruction of its scaled 8x8 Schur block reproduces the archived weakest
eigenvector to absolute dot product 1 within floating-point rounding.  Removing
only that one component changes no coordinate of any other camera before the
ordinary global radius clip.

| quantity | control | D20 quotient |
|---|---:|---:|
| raw/radius ratio, range | 428.257--428.267 | 2.24076--2.24087 |
| total raw-step energy in removed component | -- | 99.9972622--99.9972623% |
| true decrease, range | 1.60320--1.60323 | 481.144--481.171 |
| rho, range | 0.300632--0.300637 | 1.004547--1.004547 |
| other camera coordinates changed before clipping | -- | exactly zero |

The true decrease is roughly 300 times the control decrease.  Three repeated
CPU evaluations per state agree, and the independent full-objective and model
audits pass.  The result directly supports the wave-3 diagnosis: almost the
entire apparently global trust-region violation is one locally unobservable
combination of one camera.  A global clip spends nearly all of the radius on
that direction and suppresses every healthy component.

## Important limitation

This is not yet a convergence result.  Point back-substitution remains extreme
in these archived terminal states: maximum point displacement is about
7.4 million scene units, 16 large moves are outward, and the D20 proposal moves
one observation from front to behind.  The full plain-L2 objective nevertheless
decreases and the standard model/acceptance audit accepts every proposal.  The
registered native run is therefore necessary; fixed-state improvement alone
has repeatedly failed to predict final basins in this project.

## Reproducibility

- Protocol: `D20_SLOPPY_QUOTIENT_PROTOCOL.md`
- Scorer: `d20_sloppy_quotient/score_fixed.py`
- Full rows: `d20-sloppy-quotient-results.json`
- Gate summary: `d20-sloppy-quotient-summary.json`

