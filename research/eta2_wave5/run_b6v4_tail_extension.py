#!/usr/bin/env python3
"""Preregistered N=30 pooled reliability check for B6v4 pruning."""
from pathlib import Path
import json
import math
import statistics

import native_light as N
import run_b6v4 as V4

P = Path(__file__).resolve().parent
PROTOCOL = P / "B6V4_TAIL_EXTENSION_PROTOCOL.md"


def fisher_two_sided(a, b, c, d):
    # Table [[a,b],[c,d]], conditioning on margins.
    n1, n2, good = a + b, c + d, a + c
    total = n1 + n2
    lo, hi = max(0, good - n2), min(n1, good)
    def probability(x):
        return math.comb(good, x) * math.comb(total - good, n1 - x) / math.comb(total, n1)
    observed = probability(a)
    return min(1.0, sum(probability(x) for x in range(lo, hi + 1)
                        if probability(x) <= observed * (1 + 1e-12)))


def wilson(k, n):
    z = 1.959963984540054
    centre = (k / n + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(k * (n-k) / n**3 + z*z / (4*n*n)) / (1 + z*z/n)
    return [centre - half, centre + half]


def run_extension():
    reg = V4.register(); cell = reg["tails"]["final-3068"]
    rows = []
    for rep in range(20):
        arms = ["prep", "dots-prep"] if rep % 2 == 0 else ["dots-prep", "prep"]
        for arm in arms:
            folder = P / "evidence" / "b6v4-tail-extension" / f"final-3068-{arm}-{rep}"
            row = N.run(folder, cell, arm, rep, V4.BINARY, V4.ARMS[arm], PROTOCOL,
                        reg["build_manifest"])
            rows.append(V4.enrich(row))
            N.write(P / "b6v4-tail-extension-results.json", rows)
    return rows


def main():
    new = run_extension()
    old4 = json.loads((P / "b6v4-tails-results.json").read_text())
    old5 = json.loads((P / "b6v5-tails-final-results.json").read_text())
    cohorts = {
        "off": [r for r in old4 + old5 if r["scene"] == "final-3068" and r["arm"] == "off"],
        "prep": [r for r in old4 + new if r["scene"] == "final-3068" and r["arm"] == "prep"],
        "dots": [r for r in old4 + old5 if r["scene"] == "final-3068" and r["arm"] == "dots"],
        "dots-prep": [r for r in old4 + new if r["scene"] == "final-3068" and r["arm"] == "dots-prep"],
    }
    assert all(len(rows) == 30 for rows in cohorts.values())
    result = {
        "protocol_sha256": N.sha(PROTOCOL),
        "cohort_sources": {
            "controls": ["b6v4-tails-results.json", "b6v5-tails-final-results.json"],
            "active": ["b6v4-tails-results.json", "b6v4-tail-extension-results.json"],
        },
        "arms": {}, "comparisons": {},
    }
    for arm, rows in cohorts.items():
        hits = [r for r in rows if r["hit"]]
        result["arms"][arm] = {
            "n": len(rows), "hits": len(hits), "hit_rate": len(hits) / len(rows),
            "wilson95": wilson(len(hits), len(rows)),
            "conditional_target_median": statistics.median(r["target_seconds"] for r in hits),
            "conditional_target_range": [min(r["target_seconds"] for r in hits),
                                         max(r["target_seconds"] for r in hits)],
            "endpoint_median": statistics.median(r["cost"] for r in rows),
            "endpoint_range": [min(r["cost"] for r in rows), max(r["cost"] for r in rows)],
        }
    for control, active in (("off", "prep"), ("dots", "dots-prep")):
        x, y = result["arms"][control], result["arms"][active]
        p = fisher_two_sided(x["hits"], x["n"]-x["hits"],
                             y["hits"], y["n"]-y["hits"])
        delta = y["hit_rate"] - x["hit_rate"]
        result["comparisons"][f"{active}_vs_{control}"] = {
            "hit_rate_delta": delta, "fisher_two_sided_p": p,
            "evidence_of_registered_loss": delta <= -.15 and p < .05,
        }
    N.write(P / "b6v4-tail-extension-summary.json", result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
