#!/usr/bin/env python3
"""Evaluate the preregistered rank-one residual tensor model on D8 states.

This is a fixed-trajectory FP64 diagnostic.  It does not optimize, alter, or
rerun the native trajectory.  See D8_TENSOR_SECANT_PROTOCOL.md.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np
from scipy.spatial.transform import Rotation


P = Path(__file__).resolve().parent
ROOT = P.parents[1]
CHART_DIR = ROOT / "research/eta2_research_20260912/charts"
sys.path.insert(0, str(CHART_DIR))
import reference as CHART  # noqa: E402

INPUT = Path("/workspace/bal/final-3068.txt")
EVIDENCE = Path("/workspace/eta2-wave6-evidence/d8-tensor")
CAPTURE = P / "d8-capture-manifest.json"
PROTOCOL = P / "D8_TENSOR_SECANT_PROTOCOL.md"
OUT = P / "d8-tensor-results.json"
CURRENT = (37, 40, 43, 47, 51)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def state_path(k: int) -> Path:
    if k == 52:
        return EVIDENCE / "endpoint.state"
    return EVIDENCE / f"state_it{k}.txt"


def state_tangent(base, target):
    """Return target = Retract(base, d), in the native left SO(3) chart."""
    cb, xb, _ = base
    ct, xt, _ = target
    relative = np.einsum("nij,nkj->nik", ct.R, cb.R)
    dw = Rotation.from_matrix(relative).as_rotvec()
    dc = np.zeros((len(cb.R), 9), dtype=np.float64)
    dc[:, :3] = dw
    dc[:, 3:6] = ct.t - cb.t
    dc[:, 6:9] = ct.intrinsics - cb.intrinsics
    if np.any(dc[:, 8] != 0):
        raise AssertionError("fixed k2 changed between states")
    return dc, xt - xb


def residual_and_jacobian(state, ci, pi, uv):
    camera, points, _ = state
    chart = CHART.make_chart(points, camera, "euclidean")
    return CHART.observation_jacobians(
        camera, chart.H, chart.T, ci, pi, uv)


def residual_only(state, ci, pi, uv):
    return residual_and_jacobian(state, ci, pi, uv)[0]


def sum_blocks(values: np.ndarray, index: np.ndarray, count: int) -> np.ndarray:
    """Stable-enough FP64 bincount by the last dimension."""
    return np.column_stack([
        np.bincount(index, weights=values[:, k], minlength=count)
        for k in range(values.shape[1])
    ])


def damping_metric(state, ci, pi, uv, tau: float):
    """Coherent FP64 Dp and diagonal of the point-damped Schur operator."""
    camera, points, _ = state
    nc, npt = len(camera.R), len(points)
    residual, jc9, jp, y = residual_and_jacobian(state, ci, pi, uv)
    jc = jc9[:, :, :8]

    # Point normal blocks and the exact native trace-floor damping metric.
    v = np.empty((npt, 3, 3), dtype=np.float64)
    for a in range(3):
        for b in range(a, 3):
            q = np.einsum("ni,ni->n", jp[:, :, a], jp[:, :, b])
            v[:, a, b] = np.bincount(pi, weights=q, minlength=npt)
            v[:, b, a] = v[:, a, b]
    vdiag = np.diagonal(v, axis1=1, axis2=2).copy()
    dp = np.maximum(vdiag, 1e-3 * (vdiag.sum(axis=1) / 3)[:, None])
    vlam = v.copy()
    vlam[:, np.arange(3), np.arange(3)] += tau * dp
    vinv = np.linalg.inv(vlam)

    # The BAL data has one observation per camera-point pair.  Keeping this
    # assertion explicit prevents the per-observation W terms below from
    # silently replacing the required per-pair aggregate.
    keys = ci.astype(np.int64) * npt + pi
    if len(np.unique(keys)) != len(keys):
        raise AssertionError("D8 Schur diagonal requires camera-point aggregation")

    udiag = sum_blocks(np.sum(jc * jc, axis=1), ci, nc)
    w = np.einsum("nra,nrb->nab", jc, jp)
    q = np.einsum("nai,nij,naj->na", w, vinv[pi], w)
    schur_diag = udiag - sum_blocks(q, ci, nc)

    # Same absolute intrinsics regularizer as KernelDampIntr9 (weight 1).
    counts = np.bincount(ci, minlength=nc)
    normalized_r2 = np.sum((y[:, :2] / y[:, 2, None]) ** 2, axis=1)
    average_r2 = np.maximum(
        np.bincount(ci, weights=normalized_r2, minlength=nc)
        / np.maximum(counts, 1), 1e-12)
    prior = np.zeros((nc, 8), dtype=np.float64)
    prior[:, 6] = np.where(
        counts > 0, 1 / (.5 * np.abs(camera.intrinsics[:, 0]) + 1e-3) ** 2, 0)
    prior[:, 7] = np.where(counts > 0, average_r2 ** 2, 0)
    schur_diag += prior
    if not np.isfinite(schur_diag).all() or np.any(schur_diag <= 0):
        raise FloatingPointError(
            f"invalid coherent Schur diagonal: min={schur_diag.min()}")
    return residual, jc, jp, dp, schur_diag


def d_inner(dc_a, dp_a, dc_b, dp_b, dcam, dpoint):
    return float(
        np.sum(dcam * dc_a[:, :8] * dc_b[:, :8], dtype=np.longdouble)
        + np.sum(dpoint * dp_a * dp_b, dtype=np.longdouble))


def cost(residual: np.ndarray) -> float:
    return float(.5 * np.sum(residual * residual, dtype=np.longdouble))


def analyze_transition(k, states, attempts, ci, pi, uv):
    previous, current, following = states[k - 1], states[k], states[k + 1]
    s_cam, s_point = state_tangent(current, previous)
    d_cam, d_point = state_tangent(current, following)

    r_prev = residual_only(previous, ci, pi, uv)
    r_next = residual_only(following, ci, pi, uv)
    r, jc, jp, dpoint, dcam = damping_metric(
        current, ci, pi, uv, attempts[str(k)]["tau"])
    js = (np.einsum("nra,na->nr", jc, s_cam[ci, :8])
          + np.einsum("nra,na->nr", jp, s_point[pi]))
    jd = (np.einsum("nra,na->nr", jc, d_cam[ci, :8])
          + np.einsum("nra,na->nr", jp, d_point[pi]))

    ss = d_inner(s_cam, s_point, s_cam, s_point, dcam, dpoint)
    dd = d_inner(d_cam, d_point, d_cam, d_point, dcam, dpoint)
    sd = d_inner(s_cam, s_point, d_cam, d_point, dcam, dpoint)
    if not (ss > 0 and dd > 0):
        raise FloatingPointError("nonpositive direction norm")
    secant_error = r_prev - r - js
    beta = (sd / ss) ** 2
    correction = secant_error * beta
    r_gn = r + jd
    r_tensor = r_gn + correction
    r_interp = r + js + secant_error

    # Retract both stored tangents and certify the state-coordinate conversion
    # in residual space rather than by comparing rotation matrices alone.
    cc, xc, meta = current
    reconstructed_previous = (cc.retract(s_cam), xc + s_point, meta)
    reconstructed_next = (cc.retract(d_cam), xc + d_point, meta)
    rp_reconstructed = residual_only(reconstructed_previous, ci, pi, uv)
    rn_reconstructed = residual_only(reconstructed_next, ci, pi, uv)
    tiny = np.finfo(np.float64).tiny
    prev_reconstruction = float(
        np.linalg.norm(rp_reconstructed - r_prev) / max(np.linalg.norm(r_prev), tiny))
    next_reconstruction = float(
        np.linalg.norm(rn_reconstructed - r_next) / max(np.linalg.norm(r_next), tiny))
    interpolation = float(
        np.linalg.norm(r_interp - r_prev) / max(np.linalg.norm(r_prev), tiny))

    change_norm = max(float(np.linalg.norm(r_next - r)), tiny)
    residual_error_gn = float(np.linalg.norm(r_next - r_gn) / change_norm)
    residual_error_tensor = float(np.linalg.norm(r_next - r_tensor) / change_norm)
    c0, c1 = cost(r), cost(r_next)
    actual_decrease = c0 - c1
    scale = max(abs(actual_decrease), tiny)
    c_gn, c_tensor = cost(r_gn), cost(r_tensor)
    predicted_gn, predicted_tensor = c0 - c_gn, c0 - c_tensor
    cost_error_gn = abs(c_gn - c1) / scale
    cost_error_tensor = abs(c_tensor - c1) / scale
    obs_energy = np.sum(correction * correction, axis=1)
    top = min(200, len(obs_energy))
    top_fraction = float(
        np.partition(obs_energy, len(obs_energy) - top)[-top:].sum()
        / max(obs_energy.sum(), tiny))

    del jc, jp, dpoint, dcam
    return {
        "outer": k,
        "tau": attempts[str(k)]["tau"],
        "controller": attempts[str(k)],
        "cost_current": c0,
        "cost_next": c1,
        "actual_decrease": actual_decrease,
        "d_metric": {
            "previous_backward_norm": ss ** .5,
            "next_norm": dd ** .5,
            "backward_next_cosine": sd / np.sqrt(ss * dd),
            "forward_previous_next_cosine": -sd / np.sqrt(ss * dd),
            "next_to_previous_norm_ratio": np.sqrt(dd / ss),
            "tensor_projection_beta": beta,
        },
        "residual_change_error": {
            "gauss_newton": residual_error_gn,
            "tensor": residual_error_tensor,
            "tensor_to_gauss_newton": residual_error_tensor / residual_error_gn,
        },
        "normalized_cost_prediction_error": {
            "gauss_newton": cost_error_gn,
            "tensor": cost_error_tensor,
            "tensor_to_gauss_newton": cost_error_tensor / cost_error_gn,
        },
        "prediction": {
            "gauss_newton_decrease": predicted_gn,
            "tensor_decrease": predicted_tensor,
            "gauss_newton_sign_correct": bool((predicted_gn >= 0) == (actual_decrease >= 0)),
            "tensor_sign_correct": bool((predicted_tensor >= 0) == (actual_decrease >= 0)),
        },
        "tensor_correction_top200_observation_energy_fraction": top_fraction,
        "certificates": {
            "previous_state_reconstruction_relative_residual": prev_reconstruction,
            "next_state_reconstruction_relative_residual": next_reconstruction,
            "tensor_secant_interpolation_relative_residual": interpolation,
        },
    }


def main():
    started = time.monotonic()
    capture = json.loads(CAPTURE.read_text())
    if capture["protocol_sha256"] != sha256(PROTOCOL):
        raise AssertionError("protocol changed after capture")
    for key, record in capture["files"]["states"].items():
        if sha256(Path(record["path"])) != record["sha256"]:
            raise AssertionError(f"state hash mismatch: {key}")
    if sha256(EVIDENCE / "endpoint.state") != capture["files"]["endpoint"]["sha256"]:
        raise AssertionError("endpoint hash mismatch")

    ci, pi, uv, dims = CHART.load_observations(INPUT)
    needed = sorted({v + o for v in CURRENT for o in (-1, 0, 1)})
    states = {k: CHART.load_prisms01(state_path(k)) for k in needed}
    if any(s[2] != dims for s in states.values()):
        raise AssertionError("state/input dimensions disagree")

    rows = []
    for k in CURRENT:
        row = analyze_transition(
            k, states, capture["replay"]["accepted_attempts"], ci, pi, uv)
        rows.append(row)
        print(json.dumps({
            "outer": k,
            "residual_ratio": row["residual_change_error"]["tensor_to_gauss_newton"],
            "cost_ratio": row["normalized_cost_prediction_error"]["tensor_to_gauss_newton"],
            "beta": row["d_metric"]["tensor_projection_beta"],
        }), flush=True)

    residual_ratios = np.array([
        row["residual_change_error"]["tensor_to_gauss_newton"] for row in rows])
    cost_ratios = np.array([
        row["normalized_cost_prediction_error"]["tensor_to_gauss_newton"] for row in rows])
    gn_signs = sum(row["prediction"]["gauss_newton_sign_correct"] for row in rows)
    tensor_signs = sum(row["prediction"]["tensor_sign_correct"] for row in rows)
    cert_max = max(max(row["certificates"].values()) for row in rows)
    gates = {
        "residual_20pct_better_at_least_3": int(np.sum(residual_ratios <= .8)) >= 3,
        "residual_median_better": float(np.median(residual_ratios)) < 1,
        "cost_20pct_better_at_least_3": int(np.sum(cost_ratios <= .8)) >= 3,
        "cost_median_better": float(np.median(cost_ratios)) < 1,
        "sign_not_worse": tensor_signs >= gn_signs,
        "no_residual_blowup_over_2x": bool(np.all(residual_ratios <= 2)),
        "no_cost_blowup_over_2x": bool(np.all(cost_ratios <= 2)),
        "all_certificates_below_1e-9": cert_max < 1e-9,
    }
    result = {
        "schema": 1,
        "protocol": str(PROTOCOL),
        "protocol_sha256": sha256(PROTOCOL),
        "capture_manifest": str(CAPTURE),
        "capture_manifest_sha256": sha256(CAPTURE),
        "analysis_tool_sha256": None,
        "input_sha256": sha256(INPUT),
        "arithmetic": "coherent CPU FP64 residuals/Jacobians/Schur diagonal",
        "rows": rows,
        "summary": {
            "median_residual_tensor_to_gn": float(np.median(residual_ratios)),
            "residual_20pct_better_count": int(np.sum(residual_ratios <= .8)),
            "median_cost_tensor_to_gn": float(np.median(cost_ratios)),
            "cost_20pct_better_count": int(np.sum(cost_ratios <= .8)),
            "gauss_newton_correct_sign_count": int(gn_signs),
            "tensor_correct_sign_count": int(tensor_signs),
            "max_certificate_error": cert_max,
            "gates": gates,
            "full_tensor_step_earned": all(gates.values()),
            "elapsed_seconds": time.monotonic() - started,
        },
    }
    # Hash the exact source that produced the artifact, then write atomically.
    result["analysis_tool_sha256"] = sha256(Path(__file__))
    temporary = OUT.with_suffix(".tmp")
    temporary.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    temporary.replace(OUT)
    print(json.dumps(result["summary"], indent=2), flush=True)


if __name__ == "__main__":
    main()
