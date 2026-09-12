#!/usr/bin/env python3
"""Fixed-state focal/depth chart diagnostic registered in D7."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import time

import numpy as np
import scipy.linalg as la
import scipy.sparse as sp

P = Path(__file__).resolve().parent
RESEARCH = P.parent
W2 = RESEARCH / "eta2_wave2"
W3 = RESEARCH / "eta2_wave3"
CORE = RESEARCH / "eta2_research_20260912"
PROTOCOL = P / "D7_INTRINSICS_CHART_PROTOCOL.md"
BAL = Path("/workspace/bal/venice-52.txt")

sys.path[:0] = [str(W2), str(CORE / "analysis"), str(CORE / "coarse")]
import lossless_float_archive as FA
from audit_capture import load_capture_state, CHART
from spectrum import point_qr, point_inverse


def sha(path: Path) -> str:
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def write(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True,
                               allow_nan=False) + "\n")


def read_array(path: Path, shape):
    result = np.fromfile(path, "<f8")
    if result.size != int(np.prod(shape)):
        raise ValueError((path, result.size, shape))
    result = result.reshape(shape)
    if not np.isfinite(result).all():
        raise ValueError(f"nonfinite array {path}")
    return result


def aggregate(values, ids, count):
    flat = values.reshape(len(values), -1)
    result = np.column_stack([
        np.bincount(ids, weights=flat[:, column], minlength=count)
        for column in range(flat.shape[1])])
    return result.reshape((count,) + values.shape[1:])


def block_diagonal(blocks):
    count, width, _ = blocks.shape
    result = np.zeros((count * width, count * width))
    for index, block in enumerate(blocks):
        sl = slice(width * index, width * (index + 1))
        result[sl, sl] = block
    return result


def validate_members(folder: Path, expected, prefix=""):
    required = ("metadata.txt", "E.f64", "Cdiag.f64", "eta2_raw_scaled.f64",
                "R_state.f64", "t_state.f64", "X_state.f64", "intr_state.f64")
    actual = {}
    for name in required:
        key = prefix + name
        digest = sha(folder / name)
        if expected[key] != digest:
            raise ValueError(f"member hash mismatch: {key}")
        actual[key] = digest
    return actual


def chart_transform(camera, kind: str):
    """Block tangent map: physical additive delta = T * chart delta."""
    nc = len(camera.R)
    T = np.broadcast_to(np.eye(8), (nc, 8, 8)).copy()
    if kind == "additive":
        return T
    f = camera.intrinsics[:, 0]
    tz = camera.t[:, 2]
    if np.any(~np.isfinite(f)) or np.any(f <= 0):
        raise ValueError("ratio charts require positive focal lengths")
    T[:, 5:7, 5:7] = 0
    if kind == "ratio-linear":
        T[:, 5, 5] = f
        T[:, 5, 6] = tz / f
        T[:, 6, 6] = 1
    elif kind == "ratio-log":
        T[:, 5, 5] = f
        T[:, 5, 6] = tz
        T[:, 6, 6] = f
    else:
        raise ValueError(kind)
    return T


def chart_retract(camera, delta_chart, kind: str):
    """Use the registered nonlinear camera chart and existing SO(3) retraction."""
    if kind == "additive":
        physical = np.zeros((len(camera.R), 9))
        physical[:, :8] = delta_chart
        return camera.retract(physical)
    result_physical = np.zeros((len(camera.R), 9))
    # Rotation, transverse translation and k1 retain their additive semantics.
    result_physical[:, :5] = delta_chart[:, :5]
    result_physical[:, 7] = delta_chart[:, 7]
    result = camera.retract(result_physical)
    old_f = camera.intrinsics[:, 0]
    old_q = camera.t[:, 2] / old_f
    new_q = old_q + delta_chart[:, 5]
    if kind == "ratio-linear":
        new_f = old_f + delta_chart[:, 6]
    elif kind == "ratio-log":
        new_f = old_f * np.exp(delta_chart[:, 6])
    else:
        raise ValueError(kind)
    if np.any(~np.isfinite(new_f)) or np.any(new_f <= 0):
        raise FloatingPointError("chart retraction produced invalid focal length")
    t = result.t.copy()
    intrinsics = result.intrinsics.copy()
    t[:, 2] = new_q * new_f
    intrinsics[:, 0] = new_f
    return CHART.CameraState(result.R, t, intrinsics)


def build_model(folder: Path, ci, pi, uv):
    camera, X, meta = load_capture_state(folder)
    nc, npt, nobs = len(camera.R), len(X), len(ci)
    if (nc, npt, nobs) != tuple(int(meta[key]) for key in
                                  ("ncam", "npt", "nobs")):
        raise ValueError("capture dimensions disagree")
    E_capture = read_array(folder / "E.f64", (nc, 9))[:, :8]
    Cdiag = read_array(folder / "Cdiag.f64", (npt, 3))
    raw_capture = -read_array(folder / "eta2_raw_scaled.f64", (nc, 9))[:, :8]
    point_chart = CHART.make_chart(X, camera, "euclidean")
    residual, Jc9, Jp, Y = CHART.observation_jacobians(
        camera, point_chart.H, point_chart.T, ci, pi, uv)
    Jc = Jc9[:, :, :8]

    tracks = np.bincount(pi, minlength=npt)
    point_floor = np.maximum(Cdiag,
                             .001 * np.maximum(Cdiag.mean(axis=1), 1e-32)[:, None])
    multiplier = (np.where(tracks >= 6, .3, 1.)
                  if meta.get("static_replay", 0) else np.ones(npt))
    point_diagonal = meta["tau"] * multiplier[:, None] * point_floor
    _, inverse_R, _ = point_qr(Jp, pi, point_diagonal)

    keys = ci.astype(np.int64) * npt + pi
    unique, inverse = np.unique(keys, return_inverse=True)
    pair_camera = (unique // npt).astype(np.int64)
    pair_point = (unique % npt).astype(np.int64)
    cross = aggregate(np.einsum("nri,nrj->nij", Jc, Jp),
                      inverse, len(unique))
    rows = np.broadcast_to(pair_camera[:, None, None] * 8
                           + np.arange(8)[None, :, None], cross.shape).ravel()
    cols = np.broadcast_to(pair_point[:, None, None] * 3
                           + np.arange(3)[None, None, :], cross.shape).ravel()
    W = sp.coo_matrix((cross.ravel(), (rows, cols)),
                      shape=(8*nc, 3*npt)).tocsr()
    Rinv = sp.bsr_matrix((inverse_R, np.arange(npt), np.arange(npt+1)),
                         shape=(3*npt, 3*npt)).tocsr()
    factor = W @ Rinv

    camera_normal = aggregate(np.einsum("nri,nrj->nij", Jc, Jc), ci, nc)
    camera_gradient = aggregate(np.einsum("nri,nr->ni", Jc, residual), ci, nc)
    point_gradient = aggregate(np.einsum("nri,nr->ni", Jp, residual), pi, npt)
    counts = np.bincount(ci, minlength=nc)
    normalized_r2 = np.sum((Y[:, :2] / Y[:, 2, None]) ** 2, axis=1)
    average_r2 = np.maximum(np.bincount(ci, weights=normalized_r2,
                                        minlength=nc) / np.maximum(counts, 1), 1e-12)
    prior = np.zeros((nc, 8))
    prior[:, 6] = np.where(counts > 0,
                           1 / (.5*np.abs(camera.intrinsics[:, 0]) + 1e-3)**2, 0)
    prior[:, 7] = np.where(counts > 0, average_r2**2, 0)
    blocks = camera_normal.copy()
    blocks[:, np.arange(8), np.arange(8)] += prior
    S = block_diagonal(blocks) - (factor @ factor.T).toarray()
    S = .5 * (S + S.T)
    point_inverse_gradient = point_inverse(inverse_R, point_gradient)
    b = -camera_gradient.reshape(-1) + W @ point_inverse_gradient.reshape(-1)
    E_coherent = 1 / np.sqrt(np.diag(S).reshape(nc, 8))
    return dict(camera=camera, X=X, meta=meta, E_capture=E_capture,
                E_coherent=E_coherent, raw_capture=raw_capture, residual=residual,
                Jc=Jc, Jp=Jp, S=S, b=np.asarray(b), W=W, inverse_R=inverse_R,
                point_gradient=point_gradient, counts=counts,
                point_diagonal=point_diagonal,
                score=float(.5*np.sum(residual*residual, dtype=np.longdouble)))


def evaluate(model, delta_chart, physical_delta, kind):
    camera, X = model["camera"], model["X"]
    ci, pi, uv = model["ci"], model["pi"], model["uv"]
    rhs_point = -model["point_gradient"].reshape(-1) - model["W"].T @ physical_delta.reshape(-1)
    dp = point_inverse(model["inverse_R"], np.asarray(rhs_point).reshape(len(X), 3))
    linear = (model["residual"]
              + np.einsum("nri,ni->nr", model["Jc"], physical_delta[ci])
              + np.einsum("nri,ni->nr", model["Jp"], dp[pi]))
    pred = model["score"] - float(.5*np.sum(linear*linear, dtype=np.longdouble))
    candidate_camera = chart_retract(camera, delta_chart, kind)
    H = np.column_stack((X + dp, np.ones(len(X))))
    tangent = np.zeros((len(X), 4, 3)); tangent[:, :3] = np.eye(3)
    candidate_residual = CHART.observation_jacobians(
        candidate_camera, H, tangent, ci, pi, uv)[0]
    candidate_cost = float(.5*np.sum(candidate_residual*candidate_residual,
                                      dtype=np.longdouble))
    decrease = model["score"] - candidate_cost
    return dict(prediction=pred, true_decrease=decrease,
                rho=decrease/pred if pred != 0 else None,
                candidate_cost=candidate_cost,
                point_step_norm=float(np.linalg.norm(dp)),
                linear_model_cost=float(.5*np.sum(linear*linear,
                                                   dtype=np.longdouble)))


def chart_result(model, kind):
    camera, nc = model["camera"], len(model["camera"].R)
    Tblocks = chart_transform(camera, kind)
    T = block_diagonal(Tblocks)
    Sy = T.T @ model["S"] @ T
    Sy = .5 * (Sy + Sy.T)
    by = T.T @ model["b"]
    diagonal = np.diag(Sy)
    if np.any(diagonal <= 0):
        raise ValueError(f"nonpositive chart Schur diagonal: {kind}")
    Ey = 1 / np.sqrt(diagonal)
    A = Sy * Ey[:, None] * Ey[None, :]
    A.flat[::len(A)+1] += model["meta"]["lambda"]
    L = la.cholesky(A, lower=True, check_finite=True)
    z = la.cho_solve((L, True), Ey * by)
    relative_residual = float(np.linalg.norm(A @ z - Ey*by)
                              / max(np.linalg.norm(Ey*by), 1e-300))
    radius = model["meta"]["radius"]
    raw_norm = float(np.linalg.norm(z))
    clip = min(1., radius / max(raw_norm, np.finfo(float).tiny))
    delta_chart = (Ey * (clip*z)).reshape(nc, 8)
    physical = np.einsum("nij,nj->ni", Tblocks, delta_chart)
    raw_chart = (Ey * z).reshape(nc, 8)
    raw_physical = np.einsum("nij,nj->ni", Tblocks, raw_chart)
    energy = np.sum(z.reshape(nc, 8)**2, axis=1)

    local = []
    for camera_id in range(nc):
        sl = slice(8*camera_id, 8*(camera_id+1))
        block = Sy[sl, sl]
        scale = 1/np.sqrt(np.diag(block))
        scaled = block * scale[:, None] * scale[None, :]
        values, vectors = la.eigh(.5*(scaled+scaled.T))
        weak = vectors[:, 0]
        local.append(dict(
            camera=camera_id,
            condition=float(values[-1]/values[0]) if values[0] > 0 else None,
            eigenvalues=values.tolist(),
            weak_q_or_tz_loading=float(weak[5]**2),
            weak_f_or_logf_loading=float(weak[6]**2),
            weak_pair_loading=float(weak[5]**2+weak[6]**2),
            max_weak_pair_coordinate_loading=float(max(weak[5]**2, weak[6]**2)),
            normalized_pair_correlation=float(scaled[5, 6])))

    # Re-express the identical captured physical direction in this chart metric.
    captured_physical = model["E_capture"] * model["raw_capture"]
    captured_chart = np.linalg.solve(Tblocks, captured_physical[..., None])[..., 0]
    captured_z = captured_chart / Ey.reshape(nc, 8)
    captured_norm = float(np.linalg.norm(captured_z))
    captured_clip = min(1., radius/max(captured_norm, np.finfo(float).tiny))
    top = int(np.argmax(energy))
    healthy = np.ones(nc, dtype=bool); healthy[34] = False
    return dict(kind=kind, transform_blocks=Tblocks,
                E=Ey.reshape(nc, 8), scaled_operator=A,
                exact_scaled_step=z.reshape(nc, 8),
                exact_raw_physical=raw_physical,
                exact_raw_radius_ratio=raw_norm/radius,
                exact_clip_factor=clip,
                exact_top_camera=top,
                exact_top_camera_energy_fraction=float(energy[top]/np.sum(energy)),
                exact_healthy_physical_norm=float(np.linalg.norm(physical[healthy])),
                exact_healthy_raw_physical_norm=float(np.linalg.norm(raw_physical[healthy])),
                exact_linear_relative_residual=relative_residual,
                exact_proposal=evaluate(model, delta_chart, physical, kind),
                local=local,
                captured_direction=dict(
                    raw_radius_ratio=captured_norm/radius,
                    clip_factor=captured_clip,
                    healthy_clipped_physical_norm=float(
                        captured_clip*np.linalg.norm(captured_physical[healthy])),
                    top_camera=int(np.argmax(np.sum(captured_z**2, axis=1))),
                    top_camera_energy_fraction=float(np.max(np.sum(captured_z**2, axis=1))
                                                       / np.sum(captured_z**2))))


def audit(folder: Path, ci, pi, uv):
    model = build_model(folder, ci, pi, uv)
    model.update(ci=ci, pi=pi, uv=uv)
    if abs(model["score"]-model["meta"]["cost"])/max(1, model["score"]) > 1e-8:
        raise ValueError("score mismatch")
    charts = {kind: chart_result(model, kind)
              for kind in ("additive", "ratio-linear", "ratio-log")}
    additive = charts["additive"]
    coherent_E_error = float(np.linalg.norm(model["E_coherent"]-model["E_capture"])
                             / np.linalg.norm(model["E_capture"]))
    coherent_E_max_relative = float(np.max(np.abs(
        model["E_coherent"]/model["E_capture"]-1)))
    compact = {}
    for kind, row in charts.items():
        compact[kind] = {key: value for key, value in row.items()
                         if key not in ("transform_blocks", "E", "scaled_operator",
                                        "exact_scaled_step", "exact_raw_physical", "local")}
        compact[kind]["camera34_local"] = row["local"][34]
        compact[kind]["condition_improvement_vs_additive"] = (
            additive["local"][34]["condition"] / row["local"][34]["condition"])
        compact[kind]["true_decrease_delta_vs_additive"] = (
            row["exact_proposal"]["true_decrease"]
            - additive["exact_proposal"]["true_decrease"])
        compact[kind]["captured_ratio_reduction_vs_additive"] = (
            additive["captured_direction"]["raw_radius_ratio"]
            / row["captured_direction"]["raw_radius_ratio"])
        compact[kind]["captured_healthy_retention_vs_additive"] = (
            row["captured_direction"]["healthy_clipped_physical_norm"]
            / max(additive["captured_direction"]["healthy_clipped_physical_norm"], 1e-300))
    return dict(metadata=model["meta"], score_init=model["score"],
                native_captured_raw_radius_ratio=float(
                    np.linalg.norm(model["raw_capture"])/model["meta"]["radius"]),
                coherent_E_relative_error=coherent_E_error,
                coherent_E_max_coordinate_relative_error=coherent_E_max_relative,
                charts=compact)


def terminal_case(index, ci, pi, uv):
    record_path = W3 / f"forensics/venice-terminal-{index}.json"
    record = json.loads(record_path.read_text())["archive_source"]
    archive = Path(record["path"])
    if sha(archive) != record["sha256"]:
        raise ValueError("terminal archive mismatch")
    with tempfile.TemporaryDirectory(prefix="d7-terminal-", dir="/dev/shm") as tmp:
        root = Path(tmp)
        with tarfile.open(archive) as handle:
            handle.extractall(root, filter="data")
        members = validate_members(root/"0", record["member_sha256"], "0/")
        result = audit(root/"0", ci, pi, uv)
    result.update(case=f"terminal-{index}", kind="terminal",
                  archive=str(archive), archive_sha256=record["sha256"],
                  member_sha256=members, record_sha256=sha(record_path))
    return result


def opening_case(index, ci, pi, uv):
    record_path = W3 / f"opening-captures/{index}/result.json"
    record = json.loads(record_path.read_text())
    archive = Path(record["archive"])
    if sha(archive) != record["sha256"]:
        raise ValueError("opening archive mismatch")
    with tempfile.TemporaryDirectory(prefix="d7-opening-", dir="/dev/shm") as tmp:
        root = Path(tmp)
        FA.restore(archive, root)
        members = validate_members(root/"2", record["member_hashes"], "2/")
        result = audit(root/"2", ci, pi, uv)
    result.update(case=f"opening-{index}", kind="opening",
                  archive=str(archive), archive_sha256=record["sha256"],
                  member_sha256=members, record_sha256=sha(record_path))
    return result


def main():
    started = time.time()
    baseline = CHART.verify_frozen_baseline()
    ci, pi, uv, dimensions = CHART.load_observations(BAL)
    if dimensions != (52, 64053, 347173):
        raise ValueError(dimensions)
    cases = []
    for index in range(5):
        result = terminal_case(index, ci, pi, uv)
        cases.append(result)
        row = result["charts"]["ratio-log"]
        print("D7", result["case"], "ratio", row["captured_direction"]["raw_radius_ratio"],
              "gain", row["captured_healthy_retention_vs_additive"],
              "dF", row["exact_proposal"]["true_decrease"], flush=True)
    for index in range(3):
        result = opening_case(index, ci, pi, uv)
        cases.append(result)
        row = result["charts"]["ratio-log"]
        print("D7", result["case"], "ratio", row["captured_direction"]["raw_radius_ratio"],
              "dF", row["exact_proposal"]["true_decrease"], flush=True)

    terminal = [row for row in cases if row["kind"] == "terminal"]
    opening = [row for row in cases if row["kind"] == "opening"]
    metric = [row for row in terminal if
              row["charts"]["ratio-log"]["captured_ratio_reduction_vs_additive"] >= 10 and
              row["charts"]["ratio-log"]["captured_healthy_retention_vs_additive"] >= 10]
    proposal = [row for row in terminal if
                row["charts"]["ratio-log"]["exact_proposal"]["prediction"] > 0 and
                row["charts"]["ratio-log"]["exact_proposal"]["true_decrease"] >
                row["charts"]["additive"]["exact_proposal"]["true_decrease"]]
    aligned = [row for row in terminal if
               row["charts"]["ratio-log"]["camera34_local"]["max_weak_pair_coordinate_loading"] >= .9 and
               row["charts"]["ratio-log"]["condition_improvement_vs_additive"] >= 10]
    opening_ok = [row for row in opening if
                  row["charts"]["ratio-log"]["exact_raw_radius_ratio"] <= 2 and
                  row["charts"]["ratio-log"]["exact_proposal"]["true_decrease"] >=
                  .9985*row["charts"]["additive"]["exact_proposal"]["true_decrease"]]
    gates = dict(
        metric_improvement_at_least_4_of_5=len(metric) >= 4,
        metric_improvement_cases=[row["case"] for row in metric],
        true_proposal_improvement_at_least_4_of_5=len(proposal) >= 4,
        true_proposal_improvement_cases=[row["case"] for row in proposal],
        alignment_and_condition_at_least_4_of_5=len(aligned) >= 4,
        alignment_and_condition_cases=[row["case"] for row in aligned],
        all_three_opening_controls_pass=len(opening_ok) == 3,
        opening_control_pass_cases=[row["case"] for row in opening_ok])
    gates["native_ratio_log_justified"] = all(
        value for key, value in gates.items() if not key.endswith("cases"))
    output = dict(
        registration=dict(protocol_sha256=sha(PROTOCOL), analysis_sha256=sha(Path(__file__)),
                          bal=str(BAL), bal_sha256=sha(BAL), dimensions=dimensions,
                          terminal_indices=list(range(5)), opening_indices=list(range(3)),
                          opening_archive_member="2 (selected attempt2)",
                          arithmetic="coherent FP64 dense diagnostic"),
        baseline=baseline, cases=cases, gates=gates,
        elapsed_seconds=time.time()-started)
    write(P/"d7-intrinsics-chart-results.json", output)
    print(json.dumps(gates, indent=2), flush=True)


if __name__ == "__main__":
    main()
