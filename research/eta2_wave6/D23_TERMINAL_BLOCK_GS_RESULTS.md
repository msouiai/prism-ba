# D23 result: terminal block Gauss--Seidel finds no descent on the miss

## Verdict

D23 fails its preregistered first screen and stops. Five fresh deterministic
Final3068 pairs give `4/5` target hits in both control and D23, with zero
discordant hits. The four successful Eta2 trajectories reach the target before
the terminal hook and remain exactly unchanged. On the sole miss, neither the
camera-resection half nor the point-intersection half lowers the full L2
objective, so D23 commits zero sweeps and leaves the endpoint unchanged at
`1,941,429.5028`.

The frozen Eta2 champion, B6v7 systems candidate, and portfolio labels remain
unchanged. No extension, Venice, panel, sweep-count, or damping search is run.

## Registered design and correctness

D23 is a one-shot terminal nonlinear block Gauss--Seidel audit. It runs only
when Eta2's existing stop rule fires before the target. Each sweep first solves
the independent damped 9x9 camera blocks with points fixed and then the
independent damped 3x3 point blocks with cameras fixed, reassembling between
halves. Each half is committed only if the unchanged full pixel objective
falls; a sweep with neither improvement stops the audit.

The derived binary with D23 disabled matches deterministic B6v7 exactly on the
compatibility cell: endpoint bytes, accepted-cost and decision hashes, target
status, outers, rejects, products, and audited objective all agree. All five
active/control preterminal paths in the scored cohort also agree exactly.

## Screen result

| Quantity | Result |
|---|---:|
| Control hits | 4/5 |
| D23 hits | 4/5 |
| D23-only / control-only hits | 0 / 0 |
| Terminal invocations | 1/5 |
| Accepted sweeps / added states | 0 / 0 |
| Terminal relative decrease | 0% |
| Active/control native wall on invoked pair | 1.012414x |
| Exact preterminal paired paths | 5/5 |

The invoked audit costs `0.02847 s`. Its inherited camera damping starts from
Eta2's terminal `lambda = 2.13e6`; after the rejected camera half the local
trial value is `2.13e7`, while point damping is `1e-5`. Neither proposed half
step improves the objective. This is evidence against this registered
terminal block policy, not a proof of mathematical stationarity over every
possible block damping or globally solved PnP subproblem.

## Combined interpretation with D22

D22 finds only `0.001304%` median decrease from exact fixed-camera two-view
point replacements. D23 finds no decrease from its tested alternating camera
and point block directions on a fresh miss. These results rule out the cheap
forms of post-hoc polishing that preserve the opening. They strengthen the
basin-selection interpretation: once a losing trajectory stops, inexpensive
separable corrections do not transport it to the registered good endpoint.
The unchanged arithmetic-restart portfolio remains the strongest measured
reliability intervention.

## Evidence

- `D23_TERMINAL_BLOCK_GS_PROTOCOL.md`
- `d23-registration.json`
- `d23_terminal_block_gs/build-manifest.json`
- `d23-compatibility.json`
- `d23-final3068-results.json`
- `d23-final3068-summary.json`

