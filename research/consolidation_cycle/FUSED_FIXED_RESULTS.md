# Fixed-system fusion results

Source SHA `99425dad111b8aa79744f3e00ab6b51b3e1ee4374b36fb6326630f36285a376e` was run under `/tmp/prism_gpu.lock` on the archived Muell-gba146 outer-12 and Final1936 outer-0 captures. No compatible Final13682 or Final4585 fixed capture was available; using Final1936 is an archived-capture availability deviation from the registered memory-only fallback rule, not evidence that it is the largest feasible capture. The baseline is the fixed point-CSR q+=32 tree with one warp per block, a `tacc` clear, and a separate 3x3 point solve. Fusion uses the same mapping/tree, packs four warps per block, and includes the point solve, so the measured package combines block packing and fusion.

All 12 seeded probes per capture produced numerically exact zero differences for point outputs and bare-Schur actions; the harness did not compare signed-zero bit patterns. The tiny probe covers point output only. Invalid-factor output zeroing was exact. Maximum sampled symmetry defects were below `8e-17`, against the registered `1e-12` threshold. The printed `term_norm=2*||Sv||` is a placeholder and is not the registered cancellation-safe expression; zero sampled action differences make it immaterial to these comparisons.

Median CUDA-event Pass1+point-solve chain times over three alternating repetitions were:

| capture | baseline ms | fused ms | fused / baseline |
|---|---:|---:|---:|
| Muell-gba146 | 11.9127 | 16.0335 | 1.3459 |
| Final1936 | 20.6940 | 31.3396 | 1.5144 |

Fusion regressed the fixed chain phase by 34.6% and 51.4%. The timed region excludes Pass2 and therefore does not satisfy the registered complete fixed-product measurement. The chain package fails its performance screen decisively, so native trajectory tests were not opened. Nsight Compute is installed, but profiler replay was not run after this kill; bytes and atomic transactions remain unmeasured. Raw logs are `FUSED_MUELL.log` (SHA `9e634ebae5ee95ce6eaf51d3d41d4590f5320e040d53ffdbb6360d4742702804`) and `FUSED_FINAL1936.log` (SHA `ad456b91035a2307c13378ec74b1db7c90b8108fc900dbeb2ba04b696d80043c`).
