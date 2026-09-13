# D19 result: rank-one prior still perturbs the global Krylov direction

## Verdict

D19 stops at its fixed-state gate.  Regularising only camera 34's weakest local
eigenvector collapses raw/radius from about 428 to 0.844 and raises true
decrease from 1.603 to about 626.64 with rho `1.00028` in all five Venice
states.  Yet the re-solved direction retains only `87.667%` of the ungated
camera norm, below the preregistered 95% requirement.  No native arm runs and
the frozen Eta2 champion remains the winner.

## Fixed result

The corrected D18 captures and immutable geometric gate are reused.  In every
state camera 34 is both the raw-energy leader (`99.99956%`) and the camera with
the smallest active local Schur eigenvalue.  The only intervention is

`Delta_1 = max(0, mu_ref - mu_0) q_0 q_0^T`.

| Quantity | Control | Rank-one prior |
|---|---:|---:|
| Raw/radius | 428.26 | 0.8440 |
| Ungated norm retained | 100% | 87.667% |
| True decrease | 1.603 | 626.64 |
| Rho | 0.3006 | 1.00028 |

All five states pass the ratio, decrease and rho conditions.  All five fail
only healthy-component retention.  Three deterministic linear repetitions
agree to rounding, and the archived direction and full objective pass the same
audits as D18.

## Interpretation

A low-rank operator change is not a low-rank step change.  Through Schur
coupling, the preconditioner and Eta2's loose one-update forcing stop, a
rank-one prior changes the entire returned camera vector.  This explains why
its healthy-component loss is larger than D18 dose 1's all-mode prior despite
modifying fewer eigenvalues.

Direct decomposition supplies the next, distinct actuator.  Camera 34's
weakest eigenvector contains `99.99726%` of total raw-step energy in every
state.  Subtracting that one coefficient from the already-computed direction
gives raw/radius `2.24076--2.24087` and leaves every other camera bit-identical
before the ordinary global clip.  D20 tests that quotient projection under a
separate protocol; D19's native gate remains closed.

Machine-readable evidence is in `d19-rank-one-prior-results.json` and
`d19-rank-one-prior-summary.json`; source and fixed-system manifests are under
`d19_rank_one_prior/`.
