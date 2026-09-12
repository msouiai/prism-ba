# Capacity-only storage placement

Registered while the initial tail cohort is running, before the opening grid.
No flags, order, scores or evidence-retention rule changes. Once compressed
wave-3 artifacts under /workspace/eta2-wave3-evidence exceed 270 MB, new endpoint
exports go to research/eta2_wave3/durable_states on the root volume. Each run
still stages raw state in RAM, verifies a durable compressed copy by SHA256,
and records its exact path. No existing archive or endpoint is removed.
Root has approximately 184 MB free at this registration. Failure to preserve
an endpoint halts dependent work; it is not a valid completed result.
