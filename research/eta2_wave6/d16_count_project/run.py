#!/usr/bin/env python3
"""Deterministic common-random-number confirmation for D16."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import pathlib
import re
import statistics
import sys

HERE = pathlib.Path(__file__).resolve().parent
WAVE6 = HERE.parent
WAVE5 = WAVE6.parent / "eta2_wave5"
sys.path[:0] = [str(WAVE6), str(WAVE5)]

import native_light as N  # noqa: E402
from bal_perturb import (field_scales, load_bal, perturb, residual_distance, sha256,
                         state_from_bal, write_state)  # noqa: E402
from paired_sprt import PairedSprt  # noqa: E402

N.HERE = WAVE6

PARENT = WAVE6 / "build" / "prism-deterministic"
BINARY = pathlib.Path("/tmp/prism-wave6-d16/prism-d16")
BUILD = HERE / "build-manifest.json"
PROTOCOL = WAVE6 / "D16_COUNT_PROJECT_PROTOCOL.md"
SOURCE = pathlib.Path("/workspace/bal/final-3068.txt")
TARGET = 1744796.9841897595
SEEDS = list(range(660024, 660048))
EPSILON = 1e-12
OPTIMIZED = json.loads((WAVE5 / "optimized_candidate.json").read_text())
FLAGS = {**OPTIMIZED["flags_overlay"], "OCA_W6_DETERMINISTIC": "1"}


def canonical(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def registration() -> dict:
    build = json.loads(BUILD.read_text())
    assert sha256(BINARY) == build["binary_sha256"]
    assert sha256(PARENT) == json.loads((WAVE6 / "deterministic-build-manifest.json").read_text())["binary_sha256"]
    assert all(sha256(path) == digest for path, digest in build["sources"].items())
    base = json.loads((WAVE5 / "b1-registration.json").read_text())
    reg = {
        "protocol_sha256": sha256(PROTOCOL), "build_manifest": build,
        "runner_sha256": sha256(HERE / "run.py"),
        "parent_binary": str(PARENT), "parent_sha256": sha256(PARENT),
        "derived_binary": str(BINARY), "derived_sha256": sha256(BINARY),
        "source": str(SOURCE), "source_sha256": sha256(SOURCE),
        "target": TARGET, "cap": 60, "epsilon": EPSILON, "seeds": SEEDS,
        "flags": FLAGS,
        "compatibility": next(x for x in base["practical"] if x["cell"] == "ladybug-539-1.01"),
        "sprt": {"q0": .50, "q1": .70, "alpha": .05, "beta": .05,
                 "max_pairs": len(SEEDS)},
        "arm_order": "control,d16 on even pair index; d16,control on odd pair index",
    }
    N.write(WAVE6 / "d16-paired-registration.json", reg)
    return reg


def trace_fields(row: dict) -> dict:
    folder = WAVE6 / row["source"]
    curve = list(csv.DictReader(x for x in (folder / "curve.csv").read_text().splitlines()
                                if not x.startswith("#")))
    row["accepted_cost_strings"] = [x["cost"] for x in curve]
    row["accepted_cost_hash"] = canonical(row["accepted_cost_strings"])
    prefixes = ("PCG_PREP ", "ATTR_RADIUS ", "CLASSICAL_LM ", "POINT_SAFE o=",
                "MFCG it ", "NUMERIC_REPAIR ")
    lines = []
    for line in (folder / "stdout.log").read_text().splitlines():
        line = line.strip()
        if line.startswith(prefixes):
            lines.append(line.replace(" d16_prior=0", ""))
    row["decision_hash"] = canonical(lines)
    row["decision_lines"] = lines
    tests = list(re.finditer(
        r"D16_TEST o=(\d+) retry=(\d+) ratio=(\S+) gated_fraction=(\S+) "
        r"raw=(\S+) radius=(\S+) trigger=(\d+) post_raw=(\S+) post_ratio=(\S+)",
        (folder / "stdout.log").read_text(),
    ))
    summary = re.search(r"D16_SUMMARY tests=(\d+) projections=(\d+)",
                        (folder / "stdout.log").read_text())
    row["d16"] = {
        "tests": int(summary[1]) if summary else 0,
        "projections": int(summary[2]) if summary else 0,
        "max_ratio": max((float(m[3]) for m in tests), default=None),
        "max_gated_fraction": max((float(m[4]) for m in tests), default=None),
        "min_post_ratio": min((float(m[9]) for m in tests if int(m[7])), default=None),
    }
    N.write(folder / "result.json", row)
    return row


def compatibility(reg: dict) -> dict:
    cell = reg["compatibility"]
    rows = []
    for arm, binary in [("d0v3-parent", PARENT), ("d16-derived-off", BINARY)]:
        folder = WAVE6 / "evidence" / "d16-paired-compatibility" / arm
        rows.append(trace_fields(N.run(folder, cell, arm, 0, binary, FLAGS, PROTOCOL,
                                       reg["build_manifest"])))
    keys = ["state_sha256", "accepted_cost_hash", "decision_hash", "hit", "outers",
            "rejects", "matvecs", "cost"]
    result = {"rows": rows, "equal": {k: rows[0][k] == rows[1][k] for k in keys}}
    result["passed"] = all(result["equal"].values())
    N.write(WAVE6 / "d16-paired-compatibility.json", result)
    if not result["passed"]:
        raise SystemExit(2)
    return result


def run_arm(reg: dict, cell: dict, seed: int, index: int, arm: str) -> dict:
    folder = WAVE6 / "evidence" / "d16-paired-final3068" / f"{seed}-{arm}"
    flags = dict(FLAGS)
    if arm == "d16":
        flags["OCA_D16_COUNT_PROJECT"] = "1"
    return trace_fields(N.run(folder, cell, arm, index, BINARY, flags, PROTOCOL,
                              reg["build_manifest"]))


def exact_one_sided(wins: int, discordant: int) -> float:
    if not discordant:
        return 1.0
    return sum(math.comb(discordant, k) for k in range(wins, discordant + 1)) / 2**discordant


def summarize(pairs: list[dict], reg: dict) -> dict:
    s = PairedSprt(**reg["sprt"])
    for pair in pairs:
        if s.decision != "continue":
            break
        s.update(pair["control"]["hit"], pair["d16"]["hit"])
    double = [p for p in pairs if p["control"]["hit"] and p["d16"]["hit"]]
    endpoint = [p["d16"]["cost"] / p["control"]["cost"] - 1 for p in pairs]
    time_ratios = [p["d16"]["target_seconds"] / p["control"]["target_seconds"]
                   for p in double]
    report = s.report()
    report.update({
        "completed_pairs": len(pairs),
        "control_hits": sum(p["control"]["hit"] for p in pairs),
        "d16_hits": sum(p["d16"]["hit"] for p in pairs),
        "exact_one_sided_mcnemar_p": exact_one_sided(s.variant_wins, s.discordant),
        "double_hit_pairs": len(double),
        "median_double_hit_time_ratio": statistics.median(time_ratios) if time_ratios else None,
        "double_hit_time_ratio_range": [min(time_ratios), max(time_ratios)] if time_ratios else None,
        "median_paired_endpoint_delta": statistics.median(endpoint),
        "paired_endpoint_delta_range": [min(endpoint), max(endpoint)],
        "d16_activated_pairs": sum(p["d16"]["d16"]["projections"] > 0 for p in pairs),
        "d16_total_projections": sum(p["d16"]["d16"]["projections"] for p in pairs),
        "promotion_time_gate": (
            bool(time_ratios) and statistics.median(time_ratios) <= 1.20
        ),
    })
    report["promote"] = report["decision"] == "noninferior" and report["promotion_time_gate"]
    # paired_sprt's legacy label means the directional q1 boundary; spell it out here.
    report["decision_interpretation"] = {
        "noninferior": "D16-better boundary",
        "harmful": "D16-harmful boundary",
        "continue": "continue registered pairs",
        "inconclusive_at_cap": "unresolved at 24-pair cap",
    }[report["decision"]]
    return report


def execute(reg: dict) -> dict:
    assert json.loads((WAVE6 / "d16-paired-compatibility.json").read_text())["passed"]
    problem = load_bal(SOURCE)
    initial = state_from_bal(problem)
    pairs = []
    result_path = WAVE6 / "d16-paired-results.json"
    existing = {p["seed"]: p for p in json.loads(result_path.read_text())} if result_path.exists() else {}
    for index, seed in enumerate(SEEDS):
        if seed in existing:
            pairs.append(existing[seed])
            if summarize(pairs, reg)["decision"] != "continue":
                break
            continue
        cameras, points, scales = perturb(problem, seed, EPSILON)
        path = pathlib.Path(f"/dev/shm/eta2-d16-paired-{seed}.txt")
        write_state(problem, path, cameras, points)
        input_hash = sha256(path)
        distance = residual_distance(problem, initial, state_from_bal(problem, cameras, points))
        cell = {"scene": "final-3068", "cell": f"final-3068-seed-{seed}",
                "path": str(path), "input_sha256": input_hash, "target": TARGET, "cap": 60}
        arms = ["control", "d16"] if index % 2 == 0 else ["d16", "control"]
        rows = {}
        try:
            for arm in arms:
                rows[arm] = run_arm(reg, cell, seed, index, arm)
        finally:
            N.OBSERVATIONS.pop(str(path), None)
            path.unlink(missing_ok=True)
        pair = {"index": index, "seed": seed, "epsilon": EPSILON,
                "input_sha256": input_hash, "field_scales": scales,
                "initial_residual_distance": distance,
                "control": rows["control"], "d16": rows["d16"]}
        pairs.append(pair)
        N.write(result_path, pairs)
        report = summarize(pairs, reg)
        N.write(WAVE6 / "d16-paired-summary.json", report)
        print("PAIR", index + 1, "seed", seed,
              "hits", int(pair["control"]["hit"]), int(pair["d16"]["hit"]),
              "projections", pair["d16"]["d16"]["projections"],
              "sprt", report["decision"], "llr", round(report["log_likelihood_ratio"], 4),
              flush=True)
        if report["decision"] != "continue":
            break
    report = summarize(pairs, reg)
    N.write(WAVE6 / "d16-paired-summary.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["register", "compatibility", "run", "summarize"])
    args = parser.parse_args()
    reg = registration()
    if args.stage == "register":
        result = reg
    elif args.stage == "compatibility":
        result = compatibility(reg)
    elif args.stage == "run":
        result = execute(reg)
    else:
        result = summarize(json.loads((WAVE6 / "d16-paired-results.json").read_text()), reg)
        N.write(WAVE6 / "d16-paired-summary.json", result)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
