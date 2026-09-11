# Execution-order note, before any new Eta2 measurements

Claude delivered his MFREE Venice52 stopping result while our first Ceres
dogleg run on Final3068 was in flight. Queue the already registered Venice52
stage as one lock group at the next solver boundary, then allow Ceres to
continue. Do not interrupt the running solve. This avoids waiting for the full
Ceres endpoint sweep before testing the supplied stopping-policy prediction.
Native parameters, targets, repetition counts and within-stage order remain
unchanged. The lock spans input/audit/compression work too, so the stages do not
overlap heavy CPU work with each other's timed solves. No benchmark expansion.
