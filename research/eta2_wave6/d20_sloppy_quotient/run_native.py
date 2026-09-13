#!/usr/bin/env python3
"""Registered native gates for D20 sloppy-mode quotient projection."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import pathlib
import re
import statistics
import sys

HERE = pathlib.Path(__file__).resolve().parent
WAVE6 = HERE.parent
WAVE5 = WAVE6.parent / "eta2_wave5"
sys.path[:0] = [str(WAVE6), str(WAVE5)]

import native_light as N  # noqa: E402
from bal_perturb import load_bal, perturb, residual_distance, sha256, state_from_bal, write_state  # noqa: E402

N.HERE = WAVE6
PARENT = WAVE6 / "build/prism-deterministic"
BINARY = pathlib.Path("/tmp/prism-wave6-d20/prism-d20")
BUILD = HERE / "build-manifest.json"
PROTOCOL = WAVE6 / "D20_NATIVE_PROTOCOL.md"
SOURCE = {
    "venice": pathlib.Path("/workspace/bal/venice-52.txt"),
    "final": pathlib.Path("/workspace/bal/final-3068.txt"),
}
TARGET = {"venice": 243740.27, "final": 1744796.9841897595}
SEEDS = {"venice": list(range(660048, 660053)),
         "final": list(range(660053, 660058))}
EPSILON = 1e-12
OPTIMIZED = json.loads((WAVE5 / "optimized_candidate.json").read_text())
FLAGS = {**OPTIMIZED["flags_overlay"], "OCA_W6_DETERMINISTIC": "1"}


def canonical(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def registration() -> dict:
    build = json.loads(BUILD.read_text())
    parent_build = json.loads((WAVE6 / "deterministic-build-manifest.json").read_text())
    base = json.loads((WAVE5 / "b6v7-registration.json").read_text())
    assert sha256(BINARY) == build["binary_sha256"]
    assert sha256(PARENT) == parent_build["binary_sha256"]
    assert all(sha256(path) == digest for path, digest in build["sources"].items())
    reg = {
        "protocol_sha256": sha256(PROTOCOL), "build_manifest": build,
        "runner_sha256": sha256(HERE / "run_native.py"),
        "parent_binary": str(PARENT), "parent_sha256": sha256(PARENT),
        "derived_binary": str(BINARY), "derived_sha256": sha256(BINARY),
        "flags": FLAGS, "epsilon": EPSILON,
        "compatibility": next(x for x in base["practical"]
                              if x["cell"] == "ladybug-539-1.01"),
        "venice": {"scene": "venice-52", "path": str(SOURCE["venice"]),
                   "input_sha256": sha256(SOURCE["venice"]),
                   "target": TARGET["venice"], "cap": 60,
                   "seeds": SEEDS["venice"]},
        "final": {"scene": "final-3068", "path": str(SOURCE["final"]),
                 "input_sha256": sha256(SOURCE["final"]),
                 "target": TARGET["final"], "cap": 60,
                 "seeds": SEEDS["final"]},
        "practical": base["practical"], "panel_repetitions": 3,
        "arm_order": "control,d20 on even pair/repetition; d20,control on odd",
        "gates": {
            "venice": "D20 hit >= 3/5",
            "final": "D20 hit count >= control hit count",
            "panel": "no endpoint regression >0.15%; disjoint target-time loss on <5/9 cells",
        },
    }
    N.write(WAVE6 / "d20-native-registration.json", reg)
    return reg


def trace_fields(row: dict) -> dict:
    folder = WAVE6 / row["source"]
    curves = list(csv.DictReader(x for x in (folder / "curve.csv").read_text().splitlines()
                                 if not x.startswith("#")))
    row["accepted_cost_strings"] = [x["cost"] for x in curves]
    row["accepted_cost_hash"] = canonical(row["accepted_cost_strings"])
    prefixes = ("PCG_PREP ", "ATTR_RADIUS ", "CLASSICAL_LM ", "POINT_SAFE o=",
                "MFCG it ", "NUMERIC_REPAIR ")
    decision = [line.strip() for line in (folder / "stdout.log").read_text().splitlines()
                if line.strip().startswith(prefixes)]
    row["decision_hash"] = canonical(decision)
    row["decision_lines"] = decision
    text = (folder / "stdout.log").read_text()
    tests = list(re.finditer(
        r"D20_TEST o=(\d+) retry=(\d+) ratio=(\S+) top=(-?\d+) "
        r"top_fraction=(\S+) preliminary=(\d+) weakest=(-?\d+) trigger=(\d+) "
        r"removed_fraction=(\S+) post_raw=(\S+) post_ratio=(\S+)", text))
    summary = re.search(
        r"D20_SUMMARY tests=(\d+) block_builds=(\d+) projections=(\d+) block_seconds=(\S+)",
        text)
    triggered = [m for m in tests if int(m[8])]
    row["d20"] = {
        "tests": int(summary[1]) if summary else 0,
        "block_builds": int(summary[2]) if summary else 0,
        "projections": int(summary[3]) if summary else 0,
        "block_seconds": float(summary[4]) if summary else 0.0,
        "max_ratio": max((float(m[3]) for m in tests), default=None),
        "max_top_fraction": max((float(m[5]) for m in tests), default=None),
        "selected_cameras": sorted({int(m[4]) for m in triggered}),
        "weakest_cameras": sorted({int(m[7]) for m in triggered}),
        "removed_fraction_range": ([min(float(m[9]) for m in triggered),
                                    max(float(m[9]) for m in triggered)]
                                   if triggered else None),
        "post_ratio_range": ([min(float(m[11]) for m in triggered),
                              max(float(m[11]) for m in triggered)]
                             if triggered else None),
    }
    N.write(folder / "result.json", row)
    return row


def compatibility(reg: dict) -> dict:
    cell = reg["compatibility"]
    rows = []
    for arm, binary in (("d0v3-parent", PARENT), ("d20-derived-off", BINARY)):
        folder = WAVE6 / "evidence/d20-native-compatibility" / arm
        rows.append(trace_fields(N.run(folder, cell, arm, 0, binary, FLAGS, PROTOCOL,
                                       reg["build_manifest"])))
    keys = ["state_sha256", "accepted_cost_hash", "decision_hash", "hit", "outers",
            "rejects", "matvecs", "cost"]
    result = {"rows": rows, "equal": {key: rows[0][key] == rows[1][key] for key in keys}}
    result["passed"] = all(result["equal"].values())
    N.write(WAVE6 / "d20-native-compatibility.json", result)
    if not result["passed"]:
        raise SystemExit(2)
    return result


def run_arm(reg: dict, folder: pathlib.Path, cell: dict, arm: str, rep: int) -> dict:
    flags = dict(FLAGS)
    if arm == "d20":
        flags["OCA_D20_SLOPPY_QUOTIENT"] = "1"
    return trace_fields(N.run(folder, cell, arm, rep, BINARY, flags, PROTOCOL,
                              reg["build_manifest"]))


def paired_summary(pairs: list[dict], kind: str) -> dict:
    controls = [p["control"] for p in pairs]
    variants = [p["d20"] for p in pairs]
    double = [p for p in pairs if p["control"]["hit"] and p["d20"]["hit"]]
    time_ratios = [p["d20"]["target_seconds"] / p["control"]["target_seconds"]
                   for p in double]
    endpoint = [p["d20"]["cost"] / p["control"]["cost"] - 1 for p in pairs]
    report = {
        "kind": kind, "pairs": len(pairs),
        "control_hits": sum(r["hit"] for r in controls),
        "d20_hits": sum(r["hit"] for r in variants),
        "d20_activated_runs": sum(r["d20"]["projections"] > 0 for r in variants),
        "d20_total_projections": sum(r["d20"]["projections"] for r in variants),
        "selected_cameras": sorted({c for r in variants for c in r["d20"]["selected_cameras"]}),
        "double_hits": len(double),
        "median_double_hit_target_time_ratio": statistics.median(time_ratios) if time_ratios else None,
        "double_hit_target_time_ratio_range": [min(time_ratios), max(time_ratios)] if time_ratios else None,
        "median_paired_endpoint_delta": statistics.median(endpoint),
        "paired_endpoint_delta_range": [min(endpoint), max(endpoint)],
        "control_median_cost": statistics.median(r["cost"] for r in controls),
        "d20_median_cost": statistics.median(r["cost"] for r in variants),
        "control_median_native_seconds": statistics.median(r["native_seconds"] for r in controls),
        "d20_median_native_seconds": statistics.median(r["native_seconds"] for r in variants),
    }
    report["advance"] = (report["d20_hits"] >= 3 if kind == "venice"
                         else report["d20_hits"] >= report["control_hits"])
    return report


def run_tail(reg: dict, kind: str) -> dict:
    if kind == "final":
        venice = json.loads((WAVE6 / "d20-venice-summary.json").read_text())
        if not venice["advance"]:
            raise SystemExit("Venice hard gate did not advance")
    problem = load_bal(SOURCE[kind]);initial = state_from_bal(problem)
    pairs = []
    for index, seed in enumerate(SEEDS[kind]):
        cameras, points, scales = perturb(problem, seed, EPSILON)
        path = pathlib.Path(f"/dev/shm/eta2-d20-{kind}-{seed}.txt")
        write_state(problem, path, cameras, points)
        cell = {"scene": reg[kind]["scene"], "cell": f"{kind}-seed-{seed}",
                "path": str(path), "input_sha256": sha256(path),
                "target": TARGET[kind], "cap": 60}
        order = ["control", "d20"] if index % 2 == 0 else ["d20", "control"]
        rows = {}
        try:
            for arm in order:
                folder = WAVE6 / f"evidence/d20-{kind}" / f"{seed}-{arm}"
                rows[arm] = run_arm(reg, folder, cell, arm, index)
        finally:
            N.OBSERVATIONS.pop(str(path), None);path.unlink(missing_ok=True)
        pair = {"index": index, "seed": seed, "epsilon": EPSILON,
                "input_sha256": cell["input_sha256"], "field_scales": scales,
                "initial_residual_distance": residual_distance(
                    problem, initial, state_from_bal(problem, cameras, points)),
                "control": rows["control"], "d20": rows["d20"]}
        pairs.append(pair)
        N.write(WAVE6 / f"d20-{kind}-results.json", pairs)
        report = paired_summary(pairs, kind)
        N.write(WAVE6 / f"d20-{kind}-summary.json", report)
        print("PAIR", kind, index + 1, "hits", int(rows["control"]["hit"]),
              int(rows["d20"]["hit"]), "projections", rows["d20"]["d20"]["projections"],
              flush=True)
    return paired_summary(pairs, kind)


def panel_summary(rows: list[dict]) -> dict:
    cells = []
    for cell in sorted({r["cell"] for r in rows}):
        a = [r for r in rows if r["cell"] == cell and r["arm"] == "control"]
        b = [r for r in rows if r["cell"] == cell and r["arm"] == "d20"]
        endpoint = statistics.median(r["cost"] for r in b) / statistics.median(r["cost"] for r in a) - 1
        at = [r["target_seconds"] for r in a if r["hit"]]
        bt = [r["target_seconds"] for r in b if r["hit"]]
        disjoint_loss = bool(at and bt and min(bt) > max(at))
        cells.append({"cell": cell, "control_hits": sum(r["hit"] for r in a),
                      "d20_hits": sum(r["hit"] for r in b),
                      "endpoint_delta": endpoint, "disjoint_time_loss": disjoint_loss,
                      "control_target_range": [min(at), max(at)] if at else None,
                      "d20_target_range": [min(bt), max(bt)] if bt else None,
                      "d20_projections": sum(r["d20"]["projections"] for r in b)})
    report = {"cells": cells,
              "endpoint_regressions_over_0.15pct": sum(c["endpoint_delta"] > .0015 for c in cells),
              "disjoint_time_losses": sum(c["disjoint_time_loss"] for c in cells)}
    report["promote"] = (report["endpoint_regressions_over_0.15pct"] == 0 and
                         report["disjoint_time_losses"] < 5)
    return report


def run_panel(reg: dict) -> dict:
    final = json.loads((WAVE6 / "d20-final-summary.json").read_text())
    if not final["advance"]:
        raise SystemExit("Final hard gate did not advance")
    rows = []
    for rep in range(3):
        cells = list(reg["practical"])
        if rep % 2:
            cells.reverse()
        for cell in cells:
            order = ["control", "d20"] if rep % 2 == 0 else ["d20", "control"]
            for arm in order:
                folder = WAVE6 / "evidence/d20-panel" / f"{cell['cell']}-r{rep}-{arm}"
                rows.append(run_arm(reg, folder, cell, arm, rep))
                N.write(WAVE6 / "d20-panel-results.json", rows)
    report = panel_summary(rows);N.write(WAVE6 / "d20-panel-summary.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["register", "compatibility", "venice", "final", "panel"])
    args = parser.parse_args();reg = registration()
    if args.stage == "register": result = reg
    elif args.stage == "compatibility": result = compatibility(reg)
    elif args.stage == "venice": result = run_tail(reg, "venice")
    elif args.stage == "final": result = run_tail(reg, "final")
    else: result = run_panel(reg)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()

