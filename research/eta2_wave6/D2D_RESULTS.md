# D2d result: fragment precision also controls the Final3068 branch

## Registered gate

FP64 fragments pass both alternatives of the registered mechanistic gate:

- the three-dose perturbation slope stays in `[0.75,1.25]` through outer five,
  versus only through outer three with FP32 fragments: **two extra linear
  outers**;
- at `epsilon=1e-12`, median D10 falls from 153.064 to 0.0003448, a
  **443,916x reduction**, without an earlier discrete split.

This permits a separate paired full-convergence precision experiment.  It does
not promote FP64 storage by itself.

| Dose | FP32 median D10 | FP64 median D10 | FP64 global / CG / safeguard splits |
|---:|---:|---:|---:|
| 1e-8 | 175.62 | 57.01 | 3/4, 3/4, 4/4 |
| 1e-10 | 133.03 | 0.03479 | 0/4, 0/4, 1/4 |
| 1e-12 | 153.06 | 0.0003448 | **0/4, 0/4, 0/4** |

At the smallest dose, the FP32 path changes its point-safeguard aggregate in
4/4 directions, its CG sequence in 3/4, and its global accept/reject sequence
in 1/4.  FP64 retains all three discrete traces in 4/4.  At `1e-10`, FP64 is
still smooth except for one aggregate frozen-point count.  The large `1e-8`
perturbation can drive real nonlinear branches even with FP64, as expected.

## Per-outer mechanism

With FP32 fragments, the fitted slope is 1.000, 0.997, 0.992 and 0.958 at
outers zero through three, then drops to 0.511 at outer four and approaches
zero by outer ten.  With FP64 fragments it remains 1.000, 1.000, 1.000, 1.000,
1.000 and 1.016 through outer five.  Its later slopes are 1.06--1.37 rather
than collapsing toward zero; the finite-difference direction is being
amplified nonuniformly but remains proportional to its input dose.

Thus FP32 fragment rounding is upstream of the Final3068 controller branch,
not merely a harmless endpoint perturbation.  The point-safeguard and
accept/reject differences are consequences after the smoothness is lost.

## Scope and next test

This still does not say whether precision improves the registered target hit
rate.  Basin-sensitive optimisers can benefit from numerical perturbations,
and doubling fragment bandwidth can lose time.  The justified next step is a
common-input, deterministic FP32-versus-FP64 full-convergence cohort on
Final3068, reporting paired hit outcomes, target time, endpoints and work.  A
compact residual representation is only worth building if FP64 first improves
that reliability experiment.

Rows are in `d2d-results.json`; the slope and gate calculation is in
`d2d-summary.json`.
