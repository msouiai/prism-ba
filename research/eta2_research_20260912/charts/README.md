# Brief 2 preparation: point charts, without a solver rollout

This directory contains a **CPU FP64 reference and mathematical audit**, not a new champion or a measured BA improvement. No GPU run, witness selection, accepted-state update, or parameter sweep is performed here. The frozen source and all 44 headers were verified against `source_manifest.json`; `Scalar=double`, the actual compact FP32 storage flags, and the full champion configuration are recorded in [verification.json](verification.json).

## Interface for witness replay

[reference.py](reference.py) uses `CameraState(R[nc,3,3], t[nc,3], intrinsics[nc,3])`, with intrinsics `(f,k1,k2)` and `k2=0`. Camera directions have shape `(nc,9)` and the native convention `[dw,dt,df,dk1,0]`: `R_new=Exp(dw) R`, additive translation and intrinsics. `load_prisms01` reads exact native matrix states and transposes the native intrinsic layout `(3,nc)` without converting rotations to angle-axis and back.

```python
from reference import load_prisms01, load_observations, evaluate_chart_step

cameras, X, dims = load_prisms01(state_path)
ci, pi, uv, bal_dims = load_observations(bal_path)
assert dims == bal_dims
result = evaluate_chart_step(
    cameras, X, ci, pi, uv, camera_step, lam,
    chart="homogeneous",  # or "euclidean", "inverse_depth"
    scene_radius=registered_radius,
)
```

The **same prescribed camera step** goes into every chart. Point steps solve

\[
(J_p^T J_p+\operatorname{diag}(d))\delta
=-J_p^T(r+J_c d_c),
\quad d_a=\max(\tau (J_p^TJ_p)_{aa},10^{-3}\tau\operatorname{tr}(J_p^TJ_p)/3),
\]

with the native tiny-block fallback. By default `tau=lam`; an explicit `tau` is possible for a subsequently registered ablation. This reference builds all blocks from the same FP64 residual Jacobians; it is not a bit-exact emulation of the champion's compact point factors/cross blocks. A native direction/control arm must be retained separately when that distinction matters.

Outputs include chart coordinates, homogeneous candidate points, FP64 point normals/damping, solve residual, `score_init`, full/camera-only/point-only true costs, full GN prediction, true decrease, `rho`, per-track costs and model errors, track lengths, Euclidean displacement/fling count, and observation-level cheirality flips. CPU time is diagnostic overhead, not an estimate of native GPU solve time. Invalid projections are counted and scored as infinity, never silently dropped. `track_max_parallax` computes the exact maximum pair angle per track, with explicitly reported O(sum track-length-squared) diagnostic work.

The error decomposition is

\[
e_{\rm full}=F(c^+,p^+)-\tfrac12\|r+J_cd_c+J_p\delta\|^2,
\]
\[
e_c=F(c^+,p)-\tfrac12\|r+J_cd_c\|^2,
\quad e_p=F(c,p^+)-\tfrac12\|r+J_p\delta\|^2,
\quad e_{\rm cross}=e_{\rm full}-e_c-e_p.
\]

These terms are returned per track for the main witness driver to bin or rank. The decomposition is algebraic, not a causal attribution: a signed cross term can cancel other errors. The full candidate still needs the main solver's acceptance checks.

For inverse depth the deterministic default anchor is the point's first observation in the original ordering; explicit anchors are accepted. An anchor exactly on the projection horizon raises instead of silently choosing another chart. Unobserved points default to camera zero; their normal equations contain only the native tiny numerical floor. Report anchor choice when comparing runs.

## Mathematical audit

**Homogeneous sphere.** Write the point as a unit vector `H=(h,w)` on `S3`, with antipodal vectors representing the same projective point. Let `B` be an orthonormal basis of `H`-perpendicular. The Householder construction is stable at either coordinate pole. The retraction

\[
H^+=\frac{H+B\delta}{\sqrt{1+\|\delta\|^2}}
\]

has angular displacement `atan(||delta||)<pi/2`, and derivative `B` at zero. The exact point Jacobian is `J_projection [R | t] B`. For the native left rotation retraction, the camera-space derivative is `[-[Rh]_cross | w I]`.

This bound is **not a bound on Euclidean displacement**: division by `w` is unbounded near zero. The verified counterexample in [verification.json](verification.json) takes a tangent step of approximately `0.001` and moves the Euclidean point by approximately `1e12`. Nor does sphere normalization ensure a finite pixel projection: the unchanged SIMPLE_RADIAL projection still has a pole wherever `[R | t]H` has zero third coordinate. Regular points at infinity (`w=0`, nonzero projected depth) are representable and differentiable; camera-image horizons remain singular.

**Frozen-anchor inverse depth.** For copied anchor pose `(Ra,ta)`, center `Ca=-Ra.T ta`, and `q=Ra X+ta`, set `(u,v,rho)=(q_x/q_z,q_y/q_z,1/q_z)`. Retain the signed depth appropriate to Snavely's negative-Z viewing convention. Use the homogeneous representative

\[
H(u,v,\rho)=\begin{bmatrix}R_a^T(u,v,1)^T+\rho C_a\\\rho\end{bmatrix}.
\]

The stored derivative is the constant matrix with columns `(Ra.T e1,0)`, `(Ra.T e2,0)`, `(Ca,1)`. This avoids evaluating `1/rho` when scoring at infinity. The anchor stays fixed during both Jacobian construction and retraction, so an observation still touches one live camera and one point. Changing to a new anchor/chart after acceptance is a separate operation; this reference does not do an optimizer rollout.

Undistorted image coordinates at fixed bearing are ratios of affine functions of `rho`, not generally affine functions. Radial distortion adds further nonlinearity. Thus near-linearity is a geometric regime to measure, not a guarantee. Inverse depth can improve representation of poorly constrained depth without making every thin-track model accurate.

**Claims that do not follow from either chart.** The same plain pixel objective remains insensitive to reversal of a camera ray, so a chart cannot eliminate its cheirality blind spot. Treat cheirality counts as diagnostics, not hidden acceptance restrictions. Neither chart by itself proves that `tau << lambda` is safe or removes the point-damping floor. A changed chart changes both the retraction and the diagonal Marquardt damping metric: `diag(G.T V G)` is not the pullback `G.T diag(V) G`. A later success must not be attributed solely to boundedness. Spherical normalization also introduces dependence on the chosen world origin and coordinate scale; freeze that convention.

Depth freezing would constrain a search direction, not change scored observations, but has not been implemented or tested here. In the inverse-depth chart fixing `rho` removes depth displacement while retaining two bearing coordinates; it does not forbid large lateral displacements from large bearing updates at small fixed `rho`. A universal no-fling guarantee would therefore still be incorrect.

## Prior art boundary

[Triggs et al., Bundle Adjustment — A Modern Synthesis (2000)](https://lear.inrialpes.fr/people/triggs/pubs/Triggs-va99.pdf), section 2.2, explicitly describes flat XYZ behavior at distant points and recommends homogeneous point coordinates with spherical normalization. Better conditioning near projective infinity is established motivation.

[Schneider, Schindler, Läbe and Förstner (ISPRS Annals 2012)](https://isprs-annals.copernicus.org/articles/I-3/75/2012/isprsannals-I-3-75-2012.pdf), equations 16–17 and the subsequent scene-point substitution, already use the normalized tangent update `N(X + null(X.T) delta)` for homogeneous points. The S3 construction itself is not novel. Their ray-observation formulation and handling of fixed calibration are not the same scored objective as this SIMPLE_RADIAL pixel experiment.

[Civera, Davison and Montiel (IEEE T-RO 2008)](https://www.doc.ic.ac.uk/~ajd/Publications/civera_etal_tro2008.pdf), sections III–IV, establish inverse-depth representations and analyze measurement linearity, especially at low parallax. This is substantial overlap with the proposed motivation; frozen-per-outer anchoring within a GPU inexact Schur method is an integration choice whose priority has not been established.

[Zhao et al., ParallaxBA (IJRR 2015)](https://journals.sagepub.com/doi/10.1177/0278364914551583), also available via the [author-affiliated research record](https://www.research.ed.ac.uk/en/publications/parallaxba-bundle-adjustment-using-parallax-angle-feature-paramet/), shows that both XYZ and inverse-depth BA can have poorly conditioned normal equations. It proposes parallax-angle parametrization and measures improved behavior. This prevents claiming that inverse depth generically solves weak geometry.

The plausible contribution here remains empirical and specific: whether a chart and its damping metric improve Eta2's measured nonlinear witness steps without losing its time-to-target advantage. No result in this directory establishes that.

## Verification and current status

Run `OPENBLAS_NUM_THREADS=1 python research/eta2_research_20260912/charts/verify_reference.py` from the repository root. The deterministic suite checks all active camera/point Jacobian columns against independent central differences in all three charts; homogeneous tangent orthogonality and retraction angle; exact-state file round trips; chart invariance of the initial objective/camera Jacobian; the point-coordinate chain rule; and conditional normal solves against independent augmented least-squares solves. It also verifies the counterexamples above and a regular point at infinity.

Latest verification: maximum finite-difference relative error `2.97e-8`; maximum normal-solve versus augmented-least-squares relative error `1.55e-14`. These are implementation checks on synthetic fixtures, not repeated BAL performance cells. Witness replay and any champion combination await the main agent's pre-registered experiment.
