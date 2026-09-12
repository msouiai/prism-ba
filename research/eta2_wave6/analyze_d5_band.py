#!/usr/bin/env python3
"""Registered graph and fixed-Schur screen for a banded camera preconditioner."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import shutil
import sys
import time

import numpy as np
import scipy
import scipy.linalg as la
import scipy.sparse as sp
from scipy.sparse.csgraph import reverse_cuthill_mckee

P = Path(__file__).resolve().parent
ROOT = P.parents[1]
PROTOCOL = P / "D5_BAND_PROTOCOL.md"
ARCHIVE = ROOT / "research/eta2_curvature_audit/evidence_archives/capture-0.xor.tar.xz"
ARCHIVE_RECORD = ROOT / "research/eta2_curvature_audit/evidence/capture-0/ARCHIVED.json"
RESTORE = Path("/dev/shm/eta2-wave6-d5-capture-0")
BANDS = (1, 2, 4, 8, 16, 32, 64, 128)
SCENES = (
    ("ladybug-539", Path("/tmp/prism-speed-novelty/inputs/ladybug-539.txt"), "sequence"),
    ("ladybug-1197", Path("/workspace/bal/ladybug-1197.txt"), "sequence"),
    ("venice-52", Path("/workspace/bal/venice-52.txt"), "sequence"),
    ("venice-951", Path("/workspace/bal/venice-951.txt"), "sequence"),
    ("final-3068", Path("/workspace/bal/final-3068.txt"), "control"),
    ("muell-gba146", Path("/workspace/bal/muell-gba146.txt"), "control"),
)


def sha(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def write(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True,
                               allow_nan=False) + "\n")


def read_bal_graph(path: Path):
    with path.open() as handle:
        header = handle.readline().split()
        if len(header) != 3:
            raise ValueError(f"bad BAL header: {path}")
        nc, npt, no = map(int, header)
        pairs = np.loadtxt(handle, dtype=np.int32, usecols=(0, 1),
                           max_rows=no, ndmin=2)
    if pairs.shape != (no, 2):
        raise ValueError((path, pairs.shape, no))
    ci, pi = pairs[:, 0], pairs[:, 1]
    if ci.min() < 0 or ci.max() >= nc or pi.min() < 0 or pi.max() >= npt:
        raise ValueError(f"indices outside header dimensions: {path}")
    return nc, npt, no, ci, pi


def incidence(nc, npt, ci, pi):
    matrix = sp.coo_matrix((np.ones(len(ci), dtype=np.float64), (ci, pi)),
                           shape=(nc, npt)).tocsr()
    matrix.sum_duplicates()
    # BAL should contain at most one observation of a point in a camera.
    duplicate_entries = int(np.count_nonzero(matrix.data != 1))
    matrix.data[:] = 1.0
    counts = np.asarray(matrix.sum(axis=0)).ravel().astype(np.int64)
    return matrix, counts, duplicate_entries


def camera_graph(B, counts, normalized):
    if normalized:
        weights = 1.0 / np.maximum(counts - 1, 1)
        product = B.multiply(weights) @ B.T
    else:
        product = B @ B.T
    product = product.tocsr()
    product.setdiag(0)
    product.eliminate_zeros()
    product.sort_indices()
    return product


def order_positions(permutation):
    position = np.empty(len(permutation), dtype=np.int64)
    position[permutation] = np.arange(len(permutation))
    return position


def edge_band_stats(graph, position):
    upper = sp.triu(graph, k=1).tocoo()
    distance = np.abs(position[upper.row] - position[upper.col])
    weight = upper.data.astype(np.float64)
    total = float(weight.sum())
    if not total:
        raise ValueError("empty camera graph")
    by_distance = np.bincount(distance, weights=weight, minlength=len(position))
    cumulative = np.cumsum(by_distance) / total
    result = {
        "edges": int(len(weight)),
        "mass": total,
        "weighted_mean_distance": float(np.dot(distance, weight) / total),
        "fractions": {str(b): float(cumulative[min(b, len(cumulative) - 1)])
                      for b in BANDS},
        "width_for_fraction": {},
    }
    for fraction in (0.50, 0.80, 0.90, 0.95):
        result["width_for_fraction"][str(fraction)] = int(
            np.searchsorted(cumulative, fraction, side="left"))
    return result


def span_stats(B, position):
    coo = B.tocoo()
    npt = B.shape[1]
    lo = np.full(npt, len(position), dtype=np.int64)
    hi = np.full(npt, -1, dtype=np.int64)
    pos = position[coo.row]
    np.minimum.at(lo, coo.col, pos)
    np.maximum.at(hi, coo.col, pos)
    counts = np.bincount(coo.col, minlength=npt)
    values = (hi - lo)[counts >= 2]
    if not len(values):
        return {"tracks": 0}
    return {
        "tracks": int(len(values)),
        "median": float(np.median(values)),
        "p90": float(np.quantile(values, .90)),
        "p99": float(np.quantile(values, .99)),
        "maximum": int(values.max()),
    }


def analyze_graph(name, path, family):
    start = time.perf_counter()
    nc, npt, no, ci, pi = read_bal_graph(path)
    B, counts, duplicates = incidence(nc, npt, ci, pi)
    raw = camera_graph(B, counts, False)
    normalized = camera_graph(B, counts, True)
    adjacency = raw.copy()
    adjacency.data[:] = 1.0
    permutation = reverse_cuthill_mckee(adjacency, symmetric_mode=True)
    natural = np.arange(nc, dtype=np.int64)
    positions = {"natural": order_positions(natural),
                 "rcm": order_positions(permutation)}
    result = {
        "scene": name,
        "family": family,
        "path": str(path),
        "input_sha256": sha(path),
        "ncam": nc,
        "npoint": npt,
        "nobs": no,
        "duplicate_camera_point_entries": duplicates,
        "track_length": {
            "median": float(np.median(counts[counts > 0])),
            "p90": float(np.quantile(counts[counts > 0], .90)),
            "maximum": int(counts.max()),
        },
        "orderings": {},
    }
    for order, position in positions.items():
        result["orderings"][order] = {
            "raw": edge_band_stats(raw, position),
            "normalized": edge_band_stats(normalized, position),
            "track_spans": span_stats(B, position),
        }
    result["rcm_permutation_sha256"] = hashlib.sha256(
        permutation.astype("<i4").tobytes()).hexdigest()
    result["analysis_seconds"] = time.perf_counter() - start
    print("GRAPH", name, "ncam", nc,
          "RCM normalized@16",
          result["orderings"]["rcm"]["normalized"]["fractions"]["16"],
          "seconds", result["analysis_seconds"], flush=True)
    return result, (B, counts, raw, permutation)


def forward_factor(r, b):
    """Solve R^T y=b for packed upper-triangular R, batched over observations."""
    y = np.empty_like(b, dtype=np.float64)
    y[:, :, 0] = b[:, :, 0] / r[:, None, 0]
    y[:, :, 1] = (b[:, :, 1] - r[:, None, 1] * y[:, :, 0]) / r[:, None, 3]
    y[:, :, 2] = (b[:, :, 2] - r[:, None, 2] * y[:, :, 0]
                    - r[:, None, 4] * y[:, :, 1]) / r[:, None, 5]
    return y


def block_diagonal(blocks):
    nc, width, _ = blocks.shape
    out = np.zeros((nc * width, nc * width), dtype=np.float64)
    for camera in range(nc):
        sl = slice(width * camera, width * (camera + 1))
        out[sl, sl] = blocks[camera]
    return out


def generalized_condition(A, M):
    result = {
        "min_eigenvalue_M": float(la.eigvalsh(M, subset_by_index=(0, 0))[0]),
        "max_eigenvalue_M": float(la.eigvalsh(M,
                                              subset_by_index=(len(M)-1, len(M)-1))[0]),
    }
    try:
        la.cholesky(M, lower=True, check_finite=True)
        values = la.eigh(A, M, eigvals_only=True, check_finite=True,
                         driver="gvd")
        positive = values[values > 0]
        result.update({
            "unshifted_spd": True,
            "generalized_min": float(values[0]),
            "generalized_max": float(values[-1]),
            "generalized_nonpositive": int(np.count_nonzero(values <= 0)),
            "generalized_condition": (float(values[-1] / values[0])
                                      if values[0] > 0 else None),
        })
    except la.LinAlgError:
        result.update({"unshifted_spd": False, "generalized_min": None,
                       "generalized_max": None,
                       "generalized_nonpositive": None,
                       "generalized_condition": None})
    scale = max(abs(result["min_eigenvalue_M"]),
                abs(result["max_eigenvalue_M"]), 1.0)
    result["diagnostic_shift_to_spd"] = max(
        0.0, -result["min_eigenvalue_M"] + 1e-12 * scale)
    return result


def numerical_screen(graph_record, graph_aux):
    record = json.loads(ARCHIVE_RECORD.read_text())
    if sha(ARCHIVE) != record["archive_sha256"]:
        raise ValueError("capture archive hash mismatch")
    sys.path.insert(0, str(ROOT / "research/eta2_wave2"))
    import lossless_float_archive as archive
    archive.verify(ARCHIVE, record["files"])
    shutil.rmtree(RESTORE, ignore_errors=True)
    archive.restore(ARCHIVE, RESTORE)
    try:
        metadata = {}
        for line in (RESTORE / "metadata.txt").read_text().splitlines():
            key, value = line.split("=", 1)
            metadata[key] = float(value)
        nc, npt, no = (int(metadata[key]) for key in ("ncam", "npt", "nobs"))
        fc = np.fromfile(RESTORE / "fragment_cams.i32", "<i4")
        fp = np.fromfile(RESTORE / "fragment_points.i32", "<i4")
        W = np.memmap(RESTORE / "W64.f64", mode="r", dtype="<f8",
                      shape=(9, 3, no))
        R = np.fromfile(RESTORE / "R_fp64qr.f64", "<f8").reshape(npt, 6)
        E = np.fromfile(RESTORE / "E.f64", "<f8").reshape(nc, 9)
        H = np.fromfile(RESTORE / "Hcc.f64", "<f8").reshape(nc, 9, 9)
        if len(fc) != no or len(fp) != no:
            raise ValueError("capture observation dimensions disagree")
        if np.any(R[:, (0, 3, 5)] <= 0):
            raise ValueError("invalid point factor")

        # Each observation contributes T_ij=R_j^-T W_ij^T.  Stack the three
        # rows per point into a sparse T so the eliminated term is exactly T^T T.
        w = np.asarray(W).transpose(2, 0, 1)
        transformed = forward_factor(R[fp], w)
        transformed *= E[fc, :, None]
        rows = np.broadcast_to(fp[:, None, None] * 3
                               + np.arange(3)[None, None, :],
                               transformed.shape).ravel()
        cols = np.broadcast_to(fc[:, None, None] * 9
                               + np.arange(9)[None, :, None],
                               transformed.shape).ravel()
        T = sp.coo_matrix((transformed.ravel(), (rows, cols)),
                          shape=(3 * npt, 9 * nc)).tocsr()
        point_term = (T.T @ T).toarray()
        Hscaled = H * E[:, :, None] * E[:, None, :]
        A = block_diagonal(Hscaled) - point_term
        A.flat[::len(A)+1] += metadata["lambda"]
        A = .5 * (A + A.T)
        direction = np.fromfile(RESTORE / "direction.f64", "<f8")
        saved = np.fromfile(RESTORE / "W64_R64qr_product.f64", "<f8")
        action = A @ direction
        action_relative_error = float(np.linalg.norm(action - saved)
                                      / np.linalg.norm(saved))
        if action_relative_error > 2e-10:
            raise ValueError(f"dense/matrix-free action mismatch {action_relative_error}")

        B, counts, raw, permutation = graph_aux
        if B.shape != (nc, npt):
            raise ValueError("BAL and capture graph dimensions disagree")
        capture_B, capture_counts, duplicates = incidence(nc, npt, fc, fp)
        if duplicates or (capture_B != B).nnz or not np.array_equal(capture_counts, counts):
            raise ValueError("BAL and capture incidence differ")
        result = {
            "capture_archive": str(ARCHIVE),
            "capture_archive_sha256": record["archive_sha256"],
            "restored_member_sha256": {name: record["files"][name] for name in
                ("W64.f64", "R_fp64qr.f64", "E.f64", "Hcc.f64",
                 "direction.f64", "W64_R64qr_product.f64",
                 "fragment_cams.i32", "fragment_points.i32", "metadata.txt")},
            "metadata": metadata,
            "dense_action_relative_error": action_relative_error,
            "matrix_min_eigenvalue": float(la.eigvalsh(A, subset_by_index=(0, 0))[0]),
            "matrix_max_eigenvalue": float(la.eigvalsh(
                A, subset_by_index=(len(A)-1, len(A)-1))[0]),
            "preconditioners": {},
            "orderings": {},
        }
        Hpre = block_diagonal(Hscaled)
        Hpre.flat[::len(Hpre)+1] += metadata["lambda"]
        Sdiag = block_diagonal(np.stack(
            [A[9*i:9*i+9, 9*i:9*i+9] for i in range(nc)]))
        result["preconditioners"]["eta2_Hcc"] = generalized_condition(A, Hpre)
        result["preconditioners"]["schur_jacobi"] = generalized_condition(A, Sdiag)

        for label, camera_perm in (("natural", np.arange(nc)),
                                   ("rcm", permutation)):
            coordinate_perm = (camera_perm[:, None] * 9
                               + np.arange(9)[None, :]).ravel()
            Ap = A[np.ix_(coordinate_perm, coordinate_perm)]
            off = Ap.copy()
            for camera in range(nc):
                sl = slice(9*camera, 9*(camera+1))
                off[sl, sl] = 0
            total_energy = float(np.sum(off * off))
            order_result = {"bands": {}}
            camera_coordinate = np.repeat(np.arange(nc), 9)
            distance = np.abs(camera_coordinate[:, None]
                              - camera_coordinate[None, :])
            for band in BANDS:
                if band >= nc:
                    continue
                mask = distance <= band
                M = np.where(mask, Ap, 0.0)
                retained = float(np.sum((off * mask) ** 2) / total_energy)
                order_result["bands"][str(band)] = {
                    "offdiagonal_frobenius_energy_fraction": retained,
                    "preconditioner": generalized_condition(Ap, M),
                }
            result["orderings"][label] = order_result
        return result
    finally:
        shutil.rmtree(RESTORE, ignore_errors=True)


def main():
    started = time.time()
    graph_records = []
    venice_aux = None
    for name, path, family in SCENES:
        record, aux = analyze_graph(name, path, family)
        graph_records.append(record)
        if name == "venice-52":
            venice_aux = aux
    numerical = numerical_screen(
        next(row for row in graph_records if row["scene"] == "venice-52"),
        venice_aux)
    seq_pass = [row["scene"] for row in graph_records
                if row["family"] == "sequence" and
                row["orderings"]["rcm"]["normalized"]["fractions"]["16"] >= .80]
    band16 = numerical["orderings"]["rcm"]["bands"]["16"]
    hcond = numerical["preconditioners"]["eta2_Hcc"]["generalized_condition"]
    bcond = band16["preconditioner"]["generalized_condition"]
    gates = {
        "two_sequence_scenes_normalized_mass_at_RCM16_ge_0.80": len(seq_pass) >= 2,
        "passing_sequence_scenes": seq_pass,
        "venice_RCM16_offdiagonal_energy_ge_0.80":
            band16["offdiagonal_frobenius_energy_fraction"] >= .80,
        "venice_RCM16_unshifted_spd": band16["preconditioner"]["unshifted_spd"],
        "venice_RCM16_condition_improvement_ge_3": bool(
            hcond is not None and bcond is not None and hcond / bcond >= 3),
        "condition_improvement": hcond / bcond if hcond and bcond else None,
    }
    gates["native_build_justified"] = all(
        value for key, value in gates.items()
        if key not in ("passing_sequence_scenes", "condition_improvement"))
    result = {
        "registration": {
            "protocol_sha256": sha(PROTOCOL),
            "analysis_sha256": sha(Path(__file__)),
            "numpy_version": np.__version__,
            "scipy_version": scipy.__version__,
            "bands": list(BANDS),
            "inputs": {name: {"path": str(path), "sha256": sha(path),
                              "family": family}
                       for name, path, family in SCENES},
        },
        "graphs": graph_records,
        "numerical": numerical,
        "gates": gates,
        "elapsed_seconds": time.time() - started,
    }
    write(P / "d5-band-results.json", result)
    print(json.dumps(gates, indent=2), flush=True)


if __name__ == "__main__":
    main()
