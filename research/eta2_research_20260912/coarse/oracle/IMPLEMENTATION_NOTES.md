# Fixed implementation details before the terminal oracle runs

Implements the committed [PROTOCOL_09.md](../../PROTOCOL_09.md), K8, three
Final3068 terminal witnesses and three complete CPU repetitions per witness.
No GPU calls or optimizer rollout. BLAS and OpenMP each use one thread.

Reconstruct coherent FP64 observation Jacobians in the native tangent; retain
captured E, lambda, Cdiag and the same intrinsic solve prior. Point factors use
the existing QR routine. Assemble only sparse W, sparse local Z and T=W^T E Z,
then Ac from camera-block terms minus the triangular-factor Gram. Do not form
a dense full camera Schur matrix. All temporary arrays stay in RAM and are
discarded after a repetition; reports contain scalar diagnostics and small
matrices only.

Independent reduced products use the Jacobian forward/adjoint form on four
fixed coarse vectors. Required relative agreement is 1e-7, along with a finite
positive coarse Cholesky and initial-score agreement within 1e-10 relative.
The full quadratic-versus-eliminated identity uses a relative 1e-7 budget with
absolute scale max(1, sum of magnitudes of its terms). Preserve failures.

The practical continuation gate is exactly the protocol's: on at least two
of three states, all three repeated clipped proposals must have rho>0.1 and
true decrease >2 times the stored Eta2 witness decrease. The repetitions are
deterministic fixed-state CPU checks, not optimizer success-rate samples.

For the separate original approximate-zero question, report the actual
decrement, its ratio to the Eta2 gain, and whether it is at numerical zero:
decrement <=100*machine_epsilon*max(1, point-only damped decrement).
This numerical-zero convention cannot authorize a rollout; only the practical
feasibility gate above can do that. Also report the norm and global similarity
fraction of the proposed camera direction; damped gauge modes are not deleted.

No source reference is relabeled an exact full GN step. The original retained
prediction mismatches remain linked in every final report.
