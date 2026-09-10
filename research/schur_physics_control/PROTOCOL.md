# Prospective bounded implementation gate

Registered before executing the new GPU code, 2026-09-10.

Incumbent: frozen d3d42dc eta2 package, source and header hashes verified by builds.
Experimental sources live here; generated copies never modify that package.

1. Implement a balanced SPD coarse correction with rank 8/16, using Ritz
   vectors extracted from at most 32 normalized directions of a previous Hcc
   solve. Small Gram matrices are rank-truncated at 1e-10 relative eigenvalue;
   the current coarse matrix must pass an SPD/finiteness gate. Ordinary PCG
   holds its preconditioner fixed during each solve.
2. Use Muell outer11->12 and Ladybug598 outer7->8 to test reuse between adjacent
   frozen linearizations. Capture the missing predecessor and complete damping
   data without changing the champion trajectory. Final1936 outer0 is the
   no-history shallow control. Construction, history collection, refresh and
   true-residual checks are charged. Also report a cold construction probe,
   so a warm timing cannot be confused with a free setup. N=3, rotated arms.
3. If any meaningful operator saving appears, integrate the correction after a
   preceding solve of at least 16 iterations. Test both ranks on short Muell /
   Final1936 target screens, N=3, targets 1946488.746262194 / 5125687.352261469,
   12 native seconds, 600 outers. Ladybug598 is a transfer control with its
   existing registered target located before running, not fitted to new arms.
   A failed fixed gate may still receive a clearly labeled small exploratory
   nonlinear screen if linear trajectories offer a reasonable mechanism.
4. Diagnose Final3068 gradient/stop behavior in Claude v2 library-equivalent
   configuration, and the frozen champion as a distinct arm. First log
   undamped scaled camera/point gradient, lambda/tau and stopping events.
   Use N=10 for the known multimodal configuration, 60 outers and a 30-second
   safety limit per run. Compare the existing stop-window option separately;
   do not call removal of early stopping an algorithmic speedup. Any new
   recovery requires an explicit follow-up amendment and original stop control.
5. Test the exact projected coupled menu at factors .25,.5,1,2,4 on frozen
   captures, ranks 8/16. Reconstruct point damping from original undamped
   factors/diagonal, update BOTH Schur matrix and RHS, and validate each lifted
   solution against a true full-operator residual at the original forcing
   tolerance. Compare charged basis/setup/solve/validation work to independent
   Hcc-PCG. Failed residual gates are failures, not speedups. Only a passed
   linear gate justifies a nonlinear menu integration.

Zero-error CUDA memcheck and off-mode objective parity precede timing. Keep all
runs, cap hits and residual failures. The promotion bar is a consistent roughly
1.10x time-to-identical-target gain with reliable hits; small single-digit
regressions on a control do not automatically veto a useful configuration.
No claim against Caspar is inferred from a comparison between Prism variants.
The physical/control work here is the diagnostic and conditional-work route;
it does not launch an unrelated Hamiltonian/GBP/DABA implementation.
