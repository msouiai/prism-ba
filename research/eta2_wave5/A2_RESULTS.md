# A2 adaptive robust-exit result

The preregistered adaptive exit fails its tail gate.  The practical panel was
therefore skipped.

| Scene | Arm | Hits | Conditional target time, median [range] | Endpoint median [range] | Rejects, median |
|---|---|---:|---:|---:|---:|
| Final3068 | frozen/off | 6/10 | 3.869 [2.582, 5.433] s | 1,744,558.34 [1,736,711.54, 1,954,908.35] | 4.5 |
| Final3068 | adaptive robust exit | 5/10 | 5.219 [2.096, 7.338] s | 1,782,098.29 [1,733,632.57, 1,885,765.83] | 13.5 |
| Venice52 | frozen/off | 0/10 | — | 246,335.15 [244,948.84, 247,590.86] | 7.0 |
| Venice52 | adaptive robust exit | 0/10 | — | 255,399.78 [255,394.70, 255,416.33] | 6.0 |

The adaptive arm normally exits at the transition to robust stage 2 after
seven weight-count checks.  The checks, including their device work and host
scalar transfer, are charged.  Off-mode compatibility with the parent O5
binary is `4.7e-15` relative at the median over three paired runs.

The mechanism is a negative result: the instantaneous fraction of observations
with Cauchy weight below 0.5 does not say that the robust opening has finished
its basin-selection work.  Leaving after four robust accepts sends all ten
Venice trajectories to a tightly clustered endpoint 3.68% above the control
median and loses one Final3068 hit.  Thus the fixed robust schedule's later
stages are trajectory-shaping rather than removable overhead.  No champion
change is made.

All 40 endpoints were independently rescored in FP64.  The compact evidence
keeps exact endpoint hashes, curves, logs, attempt traces, source/build hashes,
and manifests in `a2-tails-results.json` and `evidence/a2-tails/`.
