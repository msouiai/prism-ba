# Prism — one Krylov sweep, a spectrum of damped solutions

Latest solver study: [camera-block PCG, reuse, and fresh Caspar comparisons](docs/camera_pcg_results.md).

Latest bounded study: [point preparation optimizations and fresh Caspar comparisons](docs/point_preparation_results.md).

*(working name during development: MFREE)*

GPU (CUDA) and CPU implementations of a matrix-free Levenberg–Marquardt bundle
adjuster. The name is the mechanism — like a prism splitting one beam into a
spectrum, the solver splits a single Krylov sweep into solutions for an entire
spectrum of damping values — **multi-shift CG with a ζ-recurrence**, the
candidate steps scored by true nonlinear cost.

CG stopping follow-up: [guarded Krylov-projected TR and fresh largest-scene comparison](docs/cg_stopping_results.md). The new variant reaches the largest target in 16.35s versus Caspar FP64 at 16.69s and FP32 at 7.80s (N1), while frozen mixed-buffer TR misses its cap. Dubrovnik regresses 24% in N3: this remains an opt-in large-scene candidate.

Mixed-storage follow-up: [TR profiling, FP32 buffers and Caspar screening](docs/tr_mixed_storage_results.md). The experimental TR build reduces Final1936 runtime by 23%, saves 3.56 GiB of fragment storage on Final13682, and passes 63 endpoint audits. Small-scene variability remains; Caspar FP32 still leads the two difficult comparison scenes.

Fresh Caspar comparison: [TR versus Caspar FP64 and FP32, five scenes × three repeats](docs/fresh_tr_caspar_results.md). PRISM leads Trafalgar126, Dubrovnik88 and Final4585. Caspar FP32 leads Final1936; on Final13682 it is faster but only 2/3 raw runs certify, while a separate stopping-margin check certifies 3/3 at 7.76 s median. All 48 endpoints audited; no universal winner.

Current improving TR candidate: [TR-one with recurrence scoring](docs/tr_candidate_results.md). Fresh N5 confirmation improves all three scene medians (1.033× Trafalgar, 1.220× Dubrovnik, 1.042× Final1936), wins 14/15 pairs and hits 15/15 targets. Standalone opt-in build and run scripts included; production defaults unchanged.

Latest radius rollouts: [four adaptive and selective variants](docs/adaptive_radius_results.md). No consistent two-scene improvement. Initial-only expansion cuts Trafalgar time by 15% but increases Dubrovnik time by 18%; corrected TR-one remains the general incumbent. All 56 endpoint audits pass.

Latest actual-radius test: [three radii from one projected Krylov space](docs/camera_radius_results.md). Selective expansion helps at five of ten distinct sampled states, but larger radii duplicate the current step at five and neither neighbor rescues two failed candidates. All 52 state audits pass; 3.80 native seconds. Local diagnostic only; corrected TR-one remains the measured incumbent.

Latest matched trust-region ablation: [one versus five shifts, with a shared interior-damping correction](docs/camera_tr_width_results.md). Corrected one-shift TR reaches both targets in 0.474/0.753 s versus five at 0.683/0.828 s. Both hit 6/6; one is the provisional two-scene winner. One real rejected step activates candidate-bank reuse; no default change.

Previous camera trust-region screen: [two scenes, three repeats, frozen prototype](docs/camera_tr_results.md). All targets reached; camera TR takes 0.679 s on Trafalgar126 and 1.041 s on Dubrovnik88, versus fixed five at 1.244/2.300 s. Promising provisional winner; no default change, no activated BA retry reuse, and the same-controller single-shift ablation remains necessary.

Previous matched-state repair test: [four Dubrovnik88 checkpoints, 24 short continuations](docs/repair_rollout_results.md). Repair improves the accepted menu’s immediate cost at two states but loses after three steps; the next-lambda update differs by 5×. No default change; single guarded remains the end-to-end incumbent on this scene.

Previous controlled menu ablation: [single shift, fixed five and Caspar FP64; three scenes × three repeats](docs/menu_caspar_ablation_results.md). Both PRISM arms hit 9/9 targets, Caspar 6/9. Single leads Dubrovnik88/Final1936, five leads Trafalgar126. Timings disable candidate logging; profiles are separate. Zero PRISM rejections.

Previous initialization-noise check: [four contrasting problems, three matched seeds](docs/noise_caspar_results.md). PRISM reaches 9/12 targets versus Caspar FP64 6/12. Smaller-scene median winners persist; both miss the largest target, where Caspar retains lower endpoint costs. Zero PRISM rejections or restart activations.

Previous breadth check: [12 additional problems, three repeats, frozen Caspar FP64 comparison](docs/expanded_caspar_results.md). PRISM certifies 75/108 targets versus 38/108, but common-hit average speed remains inconclusive and Caspar wins the largest problem. Tight-target consistency is weak; no restart activates.

Previous expanded comparison: [six additional scenes, three frozen targets, two repeats](docs/six_scene_caspar_results.md). PRISM hits 36/36 versus Caspar FP64 32/36; PRISM wins 13 of 18 scene/target cells, Caspar five. No restarts trigger; native timing and quality threshold matter.

Previous Caspar comparison: [precision-verified strict and relaxed target results](docs/current_caspar_results.md). PRISM reaches the strict targets; Caspar FP64 wins looser Ladybug, PRISM wins looser Dubrovnik. Quality threshold matters; no universal speed claim.

Latest trigger search: [four short baseline probes, no qualifying early rejection](docs/restart_trigger_search_results.md). The rule remains unchanged; active recovery beyond Ladybug1197 is still unproven.

Latest restart validation: [three additional scenes pass without triggering](docs/restart_validation_results.md). All six new targets reached; fixed-five behavior leads Venice89/Final93, but active recovery outside Ladybug1197 remains untested.

Latest restart test: [all six development targets reached](docs/early_restart_results.md). A bounded early restart recovers Ladybug while retaining fixed-five on Dubrovnik/Venice; all abandoned solver work is charged, process overhead reported, defaults unchanged.

Latest switching test: [fewer rejections, but no Ladybug recovery](docs/rejection_switch_results.md). Experimental mode 3 reduces rejections from 34 to 4 but misses both targets; incumbents and defaults remain unchanged.

Latest counterexample check: [paired still wins Ladybug1197](docs/ladybug_countercheck_results.md). Fixed-five misses both six-second targets; paired reaches both in 2.44 s median. No universal winner or default change.

Latest original-input check: [fixed-five leads Dubrovnik173 and Venice52](docs/original_menu_results.md). Two repeats per arm; fixed-five + point repair reaches both targets fastest. This is a two-scene result, not a universal default.

Latest budget comparison: [ten-step time-to-quality results and winners](docs/menu_budget_results.md). Fixed-five wins two shared restart targets, paired one, single one; all 27 target runs hit. Original-scene incumbents are unchanged.

Latest identical-state study: [ten-step damping results and current winners](docs/identical_state_damping_results.md). Paired wins local next-step quality on four states at higher work; single + point repair remains the Dubrovnik173 end-to-end incumbent.

Latest probe optimization: [ten-step results and current winners](docs/repair_probe_skip_results.md). Single + point repair still wins Dubrovnik173; optional probe skipping reduces local work without a demonstrated overall speedup.

Latest ten-step follow-up: [repair-active validation and winner ledger](docs/split_ten_steps_results.md). Single + point repair wins Dubrovnik173; split improves tighter-target time against frozen paired in one run.

Latest split validation: [two additional scenes, unchanged rule](docs/split_validation_results.md). All split targets reached, but no damping changes occurred; no new speed benefit established.

Latest block-error study: [separate damping decisions and short results](docs/repair_block_error_results.md), [math](docs/repair_block_error_math.md). The optimized split policy reaches both contrasting scene targets in two repeats; it remains experimental.

Previous damping study: [actual repaired-step model feedback and results](docs/repair_damping_results.md), [mathematical analysis](docs/repair_damping_math.md). The paired controller improves the medium screen but fails one prospective Venice target; it remains experimental.

Previous pointwise rescue study: [online results and controller diagnosis](docs/point_safeguard_results.md), [mathematical derivation](docs/point_safeguard_math.md). Both point-safeguard modes remain experimental and off by default.

Latest comparison: [short PRISM versus Caspar target-quality screen](docs/short_caspar_results.md).

Previous investigation: [thirty steps: local nonlinear curvature and pointwise rescue](docs/local_curvature_results.md).

Previous investigation: [thirty further steps: coupled subspace rescue](docs/subspace_rescue_results.md).

Previous investigation: [full-model prediction on a large scene](docs/full_model_large_results.md).

Previous investigation: [thirty math-led steps: point damping and full-model prediction](docs/point_trust_results.md).

Previous investigation: [second ten steps: upward recovery and attribution](docs/backtrack_upward_results.md).

Previous investigation: [ten-step backtracking schedule investigation](docs/backtrack_schedule_results.md).

Previous investigation: [bounded backtracking cost screen](docs/bounded_backtrack_results.md).

Previous investigation: [fixed-system reuse comparison and stopping decision](docs/fixed_reuse_results.md).

Latest large-scene check: [selective reuse on final-4585](docs/selective_reuse_large_results.md).

Latest prototype: [selective Krylov reuse and equal-quality comparison](docs/selective_reuse_results.md).

Earlier capture study: [CG-capture reuse and time to equal quality](docs/cg_capture_results.md).

Earlier prototype: [retained Krylov basis and short ablation](docs/retained_krylov_results.md).

Latest timing study: [CPU-checked time to equal quality](docs/equal_quality_results.md).

Latest controller prototype: [demand-driven menu and paired damping results](docs/demand_menu_results.md).

Latest five-scene screen: [five additional large BAL cases against Caspar FP32](docs/five_large_results.md).

Latest large-scene transfer: [final-1936 comparison against Caspar FP32](docs/final1936_results.md).

Latest memory optimization: [compact FP64 buffers make the largest BAL case fit](docs/compact_fragment_results.md).

Latest scaling screen: [largest BAL case (13,682 cameras): PRISM memory limit and Caspar result](docs/largest_bal_results.md).

Latest validation: [CPU-audited fixed-policy comparison against Caspar FP32](docs/fixed_policy_validation.md), including the projection-guard and precision caveats.
Earlier compute study: [progressive depth, cost batching and controller replay](docs/multishift_compute_results.md).

## Layout

- `gpu/` — the CUDA solver (`oca_cuda.cu`, BAL/dof9 path; `oca_rigfisheye.cuh`,
  rig-fisheye CD=14 path), generated Jacobian kernels, core tests, and the CPU
  reference header used by the bit-compat gates (`mfree_cpu.h`).
  Snapshot of the `mfree_combo` research tree, 2026-09-01.
- `cpu/` — standalone instrumented CPU port (`mfree_cpu_instr.h`) with a
  minimal driver (`cpu_drv.cc`). Used for prototyping (the block-congruence
  preconditioner was built here first) and for CPU-vs-GPU parity checks.
- `docs/` — the cumulative results compendium (`ba_report.pdf`) and its
  generator (`mkreport.py`; regenerates every table from raw solver traces).

## Solver architecture (GPU)

Two-block BA: Schur-complement point elimination with an augmented Givens-QR
point factor (conditioning κ(V)^½, not κ(V)), matrix-free S·v as
Pass1 → V⁻¹-apply → Pass2 over CSR indexing, multi-shift CG over the damping
menu σ_l = λ·10^(l−grid_down), checkpointed candidate extraction, and a
per-camera block-congruence preconditioner (L⁻¹SL⁻ᵀ + σI — the shift survives
as σI, so the shared Krylov space and the menu survive preconditioning).

## Environment flags (all default-off, bit-compatible)

| flag | validated setting | effect |
|---|---|---|
| `OCA_RHO_LAMBDA` + `OCA_GRID_DOWN=2` + `OCA_RHO_SHIFT` + `OCA_ALPHA_RHO` | on (cold solves) | ρ-gated λ policy v3 + two-sided menu |
| `OCA_BLOCKEQ` | on | block-congruence preconditioner (9×9 per camera; 6×6/3×3 reduced space under shared intrinsics) |
| `OCA_BLOCK_CM` | 1 | atomics-free camera-major factor build |
| `OCA_MENU_GATE` | 1e-2 | skip scoring degenerate menus (gates on ζ-recurrence predictions; canonical order preserved) |
| `OCA_FTOL` / `OCA_FTOL_K` | 5e-5 / 5 | persistent relative-decrease stop |
| `OCA_CKPT_MAX` | 32 (cold) | cap CG checkpoint depth |
| `OCA_NSHIFTS` | 5 (default) | menu width; 1 = classical LM (research knob) |
| `OCA_MENU_BACKTRACK` | 8 (experimental) | full-step rescue after a failed menu; preserves the first three accepts and confirms convergence with the original policy; unshared fp64 dof9 only |
| `OCA_LAM_FLOOR` | 8 (default) | damping-floor decades below λ₀ (diagnostic knob) |
| `OCA_FORCE_UNSHARED` | research only | disable calibration groups (BAL benchmarking) |

## Reproduction and corrected results

The [retry-reduction follow-up](docs/menu_retry_investigation.md) tests a
full-step safeguard for failed multi-shift menus.
The [controlled Caspar-f64 comparison](docs/caspar_comparison.md) evaluates
both fixed Prism arms against the backend vendored by COLMAP, with matched-cost
timings and explicit stopping reasons.

Start with [REPRODUCE.md](REPRODUCE.md) and the retractions in
[the September results](docs/results_2026_09.md). Earlier BAL speed and win-count
headlines mixed fp32 and fp64 Caspar baselines and are withdrawn. The corrected
comparison reports a quality advantage on many scenes with substantially higher
solve time; it does not establish a general speed advantage over Caspar-f64.

The [iteration-cost investigation](docs/performance_investigation.md) records
kernel profiles, opt-in execution optimizations and reproducible validation.
The damping menu remains useful as protection against scene-dependent failures;
its endpoint benefit and execution cost must be measured separately.

## Provenance

Extracted from the COLMAP-adjacent research trees (`mfree_r10` → `mfree_combo`)
on the lambda workstation. The integration shim into COLMAP
(`--BundleAdjustment.backend MFREE` / `--Mapper.ba_global_backend MFREE`) lives
in the COLMAP tree, not here.

## Expanded novelty study (in progress)

The frozen Caspar-fp32, four-arm Prism, Ceres LM/Dogleg and generalization
study is documented in [the protocol](docs/novelty_protocol.md).
See [the interim assessment](docs/novelty_assessment.md),
[retained measurements](docs/novelty_results.md),
[fixed-system audit](docs/krylov_audit_results.md), and
[theory/prior art](docs/novelty_analysis.md).
Incomplete cells are explicit; second-GPU replication is pending.

The completed [lambda-hysteresis pilot](docs/lambda_hysteresis_assessment.md)
reports mixed results; the new selection rule remains opt-in.

The completed [adaptive-menu pilot](docs/adaptive_menu_assessment.md) compares
fixed one/five-shift controls with adaptive scoring at 1%, 3%, and 5% quality
bands. The controller remains opt-in.

The completed [bounded rejection investigation](docs/rejection_assessment.md) examines
candidate coverage, damping-range failures and safeguard rearming on small BA
problems. See [measurements](docs/rejection_results.md). These are exploratory
opt-in changes; the broad novelty queue remains paused.

The [short medium-size screen](docs/medium_screen_results.md) compares fixed
PRISM configurations with Caspar FP32 on final-3068 and Venice-1672 using small
iteration budgets. It measures early progress, not full convergence.

The [short large-scene screen](docs/large_screen_results.md) applies the same
comparison to final-4585, capped at 20 PRISM outers and 200 Caspar iterations.

[Multi-shift compute priorities](docs/multishift_compute_next.md) uses fresh
single/five-shift phase profiles to identify the next bounded optimizations.

FP32 Schur-products follow-up: [results and bottleneck revision](docs/fp32_schur_results.md).

Reference ranking and point-owned Schur accumulation: [results](docs/reference_ranking_results.md).

Factored FP64 derivatives and paired safeguard selection: [results and current large-scene PRISM candidate](docs/safeguard_and_factored_results.md).
