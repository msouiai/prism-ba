#!/usr/bin/env python3
"""Registered B6 PCG synchronization and launch measurements."""
from pathlib import Path
import argparse
import json
import math
import re
import statistics
import subprocess

import native_light as N

P = Path(__file__).resolve().parent
BINARY = P / "build" / "prism-b6"
PARENT = Path(N.CHAMPION["binary"])
PROTOCOL = P / "B6_PROTOCOL.md"
ARMS = {"off": {}, "batched": {"OCA_W5_CG_BATCH": "1"}}


def register():
    subprocess.run(["python3", str(N.FROZEN / "build.py"), "--check-only"], check=True)
    build = json.loads((P / "b6-build-manifest.json").read_text())
    assert N.sha(BINARY) == build["binary_sha256"]
    assert all(N.sha(path) == digest for path, digest in build["sources"].items())
    old = json.loads((P / "b1-registration.json").read_text())
    reg = {
        "arms": ARMS, "practical": old["practical"], "tails": old["tails"],
        "muell": old["muell"], "panel_repetitions": 3, "tail_repetitions": 5,
        "binary": str(BINARY), "binary_sha256": N.sha(BINARY),
        "parent_binary": str(PARENT), "parent_binary_sha256": N.sha(PARENT),
        "build_manifest": build, "protocol_sha256": N.sha(PROTOCOL),
        "cohort_rule": "Fresh paired rows; alternating arms and reversed cells on odd repetitions",
        "registered_arm": "Device-result cuBLAS dot pairs plus fused x/r and p PCG vector updates",
    }
    path = P / "b6-registration.json"
    if path.exists():
        assert json.loads(path.read_text()) == reg
    else:
        N.write(path, reg)
    return reg


def enrich(row):
    log = (P / row["source"] / "stdout.log").read_text()
    active = re.search(r"W5_CG_BATCH active n=(\d+)", log)
    summary = re.search(r"W5_CG_BATCH summary dot_pairs=(\d+)", log)
    profile = re.search(
        r"\[PROFILE\] assembly=(\S+)s pointfactor\+rhs=(\S+)s krylov=(\S+)s candidates=(\S+)s", log)
    row["cg_batch_active"] = bool(active)
    if active:
        row["cg_dimension"] = int(active[1])
    if summary:
        row["batched_dot_pairs"] = int(summary[1])
    if profile:
        row["profile_seconds"] = {
            "assembly": float(profile[1]), "pointfactor_rhs": float(profile[2]),
            "krylov": float(profile[3]), "candidates": float(profile[4]),
        }
    N.write(P / row["source"] / "result.json", row)
    return row


def execute(reg, stage, cells, arms, reps, extra=None):
    rows = []
    extra = extra or {}
    for rep in range(reps):
        ordered_cells, ordered_arms = list(cells), list(arms)
        if rep % 2:
            ordered_cells.reverse(); ordered_arms.reverse()
        for cell in ordered_cells:
            for arm in ordered_arms:
                binary = PARENT if arm == "parent-off" else BINARY
                flags = {} if arm == "parent-off" else dict(ARMS[arm], **extra)
                folder = P / "evidence" / stage / f"{cell.get('cell', cell['scene'])}-{arm}-{rep}"
                row = N.run(folder, cell, arm, rep, binary, flags, PROTOCOL,
                            reg["build_manifest"])
                rows.append(enrich(row))
                N.write(P / f"{stage}-results.json", rows)
    return rows


def summarize(rows, arms=("off", "batched")):
    cells = []
    for cid in sorted({row["cell"] for row in rows}):
        rec = {"cell": cid}
        for arm in arms:
            group = [row for row in rows if row["cell"] == cid and row["arm"] == arm]
            hit_times = [row["target_seconds"] for row in group if row["target_seconds"] is not None]
            rec[arm] = {
                "n": len(group), "hits": sum(row["hit"] for row in group),
                "median_target_seconds": statistics.median(hit_times) if hit_times else None,
                "target_range": [min(hit_times), max(hit_times)] if hit_times else None,
                "median_native_seconds": statistics.median(row["native_seconds"] for row in group),
                "native_range": [min(row["native_seconds"] for row in group),
                                 max(row["native_seconds"] for row in group)],
                "median_products": statistics.median(row["matvecs"] for row in group),
                "product_range": [min(row["matvecs"] for row in group),
                                  max(row["matvecs"] for row in group)],
                "product_values": [row["matvecs"] for row in group],
                "median_endpoint": statistics.median(row["cost"] for row in group),
                "endpoint_range": [min(row["cost"] for row in group), max(row["cost"] for row in group)],
                "median_outers": statistics.median(row["outers"] for row in group),
                "median_rejects": statistics.median(row["rejects"] for row in group),
            }
            pairs = [row["batched_dot_pairs"] for row in group if "batched_dot_pairs" in row]
            if pairs:
                rec[arm]["median_batched_dot_pairs"] = statistics.median(pairs)
        if all(rec[arm]["median_target_seconds"] is not None for arm in arms):
            rec["time_ratio"] = rec[arms[1]]["median_target_seconds"] / rec[arms[0]]["median_target_seconds"]
        rec["product_ratio"] = rec[arms[1]]["median_products"] / rec[arms[0]]["median_products"]
        rec["endpoint_delta"] = rec[arms[1]]["median_endpoint"] / rec[arms[0]]["median_endpoint"] - 1
        cells.append(rec)
    ratios = [cell["time_ratio"] for cell in cells if "time_ratio" in cell]
    return {
        "rows": len(rows),
        "geometric_mean_time_ratio": math.exp(sum(map(math.log, ratios)) / len(ratios)) if ratios else None,
        "all_median_product_counts_equal": all(cell["product_ratio"] == 1 for cell in cells),
        "cells": cells,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["compatibility", "panel", "profile", "muell", "tails"])
    args = parser.parse_args(); reg = register()
    calm = next(cell for cell in reg["practical"] if cell["cell"] == "ladybug-539-1.01")
    if args.stage == "compatibility":
        rows = execute(reg, "b6-compatibility", [calm], ["off", "parent-off"], 3)
        med = {arm: statistics.median(row["cost"] for row in rows if row["arm"] == arm)
               for arm in ("off", "parent-off")}
        result = {"rows": len(rows), "medians": med,
                  "relative_delta": med["off"] / med["parent-off"] - 1}
        result["passed"] = abs(result["relative_delta"]) < .0015
        N.write(P / "b6-compatibility-summary.json", result); assert result["passed"], result
    elif args.stage == "panel":
        assert json.loads((P / "b6-compatibility-summary.json").read_text())["passed"]
        result = summarize(execute(reg, "b6-panel", reg["practical"], list(ARMS), 3))
        N.write(P / "b6-panel-summary.json", result)
    elif args.stage == "profile":
        traf = next(cell for cell in reg["practical"] if cell["cell"] == "trafalgar-138-1.005")
        rows = execute(reg, "b6-profile", [traf, reg["muell"]], list(ARMS), 3,
                       {"OCA_PROFILE": "1"})
        result = summarize(rows)
        for cell in result["cells"]:
            for arm in ARMS:
                group = [row for row in rows if row["cell"] == cell["cell"] and row["arm"] == arm]
                cell[arm]["median_profile_seconds"] = {
                    phase: statistics.median(row["profile_seconds"][phase] for row in group)
                    for phase in ("assembly", "pointfactor_rhs", "krylov", "candidates")
                }
        N.write(P / "b6-profile-summary.json", result)
    elif args.stage == "muell":
        result = summarize(execute(reg, "b6-muell", [reg["muell"]], list(ARMS), 3))
        N.write(P / "b6-muell-summary.json", result)
    else:
        result = summarize(execute(reg, "b6-tails", list(reg["tails"].values()), list(ARMS), 5))
        N.write(P / "b6-tails-summary.json", result)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
