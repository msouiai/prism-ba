# O2 handoff to parent

Ready for the parent's registered O2 comparison; no scored O2 BAL arm was run.
The frozen champion remains unchanged.

Binary: `o2/build/prism-o2`, SHA256
`4b05ad4ee261e7a346dbf43cfc0d207366bdf7544734b31b288c10f4bbcdbd10`.
Enable `OCA_O2=1` with the exact champion.json environment and ordinary
SIMPLE_RADIAL CLI. Do not enable the tiny-only `OCA_O2_AUDIT` in the grid.
Use `build_manifest.json`, `validation_manifest.json`, `tests.json`, `README.md`
and `MATH_AND_COVERAGE.md` for provenance, supported flags, clocks and limitations.

All correctness gates passed on this binary:

* 96 CPU derivative cases; worst relative finite-difference error 6.11e-11.
  Shared C++ projection versus independent NumPy: 3.64e-16.
* Actual native assembly, stage cost, full joint GN prediction, point normal
  solve and exact point masks checked at all six stages. Maximum native RHS
  discrepancy 8.02e-14; model discrepancy 6.04e-15; point solve 3.11e-16.
* Both on/off memcheck: zero errors. Tiny exported endpoint independently
  rescored at original L2 = 0.9670273344165908, consistent with native RESULT.
* Original/off N=3 Dubrovnik-88 compatibility passed. The original control had
  one 31-outer run and two 33-outer runs; all off runs used 33 outers. Preserve
  that variation rather than claiming iteration-level identity. Exact costs
  and times, medians and ranges are in `validation_manifest.json`.
* Wave and work traces agree row-for-row on every derived-binary check. The
  ordinary tiny audit exercised three actual numerical-repair continuations;
  their damping, forcing, unchanged costs and unmeasured fields were checked.
* Stage-cap edge case: exactly 18 failed surrogate attempts, then direct s=1
  with no state rollback. It records an incomplete opening and only then emits
  a target hit. A one-outer staging stop emits no hit even with original cost 0.

The source overlay has 32 reversible substitutions across the CU source and
two local header copies. The frozen source plus 44 headers were verified in
session. It covers projection assembly/statistics, all enabled cost/backtrack
paths, full-model prediction, point safeguards, factors/RHS refresh, stage-local
stopping histories, original-score logs and target gating. Surrogate changes
reset numeric caches and objective histories, while current lambda/radius/floor,
cumulative work and warmup count persist. The environment whitelist rejects
unsupported paths such as replay, robust objectives and additional solver knobs.

Use native `solve_seconds` from the target-stopping invocation for charged
time-to-target including cleanup. The internal `TARGET` timestamp precedes
cleanup, as in frozen Eta2. Legacy CSV wall starts after setup; it must not be
the charged metric. CSV and JSON costs are original L2; optional RLD logs remain
internal stage quantities and require the O2 stage trace when interpreted.

## Wave harness integration

Set both `OCA_WAVE_TRACE=.../wave.json` and
`OCA_STCG_ATTEMPTS=.../attempts.json`, as shared `N.run` does. O2 recognizes
`OCA_WAVE_TRACE` explicitly; failure to open its output file is fatal. Enabled
O2 rejects unsupported ambient flags. The common `attempt_trace.h` is unchanged
(SHA256 `43400101d54c0ccf94464025497105ef825e16c7e7cbb1d21f7dff019619daf6`).
No additional GPU copies, reductions, projection or synchronization were added.

`wave.json` is a **top-level JSON array**, one row per common attempt-clock
scope. This includes numerical continuations; `outer`/`retry` may repeat when
the damping repair continues before an ordinary retry. Stage transitions or
target hits before an actual solve create no attempt in either file.

| Fields | Meaning |
|---|---|
| `outer`, `retry`, `accepts_before` | Native zero-based outer, retry index and accepted-outer count at entry. |
| `lambda`, `tau`, `eta` | Actual damping, point damping and forcing tolerance passed to this PCG solve. |
| `radius_before` | Radius entering the attempt, possibly zero before initial bootstrap. |
| `raw_norm`, `raw_radius_ratio` | Existing camera CG norm before radial clipping, and its ratio to positive `radius_before`. |
| `rho` | Native controller ratio (including its `-1` rejected/ineligible sentinel), or null if scoring was never reached. |
| `pcg_iterations`, `accepted`, `numeric_repair`, `curvature_cutoff` | Exactly the corresponding common work-trace values. |
| `observed` | True when the existing finite pre-clipping raw norm was reached. |
| `gauge_fraction`, `top5_fraction`, `gauge_measured`, `gauge_seconds` | Null, null, false, 0: gauge composition is **not measured**. |
| `stage` | O2 surrogate parameter; off mode is 1. |
| `radius_effective`, `effective_raw_radius_ratio` | Radius after initial bootstrap and norm ratio to that radius. |
| `lambda_after`, `radius_after`, `numeric_floor_before`, `numeric_floor_after` | Controller values before/after scope termination, including repair continuations. |
| `cost_stage_before`, `cost_stage_after` | Internal stage objective at attempt entry/exit. |
| `cost_original_before`, `cost_original_after` | Full original L2 at attempt entry/exit. |

Unreached or nonfinite floating quantities are JSON null. In particular, a
numerical continuation before scoring has null `raw_norm`, ratio and `rho`,
`observed=false`, unchanged costs, and its updated damping/floor; it never
inherits the preceding attempt's ratio. On the first bootstrap attempt,
`raw_radius_ratio` is null if the entering radius was zero; use the explicitly
named effective ratio if that diagnostic is wanted. These distinctions must
survive aggregation: do not treat missing gauge fractions or raw norms as zero.

The trace also works without `OCA_STCG_ATTEMPTS`; the recorded validation uses
both files to establish exact row/flag/work parity, matching the shared harness.

Mathematical negatives are explicit: s=0 is nonconvex under distortion, equal
initial costs do not give equal gradients, signed denominator interpolation can
introduce a pole, and the CIESTA convergence result does not apply. Full
Christy–Horaud1996 and Oliensis–Hartley ECCV2006 were read. The TPAMI2007 extension
was identified and its abstract read, but its full text was unavailable.

No scored BAL rollout, retuning, chart substitution, GPU portfolio or novelty
claim is included. Primary PDFs
and parser packages live locally under ignored literature/build paths; public
URLs and hashes are retained. All created/modified files are inside `o2/`.
