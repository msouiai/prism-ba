#!/usr/bin/env python3
"""Registered deterministic gate for D22 terminal two-view point polish."""
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
W6 = HERE.parent
W5 = W6.parent / "eta2_wave5"
sys.path[:0] = [str(W6), str(W5)]

import native_light as N  # noqa: E402
from bal_perturb import load_bal, perturb, residual_distance, sha256, state_from_bal, write_state  # noqa: E402

N.HERE = W6
PARENT = W6 / "build/prism-deterministic"
BINARY = pathlib.Path("/tmp/prism-wave6-d22/prism-d22")
BUILD = HERE / "build-manifest.json"
PROTOCOL = W6 / "D22_TERMINAL_TRACK_POLISH_PROTOCOL.md"
SOURCE = pathlib.Path("/workspace/bal/final-3068.txt")
TARGET = 1744796.9841897595
CAP = 60
EPSILON = 1e-12
SCREEN_SEEDS = list(range(660058, 660063))
EXTENSION_SEEDS = list(range(660063, 660068))
OPT = json.loads((W5 / "optimized_candidate.json").read_text())
FLAGS = {**OPT["flags_overlay"], "OCA_W6_DETERMINISTIC": "1"}


def canonical(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def registration() -> dict:
    build = json.loads(BUILD.read_text())
    parent_build = json.loads((W6 / "deterministic-build-manifest.json").read_text())
    base = json.loads((W5 / "b6v7-registration.json").read_text())
    assert sha256(BINARY) == build["binary_sha256"]
    assert sha256(PARENT) == parent_build["binary_sha256"]
    assert all(sha256(path) == digest for path, digest in build["sources"].items())
    reg = {
        "protocol_sha256": sha256(PROTOCOL), "build_manifest": build,
        "runner_sha256": sha256(HERE / "run.py"),
        "parent_binary": str(PARENT), "parent_sha256": sha256(PARENT),
        "derived_binary": str(BINARY), "derived_sha256": sha256(BINARY),
        "flags": FLAGS, "epsilon": EPSILON,
        "source": str(SOURCE), "source_sha256": sha256(SOURCE),
        "target": TARGET, "cap": CAP,
        "screen_seeds": SCREEN_SEEDS, "extension_seeds": EXTENSION_SEEDS,
        "compatibility": next(x for x in base["practical"]
                              if x["cell"] == "ladybug-539-1.01"),
        "arm_order": "control,d22 on even pair; d22,control on odd pair",
        "screen_gate": (
            "advance iff >=1 D22-only target hit or median committed terminal "
            "relative decrease >0.0015"
        ),
        "full_gate": {
            "minimum_d22_only_hits": 2,
            "maximum_control_only_hits": 0,
            "maximum_median_invoked_native_wall_ratio": 1.20,
        },
        "conditional": {
            "venice52": {**base["tails"]["venice-52"], "repetitions": 5},
            "practical": base["practical"], "repetitions": 3,
        },
    }
    N.write(W6 / "d22-registration.json", reg)
    return reg


def trace_fields(row: dict) -> dict:
    folder = W6 / row["source"]
    curve = list(csv.DictReader(x for x in (folder / "curve.csv").read_text().splitlines()
                                if not x.startswith("#")))
    text = (folder / "stdout.log").read_text()
    terminal = re.search(
        r"D22_TERMINAL outer=(\d+) before=(\S+) candidate=(\S+) decrease=(\S+) "
        r"eligible=(\d+) wins=(\d+) margin=(\d+) algebra=(\d+) "
        r"local_decrease=(\S+) commit=(\d+) target=(\d+)", text)
    summary = re.search(r"D22_SUMMARY calls=(\d+) seconds=(\S+)", text)
    d22 = {
        "calls": int(summary[1]) if summary else 0,
        "seconds": float(summary[2]) if summary else 0.0,
        "outer": int(terminal[1]) if terminal else None,
        "before": float(terminal[2]) if terminal else None,
        "candidate": float(terminal[3]) if terminal else None,
        "decrease": float(terminal[4]) if terminal else 0.0,
        "eligible": int(terminal[5]) if terminal else 0,
        "wins": int(terminal[6]) if terminal else 0,
        "margin_rejects": int(terminal[7]) if terminal else 0,
        "algebra_failures": int(terminal[8]) if terminal else 0,
        "local_decrease": float(terminal[9]) if terminal else 0.0,
        "commit": bool(int(terminal[10])) if terminal else False,
        "target": bool(int(terminal[11])) if terminal else False,
        "stop_ftol": "converged (OCA_FTOL:" in text,
        "stop_relative": "converged (relative cost decrease" in text,
        "stop_failures": "consecutive outer iterations with no improving step" in text,
    }
    costs = [x["cost"] for x in curve]
    preterminal = costs[:-1] if d22["commit"] else costs
    row["accepted_cost_strings"] = costs
    row["accepted_cost_hash"] = canonical(costs)
    row["preterminal_cost_strings"] = preterminal
    row["preterminal_cost_hash"] = canonical(preterminal)
    prefixes = ("PCG_PREP ", "ATTR_RADIUS ", "CLASSICAL_LM ", "POINT_SAFE o=",
                "MFCG it ", "NUMERIC_REPAIR ")
    decisions = [line.strip() for line in text.splitlines()
                 if line.strip().startswith(prefixes)]
    row["decision_lines"] = decisions
    row["decision_hash"] = canonical(decisions)
    row["d22"] = d22
    N.write(folder / "result.json", row)
    return row


def compatibility(reg: dict) -> dict:
    rows = []
    cell = reg["compatibility"]
    for arm, binary in (("d0v3-parent", PARENT), ("d22-derived-off", BINARY)):
        folder = W6 / "evidence/d22-compatibility" / arm
        rows.append(trace_fields(N.run(folder, cell, arm, 0, binary, FLAGS, PROTOCOL,
                                       reg["build_manifest"])))
    keys = ["state_sha256", "accepted_cost_hash", "decision_hash", "hit", "outers",
            "rejects", "matvecs", "cost"]
    result = {"rows": rows, "equal": {key: rows[0][key] == rows[1][key] for key in keys}}
    result["passed"] = all(result["equal"].values()) and rows[1]["d22"]["calls"] == 0
    N.write(W6 / "d22-compatibility.json", result)
    if not result["passed"]:
        raise SystemExit(2)
    return result


def summarize(pairs: list[dict], stage: str) -> dict:
    d22_only = [p for p in pairs if p["d22"]["hit"] and not p["control"]["hit"]]
    control_only = [p for p in pairs if p["control"]["hit"] and not p["d22"]["hit"]]
    invoked = [p for p in pairs if p["d22"]["d22"]["calls"]]
    committed = [p for p in invoked if p["d22"]["d22"]["commit"]]
    decreases = [p["d22"]["d22"]["decrease"] / p["d22"]["d22"]["before"]
                 for p in invoked if p["d22"]["d22"]["before"]]
    wall = [p["d22"]["native_seconds"] / p["control"]["native_seconds"] for p in invoked]
    prefix_equal = [p["control"]["accepted_cost_hash"] == p["d22"]["preterminal_cost_hash"]
                    and p["control"]["decision_hash"] == p["d22"]["decision_hash"]
                    for p in pairs]
    report = {
        "stage": stage, "pairs": len(pairs),
        "control_hits": sum(p["control"]["hit"] for p in pairs),
        "d22_hits": sum(p["d22"]["hit"] for p in pairs),
        "d22_only_hits": len(d22_only), "control_only_hits": len(control_only),
        "invoked_pairs": len(invoked), "committed_pairs": len(committed),
        "total_eligible_tracks": sum(p["d22"]["d22"]["eligible"] for p in invoked),
        "total_winning_tracks": sum(p["d22"]["d22"]["wins"] for p in invoked),
        "median_terminal_relative_decrease": statistics.median(decreases) if decreases else 0.0,
        "terminal_relative_decrease_range": [min(decreases), max(decreases)] if decreases else None,
        "median_invoked_native_wall_ratio": statistics.median(wall) if wall else None,
        "invoked_native_wall_ratio_range": [min(wall), max(wall)] if wall else None,
        "all_preterminal_paths_exact": all(prefix_equal),
        "preterminal_path_equal": prefix_equal,
    }
    report["advance"] = (len(d22_only) >= 1 or
                         report["median_terminal_relative_decrease"] > 0.0015)
    if stage == "full":
        report["pass"] = (len(d22_only) >= 2 and not control_only and
                          bool(wall) and statistics.median(wall) <= 1.20 and
                          all(prefix_equal))
    return report


def run_arm(reg: dict, cell: dict, seed: int, index: int, arm: str) -> dict:
    flags = dict(FLAGS)
    if arm == "d22":
        flags["OCA_D22_TERMINAL_TRACK_POLISH"] = "1"
    folder = W6 / "evidence/d22-final3068" / f"{seed}-{arm}"
    return trace_fields(N.run(folder, cell, arm, index, BINARY, flags, PROTOCOL,
                              reg["build_manifest"]))


def execute(reg: dict, stage: str) -> dict:
    assert json.loads((W6 / "d22-compatibility.json").read_text())["passed"]
    result_path = W6 / "d22-final3068-results.json"
    existing = {x["seed"]: x for x in json.loads(result_path.read_text())} if result_path.exists() else {}
    seeds = SCREEN_SEEDS if stage == "screen" else SCREEN_SEEDS + EXTENSION_SEEDS
    if stage == "extend":
        screen = summarize([existing[s] for s in SCREEN_SEEDS], "screen")
        if not screen["advance"]:
            raise SystemExit("registered first screen did not advance")
    problem = load_bal(SOURCE)
    initial = state_from_bal(problem)
    pairs = []
    for index, seed in enumerate(seeds):
        if seed in existing:
            pairs.append(existing[seed])
            continue
        cameras, points, scales = perturb(problem, seed, EPSILON)
        path = pathlib.Path(f"/dev/shm/eta2-d22-{seed}.txt")
        write_state(problem, path, cameras, points)
        cell = {"scene": "final-3068", "cell": f"final-3068-seed-{seed}",
                "path": str(path), "input_sha256": sha256(path),
                "target": TARGET, "cap": CAP}
        order = ["control", "d22"] if index % 2 == 0 else ["d22", "control"]
        rows = {}
        try:
            for arm in order:
                rows[arm] = run_arm(reg, cell, seed, index, arm)
        finally:
            N.OBSERVATIONS.pop(str(path), None)
            path.unlink(missing_ok=True)
        pair = {
            "index": index, "seed": seed, "epsilon": EPSILON,
            "input_sha256": cell["input_sha256"], "field_scales": scales,
            "initial_residual_distance": residual_distance(
                problem, initial, state_from_bal(problem, cameras, points)),
            "control": rows["control"], "d22": rows["d22"],
        }
        existing[seed] = pair
        pairs.append(pair)
        ordered = [existing[s] for s in sorted(existing)]
        N.write(result_path, ordered)
        report = summarize(pairs, "screen" if len(seeds) == 5 else "full")
        N.write(W6 / "d22-final3068-summary.json", report)
        print("PAIR", len(pairs), "seed", seed, "hits", int(rows["control"]["hit"]),
              int(rows["d22"]["hit"]), "called", rows["d22"]["d22"]["calls"],
              "wins", rows["d22"]["d22"]["wins"],
              "decrease", rows["d22"]["d22"]["decrease"], flush=True)
    report = summarize(pairs, "screen" if len(seeds) == 5 else "full")
    N.write(W6 / "d22-final3068-summary.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["register", "compatibility", "screen", "extend", "summarize"])
    args = parser.parse_args()
    reg = registration()
    if args.stage == "register":
        result = reg
    elif args.stage == "compatibility":
        result = compatibility(reg)
    elif args.stage in ("screen", "extend"):
        result = execute(reg, args.stage)
    else:
        pairs = json.loads((W6 / "d22-final3068-results.json").read_text())
        result = summarize(pairs, "full" if len(pairs) == 10 else "screen")
        N.write(W6 / "d22-final3068-summary.json", result)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
