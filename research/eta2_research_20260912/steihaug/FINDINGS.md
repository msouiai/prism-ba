# Brief 3: prototype correctness gate

Date: 2026-09-12. **Correctness-ready; no BAL performance verdict. Frozen
Eta2 remains the champion.** The candidate has not run the nine-cell grid
or registered Venice/Final3068 hit-rate experiments.

## What is implemented

The isolated builder derives from frozen source SHA256
`22c18359a526526ae0a5b5109187878ab1cef33b453f6bbddc2aa92597a607d8`,
verifies all 44 header hashes, and makes 17 exact substitutions. Reversing
them recovers the frozen source byte-for-byte. The built prototype SHA256 is
`d633bae5a855cd7c9f0aaa6e51a63f9befa5c6766aa1b3649e157f6943fcf699`.
Build command and local header hashes are in [build_manifest.json](build_manifest.json).

The STCG arm truncates at the M-norm boundary along the current PCG search
direction and uses that same actual factored preconditioner metric for final
rescued-camera acceptance. Finite curvature-cutoff events propose a boundary
step and skip the persistent numerical floor. The full objective, residual
forcing, nonlinear safeguards and acceptance threshold stay as specified in
the [protocol](PROTOCOL_DRAFT.md). The optional model-progress stop is omitted.

The initial ordinary solve bootstraps the radius from its M-norm. A cutoff
before bootstrap has an explicit preconditioned-gradient radius fallback.
Between attempts the radius scalar is interpreted in the newly factored
metric. This is a variable-metric policy, not a fix that preserves an old
physical ellipsoid; a later gain cannot automatically be attributed solely
to truncation rather than the changed metric or floor response.

Both derived arms support a common buffered host attempt trace with no
added CUDA call/barrier. Its RAII scope includes numerical-repair continues.
It separately reports retry-entry wall, unsuccessful-attempt wall, numerical
repair wall, PCG iteration count, all Schur products, and cutoff acceptance.
The trace's buffering/output overhead is part of native solve wall.

## Completed checks

| Check | Result |
|---|---|
| Interior SPD PCG vs dense solve | Relative direction error 1.21e-13; true residual 1.97e-12 |
| Boundary PCG vs whitened-coordinate CG | Four radii, direction agreement within 1.76e-12; M-radius errors <=2.23e-16 |
| Scalar boundary equation | 1000 random cases over 140 decades; max radius error 3.34e-16 |
| Curvature branch | Indefinite toy and strictly SPD 1e-18-curvature toy both handled as cutoff events |
| Actual GPU M-Gram kernel | 257 camera blocks, relative error 1.90e-16 vs long-double CPU; memcheck 0 errors |
| Tiny BAL off/STCG | Both memcheck 0 errors; original full cost independently audited; all accepted STCG steps inside M-radius |
| RAII attempt trace | Numeric continue, rejected continue and accepted break retained; no CUDA calls |
| Source-off Dubrovnik88 N=3 | All six runs 33 outers; median endpoint change +0.0000207% |

Finite arithmetic slightly violates exact-arithmetic M-norm monotonicity in
the converged SPD CPU case (minimum squared-norm relative increment -3.07e-9).
The implementation therefore measures the Gram products directly instead of
assuming a norm recurrence remains exact. A positive SPD test still trips
the native cutoff, so `curvature_cutoff` does not mean a genuine saddle.

The tiny eight-outer fixture exercised two actual radius-boundary steps,
both accepted, and a nonlinear backtrack. Off/STCG used 35/32 Schur products
and 26/25 PCG iterations; both made eight accepts and one reject. Their costs
were 3.1722010 / 3.0610009 from score_init 364516.1939041. These are a single
synthetic correctness case under memcheck, **not a speed or quality claim**.
Neither tiny run had a numerical cutoff, so only the linear and metric tests
cover that branch so far.

Source-off compatibility endpoints:

| Rep | Frozen original | Derived disabled | Original / disabled Schur products |
|---|---:|---:|---:|
| 0 | 358945.1132065 | 358945.1874776 | 125 / 125 |
| 1 | 358944.9215233 | 358946.2963732 | 125 / 129 |
| 2 | 358947.3889093 | 358944.6535891 | 133 / 125 |

All score_init values agree to approximately 1e-8 absolute at 30,562,787.8472.
This passes the registered compatibility threshold but is not bit identity
or a timing comparison. Derived trace acceptance and Schur-product totals
match the solver's native summaries. Raw logs, commands, flags and compact
results are under [results/](results/); saved states are under ignored build/.

## Next gate

Freeze the parent's one global STCG configuration/grid manifest, then test
the same nine target cells and the Venice/Final3068 hit-rate targets. Count
all metric work. The direct Gram kernel plus host copy adds one synchronization
per PCG iteration, so the wall test can reject this implementation even if
it reduces products. No speed prediction is warranted from correctness alone.
