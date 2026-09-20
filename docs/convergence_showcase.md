# Prism convergence showcase

These figures use three fresh same-host runs per configuration and fixed historical 1%-above-anchor targets. Cost traces stop when a solver reaches its target or exhausts its native cap; endpoints are independently rescored in FP64.

| Scene | Prism | Caspar FP32 | Caspar FP64 |
|---|---:|---:|---:|
| [Ladybug-1469](ladybug1469_convergence.md) | 3/3, 0.318 s | 0/3, 13.37× target | 3/3, 0.942 s |
| [Final-4585](final4585_convergence.md) | 3/3, 1.845 s | 0/3, 1.49× target at 12 s | 0/3, 1.62× target at 12 s |
| [Final-13682](final13682_convergence.md) | 3/3, 4.275 s | 3/3, 7.096 s | 3/3, 14.982 s |

[Ladybug-1469 figure](figures/convergence/ladybug1469_convergence.png) · [Final-4585 figure](figures/convergence/final4585_convergence.png) · [Final-13682 figure](figures/convergence/final13682_convergence.png)

Ladybug recordings are correlated subsets, so Ladybug-1469 is useful as an FP32 precision diagnostic but not as independent panel evidence. Final-4585 is the large-scene separation, although both Caspar precisions miss there. Final-13682 is the clean time-to-same-quality comparison where all arms reach the target.
