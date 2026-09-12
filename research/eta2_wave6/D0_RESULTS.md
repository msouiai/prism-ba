# D0 result: exact deterministic trajectories achieved

## Verdict

The D0v3 measurement binary passes the preregistered deterministic-trajectory
gate.  On both tail scenes, five independent executions produced one unique
endpoint-state SHA256, one exact accepted-cost sequence, one normalized
decision trace, and identical endpoint/outer/rejection/Schur-product/stop
fields.  The feature-disabled derived binary remains compatible with B6v7:
the median calm-cell endpoint difference is `-1.24e-14` relative.

| Scene | N | Exact endpoint | Outers | Rejects | Schur products | Target hit | Native seconds |
|---|---:|---:|---:|---:|---:|---:|---:|
| Venice-52 | 5 | 246336.9465235868 | 102 | 2 | 359 | 0/5 | 2.505--2.538 |
| Final3068 | 5 | 1783291.8357667031 | 121 | 25 | 472 | 0/5 | 13.235--13.292 |

The endpoints are not algorithm promotions.  Fixing floating-point reduction
order chooses one reproducible trajectory, and on these two scenes that
trajectory misses the registered targets.  Its purpose is experimental:
different deterministic input perturbations can now represent distinct basin
draws, while a control and intervention evaluated on the same perturbation
have common random numbers and differ only because of the intervention.

## Localisation sequence

- D0v1 fixed normal assembly, point-side Schur accumulation, nonlinear cost,
  and full-model sums.  It failed because cuBLAS dot/norm reductions varied in
  the last bits.
- D0v2 fixed every source-level cuBLAS dot and norm.  It failed because the
  small-scene reduced-RHS path and accepted point-step path still used atomic
  sums.
- D0v3 made those two paths camera-owned and point-owned.  Numerical output
  became exact across all repetitions.

The first D0v3 summary failed only because the parser hashed the terminal
`POINT_SAFE summary ... seconds=` wall-time line.  The registered object was
the normalized per-attempt decision trace.  The correction excluded that
timing-only summary without rerunning any numerical row; it is documented in
`D0V3_HARNESS_AMENDMENT.md`, and the pre-correction summary is retained.

## Consequence for subsequent campaigns

Identical repeated runs no longer estimate tail reliability under this build;
they repeat one basin.  D1 must use a preregistered family of deterministic,
small input perturbations and compare algorithms pairwise on each member.
Discordant target hits feed the registered sequential probability-ratio test;
paired time and endpoint deltas are reported in both directions.

Machine-readable evidence: `d0v3-registration.json`, `d0v3-results.json`,
`d0v3-summary.json`, and `d0v3-summary-pre-normalization.json`.
