# FP32 Schur-products investigation — 2026-09-09

**Verdict: keep the guarded projected TR as the large-scene PRISM candidate. Caspar FP32 remains faster.** Ordinary FP32 products help the two small scenes modestly, regress Final-1936, and lose the projected-TR advantage on Final-13682. Compensated products restore numerical accuracy but are too costly in the small diagnostic screen. None of these prototypes is promoted to the production solver.

## What was implemented

Three isolated builds under `/workspace/prism-tr-fp32-products/`, all opt-in via `OCA_FP32_PRODUCTS=1`:

1. `build`: local per-observation Schur products in FP32 during CG. All cross-observation accumulation, point-factor solves, camera-block multiplication/final subtraction, preconditioning, CG/reductions, state and nonlinear acceptance remain FP64. Snapshot curvature and projected candidates are explicitly checked with the original FP64 operator. This is not a fully FP32 Schur operator.
2. `reliable`: adds reference-residual checks every 16 CG steps and before accepting the usual estimated-residual convergence condition. If the residual gap exceeds `min(0.001, 0.1*eta)*norm(b)`, or estimated convergence is false, replace the residual, restart CG from that residual and use FP64 products for the rest of that outer solve. Discard the projected basis after restart. The threshold is a trigger at check points, not an upper bound between checks. These checks are charged in timings.
3. `compensated`: split each FP64 vector component into float high/low parts and use float FMA to recover high-product rounding error. Accumulate in FP64 and retain the reliable policy. This approximates the original float-fragment/double-vector product far more accurately than an ordinary float product, but adds instructions.

The initial prototype exceeded the diagnostic residual-gap budget on Trafalgar (0.001182 relative to norm(b)); the failed run is retained. Dubrovnik passed. The reliable version completed the subsequent screens. In one timed Trafalgar run the gap reached 0.09599 at a check and triggered fallback; this is not a certified globally bounded inexact operator.

## Bounded equal-quality timing

Original BAL observations and exported states are independently evaluated in FP64. All completed solver outputs agree with the endpoint auditor within 1e-7 relative. Paired order alternates across three repeats. No profiler or diagnostic trace is enabled in the timing phase; mandatory reference checks remain enabled.

Historical harness labels `double` and `storage` mean **guarded projected TR control** and **FP32-products candidate** here; they do not describe full solver arithmetic.

| Scene | Guarded TR median | Reliable FP32-products median | Time change | Paired wins |
|---|---:|---:|---:|---:|
| dubrovnik-88 | 0.6822 s | 0.6216 s | -8.9% | 3/3 |
| final-1936 | 2.9883 s | 3.1885 s | +6.7% | 0/3 |
| trafalgar-126 | 0.5122 s | 0.4802 s | -6.2% | 2/3 |

All 18 timing endpoints met their targets. Trafalgar candidate fallback counts were 5, 7, 5; Dubrovnik and Final-1936 needed none. Final-1936 used 207–208 products versus 179–180 for the control. The added reference work is a plausible contributor to that regression; altered trajectories and per-product costs also matter.

### Largest scene: fresh N=1 comparison

| Arm | Certified target time | Endpoint cost | Outcome |
|---|---:|---:|---|
| control | 16.3376 s | 27232346.688 | Hit |
| tr | Missed 20 s budget | 27390782.846 | Miss |
| caspar32 | 7.7945 s | 27182334.203 | Hit |

`control` is guarded projected TR; `tr` is the reliable FP32-products prototype. Effective audited target: 27,318,392.35812812. Caspar FP32 uses the fixed 0.1% tighter native stopping margin, and receives credit at that stricter native crossing only after original-observation endpoint qualification. Native solver timing excludes CLI input loading; solver-local setup inclusion differs as documented in the preceding studies. One pair does not establish statistical certainty.

The prototype recorded 24.939 seconds because the time cap is checked at solver boundaries. It retained seven accepted steps with zero rejections and 308 total products, including an uncommitted eighth attempt. Its seventh committed endpoint stayed above target. This miss has no equal-quality speed ratio. The control reaches the target with seven accepted steps, zero rejections and 160 products.

## Compensated numerical screen

On 200,000 deterministic GPU product samples (seed 90209, exponent sampling -40 to 40), maximum relative error versus a host FP64 product was 8.88e-15, compared with 1.14e-7 for ordinary FP32. This test does not cover every underflow/overflow case or certify full-solver accuracy.

On the two small BA scenes, the compensated residual-gap maxima were 2.95e-10 (Trafalgar) and 4.23e-13 (Dubrovnik), with no fallbacks. Logged Dubrovnik projected-model error was at most 1.35e-13. Both endpoints qualified. However, diagnostic crossing times were 1.246 s vs control 0.477 s, and 1.424 s vs 0.699 s. These instrumented N=1 screens are not benchmark estimates, but the large slowdown is sufficient to stop this branch without an expensive large-scene run.

## Seven-iteration largest-scene profile

Separate instrumented attribution run (not a benchmark repeat):

| Kernel | Reference FP64 products | Ordinary FP32 products |
|---|---:|---:|
| Pass 1 | 26.123 ms | 26.696 ms |
| Pass 2 | 21.801 ms | 20.727 ms |
| Point inverse (unchanged) | 2.582 ms | 2.582 ms |

The representative three-kernel application improves only about 1%. Both variants were observed in the same instrumented run because the reliable method invokes the reference operator for verification. Pass 1 has double atomic accumulation; pass 2 retains double accumulation/reduction and the same indirect fragment access. These results revise the earlier broad precision diagnosis: changing local multiply precision alone scarcely accelerates the large-scene operator. Memory access, atomic accumulation and retained reductions are likely constraints, but hardware-counter evidence is needed to separate them.

All seven logged projected proposals (depths 32 through 128) fail the unchanged 1e-7 reference-model agreement gate. At depth 96, the exact reference FW-gap/prediction ratio is 0.04141, but reconstructed-model relative error is 7.78e-5, so it is discarded. At depth 128 error is 1.57e-4. Thus the candidate loses the useful projected step even though its residual-gap fallback is not triggered on this solve. These are distinct checks with distinct purposes.

The strict reduced-model agreement gate is conservative: a future experiment could rank proposals directly using the reference quadratic already evaluated, retaining the radius, reference-gradient and nonlinear acceptance tests. That would require an explicitly revised policy and separate comparison. This experiment did not silently weaken that gate.

## Mathematical interpretation

The Schur operator subtracts `W V^-1 W^T` from the camera block. Rounding in either pass can be amplified by cancellation. More importantly, the projected TR basis reuses identities from CG that assume a consistent linear operator. With product errors, recursively reconstructed `S Q` can disagree with the reference operator. Full Gram matrices address loss of orthogonality, but do not remove operator inconsistency.

The reference model threshold remains 1e-7. We did not loosen it to admit a cheap, inaccurate projected candidate. Nonlinear acceptance remains the existing FP64 full-model/actual-cost check.

## Reproduction and artifacts

Builders: `bench/build_tr_fp32_products.py`, `bench/build_tr_fp32_reliable.py`, `bench/build_tr_fp32_compensated.py`. They verify frozen parent source/header hashes and refuse to overwrite their build directories. The build chain starts from `/workspace/prism-tr-cg-stop/guarded`; its frozen inputs must be available.

Runs: `bench/tr_fp32_products_study.py` (supports `--candidate`), `bench/tr_fp32_products_large.py`. Product test: `bench/test_tr_compensated_product.py`. Attribution: `bench/profile_tr_fp32_products.py`. Summary: `bench/summarize_tr_fp32_products.py`.

Raw manifests, binary/source/header hashes, endpoint states and audits, failed-run logs, and summary are under `/workspace/prism-tr-fp32-products/`. All GPU work was serialized on the existing lock. The small and medium time caps remain 4/4/12 s; the largest cap remains 20 s. No paused jobs were resumed.

## Next priority

Keep guarded projected TR for the large scene. Profile memory transactions and atomic/reduction costs before another precision conversion. A focused next kernel experiment is point-owned or segmented accumulation in pass 1, replacing per-observation double atomic scattering while preserving the operator arithmetic and the projected-model identities. Evaluate operator accuracy and kernel cost on a fixed captured system before paying for complete BA runs. Assembly/point preparation and the full-model pass remain sizable independent targets.

Final verification: 33 completed endpoints independently audited, 1 failed initial prototype retained, three build manifests verified, 200,000 product samples checked, 11 paused jobs verified unchanged. Recorded completed BA native time: 102.353 s (includes diagnostics; excludes build, load/audit, profiler export and failed-run solve time). Python compilation and repository whitespace checks passed.
