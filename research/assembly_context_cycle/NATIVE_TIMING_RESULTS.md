# Native Stage 1 timing

The retained V2 cohort uses the generated B6v7 derivative in `NATIVE_TIMING_BUILD.json`, fixed at three outer iterations. Each scene has one attributed run and three uninstrumented controls. Both attributed runs accepted all three steps with zero rejects and zero negative-curvature events, so the recorded assembly-to-first-factor chains do not omit retry factorization. Endpoint states were independently rescored in FP64; maximum relative native-versus-audit error was `1.83e-14`.

| Scene | Control solve seconds (N=3) | Median | Profile solve | MFAssemble, 3 calls | MFAssemble / solve | Covered chain / solve |
|---|---:|---:|---:|---:|---:|---:|
| Muell-gba146 | 0.222964, 0.232467, 0.234334 | 0.232467 | 0.245302 | 151.368 ms | 61.71% | 68.07% |
| Final13682 | 2.266889, 2.256169, 2.286389 | 2.266889 | 2.293363 | 884.486 ms | 38.57% | 48.92% |

The other observable GPU boundaries were 9.446/137.402 ms for point factor plus point RHS and 5.922/96.690 ms for the fused reduced-RHS boundary on Muell/Final13682. The reduced-RHS kernel includes equilibration work in this implementation. The covered-chain percentage is not total GPU utilization; candidate evaluation, Krylov work, and other solve work lie outside it.

Setup attribution is coarse because allocation and H2D are coupled in the current entry point. Muell recorded 991.785 ms parse, 275.588 ms problem allocation/H2D, and 78.430 ms index construction/allocation/H2D. Final13682 recorded 13,889.061 ms, 700.365 ms, and 1,216.393 ms respectively. State serialization and final diagnostic/output time remain unclassified.

The first run used the same binary and numerical configuration, but its Muell evidence directory was overwritten when setup-field extraction was amended. Its recorded summary is therefore preliminary only and is preserved in `MATH_REVIEW.md`; it is excluded from timing claims. All retained evidence is under `evidence/native-timing-v2` and is bound by `NATIVE_TIMING_RESULTS_V2.json`.

Whole-kernel timing establishes that assembly is the dominant observable launch on both scenes. It cannot distinguish projection derivatives, compact writes, and camera/point accumulation because those operations share one monolithic kernel. Candidate selection remains pending the separately validated, non-additive split replay.
