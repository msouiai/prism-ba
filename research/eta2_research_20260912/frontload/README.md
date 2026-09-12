# Brief 5 native front-loaded accuracy prototype

The registered arm is implemented and its correctness checks are complete. **This is ready for the parent's registered same-target grid; it is not a promoted solver.** The original Eta2 source and defaults are unchanged. Protocol: [PROTOCOL_05_NATIVE.md](../PROTOCOL_05_NATIVE.md), committed at `eabb5bf93a4315cfc6c338fbaef28162d9e6cda8`.

Use the complete frozen `champion.json` flags and CLI, with `OCA_FRONTLOAD=0` or `1` on **the same** `build/prism-frontload` binary. The current binary SHA256 is `24e08d038c4232b6d6a9278e6fa34242b9e9ac5488786bdcc83ecbce2c18b9f9`. Attempt tracing uses the exact unchanged shared `OCA_STCG_ATTEMPTS` header; the file hash is pinned in [build_manifest.json](build_manifest.json).

## Implemented intervention

On attempts entering with fewer than three accepted outers, an attempt-scoped workspace builds FP64 camera/point Jacobian rows and residuals. Point QR factors use those same rows and the existing saved diagonal/trace damping with coupled `tau=lambda`. The coherent reduced gradient replaces `bprime` before residual, norm and forcing-history initialization. The camera block preconditioner and ordinary native CG cap are unchanged; the forcing target is exactly 0.05 during the opening intervention.

`ProductBase` applies the coherent reduced operator with point damping and intrinsic prior curvature, **excluding camera lambda**. The unchanged native loop adds the camera shift once. Scoring back-substitutes points from the actual physical camera solve using the coherent rows/factors. The scored SIMPLE_RADIAL objective, strict full-GN model/rho calculation, point keep/move safeguard, backtracking eligibility, numerical repair and retry policy remain the frozen implementation's.

Opening camera proposals are not radially clipped. Their first radius is bootstrapped normally and the existing strict radius admissibility check remains. A raw oversized proposal therefore cannot be accepted merely because clipping was skipped. After the third accepted outer, the original path resumes with the current normal controller/history state; no historical state restoration occurs.

Original mixed-fragment assembly and preparation are still paid during coherent opening attempts. This simple prototype therefore combines tighter accuracy, coherent arithmetic/storage and unclipped proposals **and retains their additional preparation cost**. It does not claim efficient replacement of every superseded native assembly pass. The diagnostic's 20,000-step solver and snapshot writer are never called.

Workspace destruction occurs before the native target-crossing timestamp, and numerical-repair exits also destroy the workspace within the common attempt clock. Allocations, row construction, point factors, RHS, products, point completion and freeing are charged. The native forcing test's fresh residual check is reused; only a cap/cutoff exit lacking that check adds a fresh product. `FRONTLOAD_LINEAR`, `FRONTLOAD_HANDOFF` and `FRONTLOAD_SUMMARY` report residuals, phase and work. Construction/destruction component fields are host timings, not isolated CUDA kernel profiles.

## Correctness evidence

- Reversing all 16 source substitutions recovers the frozen source byte-for-byte. Frozen source and all 44 headers verify in-session; copied coherent kernels equal the validated Brief0 definitions. The unchanged common attempt header and all local header hashes were verified across compilation.
- A small GPU problem assembled independently on the CPU validates Jacobian rows, reduced RHS, damped operator, point completion and full normal equations. Maximum row error is `1.14e-13`; relative RHS/product/point/full-normal errors are `8.34e-14`, `5.27e-16`, `1.04e-13`, `8.58e-14`. The full-GN prediction identity error is `8.33e-17`. Its memcheck with full leak checking reports **zero errors and zero leaks**: [kernel-toy](results/kernel-toy/result.json).
- Native toy runs with the arm off/on pass ordinary memory-access checking and independent endpoint scoring. On-mode fresh residuals agree with recursive residuals, remain within 0.05, and the handoff occurs exactly after three accepted steps. Accepted camera proposals obey the existing radius. See [toy-summary.json](results/toy-summary.json).
- N=3 original/derived-off compatibility on Dubrovnik88 passes. All six runs use 33 outers; the derived-off median cost difference is **+0.0000723%**, within the pre-existing run variability. This is compatibility evidence, not bit-identical GPU trajectories or a speed claim: [compatibility-summary.json](results/compatibility-summary.json).

The toy's eight-outer endpoint is **973.54 on versus 3.17 off**. Both runs are valid; that unfavorable calibration result is retained rather than hidden. It is not merged into the registered BAL performance cohort.

An additional stricter leak audit fails on **all three native CLI paths**: original, derived-off and derived-on each leave 20 CLI/static allocations totaling 5,892 bytes. The stacks are in the pre-existing problem/index/state/cost/cheirality helpers, with no FrontloadAttempt allocation stack. The original failed off artifact is preserved under `results/toy-off-0/`, and the comparison is [inherited-leak-comparison.json](results/inherited-leak-comparison.json). Ordinary memcheck and the new workspace's standalone leak-clean test do not erase or excuse these inherited CLI leaks.

## Reproduction

```sh
TMPDIR=/dev/shm python research/eta2_research_20260912/frontload/build.py
TMPDIR=/dev/shm python research/eta2_research_20260912/frontload/build_toy.py
python research/eta2_research_20260912/frontload/check_gpu.py kernel
python research/eta2_research_20260912/frontload/check_gpu.py toy
python research/eta2_research_20260912/frontload/check_gpu.py compatibility
```

The GPU check runner takes `/tmp/prism_gpu.lock` for each process. Existing evidence should be retained when repeating checks; use a separate output location/version before changing source or flags. No timed grid was run by this implementation task. The parent owns all performance cells and their final verdict.
