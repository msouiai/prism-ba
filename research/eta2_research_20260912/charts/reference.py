"""CPU FP64 point-chart reference; no optimizer rollout or baseline replacement.

Camera tangent convention: R+ = Exp(dw) R; t, f, k1 are additive; dk2=0.
All scoring uses original SIMPLE_RADIAL pixel residuals, including negative depth.
The supplied camera step is held identical across chart comparisons. Point solves
are Gram-consistent FP64 references, not emulations of compact champion storage.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import struct
import time

import numpy as np
from scipy.spatial.transform import Rotation


@dataclass(frozen=True)
class CameraState:
    R: np.ndarray             # (nc,3,3), world to camera
    t: np.ndarray             # (nc,3)
    intrinsics: np.ndarray    # (nc,3), f,k1,k2; k2 must be exactly zero

    def __post_init__(self):
        nc = len(self.R)
        for name, shape in (("R", (nc, 3, 3)), ("t", (nc, 3)),
                            ("intrinsics", (nc, 3))):
            a = np.asarray(getattr(self, name), dtype=np.float64)
            if a.shape != shape or not np.isfinite(a).all():
                raise ValueError(f"invalid {name}: expected finite {shape}")
            object.__setattr__(self, name, a)
        if np.any(self.intrinsics[:, 2] != 0):
            raise ValueError("This reference fixes k2=0; it never silently zeros data")

    def retract(self, d: np.ndarray) -> "CameraState":
        d = np.asarray(d, dtype=np.float64)
        if d.shape != (len(self.R), 9) or not np.isfinite(d).all():
            raise ValueError("camera step must be finite (nc,9)")
        if np.any(d[:, 8] != 0):
            raise ValueError("camera step may not change k2")
        dR = Rotation.from_rotvec(d[:, :3]).as_matrix()
        # Match the native ExpSO3 zero-angle branch exactly.
        dR[np.linalg.norm(d[:, :3], axis=1) < 1e-12] = np.eye(3)
        return CameraState(dR @ self.R, self.t + d[:, 3:6],
                           self.intrinsics + d[:, 6:9])

    def centers(self) -> np.ndarray:
        return -np.einsum("nji,nj->ni", self.R, self.t)


def verify_frozen_baseline(champion_dir: Path | None = None) -> dict:
    """Read-only verification; no build, launch, inherited flag use, or GPU use."""
    root = champion_dir or Path(__file__).resolve().parents[2] / "eta2_champion"
    manifest = json.loads((root / "source_manifest.json").read_text())
    config = json.loads((root / "champion.json").read_text())
    source = root / "source/prism_eta2.cu"
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    if sha(source) != manifest["source_sha256"]:
        raise AssertionError("Frozen source checksum mismatch")
    for name, expected in manifest["headers_sha256"].items():
        if sha(root / "source/headers" / name) != expected:
            raise AssertionError(f"Frozen header checksum mismatch: {name}")
    if "using Scalar = double;" not in source.read_text():
        raise AssertionError("Unexpected Scalar configuration")
    required = {"OCA_NSHIFTS": "1", "OCA_PCG": "1", "OCA_CLASSICAL_LM": "1",
                "OCA_COMPACT_FRAGMENTS": "2", "OCA_RLA_FIXED_ETA": "2",
                "OCA_FORCE_UNSHARED": "1"}
    for key, expected in required.items():
        if config["flags"].get(key) != expected:
            raise AssertionError(f"Unexpected champion flag: {key}")
    return {"source_sha256": manifest["source_sha256"],
            "verified_headers": len(manifest["headers_sha256"]),
            "champion_config": config,
            "arithmetic_note": "Native Scalar=double with FP32 compact cross blocks/point rows; this CPU reference is Gram-consistent FP64"}


def load_prisms01(path: str | Path) -> tuple[CameraState, np.ndarray, tuple]:
    """Lossless matrix-state adapter; native intrinsic layout is (3,nc)."""
    with open(path, "rb") as f:
        if f.read(8) != b"PRISMS01":
            raise ValueError("Expected PRISMS01 state")
        nc, np_, no = struct.unpack("<QQQ", f.read(24))
        R = np.fromfile(f, dtype="<f8", count=9 * nc).reshape(nc, 3, 3)
        t = np.fromfile(f, dtype="<f8", count=3 * nc).reshape(nc, 3)
        X = np.fromfile(f, dtype="<f8", count=3 * np_).reshape(np_, 3)
        intr = np.fromfile(f, dtype="<f8", count=3 * nc).reshape(3, nc).T.copy()
        if f.read(1) or not np.isfinite(X).all():
            raise ValueError("Trailing bytes or nonfinite points")
    return CameraState(R, t, intr), X, (nc, np_, no)


def load_observations(path: str | Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, tuple]:
    with open(path) as f:
        dims = tuple(map(int, f.readline().split()))
        obs = np.loadtxt(f, max_rows=dims[2], ndmin=2)
    return obs[:, 0].astype(np.int64), obs[:, 1].astype(np.int64), obs[:, 2:4], dims


def normalize_rows(x: np.ndarray) -> np.ndarray:
    # Scale first so even a very large finite tangent cannot overflow its norm.
    scale = np.max(np.abs(x), axis=-1, keepdims=True)
    if np.any(scale == 0) or not np.isfinite(scale).all():
        raise ValueError("Cannot normalize zero/nonfinite homogeneous vector")
    x = x / scale
    return x / np.linalg.norm(x, axis=-1, keepdims=True)


def homogeneous_from_euclidean(X: np.ndarray) -> np.ndarray:
    return np.column_stack((np.asarray(X, dtype=np.float64), np.ones(len(X))))


def euclidean_from_homogeneous(H: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        return H[:, :3] / H[:, 3, None]


def householder_tangent(H: np.ndarray) -> np.ndarray:
    """Orthonormal (n,4,3) tangent basis at unit H, stable at both poles.

    The Householder map sends H to -sign(H_4)e_4. Its first three
    columns therefore span H-perp. Basis signs need not be continuous between
    accepted outers; hold this basis fixed within each solve/retraction.
    """
    H = normalize_rows(H)
    v = H.copy()
    v[:, 3] += np.where(H[:, 3] >= 0, 1.0, -1.0)
    v = normalize_rows(v)
    return np.eye(4)[:, :3][None, :, :] - 2 * v[:, :, None] * v[:, None, :3]


@dataclass(frozen=True)
class PointChart:
    kind: str
    H: np.ndarray       # (np,4), base homogeneous representative
    T: np.ndarray       # (np,4,3), derivative of homogeneous representative
    anchor_idx: np.ndarray | None = None

    def retract(self, delta: np.ndarray) -> np.ndarray:
        delta = np.asarray(delta, dtype=np.float64)
        if delta.shape != (len(self.H), 3):
            raise ValueError("point chart delta must have shape (np,3)")
        H = self.H + np.einsum("nij,nj->ni", self.T, delta)
        return normalize_rows(H) if self.kind == "homogeneous" else H


def make_chart(X: np.ndarray, cameras: CameraState, kind: str,
               anchor_idx: np.ndarray | None = None) -> PointChart:
    """No invisible anchor adjustment: an invalid inverse-depth anchor raises.

    Anchors are frozen camera snapshots for this local chart, not optimization
    variables. The inverse-depth chart uses signed depth q_z in the anchor,
    retaining the Snavely negative-Z viewing convention.
    """
    X = np.asarray(X, dtype=np.float64)
    if X.ndim != 2 or X.shape[1] != 3 or not np.isfinite(X).all():
        raise ValueError("points must be finite (np,3)")
    n = len(X)
    if kind == "euclidean":
        T = np.zeros((n, 4, 3)); T[:, :3] = np.eye(3)
        return PointChart(kind, homogeneous_from_euclidean(X), T)
    if kind == "homogeneous":
        H = normalize_rows(homogeneous_from_euclidean(X))
        return PointChart(kind, H, householder_tangent(H))
    if kind != "inverse_depth":
        raise ValueError(f"unknown chart {kind}")
    if anchor_idx is None:
        raise ValueError("inverse_depth requires an explicit per-point anchor_idx")
    ai = np.asarray(anchor_idx, dtype=np.int64)
    if ai.shape != (n,) or np.any(ai < 0) or np.any(ai >= len(cameras.R)):
        raise ValueError("invalid anchor indices")
    Ra = cameras.R[ai].copy()
    ta = cameras.t[ai].copy()
    Ca = -np.einsum("nji,nj->ni", Ra, ta)
    q = np.einsum("nij,nj->ni", Ra, X) + ta
    if np.any(q[:, 2] == 0):
        raise ValueError("inverse-depth anchor lies on projection horizon")
    rho = 1 / q[:, 2]
    bearing = q * rho[:, None]
    H = np.column_stack((np.einsum("nji,nj->ni", Ra, bearing) + rho[:, None] * Ca, rho))
    T = np.zeros((n, 4, 3))
    T[:, :3, :2] = Ra.transpose(0, 2, 1)[:, :, :2]
    T[:, :3, 2] = Ca
    T[:, 3, 2] = 1
    return PointChart(kind, H, T, ai.copy())


def first_observation_anchors(cam_idx: np.ndarray, pt_idx: np.ndarray, npt: int) -> np.ndarray:
    """Deterministic run-everywhere default. Unobserved points use camera zero."""
    first = np.full(npt, len(pt_idx), dtype=np.int64)
    np.minimum.at(first, pt_idx, np.arange(len(pt_idx)))
    result = np.zeros(npt, dtype=np.int64)
    seen = first < len(pt_idx)
    result[seen] = cam_idx[first[seen]]
    return result


def skew(v: np.ndarray) -> np.ndarray:
    a = np.zeros((*v.shape[:-1], 3, 3), dtype=np.float64)
    a[..., 0, 1] = -v[..., 2]; a[..., 0, 2] = v[..., 1]
    a[..., 1, 0] = v[..., 2]; a[..., 1, 2] = -v[..., 0]
    a[..., 2, 0] = -v[..., 1]; a[..., 2, 1] = v[..., 0]
    return a


def project_jacobian(Y: np.ndarray, intr: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Exact SIMPLE_RADIAL projection, d pixel/dY, d pixel/d(f,k1,k2).

    k2 and its Jacobian column are fixed to zero. No projection-depth floor,
    finite-cost substitution, or cheirality rejection changes the objective.
    """
    if np.any(intr[:, 2] != 0):
        raise ValueError("SIMPLE_RADIAL projection requires k2=0")
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        x = -Y[:, :2] / Y[:, 2, None]
        r2 = np.einsum("ni,ni->n", x, x)
        f, k1 = intr[:, 0], intr[:, 1]
        distortion = 1 + k1 * r2
        pixel = (f * distortion)[:, None] * x
        dxy = np.zeros((len(Y), 2, 3))
        dxy[:, 0, 0] = -1 / Y[:, 2]; dxy[:, 1, 1] = -1 / Y[:, 2]
        dxy[:, :, 2] = -x / Y[:, 2, None]
        d_radial = f[:, None, None] * (distortion[:, None, None] * np.eye(2)
                        + 2 * k1[:, None, None] * x[:, :, None] * x[:, None, :])
        dY = d_radial @ dxy
        d_intr = np.zeros((len(Y), 2, 3))
        d_intr[:, :, 0] = distortion[:, None] * x
        d_intr[:, :, 1] = (f * r2)[:, None] * x
    return pixel, dY, d_intr


def observation_jacobians(cameras: CameraState, H: np.ndarray, T: np.ndarray,
                          cam_idx: np.ndarray, pt_idx: np.ndarray,
                          uv: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return residual (o,2), camera J (o,2,9), chart J (o,2,3), homogeneous Y."""
    R, t = cameras.R[cam_idx], cameras.t[cam_idx]
    h = H[pt_idx]
    Rh = np.einsum("nij,nj->ni", R, h[:, :3])
    Y = Rh + t * h[:, 3, None]
    pred, dY, d_intr = project_jacobian(Y, cameras.intrinsics[cam_idx])
    Jc = np.concatenate((dY @ (-skew(Rh)), dY * h[:, None, 3, None], d_intr), axis=2)
    Tc = R @ T[pt_idx, :3, :] + t[:, :, None] * T[pt_idx, None, 3, :]
    Jp = dY @ Tc
    return pred - uv, Jc, Jp, Y


def _track_sum(values: np.ndarray, pt_idx: np.ndarray, npt: int) -> np.ndarray:
    return np.bincount(pt_idx, weights=values, minlength=npt)


def conditional_point_solve(cameras: CameraState, X: np.ndarray,
                             cam_idx: np.ndarray, pt_idx: np.ndarray, uv: np.ndarray,
                             camera_step: np.ndarray, lam: float, *,
                             chart: str = "euclidean", anchor_idx: np.ndarray | None = None,
                             tau: float | None = None, chunk_size: int = 50000,
                             freeze_depth: np.ndarray | None = None) -> dict:
    """Solve (Jp'Jp + diag_damping) delta = -Jp'(r + Jc*camera_step).

    Point damping uses the champion's per-coordinate diagonal/trace-floor rule
    *in each chart*. This changes the physical damping metric across charts and
    must not be described as a pure nonlinear-retraction ablation. No fallback
    silently replaces a singular or nonfinite point solve; it raises instead.
    Optional inverse-depth constraints set delta_rho=0 and solve the remaining
    2x2 bearing block with the original three-coordinate damping unchanged.
    Report the active-coordinate residual; the constrained depth residual is a
    Lagrange reaction, not evidence that the constrained solve is inaccurate.
    """
    start = time.perf_counter()
    tau = lam if tau is None else tau
    if not (np.isfinite(lam) and np.isfinite(tau) and lam >= 0 and tau >= 0):
        raise ValueError("lam and tau must be finite and nonnegative")
    cameras.retract(camera_step)  # validate shape and masked coordinates
    if chart == "inverse_depth" and anchor_idx is None:
        anchor_idx = first_observation_anchors(cam_idx, pt_idx, len(X))
    point_chart = make_chart(X, cameras, chart, anchor_idx)
    npt = len(X)
    if freeze_depth is not None:
        freeze_depth = np.asarray(freeze_depth)
        if chart != "inverse_depth" or freeze_depth.dtype != np.bool_ or freeze_depth.shape != (npt,):
            raise ValueError("freeze_depth requires inverse_depth and a boolean (npt,) mask")
    V = np.zeros((npt, 3, 3)); b = np.zeros((npt, 3))
    score_init = np.longdouble(0)
    for start_o in range(0, len(cam_idx), chunk_size):
        sl = slice(start_o, start_o + chunk_size)
        ci, pi = cam_idx[sl], pt_idx[sl]
        r, Jc, Jp, _ = observation_jacobians(cameras, point_chart.H, point_chart.T, ci, pi, uv[sl])
        rc = r + np.einsum("nij,nj->ni", Jc, camera_step[ci])
        score_init += .5 * np.sum(r * r, dtype=np.longdouble)
        for a in range(3):
            b[:, a] -= _track_sum(np.einsum("ni,ni->n", Jp[:, :, a], rc), pi, npt)
            for c in range(a, 3):
                V[:, a, c] += _track_sum(np.einsum("ni,ni->n", Jp[:, :, a], Jp[:, :, c]), pi, npt)
    for a in range(3):
        for c in range(a):
            V[:, a, c] = V[:, c, a]
    diagonal = np.diagonal(V, axis1=1, axis2=2)
    floor = tau * np.sum(diagonal, axis=1) / 3
    floor = np.where(floor > 0, floor, 1e-32)
    damping = np.maximum(tau * diagonal, 1e-3 * floor[:, None])
    damped = V.copy()
    for a in range(3):
        damped[:, a, a] += damping[:, a]
    if not np.isfinite(damped).all() or not np.isfinite(b).all():
        raise FloatingPointError("Nonfinite point model")
    constrained = freeze_depth is not None and np.any(freeze_depth)
    if constrained:
        delta = np.zeros_like(b)
        free = ~freeze_depth
        if np.any(free):
            delta[free] = np.linalg.solve(damped[free], b[free, :, None])[..., 0]
        delta[freeze_depth, :2] = np.linalg.solve(damped[freeze_depth, :2, :2], b[freeze_depth, :2, None])[..., 0]
    else:
        # Preserve the original default and all-false control arithmetic exactly.
        delta = np.linalg.solve(damped, b[..., None])[..., 0]
    residual = np.einsum("nij,nj->ni", damped, delta) - b
    active_rhs = b
    reaction_norm = 0.
    if constrained:
        reaction_norm = float(np.linalg.norm(residual[freeze_depth, 2]))
        residual[freeze_depth, 2] = 0.
        active_rhs = b.copy()
        active_rhs[freeze_depth, 2] = 0.
    return {"chart": point_chart, "delta": delta, "H_candidate": point_chart.retract(delta),
            "point_normal": V, "point_damping": damping,
            "linear_relative_residual": float(np.linalg.norm(residual) / max(np.linalg.norm(active_rhs), 1e-300)),
            "frozen_depth_count": int(np.count_nonzero(freeze_depth)) if freeze_depth is not None else 0,
            "constraint_reaction_norm": reaction_norm,
            "score_init": float(score_init), "lambda": float(lam), "tau": float(tau),
            "cpu_solve_seconds": time.perf_counter() - start}


def evaluate_chart_step(cameras: CameraState, X: np.ndarray,
                        cam_idx: np.ndarray, pt_idx: np.ndarray, uv: np.ndarray,
                        camera_step: np.ndarray, lam: float, *,
                        chart: str = "euclidean", anchor_idx: np.ndarray | None = None,
                        tau: float | None = None, scene_radius: float | None = None,
                        chunk_size: int = 50000, freeze_depth: np.ndarray | None = None) -> dict:
    """Point solve and independent true/model scores; no candidate acceptance.

    A returned candidate still needs the main solver's full acceptance checks.
    Per-track model error arrays sum to full error via camera+point+remainder.
    CPU elapsed times are diagnostic costs, never champion solve-wall estimates.
    """
    start = time.perf_counter()
    result = conditional_point_solve(cameras, X, cam_idx, pt_idx, uv, camera_step, lam,
                                    chart=chart, anchor_idx=anchor_idx, tau=tau, chunk_size=chunk_size,
                                    freeze_depth=freeze_depth)
    pc = result["chart"]; Hnew = result["H_candidate"]; delta = result["delta"]
    updated_cameras = cameras.retract(camera_step)
    names = ("initial", "full", "camera_only", "point_only", "model_full", "model_camera", "model_point")
    totals = {name: np.longdouble(0) for name in names}
    prediction_sum = np.longdouble(0)
    by_track = {name: np.zeros(len(X)) for name in names}
    flips = {"full": 0, "camera_only": 0, "point_only": 0}
    invalid_projection = {name: 0 for name in ("initial", "full", "camera_only", "point_only")}
    for start_o in range(0, len(cam_idx), chunk_size):
        sl = slice(start_o, start_o + chunk_size)
        ci, pi = cam_idx[sl], pt_idx[sl]
        r, Jc, Jp, Y0 = observation_jacobians(cameras, pc.H, pc.T, ci, pi, uv[sl])
        yc = np.einsum("nij,nj->ni", Jc, camera_step[ci])
        yp = np.einsum("nij,nj->ni", Jp, delta[pi])
        jd = yc + yp
        prediction_sum -= np.sum(r * jd + .5 * jd * jd, dtype=np.longdouble)
        residuals = {"initial": r, "model_full": r + yc + yp,
                     "model_camera": r + yc, "model_point": r + yp}
        old_sign = np.sign(Y0[:, 2]) * np.sign(pc.H[pi, 3])
        for name, cs, hp in (("full", updated_cameras, Hnew),
                             ("camera_only", updated_cameras, pc.H),
                             ("point_only", cameras, Hnew)):
            Y = np.einsum("nij,nj->ni", cs.R[ci], hp[pi, :3]) + cs.t[ci] * hp[pi, 3, None]
            pred = project_jacobian(Y, cs.intrinsics[ci])[0]
            residuals[name] = pred - uv[sl]
            new_sign = np.sign(Y[:, 2]) * np.sign(hp[pi, 3])
            finite_point = (pc.H[pi, 3] != 0) & (hp[pi, 3] != 0)
            flips[name] += int(np.count_nonzero(finite_point & (new_sign != old_sign)))
        for name, residual in residuals.items():
            values = .5 * np.einsum("ni,ni->n", residual, residual)
            # Undefined projections count as infinity, never as omitted data.
            if name in invalid_projection:
                invalid_projection[name] += int(np.count_nonzero(~np.isfinite(values)))
            values = np.where(np.isfinite(values), values, np.inf)
            totals[name] += np.sum(values, dtype=np.longdouble)
            by_track[name] += _track_sum(values, pi, len(X))
    prediction = float(prediction_sum)
    decrease = float(totals["initial"] - totals["full"])
    model_error = {"full": by_track["full"] - by_track["model_full"],
                   "camera": by_track["camera_only"] - by_track["model_camera"],
                   "point": by_track["point_only"] - by_track["model_point"]}
    model_error["cross"] = model_error["full"] - model_error["camera"] - model_error["point"]
    Xnew = euclidean_from_homogeneous(Hnew)
    displacement = np.linalg.norm(Xnew - X, axis=1)
    # A valid projective point at infinity has no finite Euclidean displacement;
    # 0/0 in individual coordinates must not make the fling comparison false.
    displacement[Hnew[:, 3] == 0] = np.inf
    radius = scene_radius
    if radius is None:
        centers = cameras.centers()
        radius = float(np.max(np.linalg.norm(centers - np.mean(centers, axis=0), axis=1)))
    normalized_Hnew = normalize_rows(Hnew)
    result.update({"costs": {name: float(value) for name, value in totals.items()},
                   "pred": prediction, "true_decrease": decrease,
                   "rho": decrease / prediction if prediction != 0 else float("nan"),
                   "costs_per_track": by_track, "model_error_per_track": model_error,
                   "track_lengths": np.bincount(pt_idx, minlength=len(X)),
                   "scene_radius": float(radius),
                   "euclidean_displacement": displacement,
                   "fling_count": int(np.count_nonzero(displacement > radius)),
                   "exact_infinity_count": int(np.count_nonzero(Hnew[:, 3] == 0)),
                   "near_infinity_count": int(np.count_nonzero(np.abs(normalized_Hnew[:, 3]) <= 1e-12)),
                   "cheirality_flip_observations": flips,
                   "invalid_projection_observations": invalid_projection,
                   "cpu_total_seconds": time.perf_counter() - start})
    return result


def track_max_parallax(cameras: CameraState, X: np.ndarray,
                       cam_idx: np.ndarray, pt_idx: np.ndarray) -> np.ndarray:
    """Exact maximum pair angle per track in degrees; O(sum track_length^2).

    Diagnostic only. Geometric rays are X-C with no absolute-dot folding, and
    projection/cheirality is not used to drop any observation.
    """
    centers = cameras.centers()
    order = np.argsort(pt_idx, kind="stable")
    counts = np.bincount(pt_idx, minlength=len(X))
    offsets = np.concatenate(([0], np.cumsum(counts)))
    angles = np.zeros(len(X))
    for j in np.flatnonzero(counts >= 2):
        ci = cam_idx[order[offsets[j]:offsets[j + 1]]]
        rays = X[j] - centers[ci]
        if np.any(np.linalg.norm(rays, axis=1) == 0):
            angles[j] = np.nan
            continue
        rays = normalize_rows(rays)
        angles[j] = np.degrees(np.arccos(np.clip(np.min(rays @ rays.T), -1, 1)))
    return angles
