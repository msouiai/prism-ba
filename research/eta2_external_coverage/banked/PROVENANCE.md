# Banked and collaborator rows

These additions do not alter the registered target rule or the primary runs.
`sources.json` records byte-preserved inputs and their SHA256 hashes.

## Caspar32: local banked measurements

All available Final3068 and Final4585 rows from the previously registered
`/workspace/prism-novelty/caspar32-development` sweep are included, split by
profile and outer cap. The frozen binary SHA256 is
84e16ac1872115faaac9b3847101c3a59373dab5ad08f1dc1349c2248c1615c6.
Input hashes match this experiment's registered originals. Measurements use
the Codex host. They are banked measurements, not new contemporaneous pairs.

The primary endpoint is the driver's CPU FP64 score against original double
observations, not its native float objective. Native traces are diagnostic:
their minimum cannot certify crossing of the original-data FP64 target.
Endpoint hits use the audited final cost. No target time is imputed for a
miss. Full native solve time remains visible. Final3068 has N=3 for all four
profiles/caps; Final4585 has only N=1,1,1,2 available, respectively. Do not pool
profiles, invent missing repetitions, or call this an N=3 Final4585 baseline.

Caspar32 quantizes the input state and observations to float for its solve.
On Final3068 its quantized initial state rescored on original observations is
91376508.0730, versus the original-double initial 90993342.0244 (about .421%
higher). This is an implementation/precision comparison, not a claim that
every solver retains the same internal initial floating-point representation.

## MFREE: collaborator measurements

Claude delivered `mfree_target3068.csv` on 2026-09-11 with the stated rule:
target 1744796.9841897595; N=10 per arm; library configuration; base versus
OCA_DEEP_REJECT=512 / OCA_DEEP_AFTER=2. Hit means final cost below target.
The terminal sentinel TARGET3068_DONE is retained in the raw CSV and excluded
from numerical parsing. Each supplied hit bit is checked against the target.

Times are successful runs' full native solve seconds, which upper-bound
crossing time. There are no crossing traces, exported states, binary hashes,
or full flag manifests in this delivery. Costs are collaborator-reported,
not locally independently audited. The host is Claude's separate RTX 2000 Ada
machine. Do not report their ratio to Codex-host Eta2 times as a measured
same-host speedup. Base's 0/10 is an observed count, not a zero population
success probability. With a hypothetical true probability .2, the probability
of observing zero in ten is .8**10 = .1073741824.

## Caspar f64: collaborator aggregate only

Claude identifies the Caspar column of `champion_vs_mine_samehost.txt` as f64
from the original 23-scene ledger. The Final3068 entry is 2.6351e+06, a rounded
aggregate. Claude reports that it never reached the newly registered target.
This delivery does not contain individual Caspar repetitions, their count,
solve times, binary/input hashes, or a crossing trace. The file's final
`3/3` column concerns the other two solvers at the OLD Caspar-derived target;
it is not a Caspar repetition count at this study's target. Record a reported
miss with N/time unavailable, rather than manufacture a 0/3 row.

The older MFREE/champion timing columns in that file are not imported: they
use different targets. Individual raw f64 rows can replace this aggregate
provenance entry when provided, with the aggregate retained for traceability.
