# Complete deterministic-path overhead protocol

Registered 2026-09-14 before timing runs.

Compare the fastest equivalent unordered B6v7 compile-time FP32 compact2 path
against the same generated binary with complete `OCA_W6_DETERMINISTIC=1`
reductions. All other flags and CLI values are byte-identical. Use identical
unperturbed inputs, alternating order, N=3 per scene: Final3068 target
`1744796.9841897595`, cap 45 s; Final4585 target `7075838.613048037`, cap 60 s.
Every endpoint is rescored independently in FP64. Report paired deterministic /
unordered target-time ratios, all-run native wall, and exact repeatability.

The deterministic path remains a measurement instrument. A production-speed
candidate passes only if its median target-time tax is at most 1% on both cells.
At least one matched double hit per scene is required for target-time tax;
otherwise target-time overhead is unmeasured and all-run wall is descriptive.
Otherwise retain it as opt-in diagnostic infrastructure and state the wall tax.
