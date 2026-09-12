# Registered PI radius arm: do not promote

The same-binary off/on experiment comprises54 practical and20 tail runs, with N3 per practical arm/cell and N5 per tail arm/cell. All initial scores, endpoint audits and attempt counters pass. Full paired results are in [PI_NATIVE_RESULTS.md](../PI_NATIVE_RESULTS.md).

All27 practical targets are reached in each arm. Four cells have faster disjoint observed time ranges (largest median speedup1.068x); one has slower disjoint ranges (Final394 at1% tolerance,2.3% longer); four overlap. These small practical wins do not establish the proposed storm mechanism: those target traces contain no rejections.

On Venice52 neither arm reaches the target (0/5 each), and PI's median endpoint is276621 versus246344, **12.29% worse**. On Final3068 the observed hit count rises from1/5 to2/5, but rejection counts overlap substantially: off8–15 versus on1–14. Venice reject counts also overlap. The preregistered clear storm-reduction gate is not met. Successful-run conditional times from these small, differently selected subsets are not a general speedup estimate.

The PI arm changes only the accepted-radius update and its accepted-history state; rejection handling and the champion's interior-step lambda reduction remain. Consequently this is an ablation of that particular composite controller, not a universal rejection of PI control or a proof of a limit cycle. It supplies no basis for replacing the frozen Eta2 champion.
