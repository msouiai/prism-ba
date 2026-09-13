# D12 result: Nyström is dominated; restart-at-8 is the discovery

## Verdict

The randomized Nyström correction is rejected.  On Muell outer 12, every
delayed rank reaches the forcing gate after the same 13 PCG iterations and 15
solve products as a rank-zero restart at iteration 8.  Ranks 4, 8 and 16 add
respectively 4, 8 and 16 sketch products and raise median wall from 46.51 ms
to 59.88, 73.62 and 104.56 ms.  The low-rank factors change the final residual
slightly but save no Krylov work.  Starting with Nyström is worse: rank 4 needs
47 iterations versus frozen Hcc's 41, and higher ranks need 42--47.

The attribution control is a positive result deserving its own native gate.
A plain, mathematically valid PCG restart from the exact current residual at
iteration 8 reduces the identical fixed solve from 41 iterations / 42 products
/ 130.35 ms to 13 / 15 / 46.51 ms.  The extra product explicitly recomputes
the current residual before the restart.  It leaves the shallow Ladybug and Final
controls untouched because they finish before the trigger.  This is a 64.3%
wall reduction and 64.3% product reduction without changing the matrix,
preconditioner, RHS, forcing threshold, or accepted linear-residual criterion.
It is not yet a BA speed claim: the native nonlinear trajectory and the set of
triggered solves remain unmeasured.

## Fixed-system rows

All values are N=3 medians after one process-level warm path; true residuals
are recomputed with the unchanged matrix-free operator.

| Muell arm | Iterations | Solve products | Sketch products | Total products | Wall |
|---|---:|---:|---:|---:|---:|
| Frozen-equivalent Hcc | 41 | 42 | 0 | 42 | 130.35 ms |
| Restart Hcc at 8 | **13** | **15** | 0 | **15** | **46.51 ms** |
| Nyström rank 4 from start | 47 | 48 | 4 | 52 | 163.67 ms |
| Nyström rank 4 after 8 | 13 | 15 | 4 | 19 | 59.88 ms |
| Nyström rank 8 after 8 | 13 | 15 | 8 | 23 | 73.62 ms |
| Nyström rank 16 after 8 | 13 | 15 | 16 | 31 | 104.56 ms |

All rows hit the same `eta=0.5` true-residual gate.  The uninterrupted median
is `0.49729670082728`; restart-only is `0.47888588637639`.  Nyström factor
interpolation residuals are `1e-15`--`1e-14`, all retained eigenvalues lie in
`[0.446, 0.544]`, and no SPD repair or negative curvature occurs.  The sketch
is implemented correctly; it simply does not capture a useful low-dimensional
near-unit subspace at these ranks.

Ladybug completes in two iterations / three products and Final1936 in one / two
under every delayed arm.  No sketch or restart fires, satisfying the locality
gate exactly.

## Why the restart helps

PCG chooses the degree-k residual polynomial that minimizes the energy norm of
the error over one growing Krylov space.  Eta2 stops on a different quantity,
the Euclidean norm of the explicitly recomputed residual.  That norm need not
decrease monotonically under CG.  Restarting discards conjugacy and begins a
new polynomial from the current residual; it can therefore reach this loose,
different norm criterion much sooner even though it cannot improve CG's
energy-minimization theorem.  The fixed Muell result is an extreme instance of
this objective mismatch.

The next experiment must compare restart locations and a Krylov method that
directly minimizes residual norm, then integrate only one preregistered rule.
Periodic restarting is standard numerical linear algebra, not a novelty claim.
The potentially publishable result would be the forcing-metric mismatch and a
GPU BA policy that turns it into measured time-to-target improvement.

## Boundary and provenance

Frangella--Tropp--Udell Nyström PCG is designed for regularized PSD systems.
D12 instead sketches the point-coupling `G` in `I-G`; this sign adaptation is
necessary for Hcc-preconditioned BA.  Eta2 has coupled `tau=lambda`, so the
sketch cannot be reused across retry shifts as the categorical brief proposed.

The preregistration, source, exact rows, hashes and gate decisions are in
`D12_NYSTROM_PROTOCOL.md`, `d12_nystrom/`, and
`d12-nystrom-results.json`.  The frozen champion is unchanged.
