# Pair restoration and probe precision: completed follow-up

**Verdict: retain the frozen Eta2 champion. Neither restoration nor de-clipping passes the registered target gates. FP64 cross blocks remove the measured Venice probe curvature truncation, but do not produce an accepted rescue there.**

Registration: `62a756b`, before implementation or new solver runs. Branch `research/eta2-pair-precision`; original solver and frozen champion untouched. 122 primary native solves plus 18 external-state operator captures. All primary endpoint states were independently scored in CPU FP64. No new Caspar/Ceres timing comparison is implied.

## Final3068: target 1744796.9841897595

| Arm | Hits | Target seconds: median [min, max], successful runs only | Above-target stop witnesses rescued | Probe accepts | Curvature cutoffs |
|---|---:|---:|---:|---:|---:|
| original | 6/10 | 3.483 [1.656, 5.016] | 0/0 | 0/0 | 0 |
| pair | 6/10 | 3.504 [2.320, 5.014] | 0/4 | 0/4 | 1 |
| pair64 | 4/10 | 3.578 [3.112, 3.998] | 0/6 | 1/6 | 0 |

Both candidate conditional medians are below the registered 3.96s limit, but both fail the decisive witness gate: pair restores rescue 0/4 stopping misses; pair64 rescues 0/6. Every successful target crossing happened before its probe. The 6/10 versus 4/10 fresh hit counts are not a causal estimate of precision harm: floating-point trajectories differ before intervention, so those successes cannot be attributed to it.

The pair arm has one curvature truncation and two 512-iteration cap hits among four probes. Pair64 has zero truncations but four 512-iteration cap hits among six probes. Its one accepted probe gains 17.0864 cost units from 1,900,167.3 and ultimately stops near 1,900,147.9, still above target. A 512 cap is a budget, not a certificate of reaching residual 1e-3; actual residuals are retained in every row.

Implementation restores both outgoing lambda and radius from the last accepted ordinary step with relative decrease >1e-4. The numerical floor is preserved, with radius adjusted to keep lambda*R² constant when lambda is clamped. All restored pairs pass this invariant check. The raw camera directions remain 6–835 times the restored radius for the mixed probes and 34–23,013 times for the FP64 probes. Pair restoration therefore does not guarantee that the deeper direction survives clipping at a later state.

## Venice52: target 243740.27

| Arm | Target hits | Endpoint: median [min, max] | Native endpoint seconds: median [min, max] | Probe accepts | Curvature cutoffs |
|---|---:|---:|---:|---:|---:|
| original | 0/10 | 246703.7 [246316.0, 247583.2] | 1.378 [0.877, 2.068] | 0/0 | 0 |
| pair | 0/10 | 246346.0 [244957.5, 247892.8] | 1.602 [1.105, 2.091] | 6/10 | 0 |
| pair64 | 0/10 | 246322.5 [244947.6, 247892.0] | 1.848 [1.359, 2.083] | 5/10 | 0 |
| declip | 0/10 | 246331.6 [244966.9, 247589.1] | 1.492 [1.214, 2.338] | 0/10 | 10 |
| declip64 | 0/10 | 247004.8 [244955.5, 247894.2] | 1.427 [0.957, 2.294] | 0/10 | 0 |

All arms have zero observed hits, so their endpoint times are not time-to-target speed measurements. Small endpoint differences do not make any arm pass. Pair and pair64 can accept tiny late steps (6/10 and 5/10), but none rescues its stopping witness to target.

The precision mechanism is clean: all ten mixed de-clipping probes truncate, while all ten FP64-cross probes complete 83 CG iterations without truncation, with true relative residuals 0.000538–0.000576. Nonetheless all ten FP64 proposals fail acceptance. Their raw camera norm is about 221,440 against radius 12,901 (still about 17.2x clipped). A representative exact full model predicts a positive 304.60 decrease, but no improving true-cost candidate is retained. The logged candidate==current sentinel means no retained improvement, not an independently measured equal-cost rejected trial; the failed trial objective is not logged.

FP64 cross blocks are lazy and probe-only: 74,989,368 extra bytes on Venice52, 357,223,392 on Final3068. Rebuilds, allocation, RHS, products and back-substitution are charged inside native solve time. No precision work is performed before a probe. Point factors remain based on rounded point rows; cross-only precision is not a universal positive-definiteness guarantee.

## External trajectory audit: all 18 supplied states

All input SHA256 hashes, dimensions, exact observations and zero-k2 values match the supplied manifest/shared input conventions. The transfer archive SHA256 is `c73caa99310c603596c88c84005a1c0c4181f474172454bc3ee733c66f02f35a`. Every capture uses the input state unchanged, without an optimization update. Damping is fixed to lambda=tau=1e-8, intrinsics prior=1, rather than claiming to reproduce Claude's native damping settings.

At every state, all three 468x468 matrices (stored mixed, W64 with stored point factor, W64 with FP64-QR point factor) have zero negative eigenvalues and zero eigenvalues below 1e-14. The full minimum is approximately 1e-8 because 52 frozen k2 coordinates contribute trivial damping-only eigenvalues. The following supplementary active-coordinate audit removes those coordinates; its matrices are unchanged, only the spectral subspace differs.

| Snapshot | CPU cost | Active mixed minimum eigenvalue | Active cross-FP64 minimum | Active full-FP64 minimum |
|---|---:|---:|---:|---:|
| run1_it40 | 245583.5729 | 1.0093475e-08 | 1.0084798e-08 | 1.0083235e-08 |
| run2_it40 | 246486.1339 | 1.0087482e-08 | 1.0083221e-08 | 1.0083411e-08 |
| run3_it40 | 245840.1352 | 1.0118232e-08 | 1.0082302e-08 | 1.0083032e-08 |
| run1_it60 | 243847.6629 | 1.0106198e-08 | 1.0080575e-08 | 1.0083274e-08 |
| run2_it60 | 245196.2879 | 1.0086273e-08 | 1.0085308e-08 | 1.0083401e-08 |
| run3_it60 | 243846.7985 | 1.0099572e-08 | 1.008437e-08 | 1.0083091e-08 |
| run1_it90 | 242819.2460 | 1.0055844e-08 | 1.0086012e-08 | 1.008329e-08 |
| run2_it90 | 243302.6800 | 1.0063416e-08 | 1.0085952e-08 | 1.0083334e-08 |
| run3_it90 | 242656.3281 | 1.008498e-08 | 1.0083689e-08 | 1.0083038e-08 |
| run1_it120 | 242267.8008 | 1.0074894e-08 | 1.0079992e-08 | 1.0083302e-08 |
| run2_it120 | 242459.5042 | 1.0102979e-08 | 1.0082576e-08 | 1.0083332e-08 |
| run3_it120 | 242276.3866 | 1.0086867e-08 | 1.0082957e-08 | 1.0083019e-08 |
| run1_it180 | 241910.0593 | 1.0091349e-08 | 1.0080967e-08 | 1.0083318e-08 |
| run2_it180 | 241934.5900 | 1.0072598e-08 | 1.0081525e-08 | 1.0083324e-08 |
| run3_it180 | 241873.8544 | 1.0083398e-08 | 1.0083293e-08 | 1.0083026e-08 |
| run1_it299 | 241640.0208 | 1.0071917e-08 | 1.0081838e-08 | 1.0083335e-08 |
| run2_it299 | 241640.8488 | 1.0096252e-08 | 1.008423e-08 | 1.0083336e-08 |
| run3_it299 | 241617.5632 | 1.0090965e-08 | 1.0082602e-08 | 1.0083034e-08 |

Dense products agree with the native captured products to maximum relative discrepancy 4.64e-11. The spectra use the symmetric parts; maximum pre-symmetrization entrywise asymmetry is 1.78e-15. Extended-precision scalar quotients and nonnegative full-Jacobian energies also agree. Since all full minima are damping-only k2 modes here, those minimum-vector scalar checks are trivial; the full/active spectra and nontrivial native-product checks carry the external positivity evidence. The first complete raw capture, all dense matrices/eigenvectors, native logs, product-check results and hashes are preserved. Other raw operator arrays were processed transiently and removed after validation, as registered.

**Cost provenance correction:** our prior three actual failed-probe captures were near 248,405, not 246,300. The latter was an eventual endpoint. These delivered states span about 241,618–246,486, so this is a cross-trajectory check, not an exact cost-matched replay of the failed state. Positive mixed operators here agree with Claude's no-cutoff observation; they do not contradict the independently confirmed negative mixed operator at our different states.

The prior same-state audit remains the direct precision attribution: holding our state/direction/damping fixed, W32 gives Rayleigh quotients around -0.56e-9 to -2.57e-9, while W64 alone makes them +3.43e-8 to +4.28e-8. Rebuilding point QR alone does not fix them. The dominant cross-rounding error came from two ill-conditioned, two-observation tracks close to a camera. This is not evidence of a real nonlinear saddle: positively damped Gauss–Newton is positive definite in exact consistent arithmetic.

## No-regression screen

| Scene | Arm | Median endpoint delta vs original | Median native seconds | Median wall delta | Worst paired wall delta | Paired gate fails / N |
|---|---|---:|---:|---:|---:|---:|
| dubrovnik-88 | off | -0.0000% | 0.4163 | -1.0% | -0.3% | 0/3 |
| dubrovnik-88 | pair | -0.0000% | 0.4750 | +13.0% | +14.2% | 0/3 |
| dubrovnik-88 | pair64 | -0.0001% | 0.4806 | +14.3% | +15.7% | 0/3 |
| dubrovnik-88 | declip64 | +0.0001% | 0.5071 | +20.6% | +21.7% | 2/3 |
| dubrovnik-88 | both64 | -0.0001% | 0.5438 | +29.3% | +29.9% | 3/3 |
| ladybug-1197 | off | -0.0112% | 5.2483 | +29.1% | +35.7% | 2/3 |
| ladybug-1197 | pair | -0.0168% | 5.6685 | +39.4% | +47.4% | 3/3 |
| ladybug-1197 | pair64 | -0.0025% | 5.6163 | +38.1% | +78.5% | 3/3 |
| ladybug-1197 | declip64 | -0.0089% | 5.0450 | +24.1% | +36.2% | 2/3 |
| ladybug-1197 | both64 | -0.0039% | 5.2307 | +28.7% | +35.9% | 2/3 |

The registered per-pair thresholds are >0.5% endpoint or >20% native-wall regression. These are ordinary-endpoint screens, not equal-quality speed comparisons. Flags-off differences limit causal interpretation: original Ladybug1197 uses 57–59 outers and 2964–3332 products, versus 57–85 outers and 3094–4285 products with the new binary off. Thus extra work from different floating-point trajectories is visible even without a probe. This screen does not isolate pure intervention overhead. Full ranges and individual pairs are in summary.json.

The conditional both64 target panels were not launched: pair64 failed its Final3068 witness gate and declip64 had zero Venice hits. The pre-registered both64 guard screen was still completed. No arm is promoted.

## What the measurements separate

1. Numerical validity: probe-only W64 repairs the observed false curvature and permits accurate deeper CG on Venice.
2. Linear accuracy versus nonlinear usefulness: reaching residual about 5.6e-4 does not make the proposed retraction acceptable, even when the quadratic model predicts descent.
3. Controller restoration: restoring a previously useful scalar pair neither reconstructs the old state nor guarantees an appropriate radius for the current direction.

Two mathematical limitations explain why neither proposed rescue was guaranteed. First, camera radius limits do not bound the eliminated point step: d_p(alpha)=-V^-1 b_p-alpha V^-1 W^T d_c. The point-only offset remains even as the camera step shrinks. Second, R is measured in the current camera scaling E; restoring an old scalar radius does not transport the old metric when Hcc changes. These are structural observations, not newly measured causes or replacement experiments.

The useful retained asset is the precision diagnosis and reproducible operator audit. The present restoration/de-clipping policies should stay as negative research arms. Do not relax the curvature cutoff, lower the numeric floor, claim a saddle, or count fresh no-probe hits as rescue evidence.

## Reproduction and evidence

All 122 primary rows are valid. Maximum independent endpoint relative discrepancy: 5.73e-12. All 122 exported endpoint states have verified lossless compressed copies. Source, binaries, commands, flags and input hashes are recorded. See PROTOCOL.md, README.md, provenance/, audit.json, summary.json, gates.json, external-results.json, active-spectrum.json, and the verified archive pointer in archive.json.
