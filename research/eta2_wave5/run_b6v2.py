#!/usr/bin/env python3
"""Registered B6v2 dots-only synchronization measurements."""
from pathlib import Path
import argparse
import json
import re
import statistics
import subprocess

import native_light as N
import run_b6 as B

P = Path(__file__).resolve().parent
BINARY = P / "build" / "prism-b6v2"
PARENT = Path(N.CHAMPION["binary"])
PROTOCOL = P / "B6V2_PROTOCOL.md"
ARMS = {"off": {}, "dots": {"OCA_W5_CG_DOTS": "1"}}


def register():
    subprocess.run(["python3", str(N.FROZEN / "build.py"), "--check-only"], check=True)
    build = json.loads((P / "b6v2-build-manifest.json").read_text())
    assert N.sha(BINARY) == build["binary_sha256"]
    assert all(N.sha(path) == digest for path, digest in build["sources"].items())
    old = json.loads((P / "b1-registration.json").read_text())
    reg = {
        "arms": ARMS, "practical": old["practical"], "tails": old["tails"],
        "muell": old["muell"], "panel_repetitions": 3, "tail_repetitions": 10,
        "binary": str(BINARY), "binary_sha256": N.sha(BINARY),
        "parent_binary": str(PARENT), "parent_binary_sha256": N.sha(PARENT),
        "build_manifest": build, "protocol_sha256": N.sha(PROTOCOL),
        "cohort_rule": "Fresh paired rows; alternating arms and reversed cells on odd repetitions",
        "registered_arm": "Device-result cuBLAS dot pairs; original cuBLAS vector updates retained",
    }
    path = P / "b6v2-registration.json"
    if path.exists():
        assert json.loads(path.read_text()) == reg
    else:
        N.write(path, reg)
    return reg


def enrich(row):
    log = (P / row["source"] / "stdout.log").read_text()
    active = re.search(r"W5_CG_DOTS active n=(\d+)", log)
    summary = re.search(r"W5_CG_DOTS summary dot_pairs=(\d+)", log)
    profile = re.search(
        r"\[PROFILE\] assembly=(\S+)s pointfactor\+rhs=(\S+)s krylov=(\S+)s candidates=(\S+)s", log)
    row["cg_dots_active"] = bool(active)
    if active:
        row["cg_dimension"] = int(active[1])
    if summary:
        row["batched_dot_pairs"] = int(summary[1])
    if profile:
        row["profile_seconds"] = {
            "assembly": float(profile[1]), "pointfactor_rhs": float(profile[2]),
            "krylov": float(profile[3]), "candidates": float(profile[4]),
        }
    N.write(P / row["source"] / "result.json", row)
    return row


def execute(reg, stage, cells, arms, reps, extra=None):
    rows = []; extra = extra or {}
    for rep in range(reps):
        ordered_cells, ordered_arms = list(cells), list(arms)
        if rep % 2:
            ordered_cells.reverse(); ordered_arms.reverse()
        for cell in ordered_cells:
            for arm in ordered_arms:
                binary = PARENT if arm == "parent-off" else BINARY
                flags = {} if arm == "parent-off" else dict(ARMS[arm], **extra)
                folder = P / "evidence" / stage / f"{cell.get('cell', cell['scene'])}-{arm}-{rep}"
                row = N.run(folder, cell, arm, rep, binary, flags, PROTOCOL,
                            reg["build_manifest"])
                rows.append(enrich(row)); N.write(P / f"{stage}-results.json", rows)
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["compatibility", "panel", "profile", "muell", "tails"])
    args = parser.parse_args(); reg = register()
    calm = next(cell for cell in reg["practical"] if cell["cell"] == "ladybug-539-1.01")
    if args.stage == "compatibility":
        rows = execute(reg, "b6v2-compatibility", [calm], ["off", "parent-off"], 3)
        med = {arm: statistics.median(row["cost"] for row in rows if row["arm"] == arm)
               for arm in ("off", "parent-off")}
        result = {"rows": len(rows), "medians": med,
                  "relative_delta": med["off"] / med["parent-off"] - 1}
        result["passed"] = abs(result["relative_delta"]) < .0015
        N.write(P / "b6v2-compatibility-summary.json", result); assert result["passed"], result
    elif args.stage == "panel":
        assert json.loads((P / "b6v2-compatibility-summary.json").read_text())["passed"]
        result = B.summarize(execute(reg, "b6v2-panel", reg["practical"], list(ARMS), 3),
                             ("off", "dots"))
        N.write(P / "b6v2-panel-summary.json", result)
    elif args.stage == "profile":
        traf = next(cell for cell in reg["practical"] if cell["cell"] == "trafalgar-138-1.005")
        rows = execute(reg, "b6v2-profile", [traf, reg["muell"]], list(ARMS), 3,
                       {"OCA_PROFILE": "1"})
        result = B.summarize(rows, ("off", "dots"))
        for cell in result["cells"]:
            for arm in ARMS:
                group = [row for row in rows if row["cell"] == cell["cell"] and row["arm"] == arm]
                cell[arm]["median_profile_seconds"] = {
                    phase: statistics.median(row["profile_seconds"][phase] for row in group)
                    for phase in ("assembly", "pointfactor_rhs", "krylov", "candidates")
                }
        N.write(P / "b6v2-profile-summary.json", result)
    elif args.stage == "muell":
        result = B.summarize(execute(reg, "b6v2-muell", [reg["muell"]], list(ARMS), 3),
                             ("off", "dots"))
        N.write(P / "b6v2-muell-summary.json", result)
    else:
        result = B.summarize(execute(reg, "b6v2-tails", list(reg["tails"].values()),
                                     list(ARMS), 10), ("off", "dots"))
        N.write(P / "b6v2-tails-summary.json", result)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()

