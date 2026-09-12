# Eta2 wave 6 protocol: deterministic measurement before intervention

Registered before building or scoring the wave-6 native binary.

## Frozen controls and objective

The scientific control is `research/eta2_champion/champion.json`.  The optimized
systems control is `research/eta2_wave5/optimized_candidate.json`.  Neither file,
its source, nor its binary is modified.  Every scored endpoint remains the full
plain-L2 SIMPLE_RADIAL objective with unshared intrinsics and `k2=0`.

The supplied categorical map predates the completed wave-5 campaign.  In
particular, targeted Lindstrom-style two-view correction, Schur-Jacobi, dense
Schur Cholesky, square-root Schur products, and FP32 iterative refinement now
have native negative results.  Wave 6 does not repeat those cells without a new
mechanism.

## D0: deterministic trajectory substrate

The diagnostic binary is derived reversibly from the B6v7 source.  Under
`OCA_W6_DETERMINISTIC=1`, every floating-point reduction that can affect the
frozen Eta2 trajectory is assigned a fixed owner and fixed tree:

1. camera and point normal-equation assembly;
2. the point-side accumulation in every Schur product and scoring backsolve;
3. full nonlinear candidate cost;
4. the full-step slope and curvature used by the strict LM acceptance test.

B6v7 already supplies a camera-owned reduced RHS and batched FP64 CG scalar
returns.  Integer diagnostic counters are allowed to retain atomics because
their exact sums cannot change a decision.  cuBLAS vector reductions are
audited empirically for exact repeatability on this GPU.

The deterministic path is a measuring instrument, not a speed candidate; all
of its overhead is nevertheless recorded.  The disabled path must pass an N=3
compatibility screen against B6v7 at the Ladybug539 1.01 target.  The enabled
path must produce identical accepted-cost traces and identical endpoint SHA256
values in five repeated runs on Venice52 and Final3068.  Any mismatch blocks
the paired experiments and is localized before proceeding.

## D1: common perturbations and paired inference

Pairs use the same deterministic perturbed BAL input in both arms.  A seed
generates a zero-mean Gaussian tangent-sized perturbation with fixed per-field
scales; observations are byte-identical and `k2` remains zero.  The perturbation
amplitude is registered in the experiment-specific protocol and its initial
residual-space norm is reported.  Inputs live in `/dev/shm` and are removed
after their hashes and scalar results are retained.

The paired design reports every pair, including double misses.  Binary hit
outcomes use a Wald SPRT on discordant pairs with hypotheses fixed before a
cohort.  The default non-inferiority screen is

- harmful boundary `q0=0.35`, where `q=P(variant wins | pair discordant)`;
- non-inferior boundary `q1=0.50`;
- type-I and type-II risks `alpha=beta=0.05`;
- maximum 100 total pairs, with no conclusion if neither boundary is crossed.

The likelihood is updated only by discordant pairs, while total pairs and all
concordant outcomes remain reported.  This test answers direction among
discordances; it does not by itself bound the unpaired hit-rate difference.
Continuous time and endpoint comparisons use paired differences with a fixed-N
interval specified before each experiment.

Synthetic unit tests must recover the registered accept/reject boundaries and
show that arm order and concordant outcomes do not affect the likelihood.

## D2: finite-time Lyapunov diagnostic

Run the deterministic optimized control on Final3068 and Venice52.  For each
of eight registered directions, run an unperturbed state and a paired state
perturbed at relative field scale `epsilon=1e-12`, for ten accepted outer
iterations.  Repeat four directions at `epsilon=1e-10` as a linear-regime
check.  Dump states before outers 0 through 9 and at termination, compute all
reprojection residuals independently in FP64, then delete the states.

The gauge-invariant amplification is

`A_k = ||r(x_k + delta_k) - r(x_k)||_2 / ||r(x_0 + delta_0) - r(x_0)||_2`,

and the finite-time exponent is `log(A_k)/k`.  Also report the first accepted
outer, rejection, or stopping decision that differs.  Classify the opening as:

- sensitive/positive: median `A_10 > 1e3` and median exponent `>0.5` per outer;
- stable/switch-like: median `A_10 < 10` and median exponent `<0.1`;
- unresolved otherwise.

The two epsilon cohorts must agree in sign and their pre-saturation median
exponents must agree within 25%; otherwise report a numerical-scale ambiguity.
Positive FTLE sends the campaign toward map changes or portfolios.  A stable
trajectory with discrete decision divergence sends it toward soft/filter
acceptance.

## Subsequent cells

Only after D0-D2:

1. effective resistance plus k-core as a sparse camera-prior gate;
2. exact/global per-track algebra only if it improves on wave-5 A1's detector
   and explains a paired divergence;
3. soft or filter acceptance only if D2 identifies a switching mechanism;
4. remaining speed cells only where the wave-5 B0/B6 profile leaves a credible
   ceiling.

Every subsequent native arm gets a separate preregistration, N>=5 for a tail
claim, the existing fixed targets and caps, independent FP64 endpoint scoring,
and a plain negative verdict when its gate fails.
