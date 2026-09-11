# Exploratory Venice diagnostics — registered after first two extensions

This supplements rather than alters PROTOCOL.md. At registration the first
stop-disabled runs miss 243740.27 at 60 seconds and about244929.6 cost. One
trace has 6630 accepted outers, final CG depth1, no final radius clipping,
rho near1 and a persistent numeric-repair damping floor2.222e-7. The primary
N=10 arms continue unchanged. These observations motivate two bounded
mechanism probes, not a new globally selected champion.

Same frozen Eta2 binary, input and target243740.27. N=3 per probe, alternating
order, 600 outers /60 native seconds, original lambda0.1 and all remaining
champion flags. Independent original-observation endpoint audit and compact
state preservation use the same helper as the primary experiment.

- probe_relaxed_ftol: only OCA_FTOL=1e-7. This delays but preserves the
  stop-confirmation trigger; original forcing multiplier2.
- probe_tighter_forcing: OCA_FTOL=0 and OCA_RLA_FIXED_ETA=0.1. This tightens
  the existing residual forcing test relative to its original EW sequence.
  It does not change the numerical safeguard or damping floor.

No source or binary edits. Both probes change the trajectory and are
exploratory. An improvement cannot be attributed to late-phase behavior
alone because each altered flag is active from initialization. A miss does
not rule out other forcing/damping repairs or budgets. No automatic
promotion, broad scene sweep or target revision follows from these probes.
Time them under the shared measurement lock after the primary Venice stage;
keep the ongoing Ceres repetition order and all primary evidence intact.
