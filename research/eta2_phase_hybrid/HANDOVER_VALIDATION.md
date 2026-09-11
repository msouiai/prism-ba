# Post-diagnostic integration check

The 18-run collapse diagnostic finished before registering this check. Its two
Ladybug49 collapse markers occur at the same iteration as target termination,
so they exercise the detector but do not exercise PCG after that event.

Use the unchanged diagnostic binary, menu-feedback mode, opening limit 600,
Ladybug49, N=3, max_iter=20 and the same 12-second safety budget, with no target.
Verify that any observed genuine collapse is followed by PCG preparation and
monotone accepted objective. Record runs even if their atomic-order trajectory
does not trigger the detector. This is an integration check, not a new speed
or endpoint-quality comparison. Do not alter either reported study.
