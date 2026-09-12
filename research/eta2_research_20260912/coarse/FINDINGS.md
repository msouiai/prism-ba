# Brief-0 coarse projection pre-test

Seven primary native witnesses; three separately computed reference directions per witness. These are projections, not optimizer rollouts or independent hit-rate repetitions. All captured reference records pass their reduced-system certificate; this is not a full-normal certificate. Some original full-normal checks failed, with failures and supplementary Venice point completions preserved in the main audit. Native inputs were not changed.

| Witness | K=8 rank | Reduced-certified reference minus raw Eta2 | After global removal | Equally clipped comparison |
|---|---:|---:|---:|---:|
| final-3068-capture-0 | 50 | 1.319% | 0.786% | 1.319% |
| final-3068-capture-5 | 50 | 12.584% | 1.258% | 12.600% |
| final-3068-capture-6 | 50 | 1.764% | 1.698% | 1.799% |
| ladybug-1197-capture-0 | 56 | 10.359% | 10.359% | 10.359% |
| venice-52-capture-0 | 54 | 88.393% | 85.624% | 88.393% |
| venice-52-capture-1 | 54 | 87.318% | 74.224% | 92.647% |
| venice-52-capture-2 | 54 | 81.386% | 80.794% | 81.386% |

The registered all-witness/all-K <25% kill condition is not met. Venice has substantial coverage already at K=8, with ranks54 of312 extrinsic camera dimensions; its after-global-removal raw fractions remain74–86%. This justifies the next spectral/model-usefulness pre-test, not a solver promotion.

Final3068 witness0 has a raw difference norm only about2.1e-10 and equally clipped difference about5.4e-12. Its normalized fractions are numerically sensitive and must not be interpreted as substantial missing work. The main native diagnostic also finds essentially identical useful clipped steps on Final3068. Final0/5/6 K8 partitions contain a dominant cluster and singleton outliers; their very different coverage demonstrates why center clustering is only one proposed basis.

Venice K=128 caps to52 and rank312, spanning essentially the complete extrinsic camera space. Those high fractions do not demonstrate an economical coarse level. Intrinsic components remain outside all these rigid bases. Full K8/32/128 ranks, singular values, memberships, actual CPU overhead, reference repetitions and certification records are in audits/*.json and projection_summary.json.

A first implementation subtracted absolute transformed translations when forming finite differences. Extreme Final camera coordinates produced up to6.5e-5 closed-form discrepancy. The identical finite translation increment is now evaluated algebraically, with no change in epsilon, clustering or metric. Closed-form errors across all seven witnesses are below1.67e-11; first-pass records remain in audits/first-pass for transparency. The corrected global-basis containment errors are reported in every cell.

The follow-up [Venice0 spectral pre-test](SPECTRAL_FINDINGS.md) is now complete.
It supports a camera coarse-space experiment while retaining the original
point-parity failure and supplementary full-normal completions explicitly.
That pretest was followed by the [native additive arm](native/VERDICT.md), which did not improve target reliability. A later [covisibility-partition control](graph_pretest/FINDINGS.md) improves coverage on some Final witnesses without establishing nonlinear usefulness or a native graph-preconditioner result.
