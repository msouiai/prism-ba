# Timing semantics

Authoritative Eta2 time-to-target is the frozen native TARGET reached
seconds field. Its clock starts at entry to SolveMFreeShiftedCG, before
solver allocations and initial cost, and the hook runs immediately after
the accepted-state CSV record. Export and independent audit occur outside
that timer. Native RESULT solve_seconds wraps the solver call and includes
its final cleanup. Both exclude CLI input loading and initial device setup.
Process seconds remain separately recorded.

The historical Eta2 CSV clock starts later, after initial solver allocations
and initial cost (prism_eta2.cu lines 8938 and 9493). Raw CSV wall_s must not be
silently presented as identical to native TARGET time. It also has only
four decimal places. For visualization, hit curves are translated by the
difference between their final TARGET timestamp and final CSV timestamp.
For misses, translation instead aligns the final CSV point to native RESULT
time. That latter shift includes final tail work and conservatively delays
the curve; it is an upper bound alignment, not an exact reconstruction of
the missing initial offset. Raw CSV files are preserved unchanged. Neither
adjustment changes the independently measured target-hit table.

Ceres crossing times use cumulative_time_in_seconds from accepted callback
states. The old driver buffers those rows and only prints them after Solve
returns. Its callback clock includes Ceres preprocessing but excludes BAL
parsing and construction of ceres::Problem; setup_seconds reports the latter.
Native RESULT runtime wraps ceres::Solve. Rejected callbacks expose trial
costs, so treating every TRACE row as an incumbent objective would corrupt
both monotonicity and target timing.

The Venice Ceres reference is banked on this host, not a fresh contemporaneous
pair. New Ceres storm and Eta2 runs are serialized with the same lock. Ceres
has a 3600-process-second cap and Eta2 a 60-native-second allowance; these are
different maxima and remain explicit. A larger Ceres allowance does not
justify substituting its full runtime for its earlier target crossing.
