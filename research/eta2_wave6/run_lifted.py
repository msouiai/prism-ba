#!/usr/bin/env python3
"""Registered D9 lifted-opening compatibility and tail screen."""
from pathlib import Path
import argparse
import json
import re
import statistics
import subprocess
import sys

P = Path(__file__).resolve().parent
W5 = P.parent / "eta2_wave5"
sys.path.insert(0, str(W5))
import native_light as N
import run_b6 as B

PROTOCOL = P / "D9_LIFTED_ROBUST_PROTOCOL.md"
BINARY = P / "build" / "prism-lifted"
PARENT = W5 / "build" / "prism-b6v7"
OPT = json.loads((W5 / "optimized_candidate.json").read_text())["flags_overlay"]
ARMS = {"control": dict(OPT), "lift3": dict(OPT, OCA_W6_LIFTED="1")}
N.HERE = P


def register():
    subprocess.run(["python3", str(N.FROZEN / "build.py"), "--check-only"], check=True)
    build = json.loads((P / "d9-lifted-build-manifest.json").read_text())
    assert N.sha(BINARY) == build["binary_sha256"]
    assert N.sha(PARENT) == build["b6v7_binary_sha256"]
    assert all(N.sha(path) == digest for path, digest in build["sources"].items())
    old = json.loads((W5 / "b6v7-registration.json").read_text())
    reg = {
        "arms": ARMS,
        "tails": old["tails"],
        "practical": old["practical"],
        "tail_repetitions": 5,
        "compatibility_repetitions": 3,
        "binary": str(BINARY), "binary_sha256": N.sha(BINARY),
        "parent_binary": str(PARENT), "parent_binary_sha256": N.sha(PARENT),
        "build_manifest": build, "protocol_sha256": N.sha(PROTOCOL),
        "implementation_amendment_sha256": N.sha(P / "D9_IMPLEMENTATION_AMENDMENT.md"),
        "cohort_rule": "Fresh paired rows; reverse cell and arm order on odd repetitions",
        "registered_arm": "three-accepted-step persistent smooth lifted robust opening, then L2 Eta2",
    }
    path = P / "d9v2-lifted-registration.json"
    if path.exists():
        assert json.loads(path.read_text()) == reg
    else:
        N.write(path, reg)
    return reg


def enrich(row):
    log = (P / row["source"] / "stdout.log").read_text()
    hand = re.search(
        r"W6_LIFT_HANDOFF accepts=(\d+) lifted=(\S+) l2=(\S+) "
        r"w_min=(\S+) w_p10=(\S+) w_med=(\S+) w_p90=(\S+) w_max=(\S+) "
        r"below_half=(\d+) retry_rebuilds=(\d+)", log)
    init = re.search(r"W6_LIFT_INIT accepts=(\d+) tau2=(\S+) median_r2=(\S+)", log)
    incomplete = re.search(r"W6_LIFT_INCOMPLETE accepts=(\d+) l2=(\S+)", log)
    row["lift_enabled"] = bool(init)
    row["lift_handoff"] = bool(hand)
    row["lift_incomplete"] = bool(incomplete)
    if init:
        row["lift_tau2"] = float(init[2])
    if hand:
        row["lift_opening_accepts"] = int(hand[1])
        row["lifted_cost_at_handoff"] = float(hand[2])
        row["l2_cost_at_handoff"] = float(hand[3])
        row["weight_stats"] = {
            "min": float(hand[4]), "p10": float(hand[5]),
            "median": float(hand[6]), "p90": float(hand[7]),
            "max": float(hand[8]), "below_half": int(hand[9]),
        }
        row["lift_retry_rebuilds"] = int(hand[10])
    N.write(P / row["source"] / "result.json", row)
    return row


def execute(reg, stage, cells, arms, reps):
    rows = []
    for rep in range(reps):
        ordered_cells, ordered_arms = list(cells), list(arms)
        if rep % 2:
            ordered_cells.reverse(); ordered_arms.reverse()
        for cell in ordered_cells:
            for arm in ordered_arms:
                binary = PARENT if arm == "parent" else BINARY
                flags = dict(OPT) if arm in ("parent", "derived-off") else ARMS[arm]
                folder = P / "evidence" / stage / f"{cell.get('cell',cell['scene'])}-{arm}-{rep}"
                row = N.run(folder, cell, arm, rep, binary, flags, PROTOCOL,
                            reg["build_manifest"])
                rows.append(enrich(row))
                N.write(P / f"{stage}-results.json", rows)
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["compatibility", "diagnostic", "tails", "panel"])
    args = parser.parse_args(); reg = register()
    calm = next(x for x in reg["practical"] if x["cell"] == "ladybug-539-1.01")
    if args.stage == "compatibility":
        rows = execute(reg, "d9v2-lifted-compatibility", [calm], ["parent", "derived-off"], 3)
        med = {arm: statistics.median(r["cost"] for r in rows if r["arm"] == arm)
               for arm in ("parent", "derived-off")}
        result = {"rows": len(rows), "medians": med,
                  "relative_delta": med["derived-off"]/med["parent"]-1}
        result["passed"] = abs(result["relative_delta"]) < .0015
        N.write(P / "d9v2-lifted-compatibility-summary.json", result)
        assert result["passed"], result
    elif args.stage == "diagnostic":
        rows = execute(reg, "d9v2-lifted-diagnostic", [calm], ["lift3"], 1)
        result = {"passed": rows[0]["lift_handoff"] and
                            rows[0].get("lift_opening_accepts") == 3 and
                            not rows[0]["lift_incomplete"], "row": rows[0]}
        N.write(P / "d9v2-lifted-diagnostic-summary.json", result)
        assert result["passed"], result
    elif args.stage == "tails":
        assert json.loads((P / "d9v2-lifted-compatibility-summary.json").read_text())["passed"]
        assert json.loads((P / "d9v2-lifted-diagnostic-summary.json").read_text())["passed"]
        rows = execute(reg, "d9v2-lifted-tails", list(reg["tails"].values()),
                       ["control", "lift3"], reg["tail_repetitions"])
        result = B.summarize(rows, ("control", "lift3"))
        N.write(P / "d9v2-lifted-tails-summary.json", result)
    else:
        rows = execute(reg, "d9v2-lifted-panel", reg["practical"],
                       ["control", "lift3"], 3)
        result = B.summarize(rows, ("control", "lift3"))
        N.write(P / "d9v2-lifted-panel-summary.json", result)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
