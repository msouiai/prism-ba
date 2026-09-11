# Pair restoration and precision follow-up — registration, 2026-09-11

Parent branch `research/eta2-curvature-audit`, commit26f95c2. No changes to
the original solver or frozen champion. This registration precedes new
optimization measurements. The completed three-state curvature audit is
reused as evidence; it already found negative mixed-precision quotients
becoming positive when cross blocks alone were recomputed in FP64.

## Pair restoration

At each accepted ordinary step with relative true-cost decrease strictly
greater than max(1e-4,10*OCA_FTOL)=1e-4, save the outgoing damping center
and outgoing radius as one pair. This is the meaningful-progress boundary
already used by Eta2's backtracking rearm. Do not update the saved pair on
tiny accepted steps, rejected trials or a rescue probe. If no such accepted
step has established a positive finite radius, do not invent a saved pair.

When the original solver would finally stop after its existing confirmation,
record that stopping state/cost/time, restore the saved lambda AND radius,
and run one depth probe. If the current numerical floor raises saved lambda,
shrink saved radius by sqrt(saved_lambda/applied_lambda) to preserve lambda R²
under that clamp. Keep the numerical floor; no blind lowering of it.
The probe uses residual ratio <=min(original_eta,1e-3), cap512, and disables
backtracking. Existing true-cost decrease, full-model rho>.1 and radius
feasibility remain mandatory. One stopping probe per run. Failure restores
the original controller and terminates at the original endpoint; acceptance
resumes ordinary Eta2. Original 600-outer/60-native-second caps remain.

## Probe-only cross-block precision

Optional FP64 cross blocks are rebuilt from the exact current accepted
state only when a probe fires. Lazy allocation and rebuild time are charged
inside the solver timer. Use those blocks consistently in the Schur RHS,
matrix products and point back-substitution. Keep Hcc, point factors, scaling
rules, damping and preconditioner policy otherwise unchanged. Original FP32
buffers remain for ordinary iterations. Invalidate factor/RHS caches on both
entry and fallback. Restore ordinary storage after the one-shot intervention.

This removes the specific fault observed in the previous three captures;
FP64 cross blocks with rounded point rows are not a universal PSD guarantee.
Retain the curvature cutoff. A negative result does not establish a saddle
of the nonlinear BA objective: the damped Gauss–Newton matrix should be SPD
under positive damping in exact arithmetic, so precision/assembly needs
checking first. No cutoff relaxation is registered.

## Arms and primary measurements

Frozen original binary and exact champion flags; zero k2, fixed observation
L2, independent CPU FP64 endpoint audit, input/source/binary hashes, all
native target times, misses, probe witnesses, products, costs and caps.
Serialize builds, solves and CPU audits on `/tmp/prism_gpu.lock`.

- `original`: frozen Eta2 binary.
- `off`: new binary with all new features off (compatibility control).
- `pair`: one-shot pair restoration, existing mixed operator.
- `pair64`: pair restoration with FP64 cross blocks during that probe.
- `declip`: previous one-shot mixed de-clipping policy, unchanged.
- `declip64`: same policy with FP64 cross blocks during the probe.
- `both64`: pair restoration and de-clipping, FP64 cross blocks on probes.

1. Compatibility: Dubrovnik88 original/off, N=3 each, ordinary endpoints.
2. Final3068: original/pair/pair64, N=10 each, rotating order, identical
   target1744796.9841897595. Primary success requires at least two actual
   above-target stopping witnesses, all witnessed stops eventually rescued,
   and conditional successful-run median <=3.96s (1.2*the registered3.3s).
   Any remaining witnessed miss kills that arm. Fewer than two witnesses is
   insufficient coverage, not a pass. Also report fresh original hit/time
   distributions; favorable new trajectories without a probe are not rescues.
3. Venice52: audit-cleared secondary scene, original/pair/pair64/declip/
   declip64, N=10 each, rotating order, identical target243740.27. Zero hits
   kills the arm. Report actual probe acceptances and curvature cutoffs,
   not just endpoint changes. A nonzero hit count is not a precise reliability
   estimate or proof of speed superiority over solvers missing the target.
4. No-regression: Dubrovnik88/Ladybug1197, original/off/pair/pair64/declip64/
   both64, N=3 each, ordinary endpoints and rotating order. Any paired endpoint
   regression >0.5% or native wall >20% fails the requested guard. Report
   medians/ranges too; the old flags-off outlier means such failures are not
   automatically causal. These endpoint times are not time-to-equal-quality.
5. Only if pair64 passes its Final3068 gate and declip64 hits on Venice:
   both64 N=10 on each target scene, same caps and witness reporting.

No change of saved-pair boundary, forcing, expansion factor, depth or stop
count in response to these results. Further variants need a dated amendment
and cannot replace registered failures. Preserve every endpoint/state.

## Cross-check on Claude's trajectory states

When `/workspace/collab/results/v52_states/` arrives, verify its manifest and
original observation/model correspondence before consuming snapshots.
Expected panel: outers40/60/90/120/180/299 across three trajectories.
Use every available requested state, documenting omissions; no cost-based
cherry-picking. Evaluate Eta2's operator at a common lambda=tau=1e-8, the
same damping as its audited failure. These need not equal MFREE's actual
controller settings and are not comparisons of native stopping behavior.

Capture the input linearization without an optimization update. Construct
the 468-by-468 reduced camera matrices from exported components, compare
their smallest eigenvalues, and evaluate any mixed negative eigenvector in
the FP64 reference at the identical state/damping. Validate matrix products
against captured native products and scalar extended-precision quotients.
Retain dense matrices/eigenvectors, metadata, original input hashes and
analysis; full operator arrays may be processed one state at a time to bound
storage, retaining the first complete external-state capture as a witness.

This is a numerical audit, not an optimizer benchmark. A positive FP64
quotient on a mixed negative eigenvector clears that particular false-cutoff
mechanism; it does not prove every optimization trajectory will succeed.
