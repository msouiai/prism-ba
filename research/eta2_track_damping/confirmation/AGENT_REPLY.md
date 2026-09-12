# Reply: static tau classes do not pass the requested Eta2 confirmation

The requested fresh experiment is complete: Final3068 and Venice52 at N=10 per arm, plus Final4585, Dubrovnik88 and Ladybug539 controls at N=3. **58 new scored runs**, kept separate from the earlier N=5 screen. Frozen Eta2 remains the champion.

## Intervention fidelity

Eta2's baseline applies the same relative point damping factor `tau = lambda` to each guarded point-block diagonal. The implemented rule is exactly **1 / 1 / 0.3** for track lengths **≤2 / 3–5 / ≥6**, applied on every attempt, including retries. There is no feedback loop or alternative dose.

The point-factor kernel reads the existing observation offsets and multiplies the long-track tau by 0.3. Its factors consistently feed the Schur products, reduced RHS, scaling and point back-substitution. There is no additional solve or kernel launch. Camera damping, clipping, forcing, point rescue, numerical recovery and stopping remain unchanged. The full scored objective remains original-observation L2 SIMPLE_RADIAL with unshared intrinsics and k2=0.

The existing binary was not rebuilt: SHA256 `37b262dc44c6f75cbd971f24bbb261735c793ff929ba92962bcc0bde27837679`. Comparisons use that binary off/on, with prior original-versus-derived-off compatibility and GPU factor/memory checks retained, and source, all 44 headers, flags and binary hashes reverified in-session.

## Primary: Final3068

Target: **1744796.9841897595**, preserving the full-precision frozen threshold corresponding to the request's 1744796.98 shorthand.

| Metric | Uniform Eta2 | Static class damping |
|---|---:|---:|
| Target hits | **6/10** | **3/10** |
| FTOL target misses | 4 | **7** |
| Successful-run median crossing | 3.65245s | 1.7805s |
| Successful-run crossing range | 3.1619–4.3497s | 1.5835–2.4113s |
| Median endpoint | 1,743,115.341 | 1,791,194.512 |

The timing condition passes when considered alone: the on-arm successful median is below both the fresh-control +20% ceiling of **4.38294s** and the historical +20% ceiling of **4.430679s**. The latter comes from the actual historical eight-success median of **3.692232s**, frozen before this cohort.

**The zero-miss prediction fails.** All seven on-arm misses stop on FTOL, at costs approximately 1.784–1.796M. The faster successful subset cannot compensate for those misses, and it is not an unconditional speedup. These are independent stochastic solves from the same initial problem, not replayed identical internal failure states. The counts do not establish population probabilities, but they directly contradict elimination of the failure class in this sample.

The earlier N=5 experiment observed 4/5 hits in each arm. It has not been pooled into the primary N=10 verdict, and the earlier historical 8/10 baseline is not substituted for the fresh 6/10 control.

## Secondary: Venice52

Target: **243740.27**. Both arms hit **0/10**.

Median endpoint is **246,355.208 off versus 261,513.852 on: +6.153% worse**. Every stratified run takes 71 outers, records two rejects and zero numerical repairs, then stops on FTOL. Its roughly 0.7525s median termination time is faster than the control's 1.3347s, but neither is a crossing time: the intervention stops sooner at worse quality.

This does not support the proposed cure for the late clipping bind. The earlier N=5 state audit also found a roughly 425× terminal raw/clipped step ratio and cost increases in every track class; that audit is earlier-cohort evidence, not a newly repeated decomposition of all ten fresh states.

## Controls

Controls run to ordinary termination, while their full traces are scored at preregistered equal-cost targets. All control arms cross their respective targets 3/3.

One provenance correction: the protocol mistakenly called the supplied rounded Dubrovnik88 reference a Caspar result; it was the MFREE library endpoint. Its numerical target was frozen before all runs and remains unchanged at 362571.82. [Correction record](PROVENANCE_CORRECTION.md).

| Scene | Median endpoint change, on vs off | Equal-target median time, off → on | Interpretation |
|---|---:|---|---|
| Final4585 | **−0.484%** | 1.6784s → 1.7220s | Endpoint ranges overlap; target time about 2.6% slower |
| Dubrovnik88 | **+0.241%** | 0.0830s → 0.1262s | About 52% slower at the same target, disjoint ranges |
| Ladybug539 | **+0.000199%** | 0.0594s → 0.0596s | Essentially tied; timing ranges overlap |

The expected +2–3% Final4585 endpoint loss did not appear in the N=3 median. This is not evidence that the scene is insensitive: endpoints span approximately **6.590–6.938M off** and **6.682–6.926M on**, and each arm has one time-capped run and two FTOL stops. N=3 does not resolve its basin distribution. The small median difference should not be treated as a robust quality win.

Dubrovnik88 also illustrates why native time to a solver's own endpoint is insufficient: total termination medians are similar, while identical-target crossing slows materially.

## Interpretation

The implementation transfers; the claimed convergence benefit does not pass Eta2's requested protocol. This does not invalidate the supplied MFREE dose study or its offline MacKay analysis, which were not independently reproduced here.

The argument that a problem-derived damping law must transfer independently of solver machinery is too strong. At a fixed linearization, lowering the point regularizer changes both `U_lambda - W V_lambda^-1 W^T` and the reduced RHS. The resulting camera/point direction then interacts with Eta2's scaling, inexact solve, clipping and acceptance trajectory. The present data establishes a negative transfer of this exact rule; it does not identify a unique cause or refute every class-dependent regularizer.

No alternative dose, late-only schedule, learned rule, or accurate-opening combination was tuned after these outcomes. The primary rescue criterion fails, Venice regresses, and one calm control loses equal-target speed. There is no basis for replacing the champion with this configuration.

## Evidence

- [Full results, ranges, counters and every miss](RESULTS.md)
- [Machine-readable verified summary](summary.json)
- [Frozen registration](registration.json) and [protocol](../PROTOCOL_CONFIRMATION.md)
- [All fresh N=10 convergence curves](figures/tail_convergence.png)
- [Implementation and earlier N=5 result](../README.md)

Protocol registration commit: `f3f1de4`, on `research/eta2-track-damping`. All 58 endpoints were independently CPU-audited. Input/initial-score parity, source/binary/flag hashes, exact compressed endpoint hashes, CSV crossing times and trace acceptance/matvec counts pass verification. Large endpoint containers remain local; compact evidence, implementation and reports are versioned. The original champion and the earlier negative screen remain intact.
