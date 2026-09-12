# Eta2 wave 2: registered first-stage diagnostics and attribution

Registered 2026-09-12 before new witness decompositions or native comparisons.
Parent: `59ffeb3`. Frozen champion source, 44 headers, configuration and original
binary are checked in-session. Read `../eta2_champion/docs/theory_and_novelty.md`.
The later mentioned `ba_wave2_local_clocks.tex` is absent locally; its numbering
is not interchangeable with the W1–W10 brief supplied in the conversation.
Dependent Local Clocks arms await the actual text. Work below is independent.

## Standing rules

Unchanged observations, plain L2 SIMPLE_RADIAL, unshared intrinsics, k2=0.
No robust loss, observation dropping, learned controller, external restart,
cross-attempt Krylov reuse, outer acceleration, retriangulation, static track
damping, or multishift candidate selection. Original champion files immutable.
One configuration per arm, used everywhere. No per-scene flag selection.
All attempted runs and failures retained; no pooling historical repetitions.
Cost verdict threshold 0.15%; time verdict requires disjoint ranges. Report both
directions, misses, endpoints, initial costs, PCG/outer, rejects and retry wall.
All diagnostic overhead is included in native timing when enabled. Detailed
diagnostic runs are not substituted for low-overhead solver speed measurements.

## Mathematical qualifications (before testing)

1. Frozen tau, E, linearization: A(lambda)=S_tau+lambda I with fixed RHS;
   camera norm is monotone for an SPD exact solve. Coupled tau=lambda changes
   RHS and S, so the CAMERA-only norm need not be monotone. A coupled re-solve
   is a safeguarded heuristic, not an exact camera-radius More–Sorensen method.
2. Point damping adds gauge curvature n_p^T[V - V V_tau^-1 V]n_p, as well as
   camera lambda curvature. The brief's RHS injection identity will be checked,
   but its claim that only camera damping supplies gauge curvature is incomplete.
   Removing camera gauge and re-completing damped points is a physical change,
   not an exactly objective-invariant joint similarity transformation.
3. A model-decrease decomposition must include cross terms and the point-only
   offset. Norm fractions alone are not decrease fractions.
4. A depth barrier must respect signed Snavely depths; log(Y3) is undefined on
   valid negative-depth observations. A same-sign depth ratio is the prospective
   model domain. Positive curvature cutoffs alone are not acceptance evidence.
5. The supplied two-mode lambda=0.008 is illustrative, not an exact unit-radius
   root. Verify toy quantities rather than copying the stated factor.

## W1: fixed states and native telemetry

Use all seven primary wave-1 captures: Venice reps 0/1/2, Final3068 0/5/6,
Ladybug1197 rep0. Also inspect all five earlier stratified Venice endpoint states
at their recorded terminal lambda/radius; label a reconstructed next solve as
such, never as the exact historical last proposal.

Metric: Euclidean in z=E^-1 dc. Global similarity basis from the existing
finite-difference retraction implementation; deterministic K8 geometric clusters
with cluster basis orthogonalized against global gauge. Separately report raw
top-five-camera squared norm fraction. Any sequential remainder decomposition
must retain cross terms or use orthogonalized spaces explicitly.

Report native raw direction and certified coherent reference separately;
prior certification limitations remain. Gauge >50% suggests W4 priority; gauge
<25% at high-ratio witnesses rejects gauge projection as the primary cure.
Five cameras >80% suggests W6c; otherwise test W2. No claim of causation from
decomposition alone.

Native per-attempt telemetry records lambda, tau, radius, raw norm/radius,
eta, PCG iterations, rho, gauge squared fraction, accepted status, numeric
repair, retry scope and measured overhead. Radius-undefined/numeric-repair
attempts are marked explicitly. A low-overhead gauge summary may run each
attempt; full cluster/model decomposition is diagnostic-only and charged.

## W2(a)/W3: opening attribution

One derived binary, default off. Arms: off; lambda0=1,10,100;
disable interior 0.1-lambda reduction permanently; disable it for first three
accepts; multiply lambda by16 exactly once at outer1; eta0.05 first3 accepts
with original clipping/storage; eta0.05 first3 with oversized rejection and
original storage; existing coherent accurate opening reference.

First run Venice52, N=5/arm, alternating/reversing arm order per repetition,
target243740.27, 600 outers, 60 native seconds, champion stopping. Tests of
lambda hypotheses are descriptive per arm, not retrospective winner selection.
Stop the cheap-lambda branch if no cheap arm exceeds2/5 hits. Any >=4/5
mechanism survivor must also be measured on Final3068 N5 at
1744796.9841897595 and every frozen nine-cell practical target at N3 before
promotion. The entire survivor set is retained; no selective panel reporting.
Source/binary/flag/input hashes and independent FP64 endpoint audits required.

## Later stages and gates

W2(b,c): matched-radius witness re-solves, coupled and frozen tau separately;
fresh solves, count all products/factors/RHS work; kappa2 trigger, target interval
[R/2,R], maximum eight root iterations, explicit clipped fallback. No nonlinear
cost candidate menu. Native extension only if Final witness true decrease rises.
W4 only after W1, with RHS/curvature identities and full true-cost checks.
W5: within-step geodesic correction on Final0/5/6 and Venice0; h0.1,
acceleration guard0.75 in full diagonal metric, matched camera radius,
independent normal residual certificates. No momentum/bold acceptance.
W6: horizon witness gate before any full chart grid; signed depth domain.
W8 requires successful W2/W5 directions; no generic stopping-rule retry.
W7/W9/W10 remain lower priority and conditional as the user specified.
Every later native arm requires a separate pre-run registration; an unimplemented
or unevaluated stage is marked pending, never called negative.

## Storage

Root filesystem started with38MB free. Exact old input/export bytes are packed
losslessly with hashes and restoration paths in `storage_compression.json`.
Compiler temporaries and transient state exports may use /dev/shm, with durable
verified compressed evidence retained before transient copies are removed.

## Primary literature

- Transtrum & Sethna, geodesic acceleration/damping updates:
  https://arxiv.org/abs/1201.5885
- GSL nonlinear least-squares documentation (LM/geodesic implementation):
  https://www.gnu.org/software/gsl/doc/html/nls.html
- Existing wave-1 primary-source audit remains applicable:
  `../eta2_research_20260912/literature/MATH_AND_PRIOR_ART.md`.

These establish prior art, not novelty or empirical success of this campaign.
