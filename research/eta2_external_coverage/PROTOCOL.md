# External coverage and Venice52 reachability — 2026-09-11

Frozen before new solver measurements. No new solver algorithm or global
champion selection. Original Eta2 and all previously measured files stay intact.
All timed CPU/GPU solves serialize with /tmp/prism_gpu.lock; no heavy audit or
compilation overlaps a timed run. Compact states/logs only. The old OS-stopped
workers are left stopped; this study uses a separate evidence directory.

## Ceres storm coverage

Use the exact banked ceres-frozen binary, SHA256
6543c8e6f9baa69c421eeda61aef5d1115ca0d825931b71905904f1f53d74837.
Profiles selected by the old development protocol: lm-10000 and dogleg-10000,
where 10000 is the initial radius, NOT the iteration count. LM uses iterative
Schur / Schur-Jacobi; dogleg uses sparse Schur / SuiteSparse. Eight threads,
600 outer iterations, unchanged default Ceres termination criteria, up to
3600 process seconds per run. N=3 on Final3068 and Final4585, alternating
profile order. Preserve failures, timeouts and all native attempted-step traces.
If the 600-iteration cap prevents convergence, report it and register any
extension separately; do not mislabel a capped endpoint as converged.

The native harness independently checks the final objective in CPU double
precision against original observations; compare initial scores to an
independent NumPy implementation. Inputs and binaries must match the banked
hashes. Do not export large Ceres states or change the frozen binary.

After all Ceres runs, freeze a target per storm scene at 1.01 times the LOWER
of the two valid profile median endpoint costs. If a profile has failures,
retain them and do not call its reduced subset a completed baseline. Run the
unchanged Eta2 champion against these fixed targets at N=10, 600 outers and
60 native seconds. Compute Ceres crossing times at accepted FP64 callback
states, without interpolation; report all misses. Successful-subset timing
ratios are not unconditional speedups. Endpoint comparisons at unlike stops
are separate from identical-target convergence-speed comparisons.

## Venice52 reachability

The banked LM-10000 / 600 row independently scores 241326.95669747482. Freeze
the explicitly proposed target at 241327 * 1.01 = 243740.27 before new Eta2
runs. N=10 per arm, alternating order, same frozen Eta2 binary:

- Champion: original flags and 600 outers, with a 60-native-second safety cap.
- Stop-disabled diagnostic: only OCA_FTOL=0, max_iter=10000 and the same
  60-second cap change. Keep lambda, forcing, safeguards and all other flags.

Disabling FTOL also changes the timing of the existing stop-confirmation and
backtracking rearm interaction. This is a stopping-policy reachability probe,
not a claim that an exactly identical trajectory was merely continued. Stop
at the target if reached, otherwise retain the final cost and stopping reason.
Export and independently audit each compact endpoint; no conclusion that a
basin is mathematically unreachable follows from a bounded miss.

## Legacy sweep and public scope

The old 37/48 A/B/C/D evaluation uses binary 80c14509..., Config-A-style flags
and no Eta2 classical-LM/PCG radius policy. Its historical pause reason has not
been recovered; completing it cannot close current Eta2 baseline coverage.
Leave it paused by decision for this task, preserving all existing work.

Audit rather than assume the proposed 5–30x / strict-domination headlines.
The frozen Eta2 evidence, old A/B/C/D evidence and collaborator's independent
results have different configurations/panels; do not pool them. Public claims
are limited to named measured implementations, hardware, flags, targets and
scene panels. An optional external-GPU build feasibility check may inform a
future gate; no new GPU implementation comparison is implied here.
