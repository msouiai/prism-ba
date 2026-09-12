# D0 fixed-reduction validation

Registered before native D0 execution.

## Arms

- `b6v7`: the wave-5 optimized binary and its four registered overlay flags;
- `derived-off`: the wave-6 derived binary with the same flags and
  `OCA_W6_DETERMINISTIC` unset;
- `deterministic`: the derived binary with `OCA_W6_DETERMINISTIC=1`.

The disabled-mode comparison uses Ladybug539 at the registered 1.01 target,
N=3 per arm, alternating order.  It passes when both arms produce valid audited
endpoints and their median endpoint costs differ by less than 0.15%.

The deterministic repeatability test uses the registered Venice52 and
Final3068 targets and 60-second caps, N=5 identical executions per scene.  It
passes only when all five runs in a scene have identical:

1. independently audited endpoint-state SHA256;
2. accepted-cost sequence, including exact FP64 spellings;
3. normalized `PCG_PREP`, `ATTR_RADIUS`, `CLASSICAL_LM`, point-safeguard and
   accepted-outer decision trace;
4. endpoint cost, outer/accept/reject/product counts, hit status and stop class.

Native wall time is deliberately excluded from exact comparison.  A
time-budget stop also fails the repeatability gate because wall jitter could
then change the endpoint.  The deterministic path is diagnostic and receives
no speed or quality promotion from this experiment.
