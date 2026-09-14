# Per-solve CUDA workspace protocol

Registered 2026-09-14 before implementation.

Replace function-static nonlinear-cost scratch, including deterministic cost
partials/output, with explicit RAII ownership scoped to a solve and CUDA device
in a derived, default-off path. Record the owner
device, allocate after device selection, synchronize before destruction, restore
the previous device, and reject cross-device use. Serial deterministic flag-off
and flag-on traces must be exact and logs must confirm the owned cost path fired.
The inherited deterministic BLAS reduction workspace remains process-static in
this scoped prototype, so it cannot claim complete concurrent deterministic
solve safety. A two-thread one-GPU test is deferred unless BLAS scratch is also
plumbed per solve. Kill promotion if exact serial compatibility fails; treat
the partial result as negative for full concurrency until all static scratch is
removed.
