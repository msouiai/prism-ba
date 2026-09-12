# Reproducing wave 3

Start with [AGENT_FEEDBACK.md](AGENT_FEEDBACK.md), [PROTOCOL.md](PROTOCOL.md),
[NATIVE_PROTOCOL.md](NATIVE_PROTOCOL.md) and the per-stage addenda. The frozen
champion lives in `../eta2_champion`; no source/default there was changed.

From the repository root:

```bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python3 research/eta2_champion/build.py --check-only
python3 research/eta2_wave3/build.py
python3 research/eta2_wave3/validate_local.py
python3 research/eta2_wave3/run_native.py compatibility
python3 research/eta2_wave3/run_native.py locality
python3 research/eta2_wave3/run_native.py tails
python3 research/eta2_wave3/run_native.py opening
python3 research/eta2_wave3/run_native.py practical
python3 research/eta2_wave3/run_opening_cap.py venice
python3 research/eta2_wave3/run_opening_cap.py final
python3 research/eta2_wave3/run_opening_cap.py practical
python3 research/eta2_wave3/run_confirmation.py practical
python3 research/eta2_wave3/run_confirmation.py tails
python3 research/eta2_wave3/report.py
```

Existing completed rows are cached, not rerun. A new hardware/build evaluation
needs a new registered cohort and provisioned source, baseline binary and BAL
inputs; do not bypass hash checks to label a different executable as the frozen
one. Build commands, source overlays and exact flags are in the manifests.
Compaction and heavy forensic analysis must be stopped before practical timing.

The witness diagnostics use retained wave-1/wave-2 arrays. E1 adds a coherent
CPU block assembly, direct Gram checks and signed cost scans. E4 uses a separate
capture binary (`build_e4.py`) and records actual accepted directions; it is
not a scored speed arm. `miss-forensics/decision.json` indexes the retained
boundary states. Other new intermediate point arrays were omitted according to
the pre-registered retention rule, and hashes cannot reconstruct them.

Native endpoint exports are lossless gzip files, often linked to durable storage
under `/workspace/eta2-wave3-evidence` or this directory's `durable_states`.
They are not Git blobs. Manifests and per-run staging records identify them;
all numerical ledgers and compact traces are in the branch. Large witness
archives likewise require separate transfer to reproduce the CPU calculations.

Decode the lossless XOR/byte-plane archives with:

```bash
python3 research/eta2_wave2/lossless_float_archive.py ARCHIVE DESTINATION
```

No float rounding occurs. A quota error interrupted the last standalone
intrinsic run's export and the first E4 archive attempt. The native result was
recovered from its preserved raw state without rerunning it. The E4 archive was
rebuilt from preserved captures with exactly the registered full-state retention.
The failed partial archives were removed only while original data remained.

Space recovery also archived older, completed Final13682 endpoint files. Their
decoded state and **original gzip container bytes** were verified exactly before
the old gzip files were removed. `old_endpoint_archives.json` records original
paths, archive hashes, raw hashes and gzip reconstruction metadata. Restore an
old gzip file to its original location with:

```bash
python3 research/eta2_wave3/compact_old_endpoints.py --restore ARCHIVE
```

This restores the original compressed SHA, not just equivalent point values.
Existing mismatching destinations are never overwritten. Original solver code,
binaries and input observations were not part of this compaction.

Further headroom came from hardlinking byte-identical large assets in three
inactive cached editor versions. Every original path and content remains;
the active editor version and its open/mapped files were excluded. The two
`editor_cache_*deduplication.json` records retain the hashes and inode changes.
No more old research endpoints needed compaction for the confirmation cohort.

`audit_release.py` verifies frozen source/headers, executable provenance,
initial-score agreement, every native endpoint's compressed and decoded hashes,
the projected-operator check, and archive integrity. The large local artifacts
must be present to rerun that full check elsewhere.
