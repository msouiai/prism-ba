# Venice52 registered stopping test: completed result

At the fixed objective target **243740.27**, neither frozen Eta2 arm hits in any of its ten repetitions. Banked same-host Ceres LM reaches that target in all three runs, median **4.935336 seconds**. Ceres wins this specific target comparison. The stopping extension is not a replacement champion.

| Arm | Hits | Median endpoint | Endpoint range | Median native seconds | Median outers |
|---|---:|---:|---:|---:|---:|
| champion | 0/10 | 246,309.540 | 244,954.925–247,590.510 | 1.546301 | 128.0 |
| stop_disabled | 0/10 | 244,929.689 | 244,928.343–246,035.272 | 60.007475 | 6619.5 |

The target is 1% above the stated Ceres reference 241327. Champion stops on persistent flatness; the extension disables FTOL, raises the outer cap from 600 to 10000 and exhausts 60 native seconds every time. Its median cost improves by about 0.56% relative to the champion median, but remains about 1.49% above the Ceres endpoint. This improves the gap without meeting the registered tolerance. No successful-subset speed ratio exists because there are no hits.

All 20 exported endpoints passed independent FP64 scoring against original observations; maximum relative native/audited discrepancy 1.02e-13. Both arms use the same frozen binary and identical inputs, with all differences registered in PROTOCOL.md. These are N=10 observations, not a proof of zero population success probability.

The tail analysis finds 100/100 final accepted attempts in all ten extended runs, final logged CG index 0 (one CG iteration), and minuscule remaining gains. Seven runs have no final camera-radius clipping and rho close to 1; three are clipped and end worse near 246034. Thus the observed terminal regime is slow accepted progress, not a reject storm. The numeric guard leaves differing damping floors across repetitions. These measurements motivate tighter linear forcing and delayed stop confirmation as separate exploratory probes; they do not yet prove which mechanism causes the floor.

Claude’s supplied six MFREE rows reach 241602–241656 in about 30 seconds with its own stopping disabled. That explains its old stopping floor, but does not transfer directly to Eta2. The delivered endpoint CSV contains no target crossing times or exported states; its full runtime is not comparable to Ceres’s 4.94-second crossing time. See claude-venice-rows.json and the byte-preserved CSV in provenance/.

This closes the primary reachability test with a negative result for a simple extension. Two exploratory N=3 probes are separately registered in PROBE_PROTOCOL.md and have no results yet at this report version. The Ceres storm coverage and subsequent Eta2 target stage are still running; this file is not their verdict.
