#!/usr/bin/env python3
"""Run and summarize the preregistered D14 fixed-system cohort."""
from __future__ import annotations

import fcntl
import hashlib
import json
import pathlib
import re
import statistics
import subprocess
import time

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BINARY = pathlib.Path("/tmp/prism-wave6-d14/ca_fixed")
CAPTURES = pathlib.Path("/workspace/prism-schur-physics")
EVIDENCE = HERE / "evidence"
EVIDENCE.mkdir(exist_ok=True)
CELLS = {
    "muell-o11": CAPTURES / "muell-gba146-o11",
    "muell-o12": CAPTURES / "muell-gba146-o12",
    "ladybug-o8": CAPTURES / "ladybug-598-o8",
    "final-o0": CAPTURES / "final-1936-o0",
}


def sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def scalar(value: str):
    if value in {"0", "1"}:
        return int(value)
    try:
        return int(value)
    except ValueError:
        return float(value)


def parse(log: str):
    rows = []
    pairs = []
    for line in log.splitlines():
        if line.startswith("RESULT "):
            row = {key: scalar(value) if key != "arm" else value
                   for key, value in re.findall(r"(\w+)=([^ ]+)", line)}
            rows.append(row)
        elif line.startswith("PAIR "):
            pairs.append({key: scalar(value)
                          for key, value in re.findall(r"(\w+)=([^ ]+)", line)})
    assert len(rows) == 20 and len(pairs) == 10, (len(rows), len(pairs))
    return rows, pairs


def summarize(rows, pairs):
    out = {"n_pairs": len(pairs),
           "median_relative_solution_difference": statistics.median(
               p["relative_solution_difference"] for p in pairs)}
    for arm in ("standard", "cgcg"):
        selected = [r for r in rows if r["arm"] == arm]
        out[arm] = {
            "hits": sum(r["hit"] for r in selected),
            "negative": sum(r["negative"] for r in selected),
            "audit_failed": sum(r["audit_failed"] for r in selected),
            "median_ms": statistics.median(r["total_ms"] for r in selected),
            "range_ms": [min(r["total_ms"] for r in selected), max(r["total_ms"] for r in selected)],
            "median_updates": statistics.median(r["updates"] for r in selected),
            "median_products": statistics.median(r["products"] for r in selected),
            "median_reductions": statistics.median(r["reductions"] for r in selected),
            "median_true_relative": statistics.median(r["true_relative"] for r in selected),
            "min_den_ratio": min(r["min_den_ratio"] for r in selected),
        }
    out["time_ratio"] = out["cgcg"]["median_ms"] / out["standard"]["median_ms"]
    out["product_delta"] = out["cgcg"]["median_products"] - out["standard"]["median_products"]
    out["reduction_ratio"] = out["cgcg"]["median_reductions"] / out["standard"]["median_reductions"]
    return out


def main() -> None:
    assert BINARY.exists()
    manifest = {
        "binary": str(BINARY),
        "binary_sha256": sha(BINARY),
        "protocol_sha256": sha(ROOT / "research" / "eta2_wave6" / "D14_CA_PCG_PROTOCOL.md"),
        "cells": {},
    }
    complete = {}
    summaries = {}
    with open("/tmp/prism_gpu.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        for name, capture in CELLS.items():
            log_path = EVIDENCE / f"{name}.log"
            started = time.perf_counter()
            proc = subprocess.run([str(BINARY), str(capture)], text=True,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  check=True, timeout=600)
            wall = time.perf_counter() - started
            log_path.write_text(proc.stdout)
            rows, pairs = parse(proc.stdout)
            complete[name] = {"rows": rows, "pairs": pairs}
            summaries[name] = summarize(rows, pairs)
            capture_manifest = capture / "capture_manifest.json"
            manifest["cells"][name] = {
                "capture": str(capture),
                "capture_manifest_sha256": sha(capture_manifest) if capture_manifest.exists() else None,
                "log_sha256": sha(log_path),
                "process_wall_seconds": wall,
            }
            print(name, json.dumps(summaries[name], sort_keys=True), flush=True)
    hard = [summaries[x] for x in ("muell-o11", "muell-o12")]
    passed = (
        all(s["standard"]["hits"] == 10 and s["cgcg"]["hits"] == 10 for s in summaries.values())
        and all(s["cgcg"]["negative"] == 0 and s["cgcg"]["audit_failed"] == 0 for s in summaries.values())
        and any(s["time_ratio"] <= 0.95 for s in hard)
    )
    result = {"manifest": manifest, "cells": complete}
    summary = {"cells": summaries, "advance_native": passed,
               "hard_best_time_ratio": min(s["time_ratio"] for s in hard),
               "decision_rule": "advance only with >=5% hard-system speedup and all correctness gates"}
    (ROOT / "research" / "eta2_wave6" / "d14-fixed-results.json").write_text(json.dumps(result, indent=2) + "\n")
    (ROOT / "research" / "eta2_wave6" / "d14-fixed-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (HERE / "run-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
