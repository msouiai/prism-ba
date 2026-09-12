# Eta2 wave 5 protocol

Registered 2026-09-12 before any wave-5 score was computed.

## Frozen baseline and objective

The baseline is `research/eta2_champion/champion.json`.  The frozen source SHA
is `22c18359a526526ae0a5b5109187878ab1cef33b453f6bbddc2aa92597a607d8`
and the original binary SHA is
`1e3d2cf22a8a43075114e0ca2024923dad330461e35d0074938d0412cd77ecc0`.
Every build verifies the source manifest in-session.  The scored objective is
the original plain-L2 SIMPLE_RADIAL objective, with unshared intrinsics and k2
fixed to zero.  No observation is removed from scoring.

Native comparisons use a same-derived-binary off arm, independent FP64
endpoint scoring, the registered targets and caps, alternating arm order, and
N>=3 per ordinary cell.  Tail/hit-rate claims use N>=5; the A2 and A4 settling
cohorts use fresh N=10.  A cost difference is resolved only beyond 0.15%, and
time-to-target requires disjoint ranges.  Misses remain in every table.

No result changes the frozen champion automatically.  Promotion requires the
gate written before its run.  Negative results retain their mechanism and raw
row provenance.

## Ordered gates

- A1 first replays the exact E4 hit/miss states.  Native work is permitted only
  if targeted optimization removes at least 90% of the point-cost gap, preserves
  depth signs, and leaves a positive full-step prediction with rho>0.1 in both
  proposals.  The detector must touch at most 1% of points on healthy scenes.
- B0 profiles the untouched champion before any speed implementation.  A speed
  path is not pursued when its measured end-to-end ceiling is too small to pass
  the 0.15%/disjoint-range decision rule after expected overhead.
- A2 uses one adaptive robust-exit rule fixed before the N=10 cohort.  It must
  retain the Final3068 reliability signal and stay within 1.02x geometric-mean
  time on the nine practical cells to become a promotion candidate.
- A4 compares `rho_min=1e-3` against off at N=10.  Existing wave-4 panel rows
  remain valid supporting evidence; the new cohort does not get pooled with
  the earlier N=5 screen.
- B3 activates the already-implemented exact 9x9 Schur-diagonal blocks before
  considering Nyström.  Nyström requires at least 30% fewer PCG iterations at
  fixed forcing and amortization of all sketch products on the tail workloads.

Wave-4 exclusions remain excluded.  In particular, no learned component,
outer acceleration, cross-attempt or cross-outer Krylov reuse, periodic all-point
retriangulation, controller restoration, marginal-value stopping, or multi-shift
candidate generation is reintroduced.

