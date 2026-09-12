#!/usr/bin/env python3
"""Run registered B6v6 deterministic camera-major RHS measurements."""
from pathlib import Path
import argparse
import json
import re
import statistics
import subprocess

import native_light as N
import run_b6 as B

P = Path(__file__).resolve().parent
BINARY = P / "build" / "prism-b6v6"
PARENT = Path(N.CHAMPION["binary"])
PROTOCOL = P / "B6V6_PROTOCOL.md"
ARMS = {
    "dots": {"OCA_W5_CG_DOTS": "1"},
    "dots-atomic": {"OCA_W5_CG_DOTS": "1", "OCA_W5_PREP_FUSE": "1"},
    "dots-camera": {"OCA_W5_CG_DOTS": "1", "OCA_W5_PREP_FUSE": "1",
                    "OCA_W5_PREP_CAMERA": "1"},
}
PAIRS = (("dots", "dots-atomic"), ("dots", "dots-camera"),
         ("dots-atomic", "dots-camera"))


def register():
    subprocess.run(["python3", str(N.FROZEN / "build.py"), "--check-only"], check=True)
    build = json.loads((P / "b6v6-build-manifest.json").read_text())
    assert N.sha(BINARY) == build["binary_sha256"]
    assert all(N.sha(path) == digest for path, digest in build["sources"].items())
    old = json.loads((P / "b6v4-registration.json").read_text())
    reg = {
        "arms": ARMS,
        "practical": old["practical"],
        "tails": old["tails"],
        "muell": old["muell"],
        "panel_repetitions": 3,
        "tail_repetitions": 10,
        "binary": str(BINARY),
        "binary_sha256": N.sha(BINARY),
        "parent_binary": str(PARENT),
        "parent_binary_sha256": N.sha(PARENT),
        "build_manifest": build,
        "protocol_sha256": N.sha(PROTOCOL),
        "cohort_rule": "Fresh three-arm rows; reverse cells and arms on odd repetitions",
        "registered_arm": "B6v4 dead-work pruning with deterministic camera-major reduced-RHS accumulation",
    }
    path = P / "b6v6-registration.json"
    if path.exists():
        assert json.loads(path.read_text()) == reg
    else:
        N.write(path, reg)
    return reg


def enrich(row):
    log = (P / row["source"] / "stdout.log").read_text()
    prep = re.search(r"W5_PREP_FUSE active .* camera_rhs=(\d+)", log)
    calls = re.search(r"W5_PREP_FUSE summary calls=(\d+) camera_rhs=(\d+)", log)
    dots = re.search(r"W5_CG_DOTS summary dot_pairs=(\d+)", log)
    profile = re.search(
        r"\[PROFILE\] assembly=(\S+)s pointfactor\+rhs=(\S+)s krylov=(\S+)s candidates=(\S+)s", log)
    row["prep_fuse_active"] = bool(prep)
    row["camera_rhs_active"] = bool(prep and prep[1] == "1")
    if calls:
        row["prep_calls"] = int(calls[1])
    if dots:
        row["batched_dot_pairs"] = int(dots[1])
    if profile:
        row["profile_seconds"] = {
            "assembly": float(profile[1]),
            "pointfactor_rhs": float(profile[2]),
            "krylov": float(profile[3]),
            "candidates": float(profile[4]),
        }
    N.write(P / row["source"] / "result.json", row)
    return row


def execute(reg, stage, cells, arms, reps, extra=None):
    rows = []
    extra = extra or {}
    for rep in range(reps):
        ordered_cells, ordered_arms = list(cells), list(arms)
        if rep % 2:
            ordered_cells.reverse()
            ordered_arms.reverse()
        for cell in ordered_cells:
            for arm in ordered_arms:
                binary = PARENT if arm == "parent-off" else BINARY
                flags = {} if arm == "parent-off" else dict(ARMS[arm], **extra)
                folder = P / "evidence" / stage / f"{cell.get('cell', cell['scene'])}-{arm}-{rep}"
                row = N.run(folder, cell, arm, rep, binary, flags, PROTOCOL,
                            reg["build_manifest"])
                rows.append(enrich(row) if arm != "parent-off" else row)
                N.write(P / f"{stage}-results.json", rows)
    return rows


def comparisons(rows):
    return {f"{b}_vs_{a}": B.summarize(rows, (a, b)) for a, b in PAIRS}


def add_profiles(result, rows):
    for comparison in result.values():
        for cell in comparison["cells"]:
            for arm in ARMS:
                group = [r for r in rows if r["cell"] == cell["cell"] and r["arm"] == arm]
                if group and all("profile_seconds" in r for r in group):
                    cell.setdefault(arm, {})["median_profile_seconds"] = {
                        phase: statistics.median(r["profile_seconds"][phase] for r in group)
                        for phase in ("assembly", "pointfactor_rhs", "krylov", "candidates")
                    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["compatibility", "panel", "profile", "muell", "tails"])
    args = parser.parse_args()
    reg = register()
    calm = next(c for c in reg["practical"] if c["cell"] == "ladybug-539-1.01")
    if args.stage == "compatibility":
        rows = execute(reg, "b6v6-compatibility", [calm], ["dots", "parent-off"], 3)
        med = {a: statistics.median(r["cost"] for r in rows if r["arm"] == a)
               for a in ("dots", "parent-off")}
        result = {"rows": len(rows), "medians": med,
                  "relative_delta": med["dots"] / med["parent-off"] - 1}
        result["passed"] = abs(result["relative_delta"]) < .0015
        N.write(P / "b6v6-compatibility-summary.json", result)
        assert result["passed"]
    elif args.stage == "panel":
        assert json.loads((P / "b6v6-compatibility-summary.json").read_text())["passed"]
        result = comparisons(execute(reg, "b6v6-panel", reg["practical"], list(ARMS), 3))
        N.write(P / "b6v6-panel-summary.json", result)
    elif args.stage == "profile":
        traf = next(c for c in reg["practical"] if c["cell"] == "trafalgar-138-1.005")
        rows = execute(reg, "b6v6-profile", [traf, reg["muell"]], list(ARMS), 3,
                       {"OCA_PROFILE": "1"})
        result = comparisons(rows)
        add_profiles(result, rows)
        N.write(P / "b6v6-profile-summary.json", result)
    elif args.stage == "muell":
        result = comparisons(execute(reg, "b6v6-muell", [reg["muell"]], list(ARMS), 3))
        N.write(P / "b6v6-muell-summary.json", result)
    else:
        result = comparisons(execute(reg, "b6v6-tails", list(reg["tails"].values()),
                                     list(ARMS), 10))
        N.write(P / "b6v6-tails-summary.json", result)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
