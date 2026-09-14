# Consolidation and performance cycle

The current outcome retains the existing unordered compile-time-FP32 compact2 B6v7 baseline. No tested speed candidate earned promotion.

The clean linear-edge derivative is the positive result. Default-off behavior passed a fresh fixed-order exact compatibility test. Enabled ordinary behavior also matched exactly on that cell. CPU extreme-scale tests and an injected CUDA fixture validate exact-zero reduced-RHS handling, safe forcing arithmetic, finite scaled norms, zero-depth metadata, and preserved point-only updates. This path remains a correctness option with a host-copy cost, not a speed default.

The owned workspace derivative passes exact serial compatibility and same-GPU two-thread testing on distinct inputs and capacities. It owns active BAL cost, deterministic reduction, and diagnostic scratch per solve/device, restores caller devices, and cleans injected partial construction failure. Rig and whole-solver exception cleanup remain outside the proven scope.

Point-owned Pass1+Vinv fusion failed its fixed-system gate. Outputs were exact, but product time regressed 34.6% on Muell-gba146 and 51.4% on Final1936. Native tests were correctly skipped.

Fresh B6v7 profiling makes the next ceiling concrete. Cold three-outer process wall is dominated by input/setup. Within returned solve time, assembly leads on Muell and Final13682; Final13682 also spends 29.2% in Krylov. Future performance work should first separate reusable parsed/device-resident problem setup from solve calls, then optimize assembly and Krylov on captured identical work rather than pursue the rejected fusion.

Commits are on `research/agent-audit-consolidation`; frozen Eta2/B6v7 files were not modified.
