# The frozen eta2 champion is single-shift

The Final13682 Caspar wins belong to single-shift, coupled LM with Hcc-block
PCG and fixed eta2 forcing. They do not establish an advantage for the
multi-lambda menu. There is no matched five-shift arm of this champion in the
published evidence. Older one/five comparisons concern a predecessor.

At d3d42dc, `source/prism_eta2.cu` explicitly requires L=1 in the classical-LM
compatibility check, forcing wrapper, and PCG path (lines 9251, 9630, 11090).
A runtime probe using the complete champion flags and only NSHIFTS changed to 5
returns nonzero with `classical LM requires plain 9DOF single-shift PCG...`.
Removing these guards alone would not work: the classical shift assignment
(line 10804) fills EVERY entry with lam_cam, not distinct shifts.

More fundamentally, write the coupled normal equations as

    [ B + lambda Dc       W             ] [dc] = [bc]
    [ W^T                 C + lambda Dp ] [dp]   [bp].

For camera scaling E = Dc^(-1/2), eliminating points gives

    A(lambda) = E [B - W(C+lambda Dp)^(-1) W^T] E + lambda I,
    b(lambda) = E [bc - W(C+lambda Dp)^(-1) bp].

Both the reduced operator and RHS depend on lambda. The frozen implementation
sets tau_eff=lambda in classical LM; the camera scaling comes from Hcc.
Thus this is not a fixed A plus scalar shifts with one common RHS. Furthermore,
for even a fixed preconditioner M, preconditioning A+lambda I gives
M^(-1)A + lambda M^(-1), rather than a scalar identity shift. The generic
unpreconditioned shifted-CG zeta recurrence is not valid just by enabling PCG.
The Hcc block preconditioner here itself includes the current shift.

These are statements about the existing implementation and recurrence, not an
impossibility theorem for preconditioned families or multi-damping BA. A valid
coupled five-lambda comparator could perform five separately factored/RHS PCG
solves with matched stopping and scoring, then measure shared assembly versus
extra solves. It would be a new implementation, not the existing shared-Krylov
menu. Alternatively fixing point damping and changing the preconditioner/metric
could restore a suitable shifted family, but that changes the champion's
algorithm and must be labeled separately.

Single-shift is therefore load-bearing for this implementation. Whether it is
performance-optimal against a properly redesigned multi-lambda solver remains
unmeasured. Do not interpret a rejected configuration as evidence of slowness.

The original /workspace/prism-ba checkout lacks d3d42dc, but the object exists
locally in /tmp/prism-ba-publish on research/eta2-champion-publish, as well as
on origin. The research/schur-preconditioner worktree was created from it.
