# Brief 5: early-trajectory predictor pre-test

Forty fresh full-budget frozen Eta2 runs, twenty per scene. Every endpoint passed the independent original-observation FP64 audit. No input, damping, forcing or stopping-policy tuning. These repeated atomics-order executions are not controllable RNG seeds.

| Scene | Feature | Full rho | First-half rho | Held-out-half rho | Registered gate |
|---|---|---:|---:|---:|---|
| ladybug-1197 | cost5 | -0.050 | +0.224 | -0.139 | False |
| ladybug-1197 | cost3 | -0.314 | -0.212 | -0.418 | False |
| ladybug-1197 | cost10 | +0.383 | +0.406 | +0.236 | False |
| ladybug-1197 | rho5 | +0.057 | -0.164 | +0.139 | False |
| ladybug-1197 | reject5 | undefined | undefined | undefined | False |
| ladybug-1197 | clip5 | undefined | undefined | undefined | False |
| final-3068 | cost5 | +0.202 | -0.006 | +0.200 | False |
| final-3068 | cost3 | +0.231 | -0.231 | +0.309 | False |
| final-3068 | cost10 | +0.236 | +0.503 | +0.030 | False |
| final-3068 | rho5 | -0.202 | +0.006 | -0.200 | False |
| final-3068 | reject5 | undefined | undefined | undefined | False |
| final-3068 | clip5 | undefined | undefined | undefined | False |

Both-scene racing gate: **False**. Selection follows the committed first-half/held-out-half rule; all alternatives and ties remain visible.

Costs at accepted outer3/5/10 are native trace readings; final cost is independently audited. A raw full-cohort correlation by itself is not the registered decision. This cohort is a predictor screen, not a measured racing benefit or a time-to-target comparison. A failed gate does not refute front-loaded accuracy, which is a separate intervention.
