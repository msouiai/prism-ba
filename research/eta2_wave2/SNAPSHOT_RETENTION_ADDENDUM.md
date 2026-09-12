# Snapshot retention change for the storage quota

All registered numerical metrics and all attempted-run records remain. Full
per-attempt point-state retention exhausted the root quota on the first W1
trajectory; the archive held104 point states and was198MB. Before further
trajectory runs, use this deterministic diagnostic retention rule:

- Keep ALL attempt metadata, traces, raw camera directions, R/t/intrinsics/E,
  and CPU model-decrease/norm decompositions.
- Keep full X point states and point diagonal arrays for first attempt, largest raw/R (first tie), last
  attempt. For single-attempt terminal reconstructions this retains everything.
- Keep SHA256 of every original raw member and all retained archive members.
- Preserve all scored native endpoint exports and all historical research bytes.

Apply the same rule to the first W1 trajectory already collected, recording the
original full archive hash and the retained members. Verify the smaller archive
before releasing its superseded full diagnostic archive. This is a storage
change, not a scoring, arm-selection, or stopping change. A non-retained point
state cannot be recovered byte-for-byte from its hash; stochastic replay may
produce a nearby trajectory. Explicitly report that reproducibility limitation.
The chosen full states are forensic representatives, not a subset used for
performance/hit-rate conclusions. All per-attempt numerical summaries remain.
