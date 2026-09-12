# D0v2 fixed-reduction validation

Registered before D0v2 native execution.  All arms, scenes, repetitions and
decision gates in `D0_PROTOCOL.md` remain fixed.

D0v1 failed repeatability.  The first differing trajectory value was the
outer-0 camera-step norm on Venice (spread about 3e-15 relative); on Final3068
the first differing norm or rho appeared by outer 1--2.  Assembly, Schur
point accumulation, nonlinear cost and full-model reduction were already
fixed, leaving source-level cuBLAS dot products and norms as the earliest
uncontrolled floating reductions.

D0v2 routes every source-level `cublasDdot` and `cublasDnrm2` call through the
same private-block plus fixed-final-tree reduction when
`OCA_W6_DETERMINISTIC=1`.  It preserves cuBLAS pointer-mode semantics and
delegates to cuBLAS verbatim when disabled.  No nonlinear algorithm,
preconditioner, stopping rule, target, cap or statistical gate changes.

The v1 rows are retained as localization evidence and are not pooled with v2.
