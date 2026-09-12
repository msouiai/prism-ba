# D5 result: a fixed narrow band is not supported across sequence BA

## Verdict

The registered structural gate fails, so no native banded preconditioner was
built.  None of the four sequence-family scenes retained 80% of normalized
camera coupling inside RCM half-bandwidth 16.  The actual Venice52 Schur matrix
also retained only 70.85% of its off-diagonal Frobenius energy at that band.

There is a real small-scene spectral signal: the RCM-16 truncation is SPD and
improves the generalized condition number by 14.0x relative to Eta2's Hcc
block preconditioner; RCM-32 retains 93.54% of off-diagonal energy and improves
it by 106.6x.  This does not satisfy the registered cross-sequence premise and
does not override wave 5's native finding that a stronger Schur-Jacobi
preconditioner changed the finite Krylov iterate and harmed nonlinear target
time and tail reliability.

## Graph locality

The table reports the track-normalized clique-expansion mass inside bandwidth
16 and the minimum bandwidth containing 80% of that mass.

| Scene | Cameras | Natural @16 | RCM @16 | Natural width-80 | RCM width-80 |
|---|---:|---:|---:|---:|---:|
| Ladybug539 | 539 | 51.76% | 58.49% | 60 | 82 |
| Ladybug1197 | 1,197 | 55.14% | 49.03% | 52 | 138 |
| Venice52 | 52 | 52.48% | 60.86% | 29 | 25 |
| Venice951 | 951 | 14.47% | 28.40% | 216 | 215 |
| Final3068 control | 3,068 | 11.20% | 12.55% | 1,711 | 667 |
| Muell production control | 493 | 77.69% | 64.89% | 19 | 33 |

Natural camera order is useful on Ladybug and Muell, but there is no single
fixed RCM rule that improves every ordered family.  At bandwidth 32 the RCM
fractions are still only 68.69%, 58.33%, and 37.17% for Ladybug539,
Ladybug1197, and Venice951.  A bandwidth wide enough to cover those scenes
loses the formation, storage, and factorisation advantage that motivated the
proposal.  Final3068 behaves as the intended unordered control.

Raw shared-track weights give the same qualitative conclusion.  Normalising
each track by `1/(m_j-1)` actually makes Ladybug look more local, so the failure
is not caused by a few long tracks dominating the raw clique expansion.

## Fixed-state numerical audit

The existing Venice52 outer-39 capture has 52 cameras, 64,053 points, 347,173
observations, and damping `lambda=1e-8`.  The analysis losslessly restored the
captured FP64 cross blocks and point factors, formed

`A = E(Hcc - W V_tau^-1 W^T)E + lambda I`,

and then deleted the temporary raw files.  The dense action agrees with the
saved independent matrix-free product to `7.44e-11` relative.  The matrix
eigenvalue range is `9.9999995e-9` to `4.47694`, as expected for a damped
near-gauge system.

| Preconditioner | Off-diagonal energy retained | Generalized condition | Improvement vs Hcc |
|---|---:|---:|---:|
| Eta2 Hcc blocks | n/a | 1.1080e8 | 1.0x |
| Schur-Jacobi | n/a | 2.0662e7 | 5.36x |
| Natural band 16 | 54.27% | 9.9491e6 | 11.14x |
| RCM band 16 | 70.85% | 7.9035e6 | 14.02x |
| Natural band 32 | 83.68% | 2.8808e6 | 38.46x |
| RCM band 32 | 93.54% | 1.0396e6 | 106.58x |

Every listed band truncation was SPD without a diagnostic shift.  This proves
that band structure can be a strong fixed-system preconditioner on Venice52.
It does not prove a native convergence gain: Schur-Jacobi already improved the
same linear object and then lost natively, and the larger sequence scenes need
far wider bands.

## Decision and reusable result

All three registered premises were required.  The SPD and 3x conditioning
premises pass; the cross-scene graph-locality and Venice energy premises fail.
The result is therefore a scoped mathematical lead rather than an Eta2
candidate:

- a band-32 direct/preconditioned solve may be useful for a separately named
  small ordered-scene solver;
- an Eta2 run-everywhere change would need an in-run structural gate and a
  nonlinear step-equivalence contract, neither of which exists;
- RCM is not a safe universal ordering for these BA families.

Machine-readable results, hashes, ordering fingerprints, spectra, and all band
fractions are in `d5-band-results.json`.  The immutable rules are in
`D5_BAND_PROTOCOL.md`.
