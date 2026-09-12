#!/usr/bin/env python3
"""Registered adaptive robust-exit compatibility, tails, and panel cohorts."""
from pathlib import Path
import argparse, json, math, re, statistics, subprocess

import native_light as N

P = Path(__file__).resolve().parent
W4 = P.parent / "eta2_wave4"
BINARY = P / "build" / "prism-a2"
PARENT = W4 / "build" / "prism-o5"
ARMS = {
    "off": {},
    "adaptive": {"OCA_W5_CAUCHY": "1", "OCA_W5_ADAPTIVE_EXIT": "1"},
}


def register():
    subprocess.run(["python3", str(N.FROZEN / "build.py"), "--check-only"], check=True)
    build = json.loads((P / "a2-build-manifest.json").read_text())
    assert N.sha(BINARY) == build["binary_sha256"]
    assert N.sha(PARENT) == build["parent_o5_binary_sha256"]
    assert all(N.sha(path) == digest for path, digest in build["sources"].items())
    old = json.loads((W4 / "aside-registration.json").read_text())
    reg = {
        "arms": ARMS, "cells": {k: old["cells"][k] for k in ("venice-52", "final-3068")},
        "practical": old["practical"], "tail_repetitions": 10, "panel_repetitions": 3,
        "binary": str(BINARY), "binary_sha256": N.sha(BINARY),
        "parent_binary": str(PARENT), "parent_binary_sha256": N.sha(PARENT),
        "build_manifest": build, "protocol_sha256": N.sha(P / "A2_A4_PROTOCOL.md"),
    }
    path = P / "a2-registration.json"
    if path.exists():
        assert json.loads(path.read_text()) == reg
    else:
        N.write(path, reg)
    return reg


def enrich(row):
    log = (P / row["source"] / "stdout.log").read_text()
    row["exit_checks"] = [dict(re.findall(r"(\w+)=(\S+)", line))
                          for line in log.splitlines() if line.startswith("W5_EXIT_CHECK ")]
    row["robust_final"] = [line for line in log.splitlines() if line.startswith("W5_FINAL ")]
    N.write(P / row["source"] / "result.json", row)
    return row


def execute(reg, stage, cells, arms, repetitions):
    rows = []
    for rep in range(repetitions):
        ordered_cells = list(cells)
        ordered_arms = list(arms)
        if rep % 2:
            ordered_cells.reverse(); ordered_arms.reverse()
        for cell in ordered_cells:
            for arm in ordered_arms:
                binary = PARENT if arm == "parent-off" else BINARY
                flags = {} if arm == "parent-off" else ARMS[arm]
                folder = P / "evidence" / stage / f"{cell.get('cell',cell['scene'])}-{arm}-{rep}"
                rows.append(enrich(N.run(folder, cell, arm, rep, binary, flags,
                                         P / "A2_A4_PROTOCOL.md", reg["build_manifest"])))
                N.write(P / f"{stage}-results.json", rows)
    return rows


def summarize_tails(rows):
    groups = []
    for scene in ("venice-52", "final-3068"):
        for arm in ARMS:
            group = [r for r in rows if r["scene"] == scene and r["arm"] == arm]
            times = [r["target_seconds"] for r in group if r["hit"]]
            groups.append({
                "scene": scene, "arm": arm, "n": len(group),
                "hits": sum(r["hit"] for r in group),
                "median_endpoint": statistics.median(r["cost"] for r in group),
                "endpoint_range": [min(r["cost"] for r in group), max(r["cost"] for r in group)],
                "conditional_median_target_seconds": statistics.median(times) if times else None,
                "target_seconds_range": [min(times), max(times)] if times else None,
                "median_native_seconds": statistics.median(r["native_seconds"] for r in group),
                "median_rejects": statistics.median(r["rejects"] for r in group),
                "median_matvecs": statistics.median(r["matvecs"] for r in group),
                "median_exit_checks": statistics.median(len(r["exit_checks"]) for r in group),
            })
    off = {g["scene"]: g for g in groups if g["arm"] == "off"}
    adaptive = {g["scene"]: g for g in groups if g["arm"] == "adaptive"}
    proceed = (adaptive["final-3068"]["hits"] >= off["final-3068"]["hits"] and
               any(adaptive[s]["hits"] > off[s]["hits"] for s in off))
    result = {"rows": len(rows), "groups": groups, "proceed_to_panel": proceed}
    N.write(P / "a2-tails-summary.json", result)
    return result


def summarize_panel(rows):
    cells = []
    ratios = []
    slower_disjoint = faster_disjoint = 0
    for cid in sorted({r["cell"] for r in rows}):
        record = {"cell": cid}
        groups = {}
        for arm in ARMS:
            group = [r for r in rows if r["cell"] == cid and r["arm"] == arm]
            values = [r["target_seconds"] for r in group]
            assert all(x is not None for x in values), (cid, arm)
            groups[arm] = values
            record[arm] = {"median": statistics.median(values),
                           "range": [min(values), max(values)]}
        ratio = record["adaptive"]["median"] / record["off"]["median"]
        ratios.append(ratio); record["ratio"] = ratio
        if record["adaptive"]["range"][0] > record["off"]["range"][1]: slower_disjoint += 1
        if record["adaptive"]["range"][1] < record["off"]["range"][0]: faster_disjoint += 1
        cells.append(record)
    geo = math.exp(sum(math.log(x) for x in ratios) / len(ratios))
    result = {"rows": len(rows), "geometric_mean_ratio": geo,
              "faster_disjoint_cells": faster_disjoint,
              "slower_disjoint_cells": slower_disjoint, "cells": cells,
              "promotion_time_gate_passed": geo <= 1.02}
    N.write(P / "a2-practical-summary.json", result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["compatibility", "smoke", "tails", "practical"])
    args = parser.parse_args(); reg = register()
    if args.stage == "compatibility":
        cell = next(x for x in reg["practical"] if x["cell"] == "ladybug-539-1.01")
        rows = execute(reg, "a2-compatibility", [cell], ["off", "parent-off"], 3)
        med = {arm: statistics.median(r["cost"] for r in rows if r["arm"] == arm)
               for arm in ("off", "parent-off")}
        result = {"rows": len(rows), "medians": med,
                  "relative_delta": med["off"] / med["parent-off"] - 1,
                  "passed": abs(med["off"] / med["parent-off"] - 1) < 1e-8}
        N.write(P / "a2-compatibility-summary.json", result)
        assert result["passed"], result
    elif args.stage == "smoke":
        assert json.loads((P / "a2-compatibility-summary.json").read_text())["passed"]
        cell = next(x for x in reg["practical"] if x["cell"] == "ladybug-539-1.01")
        rows = execute(reg, "a2-smoke", [cell], ["adaptive"], 1)
        assert rows[0]["exit_checks"] and rows[0]["robust_final"]
        result = {"passed": True, "exit_checks": rows[0]["exit_checks"],
                  "final": rows[0]["robust_final"]}
        N.write(P / "a2-smoke-summary.json", result)
    elif args.stage == "tails":
        assert json.loads((P / "a2-smoke-summary.json").read_text())["passed"]
        rows = execute(reg, "a2-tails", list(reg["cells"].values()), list(ARMS), 10)
        result = summarize_tails(rows)
    else:
        tails = json.loads((P / "a2-tails-summary.json").read_text())
        if not tails["proceed_to_panel"]:
            N.write(P / "a2-practical-summary.json", {"skipped": True,
                    "reason": "Preregistered tail gate failed"})
            print("SKIP practical: tail gate failed", flush=True); return
        rows = execute(reg, "a2-practical", reg["practical"], list(ARMS), 3)
        result = summarize_panel(rows)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
