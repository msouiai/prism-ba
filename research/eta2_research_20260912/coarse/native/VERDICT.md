# Registered K8 additive preconditioner: no promotion

The completed same-binary panel contains54 practical and20 tail runs. All27 practical targets are hit in each arm; eight of nine timing ranges overlap. Ladybug539 at1% tolerance is11.75% slower with disjoint ranges even though the coarse algorithm never activates there. Report that timing observation without attributing it to active coarse algebra. Full rows: [COARSE_NATIVE_RESULTS.md](../../COARSE_NATIVE_RESULTS.md).

Only the tight Trafalgar practical cell activates the coarse rule. Its two active attempts both fall back because the production coarse matrix is not SPD, so they pay about7ms setup without any coarse preconditioner application. The other practical cells mostly measure an inactive rule, not successful two-level work.

On Venice52, off/on both hit0/5. The additive arm activates around outer23, makes65–71 preparations, and falls back on about18–19; setup costs0.35–0.38s. Its median endpoint is0.49% lower in this cohort, but it still misses the target and its median native termination wall grows from1.343s to1.667s. Termination wall is not time to an unmet target.

On Final3068 both hit4/5. Successful-run median crossing time is3.8133s off versus4.8538s on; ranges overlap. There are34–52 preparations, costing0.92–1.41s per run. This concrete implementation does not buy target reliability with that overhead.

The witness spectrum improvement remains real: the K8 space removes troublesome small eigenmodes in the coherent Venice reference. That does not ensure enough nonlinear progress to pay for rebuilding the actual coupled-damping preconditioner. The native arm uses the production mixed-storage operator, which can also make its coarse matrix indefinite. The result concerns one registered K8 additive implementation and activation rule. It does not meet the user's stronger all-K kill and does not refute deflation, balancing, or every coarse space. Further variants would need a cheaper assembly or a specific mechanism beyond the measured spectral improvement. Frozen Eta2 remains the current winner.
