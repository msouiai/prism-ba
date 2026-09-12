#!/usr/bin/env python3
"""Register and execute the wave-6 fixed-reduction validation."""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import statistics
import subprocess
import sys

P = Path(__file__).resolve().parent
W5 = P.parent / "eta2_wave5"
sys.path.insert(0, str(W5))
import native_light as N

PROTOCOL = P / "D0_PROTOCOL.md"
DERIVED = P / "build" / "prism-deterministic"
B6V7 = W5 / "build" / "prism-b6v7"
OPTIMIZED = json.loads((W5 / "optimized_candidate.json").read_text())
FLAGS = OPTIMIZED["flags_overlay"]


def canonical_hash(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def registration():
    build = json.loads((P / "deterministic-build-manifest.json").read_text())
    old = json.loads((W5 / "b6v7-registration.json").read_text())
    calm = next(c for c in old["practical"] if c["cell"] == "ladybug-539-1.01")
    reg = {
        "protocol_sha256": N.sha(PROTOCOL),
        "champion_sha256": N.sha(N.FROZEN / "champion.json"),
        "optimized_candidate_sha256": N.sha(W5 / "optimized_candidate.json"),
        "derived_binary": str(DERIVED),
        "derived_binary_sha256": N.sha(DERIVED),
        "b6v7_binary": str(B6V7),
        "b6v7_binary_sha256": N.sha(B6V7),
        "build_manifest": build,
        "flags": FLAGS,
        "compatibility": {"cell": calm, "repetitions": 3, "cost_tolerance": 0.0015},
        "repeatability": {"cells": old["tails"], "repetitions": 5},
        "arm_order": "reverse on odd repetition",
        "decision": "all exact repeatability fields equal; no cap stop; disabled median cost delta below 0.15%",
    }
    path = P / "d0-registration.json"
    if path.exists():
        assert json.loads(path.read_text()) == reg
    else:
        N.write(path, reg)
    return reg


def add_trace_fields(row):
    folder = P / row["source"]
    curves = list(csv.DictReader(x for x in (folder / "curve.csv").read_text().splitlines()
                                 if not x.startswith("#")))
    row["accepted_cost_strings"] = [x["cost"] for x in curves]
    row["accepted_cost_hash"] = canonical_hash(row["accepted_cost_strings"])
    prefixes = ("PCG_PREP ", "ATTR_RADIUS ", "CLASSICAL_LM ", "POINT_SAFE ",
                "  MFCG it ", "NUMERIC_REPAIR ")
    lines = [line.strip() for line in (folder / "stdout.log").read_text().splitlines()
             if line.startswith(prefixes)]
    row["decision_lines"] = lines
    row["decision_hash"] = canonical_hash(lines)
    N.write(folder / "result.json", row)
    return row


def run_one(reg, stage, cell, arm, rep):
    binary = B6V7 if arm == "b6v7" else DERIVED
    flags = dict(FLAGS)
    if arm == "deterministic":
        flags["OCA_W6_DETERMINISTIC"] = "1"
    folder = P / "evidence" / stage / f"{cell.get('cell', cell['scene'])}-{arm}-{rep}"
    row = N.run(folder, cell, arm, rep, binary, flags, PROTOCOL, reg["build_manifest"])
    return add_trace_fields(row)


def execute(reg):
    rows = []
    cell = reg["compatibility"]["cell"]
    for rep in range(reg["compatibility"]["repetitions"]):
        arms = ["b6v7", "derived-off"]
        if rep % 2:
            arms.reverse()
        for arm in arms:
            rows.append(run_one(reg, "d0-compatibility", cell, arm, rep))
            N.write(P / "d0-results.json", rows)
    for name, cell in reg["repeatability"]["cells"].items():
        for rep in range(reg["repeatability"]["repetitions"]):
            rows.append(run_one(reg, "d0-repeatability", cell, "deterministic", rep))
            N.write(P / "d0-results.json", rows)
    return rows


def summarize(reg, rows):
    comp = [r for r in rows if r["arm"] in ("b6v7", "derived-off")]
    med = {arm: statistics.median(r["cost"] for r in comp if r["arm"] == arm)
           for arm in ("b6v7", "derived-off")}
    delta = med["derived-off"] / med["b6v7"] - 1.0
    compatibility = {
        "medians": med, "relative_cost_delta": delta,
        "passed": all(r["valid"] for r in comp) and abs(delta) < reg["compatibility"]["cost_tolerance"],
    }
    fields = ["state_sha256", "accepted_cost_hash", "decision_hash", "cost", "outers",
              "accepts", "rejects", "matvecs", "hit", "cap_hit", "stop_ftol"]
    repeatability = {}
    for scene in reg["repeatability"]["cells"]:
        group = [r for r in rows if r["scene"] == scene and r["arm"] == "deterministic"]
        unique = {field: sorted({json.dumps(r[field], sort_keys=True) for r in group})
                  for field in fields}
        repeatability[scene] = {
            "runs": len(group), "unique_counts": {k: len(v) for k, v in unique.items()},
            "values": unique,
            "passed": len(group) == reg["repeatability"]["repetitions"]
                      and all(len(v) == 1 for v in unique.values())
                      and not any(r["cap_hit"] for r in group),
            "native_seconds": [r["native_seconds"] for r in group],
        }
    summary = {"compatibility": compatibility, "repeatability": repeatability}
    summary["passed"] = compatibility["passed"] and all(x["passed"] for x in repeatability.values())
    N.write(P / "d0-summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["register", "run", "summarize"])
    args = parser.parse_args()
    reg = registration()
    if args.stage == "register":
        print(json.dumps(reg, indent=2))
        return
    rows = execute(reg) if args.stage == "run" else json.loads((P / "d0-results.json").read_text())
    result = summarize(reg, rows)
    print(json.dumps(result, indent=2))
    if not result["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
