# B0 phase profile results

The untouched frozen Eta2 binary was profiled on all nine registered practical
target cells, three repetitions per cell.  All 27 runs reached their targets.
The binary, source, inputs, flags, and protocol are hashed in
`b0-registration.json`; independently audited endpoint hashes are recorded in
the per-run records before the temporary states are removed.

Across 4.8298 seconds of native solve time, the instrumented phases were:

| Phase | Seconds | Native wall | Timed-phase sum |
|---|---:|---:|---:|
| Krylov | 2.569 | 53.19% | 65.08% |
| Assembly | 0.630 | 13.04% | 15.96% |
| Point factor + reduced RHS | 0.505 | 10.46% | 12.79% |
| Backtracking | 0.1226 | 2.54% | 3.11% |
| Candidate/scoring wrapper | 0.121 | 2.51% | 3.07% |
| Unaccounted | 0.8822 | 18.27% | — |

The timer synchronizations perturb wall time, so these are diagnostic shares,
not additional speed samples.  The unaccounted fraction bounds controller,
allocation, transfer, launch/synchronization gaps, and incomplete timer
coverage; it is not attributed to launch latency without an end-to-end trace.

The result selects B3 Schur-Jacobi as the first speed implementation.  It also
sets a low ceiling on candidate-only optimization: even eliminating that
measured phase entirely could save only about 2.5% of native wall here.  The
Krylov share is especially large on Trafalgar-138: the three targets require
medians of 594, 462, and 232 matvecs and spend 0.256, 0.188, and 0.094 seconds
in Krylov respectively.
