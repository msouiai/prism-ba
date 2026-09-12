#!/usr/bin/env python3
"""Registered factored-Jacobian storage measurements."""
from pathlib import Path
import argparse
import json
import math
import re
import statistics
import subprocess

import native_light as N

P = Path(__file__).resolve().parent
BINARY = P / "build" / "prism-b1"
PARENT = Path(N.CHAMPION["binary"])
ARMS = {"off": {}, "factored": {"OCA_W5_FACTORED_J": "1"}}


def register():
    subprocess.run(["python3", str(N.FROZEN / "build.py"), "--check-only"], check=True)
    build = json.loads((P / "b1-build-manifest.json").read_text())
    assert N.sha(BINARY) == build["binary_sha256"]
    assert all(N.sha(path) == digest for path, digest in build["sources"].items())
    old = json.loads((P.parent / "eta2_wave4" / "aside-registration.json").read_text())
    audit = {
        "scene": "ladybug-49", "cell": "ladybug-49-audit",
        "path": "/workspace/bal/ladybug-49.txt",
        "input_sha256": N.sha("/workspace/bal/ladybug-49.txt"),
        "target": 13713.770267554755, "cap": 12,
    }
    muell = {
        "scene": "muell-gba146", "cell": "muell-gba146",
        "path": "/workspace/bal/muell-gba146.txt",
        "input_sha256": N.sha("/workspace/bal/muell-gba146.txt"),
        "target": 1946488.746262194, "cap": 12,
    }
    reg = {
        "arms": ARMS, "audit": audit, "practical": old["practical"],
        "tails": {k: old["cells"][k] for k in ("venice-52", "final-3068")},
        "muell": muell, "panel_repetitions": 3, "tail_repetitions": 5,
        "binary": str(BINARY), "binary_sha256": N.sha(BINARY),
        "parent_binary": str(PARENT), "parent_binary_sha256": N.sha(PARENT),
        "build_manifest": build, "protocol_sha256": N.sha(P / "B1_PROTOCOL.md"),
        "cohort_rule": "Fresh paired rows; alternating arms and reversed cells on odd repetitions",
        "registered_arm": "OCA_W5_FACTORED_J=1 with 13-value FP32 camera-major factors and retained 6-value point rows",
    }
    path = P / "b1-registration.json"
    if path.exists():
        assert json.loads(path.read_text()) == reg
    else:
        N.write(path, reg)
    return reg


def enrich(row):
    log = (P / row["source"] / "stdout.log").read_text()
    audit = re.search(
        r"W5_FACTORED_AUDIT rel_frob=(\S+) max_abs=(\S+) max_reference=(\S+) observations=(\d+)",
        log,
    )
    active = re.search(
        r"\[w5-factored\] active values_per_obs=(\d+) cross_bytes_saved=(\d+) total_fragment_bytes_saved=(\d+)",
        log,
    )
    profile = re.search(
        r"\[PROFILE\] assembly=(\S+)s pointfactor\+rhs=(\S+)s krylov=(\S+)s candidates=(\S+)s",
        log,
    )
    row["factored_active"] = bool(active)
    if active:
        row["factored_storage"] = {
            "values_per_observation": int(active[1]),
            "cross_bytes_saved": int(active[2]),
            "total_fragment_bytes_saved": int(active[3]),
        }
    if audit:
        row["fragment_audit"] = {
            "relative_frobenius_error": float(audit[1]),
            "max_absolute_error": float(audit[2]),
            "max_reference_magnitude": float(audit[3]),
            "observations": int(audit[4]),
        }
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
        ordered_cells = list(cells)
        ordered_arms = list(arms)
        if rep % 2:
            ordered_cells.reverse()
            ordered_arms.reverse()
        for cell in ordered_cells:
            for arm in ordered_arms:
                binary = PARENT if arm == "parent-off" else BINARY
                flags = {} if arm == "parent-off" else dict(ARMS[arm], **extra)
                folder = P / "evidence" / stage / f"{cell.get('cell', cell['scene'])}-{arm}-{rep}"
                rows.append(enrich(N.run(folder, cell, arm, rep, binary, flags,
                                         P / "B1_PROTOCOL.md", reg["build_manifest"])))
                N.write(P / f"{stage}-results.json", rows)
    return rows


def summarize(rows, arms=("off", "factored")):
    cells = []
    for cid in sorted({row["cell"] for row in rows}):
        rec = {"cell": cid}
        for arm in arms:
            group = [row for row in rows if row["cell"] == cid and row["arm"] == arm]
            hits = [row["target_seconds"] for row in group if row["target_seconds"] is not None]
            rec[arm] = {
                "n": len(group), "hits": sum(row["hit"] for row in group),
                "median_target_seconds": statistics.median(hits) if hits else None,
                "target_range": [min(hits), max(hits)] if hits else None,
                "median_native_seconds": statistics.median(row["native_seconds"] for row in group),
                "native_range": [min(row["native_seconds"] for row in group),
                                 max(row["native_seconds"] for row in group)],
                "median_products": statistics.median(row["matvecs"] for row in group),
                "product_range": [min(row["matvecs"] for row in group),
                                  max(row["matvecs"] for row in group)],
                "median_endpoint": statistics.median(row["cost"] for row in group),
                "endpoint_range": [min(row["cost"] for row in group), max(row["cost"] for row in group)],
                "median_outers": statistics.median(row["outers"] for row in group),
                "median_rejects": statistics.median(row["rejects"] for row in group),
            }
        if all(rec[arm]["median_target_seconds"] is not None for arm in arms):
            rec["time_ratio"] = (rec[arms[1]]["median_target_seconds"] /
                                 rec[arms[0]]["median_target_seconds"])
        rec["product_ratio"] = rec[arms[1]]["median_products"] / rec[arms[0]]["median_products"]
        rec["endpoint_delta"] = rec[arms[1]]["median_endpoint"] / rec[arms[0]]["median_endpoint"] - 1
        cells.append(rec)
    usable = [cell["time_ratio"] for cell in cells if "time_ratio" in cell]
    return {
        "rows": len(rows),
        "geometric_mean_time_ratio": (math.exp(sum(map(math.log, usable)) / len(usable))
                                       if usable else None),
        "cells": cells,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["compatibility", "audit", "panel", "muell", "tails", "profile"])
    args = parser.parse_args()
    reg = register()
    calm = next(cell for cell in reg["practical"] if cell["cell"] == "ladybug-539-1.01")
    if args.stage == "compatibility":
        rows = execute(reg, "b1-compatibility", [calm], ["off", "parent-off"], 3)
        medians = {arm: statistics.median(row["cost"] for row in rows if row["arm"] == arm)
                   for arm in ("off", "parent-off")}
        result = {"rows": len(rows), "medians": medians,
                  "relative_delta": medians["off"] / medians["parent-off"] - 1}
        result["passed"] = abs(result["relative_delta"]) < 0.0015
        N.write(P / "b1-compatibility-summary.json", result)
        assert result["passed"], result
    elif args.stage == "audit":
        assert json.loads((P / "b1-compatibility-summary.json").read_text())["passed"]
        rows = execute(reg, "b1-audit", [reg["audit"]], ["factored"], 1,
                       {"OCA_W5_FACTORED_AUDIT": "1"})
        result = {"row": rows[0], "passed": "fragment_audit" in rows[0]}
        N.write(P / "b1-audit-summary.json", result)
        assert result["passed"], result
    elif args.stage == "panel":
        result = summarize(execute(reg, "b1-panel", reg["practical"], list(ARMS), 3))
        N.write(P / "b1-panel-summary.json", result)
    elif args.stage == "muell":
        result = summarize(execute(reg, "b1-muell", [reg["muell"]], list(ARMS), 3))
        N.write(P / "b1-muell-summary.json", result)
    elif args.stage == "tails":
        result = summarize(execute(reg, "b1-tails", list(reg["tails"].values()), list(ARMS), 5))
        N.write(P / "b1-tails-summary.json", result)
    else:
        traf = next(cell for cell in reg["practical"] if cell["cell"] == "trafalgar-138-1.005")
        rows = execute(reg, "b1-profile", [traf, reg["muell"]], list(ARMS), 3,
                       {"OCA_PROFILE": "1"})
        result = summarize(rows)
        for cell in result["cells"]:
            for arm in ARMS:
                group = [row for row in rows if row["cell"] == cell["cell"] and row["arm"] == arm]
                cell[arm]["median_profile_seconds"] = {
                    phase: statistics.median(row["profile_seconds"][phase] for row in group)
                    for phase in ("assembly", "pointfactor_rhs", "krylov", "candidates")
                }
        N.write(P / "b1-profile-summary.json", result)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
