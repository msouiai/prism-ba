#!/usr/bin/env python3
"""Small exact checks for the C1 graph diagnostic; no BAL grid."""
from __future__ import annotations

import json
from pathlib import Path

import networkx as nx
import numpy as np
from scipy import sparse

import graph_observability as graph


def check_core_numbers():
    rng = np.random.default_rng(630001)
    cases = []
    for n in (2, 5, 17, 40):
        for probability in (0.08, 0.25, 0.8):
            upper = rng.random((n, n)) < probability
            upper = np.triu(upper, 1)
            adjacency = upper | upper.T
            csr = sparse.csr_matrix(adjacency.astype(np.float64))
            got = graph.core_numbers(csr.indptr, csr.indices)
            expected_map = nx.core_number(nx.from_numpy_array(adjacency))
            expected = np.asarray([expected_map[i] for i in range(n)])
            if not np.array_equal(got, expected):
                raise AssertionError((n, probability, got, expected))
            cases.append({"n": n, "probability": probability, "max_core": int(got.max(initial=0))})
    return cases


def check_normalized_clique():
    # Track 0: cameras 0,1,2. Track 1: cameras 2,3. Track 2: singleton 3.
    camera = np.asarray([0, 1, 2, 2, 3, 3], dtype=np.int32)
    point = np.asarray([0, 0, 0, 1, 1, 2], dtype=np.int32)
    adjacency, stats, metadata = graph.normalized_clique_graph(4, 3, camera, point)
    expected = np.asarray([
        [0, .5, .5, 0],
        [.5, 0, .5, 0],
        [.5, .5, 0, 1],
        [0, 0, 1, 0],
    ])
    if not np.allclose(adjacency.toarray(), expected, rtol=0, atol=1e-15):
        raise AssertionError(adjacency.toarray())
    if not np.allclose(stats["weighted_degree"], [1, 1, 2, 1], atol=1e-15):
        raise AssertionError(stats["weighted_degree"])
    if metadata["weighted_degree_identity_max_abs"] > 1e-14:
        raise AssertionError(metadata)
    return metadata


def check_resistance_estimator():
    # A weighted path has a non-uniform exact diag(L+); fixed random projections
    # must be deterministic and agree in rank/value at a loose synthetic bound.
    n = 25
    row = np.arange(n - 1)
    weight = np.linspace(0.5, 2.0, n - 1)
    adjacency = sparse.coo_matrix(
        (np.r_[weight, weight], (np.r_[row, row + 1], np.r_[row + 1, row])),
        shape=(n, n),
    ).tocsr()
    first, error1, _, _ = graph.resistance_diagonal(adjacency, projections=4096, seed=630001)
    second, error2, _, _ = graph.resistance_diagonal(adjacency, projections=4096, seed=630001)
    exact = graph.exact_resistance_diagonal(adjacency)
    correlation = float(np.corrcoef(first, exact)[0, 1])
    median_relative = float(np.median(np.abs(first - exact) / exact))
    if not np.array_equal(first, second) or not np.array_equal(error1, error2):
        raise AssertionError("fixed-seed estimator is not deterministic")
    if correlation < 0.98 or median_relative > 0.08:
        raise AssertionError((correlation, median_relative))
    return {"pearson": correlation, "median_relative_error": median_relative}


def main():
    report = {
        "passed": True,
        "core_cases": check_core_numbers(),
        "normalized_clique": check_normalized_clique(),
        "resistance_estimator": check_resistance_estimator(),
    }
    output = Path(__file__).with_name("c1-verification.json")
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
