#!/usr/bin/env python3
"""Registered native D15 sparse count-prior evaluation."""
from __future__ import annotations

import argparse
import json
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

N.HERE = WAVE6

BINARY = pathlib.Path("/tmp/prism-wave6-d15-native/prism-d15")
PARENT = pathlib.Path(N.CHAMPION["binary"])
PROTOCOL = WAVE6 / "D15_COUNT_PRIOR_PROTOCOL.md"
BUILD_MANIFEST = HERE / "native-build-manifest.json"
ARMS = {"parent": {}, "off": {}, "d15": {"OCA_D15_COUNT_PRIOR": "1"}}


def register() -> dict:
    subprocess.run(["python3", str(N.FROZEN / "build.py"), "--check-only"], check=True)
    build = json.loads(BUILD_MANIFEST.read_text())
    assert N.sha(BINARY) == build["binary_sha256"]
    assert all(N.sha(path) == digest for path, digest in build["sources"].items())
    base = json.loads((WAVE5 / "b1-registration.json").read_text())
    reg = {
        "arms": ARMS,
        "compatibility": next(x for x in base["practical"] if x["cell"] == "ladybug-539-1.01"),
        "final3068": base["tails"]["final-3068"],
        "venice52": base["tails"]["venice-52"],
        "practical": base["practical"],
        "compatibility_repetitions": 3,
        "tail_repetitions": 10,
        "binary": str(BINARY),
        "binary_sha256": N.sha(BINARY),
        "parent_binary": str(PARENT),
        "parent_binary_sha256": N.sha(PARENT),
        "protocol_sha256": N.sha(PROTOCOL),
        "build_manifest": build,
        "cohort_rule": "Fresh rows; alternate arms and reverse arm order on odd repetitions",
        "registered_arm": (
            "dose-one coherent scaled-Schur camera prior, bottom-one-percent unique-track gate, "
            "activated only at raw/R > 100 and gated raw-step energy fraction > 0.5"
        ),
    }
    N.write(WAVE6 / "d15-native-registration.json", reg)
    return reg


def enrich(row: dict) -> dict:
    folder = WAVE6 / row["source"]
    stdout = (folder / "stdout.log").read_text()
    tests = [
        {
            "outer": int(m[1]), "retry": int(m[2]), "ratio": float(m[3]),
            "gated_fraction": float(m[4]), "raw_norm": float(m[5]),
            "radius": float(m[6]), "trigger": bool(int(m[7])),
        }
        for m in re.finditer(
            r"D15_TEST o=(\d+) retry=(\d+) ratio=(\S+) gated_fraction=(\S+) "
            r"raw=(\S+) radius=(\S+) trigger=(\d+)", stdout
        )
    ]
    builds = [
        {"activation": int(m[1]), "mu_ref": float(m[2]), "dose": float(m[3]),
         "cumulative_seconds": float(m[4])}
        for m in re.finditer(
            r"D15_BUILD activation=(\d+) mu_ref=(\S+) dose=(\S+) seconds=(\S+)", stdout
        )
    ]
    gate = re.search(r"D15_GATE ncam=(\d+) median=(\S+) selected=(\d+) ids=([^\n]*)", stdout)
    summary = re.search(r"D15_SUMMARY tests=(\d+) activations=(\d+) build_seconds=(\S+)", stdout)
    if gate:
        row["d15_gate"] = {"ncam": int(gate[1]), "median_count": float(gate[2]),
                           "selected": int(gate[3]), "ids_counts": gate[4]}
    if summary:
        row["d15_summary"] = {"tests": int(summary[1]), "activations": int(summary[2]),
                              "build_seconds": float(summary[3])}
    row["d15_tests"] = tests
    row["d15_builds"] = builds
    N.write(folder / "result.json", row)
    return row


def execute(reg: dict, stage: str, cell: dict, arms: list[str], reps: int) -> list[dict]:
    rows = []
    for rep in range(reps):
        ordered = list(arms)
        if rep % 2:
            ordered.reverse()
        for arm in ordered:
            binary = PARENT if arm == "parent" else BINARY
            flags = ARMS[arm]
            folder = WAVE6 / "evidence" / stage / f"{cell.get('cell', cell['scene'])}-{arm}-{rep}"
            row = N.run(folder, cell, arm, rep, binary, flags, PROTOCOL, reg["build_manifest"])
            rows.append(enrich(row))
            N.write(WAVE6 / f"{stage}-results.json", rows)
    return rows


def summarize(rows: list[dict], arms: list[str]) -> dict:
    out = {"rows": len(rows), "arms": {}}
    for arm in arms:
        g = [r for r in rows if r["arm"] == arm]
        hits = [r for r in g if r["hit"]]
        out["arms"][arm] = {
            "n": len(g), "hits": len(hits), "hit_rate": len(hits) / len(g),
            "median_endpoint": statistics.median(r["cost"] for r in g),
            "endpoint_range": [min(r["cost"] for r in g), max(r["cost"] for r in g)],
            "median_native_seconds": statistics.median(r["native_seconds"] for r in g),
            "native_range": [min(r["native_seconds"] for r in g), max(r["native_seconds"] for r in g)],
            "median_target_seconds": statistics.median(r["target_seconds"] for r in hits) if hits else None,
            "target_range": [min(r["target_seconds"] for r in hits),
                             max(r["target_seconds"] for r in hits)] if hits else None,
            "median_outers": statistics.median(r["outers"] for r in g),
            "median_rejects": statistics.median(r["rejects"] for r in g),
            "total_activations": sum(r.get("d15_summary", {}).get("activations", 0) for r in g),
            "runs_activated": sum(r.get("d15_summary", {}).get("activations", 0) > 0 for r in g),
            "median_prior_build_seconds": statistics.median(
                [r.get("d15_summary", {}).get("build_seconds", 0.0) for r in g]
            ),
        }
    if len(arms) == 2:
        a, b = arms
        out["hit_delta"] = out["arms"][b]["hit_rate"] - out["arms"][a]["hit_rate"]
        out["endpoint_delta"] = out["arms"][b]["median_endpoint"] / out["arms"][a]["median_endpoint"] - 1
    return out


def summarize_panel(rows: list[dict]) -> dict:
    cells = []
    for cell_id in sorted({r["cell"] for r in rows}):
        rec = {"cell": cell_id}
        for arm in ["parent", "d15"]:
            g = [r for r in rows if r["cell"] == cell_id and r["arm"] == arm]
            hits = [r for r in g if r["hit"]]
            rec[arm] = {
                "n": len(g), "hits": len(hits),
                "median_target_seconds": statistics.median(r["target_seconds"] for r in hits) if hits else None,
                "target_range": [min(r["target_seconds"] for r in hits),
                                 max(r["target_seconds"] for r in hits)] if hits else None,
                "median_endpoint": statistics.median(r["cost"] for r in g),
                "endpoint_range": [min(r["cost"] for r in g), max(r["cost"] for r in g)],
                "runs_activated": sum(r.get("d15_summary", {}).get("activations", 0) > 0 for r in g),
                "total_activations": sum(r.get("d15_summary", {}).get("activations", 0) for r in g),
            }
        if all(rec[a]["median_target_seconds"] is not None for a in ["parent", "d15"]):
            rec["time_ratio"] = rec["d15"]["median_target_seconds"] / rec["parent"]["median_target_seconds"]
            rec["ranges_disjoint_slower"] = rec["d15"]["target_range"][0] > rec["parent"]["target_range"][1]
            rec["ranges_disjoint_faster"] = rec["d15"]["target_range"][1] < rec["parent"]["target_range"][0]
        rec["endpoint_delta"] = rec["d15"]["median_endpoint"] / rec["parent"]["median_endpoint"] - 1
        cells.append(rec)
    return {
        "rows": len(rows), "cells": cells,
        "disjoint_slower_cells": sum(c.get("ranges_disjoint_slower", False) for c in cells),
        "disjoint_faster_cells": sum(c.get("ranges_disjoint_faster", False) for c in cells),
        "activated_cells": sum(c["d15"]["runs_activated"] > 0 for c in cells),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["compatibility", "final3068", "venice52", "panel"])
    args = parser.parse_args()
    reg = register()
    if args.stage == "compatibility":
        # Parent-vs-derived-off verifies all reversible source surgery is inert.
        rows = execute(reg, "d15-compatibility", reg["compatibility"], ["parent", "off"], 3)
        summary = summarize(rows, ["parent", "off"])
        summary["passed"] = (
            abs(summary["endpoint_delta"]) < 0.0015
            and summary["arms"]["parent"]["hits"] == summary["arms"]["off"]["hits"]
        )
        N.write(WAVE6 / "d15-compatibility-summary.json", summary)
        assert summary["passed"], summary
    elif args.stage == "final3068":
        assert json.loads((WAVE6 / "d15-compatibility-summary.json").read_text())["passed"]
        rows = execute(reg, "d15-final3068", reg["final3068"], ["parent", "d15"], 10)
        summary = summarize(rows, ["parent", "d15"])
        summary["promotion_gate"] = "D15 hit rate strictly exceeds fresh parent hit rate"
        summary["passed"] = summary["hit_delta"] > 0
        N.write(WAVE6 / "d15-final3068-summary.json", summary)
    elif args.stage == "venice52":
        assert json.loads((WAVE6 / "d15-final3068-summary.json").read_text())["passed"]
        rows = execute(reg, "d15-venice52", reg["venice52"], ["parent", "d15"], 5)
        summary = summarize(rows, ["parent", "d15"])
        summary["kill_rule"] = "D15 endpoint regression above the registered Venice floor"
        # Preserve the raw verdict; final interpretation uses the campaign's empirical floor.
        N.write(WAVE6 / "d15-venice52-summary.json", summary)
    else:
        assert json.loads((WAVE6 / "d15-final3068-summary.json").read_text())["passed"]
        rows = []
        for rep in range(3):
            cells = list(reg["practical"])
            if rep % 2:
                cells.reverse()
            for cell in cells:
                ordered = ["parent", "d15"] if rep % 2 == 0 else ["d15", "parent"]
                for arm in ordered:
                    binary = PARENT if arm == "parent" else BINARY
                    folder = WAVE6 / "evidence" / "d15-panel" / f"{cell['cell']}-{arm}-{rep}"
                    row = N.run(folder, cell, arm, rep, binary, ARMS[arm], PROTOCOL,
                                reg["build_manifest"])
                    rows.append(enrich(row))
                    N.write(WAVE6 / "d15-panel-results.json", rows)
        summary = summarize_panel(rows)
        summary["passed"] = summary["disjoint_slower_cells"] < 5
        N.write(WAVE6 / "d15-panel-summary.json", summary)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
