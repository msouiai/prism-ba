# B6v7 Final3068 non-inferiority extension

Registered and committed before any extension run.

## Frozen inputs

- Binary: `research/eta2_wave5/build/prism-b6v7`, SHA-256
  `b1b125b55a5d4ff1415fd379a8fee269609f42dffe9409fe0f9b831e41629799`.
- Parent B6v7 protocol SHA-256:
  `115226c65db0412fbb7ab19532fe55a967f75ba4351e03b09d81997373877593`.
- Existing pooled N=20-per-arm rows SHA-256:
  `1383186b39aed663e0867799e62121573c4d87c48b5bdc771c8de51ece085b1c`.
- Scene and target: Final3068 at `1744796.9841897595`, with the frozen Eta2
  flags and caps inherited from `b6v7-registration.json`.
- Arms: `dots` and the fixed `ncam >= 128` `gated` rule, exactly as in B6v7.

## Sample size and execution

The existing cohort has 20 runs per arm.  Add 130 fresh runs per arm, in
alternating order, for a fixed total of 150 per arm.  There is no early stop and
no parameter change.  At hit probability near 0.6, an equal-arm normal power
calculation gives about 132 runs per arm for 80% power at a 15-percentage-point
non-inferiority margin; 150 allows modest variance and discreteness overhead.

Every run retains its miss, native wall, conditional target crossing, endpoint,
products, outers, rejects, source log and hashes.  The fresh and pooled results
are both reported.

## Registered decision

Let `d = p_gated - p_dots`.  Compute the one-sided 95% Newcombe-Wilson lower
confidence bound for the difference of independent proportions, using one-sided
Wilson component bounds with `z = 1.6448536269514722`:

`lower(d) = d - sqrt((p_gated - L_gated)^2 + (U_dots - p_dots)^2)`.

Declare hit-rate non-inferiority only if `lower(d) > -0.15`.  Also report
two-sided 95% Wilson intervals for each hit rate, the two-sided Fisher exact
test, conditional target-time median and range, all-run native wall mean and
median, endpoints, products, outers and rejects.

Passing permits B6v7 to become the wave-5 optimized Eta2 candidate.  It does
not prove equality, superiority, or applicability to another GPU.  Failing
keeps dots-only as the implementation winner and closes the camera-reduction
promotion attempt.
