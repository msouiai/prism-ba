# D9: lifted robust opening

Registered before deriving, building, or scoring the native arm.

## Question

Wave 4's scheduled Cauchy IRLS opening was the only objective-side change to
improve the Final3068 screen (5/5, with fewer rejects), but its fixed schedule
cost 1.145x on the practical panel and its adaptive exit failed in wave 5.
This experiment tests the still-untried categorical-map cell: optimise the
confidence weights jointly with cameras and points, eliminating the weight
increments inside each Gauss--Newton step as in Zach (ECCV 2014).  This is not
IRLS: persistent weights are state variables, and their Schur elimination
adds a rank-one residual-space correction to both the normal matrix and RHS.

## Frozen control and objective

The scientific control remains `research/eta2_champion/champion.json`.  Native
timing uses the already validated B6v7 systems overlay in
`research/eta2_wave5/optimized_candidate.json` for both arms.  The final score,
registered targets, observations, SIMPLE_RADIAL model, unshared intrinsics and
`k2=0` remain unchanged plain L2.  The derived source must reproduce B6v7 when
the new flag is absent.

## One registered arm

`lift3` enables `OCA_W6_LIFTED=1` for the first three accepted steps, then
hands the resulting state and controller variables to ordinary Eta2.  For
observation residual `r` and persistent scalar confidence `w`, the opening
objective is

```
Phi(r,w) = 1/2 [ w^2 ||r||^2 + (a2/2) (w^2 - 1)^2 ].
```

This is the smooth truncated-quadratic lifting in the released SSBA-4.0 code,
with `a2 = max(4 * median_initial(||r||^2), 1e-12)`, chosen before this cohort
to reuse O5's registered data scale.  Every weight starts at one.  On a
candidate, the scalar weight increment is the exact damped GN backsolve

```
dw = -w [ ||r||^2 + a2(w^2-1) + r^T J d ]
         / [ ||r||^2 + 2 a2 w^2 + lambda ].
```

Accepted candidates commit their matching proposed weights; rejected
candidates roll them back.  Since eliminating `dw` depends on `lambda`, a
retry rebuilds assembly rather than reusing an incompatible normal matrix.
Candidate cost, assembled matrix/RHS, and the full-step prediction used by
Eta2's strict rho test all use the same lifted objective.  The transition to
L2 occurs immediately after the third accepted candidate; it retains lambda,
radius and numerical-floor state but clears objective-dependent stopping
history.  Intermediate CSV costs and all endpoint audits use full L2, and a
target may be certified only after the L2 handoff.

The implementation is restricted to the champion-like, unshared CD=9,
single-shift, full-scoring path.  Alpha-grid, robust-kernel, replay, and menu
variants are rejected at startup.  Eta2's backtracking and point safeguard do
not activate before three accepts; if that invariant changes, the lifted arm
must fail closed rather than score a rescue without its matching weights.

## Correctness gates

1. Randomised scalar/block tests compare the transformed 2x2 metric and RHS
   against explicit dense Schur elimination to relative error below `1e-12`,
   and finite differences check the lifted objective and proposed-weight
   update.
2. With `OCA_W6_LIFTED` absent, N=3 on Ladybug539 at the 1.01 target must stay
   within 0.15% endpoint cost of B6v7, with no CUDA/memory error.
3. A one-run diagnostic must show exactly three committed lifted accepts,
   persistent weights, retry rebuilds when applicable, a clean L2 handoff,
   and agreement between native and independent FP64 endpoint scores.

## Scored screen and decisions

Run fresh paired cohorts, reversing arm order on odd repetitions:

- Final3068, target `1744796.9841897595`, 60 s cap, N=5 per arm;
- Venice52, target `243740.27`, 60 s cap, N=5 per arm.

Report hit count, conditional target time, endpoint L2, rejects, outers,
matvecs, opening accepts, weight distribution, and total lifted overhead.
The arm earns an N=10 confirmation and the nine-cell N=3 practical panel only
if it gains at least two hits on one tail without losing a hit on the other,
or if it preserves both hit counts while a disjoint conditional-time range or
clear reject reduction supplies the signal.  It is killed if both tail hit
counts are unchanged or worse with no speed signal, or if either median
endpoint regresses by more than 0.15% without a hit-rate gain.  No scale,
duration, or kernel is retuned from these results.

## Prior-art boundary

Zach's lifted robust BA and Black--Rangarajan duality are established.  This
screen does not claim the lifting itself.  The research question is whether a
short, jointly optimised lifted opening transfers O5's measured basin benefit
to a matrix-free, inexact, trust-region BA path at lower run-everywhere cost.
Released reference source was audited at SSBA-4.0 commit
`20f1fcf3283d0b2e787f0a55ea9dd1cd3258fa9b`; exact equations and deviations
from that implementation must be recorded with the result.
