#!/usr/bin/env python3
"""Fixed N=150/arm Final3068 non-inferiority extension for B6v7."""
from pathlib import Path
import hashlib
import json
import math
import statistics

import native_light as N

P = Path(__file__).resolve().parent
PROTOCOL = P / "B6V7_EXTENSION_PROTOCOL.md"
BINARY = P / "build" / "prism-b6v7"
BASE_ROWS = P / "b6v7-final-pooled-results.json"
FRESH_ROWS = P / "b6v7-extension-results.json"
SUMMARY = P / "b6v7-extension-summary.json"
TARGET_N = 150
OLD_N = 20
ADD_N = TARGET_N - OLD_N
MARGIN = 0.15
Z_ONE = 1.6448536269514722
Z_TWO = 1.959963984540054
EXPECTED = {
    BINARY: "b1b125b55a5d4ff1415fd379a8fee269609f42dffe9409fe0f9b831e41629799",
    P / "B6V7_PROTOCOL.md": "115226c65db0412fbb7ab19532fe55a967f75ba4351e03b09d81997373877593",
    BASE_ROWS: "1383186b39aed663e0867799e62121573c4d87c48b5bdc771c8de51ece085b1c",
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def wilson(k, n, z):
    p = k / n
    den = 1 + z * z / n
    center = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return center - half, center + half


def fisher_two_sided(a, b, c, d):
    # Conditional hypergeometric test with fixed margins.  Sum tables no more
    # likely than the observed table, matching the conventional two-sided test.
    row1, row2, col1 = a + b, c + d, a + c
    total = row1 + row2
    lo, hi = max(0, col1 - row2), min(row1, col1)
    den = math.comb(total, col1)
    def prob(x):
        return math.comb(row1, x) * math.comb(row2, col1 - x) / den
    observed = prob(a)
    return min(1.0, sum(prob(x) for x in range(lo, hi + 1)
                        if prob(x) <= observed * (1 + 1e-12)))


def arm_summary(rows, arm):
    g = [r for r in rows if r["arm"] == arm]
    hits = [r for r in g if r["hit"]]
    assert len(g) == TARGET_N
    return {
        "n": len(g),
        "hits": len(hits),
        "hit_rate": len(hits) / len(g),
        "wilson95": wilson(len(hits), len(g), Z_TWO),
        "conditional_target_median": statistics.median(r["target_seconds"] for r in hits) if hits else None,
        "conditional_target_range": [min(r["target_seconds"] for r in hits), max(r["target_seconds"] for r in hits)] if hits else None,
        "native_seconds_median": statistics.median(r["native_seconds"] for r in g),
        "native_seconds_mean": statistics.fmean(r["native_seconds"] for r in g),
        "endpoint_median": statistics.median(r["cost"] for r in g),
        "endpoint_range": [min(r["cost"] for r in g), max(r["cost"] for r in g)],
        "products_median": statistics.median(r["matvecs"] for r in g),
        "outers_median": statistics.median(r["outers"] for r in g),
        "rejects_median": statistics.median(r["rejects"] for r in g),
    }


def main():
    for path, digest in EXPECTED.items():
        assert sha(path) == digest, (path, sha(path), digest)
    reg = json.loads((P / "b6v7-registration.json").read_text())
    assert N.sha(BINARY) == reg["binary_sha256"]
    final = reg["tails"]["final-3068"]
    old = json.loads(BASE_ROWS.read_text())
    assert sum(r["arm"] == "dots" for r in old) == OLD_N
    assert sum(r["arm"] == "gated" for r in old) == OLD_N

    fresh = []
    if FRESH_ROWS.exists():
        fresh = json.loads(FRESH_ROWS.read_text())
    completed = {(r["arm"], r["rep"]) for r in fresh}
    for i in range(ADD_N):
        rep = OLD_N + i
        order = ["dots", "gated"] if i % 2 == 0 else ["gated", "dots"]
        for arm in order:
            if (arm, rep) in completed:
                continue
            flags = reg["arms"][arm]
            folder = P / "evidence" / "b6v7-extension" / f"final-3068-{arm}-{rep}"
            row = N.run(folder, final, arm, rep, BINARY, flags, PROTOCOL,
                        reg["build_manifest"])
            fresh.append(row)
            N.write(FRESH_ROWS, fresh)

    assert sum(r["arm"] == "dots" for r in fresh) == ADD_N
    assert sum(r["arm"] == "gated" for r in fresh) == ADD_N
    combined = old + fresh
    arms = {arm: arm_summary(combined, arm) for arm in ("dots", "gated")}
    pd, pg = arms["dots"]["hit_rate"], arms["gated"]["hit_rate"]
    ld, ud = wilson(arms["dots"]["hits"], TARGET_N, Z_ONE)
    lg, ug = wilson(arms["gated"]["hits"], TARGET_N, Z_ONE)
    diff = pg - pd
    lower = diff - math.sqrt((pg - lg) ** 2 + (ud - pd) ** 2)
    p_fisher = fisher_two_sided(
        arms["gated"]["hits"], TARGET_N - arms["gated"]["hits"],
        arms["dots"]["hits"], TARGET_N - arms["dots"]["hits"])
    summary = {
        "protocol_sha256": sha(PROTOCOL),
        "binary_sha256": sha(BINARY),
        "base_rows_sha256": EXPECTED[BASE_ROWS],
        "fresh_n_per_arm": ADD_N,
        "total_n_per_arm": TARGET_N,
        "arms": arms,
        "comparison": {
            "hit_rate_delta_gated_minus_dots": diff,
            "newcombe_wilson_one_sided_95_lower": lower,
            "noninferiority_margin": -MARGIN,
            "noninferior": lower > -MARGIN,
            "fisher_two_sided_p": p_fisher,
            "conditional_target_time_ratio": (
                arms["gated"]["conditional_target_median"] /
                arms["dots"]["conditional_target_median"]),
            "native_wall_mean_ratio": (
                arms["gated"]["native_seconds_mean"] /
                arms["dots"]["native_seconds_mean"]),
        },
    }
    N.write(SUMMARY, summary)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
