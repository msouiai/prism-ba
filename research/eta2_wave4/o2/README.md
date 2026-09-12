# O2 signed-depth projection homotopy prototype

The implementation is isolated from frozen Eta2 and default-off. It changes
the opening projection model, then returns to the original objective. It is
**not yet a measured improvement** and no O2 BAL performance cohort has been run
by this agent. Parent owns the registered comparisons.

Read `PROTOCOL.md` for the fixed stage schedule, counted attempts, transition
semantics, failed-stage handling, original-objective target rule and charged
overhead. `MATH_AND_COVERAGE.md` gives the analytic derivative, counterexamples,
primary-source boundary and complete source-path coverage. Neither convexity nor
a convergence guarantee follows from this homotopy.

## Build and run contract

```
python3 research/eta2_wave4/o2/build.py --check-only
python3 research/eta2_wave4/o2/build.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 research/eta2_wave4/o2/test_projection.py
```

The binary is `o2/build/prism-o2`; enable **`OCA_O2=1`** on top of the exact
`eta2_champion/champion.json` environment. CLI remains the frozen invocation:
`--problem PATH --algo mfree_shifted_cg --dof9 --zero_k2 --lam0 0.1 --max_iter 600`.
Use `OCA_TARGET_COST` and `OCA_MAX_SECONDS` for registered targets/budgets,
`--state_out PATH` for independent original-L2 rescoring, and the exact shared
`OCA_STCG_ATTEMPTS=PATH` trace for attempt/PCG/retry accounting. Set
`OCA_WAVE_TRACE=PATH` for the shared wave harness's JSON array of lambda, radius,
raw norm ratio, eta, rho and stage/original costs. Gauge fractions are null and
explicitly unmeasured; numerical continuations retain their own rows. The full
schema and bootstrap/null conventions are in `HANDOFF.md`. Default-off does
not apply O2's environment whitelist. Enabled O2 requires the frozen flag
strings and rejects unsupported ambient experimental flags.

`build_manifest.json` records the source/config/header hashes, binary SHA,
compiler command, and inverse-patch identity. `validation_manifest.json` and
`tests.json` record completed checks. Compiler scratch is `/dev/shm`. Local
downloaded paper PDFs and build dependencies are ignored by Git; direct URLs
and PDF SHA256 values are retained in `literature/sources.json`.

## What the native traces mean

* `O2_TRACE` has `cost_stage` and `cost_original`, with target crossings up and
  down. An opening crossing is diagnostic only.
* `TARGET reached` can occur only in stage 1. Its internal crossing time includes
  O2 setup, staging, retries, transitions and original-score evaluations. Like
  frozen Eta2's hook, it precedes final cleanup. Use the target-stopping run's
  **native `solve_seconds`** for the ledger when all cleanup/deallocation overhead
  must be charged; retain the internal crossing time separately.
* `RESULT`, `RunLog`, ordinary CSV costs and JSON iteration costs are original
  full L2. The legacy CSV timer starts after initial solver setup, so it is not
  the charged time-to-target metric.
* The optional existing `OCA_RLD_LOG` observes the **internal stage objective**.
  Join it with `O2_TRACE` for stage labels; it is not the original-L2 score ledger.
* `O2_SUMMARY full_objective_entered=1` means the original objective was reached.
  It does not mean every opening stage completed. `opening_complete=0` or
  `incomplete_events>0` records an interrupted opening; `schedule_complete`
  additionally requires the two stage 1 accepts.

`OCA_O2_AUDIT=1` enables tiny-only native assembly/cost/full-model/point-factor/
point-mask checks. It rejects inputs above 20 cameras or 2000 observations. It is
**not** a scoring flag; never enable it in a timed cohort. `validate.py` owns only
the serialized tiny checks and N=3 frozen/off compatibility, under
`/tmp/prism_gpu.lock`. It does not run the O2 BAL comparison panel.

## Correctness results and practical limits

The CPU reference passes 96 signed-depth cases across six stages; maximum
finite-difference Jacobian error is 6.11e-11. The host/device C++ primitive agrees
with independent NumPy to 3.64e-16. Tests cover the full joint camera–point
direction, full distortion, original-stage identity, equal initial costs with
different gradients, an intermediate denominator pole and nonconvex stage 0.

The current native validation passed all six stages, with point normal-equation
residual below 3.11e-16, full-model discrepancy below 6.04e-15 and actual compact
rows/cross blocks exactly matching their cast host reference on the toy.
Both on and off memory checks reported zero errors. The tiny exported original
endpoint was independently rescored. N=3 frozen/off compatibility uses
Dubrovnik-88; raw logs and exact results are in the manifest. This is a
compatibility check, not an O2 speed or endpoint improvement claim.
Wave/work trace parity passed on every derived-binary run, including three
actual numerical-repair continuations exercised by the tiny audit.

The cap/target edge test starts already below target with zero residual. It
continues through 18 failed stage 0 attempts, records an interrupted opening,
enters stage 1, and only then reports target success. A one-outer version stops
in staging and reports no hit despite its zero original endpoint cost.

The full TPAMI2007 Oliensis–Hartley extension was not available; the full
ECCV2006 primary paper was obtained from Springer and read. The latter's CIESTA
regularization, rank approximation and convergence assumptions are not those of
O2. No novelty priority or inherited convergence theorem is claimed.
