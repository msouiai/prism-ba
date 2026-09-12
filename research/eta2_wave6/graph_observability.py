#!/usr/bin/env python3
"""Deterministic camera-graph observability diagnostic for C1.

The primary graph is the normalized clique expansion registered in
``C1_PROTOCOL.md``.  This tool never runs or modifies the BA solver.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import time

import numpy as np
from scipy import sparse
from scipy.sparse.csgraph import connected_components
from scipy.sparse.linalg import splu
from scipy.stats import spearmanr


PROJECTIONS = 256
SEED = 630001


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 << 20), b""):
            h.update(block)
    return h.hexdigest()


def read_bal_incidence(path: Path):
    """Read only the header and observation incidence from a BAL file."""
    started = time.perf_counter()
    with path.open("rb") as stream:
        header = stream.readline().split()
        if len(header) != 3:
            raise ValueError(f"invalid BAL header in {path}")
        ncam, npoint, nobs = map(int, header)
        camera = np.empty(nobs, dtype=np.int32)
        point = np.empty(nobs, dtype=np.int32)
        for row in range(nobs):
            fields = stream.readline().split()
            if len(fields) != 4:
                raise ValueError(f"invalid BAL observation {row} in {path}")
            camera[row] = int(fields[0])
            point[row] = int(fields[1])
    if np.any(camera < 0) or np.any(camera >= ncam):
        raise ValueError("camera index outside BAL header range")
    if np.any(point < 0) or np.any(point >= npoint):
        raise ValueError("point index outside BAL header range")
    return (ncam, npoint, nobs), camera, point, time.perf_counter() - started


def normalized_clique_graph(ncam: int, npoint: int, camera, point):
    """Return the 1/(track_length-1) normalized clique expansion."""
    started = time.perf_counter()
    incidence = sparse.csr_matrix(
        (np.ones(len(camera), dtype=np.float64), (camera, point)),
        shape=(ncam, npoint),
    )
    incidence.sum_duplicates()
    duplicates = int(len(camera) - incidence.nnz)
    incidence.data.fill(1.0)
    incidence.sort_indices()

    track_length = np.asarray(incidence.sum(axis=0)).ravel().astype(np.int32)
    scale = np.zeros(npoint, dtype=np.float64)
    linked = track_length >= 2
    scale[linked] = 1.0 / np.sqrt(track_length[linked] - 1.0)
    weighted_incidence = incidence.multiply(scale).tocsr()
    graph = (weighted_incidence @ weighted_incidence.T).tocsr()
    graph.setdiag(0.0)
    graph.eliminate_zeros()
    graph.sum_duplicates()
    graph.sort_indices()
    if graph.nnz and (not np.all(np.isfinite(graph.data)) or np.min(graph.data) <= 0):
        raise ValueError("invalid normalized clique weights")
    asymmetry = graph - graph.T
    if asymmetry.nnz and np.max(np.abs(asymmetry.data)) > 5e-13:
        raise ValueError("normalized clique graph is not symmetric")

    unique_tracks = np.asarray(incidence.sum(axis=1)).ravel().astype(np.int64)
    tracks_ge3 = np.asarray(incidence @ (track_length >= 3).astype(np.float64)).ravel().astype(np.int64)
    track_length_sum = np.asarray(incidence @ track_length.astype(np.float64)).ravel()
    mean_track_length = np.divide(
        track_length_sum,
        unique_tracks,
        out=np.zeros(ncam, dtype=np.float64),
        where=unique_tracks > 0,
    )
    weighted_degree = np.asarray(graph.sum(axis=1)).ravel()
    unweighted_degree = np.diff(graph.indptr).astype(np.int64)
    # Each linked track contributes exactly one to weighted degree.  Keep this
    # identity as a construction audit rather than silently assuming it.
    linked_tracks = np.asarray(incidence @ linked.astype(np.float64)).ravel()
    degree_identity_error = float(np.max(np.abs(weighted_degree - linked_tracks), initial=0.0))

    metadata = {
        "duplicate_incidences_collapsed": duplicates,
        "unique_incidences": int(incidence.nnz),
        "linked_tracks": int(np.count_nonzero(linked)),
        "singleton_tracks": int(np.count_nonzero(track_length == 1)),
        "max_track_length": int(track_length.max(initial=0)),
        "undirected_camera_edges": int(graph.nnz // 2),
        "weighted_degree_identity_max_abs": degree_identity_error,
        "graph_storage_bytes": int(graph.data.nbytes + graph.indices.nbytes + graph.indptr.nbytes),
        "build_seconds": time.perf_counter() - started,
    }
    statistics = {
        "unique_tracks": unique_tracks,
        "tracks_ge3": tracks_ge3,
        "mean_track_length": mean_track_length,
        "weighted_degree": weighted_degree,
        "unweighted_degree": unweighted_degree,
    }
    return graph, statistics, metadata


def core_numbers(indptr, indices):
    """Batagelj--Zaversnik core numbers for a simple undirected CSR graph."""
    n = len(indptr) - 1
    degree = np.diff(indptr).astype(np.int64).copy()
    if n == 0:
        return degree
    max_degree = int(degree.max(initial=0))
    bins = np.bincount(degree, minlength=max_degree + 1).astype(np.int64)
    start = 0
    for d in range(max_degree + 1):
        count = int(bins[d])
        bins[d] = start
        start += count
    position = np.empty(n, dtype=np.int64)
    vertex = np.empty(n, dtype=np.int64)
    next_slot = bins.copy()
    for v in range(n):
        position[v] = next_slot[degree[v]]
        vertex[position[v]] = v
        next_slot[degree[v]] += 1

    for slot in range(n):
        v = int(vertex[slot])
        dv = int(degree[v])
        for edge in range(int(indptr[v]), int(indptr[v + 1])):
            u = int(indices[edge])
            if degree[u] <= dv:
                continue
            du = int(degree[u])
            pu = int(position[u])
            pw = int(bins[du])
            w = int(vertex[pw])
            if u != w:
                vertex[pu], vertex[pw] = w, u
                position[u], position[w] = pw, pu
            bins[du] += 1
            degree[u] -= 1
    return degree


def _component_resistance(graph, nodes, rng, projections, batch=16):
    subgraph = graph[nodes][:, nodes].tocsr()
    n = len(nodes)
    if n == 1 or subgraph.nnz == 0:
        return np.full(n, np.inf), np.full(n, np.nan), {
            "size": n,
            "edges": 0,
            "anchor_local": 0,
            "factor_seconds": 0.0,
            "projection_seconds": 0.0,
        }
    weighted_degree = np.asarray(subgraph.sum(axis=1)).ravel()
    laplacian = sparse.diags(weighted_degree, format="csc") - subgraph.tocsc()
    anchor = int(np.argmax(weighted_degree))
    keep = np.arange(n) != anchor
    factor_started = time.perf_counter()
    factor = splu(laplacian[keep][:, keep].tocsc(), permc_spec="COLAMD")
    factor_seconds = time.perf_counter() - factor_started

    upper = sparse.triu(subgraph, k=1, format="coo")
    edge_count = upper.nnz
    edge_ids = np.arange(edge_count, dtype=np.int64)
    incidence = sparse.csr_matrix(
        (
            np.concatenate((np.sqrt(upper.data), -np.sqrt(upper.data))),
            (
                np.concatenate((edge_ids, edge_ids)),
                np.concatenate((upper.row, upper.col)),
            ),
        ),
        shape=(edge_count, n),
    )
    accumulation = np.zeros(n, dtype=np.float64)
    accumulation2 = np.zeros(n, dtype=np.float64)
    projection_started = time.perf_counter()
    done = 0
    while done < projections:
        width = min(batch, projections - done)
        signs = rng.integers(0, 2, size=(edge_count, width), dtype=np.int8)
        signs = signs.astype(np.float64)
        signs *= 2.0
        signs -= 1.0
        rhs = np.asarray(incidence.T @ signs)
        solution = np.zeros((n, width), dtype=np.float64)
        solution[keep] = factor.solve(rhs[keep])
        solution -= solution.mean(axis=0, keepdims=True)
        squares = solution * solution
        accumulation += squares.sum(axis=1)
        accumulation2 += (squares * squares).sum(axis=1)
        done += width
    estimate = accumulation / projections
    variance_of_mean = np.maximum(accumulation2 / projections - estimate * estimate, 0.0)
    variance_of_mean /= max(projections - 1, 1)
    stderr = np.sqrt(variance_of_mean)
    return estimate, stderr, {
        "size": n,
        "edges": int(edge_count),
        "anchor_local": anchor,
        "anchor_camera": int(nodes[anchor]),
        "factor_seconds": factor_seconds,
        "projection_seconds": time.perf_counter() - projection_started,
    }


def resistance_diagonal(graph, projections=PROJECTIONS, seed=SEED):
    component_count, labels = connected_components(graph, directed=False, return_labels=True)
    rng = np.random.default_rng(seed)
    estimate = np.empty(graph.shape[0], dtype=np.float64)
    stderr = np.empty(graph.shape[0], dtype=np.float64)
    component_reports = []
    for component in range(component_count):
        nodes = np.flatnonzero(labels == component)
        values, errors, report = _component_resistance(graph, nodes, rng, projections)
        estimate[nodes] = values
        stderr[nodes] = errors
        report["component"] = int(component)
        component_reports.append(report)
    return estimate, stderr, labels, component_reports


def exact_resistance_diagonal(graph):
    if connected_components(graph, directed=False, return_labels=False) != 1:
        raise ValueError("exact validation currently requires a connected graph")
    degree = np.asarray(graph.sum(axis=1)).ravel()
    laplacian = np.diag(degree) - graph.toarray()
    return np.diag(np.linalg.pinv(laplacian, rcond=1e-12, hermitian=True))


def stable_descending_rank(values):
    order = np.lexsort((np.arange(len(values), dtype=np.int64), -np.asarray(values)))
    rank = np.empty(len(values), dtype=np.int64)
    rank[order] = np.arange(1, len(values) + 1)
    return rank, order


def stable_ascending_rank(values):
    order = np.lexsort((np.arange(len(values), dtype=np.int64), np.asarray(values)))
    rank = np.empty(len(values), dtype=np.int64)
    rank[order] = np.arange(1, len(values) + 1)
    return rank, order


def camera_row(camera, observation_count, stats, core, score, stderr, score_rank, count_rank, gate):
    return {
        "camera": int(camera),
        "selected": bool(gate[camera]),
        "effective_resistance_diag": float(score[camera]),
        "effective_resistance_rank_desc": int(score_rank[camera]),
        "effective_resistance_relative_stderr": (
            None if not np.isfinite(score[camera]) or score[camera] == 0
            else float(stderr[camera] / score[camera])
        ),
        "observation_count": int(observation_count[camera]),
        "unique_track_count": int(stats["unique_tracks"][camera]),
        "unique_track_count_rank_asc": int(count_rank[camera]),
        "tracks_ge3": int(stats["tracks_ge3"][camera]),
        "mean_track_length": float(stats["mean_track_length"][camera]),
        "weighted_degree": float(stats["weighted_degree"][camera]),
        "unweighted_degree": int(stats["unweighted_degree"][camera]),
        "core_number": int(core[camera]),
    }


def analyze(path: Path, label: str, exact=False, projections=PROJECTIONS, seed=SEED):
    total_started = time.perf_counter()
    dims, camera, point, parse_seconds = read_bal_incidence(path)
    ncam, npoint, nobs = dims
    observation_count = np.bincount(camera, minlength=ncam).astype(np.int64)
    graph, stats, graph_metadata = normalized_clique_graph(ncam, npoint, camera, point)
    core_started = time.perf_counter()
    core = core_numbers(graph.indptr, graph.indices)
    core_seconds = time.perf_counter() - core_started
    score, stderr, component, component_reports = resistance_diagonal(graph, projections, seed)
    score_rank, score_order = stable_descending_rank(score)
    count_rank, _ = stable_ascending_rank(stats["unique_tracks"])

    top_count = max(1, int(math.ceil(0.01 * ncam)))
    top_resistance = np.zeros(ncam, dtype=bool)
    top_resistance[score_order[:top_count]] = True
    weighted_q25 = float(np.quantile(stats["weighted_degree"], 0.25))
    core_q25 = float(np.quantile(core, 0.25))
    local_weak = (stats["weighted_degree"] <= weighted_q25) | (core <= core_q25)
    gate = top_resistance & local_weak

    exact_validation = None
    if exact:
        exact_diag = exact_resistance_diagonal(graph)
        finite = np.isfinite(score) & (exact_diag > np.finfo(float).tiny)
        correlation = float(spearmanr(score[finite], exact_diag[finite]).statistic)
        relative = np.abs(score[finite] - exact_diag[finite]) / exact_diag[finite]
        exact_rank, _ = stable_descending_rank(exact_diag)
        exact_validation = {
            "spearman_rank": correlation,
            "median_relative_error": float(np.median(relative)),
            "max_relative_error": float(np.max(relative)),
            "top_1pct_set_equal": bool(
                set(np.flatnonzero(score_rank <= top_count))
                == set(np.flatnonzero(exact_rank <= top_count))
            ),
            "passes_registered_gate": bool(correlation >= 0.90 and np.median(relative) <= 0.20),
            "exact_diag": exact_diag.tolist(),
        }

    selected = np.flatnonzero(gate)
    top_rows = [
        camera_row(int(i), observation_count, stats, core, score, stderr, score_rank, count_rank, gate)
        for i in score_order[: min(20, ncam)]
    ]
    selected_rows = [
        camera_row(int(i), observation_count, stats, core, score, stderr, score_rank, count_rank, gate)
        for i in selected
    ]
    report = {
        "schema": 1,
        "label": label,
        "input": str(path.resolve()),
        "input_sha256": sha256(path),
        "dimensions": {"cameras": ncam, "points": npoint, "observations": nobs},
        "registered_graph": "normalized point-clique, edge contribution 1/(track_length-1)",
        "estimator": {
            "quantity": "diag of componentwise Moore-Penrose camera Laplacian inverse",
            "method": "Rademacher edge projections with one grounded sparse LU per component",
            "projections": projections,
            "seed": seed,
            "components": component_reports,
        },
        "graph": graph_metadata | {
            "connected_components": int(len(component_reports)),
            "component_sizes": np.bincount(component).tolist(),
        },
        "thresholds": {
            "top_resistance_count": top_count,
            "weighted_degree_q25": weighted_q25,
            "core_q25": core_q25,
        },
        "gate": {
            "selected_count": int(len(selected)),
            "selected_fraction": float(len(selected) / ncam),
            "selected_cameras": selected.tolist(),
            "rows": selected_rows,
        },
        "top_effective_resistance": top_rows,
        "summary_statistics": {
            "observation_count": {
                "min": int(observation_count.min()),
                "median": float(np.median(observation_count)),
                "max": int(observation_count.max()),
            },
            "unique_track_count": {
                "min": int(stats["unique_tracks"].min()),
                "median": float(np.median(stats["unique_tracks"])),
                "max": int(stats["unique_tracks"].max()),
            },
            "weighted_degree": {
                "min": float(stats["weighted_degree"].min()),
                "median": float(np.median(stats["weighted_degree"])),
                "max": float(stats["weighted_degree"].max()),
            },
            "core_number": {
                "min": int(core.min()),
                "median": float(np.median(core)),
                "max": int(core.max()),
            },
            "spearman_log_resistance_vs_negative_log_tracks": float(
                spearmanr(np.log(np.maximum(score, np.finfo(float).tiny)),
                          -np.log1p(stats["unique_tracks"])).statistic
            ),
        },
        "exact_validation": exact_validation,
        "timing": {
            "parse_seconds": parse_seconds,
            "core_seconds": core_seconds,
            "total_seconds": time.perf_counter() - total_started,
        },
    }
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("bal", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--label", required=True)
    parser.add_argument("--exact", action="store_true")
    parser.add_argument("--projections", type=int, default=PROJECTIONS)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    if args.projections < 2:
        raise SystemExit("--projections must be at least 2")
    report = analyze(args.bal, args.label, args.exact, args.projections, args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "label": report["label"],
        "dimensions": report["dimensions"],
        "graph": report["graph"],
        "gate": report["gate"],
        "exact_validation": report["exact_validation"],
        "timing": report["timing"],
    }, indent=2))


if __name__ == "__main__":
    main()
