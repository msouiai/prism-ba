# Final13682 extension — 10 September 2026

**Eta2 remains the incumbent. The coarse variant ties at both fixed targets,
because its correction never activates in this short largest-scene test.**
This is evidence about the tested prefix, not a refutation of coarse methods
on every large or poorly conditioned BA problem.

The scene has **13,682 cameras, 4,456,117 points and 28,987,644 observations**.
Both arms use the same previously measured `prism-coarse` binary and frozen
eta2 flags; only `OCA_COARSE_RANK=0/16` changes. No recompilation or retuning.
GPU runs were serialized. The [protocol](LARGEST_PROTOCOL.md) was recorded
before execution and retained with the raw evidence.

## Native time to identical target

Targets come from the earlier sustained-eta2 protocol, not today's endpoints.
N=3 alternating pairs at each target, with all repeats retained. Times are
native TARGET events, excluding input loading and terminal reporting.

| Target | Eta2 median [min, max] | Rank16 median [min, max] | Outers, each | Products, each | Hits |
|---|---:|---:|---:|---:|---:|
| Primary: 27,591,576.557625167 | 3.2455 [3.2433, 3.2463] s | 3.2428 [3.2365, 3.2434] s | 4 | 19 | 6/6 |
| Tighter: 27,318,392.631312046 | 4.1234 [4.1182, 4.1282] s | 4.1164 [4.1125, 4.1199] s | 5 | 21 | 6/6 |

Zero rejects and zero coarse activations in all 12 runs. Relative median
timing differences are only -0.08% and -0.17%, so both comparisons are ties.
Median endpoint objectives are approximately 27.423M at the primary target
and 26.557M at the tighter target. The extra fifth outer overshoots the
tighter target; no interpolated crossing time is used.

Sampled peak GPU memory was 6,810 MiB for eta2 and 6,908 MiB for rank16,
comfortably within the 16 GiB device. Memory was sampled through driver
queries at half-second intervals and is not a guaranteed instantaneous peak.
Both arms used the same monitoring. Rank16's allocated coarse workspace is
approximately 91 MiB; allocator/context accounting explains why the observed
difference need not exactly match that amount.

Each process took roughly 22 seconds because the 1.46 GiB text input must
also be loaded and parsed. Those costs are outside the native solver metric.
There is no new CPU endpoint audit in this extension; costs use the unchanged
native objective evaluator in the same binary and configuration as the
preceding experiment. Caspar was not rerun, so this is not a fresh Caspar
speed comparison.

## Deeper activation probe

One pair continued without a target, with a 12-native-second budget and a
30-outer maximum. Both reached 14 committed outers and used 43 matrix
products, with zero rejects. The maximum observed prior CG depth was seven,
below the registered activation threshold of 16. The correction again never
activated, so the prospective conditional expansion to N=3 was not needed.

| Arm | Endpoint objective | Reported native seconds | Coarse activations |
|---|---:|---:|---:|
| Eta2 | 24,892,269.918 | 12.6969 | 0 |
| Rank16 | 24,880,149.708 | 12.2940 | 0 |

These are **capped N=1 diagnostics, not equal-quality speed measurements**.
The solver checks its budget at safe boundaries; completion/reporting can
therefore exceed 12 seconds. The small endpoint difference and different
point-safeguard/backtracking counts cannot be attributed to an active coarse
inverse. Extra history collection changes execution ordering even when the
correction is gated off, and floating-point trajectories need not remain
identical. They do not justify a performance claim.

This prefix does not show a need for deeper Schur solves. Testing stronger
preconditioners here for longer solely because the dataset is large would
not follow the evidence from this gate.

## Separate curvature transfer observation

One additional run used the previously built extended terminal-probe binary,
with gradient diagnostics enabled, the same 12-second/30-outer cap, and no
target. It stopped on its budget after 14 outers at cost 24,894,330.222.
It did not declare convergence. Its timing is excluded from the table above.

At that state:

- The normalized undamped gradient energy is 0.01014.
- Current camera lambda and last point damping are both approximately
  1.65e-7, unlike the enormous point damping seen at the Final3068 v2 stalls.
- The first diagonal-gradient trial, alpha=1/12, passes the true-cost Armijo
  check and would reduce cost to 24,858,303.520: **36,026.702 units, or 0.145%**.
- The complete terminal probe, including diagnostic finite differences,
  takes 0.247 s. This is not a measured recovery implementation cost or a
  time-to-target improvement. The final solver state is never replaced.

True directional curvature divided by the analytic GN upper bound:

| Finite-difference epsilon | Ratio |
|---|---:|
| 1e-4 | 0.29145 |
| 1e-5 | 0.29175 |
| 1e-6 | 0.41430 |
| 1e-7 | 10.6955 |
| 1e-8 | 1143.31 |

The largest two scales agree closely, with first-derivative errors below
4e-7 relative. The estimates deteriorate at tiny scales where subtracting
nearly equal costs amplifies numerical error; the final row must not be
reported as a thousand-fold curvature pathology. Unlike the Final3068
examples, this endpoint admits the initial gradient scale and does not show
a stable extreme curvature excess. One sampled budget endpoint cannot rule
out a different regime later in the solve.

The contrast supports **state-dependent** curvature diagnostics: neither
dataset size nor a universal damping reset identifies the difficult regime.
The next mechanism study should still localize the extreme Final3068
residual-curvature contributions before changing the champion globally.

## Evidence and reproduction

All 15 solver processes exited successfully. The 12 target runs and two
activation runs used 69.687 reported native seconds in total; the separate
instrumented diagnostic added 12.841 seconds. No full states or Schur
matrices were exported. Original source and defaults remain unchanged.

- [largest_summary.json](largest_summary.json): every run and aggregate.
- [evidence/largest-raw.tar.xz](evidence/largest-raw.tar.xz): raw traces,
  commands, flags, input/binary fingerprints, protocols and diagnostic rows.
- [evidence/largest-inventory.json](evidence/largest-inventory.json): archive
  and harness hashes.
- [run_largest.py](run_largest.py), [largest_curvature.py](largest_curvature.py),
  [analyze_largest.py](analyze_largest.py): reproduction and aggregation.

Build the experimental solver/probe as described in [RUNNING.md](RUNNING.md).
Use `PRISM_LARGEST_OUT` to choose a fresh output directory. Run
`run_largest.py`, then `largest_curvature.py`, then `analyze_largest.py --data`
with that directory. Existing completed cohorts are protected from accidental
overwrite. The archive alone is sufficient to regenerate the summary without
GPU execution.
