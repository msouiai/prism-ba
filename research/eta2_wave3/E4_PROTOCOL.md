# E4 accepted-step divergence registration

The historical miss versus four historical hits first differs materially in
scalar raw-norm/rho indicators at accepted indices 7 or 9 (zero based), not in
the first three accepts. These traces alone do not identify the actual moved
camera or prove causality. `trace_divergence.json` retains the observation.

Collect fresh original-policy diagnostic trajectories with a separately hashed
derived capture binary. N>=5, until at least one hit and one miss, at most 10
runs. Same target and flags. No deterministic miss seed is claimed. Capture raw
attempt states and actual final accepted directions, up to 128 accepts; report
if a comparison is censored. These expensive copies are excluded from scored
timing tables.

Compare the first observed hit and first observed miss by accepted index.
Material divergence is ||dc_miss/E_hit - dc_hit/E_hit|| divided by the larger
of the two norms exceeding 0.1; record all preceding scalar differences too.
Use a common E_hit for both directions, not two changing metrics. At the first
divergence and immediately preceding accept, run E1 and compute true/model cost
change for each camera at fixed old points, separately from the actual joint
proposal. A poor conditional rho_i is not automatically blame for the joint
step: the points also move, and the coupling must be reported.

Retention registered before collection: full arrays are RAM scratch. Retain
complete snapshots at the first material divergence, preceding accept and final
accepted state for the selected hit/miss pair; retain every attempt's metadata,
state hashes, native traces and compact direction-difference diagnostics.
Other newly generated point snapshots may be omitted after analysis, explicitly
recorded; hashes cannot restore omitted states. All scored endpoints retained.
Replay surgery or a deterministic-reduction implementation follows only if this
audit supports the proposed starved-camera commitment mechanism and a local
actuator has survived its gate. Otherwise report the negative or limitation.
