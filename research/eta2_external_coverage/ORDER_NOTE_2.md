# Per-scene storm scheduling amendment

Registered before any new Eta2 storm-target measurement. The numeric
protocol, candidate profiles, target rule, repetitions and budgets remain
unchanged. Once all six Final3068 Ceres records are available and valid, freeze
its target from those records and run its ten Eta2 repetitions without waiting
for the unrelated Final4585 baseline endpoints. No Eta2 outcome is used to
choose or modify the target.

The old Ceres harness computes each scene's independent initial score outside
the solve lock. To preserve serialized heavy work at the scene boundary, wait
until it announces the first Final4585 native run (after that initial audit),
then acquire the measurement lock for the entire ten-run Final3068 stage.
The Ceres run already in progress, if any, completes first. All remaining
Ceres measurements retain their original order and allowance.

Save the early registration separately. The original final controller still
waits for all twelve Ceres endpoints, recomputes both targets and asserts the
same target on any already-completed Eta2 row. It then completes Final4585.
This is an execution-order amendment, not a revised endpoint or speed metric.
The original PROTOCOL.md is preserved byte-for-byte.
