# Delivery reconciliation and joint disposition — 2026-09-11

The Eta2 opening-hybrid verdict at commit **5188722** is unchanged. Claude has
accepted it and parked his SHIFT1 reverse-direction prototype. Both champions
stay as they were. No GPU work was requested or run for this reconciliation.
The original 149-run archive remains immutable; this addendum records metadata
received after the experiment and the collaborator's subsequent consolidation.

## Received evidence and provenance

Seven files from `/workspace/multishift_repro/shipdiag` are preserved verbatim
under [evidence/claude_shipdiag](evidence/claude_shipdiag): the exact diagnostic
definition, source/binary hash declarations, three raw traces, the spectral
study script and its result JSON. [RECEIPT.json](evidence/claude_shipdiag/RECEIPT.json)
records their locally computed hashes. The exact source and executable named
in HASHES.txt were not included, and their remote paths do not exist here;
their source-to-binary identity is therefore supplied provenance, not an
independently verified build. We did not execute the delivered script.

[inspect_shipdiag.py](inspect_shipdiag.py) verifies the seven copied file hashes
and parses the logs/JSON without importing the upstream code. Its output is
[shipdiag_review.json](shipdiag_review.json). There is no need to rebuild or
repeat either solver to record the distinctions below.

## The two diagnostic functionals differ before clipping too

Both operate on equilibrated camera-block CG iterates before lifting into
physical camera coordinates; neither includes the point increment. Both use
five dynamic camera shifts lambda times [0.01, 0.1, 1, 10, 100]. However,
Claude's SHIFTDIAG is

    max_{i<j} ||y_i-y_j|| / max(||y_i||, ||y_j||),

whereas our raw diameter divides every pair by max_k ||y_k||. Our actual switch
uses the corresponding bank-wide diameter of radius-clipped vectors. For the
same nonzero vectors, our raw diameter is at most the pair-normalized one; that
inequality supplies no direct translation of the clipped switching threshold.
The equilibration and operator trajectories can also differ across solvers.
Thus the original 1e-3 threshold remains an experimental choice, not a
reproduction of Claude's measured approximately 6e-4 value. Phase locations can
be compared descriptively by outer/checkpoint index, with no matched-state claim.

The delivered traces support strong opening-versus-later differentiation on
the two small scenes. The following is a descriptive checkpoint summary, not
a newly chosen switch rule or a repeatability estimate:

| Trace | First observed maxrel | Observations at outer >=20 | Late median [min, max] |
|---|---:|---:|---:|
| Ladybug49 | 0.9934 | 39 | 0.0006553 [0.0001398, 0.005688] |
| Dubrovnik88 | 0.9907 | 43 | 0.0002368 [0.0001077, 0.02643] |
| Final3068 | 0.9836 | 0 | No later-window observations |

Final3068's last diagnostic is at outer 6, depth 128, with maxrel 0.7792 and
seven cumulative rejects. Its run subsequently ends after 13 reported outers
with 43 rejects. The diagnostic fires only at reached checkpoints, so its
absence in the later reject streak does not establish collapse there. Nor is
the small-scene phase boundary a monotone permanent transition: later/deeper
checkpoints can discriminate again. These observations support phase structure,
not a universal safe switch based only on the outer number or one shallow test.

## What the spectral comparison actually measures

The delivered script builds a dense finite-difference Schur matrix at each BAL
initial state, uses eight active camera coordinates with k2 frozen, point
Marquardt damping tau=0.003, and Jacobi equilibration. Both labels, `opening`
and `grind`, use this **same initial-state matrix** with different shift grids.
The RHS is a seeded Gaussian vector, not the native BA gradient RHS.

The script runs independent ordinary CG and reports max(five CG iteration
counts) as the cost proxy for a shared solve. It does not execute a shared-zeta
recurrence. Its `nystrom` arm uses the exact top 50 eigenvectors, an idealized
spectral preconditioner, rather than constructing a randomized Nystrom sketch.
Counts exclude eigenspace construction, vector/candidate work, handover and
nonlinear solver costs. These are useful spectral headroom measurements, not a
native GPU shared-versus-preconditioned timing experiment.

| Initial-state matrix / shift-grid label | Shared proxy: max independent CG | Sum of five exact-top50 PCGs | One central exact-top50 PCG |
|---|---:|---:|---:|
| Venice52 / opening | 34 | 44 | 4 |
| Dubrovnik88 / opening | 35 | 47 | 4 |
| Ladybug49 / opening | 36 | 42 | 4 |
| Venice52 / grind | 1,218 | 1,900 | 229 |
| Dubrovnik88 / grind | 800 | 1,629 | 277 |
| Ladybug49 / grind | 461 | 946 | 195 |

The quoted 800–1218 versus 1629–1900 values are the Dubrovnik/Venice grind-grid
rows. The full three-scene ranges include Ladybug's 461 versus 946. The center
column also illustrates why a comparison against five solves cannot establish
an advantage over one solve. That idealized preconditioner is not Eta2's native
block preconditioner, so these counts are not a new Eta2 result either.

## Joint state and remaining ownership

The following new consolidation numbers are **Claude-reported** in the delivery
message; the supplied shipdiag files do not contain those trial populations:

| Claude configuration | Final3068 good basin | Final4585 endpoint delta | Dubrovnik356 endpoint delta |
|---|---:|---:|---:|
| DEEP_REJECT=512, DEEP_AFTER=2 | 10/25 = 40%, reported p=0.037; 10.6 s wall | +3.6% | +12.2% |
| DEEP_REJECT=512, DEEP_AFTER=3 | 4/15 = 26.7%, reported p=0.38 | -0.1% | Not reported here |

These do not justify a global promotion. Claude retains his base champion and
documents AFTER=2 as an opt-in for freeze-type scenes. He owns both the proposed
zero-recent-accepts discriminator and backtrack-first / deep-second /
lambda-last ordering, in his solver. That discriminator remains a hypothesis,
not a completed result.

One trace-level consideration for that discriminator: the supplied Final3068
log records accepted outers 9 and 11 near the stalled 2.14863M objective, between
retry ladders, before the relative-decrease stop. Thus zero accepted steps and
negligible progress are distinct predicates. Define the window over attempts
or outers explicitly and retain its cumulative objective gain alongside the
Boolean accept count. This does not establish failure of the proposed guard
without its window definition; it is feedback from the delivered trace, not a
new intervention or a request to duplicate Claude's work.

The joint empirical record is: three reject responses characterized;
backtracking and same-lambda deep CG each help in their tested architecture;
neither has established a generally beneficial transfer. Candidate phase
structure is observed, but neither tested hybrid direction has produced a
promotable win so far. Preserve the storm taxonomy, raw evidence, fixed-target
comparisons and architecture-specific improvements. Do not generalize the
opening-bank rejection to every possible phase hybrid or every trust-region
method. Codex has no further GPU work queued for this proposal.
