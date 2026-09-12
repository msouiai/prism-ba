# User-requested fresh N=10 confirmation and controls

Registered before this new cohort. The new explicit request authorizes confirmation despite the failed earlier N=5 extension gate. Preserve that earlier result unchanged; do not pool it into the primary confirmation verdict.

## Frozen intervention and baseline

Same existing derived binary SHA256 `37b262dc44c6f75cbd971f24bbb261735c793ff929ba92962bcc0bde27837679`, with `OCA_TRACK_TAU=0` versus `1`. The original-versus-derived-off N=3 compatibility, factor identity and memory checks already passed. Recheck original source, all 44 headers, champion configuration and derived binary/header hashes in this session. Do not rebuild or change any algorithm during this cohort.

The intervention remains point-damping multipliers 1 / 1 / 0.3 for observation counts ≤2 / 3–5 / ≥6, on every attempt, relative to the champion's current lambda-tied damping. Original observations, full L2 SIMPLE_RADIAL objective, unshared intrinsics, k2=0, same stopping/controller/forcing settings. No dose tuning, feedback, or opening combination.

## Cells and order

- Primary: Final3068, N=10 per arm, registered full-precision target **1744796.9841897595**. This retains the pre-existing threshold; 1744796.98 in the request is treated as its decimal shorthand.
- Secondary: Venice52, N=10 per arm, target **243740.27**.
- Controls: Final4585, Dubrovnik88, Ladybug539, N=3 per arm. These run to ordinary solver termination for endpoint comparison. Also measure first crossing of frozen targets from their full CSV traces: Final4585 **7767397.3902649265** from the earlier storm ledger; Dubrovnik88 **362571.82** (1.01 × the supplied published Caspar reference 358982); Ladybug539 **165617.73918321263** from the existing practical panel. The Dubrovnik threshold is an explicitly registered rounded-reference control target, not a new Caspar run.

All runs: 600 maximum outers, ordinary champion FTOL, 60 native-second safety cap. Primary/secondary stop when their target is crossed. Controls have no target stop; evaluation targets only score their traces. Report total native termination time separately from first-crossing time. N=3 control distributions do not resolve Final4585 basin multimodality or establish a population tail result.

Alternate arm order by repetition and reverse scene order on odd repetitions. Use a new output directory. Complete every registered cell regardless of interim results unless an actual correctness/hardware failure prevents execution; retain any failed row and the reason. Serialize GPU work, heavy audit and compression. Count all solver work and the same attempt tracing in both arms. All 58 scored rows must be retained.

## Primary criterion and interpretation

The strong prediction is elimination of observed FTOL target misses: **10/10 on-arm target hits**, with successful-run median crossing time no more than **1.20 ×** the fresh control successful-run median. Also report the comparison against the historical 8/10-success median, read and frozen from `eta2_external_coverage/storm-results.json` in registration.json, rather than choosing one of several approximate values from conversation.

If the fresh off cohort has no FTOL misses, a 10/10 versus 10/10 outcome does not demonstrate rescue of that failure class. Any on-arm misses refute the literal zero-miss prediction for this sample. These are independent stochastic solves from the same original input, not replayed identical internal failure states; repetition pairing does not establish counterfactual rescue of a specific historic witness. Conditional timing changes are not unconditional speedups and must be reported with hit counts and ranges.

Report per scene/arm: hits, median/range first-crossing time, audited endpoint costs, native total time, outers, rejects, retry/failure fractions, PCG/outer, initial scores, numerical repairs and stop reasons. Use >0.15% median endpoint changes or disjoint observed timing ranges as the existing screening signals; N=10 is not certainty about population reliability. Report both signs. Record Final4585 sensitivity even when it does not pass a noise-separation criterion.

## Provenance and storage

registration.json freezes input/target/binary/protocol hashes and the historical timing reference before execution. Independent CPU FP64 endpoint audit tolerance is 1e-6 relative. Retain CSVs, commands, flags, stdout, attempt traces and hashed compressed numerical endpoints. Storage deduplication may remove only copies verified inside a retained archive, with a manifest giving exact member paths and hashes; it must not remove unique evidence. Do not merge this experiment into the original champion.
