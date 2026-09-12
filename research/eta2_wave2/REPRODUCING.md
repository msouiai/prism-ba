# Reproducing this research snapshot

Start with [AGENT_FEEDBACK.md](AGENT_FEEDBACK.md) and the per-stage protocols.
This directory contains the implementation overlays, registrations, native
traces, independent checks and report generator. Large arrays/endpoint exports
are local artifacts indexed by hashes; they are not stored as Git blobs.

Builders derive new CUDA sources from the frozen champion and the existing
wave-1 helpers. They do not edit the champion. On the original machine, from
the repository root:

```bash
python3 research/eta2_champion/build.py --check-only
python3 research/eta2_wave2/build.py
python3 research/eta2_wave2/build_witness.py
python3 research/eta2_wave2/build_root.py
python3 research/eta2_wave2/build_geodesic_native.py
python3 research/eta2_wave2/validate_geodesic_native.py
python3 research/eta2_wave2/build_plateau.py
```

`run_native.py`, `run_root.py`, `run_geodesic.py`, and `run_plateau.py` register
before their scored stages. Existing result directories are cached; use a fresh
registered output location/cohort for new measurements. Do not overwrite old
evidence with a different binary. Corresponding build manifests contain exact
NVCC commands and hashes. The coherent witness/analytic/root validation builders
and scripts are separate from the native production-path builds.

These are this-host research harnesses: the legacy baseline binary path is in
`../eta2_research_20260912/grid_common.py`, BAL inputs are under `/workspace/bal`,
and compiler commands targetsm_89. A remote replay must provision the pinned
binary or explicitly register the remote rebuilt baseline from the verified
source/config as a NEW cohort. Recompiled binaries may have different hashes;
do not bypass the checks and pretend they are the original executable. Original
arms carry the campaign's derived-build context in their manifest, but their
actual command/binary hash plus the frozen champion source/config identify the
baseline that executed. `release_audit.json` verifies those executable hashes.

Rebuild the human tables/figures without GPU work:

```bash
OPENBLAS_NUM_THREADS=1 python3 research/eta2_wave2/report.py
```

`audit_release.py` checks current executable hashes and all425 local compressed
endpoint exports, in addition to the numerical audit gates. Those large exports
must be present to run that integrity check on another machine.

Ordinary `.tar.xz` exports can be extracted with tar. Archives named
`*.xor.tar.xz` use the lossless byte-plane/XOR decoder:

```bash
python3 research/eta2_wave2/lossless_float_archive.py ARCHIVE DESTINATION
```

The decoder performs no floating-point rounding. It verifies existing destination
files rather than overwriting them. Historical raw-state restoration locations
and member hashes are in `storage_xor_archives.json`; older ordinary gzip copies
are listed in `storage_compression.json`. Some independent root audit exports
were packed in `step_archives.json`. New W1 full-trajectory point retention is
deliberately limited as described in `SNAPSHOT_RETENTION_ADDENDUM.md`; an omitted
point snapshot cannot be reconstructed from its hash.
