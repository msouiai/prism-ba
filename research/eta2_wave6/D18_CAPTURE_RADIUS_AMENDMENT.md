# D18 capture-radius amendment

Recorded before full-objective scoring and before interpreting the preliminary
fixed-system rows.

The generic fixed-system capture binary writes radius zero in `dimensions.txt`
because it starts a fresh one-outer solve and captures before Eta2 initialises
its radius.  D18 replays archived terminal attempts whose checksum-pinned
metadata records radius `403.786065864875...`.  The first harness run therefore
reported an infinite raw/radius ratio, although the other two immutable gate
conditions still selected camera 34.

Those preliminary rows are invalid and are overwritten.  The capture script
now copies the archived radius to `registered_radius.txt`, the fixed solver
requires a finite positive value from that file whenever the capture radius is
zero, and all manifests record this amendment's hash.  Lambda, tau, forcing,
operator, right-hand side, direction and every scored rule are unchanged.
