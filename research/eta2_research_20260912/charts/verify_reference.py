#!/usr/bin/env python3
"""Finite-difference, independent normal-solve, and singularity checks.

These validate an experimental numerical implementation, not a BA win. All
fixtures are synthetic and deterministic; no measured witness is tuned here.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import tempfile
import struct

import numpy as np
import scipy
from scipy.spatial.transform import Rotation

from reference import (CameraState, PointChart, conditional_point_solve,
                       evaluate_chart_step, euclidean_from_homogeneous,
                       first_observation_anchors, homogeneous_from_euclidean,
                       householder_tangent, load_prisms01, make_chart,
                       normalize_rows, observation_jacobians, project_jacobian,
                       track_max_parallax, verify_frozen_baseline)


def relative_error(a, b):
    return float(np.linalg.norm(a - b) / max(np.linalg.norm(a), np.linalg.norm(b), 1e-12))


def independent_residual(c, H, ci, pi, uv):
    """Direct scalar projection, separate from analytic projection helper."""
    out = np.zeros_like(uv)
    for o, (i, j) in enumerate(zip(ci, pi)):
        q = c.R[i] @ H[j, :3] + c.t[i] * H[j, 3]
        xp, yp = -q[0] / q[2], -q[1] / q[2]
        r2 = xp * xp + yp * yp
        f, k1, _ = c.intrinsics[i]
        out[o] = [f * (1 + k1 * r2) * xp - uv[o, 0],
                  f * (1 + k1 * r2) * yp - uv[o, 1]]
    return out


def fixture():
    rng = np.random.default_rng(20260912)
    nc, npt = 4, 9
    R = Rotation.from_rotvec(rng.normal(size=(nc, 3)) * .15).as_matrix()
    C = rng.normal(size=(nc, 3)) * .7
    t = -np.einsum("nij,nj->ni", R, C)
    intr = np.column_stack((rng.uniform(500, 1200, nc), rng.uniform(-.12, .12, nc), np.zeros(nc)))
    cams = CameraState(R, t, intr)
    X = rng.normal(size=(npt, 3)); X[:, 2] -= 7
    ci = np.tile(np.arange(nc), npt)
    pi = np.repeat(np.arange(npt), nc)
    h = homogeneous_from_euclidean(X)
    uv = independent_residual(cams, h, ci, pi, np.zeros((len(ci), 2)))
    uv += rng.normal(size=uv.shape) * 1.3
    d = rng.normal(size=(nc, 9)) * .003
    d[:, 6] *= 100; d[:, 7] *= .1; d[:, 8] = 0
    return rng, cams, X, ci, pi, uv, d


def finite_difference_checks(cams, X, ci, pi, uv):
    anchors = first_observation_anchors(ci, pi, len(X))
    out = {}
    eps = 2e-6
    for kind in ("euclidean", "homogeneous", "inverse_depth"):
        pc = make_chart(X, cams, kind, anchors)
        r, Jc, Jp, _ = observation_jacobians(cams, pc.H, pc.T, ci, pi, uv)
        assert relative_error(r, independent_residual(cams, pc.H, ci, pi, uv)) < 1e-12
        camera_errors, point_errors = [], []
        for a in range(8):
            d = np.zeros((len(cams.R), 9)); d[:, a] = eps
            fd = (independent_residual(cams.retract(d), pc.H, ci, pi, uv)
                  - independent_residual(cams.retract(-d), pc.H, ci, pi, uv)) / (2 * eps)
            camera_errors.append(relative_error(fd, Jc[:, :, a]))
        for a in range(3):
            dp = np.zeros((len(X), 3)); dp[:, a] = eps
            fd = (independent_residual(cams, pc.retract(dp), ci, pi, uv)
                  - independent_residual(cams, pc.retract(-dp), ci, pi, uv)) / (2 * eps)
            point_errors.append(relative_error(fd, Jp[:, :, a]))
        assert max(camera_errors) < 2e-7, (kind, camera_errors)
        assert max(point_errors) < 2e-7, (kind, point_errors)
        assert np.all(Jc[:, :, 8] == 0)
        out[kind] = {"camera_columns_relative_error": camera_errors,
                     "point_columns_relative_error": point_errors}
    return out


def geometric_checks(rng, cams, X, ci, pi, uv):
    out = {}
    unit = normalize_rows(rng.normal(size=(1000, 4)))
    unit = np.concatenate((unit, np.eye(4), -np.eye(4)))
    B = householder_tangent(unit)
    ortho = float(np.max(np.abs(B.transpose(0, 2, 1) @ B - np.eye(3))))
    tangent = float(np.max(np.abs(np.einsum("ni,nij->nj", unit, B))))
    assert ortho < 2e-15 and tangent < 2e-15
    pc = PointChart("homogeneous", unit, B)
    delta = rng.normal(size=(len(unit), 3)) * 7
    new = pc.retract(delta)
    angle = np.arccos(np.clip(np.einsum("ni,ni->n", unit, new), -1, 1))
    expected = np.arctan(np.linalg.norm(delta, axis=1))
    assert np.max(abs(angle - expected)) < 1e-13
    out["householder"] = {"orthonormality_max_abs": ortho, "tangent_max_abs": tangent,
                          "angle_identity_max_abs": float(np.max(abs(angle - expected)))}

    # All charts represent the exact same original points and camera Jacobian.
    base = make_chart(X, cams, "euclidean")
    r0, Jc0, Jp0, _ = observation_jacobians(cams, base.H, base.T, ci, pi, uv)
    anchors = first_observation_anchors(ci, pi, len(X))
    for kind in ("homogeneous", "inverse_depth"):
        chart = make_chart(X, cams, kind, anchors)
        r, Jc, Jp, _ = observation_jacobians(cams, chart.H, chart.T, ci, pi, uv)
        H, T = chart.H, chart.T
        G = (T[:, :3] * H[:, 3, None, None] - H[:, :3, None] * T[:, 3, None, :]) / H[:, 3, None, None]**2
        coordinate_chain_error = relative_error(Jp, Jp0 @ G[pi])
        assert coordinate_chain_error < 2e-13
        assert relative_error(r, r0) < 2e-12
        assert relative_error(Jc, Jc0) < 2e-13
        assert relative_error(euclidean_from_homogeneous(H), X) < 2e-15
        out[kind] = {"camera_jacobian_invariance_error": relative_error(Jc, Jc0),
                     "point_coordinate_chain_error": coordinate_chain_error}

    # Explicit S3 counterexample: tiny angular motion can cross infinity.
    unit = normalize_rows(np.array([[0., 0., 1., 1e-3]]))
    basis = householder_tangent(unit)
    # Tangent in depth plane, then select a finite target with w about 1e-12.
    desired = normalize_rows(np.array([[0., 0., 1., 1e-12]]))
    tangent_step = desired / np.einsum("ni,ni->n", unit, desired)[:, None] - unit
    delta = np.einsum("nij,ni->nj", basis, tangent_step)
    new = PointChart("homogeneous", unit, basis).retract(delta)
    oldX, newX = euclidean_from_homogeneous(unit), euclidean_from_homogeneous(new)
    jump = float(np.linalg.norm(newX - oldX))
    assert jump > 1e11 and np.linalg.norm(delta) < .002
    out["s3_euclidean_fling_counterexample"] = {"tangent_norm": float(np.linalg.norm(delta)),
                                               "euclidean_displacement": jump}

    # Infinity is regular if projected depth is nonzero; the image horizon is not.
    intr = np.array([[1000., .01, 0.]])
    regular = np.array([[.1, .2, -1.]])
    assert np.isfinite(project_jacobian(regular, intr)[0]).all()
    horizon = np.array([[1., 0., 0.]])
    assert not np.isfinite(project_jacobian(horizon, intr)[0]).all()
    out["projection_singularity"] = {"finite_at_regular_infinite_direction": True,
                                    "singular_at_image_horizon": True}

    # S3 alone cannot add cheirality information to the unchanged pixel objective.
    q = np.array([[.2, -.1, -1.]])
    front, behind = project_jacobian(q, intr)[0], project_jacobian(-q, intr)[0]
    assert np.array_equal(front, behind)
    out["cheirality_blindness"] = {"opposite_camera_rays_have_identical_pixels": True}

    # The exact analytic Jacobian also works at homogeneous infinity w=0.
    Hi = normalize_rows(np.array([[.1, -.2, -1., 0.]]))
    Ti = householder_tangent(Hi)
    local_pc = PointChart("homogeneous", Hi, Ti)
    c1 = CameraState(np.eye(3)[None], np.array([[.4, -.1, .2]]), intr)
    one = np.array([0]); uv0 = np.zeros((1, 2))
    _, _, Jp, _ = observation_jacobians(c1, Hi, Ti, one, one, uv0)
    fd_err = []
    for a in range(3):
        d = np.zeros((1, 3)); d[:, a] = 1e-6
        fd = (independent_residual(c1, local_pc.retract(d), one, one, uv0)
              - independent_residual(c1, local_pc.retract(-d), one, one, uv0)) / 2e-6
        fd_err.append(relative_error(fd, Jp[:, :, a]))
    assert max(fd_err) < 1e-7
    out["at_infinity_point_jacobian_relative_errors"] = fd_err
    return out


def conditional_solve_checks(cams, X, ci, pi, uv, dc):
    out = {}
    for kind in ("euclidean", "homogeneous", "inverse_depth"):
        result = evaluate_chart_step(cams, X, ci, pi, uv, dc, .1, chart=kind, chunk_size=7)
        pc = result["chart"]
        r, Jc, Jp, _ = observation_jacobians(cams, pc.H, pc.T, ci, pi, uv)
        rc = r + np.einsum("nij,nj->ni", Jc, dc[ci])
        errors = []
        # Independent augmented least-squares solve, no normal equations.
        for j in range(len(X)):
            rows = pi == j
            A = np.vstack((Jp[rows].reshape(-1, 3), np.diag(np.sqrt(result["point_damping"][j]))))
            b = np.concatenate((-rc[rows].ravel(), np.zeros(3)))
            expected = np.linalg.lstsq(A, b, rcond=None)[0]
            errors.append(relative_error(expected, result["delta"][j]))
        assert max(errors) < 1e-11
        full_r = independent_residual(cams.retract(dc), result["H_candidate"], ci, pi, uv)
        true_cost = .5 * np.sum(full_r * full_r)
        assert abs(true_cost - result["costs"]["full"]) / max(true_cost, 1) < 1e-12
        jd = np.einsum("nij,nj->ni", Jc, dc[ci]) + np.einsum("nij,nj->ni", Jp, result["delta"][pi])
        pred = -np.sum(r * jd) - .5 * np.sum(jd * jd)
        assert abs(pred - result["pred"]) / max(1, abs(pred)) < 1e-12
        e = result["model_error_per_track"]
        assert np.max(abs(e["full"] - e["camera"] - e["point"] - e["cross"])) < 1e-14
        assert result["linear_relative_residual"] < 1e-13
        out[kind] = {"augmented_lstsq_max_relative_error": max(errors),
                     "normal_equation_relative_residual": result["linear_relative_residual"],
                     "true_cost": true_cost, "prediction": pred, "rho": result["rho"]}
    # Exact undamped GN tangents are covariant; diagonal damping generally is not.
    eu = conditional_point_solve(cams, X, ci, pi, uv, dc, 0, chart="euclidean")
    for kind in ("homogeneous", "inverse_depth"):
        ans = conditional_point_solve(cams, X, ci, pi, uv, dc, 0, chart=kind)
        h, T = ans["chart"].H, ans["chart"].T
        G = (T[:, :3] * h[:, 3, None, None] - h[:, :3, None] * T[:, 3, None, :]) / h[:, 3, None, None]**2
        tangent_X = np.einsum("nij,nj->ni", G, ans["delta"])
        err = relative_error(tangent_X, eu["delta"])
        assert err < 1e-10
        out[kind]["undamped_physical_tangent_invariance_error"] = err
    return out


def adapter_checks(cams, X, ci):
    with tempfile.TemporaryDirectory(prefix="eta2-chart-test-") as temp:
        path = Path(temp) / "state.bin"
        with path.open("wb") as f:
            f.write(b"PRISMS01"); f.write(struct.pack("<QQQ", len(cams.R), len(X), len(ci)))
            for a in (cams.R, cams.t, X, cams.intrinsics.T):
                np.asarray(a, dtype="<f8").tofile(f)
        c, p, dims = load_prisms01(path)
        assert np.array_equal(c.R, cams.R) and np.array_equal(c.t, cams.t)
        assert np.array_equal(c.intrinsics, cams.intrinsics) and np.array_equal(p, X)
        assert dims == (len(cams.R), len(X), len(ci))
    # Analytically known 90-degree parallax.
    test_c = CameraState(np.tile(np.eye(3), (2, 1, 1)), np.array([[1., 0, 0], [0, 1., 0]]),
                         np.array([[1., 0, 0], [1., 0, 0]]))
    angle = track_max_parallax(test_c, np.zeros((1, 3)), np.array([0, 1]), np.array([0, 0]))
    assert abs(angle[0] - 90) < 1e-12
    return {"prisms01_roundtrip_bit_exact": True, "known_parallax_degrees": float(angle[0])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("verification.json"))
    args = parser.parse_args()
    rng, cams, X, ci, pi, uv, dc = fixture()
    baseline = verify_frozen_baseline()
    report = {"status": "reference implementation verified; no BAL performance verdict",
              "environment": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__},
              "baseline": baseline,
              "finite_differences": finite_difference_checks(cams, X, ci, pi, uv),
              "geometry": geometric_checks(rng, cams, X, ci, pi, uv),
              "conditional_solve": conditional_solve_checks(cams, X, ci, pi, uv, dc),
              "adapters": adapter_checks(cams, X, ci),
              "source_sha256": hashlib.sha256(Path(__file__).with_name("reference.py").read_bytes()).hexdigest()}
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"status": report["status"], "output": str(args.output),
                      "finite_difference_max_relative_error": max(max(v["camera_columns_relative_error"] + v["point_columns_relative_error"])
                                                                 for v in report["finite_differences"].values()),
                      "augmented_lstsq_max_relative_error": max(v["augmented_lstsq_max_relative_error"] for v in report["conditional_solve"].values()),
                      "s3_fling_counterexample": report["geometry"]["s3_euclidean_fling_counterexample"]}, indent=2))


if __name__ == "__main__":
    main()
