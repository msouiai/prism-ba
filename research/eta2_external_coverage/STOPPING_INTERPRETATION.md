# Stopping and reachable quality

Claude reports six Venice52 MFREE runs with early stopping disabled and a
300-outer cap: final cost 241602–241656, about 30 seconds. The six-row endpoint CSV has now been delivered and copied byte-for-byte
to provenance/v52_basin_mfree.csv. It contains no native traces or endpoint
states, so these remain collaborator measurements rather than independently
audited local runs; they are not new Eta2 measurements. They put that MFREE configuration within approximately 0.114–
0.136% of the banked Ceres LM endpoint 241326.95669747482. They remove the
need to invoke an inaccessible lower minimum to explain the old stopping
floor. Endpoint proximity alone does not prove that two parameter states
belong to the same mathematical attraction basin.

For Eta2, the new target is 243740.27, fixed before the experiment. The older
Venice stopping diagnostic reached 248785, a looser target; its three hits do
not settle this test. The new diagnostic keeps the frozen binary, damping,
forcing and step safeguards, disables OCA_FTOL and raises the outer cap,
retaining a 60-native-second limit. It stops at the target, so even a hit
would establish 1%-tolerance reachability, not the exact 241327 endpoint.

In the frozen source, persistent cost-change stopping is coupled to a
confirmation mechanism. A proposed stop after backtracking temporarily
turns backtracking off so the original retry policy can confirm it. A
substantial original-policy accepted step can then rearm backtracking.
Disabling OCA_FTOL removes this trigger as well as the final termination.
Therefore the diagnostic tests the complete stopping-policy interaction;
it must not be described as appending iterations to an otherwise identical
trajectory. Source: prism_eta2.cu, accepted/rejected stopping and confirmation
logic around lines 12023–12093.

A small relative decrease is a progress statistic, not a stationarity
certificate. A damped, clipped, or shortened step can give a tiny objective
change even when useful descent remains. Repeated rejected steps similarly
say that the current search failed, not that every admissible direction is
unhelpful. The relevant empirical question is whether continuing the fixed
method converts a bounded miss into a hit, and how much time that costs.
No theorem of unreachability follows if the bounded continuation misses.

Results will distinguish hit probability, conditional time among hits,
endpoint quality and stop reason. A method that often stops early cannot
claim a speed advantage merely by reporting its shorter unsuccessful runs.
Neither does a slow successful method lose by its total convergence time
when it may have crossed the shared target much earlier. Ceres crossing
times use accepted callback states only, excluding rejected trial costs.
