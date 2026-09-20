# Fresh TR / Caspar FP64 / Caspar FP32 comparison

Frozen before measurement on 2026-09-09. No new solver tuning, input perturbations, target calibration or after-the-fact scene selection.

Three arms: packaged recurrence-scored PRISM TR-one (FP64), pinned COLMAP-generated Caspar FP64, and its FP32 variant. Caspar driver settings are identical across precisions: default mode, maximum PCG20, diagonal initialization1, reduction factor0.333333, relative PCG exit1e-4. This is the standalone COLMAP Caspar backend benchmark driver, not the complete COLMAP reconstruction pipeline. PRISM uses the frozen candidate configuration from `docs/tr_candidate_results.md`.

| Scene | Cameras | Points | Observations | Nominal target | Native budget |
|---|---:|---:|---:|---:|---:|
| Trafalgar126 | 126 | 40,037 | 148,328 | 104534.24152926281 | 4 s |
| Dubrovnik88 | 88 | 64,298 | 383,937 | 359003.9111293723 | 4 s |
| Final1936 | 1,936 | 649,673 | 5,213,733 | 5074937.9725361075 | 12 s |
| Final4585 | 4,585 | 1,324,582 | 9,125,125 | 7488277.5282109585 | 20 s |
| Final13682 | 13,682 | 4,456,117 | 28,987,644 | 27318392.631312046 | 20 s |

The target is the previously frozen medium target from the original-input benchmark, multiplied by the common 1−1e-8 inward margin. PRISM receives the nominal target because its native stopping rule already applies this margin; both Caspar drivers receive the effective target directly. FP32 necessarily rounds its stored threshold and input representation. Independent certification still uses the original double-precision observations and the same effective target as the other arms.

N3 per scene and arm, 45 runs total. Each arm occupies each position in a scene's run order exactly once. Scene order rotates between repetitions. All GPU runs are serialized with the same lock. Previous paused jobs remain paused. Individual process timeout240s permits file loading, graph setup, state export and audits outside the native cap. The sum of requested native caps is540s; boundary-checked caps may overshoot by part of an iteration. No profiler, learned candidate log or explicit curvature-audit overhead is enabled in the target runs.

A hit requires both a native target crossing within budget and an independently audited final state below the effective target. A native FP32 crossing that fails that audit is labelled **uncertified**, not accepted as a speed result. All misses/crashes are retained. No speed ratio is computed from a miss or a partially successful cell. For misses, report independently audited endpoint quality and budget instead. Do not treat the cap as an observed time-to-target.

The exported endpoint certifies final quality; intermediate native traces are not each independently CPU-audited. Caspar's native target stop ordinarily returns the crossing state. This benchmark preserves the existing driver and explicitly reports native/CPU score gaps rather than silently adjusting the FP32 stop threshold after observing results.

Native time scopes differ: PRISM includes solver-local initialization, excluding CLI upload; Caspar excludes graph setup. Process wall is reported separately but includes differing internal CPU audit scopes and is not a normalized application latency comparison. Python endpoint audits occur outside subprocess and solver clocks. FP32 input/initial-state rounding gaps and final native/CPU discrepancies are recorded separately from the independent audit's numerical agreement with the driver's CPU checker.

Frozen executables:

- PRISM TR: `936a02425902ee5d0b2d7f09e2f738b53ab32c2b6076bfe0e48972f1e699f222`.
- Caspar FP64: `6ca81c85112005b024df4972b0ec16c3819838999a876513e148c58ed8f35eb2`.
- Caspar FP32: `de038488e929a8fad674d1096c5f61619f3039e6409a81670dab0df7dffe0919`.

COLMAP provenance commit: `ed8080bcf42ef0e42d3f5d0cd21eeff0698dfde8`. Existing precision proof checks generated FP64 code and hashes the FP32 driver/binary; each fresh run also logs and verifies its precision. This experiment uses these pinned implementations, without claiming they are the latest upstream version.

Full machine-readable protocol, flags, input/tooling/binary hashes, copied driver sources, manifests, raw logs, CSVs, exported matrix states and results: `/workspace/prism-fresh-tr-caspar/`. Runner: `bench/fresh_tr_caspar.py`; summary: `bench/summarize_fresh_tr_caspar.py`; independent verifier: `bench/verify_fresh_tr_caspar.py`.
