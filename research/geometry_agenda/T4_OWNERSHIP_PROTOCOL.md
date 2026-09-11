# T4 diagnostic revision: point ownership

The first automatic partition gets all camera labels right but misassigns up to
9% of points in the small transfer cohort; its nonlinear speed falls below
fine-only (0.61–0.66x). This contradicts the known-partition gain. We will test
one explicit correction, not silently replace the failed arm.

Keep the same Schur-based camera partition. Before computing the point votes,
multiply each camera–point coupling norm by the bounded confidence
`1/(1+||r_ip||^2/(2 px)^2)` at the initial state. The hypothesis is that already
consistent local projections identify which region a point should move with;
strong but currently inconsistent bridge leverage should not decide ownership.
This confidence affects **partitioning only**, not the optimization objective,
the measurements retained, or their weights in BA. Point0 remains the scale
anchor. The rule may fail when a region is internally poor, which must be
tested on real observations before promotion.

Use development seeds 0–9 for a small diagnostic, then new held-out seeds
300–309 for both 12/180 and 30/900 sizes, weak and strong bridges, N=3. Preserve
all v1 results. Same arms/targets/caps as T4_TRANSFER_PROTOCOL, naming this
partition v2 in the output. No tuning confidence scale after held-out results.
