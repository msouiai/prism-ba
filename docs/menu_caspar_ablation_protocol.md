# Single shift, fixed five shifts, and Caspar FP64

Three previously selected, contrasting original BAL problems; three repeats per arm. No noise, new calibration, or solver tuning. Targets are the existing medium thresholds from the expanded comparison.

| Scene | Nominal objective target | Native cap |
|---|---:|---:|
| Trafalgar126 | 104534.24152926281 | 4 s |
| Dubrovnik88 | 359003.9111293723 | 4 s |
| Final1936 | 5074937.9725361075 | 12 s |

The common effective threshold is nominal × (1 − 1e-8). PRISM receives the nominal threshold because its frozen target hook already applies this margin; Caspar receives the effective threshold. A certified hit requires both a native crossing within cap and an independently audited endpoint at or below the effective threshold. Internal linear and nonlinear convergence tolerances remain each algorithm's frozen settings; this aligns the target test, not every solver tolerance. Budget returns may exceed the cap; late crossings do not qualify.

PRISM uses `/workspace/prism-early-restart/prism-v7` (SHA256 `8eeaabc8180547ad4ae74226bec6285ff6325f72a9f760ecd8af14d9fefd4af7`). Both arms use the same flags, including retry cache, multi-RHS, diagonal normalization, backtracking/rearm, compact fragments mode 2, point safeguard, rho updates and point damping floor/ratchet. The only algorithmic flag difference is `OCA_NSHIFTS=1` versus `5`. Demand-menu and restart modes are zero. With one shift the grid offset clamps to zero, so it solves the central damping. With five it spans λ/100 through 100λ. The winning shift influences the next damping under the same update rule.

Caspar uses the frozen FP64 standalone BAL driver `/workspace/prism-caspar-current/caspar64` (SHA256 `6ca81c85112005b024df4972b0ec16c3819838999a876513e148c58ed8f35eb2`), with its default solver parameters. This is a backend comparison, not a full COLMAP reconstruction experiment. Both optimize the same raw-projection objective, unshared intrinsics, fixed zero k2, original observations and initial parameters.

The 27 timing runs disable both `OCA_PROFILE` and `OCA_LEARN_LOG`. Six separate, capped PRISM diagnostic runs enable both. The latter provide phase timings and detailed candidate records; they are excluded from speed statistics. Profiling synchronizes at phase boundaries, while candidate logging adds a blocking norm. These can affect runtime and floating-point execution/trajectory, so profile phases are explanatory samples rather than an exact decomposition of the unprofiled medians.

The first batch was stopped after discovering inherited candidate logging. All seven started pipelines are retained under `/workspace/prism-menu-ablation-logged-pilot`, along with the original protocol/tooling, and excluded from the replacement timing table. The replacement batch retains the same solver settings and targets, with logging disabled. Earlier studies using this harness also included the candidate-logging overhead; their values describe instrumented execution.

Runs execute serially under the GPU lock. Scene order rotates across repeats. Within each scene the arm order is fixed by the frozen plan (Trafalgar: single/five/Caspar; Dubrovnik: five/Caspar/single; Final: Caspar/single/five), so this small screen does not eliminate order effects. There are no extra timing reruns selected after outcomes. Rank target coverage first; compare medians when all three repeats hit, with a 5% descriptive tie band. Three selected scenes and three repeats cannot support a universal or tail-performance claim.

Native time begins at each solver's entry. PRISM includes solver-local allocation and initialization, but excludes CLI input preparation/upload. Caspar excludes graph allocation/index setup, separately reported by its driver. Process wall also includes loading/export and logging; Caspar's in-driver CPU checks are inside that wall, whereas PRISM's independent audit is outside. Report native crossing and process wall separately; neither is a normalized full-pipeline comparison. CSV clocks are not substituted for the PRISM target clock.

Diagnostic assembly, point factor/RHS, Krylov, candidate scoring, alpha and backtrack times are recorded separately. Point-safeguard time is nested inside backtracking and must not be added again. Candidate scoring is timed outside the Krylov loop's accumulation intervals in this configuration. Remaining initialization, cleanup and instrumentation are not assigned to those phases. Point-safeguard evaluations are included in backtrack evaluations and the total scored count, and also reported as a separate subset; do not add them again. Caspar has no matched phase breakdown in this frozen driver; logged accept/reject decisions and PCG counts are retained, without treating them as identical units to PRISM's attempts or matvecs.

Accepted objective reduction per native return second is `(initial audited cost − final audited cost) / native seconds`. Compare it only within a scene; it is dominated by the initial descent and does not replace time to equal quality.

Reproduce with `python3 bench/menu_caspar_ablation.py`, then `python3 bench/summarize_menu_caspar_ablation.py`. Artifacts, immutable protocol, input/binary/tooling hashes, all manifests, traces, exported states, CPU audits and summaries are under `/workspace/prism-menu-ablation`. Existing paused jobs remain paused. No solver defaults or binaries are changed.
