# Brief 7: valid projected ARC is nearly identical to matched LM

The fixed64 full-normal ARC screen has **zero of three registered mechanism wins**. All nine N3 matched pairs are valid; all 18 proposals decrease the original full objective and are accepted. ARC improves the decrease by tiny amounts on two states and slightly reduces it on the third. None approaches the required 20% improvement. This formulation is parked; frozen Eta2 remains unchanged.

The separate mathematical audit confirms that the advertised free shifted-Schur graft is invalid under coupled point damping. This does not invalidate cubic regularization. The tested full-normal formulation is a mathematically valid shift family and retains an explicit full-space accuracy limitation.

## Results in both directions

These are full Venice-52 saved states with 52 cameras, 64,053 points and 347,173 observations. The score retains every observation and fixed k2=0. The common 64-vector basis is built freshly for each repetition and shared only by the matched LM/ARC diagnostic pair. No old camera radius is imposed on either proposal, no points are replaced by an eliminated solve, and no shift candidate is nonlinearly scored.

| Witness | Projected LM full cost | ARC full cost | LM decrease | ARC decrease | ARC/LM decrease |
|---|---:|---:|---:|---:|---:|
| V0 | 246344.828805924 | 246344.828782783 | 14.195776375 | 14.195799516 | 1.000001630 |
| V1 | 244946.788266681 | 244946.788266677 | 0.050786245 | 0.050786249 | 1.000000084 |
| V2 | 246403.188902605 | 246403.188903199 | 0.505833074 | 0.505832480 | 0.999998825 |

N3 direction/results repeat identically within each fixed cell. The first two changes favor ARC and the third favors LM. All cost differences are far below 0.15%. Initial scores are 246359.02458229894, 244946.83905292646 and 246403.69473567858; all provenance and initial-score checks pass.

| Witness | Saved lambda | Solved ARC lambda | Smallest projected eigenvalue | Full relative residual, LM / ARC | ARC camera norm / old radius |
|---|---:|---:|---:|---:|---:|
| V0 | 8.9235e-7 | 4.4452e-7 | 1.8614e-4 | 0.76807 / 0.77002 | 0.04403 |
| V1 | 4.4584e-8 | 3.6567e-10 | 8.7505e-4 | 0.035117 / 0.035119 | 0.01027 |
| V2 | 1.1535e-6 | 1.5680e-8 | 7.7075e-4 | 0.028402 / 0.028451 | 0.00723 |

The fresh full residuals matter: a tiny projected secular residual does **not** mean these are exact full-space steps. The basis does not resolve the entire system. Within its represented modes, both saved and cubic-selected damping are much smaller than the smallest projected curvature; changing damping therefore changes the step very little. This is a measured explanation of the null result, not a claim that all ARC configurations must behave this way.

The global sigma values are 1.1529342e-9, 8.2420174e-11 and 1.2408306e-9, fixed by saved lambda divided by the captured Eta2 full-D step norm. Those anchor norms are 773.9839, 540.9340 and 929.6306. No sigma tuning or larger-basis continuation was introduced after seeing data.

## Work and numerical checks

Each matched pair uses 64 full camera-plus-point normal products to build the basis and one fresh residual-verification product per arm: 66 per pair, **594 total**. The full vector has 192,627 entries. Basis and stored products each require 98.63 MB in FP64 (decimal MB); these are RAM workspaces, not persisted arrays. This is not equivalent to 64 Schur products.

Median product time is 2.19–2.21 s per basis; orthogonalization and projection take 0.439–0.457 s. Median hypothetical standalone CPU times, charging the complete common assembly/basis to either arm, are 3.37, 3.34 and 3.34 s. The first V0 pair takes 8.19 s including the initial cold overhead and is retained. Pair actual CPU wall totals 36.501 s; campaign elapsed wall is 37.277 s. These CPU measurements do not establish GPU cost or time-to-target.

Maximum orthogonality error is 2.74e-14 and maximum projected antisymmetry is 1.44e-15. All projected cubic matrices are positive definite after their shifts. Secular relative residuals are below 8e-15; projected stationarity residuals are below 7.5e-13. Acceptance also requires positive undamped-GN prediction, true full descent and rho>0.1. Raw/full costs, intrinsic prior contributions, cubic model values and full residuals remain in the ledger.

Before witness data, the coherent toy Schur counterexample produced a 0.2820 Frobenius-norm extra term beyond the nominal identity shift, with non-scalar component 0.2221, and a reduced RHS change of 0.06298. The equivalent complete D-whitened operator satisfied the exact shift identity to 4.94e-15. Tiny dense cubic optimization agreed with the projected full-space root to 1.41e-15 relative direction error. The independent dense-J versus full-normal product error is 2.39e-16. A deliberately unresolved 64-vector toy also exhibits a 5.1% full residual despite an accurate projected root, testing the accuracy distinction before BAL data.

## Prior art and conclusion

Shifted Krylov cubic regularization already exists; the primary [ARCqK manuscript](https://optimization-online.org/wp-content/uploads/2021/03/8317.pdf) explicitly develops simultaneous shifted solves for cubic regularization. Our useful finding is the coupled-elimination obstruction in Eta2, and the measured outcome of one valid, fully charged alternative. No novelty or ARC complexity theorem is claimed for this implementation.

The [registered gate](../PROTOCOL_07.md) is a mechanism screen, not the original nine-cell native comparison against PI and not a universal ARC kill. It rejects this fixed64 basis and sigma rule for native integration. The unchanged champion remains the current winner. Captured Eta2 and separately measured coherent rows appear in [context.json](results/context.json) only as context; their timings and solve accuracy are not matched controls here.
