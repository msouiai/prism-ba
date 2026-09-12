# E2/E3 native registration

Registered after the E1/E2 fixed-state screen and before native scores.
`witness_selection.json` selects cap c=30 by the previously registered rule.
Both spectral floor families fail the healthy locality gate (minimum 46.95%
affected cameras); do not build them as production candidates.

Arms: off; cap30; spectral-intrinsic freeze; prior successful opening reference.
For spectral-intrinsic freeze, form the native 9x9 Schur diagonal including its
existing intrinsic prior at each attempt, transform by the captured E, and
eigendecompose its active 8x8 block. Gate a camera if mu_min < 0.001 mu_max,
the weakest scaled eigenvector has f-plus-t_z squared loading >0.5, and each
component has squared loading >0.05. These constants are fixed for all scenes.
Freeze f,k1 by projected RHS/operator/preconditioner application; point
completion remains coupled to the actual constrained camera step. This is the
exact-constraint limit of a strong intrinsic shadow regularizer. Recompute the
gate every attempt, with no hysteresis or controller memory. No gauge projection.

All arms use the same derived binary and W1 trace overhead. Optional cap is
applied after the raw solve and before global radius enforcement, point
completion and true scoring. Initialize the radius from the original raw step
as the champion does. Record original raw norm, intermediate capped norm,
remaining global scale and actual norm separately. Unchanged camera blocks
remain bit-identical at the cap operation; a subsequent global clip still
changes them. Intrinsic gating includes block construction, CPU eigensolves and
copies in solve wall. Duplicate camera/point observations are checked separately.

Run original/off N=3 on Dubrovnik88 for compatibility; cap and gated-intrinsics
then healthy locality N=3 on Ladybug539. An arm touching >5% at any attempt on
this healthy scene is killed as specified, with all evidence retained. Surviving
arms get N=5 Venice and Final3068, then practical N=3 if Venice >2/5. Opening
reference and off supply fresh controls. A failed locality gate is not overridden
by a favorable endpoint.

E3 opening factorial: eta 0.05,0.1,0.2 x rejection window 1,2,3 accepted steps x
forcing window either equal to rejection window or one accept; duplicate
one-accept cases removed (15 configurations). Each has N=5 Venice. Only >=4/5
survivors reach nine-cell N=3; fixed selection and confirmation in PROTOCOL.md.
Cap combination is gated on cap's locality result. Output endpoint states are
losslessly retained; RAM only stages writes. E1 fresh opening captures retain
complete state for the first 3 accepted outers (including rejection attempts).
These diagnostic runs are separate from scored timings.
