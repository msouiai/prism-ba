# D0v3 harness amendment: exclude timing-only summary text

Applied after all D0v3 solver executions and before interpreting the gate.
The preregistered gate hashes the normalized point-safeguard **decision**
trace.  The initial parser selected every line beginning with `POINT_SAFE`,
which accidentally included the terminal aggregate
`POINT_SAFE summary ... seconds=<wall time>`.  That wall-clock field differed
across otherwise byte-identical trajectories and made the decision hash fail.

The parser now selects `POINT_SAFE o=` attempt decisions and excludes the
timing-only summary.  No numerical row is rerun or discarded.  State hashes,
accepted-cost hashes, endpoint values, iteration/rejection/product counts and
all per-attempt decision lines were already identical before this correction.
The pre-correction summary is retained as
`d0v3-summary-pre-normalization.json`; the immutable raw logs remain the source
of the corrected hashes.
