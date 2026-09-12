#!/usr/bin/env python3
"""Gauge-quotient posterior camera-variance diagnostic for Eta2 wave 6."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
import time

import numpy as np
import scipy
import scipy.linalg as la
import scipy.sparse as sp
from scipy.stats import spearmanr

P = Path(__file__).resolve().parent
RESEARCH = P.parent
W3 = RESEARCH / "eta2_wave3"
CORE = RESEARCH / "eta2_research_20260912"
PROTOCOL = P / "D6_COVARIANCE_PROTOCOL.md"
BAL = Path("/workspace/bal/venice-52.txt")

sys.path[:0] = [str(RESEARCH / "eta2_wave2"), str(CORE / "analysis"),
                str(CORE / "coarse")]
import lossless_float_archive as FA
import diagnostic as D
from audit_capture import load_capture_state, CHART
from spectrum import point_qr


def sha(path: Path) -> str:
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def write(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True,
                               allow_nan=False) + "\n")


def read_array(path: Path, shape):
    data = np.fromfile(path, "<f8")
    if data.size != int(np.prod(shape)):
        raise ValueError((path, data.size, shape))
    data = data.reshape(shape)
    if not np.isfinite(data).all():
        raise ValueError(f"nonfinite data in {path}")
    return data


def aggregate(values, ids, count):
    flat = values.reshape(len(values), -1)
    answer = np.column_stack([
        np.bincount(ids, weights=flat[:, column], minlength=count)
        for column in range(flat.shape[1])])
    return answer.reshape((count,) + values.shape[1:])


def block_diagonal(blocks):
    nc, width, _ = blocks.shape
    answer = np.zeros((nc * width, nc * width), dtype=np.float64)
    for camera, block in enumerate(blocks):
        sl = slice(width * camera, width * (camera + 1))
        answer[sl, sl] = block
    return answer


def rank_descending(score):
    order = np.lexsort((np.arange(len(score)), -np.asarray(score)))
    rank = np.empty(len(score), dtype=np.int64)
    rank[order] = np.arange(1, len(score) + 1)
    return order, rank


def score_report(score, raw_energy, known=34):
    order, rank = rank_descending(score)
    total = max(float(np.sum(raw_energy)), np.finfo(float).tiny)
    return {
        "top_camera_ids": order[:10].tolist(),
        "known_camera_rank": int(rank[known]),
        "known_camera_score_ratio_to_median": float(
            score[known] / max(float(np.median(score)), np.finfo(float).tiny)),
        "top1_raw_energy_fraction": float(np.sum(raw_energy[order[:1]]) / total),
        "top3_raw_energy_fraction": float(np.sum(raw_energy[order[:3]]) / total),
        "spearman_with_raw_energy": float(spearmanr(score, raw_energy).statistic),
    }


def build_operator(folder: Path, ci, pi, uv):
    camera, X, meta = load_capture_state(folder)
    nc, npt, no = len(camera.R), len(X), len(ci)
    if (nc, npt, no) != (int(meta["ncam"]), int(meta["npt"]), int(meta["nobs"])):
        raise ValueError("state and metadata dimensions disagree")
    E = read_array(folder / "E.f64", (nc, 9))
    Cdiag = read_array(folder / "Cdiag.f64", (npt, 3))
    raw = -read_array(folder / "eta2_raw_scaled.f64", (nc, 9))
    if np.any(raw[:, 8] != 0):
        raise ValueError("inactive k2 moved")
    chart = CHART.make_chart(X, camera, "euclidean")
    residual, Jc, Jp, Y = CHART.observation_jacobians(
        camera, chart.H, chart.T, ci, pi, uv)
    point_floor = np.maximum(Cdiag,
                             .001 * np.maximum(Cdiag.mean(axis=1), 1e-32)[:, None])
    point_diagonal = meta["tau"] * point_floor
    _, inverse_R, _ = point_qr(Jp, pi, point_diagonal)

    keys = ci.astype(np.int64) * npt + pi
    unique, inverse = np.unique(keys, return_inverse=True)
    pair_camera = (unique // npt).astype(np.int64)
    pair_point = (unique % npt).astype(np.int64)
    cross = aggregate(np.einsum("nri,nrj->nij", Jc, Jp),
                      inverse, len(unique))
    camera_normal = aggregate(np.einsum("nri,nrj->nij", Jc, Jc), ci, nc)
    transformed = np.einsum("nij,njk->nik", cross, inverse_R[pair_point])
    transformed *= E[pair_camera, :, None]

    rows = np.broadcast_to(pair_point[:, None, None] * 3
                           + np.arange(3)[None, None, :], transformed.shape).ravel()
    cols = np.broadcast_to(pair_camera[:, None, None] * 9
                           + np.arange(9)[None, :, None], transformed.shape).ravel()
    T = sp.coo_matrix((transformed.ravel(), (rows, cols)),
                      shape=(3*npt, 9*nc)).tocsr()
    point_term = (T.T @ T).toarray()

    counts = np.bincount(ci, minlength=nc)
    r2 = np.sum((Y[:, :2] / Y[:, 2, None]) ** 2, axis=1)
    average_r2 = np.maximum(np.bincount(ci, weights=r2, minlength=nc)
                            / np.maximum(counts, 1), 1e-12)
    prior = np.zeros((nc, 9), dtype=np.float64)
    prior[:, 6] = np.where(counts > 0,
                           1 / (.5*np.abs(camera.intrinsics[:, 0]) + 1e-3)**2, 0)
    prior[:, 7] = np.where(counts > 0, average_r2**2, 0)
    scaled_blocks = camera_normal * E[:, :, None] * E[:, None, :]
    scaled_blocks[:, np.arange(9), np.arange(9)] += prior * E * E
    A = block_diagonal(scaled_blocks) - point_term
    A.flat[::len(A)+1] += meta["lambda"]
    symmetry_error = float(np.max(np.abs(A - A.T)))
    A = .5 * (A + A.T)

    active = (np.arange(nc)[:, None] * 9 + np.arange(8)[None, :]).ravel()
    A8 = A[np.ix_(active, active)]
    blocks, gauge_info = D.build_blocks(camera.R, camera.t, E,
                                        np.zeros(nc, dtype=np.int64))
    gauge9 = blocks[0]["Q"]
    gauge8 = gauge9.reshape(nc, 9, -1)[:, :8].reshape(8*nc, -1)
    gauge8, _ = np.linalg.qr(gauge8)
    complement = la.null_space(gauge8.T)
    reconstruction_error = float(np.linalg.norm(
        gauge8 @ gauge8.T + complement @ complement.T - np.eye(8*nc), ord=2))
    projected = complement.T @ A8 @ complement
    projected = .5 * (projected + projected.T)
    values, vectors = la.eigh(projected)
    if values[0] <= 0:
        raise ValueError(f"nonpositive quotient operator {values[0]}")
    inverse_projected = (vectors / values) @ vectors.T
    covariance = complement @ inverse_projected @ complement.T

    posterior_max = np.empty(nc)
    posterior_trace = np.empty(nc)
    local_score = np.empty(nc)
    for camera_id in range(nc):
        sl = slice(8*camera_id, 8*(camera_id+1))
        block = .5 * (covariance[sl, sl] + covariance[sl, sl].T)
        posterior_max[camera_id] = la.eigvalsh(
            block, subset_by_index=(7, 7))[0]
        posterior_trace[camera_id] = np.trace(block)
        local = A8[sl, sl]
        local_min = la.eigvalsh(local, subset_by_index=(0, 0))[0]
        local_score[camera_id] = 1 / max(local_min, np.finfo(float).tiny)
    raw_energy = np.sum(raw[:, :8] ** 2, axis=1)
    count_score = 1 / np.maximum(counts, 1)
    score_reports = {
        "posterior_max_block_eigenvalue": score_report(posterior_max, raw_energy),
        "posterior_block_trace": score_report(posterior_trace, raw_energy),
        "local_inverse_min_block_eigenvalue": score_report(local_score, raw_energy),
        "inverse_observation_count": score_report(count_score, raw_energy),
    }
    return {
        "metadata": meta,
        "score_init": float(.5*np.sum(residual*residual, dtype=np.longdouble)),
        "raw_radius_ratio": float(np.linalg.norm(raw) / meta["radius"]),
        "raw_top_camera": int(np.argmax(raw_energy)),
        "raw_top_camera_energy_fraction": float(raw_energy.max() / raw_energy.sum()),
        "matrix_symmetry_absolute_error": symmetry_error,
        "gauge_rank": int(gauge8.shape[1]),
        "gauge_basis_checks": gauge_info,
        "quotient_reconstruction_2norm_error": reconstruction_error,
        "quotient_min_eigenvalue": float(values[0]),
        "quotient_max_eigenvalue": float(values[-1]),
        "quotient_condition": float(values[-1] / values[0]),
        "scores": score_reports,
    }


def validate_members(folder, expected, prefix=""):
    required = ("metadata.txt", "E.f64", "Cdiag.f64", "eta2_raw_scaled.f64",
                "R_state.f64", "t_state.f64", "X_state.f64", "intr_state.f64")
    actual = {}
    for name in required:
        key = prefix + name
        value = sha(folder / name)
        if expected[key] != value:
            raise ValueError(f"member hash mismatch {key}")
        actual[key] = value
    return actual


def terminal_case(index, ci, pi, uv):
    forensic_path = W3 / f"forensics/venice-terminal-{index}.json"
    forensic = json.loads(forensic_path.read_text())
    record = forensic["archive_source"]
    archive = Path(record["path"])
    if sha(archive) != record["sha256"]:
        raise ValueError("terminal archive hash mismatch")
    with tempfile.TemporaryDirectory(prefix="d6-terminal-", dir="/dev/shm") as temporary:
        root = Path(temporary)
        with tarfile.open(archive) as handle:
            handle.extractall(root, filter="data")
        folder = root / "0"
        members = validate_members(folder, record["member_sha256"], "0/")
        result = build_operator(folder, ci, pi, uv)
    result.update({"case": f"terminal-{index}", "kind": "terminal",
                   "archive": str(archive), "archive_sha256": record["sha256"],
                   "forensic_sha256": sha(forensic_path),
                   "member_sha256": members})
    return result


def opening_case(index, ci, pi, uv):
    record_path = W3 / f"opening-captures/{index}/result.json"
    record = json.loads(record_path.read_text())
    archive = Path(record["archive"])
    if sha(archive) != record["sha256"]:
        raise ValueError("opening archive hash mismatch")
    with tempfile.TemporaryDirectory(prefix="d6-opening-", dir="/dev/shm") as temporary:
        root = Path(temporary)
        FA.restore(archive, root)
        folder = root / "2"
        members = validate_members(folder, record["member_hashes"], "2/")
        result = build_operator(folder, ci, pi, uv)
    result.update({"case": f"opening-{index}", "kind": "opening",
                   "archive": str(archive), "archive_sha256": record["sha256"],
                   "archive_record_sha256": sha(record_path),
                   "member_sha256": members})
    return result


def main():
    started = time.time()
    ci, pi, uv, dimensions = CHART.load_observations(BAL)
    if dimensions != (52, 64053, 347173):
        raise ValueError(dimensions)
    cases = []
    for index in range(5):
        row = terminal_case(index, ci, pi, uv)
        cases.append(row)
        print("D6", row["case"], "top",
              row["scores"]["posterior_max_block_eigenvalue"]["top_camera_ids"][0],
              "local", row["scores"]["local_inverse_min_block_eigenvalue"]["top_camera_ids"][0],
              "rank34", row["scores"]["posterior_max_block_eigenvalue"]["known_camera_rank"],
              flush=True)
    for index in range(3):
        row = opening_case(index, ci, pi, uv)
        cases.append(row)
        print("D6", row["case"], "top",
              row["scores"]["posterior_max_block_eigenvalue"]["top_camera_ids"][0],
              "raw", row["raw_top_camera"], flush=True)

    terminal = [row for row in cases if row["kind"] == "terminal"]
    primary = "posterior_max_block_eigenvalue"
    local = "local_inverse_min_block_eigenvalue"
    top34 = [row for row in terminal
             if row["scores"][primary]["top_camera_ids"][0] == 34 and
             row["scores"][primary]["top1_raw_energy_fraction"] >= .99]
    added = []
    for row in terminal:
        p = row["scores"][primary]
        l = row["scores"][local]
        if (p["known_camera_rank"] < l["known_camera_rank"] or
                p["top1_raw_energy_fraction"] > l["top1_raw_energy_fraction"] + 1e-12):
            added.append(row["case"])
    gates = {
        "posterior_top34_with_99pct_energy_at_least_4_of_5": len(top34) >= 4,
        "passing_terminal_cases": [row["case"] for row in top34],
        "strict_added_information_at_least_2_states": len(added) >= 2,
        "added_information_cases": added,
        "all_quotient_operators_spd": all(row["quotient_min_eigenvalue"] > 0
                                           for row in cases),
        "all_reconstruction_errors_below_1e-10": all(
            row["quotient_reconstruction_2norm_error"] < 1e-10 for row in cases),
    }
    gates["native_probe_or_prior_justified"] = all(
        value for key, value in gates.items()
        if key not in ("passing_terminal_cases", "added_information_cases"))
    output = {
        "registration": {
            "protocol_sha256": sha(PROTOCOL),
            "analysis_sha256": sha(Path(__file__)),
            "bal": str(BAL),
            "bal_sha256": sha(BAL),
            "numpy_version": np.__version__,
            "scipy_version": scipy.__version__,
            "terminal_indices": list(range(5)),
            "opening_indices": list(range(3)),
            "opening_archive_member": "2 (selected attempt2)",
        },
        "cases": cases,
        "gates": gates,
        "elapsed_seconds": time.time() - started,
    }
    write(P / "d6-covariance-results.json", output)
    print(json.dumps(gates, indent=2), flush=True)


if __name__ == "__main__":
    main()
