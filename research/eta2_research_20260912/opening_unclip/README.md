# Opening unclipping attribution: native handoff

The registered isolated binary is ready for the parent-owned comparison grid. It changes only the first three accepted outers' radial camera scaling. With `OCA_OPEN_UNCLIP=1`, the computed camera direction is passed unchanged to the original strict radius, cost and rho checks. An oversized proposal can therefore be rejected and retried. Production compact FP32 fragments with FP64 arithmetic/state/acceptance, original Eta2 forcing, point completion, safeguards, retry policy and controller history all remain. After three accepts ordinary clipping resumes. Off is `OCA_OPEN_UNCLIP=0` or unset.

Binary: `build/prism-opening-unclip`.
SHA256: `2210a4dae5741dc069895a852bd9b153a9822cc5c90ed372cef865e22311c2fd`.
Manifest: `build_manifest.json`.
Protocol: `../PROTOCOL_05_UNCLIP.md`.

`build.py` verifies the frozen source and 44 headers before deriving the new source. Its nine substitutions consist of one algorithm change, configuration validation and the common tracing code. Reversing them reproduces the frozen source byte for byte. The attempt header is an exact copy of the shared Steihaug header, SHA256 `43400101d54c0ccf94464025497105ef825e16c7e7cbb1d21f7dff019619daf6`; enable it with `OCA_STCG_ATTEMPTS=<path>`. Build uses `TMPDIR=/dev/shm`. Neither the frozen source nor the previous frontload binary was altered.

Correctness gates completed under `/tmp/prism_gpu.lock`:

- Tiny off/on ordinary CUDA memcheck: zero memory-access errors in both arms. Independently recomputed endpoint costs agree with native costs within relative `9.47e-12` off and `3.82e-16` on. Attempt accept/product counters agree with native counters. This is an ordinary memcheck, not a new claim about inherited CLI allocation leaks.
- Tiny on exercised the intended branch: nine opening attempts, including five oversized rejections, then a handoff at three accepts. Opening steps retain their raw norm, and every accepted step satisfies the original radius test.
- Original versus derived-off on Dubrovnik88, N3 alternating: median cost delta **+0.00009024%**, within the preregistered compatibility threshold. Original outers were 31/33/33, off 33/33/33; this establishes compatibility, not bit identity. All six full-objective audits passed.

The tiny fixture is an unfavorable quality counterexample: after the fixed eight-outer calibration cap, off cost is **3.17220** and on cost **304,820.88**, with rejects increasing from one to six. The first oversized retries repeatedly shrink radius and raise damping. This is retained as a calibration observation and is not merged into the registered grid. It is another reason to test the rule globally rather than assume that the Venice combined-arm result transfers.

`check_gpu.py` owns only these short correctness checks. Manifests, raw logs, endpoint hashes and compressed endpoint states are in `results/`; temporary state exports were audited and compressed before their `/dev/shm` temporary directories closed. No attribution performance or hit-rate grid has been run by this subagent. The parent owns all such runs and promotion decisions.
