#!/usr/bin/env python3
"""Registered native D13 GMRES(8) evaluation."""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import re
import statistics
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
WAVE6 = HERE.parent
ROOT = WAVE6.parents[1]
WAVE5 = ROOT / "research" / "eta2_wave5"
sys.path.insert(0, str(WAVE5))
import native_light as N  # noqa: E402

# native_light stores source paths relative to its owning campaign directory.
# Rebase that bookkeeping to wave6 while retaining its frozen champion loader.
N.HERE = WAVE6

BINARY = pathlib.Path("/tmp/prism-wave6-d13-native/prism-d13-gmres")
PARENT = pathlib.Path(N.CHAMPION["binary"])
PROTOCOL = WAVE6 / "D13_KRYLOV_RESTART_PROTOCOL.md"
BUILD_MANIFEST = HERE / "evidence" / "native_build_manifest.json"
ARMS = {"control": {}, "gmres8": {"OCA_PCG_GMRES": "8"}}


def register() -> dict:
    subprocess.run(["python3", str(N.FROZEN / "build.py"), "--check-only"], check=True)
    build = json.loads(BUILD_MANIFEST.read_text())
    assert N.sha(BINARY) == build["binary_sha256"]
    assert all(N.sha(path) == digest for path, digest in build["sources"].items())
    base = json.loads((WAVE5 / "b1-registration.json").read_text())
    final = {
        "scene": "final-1936",
        "cell": "final-1936",
        "path": "/workspace/bal/final-1936.txt",
        "input_sha256": N.sha("/workspace/bal/final-1936.txt"),
        "target": 5125687.352261469,
        "cap": 12,
    }
    reg = {
        "arms": ARMS,
        "practical": base["practical"],
        "tails": base["tails"],
        "muell": base["muell"],
        "final1936": final,
        "panel_repetitions": 3,
        "control_repetitions": 3,
        "tail_repetitions": 5,
        "binary": str(BINARY),
        "binary_sha256": N.sha(BINARY),
        "parent_binary": str(PARENT),
        "parent_binary_sha256": N.sha(PARENT),
        "build_manifest": build,
        "protocol_sha256": N.sha(PROTOCOL),
        "cohort_rule": "Fresh paired rows; alternate arms and reverse cells on odd repetitions",
        "registered_arm": "right-preconditioned GMRES(8), exact residual verification per cycle, nine stored camera vectors",
        "registration_revision": (
            "Binary relocated from noexec /dev/shm to /tmp after the first launch failed "
            "with PermissionError; no valid or scored row existed"
        ),
    }
    path = WAVE6 / "d13-native-registration.json"
    if path.exists():
        old = json.loads(path.read_text())
        if old != reg:
            assert old["binary"].startswith("/dev/shm/")
            invalid = WAVE6 / "evidence" / "d13-compatibility" / "ladybug-539-1.01-control-0" / "result.json"
            assert invalid.exists() and not json.loads(invalid.read_text())["valid"]
            N.write(path, reg)
    else:
        N.write(path, reg)
    return reg


def enrich(row: dict) -> dict:
    folder = WAVE6 / row["source"]
    # native_light records paths relative to eta2_wave5 even for a folder in
    # wave6; resolve from its module root exactly as it does.
    stdout = (folder / "stdout.log").read_text()
    summary = re.search(
        r"D13_GMRES summary solves=(\d+) iterations=(\d+) products=(\d+) basis_vectors=(\d+)",
        stdout,
    )
    if summary:
        row["gmres"] = {
            "solves": int(summary[1]),
            "iterations": int(summary[2]),
            "products": int(summary[3]),
            "basis_vectors": int(summary[4]),
        }
    restart = re.search(
        r"D13_RESTART summary solves=(\d+) touched=(\d+) replacements=(\d+) depth=(\d+) periodic=(\d+)",
        stdout,
    )
    if restart:
        row["restart"] = {
            "solves": int(restart[1]),
            "touched": int(restart[2]),
            "replacements": int(restart[3]),
            "depth": int(restart[4]),
            "periodic": bool(int(restart[5])),
        }
    N.write(folder / "result.json", row)
    return row


def execute(reg: dict, stage: str, cells: list[dict], arms: list[str], reps: int,
            parent_control: bool = False) -> list[dict]:
    rows = []
    for rep in range(reps):
        ordered_cells, ordered_arms = list(cells), list(arms)
        if rep % 2:
            ordered_cells.reverse()
            ordered_arms.reverse()
        for cell in ordered_cells:
            for arm in ordered_arms:
                if arm == "parent":
                    binary, flags = PARENT, {}
                else:
                    binary, flags = BINARY, ARMS[arm]
                folder = WAVE6 / "evidence" / stage / f"{cell.get('cell', cell['scene'])}-{arm}-{rep}"
                row = N.run(folder, cell, arm, rep, binary, flags, PROTOCOL,
                            reg["build_manifest"])
                rows.append(enrich(row))
                N.write(WAVE6 / f"{stage}-results.json", rows)
    return rows


def summarize(rows: list[dict], arms: tuple[str, ...] = ("control", "gmres8")) -> dict:
    cells = []
    for cell_id in sorted({row["cell"] for row in rows}):
        record = {"cell": cell_id}
        for arm in arms:
            group = [row for row in rows if row["cell"] == cell_id and row["arm"] == arm]
            times = [row["target_seconds"] for row in group if row["target_seconds"] is not None]
            record[arm] = {
                "n": len(group),
                "hits": sum(row["hit"] for row in group),
                "median_target_seconds": statistics.median(times) if times else None,
                "target_range": [min(times), max(times)] if times else None,
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
            details = [row["gmres"] for row in group if "gmres" in row]
            if details:
                record[arm]["median_gmres_iterations"] = statistics.median(
                    item["iterations"] for item in details
                )
                record[arm]["median_gmres_products"] = statistics.median(
                    item["products"] for item in details
                )
                record[arm]["basis_vectors"] = sorted({item["basis_vectors"] for item in details})
            restart_details = [row["restart"] for row in group if "restart" in row]
            if restart_details:
                record[arm]["median_restart_replacements"] = statistics.median(
                    item["replacements"] for item in restart_details
                )
                record[arm]["median_restart_touched"] = statistics.median(
                    item["touched"] for item in restart_details
                )
                record[arm]["median_restart_solves"] = statistics.median(
                    item["solves"] for item in restart_details
                )
        if len(arms) == 2 and all(record[arm]["median_target_seconds"] is not None for arm in arms):
            record["time_ratio"] = (
                record[arms[1]]["median_target_seconds"] /
                record[arms[0]]["median_target_seconds"]
            )
        if len(arms) == 2:
            record["product_ratio"] = (
                record[arms[1]]["median_products"] / record[arms[0]]["median_products"]
            )
            record["endpoint_delta"] = (
                record[arms[1]]["median_endpoint"] / record[arms[0]]["median_endpoint"] - 1
            )
        cells.append(record)
    ratios = [cell["time_ratio"] for cell in cells if "time_ratio" in cell]
    return {
        "rows": len(rows),
        "geometric_mean_time_ratio": (
            math.exp(sum(math.log(value) for value in ratios) / len(ratios)) if ratios else None
        ),
        "cells": cells,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["compatibility", "smoke", "panel", "controls", "tails"])
    args = parser.parse_args()
    reg = register()
    calm = next(cell for cell in reg["practical"] if cell["cell"] == "ladybug-539-1.01")
    if args.stage == "compatibility":
        rows = execute(reg, "d13-compatibility", [calm], ["control", "parent"], 3)
        summary = summarize(rows, ("parent", "control"))
        delta = summary["cells"][0]["endpoint_delta"]
        summary["passed"] = abs(delta) < 0.0015
        N.write(WAVE6 / "d13-compatibility-summary.json", summary)
        assert summary["passed"], summary
    elif args.stage == "smoke":
        rows = execute(reg, "d13-smoke", [calm], ["gmres8"], 1)
        summary = summarize(rows, ("gmres8",))
    elif args.stage == "panel":
        assert json.loads((WAVE6 / "d13-compatibility-summary.json").read_text())["passed"]
        rows = execute(reg, "d13-panel", reg["practical"], list(ARMS), 3)
        summary = summarize(rows)
        N.write(WAVE6 / "d13-panel-summary.json", summary)
    elif args.stage == "controls":
        rows = execute(reg, "d13-controls", [reg["muell"], reg["final1936"]], list(ARMS), 3)
        summary = summarize(rows)
        N.write(WAVE6 / "d13-controls-summary.json", summary)
    else:
        rows = execute(reg, "d13-tails", list(reg["tails"].values()), list(ARMS), 5)
        summary = summarize(rows)
        N.write(WAVE6 / "d13-tails-summary.json", summary)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
