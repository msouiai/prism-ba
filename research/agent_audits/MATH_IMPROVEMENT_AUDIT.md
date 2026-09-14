# Mathematical audit and ranked improvements

Date: 2026-09-14. Audited tree: `research/eta2-wave6-categorical`, commit
`edbc88770e7d40082b6e39c947cfd0f67e31ca6c`. This audit changes no solver,
configuration, historical score, or frozen source. No GPU workload was run.
The only new numerical work was a tiny dense CPU counterexample, floating-point
edge cases, and a read-only geometry audit of two existing Venice captures.

## Recommendation

Implement the small mathematical correctness and measurement improvements
below before commissioning another optimizer campaign. The completed record
does not support promoting a new Schur solver, stronger local regularizer,
point-polishing policy, or more accurate trajectory as a general improvement.
Those attractive ideas have already failed discriminating experiments.

| Rank | Improvement | Evidence and expected benefit | Promotion status |
|---|---|---|---|
| 1 | Correct zero-RHS PCG classification and overflow-safe forcing arithmetic | Two reproducible algebraic/numerical edge cases in the current code; avoids a false curvature event and incorrect forcing value | Implement in an isolated derived build; CPU certificates now, GPU compatibility later |
| 2 | Separate reduced linear convergence, full linear residual, and nonlinear stationarity | Existing reports have already encountered failed full-normal certificates and flat stops; makes diagnostics mathematically interpretable | Implement optional diagnostics and honest status fields; no new stopping policy |
| 3 | Report absolute paired reliability differences and uncertainty alongside the discordance SPRT | The current protocol explicitly admits that its SPRT does not bound the absolute hit-rate difference | Implement a CPU analysis helper; preserve all registered decisions |
| 4 | Reproducible arithmetic restart seeds on exactly the original input | D21 demonstrates restart complementarity, while D0 demonstrates that fixing one order fixes one basin | Research proposal only; determinism overhead is a serious obstacle |
| 5 | Audit radial-distortion folds separately from projection poles | A precise untested mathematical distinction, but the new Venice prescreen is negative | Diagnostic helper is valid; no Venice intervention justified |

None of these is a new general optimization theorem. Rank 4 could become a
useful solver experiment; rank 5 could become a new numerical diagnosis in a
different measured failure regime. Novelty in either exact application remains
unverified.

## Evidence reviewed and exclusions respected

The principal formulation sources were
`eta2_champion/docs/theory_and_novelty.md`,
`eta2_champion/docs/eta2_formulation_novelty_results.tex`, and the pinned
`eta2_champion/source/prism_eta2.cu`, `pcg_camera.cuh`, and `rl_actor.h`.
The experiment audit covered the first campaign's `AGENT_FEEDBACK.md`, wave-2
and wave-3 findings, wave-4 through wave-6 overviews/protocols, the wave-6
categorical status audit, and the individual results relevant to each proposal.
In particular:

* Wave 1 Steihaug changes lost Final3068 reliability; inverse-depth charts
  increased outward point motion; cubic and coarse proposals supplied no
  general target rescue. Exact full-normal certification was not universal.
* Wave 2 radius fitting and geodesic corrections improved selected local
  proposals yet lost native performance. The more accurate Venice opening
  remains scene-conditional.
* Wave 3 separates weak-camera directions, distributed opening rejection,
  and thin-track horizon sensitivity. The E4 point-level attribution is real.
* Wave 4's horizon constraints, projection homotopy, frozen-ray repair, and
  robust opening did not earn a general production policy.
* Wave 5 square-root products, Schur-Jacobi, dense Schur, and iterative
  refinement do not preserve the useful finite inexact trajectory. B6v7's
  measured systems changes remain the production-oriented lead.
* Wave 6 D3 made perturbation propagation smoother with FP64 fragments but
  obtained 23/35 versus 25/35 hits and a 1.6342 median double-hit time ratio.
  D7 moved the focal/depth soft mode without fixing the global step. D13,
  D13b, D14 and D12 closed the tested GMRES/restart/communication/Nystrom paths.
  D18--D20 supply strong fixed-state local mechanisms without a successful
  general native trigger. D22/D23 fail their particular terminal policies.
  D21 achieves 37/38 episode hits; D24's fixed outer-15 predictors fail.

These are implementation- and protocol-specific negatives. They are not
proofs against every member of the corresponding mathematical families.
Equally, changing a family name is not sufficient justification to rerun it.

## 1. Zero reduced RHS and forcing arithmetic

### Derivation and actual code defect

Write the damped normal system as

\[
H_\lambda d=-g,\qquad
H_\lambda=\begin{bmatrix}U+\lambda D_c&W\\W^T&V_\lambda\end{bmatrix},
\quad V_\lambda=V+\lambda D_p.
\]

The reduced RHS is
\(b_\lambda=-E(g_c-WV_\lambda^{-1}g_p)\).
If it is exactly zero, `z=0` already solves the reduced camera system.
It does **not** imply `g=0`, because point elimination can cancel the camera
RHS while the point-only correction remains nonzero.

The source obtains `nb` at line 10834, enters PCG at approximately line
11092, and checks `pAp > 1e-14*pp` at line 11099. For an exactly zero RHS,
both sides are zero. The code reports a curvature truncation and pays for a
Schur product despite already possessing the exact reduced solution.
The subsequent numerical-repair branch at line 11256 requires `nc_pp>0`,
so this exact-zero case **does not directly increase the numerical floor**.
That distinction matters: the defect is false classification and unnecessary
work, not a demonstrated damping storm on zero gradients.

A checked dense example is

\[
H=\begin{bmatrix}2&1\\1&1\end{bmatrix},\quad
D=I,\quad \lambda=1,\quad g=(1,2)^T.
\]

Then \(b_\lambda=-(1-2/2)=0\), yet
\(d=(0,-1)^T\) solves the full damped system exactly. Its undamped quadratic
decrease is \(-g^Td-d^THd/2=1.5\). It can be realized by the least-squares
Jacobian \(J=\begin{bmatrix}\sqrt2&1/\sqrt2\\0&1/\sqrt2\end{bmatrix}\)
and residual \(r=(1/\sqrt2,3/\sqrt2)^T\): cost falls from 2.5 to 1.
Stopping BA when the reduced RHS vanishes would therefore introduce a bug.

A separate arithmetic defect occurs at line 10842:

```
q = (nb*nb)/(prev_bnorm*prev_bnorm)
eta = min(eta_max, 0.9*q)
```

Finite norms `(1e200, 2e200)` produce `inf/inf`; `(1e-200, 2e-200)`
produce `0/0`. Both should give a pre-factor tolerance of 0.225 and the
Eta2 tolerance 0.45. In the current `std::min(eta_max, NaN)` ordering, the
NaN instead selects the cap. These CPU counterexamples were reproduced.
No claim is made that these norm scales occur in the banked BAL problems.

### Implementable algorithm

1. Derive an optional isolated change, e.g. `OCA_AUDIT_ZERO_RHS=1`, scoped to
   the already supported classical, single-shift camera-PCG path.
2. If `nb` is finite and exactly zero, leave the already-zero camera solution
   in place, skip PCG preparation/products, report zero iterations and no
   curvature event, and execute ordinary point back-substitution, nonlinear
   scoring, and acceptance. Do not return from the outer solver.
3. Audit every use of `cg_it+1`, especially `Score(...,cg_broke?cg_it+1:maxck)`
   near line 11280, so the zero solve is not recorded as one iteration.
4. Treat nonfinite norms as invalid; do not classify them as zero/converged.
5. For exceptional norm magnitudes use `ratio=nb/prev_bnorm`, cap before a
   dangerous square, and square only a finite bounded ratio. Keep the original
   arithmetic in its safe range if ordinary-path bitwise parity is required.
   The first-attempt/zero-previous-history policy stays unchanged.

**Assumptions and prior art.** The reduced linear problem and point factors
are valid, `E` is the current active scaling, and masks remain fixed. These
are elementary linear-solver checks and safe evaluation of an established
forcing formula, not novelty claims. The broader forcing method is inspired
by [Eisenstat and Walker](https://users.wpi.edu/~walker/Papers/forcing_terms,SISC_17,1996,16-32.pdf);
Eta2's changing reduced system does not directly inherit their convergence
theorem.

**Discriminating prediction.** Exactly zero reduced solves lose their false
negative-curvature count and one unnecessary product, while a nonzero point
correction survives. The extreme-norm examples return 0.45 after Eta2's
factor. Ordinary safe-range arithmetic and decisions remain unchanged.

**Minimal registered test.** Before GPU work, test the constructed cancellation
case, `g=0`, a nonzero-RHS control, subnormal/large finite ratios, and NaN/Inf.
Require exact zero camera iterations and a full damped residual at roundoff
on the cancellation case. Later, compare derived-off/on on the existing tiny
synthetic CUDA problem and one deterministic compatibility cell. That future
GPU check is not performed in this audit.

**Overhead and kill criterion.** Host comparisons reuse the existing norm;
the zero branch saves a product and preconditioner work. Kill the proposed
implementation if it bypasses point scoring, accepts invalid data, misreports
depth, or changes safe-range results unexpectedly. Do not claim a BAL speed
gain without observing the branch in BAL.

## 2. Full residual and nonlinear stationarity certificates

### What the existing reduced certificate does and does not prove

Let the true reduced residual be \(r_s=b_\lambda-A_\lambda z\), and let
the point completion residual be

\[
r_p=V_\lambda d_p+W^Td_c+g_p.
\]

With \(d_c=Ez\), elementary substitution gives the exact identity

\[
r_c=(U+\lambda D_c)d_c+Wd_p+g_c
     =-E^{-1}r_s+WV_\lambda^{-1}r_p.
\]

Consequently a small reduced residual alone is not a certificate for an
inaccurate point solve. Even exact point completion only certifies the
particular damped linear model. It says nothing by itself about the gradient
at the accepted nonlinear endpoint. Clipping cameras and recomputing points
also invalidate a certificate for the original raw camera vector.

The existing first-campaign reports record failed full-normal certificates
despite satisfactory reduced residuals; wave-5 refinement demonstrated that
passing the forcing tolerance does not preserve nonlinear basin selection.
D23's only invoked camera-block audit inherited `lambda=2.13e6` and committed
zero sweeps. This refutes that registered policy, not stationarity with respect
to every joint direction.

### Implementable diagnostic

Record three distinct objects, using the same point/camera coordinate masks:

* `reduced_linear_relative_residual`: the existing certificate for the raw
  camera solve, together with its exact damping/scaling identity.
* `full_linear_relative_residual`: independently compute
  \(\|D^{-1/2}(H_\lambda d+g)\|/
  \max(\|D^{-1/2}g\|,\epsilon_{\rm abs})\) for the specified full step;
  also verify the identity above and report the point/camera contributions.
* `endpoint_scaled_gradient`: independently assemble the original-objective
  \(g=J^Tr\) at the final state and report
  \(\|D^{-1/2}g\|\), its infinity norm, and the residual norm separately.
  This gradient excludes intrinsic solve priors and LM damping. Use a stated
  positive diagnostic diagonal/trace floor, and label its units/metric.

For a zero denominator, report an absolute residual instead of manufacturing
a large or tiny relative certificate. A zero reduced RHS is not an endpoint
stationarity certificate. On a step that has been clipped or safeguarded,
store a fresh full linear residual rather than attaching the raw-step value.

Initially implement this in the existing CPU endpoint/capture auditor, with
no additional production GPU pass. Use explicit stop reasons such as
`target_reached`, `flat_progress`, `iteration_limit`, `time_limit`, and
`invalid_linear_system`; add a separate stationarity diagnostic when one was
actually computed. Keep frozen solver stopping decisions unchanged.

**Assumptions and prior art.** The full linear certificate requires matching
stored blocks, factorization, regularization, and scaling; a coherent-Jacobian
certificate is a different object and should receive a different label.
First-order stationarity is chart- and metric-reported here, with a zero
gradient invariant under nonsingular local coordinate transformations.
Gauge freedom prevents inferring isolated minimizers or identifiable physical
parameters. [Ceres documents distinct function, gradient, and parameter
termination criteria](https://ceres-solver.readthedocs.io/latest/nnls_solving.html);
the proposed distinction is standard numerical analysis.

**Discriminating prediction.** Some endpoints labeled flat will remain above
a predeclared gradient threshold, and some raw reduced certificates will not
extend to modified/full directions. Conversely, the zero-RHS counterexample
will show zero reduced residual with nonzero original gradient. Those results
improve classification; they do not imply that more iterations rescue a basin.

**Minimal registered experiment.** CPU tests: exact dense Schur elimination,
deliberately perturbed point completion, camera clipping with fresh completion,
masked `k2`, zero RHS/nonzero point gradient, and zero full gradient. Then run
the diagnostic on the already preserved first-campaign witnesses and D23
terminal miss, retaining every finite/nonfinite case. The report of existing
states is retrospective. Any stop-policy intervention requires a separate
preregistered cohort.

**Overhead and kill criterion.** One streamed Jacobian/gradient pass at an
endpoint, and a matrix-vector/residual calculation per audited direction;
memory can remain linear in state plus a chunk of observations. Optional CPU
diagnostics add no solver time unless explicitly included. Kill a supposed
certificate if block identities disagree beyond the stated arithmetic error,
if it mixes coherent and compact operators, or if state/step provenance is
missing. Do not turn a diagnostic threshold into a new production stop by
default.

### A limited globalization argument, and why it does not certify Eta2

At a fixed smooth state with a positive bounded metric `D`, bounded normal
matrix `H`, and an exact full solve,

\[
d_\lambda=-(H+\lambda D)^{-1}g
 =-\lambda^{-1}D^{-1}g+O(\lambda^{-2}).
\]

Thus \(g^Td_\lambda=-\lambda^{-1}\|D^{-1/2}g\|^2+O(\lambda^{-2})\).
Under repeated ideal radius contractions preserving
\(\lambda R^2=K>0\), the scaled raw camera norm is `O(1/lambda)` while
`R=O(1/sqrt(lambda))`; eventually clipping becomes inactive. At a smooth
nonstationary state the true/model ratio tends to one, so sufficiently large
finite damping yields an accepted descent step in ideal arithmetic.

This is a local asymptotic explanation, not a global theorem for the code.
An inexact extension needs a suitable full residual/angle bound, which the
current reduced test alone does not provide. The implementation has caps,
finite arithmetic, heuristic flat stops, and state-dependent scaling. Rational
projection can approach `Z=0`, so uniform smoothness/compact-level-set
assumptions cannot simply be asserted. Similarity gauge and additional weak
focal/depth modes also obstruct isolated-solution assumptions. More damping,
more PCG, or another Cauchy fallback is therefore not recommended on the
strength of this asymptotic calculation.

## 3. Absolute paired reliability and uncertainty

For paired target hits `Hv,Hc`, let
\(p_{10}=P(H_v=1,H_c=0)\), \(p_{01}=P(H_v=0,H_c=1)\),
and \(q=p_{10}/(p_{10}+p_{01})\) when discordance is nonzero. Then

\[
\delta=P(H_v=1)-P(H_c=1)=p_{10}-p_{01}
      =P(\text{discordance})(2q-1).
\]

The wave-6 SPRT tests a hypothesis about `q`. It cannot by itself certify a
fixed absolute reliability margin. For example, `q=0.4` corresponds to
`delta=-0.004` if discordance is 0.02 and `delta=-0.16` if discordance is 0.8.
The existing wave-6 protocol already states this limitation; the improvement
is to make the missing estimand explicit in machine-readable reports.

### Implementable algorithm

Always report all four pair counts, `N`, `delta_hat=(n10-n01)/N`, and the
discordance fraction alongside the existing SPRT. A simple conservative
exact fixed-N interval needs no new statistical model:

1. Construct Clopper--Pearson intervals for `p10` and `p01`, each with
   coverage `1-alpha/2` (each tail therefore uses `alpha/4`).
2. Return `[L10-U01, U10-L01]` for `delta`, intersected with `[-1,1]`.
   Bonferroni proves coverage at least `1-alpha`; independence of the two
   discordance counts is not required.
3. If reporting an interval after arbitrary sequential stopping, assign
   `alpha_n=alpha/[n(n+1)]` at each total-pair count, then apply step 1 with
   `alpha_n`. Since `sum alpha_n=alpha`, a union bound gives simultaneous
   coverage over all positive `n`. Label this conservative interval explicitly;
   do not call a fixed-N interval anytime-valid.
4. Report `N=0` as undefined. Zero discordances imply an estimated difference
   of zero, not zero uncertainty. Preserve existing registered SPRT decisions.

**Assumptions and prior art.** Independent identically distributed pairs,
from the preregistered perturbation/instance population; within-pair dependence
is allowed. The effect is for that population, not automatically for native
unperturbed arithmetic. Exact binomial intervals, Bonferroni, and alpha
spending are established. More efficient confidence sequences are available
in [Howard et al.](https://arxiv.org/abs/1810.08240), but the elementary bound
above is easier to audit and is not claimed to reproduce their sharper method.

**Discriminating prediction.** D3-like many-discordance studies and
D15-like almost-all-concordant studies will show visibly different uncertainty
about absolute effect even if their conditional win fractions are similar.
This prevents interpreting a few discordances as a measured large reliability
improvement.

**Minimal registered test.** Exact small-N multinomial enumeration at a fixed
grid of cell probabilities must achieve at least nominal coverage. Test arm
swap symmetry, all concordant pairs, all one-sided discordances, empty data,
and alpha-spending arithmetic. Recompute old ledgers only as additional
descriptive audits; do not reopen or relabel their registered decisions.
For a future margin `m`, preregister promotion as a lower interval bound above
`-m`, plus separately specified timing/quality gates.

**Overhead and kill criterion.** CPU scalar beta quantiles per report, zero
GPU work. Reject an implementation with undercoverage, incorrect tail budgets,
or a sequential claim attached to a fixed-N interval. Conservative intervals
may be too wide to decide a small-budget experiment; that is an inconclusive
result, not a reason to silently switch tests. Scene-level generalization must
also treat three scenes at three tolerances as three scene clusters, not nine
independent scene samples.

For portfolios, report charged all-run wall, target-hit probability by a fixed
deadline, and failed-run time explicitly. Conditional successful-run time
alone is selection-sensitive. The exact sequential work is
`T1 + 1{miss1}T2 + 1{miss1,miss2}T3`; use conditional rescue rates rather than
assuming `1-(1-p)^3`. D21's lag-one hit correlation of 0.022 is evidence of
weak observed serial association, not a proof of independence.

## 4. Seeded deterministic arithmetic portfolios

**Mechanism and derivation.** D0's fixed reductions select one reproducible
trajectory; D21's unchanged fresh arithmetic restarts rescue 13/14 initial
misses. Model each fixed reduction ordering as a map `T_s` indexed by a seed.
The exact objective and observations remain identical while rounding creates
different numerical trajectories. A portfolio uses a preregistered sequence
`s1,s2,s3` and charges every attempted solve. Its hit probability is obtained
from conditional rescue probabilities, without an independence assumption.

This is distinct from D1/D3 input perturbations: the original input bytes
remain identical, making the mathematical problem exactly the same. It is
also distinct from D24: no early predictor or learned state is introduced.

**Implementable algorithm.** Extend the deterministic owner-reduction
instrument with a seed-dependent permutation of summands within each owner,
fixed for a whole solve. Preserve observation IDs, ownership, masks, and the
shared cross-block values used by both sides of each product. Hash the order,
seed, input, binary, arithmetic flags, endpoint, and decision trace. Start
with order generation on CPU; charge preprocessing. Never randomize one side
of the mathematical cross operator inconsistently. Do not reuse Krylov vectors
or mutate the observations. The first implementation is an instrument, not a
production replacement for B6v7.

**Assumptions and prior art.** Same seed reproducibility is only claimed under
the recorded compiler/GPU/library environment until cross-host checks pass.
The seed distribution must be fixed before evaluation; observations from
adversarially selected successful seeds are not reliability estimates.
[Algorithm portfolios are established](https://www.cs.cornell.edu/selman/papers/pdf/01.aij.portfolios.pdf).
The potentially distinctive result would be controlled arithmetic diversity
for this finite inexact BA map, not a new portfolio formula or proof of chaos.

**Discriminating prediction.** A repeated seed reproduces bytes; distinct
seeds provide nontrivial target-outcome diversity on the original input. If
that fails, input perturbation and native scheduler variation are not
interchangeable with the proposed controlled arithmetic family.

**Minimal registered experiment.** First, pure CPU owner/permutation tests
prove no observation is omitted or duplicated and replayed seeds reproduce
orders. A future GPU gate uses three fixed seeds repeated three times on
Venice and Final3068; all within-seed traces must match, before any reliability
analysis. Then register a fresh seed panel and three-attempt scheduler,
compare charged deadline hit rates with native B6v7 and D21-style launches on
the same host, and preserve all failed episodes. No seeds may be chosen from
their measured final costs.

**Overhead and kill criterion.** `O(nobs)` ordering/preprocessing plus the
deterministic kernels' overhead. D0's Final3068 runs took 13.235--13.292 s;
D21's first-hit conditional median was 3.2975 s in a different native cohort.
Those are not a clean speed ratio, but they warn that determinism can erase
the portfolio's practical gain. Kill operational promotion if the registered
same-host deadline/charged-time gate fails or distinct seeds supply no
useful diversity. Do not build it merely to replace working fast native
restarts with a slower reproducibility experiment.

## 5. Radial folds: distinct diagnostic, negative Venice prescreen

Projection poles are not the only singular geometry in SIMPLE_RADIAL. For
`q=(Yx/Z,Yy/Z)`, `r2=q.q`, and
\(\pi(q)=f(1+kr^2)q\),

\[
D_q\pi=f[(1+kr^2)I+2kqq^T].
\]

The eigenvalues along tangential and radial image-plane directions are

\[
f s_t=f(1+kr^2),\qquad f s_r=f(1+3kr^2).
\]

For negative `k`, the radial fold occurs at `r2=-1/(3k)` and tangential
collapse at `r2=-1/k`, even when depth stays far from zero. Their determinant
is `f*f*st*sr`. `f=0` is another separate degeneracy. Away from `Z=0`, these
can be checked without a Hessian/eigensolver. Radial invertibility is
established camera-model theory; [OpenCV's calibration documentation](https://docs.opencv.org/5.0/main_modules/calib.html)
also explicitly discusses monotonicity and bijectivity. The formulas here
follow directly by differentiation, not from a new theorem.

The reviewed wave-1--6 texts focus on depth poles, intrinsic correlation,
and track conditioning. A fold-specific test was not found. A physically
motivated barrier would nevertheless alter the feasible optimization problem
and could forbid basins admitted by the frozen plain-L2 objective. Therefore
the only proposed first action was a read-only audit.

### New CPU evidence

Before inspecting outcomes, the two captures were fixed as Venice terminal-0
and opening-0/attempt-2, corresponding to the already used D7 witness/control.
All 347,173 original observations were evaluated in each. The archive SHA256
and each state member SHA256 were checked against the existing manifests.
The archived `k2` values are exactly zero, and all focal lengths are positive.

| Quantity | Terminal-0 | Opening-0 / attempt 2 |
|---|---:|---:|
| Nonpositive radial margins | 0 | 0 |
| Nonpositive tangential margins | 0 | 0 |
| Observations with either absolute margin below 0.01 | 0 | 0 |
| Minimum radial margin | 0.8192154198240446 | 0.7195450547000779 |
| Minimum tangential margin | 0.9397384732746815 | 0.9065150182333592 |
| Camera-34 minimum radial margin | 1.0013498102488714 | 1.0033942043981499 |
| Camera-34 radial coefficient | 1930.6254420852174 | 0.8637308639907126 |
| Camera-34 focal length | 112750.74203955283 | 1572.113703551817 |

Terminal archive:
`eta2_wave2/composition/terminal-static-0-0/snapshots.tar.xz`,
SHA256 `08b97bd77e47091f5176f67ec3c783e23c702e7175e2613385737353df628628`.
Opening archive: `/workspace/eta2-wave3-evidence/opening-capture-0.xor.tar.xz`,
SHA256 `a4a4a03991139d18d67a860dd1b6c2ec65348dbcb3011d322bd97337d52906b5`.
State/hash layouts are in `eta2_wave3/forensics/venice-terminal-0.json` and
`eta2_wave3/opening-captures/0/result.json`. Arrays were decoded in memory;
no solver run or state mutation occurred.

**Decision:** a radial fold does not explain the known Venice weak-camera
failure. Its camera 34 has positive, large `k` and margins above one. This
prescreen kills a fold intervention for that witness; it is not evidence
about every Final3068 trajectory.

**Implementable diagnostic.** A pure CPU helper returns `st`, `sr`, determinant,
finite status, and a distinct depth-pole mask, optionally summarized by
camera/track. Do not replace undefined `Z=0` values with invented finite
coordinates. For `k=0`, the radial margins are exactly one even when forming
`r2` would overflow; finite `q` and image-point status still need reporting.
No barrier, camera freeze, point move, or acceptance change is justified now.

**Assumptions, prediction, experiment, overhead, kill criterion.** The formula
assumes SIMPLE_RADIAL and `k2=0`; finite differences of the 2x2 image-plane
Jacobian must match both eigenvalues. Test `k=0`, a generic finite point,
`k=-1,r2=1/3`, `k=-1,r2=1`, `f=0`, and the depth-pole limit. A future
fixed-state Final3068 audit must preregister witnesses before checking
association with misses, and must distinguish geometric prevalence from
causal repair. Cost is a few scalar operations per observation if fused into
an existing CPU projection pass, with no new solver cost. A zero/small-margin
intervention is killed when failing states have margins comfortably bounded
away from zero, as in the measured Venice pair.

## Integration boundary

The implementation agent received the exact zero-RHS edit sites, the corrected
`nc_pp>0` interpretation, forcing edge cases, the paired-difference formulas,
and the radial-fold negative result. The recommended immediately reviewable
deliverable is a derived robustness change plus tested CPU diagnostics and
inference helpers. GPU runtime parity and speed remain unmeasured in this
audit. The frozen scientific champion and the measured B6v7 systems candidate
remain the reference winners until a separately registered comparison earns
a replacement.
