# Diagnostic split replay status

The native launch-boundary profile passed, but the registered internal `MFAssemble` replay is not complete. The production kernel combines projection derivatives, compact fragment writes, camera accumulation, and point accumulation in one launch, so CUDA events cannot separate those terms without a diagnostic implementation.

An unchunked replay is infeasible on the available 16,380 MiB RTX 2000 Ada. Final13682 has 28,987,644 observations; materializing the CD9 `gx[12]` and `gy[12]` arrays alone requires about 5.565 GiB in FP64, before roughly 0.9 GiB of residual/radius intermediates, about 3.13 GiB of native compact fragments, states, indices, and reference plus split accumulation outputs.

The preregistered implementation boundary is therefore fixed at 1,000,000 observations per chunk, preserving global observation order. Each chunk must use the identical initial state, weights, and index mappings. Per-observation `Gp` and `Bo` require exact equality when the write expression and storage order are preserved. Accumulated `Hcc`, `Cdiag`, `bc`, `bp`, and `r2acc` require finite checks and a scale-aware comparison `||split-reference|| / max(||reference||, DBL_MIN) <= 1e-12`, plus an absolute difference no larger than `1e-12` when the reference norm is zero. Chunk setup and host transfers are excluded from kernel subphase event timings and reported separately.

No replay source or measurements passed review in this cycle. Consequently the internal phase breakdown, Stage 2 candidate selection, and its 5% microtime gate remain unmeasured. The native whole-kernel result cannot substitute for that gate, and no native optimization or Caspar comparison is opened.
