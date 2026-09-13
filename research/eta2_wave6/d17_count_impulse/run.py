#!/usr/bin/env python3
"""Compatibility and development replay for D17."""
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
from bal_perturb import (load_bal, perturb, residual_distance, sha256,
                         state_from_bal, write_state)  # noqa: E402

N.HERE = WAVE6
PARENT = WAVE6 / "build" / "prism-deterministic"
BINARY = pathlib.Path("/tmp/prism-wave6-d17/prism-d17")
PROTOCOL = WAVE6 / "D17_COUNT_IMPULSE_PROTOCOL.md"
BUILD = HERE / "build-manifest.json"
SOURCE = pathlib.Path("/workspace/bal/final-3068.txt")
TARGET = 1744796.9841897595
SEEDS = list(range(660024, 660048))
EPSILON = 1e-12
OPTIMIZED = json.loads((WAVE5 / "optimized_candidate.json").read_text())
FLAGS = {**OPTIMIZED["flags_overlay"], "OCA_W6_DETERMINISTIC": "1"}


def canonical(value) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def registration() -> dict:
    build = json.loads(BUILD.read_text())
    parent_manifest = json.loads((WAVE6 / "deterministic-build-manifest.json").read_text())
    assert sha256(BINARY) == build["binary_sha256"]
    assert sha256(PARENT) == parent_manifest["binary_sha256"]
    assert all(sha256(path) == digest for path, digest in build["sources"].items())
    base = json.loads((WAVE5 / "b1-registration.json").read_text())
    reg = {
        "protocol_sha256": sha256(PROTOCOL),
        "build_manifest": build,
        "runner_sha256": sha256(HERE / "run.py"),
        "parent_binary": str(PARENT), "parent_sha256": sha256(PARENT),
        "derived_binary": str(BINARY), "derived_sha256": sha256(BINARY),
        "source": str(SOURCE), "source_sha256": sha256(SOURCE),
        "target": TARGET, "cap": 60, "epsilon": EPSILON, "seeds": SEEDS,
        "flags": FLAGS,
        "compatibility": next(x for x in base["practical"] if x["cell"] == "ladybug-539-1.01"),
        "development_advance": {
            "minimum_net_hits": 2,
            "maximum_control_only_harms": 1,
            "maximum_median_double_hit_time_ratio": 1.20,
            "confirmatory": False,
        },
    }
    N.write(WAVE6 / "d17-development-registration.json", reg)
    return reg


def trace_fields(row: dict) -> dict:
    folder = WAVE6 / row["source"]
    curve = list(csv.DictReader(x for x in (folder / "curve.csv").read_text().splitlines()
                                if not x.startswith("#")))
    row["accepted_cost_strings"] = [x["cost"] for x in curve]
    row["accepted_cost_hash"] = canonical(row["accepted_cost_strings"])
    prefixes = ("PCG_PREP ", "ATTR_RADIUS ", "CLASSICAL_LM ", "POINT_SAFE o=",
                "MFCG it ", "NUMERIC_REPAIR ")
    lines = [line.strip() for line in (folder / "stdout.log").read_text().splitlines()
             if line.strip().startswith(prefixes)]
    row["decision_hash"] = canonical(lines)
    row["decision_lines"] = lines
    text = (folder / "stdout.log").read_text()
    tests = list(re.finditer(
        r"D17_TEST o=(\d+) retry=(\d+) ratio=(\S+) gated_fraction=(\S+) "
        r"raw=(\S+) radius=(\S+) trigger=(\d+) post_raw=(\S+) post_ratio=(\S+)", text))
    summary = re.search(r"D17_SUMMARY tests=(\d+) impulses=(\d+) spent=(\d+)", text)
    fired = next((m for m in tests if int(m[7])), None)
    row["d17"] = {
        "tests": int(summary[1]) if summary else 0,
        "impulses": int(summary[2]) if summary else 0,
        "spent": bool(int(summary[3])) if summary else False,
        "trigger_outer": int(fired[1]) if fired else None,
        "trigger_retry": int(fired[2]) if fired else None,
        "trigger_ratio": float(fired[3]) if fired else None,
        "trigger_fraction": float(fired[4]) if fired else None,
        "post_ratio": float(fired[9]) if fired else None,
    }
    N.write(folder / "result.json", row)
    return row


def compatibility(reg: dict) -> dict:
    cell = reg["compatibility"]
    rows = []
    for arm, binary in [("d0v3-parent", PARENT), ("d17-derived-off", BINARY)]:
        folder = WAVE6 / "evidence" / "d17-compatibility" / arm
        rows.append(trace_fields(N.run(folder, cell, arm, 0, binary, FLAGS, PROTOCOL,
                                       reg["build_manifest"])))
    keys = ["state_sha256", "accepted_cost_hash", "decision_hash", "hit", "outers",
            "rejects", "matvecs", "cost"]
    result = {"rows": rows, "equal": {k: rows[0][k] == rows[1][k] for k in keys}}
    result["passed"] = all(result["equal"].values())
    N.write(WAVE6 / "d17-compatibility.json", result)
    if not result["passed"]:
        raise SystemExit(2)
    return result


def summarize(rows: list[dict], controls: dict[int, dict], reg: dict) -> dict:
    pairs = [{"seed": r["seed"], "control": controls[r["seed"]], "d17": r} for r in rows]
    rescues = [p for p in pairs if p["d17"]["hit"] and not p["control"]["hit"]]
    harms = [p for p in pairs if p["control"]["hit"] and not p["d17"]["hit"]]
    double = [p for p in pairs if p["control"]["hit"] and p["d17"]["hit"]]
    ratios = [p["d17"]["target_seconds"] / p["control"]["target_seconds"] for p in double]
    gate = reg["development_advance"]
    report = {
        "confirmatory": False,
        "pairs": len(pairs),
        "control_hits": sum(p["control"]["hit"] for p in pairs),
        "d17_hits": sum(p["d17"]["hit"] for p in pairs),
        "d17_only_rescues": len(rescues),
        "control_only_harms": len(harms),
        "double_hits": len(double),
        "double_misses": sum(not p["control"]["hit"] and not p["d17"]["hit"] for p in pairs),
        "impulse_pairs": sum(p["d17"]["d17"]["impulses"] for p in pairs),
        "median_double_hit_time_ratio": statistics.median(ratios) if ratios else None,
        "paired_endpoint_delta_median": statistics.median(
            p["d17"]["cost"] / p["control"]["cost"] - 1 for p in pairs),
        "rescue_seeds": [p["seed"] for p in rescues],
        "harm_seeds": [p["seed"] for p in harms],
    }
    report["advance"] = (
        report["d17_hits"] - report["control_hits"] >= gate["minimum_net_hits"]
        and report["control_only_harms"] <= gate["maximum_control_only_harms"]
        and ratios and report["median_double_hit_time_ratio"] <= gate["maximum_median_double_hit_time_ratio"]
    )
    return report


def replay(reg: dict) -> dict:
    assert json.loads((WAVE6 / "d17-compatibility.json").read_text())["passed"]
    old = json.loads((WAVE6 / "d16-paired-results.json").read_text())
    controls = {p["seed"]: p["control"] for p in old}
    problem = load_bal(SOURCE)
    initial = state_from_bal(problem)
    path_out = WAVE6 / "d17-development-results.json"
    existing = {r["seed"]: r for r in json.loads(path_out.read_text())} if path_out.exists() else {}
    rows = []
    for index, seed in enumerate(SEEDS):
        if seed in existing:
            rows.append(existing[seed])
            continue
        cameras, points, scales = perturb(problem, seed, EPSILON)
        path = pathlib.Path(f"/dev/shm/eta2-d17-development-{seed}.txt")
        write_state(problem, path, cameras, points)
        input_hash = sha256(path)
        assert input_hash == old[index]["input_sha256"]
        cell = {"scene": "final-3068", "cell": f"final-3068-seed-{seed}",
                "path": str(path), "input_sha256": input_hash, "target": TARGET, "cap": 60}
        flags = {**FLAGS, "OCA_D17_COUNT_IMPULSE": "1"}
        folder = WAVE6 / "evidence" / "d17-development" / str(seed)
        try:
            row = trace_fields(N.run(folder, cell, "d17", index, BINARY, flags,
                                     PROTOCOL, reg["build_manifest"]))
        finally:
            N.OBSERVATIONS.pop(str(path), None)
            path.unlink(missing_ok=True)
        row.update({"seed": seed, "epsilon": EPSILON, "field_scales": scales,
                    "initial_residual_distance": residual_distance(
                        problem, initial, state_from_bal(problem, cameras, points))})
        rows.append(row)
        N.write(path_out, rows)
        partial = summarize(rows, controls, reg)
        print("D17", index + 1, seed, "hits", int(controls[seed]["hit"]), int(row["hit"]),
              "impulse", row["d17"]["impulses"], "net",
              partial["d17_hits"] - partial["control_hits"], flush=True)
    report = summarize(rows, controls, reg)
    N.write(WAVE6 / "d17-development-summary.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["register", "compatibility", "replay", "summarize"])
    args = parser.parse_args()
    reg = registration()
    if args.stage == "register":
        result = reg
    elif args.stage == "compatibility":
        result = compatibility(reg)
    elif args.stage == "replay":
        result = replay(reg)
    else:
        old = json.loads((WAVE6 / "d16-paired-results.json").read_text())
        controls = {p["seed"]: p["control"] for p in old}
        result = summarize(json.loads((WAVE6 / "d17-development-results.json").read_text()), controls, reg)
        N.write(WAVE6 / "d17-development-summary.json", result)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
