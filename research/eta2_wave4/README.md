# Eta2 wave 4

Start with [the handoff report](AGENT_FEEDBACK.md). The frozen champion is
retained after 255 scored native runs. Full registered tail tables are in
[TABLES.md](TABLES.md); machine-readable summaries are in
[RESULTS.json](RESULTS.json).

| Direction | Implementation / evidence | Decision |
|---|---|---|
| Acceptance aside | `build_aside.py`, `run_aside.py` | No established tail or panel improvement |
| O1 constrained object-space opening | `o1.cuh`, `build_o1.py`, `run_o1.py` | Negative on Venice; Final3068 QP numerically unresolved |
| O1 numerical follow-up | `build_o1_schur.py`, `probe_o1_schur.py` | Does not clear Final3068 gate |
| O2 projection homotopy | `o2/`, `run_o2.py` | Regresses; no panel |
| O3 rational attribution | `attribution.py` | Healthy sparsity gate fails; no constrained native arm |
| O4 restricted frozen-ray replay | `ray_replay.py` | Replay gate fails; no native arm |
| O5 Cauchy-to-L2 | `build_o5.py`, `run_o5.py` | Tail screening signal, 14.5% panel overhead; no promotion |
| O6 | No implementation | O1 prerequisite not established |

Frozen configuration is `../eta2_champion/champion.json`; source and all 44
headers are pinned by its source manifest. Verify before any new comparison:

```bash
cd /tmp/prism-ba-coarse
python3 research/eta2_champion/build.py --check-only
```

Every derived executable has its own `*_build_manifest.json` (O2's is inside
`o2/`). The build drivers use reversible overlays and retain the original
source. The root wave-4 and direction-specific protocol files precede scores.
Nothing is merged into or enabled in the original champion.

Native evidence is under `evidence/`: exact command/environment/input/binary
provenance, stdout, CSV, full-cost audit, per-attempt traces and results. The
large endpoint exports remain on durable disk in `durable_states/`, with their
raw/compressed hashes in the compact records; those large states and compiled
binaries are intentionally excluded from Git. Tiny independent QP evidence is
copied to `evidence/kernel-audits/`.

The banked manifests contain the original workstation's paths and hashes.
Use a fresh output/registration set for a new cohort or different machine;
do not overwrite these scores or silently reuse a registration after rebuilding.
The run scripts deliberately refuse source/hash mismatches and duplicate state
exports. Their existing completed rows can be read without rerunning solvers.

To regenerate descriptive tables from the banked rows:

```bash
python3 research/eta2_wave4/summarize.py
```

Numerical validation scripts are `test_o1.py`, `test_o1_schur.py`,
`test_o5_kernels.py`, `validate_o1.py`, `validate_o5.py`, and O2's own tests.
These checks cover actual GPU arithmetic and independent endpoint scoring;
their clocks are not performance evidence. O1 specifically checks active-set
KKT conditions rather than mistaking a finite penalty for an exact constraint.

Primary-source reading and corrected novelty premises are recorded in
`literature/MATH_AND_PRIOR_ART.md` and `o2/MATH_AND_COVERAGE.md`. Full third-party
PDFs are kept out of the repository. No new priority or SOTA claim is made.

Storage maintenance during this campaign preserved completed older states with
verified lossless encodings and exact regeneration of their original gzip
bytes. Restoration metadata is in `../eta2_wave3/old_endpoint_archives.json`;
`../eta2_wave3/compact_old_endpoints.py --restore ARCHIVE` restores one archive.
No unique research state was discarded. All study processes launched here
have finished; no GPU sweep remains queued.
