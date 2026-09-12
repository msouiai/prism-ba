# Passenger coarse correction: witness gate passed, native gate failed

The registered74-run native comparison is complete; [full table](../../PASSENGER_NATIVE_RESULTS.md). Both arms hit27/27 practical targets, all nine timing ranges overlap, and the intervention is inactive before those targets. Venice hits0/5 in both arms; Final3068 hits4/5 in both. No promotion.

All five Venice on-runs trigger exactly one coarse episode. Every episode accepts its three coarse steps, but none reaches the target after fine continuation. Immediate full-objective gains range0.0314–214.15. Episode work costs about0.056s. Thus the witness-local descent mechanism does transfer, but its gain is insufficient for the registered target.

Only the single Final3068 on-run that misses its target triggers an episode. Its three accepted steps gain0.89564 at cost1,939,029, paying about0.247s including fresh setup; continuation still misses. The other four on-runs reach the target before intervention. Their conditional timing difference from independently rerun off controls must not be attributed to an active coarse correction.

Fine lambda, radius, numeric floor, forcing history, last_rel and confirmation state are checked unchanged across the intervention. Probe wall is separated from ordinary LM failure/retry accounting in each `passenger_trace.json`; all source/endpoint/count checks pass. This negative concerns the one geometric K8/three-attempt/one-stop correction. The original added same-radius oracle gate and its separate negative remain historical evidence, not the rationale for rejecting this independently globalized native arm.
