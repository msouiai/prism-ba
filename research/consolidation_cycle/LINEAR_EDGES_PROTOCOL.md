# Linear-edge consolidation protocol

Registered 2026-09-14 before tests. Base `d3d42dcb803f104424a3343364cac414a7ab7342`; frozen Eta2/B6v7 are not edited. Deliver a derived source containing only default-off `OCA_AUDIT_LINEAR_EDGES`.

Enabled behavior: scaled norm accurate whenever the true norm is representable; explicit rejection of unrepresentable norms and NaN/Inf; exact all-element-zero detection distinct from tiny values; capped forcing arithmetic without spurious overflow or consequential underflow; depth-zero convergence only for classical unshared CD9 single-shift PCG, retaining point back-substitution/scoring and all mode validation.

CPU fixtures: zero, ordinary, `1.6e-162`, underflow, overflow, mixed exponents, NaN/Inf, forcing extremes, and ordinary-path bit parity. The injected GPU fixture requires zero iterations/matvecs/false negative-curvature, >=1 accepted point-only update, and independently rescored endpoint at least 1.0 below initial objective. Flag-off source and trace must exactly match an identical fixed-order deterministic derivative; unordered reruns do not establish parity. Any failure blocks extraction.

