# B0 phase profile

Registered before fresh profiling.

Run the frozen Eta2 binary on all nine practical target cells, N=3, with the
usual target/cap and `OCA_PROFILE=1 OCA_PROF_SCORE=1`.  Profiled timings are
diagnostic because the explicit synchronizations perturb native wall time.
Pair them with the already registered unprofiled frozen rows; do not mix the
two as speed samples.

Record assembly, point factor plus reduced RHS, Krylov, candidate/scoring, and
scoring subphases; also record total native wall, outers, retries, matvecs and
target hit.  Report both the fraction of the timed phase sum and the fraction
of end-to-end solve time.  Unaccounted time is a bound that includes controller
work, allocations, transfers, launch/synchronization gaps and timer coverage;
it is not labeled launch latency without a kernel-level profiler.

Use Nsight Compute only for representative kernels after B0 identifies a
material phase.  It is not an end-to-end launch-latency profiler.

