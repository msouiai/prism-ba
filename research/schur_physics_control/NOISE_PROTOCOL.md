# Final13682: distributed initialization noise

Registered before the first noisy solver run. This is a bounded stress screen,
not a new solver selection or a confidence interval from timing repeats.

- Scene: Final13682, SHA256
  `76ef34416fdca524b1ec6755b62ab33cba15c8b5b830b5ff38369c8cd609d736`.
- Keep every observation and all initial intrinsics unchanged. Perturb angle-axis
  coordinates, camera centers, and points with independent zero-mean Gaussian
  draws. The unscaled component standard deviations are 0.001 radians and
  0.001 times the median centered point radius for positions. Recompute camera
  translations as `t = -R C`. Angle-axis coordinate noise is chart-dependent;
  it is not claimed to be an isotropic rotation distribution.
- Seeds 17, 29, 43. Use the same Gaussian draws at two amplitudes: calibrate to
  0.25 and 1.0 pixels median projected displacement on a fixed uniform sample
  of 200,000 observations, sample seed 1907. Compute and report full-scene
  displacement percentiles, objective, finiteness, and depth-sign changes.
  Do not discard seeds or globally shrink noise to hide depth-sign changes.
- This differs from the old 1.1x-RMS experiment: that perturbation moved the
  median observation only around two to three millionths of a pixel. Sensitive
  observations dominated the calibration. The new levels stress broad changes
  and may also expose projection singularities; report those limitations.
- Both arms use the identical existing `prism-coarse` binary and frozen eta2
  flags. Only `OCA_COARSE_RANK` differs: 0 or 16. Retain the existing activation
  threshold (previous CG depth at least 16). No intervention is forced on.
- Fixed target: 27,318,392.631312046, the earlier tighter clean-scene target.
  Observations/objective are unchanged, so retain this absolute target. Budget:
  12 native seconds and 600 outer iterations, 120 seconds process timeout.
  Total maximum registered native budget: 144 seconds for 12 runs, with possible
  one-attempt overshoot due to the existing solver's budget-check granularity.
- One run per arm per noisy input. Three independent initialization seeds per
  level, not three timing repetitions of an identical input. Alternate arm
  order by seed and level. Serialize GPU work through `/tmp/prism_gpu.lock`.
- Record final cost, native seconds, target time/hit, rejects, matvecs, coarse
  activation and prior CG depth. Keep every miss, error and timeout. A target
  event after the native deadline does not count as a hit within budget.
- Curves show actual logged accepted states, using the unchanged CSV elapsed
  clock (after solver setup). Native target timings are reported separately.
  Do not interpolate target crossings or extend a stopped curve. Historical
  Caspar runs used clean initialization, so omit them from this noisy comparison.
- Use one automatically cleaned temporary BAL in `/dev/shm`, shared by both
  arms. Read it back to verify every parameter and observation prefix, and hash
  the entire file before solving. Archive generator, versions, seed/amplitude,
  input hashes and logs so large disposable input copies are unnecessary.

The unchanged eta2 configuration remains the incumbent unless the correction
activates and produces repeatable gains at equal objective. A tie while inactive
does not validate or refute the correction in deeper-CG regimes.
