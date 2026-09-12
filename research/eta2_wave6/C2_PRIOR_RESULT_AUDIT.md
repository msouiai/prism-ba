# C2 audit: exact per-track algebra was already tested in wave 5

The categorical map ranks Hartley--Sturm/Lindstrom point algebra after the
graph diagnostic.  That cell is not untried in the current repository.  Wave 5
A1/B7 implemented and audited the same mathematical intervention, so wave 6
does not spend another native cohort on it without a new mechanism.

At the recorded Final3068 E4 hit/miss pair, the exact two-view repair worked at
the local problem it was meant to solve:

- point 250233 track cost changed from 256.303 and 1,794.509 to 0.03348 and
  0.03344;
- the two full-step trust ratios became 0.5028 and 0.5026;
- the fixed-state branch mechanism was removed.

The native targeted policy nevertheless failed:

- Venice remained 0/5 and its median endpoint worsened 4.15%;
- Final3068 remained 3/5;
- conditional Final3068 target time rose from 3.49 to 4.66 seconds;
- median rejects rose from 7 to 17.

This separates local algebraic correctness from trajectory usefulness.  The
global point solve is not the missing implementation detail: the exact local
answer was obtained and inserted.  Greedily replacing many proposed points
changed later linearisations and selected a worse basin.  The result is direct
evidence against promoting exact per-track algebra as an always-on Eta2 policy,
while retaining it as a diagnostic or a future intervention with a causal,
paired trigger.

Primary evidence: `research/eta2_wave5/A1_RESULTS.md`,
`research/eta2_wave5/a1-replay.json`, `research/eta2_wave5/a1-tails-summary.json`,
and the frozen wave-5 feedback.  No wave-6 score was run for this audit.
