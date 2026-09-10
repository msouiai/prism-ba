# Camera-block PCG and preconditioner reuse

**Verdict:** fresh camera-Hessian block PCG is the leading tested configuration. Its three Final13682 runs have median 6.904906s versus combined PRISM 12.529994s and Caspar FP32 8.387723s. It uses43 matrix products instead of160, with8 accepted steps and0 rejections. Final4585 is a single candidate run (2.324555s); Caspar misses the20s budget in all3 repeats. Other datasets and noise regimes remain unproven; this is an opt-in research configuration, not a universal BA superiority claim.

All comparisons use original-double BAL endpoint audits and solver-native time to the common audited target. Caspar FP32 retains its empirical .1% tighter native stopping margin; input loading is excluded and established solver setup-scope differences remain. GPU tasks serialized under the shared lock. CPU builds/audits can overlap loading.

## Confirmed combined candidate versus Caspar FP32

|Scene|Arm|Hits/runs|Median qualifying seconds|
|---|---|---:|---:|
|final-13682|combined|3/3|12.529993971|
|final-13682|caspar32|3/3|8.387722541|
|final-4585|combined|3/3|5.762373785|
|final-4585|caspar32|0/3|miss within 20s|

## Fixed-system results

Captured late Final13682 system, same `A = E S E + sigma I`, same RHS and true residual tolerance, maximum128 iterations. Mode0: identity preconditioner in the incumbent diagonal coordinates; mode1: camera Hcc blocks; mode2: Schur camera blocks. Setup and true-residual verification products included. No precision reduction. One timing per configuration; not BA speed ratios. The incumbent TR method can stop on its verified radius/model criterion without reaching this linear residual target, so linear-solve gains do not predict BA gains directly.

```
FIXED mode=0 tolerance=0.16872403451599022 iterations=128 products=129 true_relative=0.18936827460464964 hit=0 neg=0 setup_ms=0.00185600005 solve_ms=6594.50928 total_ms=6594.51123 fallback_blocks=0
FIXED mode=0 tolerance=0.01 iterations=128 products=129 true_relative=0.19909355961066971 hit=0 neg=0 setup_ms=0.00185600005 solve_ms=6593.5249 total_ms=6593.52686 fallback_blocks=0
FIXED mode=1 tolerance=0.16872403451599022 iterations=13 products=14 true_relative=0.15940879887591775 hit=1 neg=0 setup_ms=0.554336011 solve_ms=716.907593 total_ms=717.461914 fallback_blocks=0
FIXED mode=1 tolerance=0.01 iterations=128 products=129 true_relative=0.019496388820675583 hit=0 neg=0 setup_ms=0.554336011 solve_ms=6607.53125 total_ms=6608.08545 fallback_blocks=0
FIXED mode=2 tolerance=0.16872403451599022 iterations=7 products=8 true_relative=0.16281449051315569 hit=1 neg=0 setup_ms=243.435516 solve_ms=409.540192 total_ms=652.975708 fallback_blocks=0
FIXED mode=2 tolerance=0.01 iterations=103 products=104 true_relative=0.0096544480920768543 hit=1 neg=0 setup_ms=243.435516 solve_ms=5326.25586 total_ms=5569.69141 fallback_blocks=0
```

## Fixed product breakdown

Parts: 0 scaling/point-buffer clear, 1 scatter Schur pass, 2 point inverse, 3 gather Schur pass, 4 final scaling/shift, 5 two dot products, 6 one axpy. CUDA events perturb timings; host means include explicit event synchronization and are not an independent idle-time measurement. Separate parts are not a complete BA phase accounting.

```
PART id=0 gpu_median_ms=0.517279983 host_mean_including_event_sync_ms=0.516201571
PART id=1 gpu_median_ms=26.1116791 host_mean_including_event_sync_ms=26.1338776
PART id=2 gpu_median_ms=2.58099198 host_mean_including_event_sync_ms=2.58902843
PART id=3 gpu_median_ms=21.7853127 host_mean_including_event_sync_ms=21.797134
PART id=4 gpu_median_ms=0.00627199979 host_mean_including_event_sync_ms=0.0153157143
PART id=5 gpu_median_ms=0.0368640013 host_mean_including_event_sync_ms=0.0553971429
PART id=6 gpu_median_ms=0.006176 host_mean_including_event_sync_ms=0.0777542857
```

The two Schur passes account for about47.9ms out of roughly51ms per product; two scalar reductions cost about.04ms. Existing full-run Nsight data supports the same diagnosis. Hardware counters remain unavailable; no new driver change attempted.

## Implementation and mathematics

Ordinary PCG solves the unchanged shifted system. The existing `OCA_BLOCKEQ` route instead changes congruence coordinates and the damping/TR metric, so it is not used here. Let z=M^-1 r and p=z+beta p_prev. Then S z = A p - beta A p_prev - sigma z. The existing full-Gram projected TR solver can therefore capture z and S z, normalize each column, whiten its measured Gram matrix, and solve the projected TR model in the original Euclidean radius. No extra product per captured column. The reference model gate, direct full GN model, nonlinear point safeguard and original cost acceptance remain active.

Preconditioners are the normalized Hcc or Schur camera block plus sigma I, factored in FP64 with existing diagonal fallback for failed Cholesky. They stay fixed throughout each inner solve. This is a research candidate restricted to single-shift, unshared9DOF, diagonal-coordinate guarded TR. This is not a general multishift-PCG implementation.

The v2 binary checks explicit residual consistency at estimated convergence with a1% slack around eta; fixed-system targets are exact and the unchanged full TR acceptance remains mandatory. The v3 binary tightens that guard to the exact eta threshold and changes only the reuse drift rule. Seven-outer audit runs also explicitly check recurrence curvatures; they are excluded from timing comparisons.

## Reuse rule

v2 refreshes if any normalized Hcc diagonal changes by more than a factor2, after a retry, or after an inner solve longer than64 iterations. It made zero reuse decisions on the initial three-scene screen. v3 removes irrelevant uniform scaling: for diagonal ratios d_current/d_saved, reuse is permitted only when max/min <=4 (and all ratios finite positive). A positive scalar multiple of M leaves exact-arithmetic PCG iterates unchanged. This diagonal check is a heuristic for preconditioner suitability, not a bound on the full operator or its off-diagonal changes. Old factors remain SPD and no stale system/Jacobian is used. All checks and rebuilds are charged.

## schur-audit

Historical arm labels: double=combined incumbent, storage=candidate. N1 unless multiple rows per scene/arm. Audit folders are capped at7 outer iterations and do not test target completion.

|Scene|Arm|Hit|Seconds to target|Native seconds|Accept/reject|Products|
|---|---|---|---:|---:|---:|---:|
|trafalgar-126|double|False|None|0.185584|7/0|283|
|trafalgar-126|storage|False|None|0.131891|7/0|100|
|dubrovnik-88|double|False|None|0.165335|7/0|76|
|dubrovnik-88|storage|False|None|0.167099|7/0|42|
|final-1936|double|False|None|1.281938|7/0|76|
|final-1936|storage|False|None|1.402428|7/0|43|

## hcc-screen

Historical arm labels: double=combined incumbent, storage=candidate. N1 unless multiple rows per scene/arm. Audit folders are capped at7 outer iterations and do not test target completion.

|Scene|Arm|Hit|Seconds to target|Native seconds|Accept/reject|Products|
|---|---|---|---:|---:|---:|---:|
|trafalgar-126|double|True|0.460566395|0.466085|15/0|988|
|trafalgar-126|storage|True|0.280496363|0.283742|11/0|386|
|dubrovnik-88|double|True|0.679006625|0.700478|15/0|593|
|dubrovnik-88|storage|True|0.209964256|0.214359|10/0|97|
|final-1936|double|True|2.168740144|2.187927|8/0|179|
|final-1936|storage|True|1.559845564|1.579256|8/0|102|

## schur-screen

Historical arm labels: double=combined incumbent, storage=candidate. N1 unless multiple rows per scene/arm. Audit folders are capped at7 outer iterations and do not test target completion.

|Scene|Arm|Hit|Seconds to target|Native seconds|Accept/reject|Products|
|---|---|---|---:|---:|---:|---:|
|trafalgar-126|double|True|0.494258271|0.517031|16/1|1025|
|trafalgar-126|storage|True|0.303578885|0.324694|13/0|378|
|dubrovnik-88|double|True|0.676779265|0.681463|15/0|589|
|dubrovnik-88|storage|True|0.269314647|0.274024|10/0|92|
|final-1936|double|True|2.191146725|2.215254|8/0|179|
|final-1936|storage|True|1.650802731|1.670204|8/0|66|

## reuse-screen

Historical arm labels: double=combined incumbent, storage=candidate. N1 unless multiple rows per scene/arm. Audit folders are capped at7 outer iterations and do not test target completion.

|Scene|Arm|Hit|Seconds to target|Native seconds|Accept/reject|Products|
|---|---|---|---:|---:|---:|---:|
|trafalgar-126|double|True|0.556718173|0.574964|16/0|1226|
|trafalgar-126|storage|True|0.290422718|0.293458|12/0|326|
|dubrovnik-88|double|True|0.582562246|0.586847|14/0|483|
|dubrovnik-88|storage|True|0.273217859|0.278533|10/0|92|
|final-1936|double|True|2.175459868|2.233298|8/0|179|
|final-1936|storage|True|1.63057028|1.64987|8/0|66|

Reuse decisions: 0 reused / 30 preparations.

## reuse-scaled-audit

Historical arm labels: double=combined incumbent, storage=candidate. N1 unless multiple rows per scene/arm. Audit folders are capped at7 outer iterations and do not test target completion.

|Scene|Arm|Hit|Seconds to target|Native seconds|Accept/reject|Products|
|---|---|---|---:|---:|---:|---:|
|trafalgar-126|double|False|None|0.192342|7/0|283|
|trafalgar-126|storage|False|None|0.096054|7/0|100|
|dubrovnik-88|double|False|None|0.139234|7/0|76|
|dubrovnik-88|storage|False|None|0.152494|7/0|42|
|final-1936|double|False|None|1.267141|7/0|76|
|final-1936|storage|False|None|1.318533|7/0|43|

Reuse decisions: 3 reused / 21 preparations.

## reuse-scaled-screen

Historical arm labels: double=combined incumbent, storage=candidate. N1 unless multiple rows per scene/arm. Audit folders are capped at7 outer iterations and do not test target completion.

|Scene|Arm|Hit|Seconds to target|Native seconds|Accept/reject|Products|
|---|---|---|---:|---:|---:|---:|
|trafalgar-126|double|True|0.486739789|0.490246|16/0|1021|
|trafalgar-126|storage|True|0.277407841|0.280618|12/0|342|
|dubrovnik-88|double|True|0.586091769|0.591529|14/0|489|
|dubrovnik-88|storage|True|0.263895625|0.268264|10/0|92|
|final-1936|double|True|2.167742806|2.186906|8/0|179|
|final-1936|storage|True|1.589818171|1.622536|8/0|66|

Reuse decisions: 3 reused / 30 preparations.

## hcc-large

Historical arm labels: double=combined incumbent, storage=candidate. N1 unless multiple rows per scene/arm. Audit folders are capped at7 outer iterations and do not test target completion.

|Scene|Arm|Hit|Seconds to target|Native seconds|Accept/reject|Products|
|---|---|---|---:|---:|---:|---:|
|final-13682|double|True|12.535953254|12.588965|7/0|160|
|final-13682|storage|True|6.904905866|6.953849|8/0|43|

## schur-large

Historical arm labels: double=combined incumbent, storage=candidate. N1 unless multiple rows per scene/arm. Audit folders are capped at7 outer iterations and do not test target completion.

|Scene|Arm|Hit|Seconds to target|Native seconds|Accept/reject|Products|
|---|---|---|---:|---:|---:|---:|
|final-13682|double|True|12.561031847|12.605702|7/0|160|
|final-13682|storage|True|7.653730808|7.701658|7/0|35|

## winner-other

Historical arm labels: double=combined incumbent, storage=candidate. N1 unless multiple rows per scene/arm. Audit folders are capped at7 outer iterations and do not test target completion.

|Scene|Arm|Hit|Seconds to target|Native seconds|Accept/reject|Products|
|---|---|---|---:|---:|---:|---:|
|final-4585|double|True|5.752512115|5.779243|9/0|253|
|final-4585|storage|True|2.324554907|2.352364|8/0|49|

## winner-repeats

Historical arm labels: double=combined incumbent, storage=candidate. N1 unless multiple rows per scene/arm. Audit folders are capped at7 outer iterations and do not test target completion.

|Scene|Arm|Hit|Seconds to target|Native seconds|Accept/reject|Products|
|---|---|---|---:|---:|---:|---:|
|final-13682|double|True|12.528877004|12.576707|7/0|160|
|final-13682|storage|True|6.89739837|6.946423|8/0|43|
|final-13682|storage|True|6.907941465|6.960259|8/0|43|
|final-13682|double|True|12.530174965|12.576979|7/0|160|

## Reuse verdict

The scale-invariant rule reused one preconditioner per scene in the completed small-panel timing screen (three reuse decisions total). Its times were 0.2774s, 0.2639s, 1.5898s versus fresh Hcc 0.2805s, 0.2100s, 1.5598s in separate N1 screens. It did not consistently improve on the leading cheap preconditioner, so it was not advanced to a large run. The tiny Trafalgar difference is inconclusive. Keep fresh Hcc as the recommendation.

## Provenance

Artifacts `/workspace/prism-tr-preconditioner`; source `gpu/pcg_camera.cuh`; builders/harnesses/report under `bench/*pcg*` and `bench/*preconditioner*`. Frozen source/header/binary hashes in each build manifest. Production defaults remain unchanged. The prior combined candidate stays available. No GitHub push and no paused-job resumption.
