# W2 and W5 fixed-state registration

Before new proposal scores: seven immutable wave-1 captures (Venice0/1/2,
Final3068 0/5/6, Ladybug1197 0). N3 repeated calculations each. These are
repeat numerical witness calculations, not independent trajectories/hit rates.
All original observations, exact captured matrix states, lambda, radius and E.
Native assembly supplies intrinsic-prior statistics; captured Hcc supplies the
camera preconditioner, captured Cdiag supplies guarded point damping.
Coherent FP64 Jacobian and augmented point QR from the existing Brief0 reference.
Record reduced fresh residual certification and preserve its prior full-normal
qualification. Any new direction promoted beyond a witness requires independent
full-normal and nonlinear CPU audits first.

W2: reference solve at original lambda, raw and clipped, and actual saved Eta2
proposal. Re-solve with increased camera lambda in two separately named arms:
coupled point tau and frozen initial point tau. Root seeks0.75R, accepts[R/2,R],
triggers only above2R, eight root updates maximum, safeguarded log secant,
positive increasing lambda while oversized, geometric bracket when undersized.
Root sees only step norm, never nonlinear cost. Fresh PCG from zero per solve;
all setup, products and root work recorded. Explicit clipped fallback if no fit.
This is a mechanism test, not a claim of zero-cost multishift or native speed.
Kill native re-solve extension if no Final witness gains true decrease at matched
radius. No claimed exact camera trust-region solution in the coupled arm.

W5: Final0/5/6 and Venice0 only; reference clipped first direction,
same lambda/tau for second RHS, h0.1 residual directional difference on the
code's retraction, correction d1+0.5d2, guard ||d2||D<=0.75||d1||D.
If corrected camera norm exceeds R, scale the entire corrected full step to R;
log scaling. No point re-completion that would silently replace the correction.
Full original GN prediction and true-cost evaluation after the modification.
Save correction and first direction for independent audits. No uphill acceptance.
Kill if witness rho does not improve or guard rejects over80% of tested proposals;
do not substitute projected or unguarded proposals for the registered arm.

The native GPU queue stays serialized with /tmp/prism_gpu.lock. Diagnostic
wall includes all solves and references and is never presented as solver speed.
