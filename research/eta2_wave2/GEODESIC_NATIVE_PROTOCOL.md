# Native analytic geodesic acceleration, before scored runs

The analytic directional-curvature audit passed: all four source witnesses,
N3, independently recomputed full-normal residuals below1e-8 and matching true
costs. Final5/6 retain useful improvement; Final0 is effectively unchanged.

Single binary, off versus on, otherwise frozen Eta2. After its radius-clipped
first camera solve and ordinary point back-substitution, build analytic r''
along that actual full step. Re-evaluate J^T r'' in FP64 without allocating a
coherent Jacobian workspace. Form the second reduced RHS using the SAME native
point factors, cross blocks, camera scaling and operator. Fresh PCG from zero,
eta0.5, native maxck iteration cap, true residual check1.01*eta. A nonpositive
curvature event or failed certificate discards the optional correction; it does
not change the champion's existing first-solve persistent-floor policy.

Form d1+0.5d2 only if ||d2||D<=0.75||d1||D; scale the full corrected direction
if its camera norm exceeds the radius. Use full original GN prediction, strict
rho>0.1 and true-cost descent. Retain the existing first proposal if the correction
does not beat it. No bold/uphill acceptance, no momentum, no radius/root/damping
combination, no change to point damping, no W8 stopping interception.

All derivative, RHS, solve, candidate and diagnostic costs count in native wall.
Log guard, second-CG depth/certificate, cutoff, candidate gain and seconds.
Count second PCG work in attempt totals, and report accepted correction versus
eventual outer acceptance separately. No extra residual evaluation is needed
for analytic r'', but extra RHS and full candidate evaluation are charged.

First validate the second RHS and solve against an independent coherent toy
and memcheck; then original-v-derived-off N3 compatibility. Scored cohorts:
Venice52 and Final3068 N5/arm at243740.27 and1744796.9841897595,
600outers/60native-seconds. If guard discards >80% of proposals, report the stated
kill and stop before the practical panel. Otherwise nine practical cells N3.
No post-hoc scene gating or threshold changes. Report both directions, all
misses and conditional timings; retain the original champion unless the
registered evidence supports replacing it.
