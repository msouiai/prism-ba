# Eta2 research briefs: implementations, measurements and conclusions

Frozen Eta2 remains the general champion. The clearest positive is the **combined accurate opening on Venice52:10/10 registered-target hits versus 0/10 controls, median 0.37605s**. That same global configuration regresses on Final3068 and slows seven practical cells, so it is an experimental option, not a replacement. Opening unclipping alone does not reproduce the gain. No new global speed or novelty claim is established.

This campaign worked through all 13 briefs, including their diagnostic gates and relevant mathematical corrections. It completed seven native candidate comparisons (**538 runs**) and an independent ten-run Venice confirmation, alongside 40 baseline predictor runs and the witness, numerical and correctness studies. These are repeated runs on a small registered scene panel, not hundreds of distinct datasets or a new Caspar/SOTA evaluation.

## Protocol and evidence

The source SHA256 is `22c18359a526526ae0a5b5109187878ab1cef33b453f6bbddc2aa92597a607d8`; the original binary is `1e3d2cf22a8a43075114e0ca2024923dad330461e35d0074938d0412cd77ecc0`. Builds verify the frozen source and 44 headers. Each native overlay has reversible source substitutions, a binary/source/flag manifest, tiny numerical/memory checks and N3 original-versus-derived-off compatibility. Comparisons use the same derived binary off/on. Neither the original solver nor its defaults was overwritten.

The objective remains full original-observation L2 SIMPLE_RADIAL, unshared intrinsics and k2=0. Native state/acceptance arithmetic is FP64; the champion retains its documented compact mixed-storage fragments. Coherent reference operators are labeled separately. There is no robust loss, observation removal, learned component or Krylov reuse across attempts/outers.

Nine practical cells are Ladybug539, Trafalgar138 and Final394 at 1.005/1.01/1.02 times their previously frozen anchors, N3 per arm. Tail targets are Venice52=243740.27 and Final3068=1744796.9841897595, N5 per arm; opening arms also use the separately registered Ladybug1197 target369997.000889023. Practical native caps are 5/5/8s; tails use60s/600outers with ordinary FTOL. All new work is charged, all endpoints independently audited and all misses retained. Conditional successful-run times are not unconditional speedups. Observed disjoint timing ranges are the requested screening criterion, not confidence intervals corrected for multiple comparisons.

## Native comparisons

Each row has its own independent off cohort. Differences between those cohorts, especially Final3068 hit counts, are not differences between baseline algorithms.

| Registered arm | Practical faster / slower / overlapping cells | Venice hits, off→on | Final3068 hits, off→on | Verdict |
|---|---:|---:|---:|---|
| Steihaug PCG |2 /4 /3|0/5→0/5|4/5→0/5|No promotion; two local timing wins, lost tail reliability|
| Additive K8 coarse PCG |0 /1 /8|0/5→0/5|4/5→4/5|No target benefit paying repeated setup|
| PI radius |4 /1 /4|0/5→0/5|1/5→2/5|No clear storm reduction; Venice median cost 12.29% worse|
| Accurate opening, three accepts |1 /7 /1|0/5→5/5|2/5→0/5|Strong local Venice win, global regression|
| Opening unclipping alone |0 /0 /9|0/5→0/5|4/5→2/5|Does not reproduce Venice; Final branch inactive|
| Terminal passenger correction |0 /0 /9|0/5→0/5|4/5→4/5|Local descent transfers, no target rescue|
| Terminal soft-mode kick |0 /0 /9|0/5→0/5|3/5→3/5|Seven eligible interventions, zero target rescues|

All seven comparisons hit27/27 practical targets in both arms. Full tables retain costs, crossing ranges, rejects, retry wall, PCG/outer and curvature events: [STCG](STCG_NATIVE_RESULTS.md), [additive](COARSE_NATIVE_RESULTS.md), [PI](PI_NATIVE_RESULTS.md), [accurate opening](FRONTLOAD_NATIVE_RESULTS.md), [unclipping](OPENING_UNCLIP_NATIVE_RESULTS.md), [passenger](PASSENGER_NATIVE_RESULTS.md), [soft kick](SOFT_KICK_NATIVE_RESULTS.md). The terminal rows separate non-LM probe work from ordinary LM retry/failure accounting. Inactive practical arms do not demonstrate an active-algorithm speed difference.

## Brief 0: solve versus model is not a binary classification

The audit captures three Venice witnesses, three Final3068 stop witnesses and a primary Ladybug1197 opening state, with two Ladybug controls. Three reference solves per state pass the reduced residual certificate. Some original full-normal checks fail; those failures are retained. Supplementary CPU point completion brings the three Venice full scaled residuals below 1e-10 without changing the nonlinear conclusion.

Venice0 has a genuinely useful missing linear direction: true decrease 0.547 for the captured Eta2 proposal versus 35.510 for the coherent reference. Venice1's raw reference instead increases cost 20.046; clipping restores a positive gain of 0.03486. The three raw Final references increase cost 218.8,205310 and 533927, while their clipped versions give almost the same useful decrease as Eta2. Thus greater linear accuracy can help one state and fail another, and clipping can dominate the difference.

At Ladybug the absolute point-only model error concentrates strongly: the top 200 points explain 98.39%, but two-view tracks explain only 26.42%. This is not exclusively a two-observation pathology. The historical2.4e4 point fling did not belong to the frozen champion; the verified current witness has one outward movement16.3 versus scene radius12.32. [Full decomposition and retained failures](analysis/FINDINGS.md).

## Brief 1: real coarse-space evidence, insufficient native benefit

The coherent Venice reference contains modes covered economically by the rigid-cluster basis. K8 removes a set of very small eigenmodes and reduces the measured dense reference condition number from about 1.245million to 4198, roughly 296x. This is spectral evidence, not a speed prediction. A 50-step RHS-started Lanczos trace alone does not resolve the smallest dense eigenvalue.

The native additive K8 implementation preserves the actual production operator and current coupled damping. On Final3068 it spends0.92–1.41s in repeated setup, with no hit-count gain; on Venice it pays0.35–0.38s and still misses. Production coarse matrices sometimes fail SPD and correctly fall back. Deflation/balancing and all K values were not timed; this is not the user's stronger all-K kill. [Native verdict](coarse/native/VERDICT.md).

The geometric Final partition was a weak distributed-mode test: nearly all cameras fell into one cluster. A pinned METIS covisibility control fixes that imbalance. At Final witness 5, K8 gauge-free **raw-reference minus raw-Eta2** coverage rises1.26%→86.65%. But the missing norm is only 0.412% of the reference norm; the equally clipped reference improves true decrease only 15.26747→15.27792. Coverage of raw reference minus the actually clipped Eta2 proposal is a different functional,19.60% there. Other K/cells include regressions. This graph pretest establishes coverage, not nonlinear usefulness or a native graph-solver win. [Graph report](coarse/graph_pretest/FINDINGS.md).

## Brief 2: charts improve some conditional steps but do not bound world motion

The 162-row conditional chart study finds large inverse-depth gains, including about 46% lower proposed Ladybug cost and about 1% lower Venice costs. They do not meet the supplied safety hypothesis: Ladybug outward flings rise from 1 to 63, maximum world displacement reaches1803 and two cheirality flips occur. Spherical angular boundedness does not bound Euclidean coordinates or remove projection horizons. Chart-dependent diagonal damping also changes the metric, so this is not purely a retraction ablation.

The 54-row depth-freezing follow-up removes the two flips and reduces maximum Ladybug displacement, but still leaves63 outward flings. On Venice it blocks the useful inward recovery of previously escaped points and loses the chart's cost gain. Both variants fail the original fling gate; no native chart rollout or claim that tau can be decoupled follows. [Charts](charts/FINDINGS.md), [depth freezing](charts/FINDINGS_DEPTHFREEZE.md).

## Brief 3: this Steihaug variant is not a replacement

The implementation uses the actual preconditioner norm, boundary interpolation, a curvature-boundary proposal and no persistent floor in that arm. Correctness passes. Two tight Final394 cells improve about 1.18x and 1.22x, but four practical cells regress; Final3068 target hits fall4/5→0/5. Fewer PCG iterations do not guarantee a useful outer step. The arm changes metric semantics and curvature handling together; it neither refutes all truncated-CG methods nor attributes failure to one ingredient. The previously rejected model-progress stopping overlap was not silently rerun. [Verdict](steihaug/VERDICT.md).

## Brief 4: numerical mechanism reproduced, with a missing error term

On the deliberately ill-conditioned3000-track synthetic cohort, separately rounded FP32 cross blocks yield negative minimum Schur eigenvalues3000/3000, versus 0/3000 for consistent-Jacobian energy forms. This is not a BAL event-frequency estimate. With an approximate point solve and residual e=s−Vlambda*u, the actual operator energy also contains u^T e. Replacing only the CG denominator by nonnegative terms can therefore hide inconsistency. The full product, point solve and intrinsic regularization must agree.

The practical targets encounter no numerical repairs, so avoided persistent floors cannot explain a practical speedup there. Coherent FP64 products are implemented and exercised in the reference and opening arm; no always-on consistent-FP32 bandwidth win is established. [Findings](gram/FINDINGS.md).

## Brief 5: confirmed opening sensitivity, failed simple racing predictor

Twenty repeated baseline runs per scene on Ladybug1197 and Final3068 give outer 5-cost Spearman correlations−.050 and+.202 with endpoint cost. None of the registered cheap log-derived alternatives passes its split-sample gate. This tests the observed stochastic repeated-config trajectory distribution, not every possible structured lambda perturbation or geometric predictor; no racing controller was rolled out.

The separate first-three-accept accurate-opening arm combines eta=.05, coherent FP64 products/RHS/point completion and oversized-step rejection instead of radial clipping. Its Venice confirmation is decisive within this protocol: original grid0/5→5/5, independent confirmation0/5→5/5, combined0/10→10/10; on target-time median 0.37605s, range 0.3730–0.4288s. There is no finite speedup ratio against a target the control never reaches.

It is a global negative despite this local positive: seven practical cells slow, worst2.33x; Final3068 loses its two observed successes. An audit of five Venice pairs shows the full opening can be23.64% worse after three accepts yet reach a better later result. Unclipping alone then fails to reproduce the win. The interaction among accuracy, numerical consistency and controller trajectory remains unresolved. [Predictor](PREDICTOR_FINDINGS.md), [opening verdict](frontload/VERDICT.md), [attribution](opening_unclip/VERDICT.md).

## Briefs6–8: controller, cubic and point-Newton screens

The PI radius rule produces a few small practical timing wins, but those target traces have no rejection storms. Its actual storm counts overlap and Venice median cost is12.29% worse. It fails its stated mechanism/promotion gate. This is one fixed PI/controller combination, not a universal control-theory negative.

The proposed free ARC Schur graft is algebraically invalid under coupled point damping: both the reduced matrix and RHS vary nontrivially with lambda. A valid full-normal, fixed-metric64-vector Krylov root-finder is implemented and tested instead. Its cubic root is accurate but its steps are almost identical to matched projected LM, with zero20% gain wins across three Venice states at N3. Full stationarity residuals remain77%,3.51%,2.85%; tiny projected root residual is not exact full-space convergence. No native ARC or comparison against PI's nine cells is claimed. [ARC report](arc/FINDINGS.md).

The conditional point-Newton witness screen fails sharply. One two-view point explains 99.9957% of a Ladybug cost explosion: its corrected block is positive definite, its world displacement is modest and both depth signs remain unchanged, yet one projected depth approacheszero and the image coordinate explodes. The issue is proximity to the projection horizon, which those guards miss. This conditional-backsubstitution screen does not refute every fully coupled partial-Newton implementation. [Point-Newton report](point_newton/FINDINGS.md).

## Briefs9–11: terminal mechanisms produce small changes, no target rescue

The initial coarse oracle's added same-fine-radius gate failed; the user's original zero-decrement kill did not. We therefore implemented the actual independently globalized passenger-cluster problem. It passes the three-witness mechanism gate2/3, with cumulative gains54.18x and 32.26x the tiny captured Eta2 gains. The largest full-cost improvement is only 0.0443%, and geometric clustering mainly isolates camera outliers.

Native continuation then accepts all three coarse steps in every eligible episode: five Venice misses and one Final miss. None reaches target. Every fine lambda/R/floor/forcing-history invariant is checked. The positive local descent mechanism survives implementation, but fails the registered convergence objective. [Native passenger verdict](coarse/nonlinear_native/VERDICT.md).

Per-track fractional selection and camera keep/move were tested on the requested Final stop witnesses. Reconstructing the existing point safeguard first reveals that all three baseline proposals already pass acceptance: there is no rejected baseline opportunity to rescue. Fractional moves add small gains; camera selection keeps all moved cameras. This is a limited conditional screen, not a universal no-benefit theorem for separable rescue. [Report](separable_rescue/FINDINGS.md).

The one-mode perturbation uses the actual generalized coarse Ritz problem, removes the seven camera-space similarity directions in the coarse-PCG metric, bounds predicted/true temporary cost increase and resumes with current controller history. All seven eligible kicks are admitted, but none rescues its run to target. Successful Final on-runs stop before the kick. The historical9/10 Eta2→MFREE portfolio is contextual, not a freshly rerun comparator; no new portfolio-superiority claim is made. [Soft-kick verdict](soft_kick/VERDICT.md).

## Brief 12: a valid two-stage method, insufficient work benefit

ROS2 passes fixed-chart gradient transport, order, dense-normal and full residual checks. The 27-row coherent CPU study gives one disjoint gain-per-work win against two successive LM steps and two disjoint losses. Against one LM step it has no disjoint win. At one Venice state the second-stage RHS produces negative prediction and a cost increase; positive rho from dividing two negative values does not make it acceptable. The full acceptance check rejects it. No native continuation is justified by that gate. [Report](rosenbrock/FINDINGS.md).

## What is novel, and what remains open

The building blocks have substantial prior art: multiscale and aggregation-based BA preconditioning, homogeneous/inverse-depth charts, Steihaug CG and Krylov cubic regularization. Representative primary sources include [Byröd and Åström](https://lup.lub.lu.se/search/files/6053078/1612241.pdf), [Konolige and Brown](https://arxiv.org/abs/2007.01941), [Square Root BA](https://arxiv.org/abs/2103.01843) and [the ARCqK author manuscript](https://optimization-online.org/wp-content/uploads/2021/03/8317.pdf). See the complete [math/prior-art audit](literature/MATH_AND_PRIOR_ART.md); no priority claim rests on a brief's assertion that a method is absent from BA.

The strongest current assets are reproducible mechanism evidence: separating linear accuracy from nonlinear value, identifying projection-horizon failure despite familiar guards, showing the difference between spectral coverage and paid convergence, and confirming a beneficial opening trajectory that early cost ranks incorrectly. These support focused research, not a claim of a new universally fastest solver.

The most motivated next experiment is to isolate tighter opening forcing while retaining ordinary storage, with a newly frozen global rule and all losing scenes retained. The already-completed clipping-only ablation rules out that ingredient alone. Graph-K8 model-usefulness, other deflation variants and a consistent-FP32 production path remain unmeasured possibilities. They are not marked successful, exhausted or refuted by the narrower tests here. The original Eta2 champion remains the reference for any continuation.

## Reproduction and storage

All work is isolated under `research/eta2_research_20260912/` on `research/eta2-diagnostic-agenda`. Individual protocols precede their data; build scripts/manifests reproduce native binaries, and `run_native.py` reproduces the registered panel. `report_native.py` and `plot_native.py` consume banked rows. Some complete endpoint contents are moved into verified local solid archives to respect the machine's quota; [archive manifests and restoration instructions](evidence_archives/README.md) preserve their numerical hashes. Large raw archives are local artifacts, while source, compact results, protocols, figures and manifests are versioned. Immutable witness deduplication preserves every original path and byte.

The final [evidence verification](FINAL_VERIFICATION.json) checks all 548 native result rows against individual files, input/binary hashes, champion flags, initial scores, CSV crossings, acceptance/product totals, and endpoint-container or durable-archive hashes. The source and 44 headers still match the frozen manifest. It verifies the 11 endpoint archives, including all 40 predictor states; archive creation had already verified every decompressed numerical member. This final audit runs without executing a solver. Legacy `stop_ftol` fields record marker presence, which is not a certified final stop reason after a terminal intervention; the new summaries label that distinction explicitly.
