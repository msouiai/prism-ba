# Final3068: uncertainty and interpretation

These calculations describe the completed samples; they were not a preregistered hypothesis test or power calculation.

| Arm | Observed hits | Pointwise Wilson 95% interval |
|---|---:|---:|
| Eta2 | 8/10 | 49.0–94.3% |
| MFREE deep | 5/10 | 23.7–76.3% |
| MFREE base | 0/10 | 0.0–27.8% |
| Ceres dogleg | 2/3 | 20.8–93.9% |
| Ceres LM | 0/3 | 0.0–56.1% |
| Caspar32 each Final3068 profile | 0/3 | 0.0–56.1% |

The post-hoc one-sided Fisher exact p-value for Eta2 8/10 versus MFREE-deep 5/10 is 0.174923. The observed ordering does not establish greater population success probability. These runs also come from different hosts. Do not call 0/10 a zero success probability. If the probability were .2, seeing zero hits in ten would have probability .1073741824.

The conditional timing columns exclude unsuccessful runs. MFREE times are full successful solves, which upper-bound their crossing times; they are not exact crossing observations. No same-host speed ratio between Eta2 and MFREE follows. Native successful-subset timing for Ceres and Eta2 is measured on the same Codex host, but a ratio conditioned on different successful subsets is not an unconditional expected runtime.

MFREE-deep has five endpoints near 1.71M and five near 2.14M. Its arithmetic median of the two central observations is about 1.925M, a value none of those runs reached as an endpoint. The raw outcomes and hit count are more informative than treating that median as a typical basin. The target stays fixed; it is not moved to accommodate any solver or noisy mode.

Wilson formula: with p=k/n, z=1.959963984540054 and d=1+z²/n, center=(p+z²/(2n))/d and half-width=z*sqrt(p*(1-p)/n+z²/(4n²))/d. Fisher probability is the exact hypergeometric upper tail with 13 total hits and ten runs assigned to Eta2. Machine-readable values are in reliability-uncertainty.json.
