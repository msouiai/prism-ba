# D18 result: geometric prior fixes the witness model but misses locality gate

## Verdict

D18 stops before native rollout.  Its immutable gate correctly selects Venice
camera 34 in all five archived terminal states, and every finite prior changes
the fixed proposal from a nearly useless clipped step into a highly faithful,
large-decrease step.  No registered dose passes every advance condition,
however.  The best-balanced dose retains `94.475%` of the ungated camera norm,
just below the preregistered `95%` requirement.  The threshold is not waived;
the frozen Eta2 champion remains the winner.

## Capture and validation

The five terminal systems have archived radius `403.786065864875...`, lambda
and tau `6.4e-10`, and forcing tolerance `0.5`.  Independent state
reconstruction agrees with the archived full cost to `2.4e-15` relative or
better.  An initial harness run inherited radius zero from the generic capture
binary and was invalidated before nonlinear scoring; the archived radius is
now explicitly checksum-pinned under `D18_CAPTURE_RADIUS_AMENDMENT.md`.

The corrected gate gives, over the five states:

- raw/radius `428.257--428.267`;
- top camera 34 in 5/5;
- weakest local scaled Schur block camera 34 in 5/5;
- camera-34 raw-step energy share `99.999556--99.999562%`.

The fixed PCG control reproduces the archived raw direction to the registered
tolerance.  Three deterministic repetitions per arm agree to numerical
roundoff, and every scored endpoint is independently evaluated on the full
plain-L2 objective.

## Dose screen

Medians are shown below; ranges across the five states are tiny.

| Dose | Raw/R | Healthy norm retained | True decrease | Rho | Registered result |
|---:|---:|---:|---:|---:|---|
| 0 | 428.26 | 100.000% | 1.603 | 0.3006 | Control |
| 0.1 | 0.794 | 87.646% | 619.58 | 0.99975 | Fails 95% retention |
| 1 | 0.853 | 94.475% | 582.97 | 0.99947 | Fails 95% retention |
| 10 | 10.71 | 1,187% | 294.77 | 1.00197 | Fails Raw/R <= 10 |
| 100 | 10.62 | 1,177% | 358.53 | 0.99918 | Fails Raw/R <= 10 |
| hard projection | 10.36 | 1,143% | 370.17 | 0.99888 | Descriptive only |

All finite doses improve true decrease in 5/5 states and never lower rho.  The
smallest two doses satisfy the ratio condition in 5/5; the larger doses do
not.  Dose 1 misses healthy retention by about 0.525 percentage points in
every state.  Since the protocol requires every condition, the selected dose
is null and `native_arm_earned=false`.

The non-monotone response to dose is expected under Eta2's loose forcing: the
prior changes both the operator and preconditioner, so the returned finite
Krylov iterate is not a monotone regularisation path.  At doses 0.1 and 1 PCG
stops after one update; doses 10 and 100 use four and six updates and amplify
the healthy component by roughly twelve times.

## Mathematical finding

This experiment cleanly separates detection from actuation.  Observation
count misses the Venice failure, while the local information spectrum finds
it without an expensive posterior inverse.  A one-camera Gaussian prior then
removes the 428-radius soft component and makes the quadratic model almost
exact on the resulting proposal.  Thus geometric starvation is real and
locally regularisable at a fixed state.

What remains unproved is trajectory benefit.  Five prior campaigns show that
a locally superior direction can select a worse basin, and D18's preregistered
locality condition was designed to block precisely that risk.  The result
therefore supports a narrower follow-up: regularise only camera 34's single
weakest eigenvector, rather than every eigenvalue below a global scale.  That
rank-one intervention is an information-geometric/MBAM actuator with a new
protocol; it is not a relaxed D18 threshold.

Machine-readable evidence is in `d18-geometric-prior-results.json` and
`d18-geometric-prior-summary.json`.  Captures, fixed solutions and logs are
represented by hashes in `d18_geometric_prior/`.
