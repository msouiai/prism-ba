# Native soft-kick correctness evidence

All required pre-grid checks pass. The production binary and flags are pinned
in [build_manifest.json](build_manifest.json). No performance or basin-escape
claim follows from this evidence.

* **Source parity:** 13 exact substitutions invert to the pinned champion
  source; all 44 frozen headers verified. Original source SHA256 starts
  `22c18359a526526a`. Derived binary SHA256 is
  `2a95a4b6899ebb89e83426f8989289a9035df10d88965a90d1c6ea774d679fc4`.
* **Generalized mode:** an independent dense constrained generalized
  eigenproblem agrees at relative error 2.16e-15. Seven gauge modes are
  removed, leakage 1.45e-17, and actual metric norm is one to roundoff.
  Substituting identity for the actual safeguarded metric changes the toy
  eigenvalue by 26.9%, testing that the factor-derived metric matters.
  Negative-only spectra and invalid metric factors are correctly skipped.
* **Energy and points:** 1,000 scale-varied ray-budget identities have maximum
  relative error 7.30e-16. Invalid/zero curvature is skipped. Dense homogeneous
  point response agrees to residual 6.64e-17. See [math_verification.json](math_verification.json).
* **Native tiny mechanism:** artificial FTOL=1,K=1 forces exactly one event
  after a fresh stopped-state assembly. The native rank-24 coarse matrix
  agrees with all-column operator products to 3.59e-16; seven gauge modes
  are removed. The admitted test ray has prediction budget 19709.02 and true
  increase 33772.92, within its twice-budget bound. Its camera norm exceeds
  the old radius, intentionally exercising the energy rule. Current
  controller and forcing history assertions pass, and the subsequent fine
  attempt rebuilds at the changed state. This is not an efficacy arm.
* **Trace accounting:** in that test, two ordinary accepts, one ordinary
  reject and all 31 matvecs agree between trace and native counters. The one
  admitted kick has its own probe row and is excluded from failed-LM wall.
  All source-off trace invariants also pass. See [tiny trace audit](evidence/correctness/tiny-memcheck-1/trace_audit.json).
* **Memory/state:** ordinary compute-sanitizer memcheck reports zero access
  errors for tiny on/off and the full-state restoration fixture. After
  warming the original cost scratch, the new snapshot helper leaves zero
  additional resident GPU bytes. It restores original state/cost after an
  unrecovered uphill state, including intrinsics, and keeps an improved
  current state. See [state test](evidence/correctness/state-restoration-memcheck-v3/stdout.log).
* **N3 original/off compatibility:** independently audited Dubrovnik88 median
  endpoint is 358944.894174 for original and 358945.203522 for the derived
  flag-off binary: **+0.0000862%**, within the registered compatibility
  threshold. Initial-score relative spread is 1.22e-16. Timing ranges overlap;
  no speed claim. [All six rows](evidence/correctness/compatibility_rows.json)
  and [summary](evidence/correctness/compatibility_summary.json) are retained.

Two preliminary issues are retained rather than hidden. The draft CPU gauge
certificate initially projected each camera block independently; Z is
orthonormal over each complete cluster, so that test was wrong. It was fixed
before any GPU data, and the independent global projection error is 1.17e-15.
The native basis itself did not change. The first standalone state harness
with process-wide leak checking reported eight bytes allocated by the
**frozen ComputeCost process-static scratch**. Context teardown still reports
that allocation under the leak checker. Both logs remain in the initial and
v2 folders. The final ordinary memcheck fixture additionally checks equal
free GPU memory before/after the new helper, with the cost scratch already
warm; it reports zero new resident bytes. No original cost kernel or solver
allocation policy was changed to suppress the report.

Correctness records use explicit source/header/test hashes in
[tests_manifest.json](tests_manifest.json); earlier harness manifests remain
as `tests_manifest_initial.json` and `tests_manifest_v2.json`. CPU and GPU
checks were bounded; no native registered efficacy grid was launched by this
agent. The parent owns that comparison.
