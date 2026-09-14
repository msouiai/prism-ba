# Fixed-system fusion results

Source SHA `99425dad111b8aa79744f3e00ab6b51b3e1ee4374b36fb6326630f36285a376e` was run under `/tmp/prism_gpu.lock` on the archived Muell-gba146 outer-12 and Final1936 outer-0 captures. The baseline is the fixed point-CSR q+=32 tree with four warps per block, a `tacc` clear, and a separate 3x3 point solve. Fusion uses the same mapping/tree and packs the point solve into that kernel.

All 12 seeded probes per capture produced bit-identical point outputs and bare-Schur actions. Tiny nonzero probes also matched exactly; invalid-factor output zeroing was exact. Maximum sampled symmetry defects were below `8e-17`, against the registered `1e-12` threshold. The printed `term_norm` is a conservative `2*||Sv||` placeholder rather than the separately measured protocol expression, but all action errors are exactly zero, so it cannot change this gate.

Median CUDA-event product times over three alternating repetitions were:

| capture | baseline ms | fused ms | fused / baseline |
|---|---:|---:|---:|
| Muell-gba146 | 11.9127 | 16.0335 | 1.3459 |
| Final1936 | 20.6940 | 31.3396 | 1.5144 |

Fusion regressed fixed-product wall by 34.6% and 51.4%. It fails the required 5% gain on both captures, so native trajectory tests were not opened. Nsight Compute is installed, but profiler replay was not run after this decisive kill; bytes and atomic transactions remain unmeasured. Raw logs are `FUSED_MUELL.log` (SHA `9e634ebae5ee95ce6eaf51d3d41d4590f5320e040d53ffdbb6360d4742702804`) and `FUSED_FINAL1936.log` (SHA `ad456b91035a2307c13378ec74b1db7c90b8108fc900dbeb2ba04b696d80043c`).
