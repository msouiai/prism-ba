#!/usr/bin/env python3
"""Run registered occupancy-gated deterministic preparation measurements."""
from pathlib import Path
import argparse
import json
import re
import statistics
import subprocess

import native_light as N
import run_b6 as B

P = Path(__file__).resolve().parent
BINARY = P / "build" / "prism-b6v7"
PARENT = Path(N.CHAMPION["binary"])
PROTOCOL = P / "B6V7_PROTOCOL.md"
ARMS = {
    "dots": {"OCA_W5_CG_DOTS": "1"},
    "gated": {"OCA_W5_CG_DOTS": "1", "OCA_W5_PREP_FUSE": "1",
              "OCA_W5_PREP_CAMERA": "1", "OCA_W5_PREP_MIN_CAMS": "128"},
}
PAIR = ("dots", "gated")


def register():
    subprocess.run(["python3", str(N.FROZEN / "build.py"), "--check-only"], check=True)
    build = json.loads((P / "b6v7-build-manifest.json").read_text())
    assert N.sha(BINARY) == build["binary_sha256"]
    assert all(N.sha(path) == digest for path, digest in build["sources"].items())
    old = json.loads((P / "b6v6-registration.json").read_text())
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
        "gpu": {"name": "NVIDIA RTX 2000 Ada Generation", "sm_count": 22},
        "cohort_rule": "Fresh paired rows; reverse cells and arms on odd repetitions",
        "pooling_rule": "Pool B6v6 Final3068 dots/dots-camera N=10 with fresh dots/gated N=10; paths are arithmetic-identical for ncam=3068",
        "registered_arm": "B6v6 camera-owned preparation iff ncam >= 128, otherwise dots-only",
    }
    path = P / "b6v7-registration.json"
    if path.exists():
        assert json.loads(path.read_text()) == reg
    else:
        N.write(path, reg)
    return reg


def enrich(row):
    log = (P / row["source"] / "stdout.log").read_text()
    active = re.search(r"W5_PREP_FUSE active .* camera_rhs=(\d+) min_cams=(\d+)", log)
    inactive = re.search(r"W5_PREP_FUSE gated_off ncam=(\d+) min_cams=(\d+)", log)
    dots = re.search(r"W5_CG_DOTS summary dot_pairs=(\d+)", log)
    row["prep_active"] = bool(active)
    row["prep_gated_off"] = bool(inactive)
    if active:
        row["min_cams"] = int(active[2])
    if inactive:
        row["ncam"] = int(inactive[1])
        row["min_cams"] = int(inactive[2])
    if dots:
        row["batched_dot_pairs"] = int(dots[1])
    N.write(P / row["source"] / "result.json", row)
    return row


def execute(reg, stage, cells, arms, reps):
    rows = []
    for rep in range(reps):
        ordered_cells, ordered_arms = list(cells), list(arms)
        if rep % 2:
            ordered_cells.reverse()
            ordered_arms.reverse()
        for cell in ordered_cells:
            for arm in ordered_arms:
                binary = PARENT if arm == "parent-off" else BINARY
                flags = {} if arm == "parent-off" else ARMS[arm]
                folder = P / "evidence" / stage / f"{cell.get('cell', cell['scene'])}-{arm}-{rep}"
                row = N.run(folder, cell, arm, rep, binary, flags, PROTOCOL,
                            reg["build_manifest"])
                rows.append(enrich(row) if arm != "parent-off" else row)
                N.write(P / f"{stage}-results.json", rows)
    return rows


def pooled_final(fresh):
    old = json.loads((P / "b6v6-tails-results.json").read_text())
    rows = []
    for row in old:
        if row["cell"] == "final-3068" and row["arm"] in ("dots", "dots-camera"):
            copy = dict(row)
            copy["arm"] = "gated" if row["arm"] == "dots-camera" else "dots"
            copy["pool_source"] = "b6v6"
            rows.append(copy)
    for row in fresh:
        if row["cell"] == "final-3068":
            copy = dict(row)
            copy["pool_source"] = "b6v7"
            rows.append(copy)
    assert sum(r["arm"] == "dots" for r in rows) == 20
    assert sum(r["arm"] == "gated" for r in rows) == 20
    result = B.summarize(rows, PAIR)
    N.write(P / "b6v7-final-pooled-results.json", rows)
    N.write(P / "b6v7-final-pooled-summary.json", result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["compatibility", "panel", "muell", "tails"])
    args = parser.parse_args()
    reg = register()
    calm = next(c for c in reg["practical"] if c["cell"] == "ladybug-539-1.01")
    if args.stage == "compatibility":
        rows = execute(reg, "b6v7-compatibility", [calm], ["dots", "parent-off"], 3)
        med = {a: statistics.median(r["cost"] for r in rows if r["arm"] == a)
               for a in ("dots", "parent-off")}
        result = {"rows": len(rows), "medians": med,
                  "relative_delta": med["dots"] / med["parent-off"] - 1}
        result["passed"] = abs(result["relative_delta"]) < .0015
        N.write(P / "b6v7-compatibility-summary.json", result)
        assert result["passed"]
    elif args.stage == "panel":
        assert json.loads((P / "b6v7-compatibility-summary.json").read_text())["passed"]
        result = B.summarize(execute(reg, "b6v7-panel", reg["practical"], list(ARMS), 3), PAIR)
        N.write(P / "b6v7-panel-summary.json", result)
    elif args.stage == "muell":
        result = B.summarize(execute(reg, "b6v7-muell", [reg["muell"]], list(ARMS), 3), PAIR)
        N.write(P / "b6v7-muell-summary.json", result)
    else:
        rows = execute(reg, "b6v7-tails", list(reg["tails"].values()), list(ARMS), 10)
        result = {"fresh": B.summarize(rows, PAIR), "final_pooled": pooled_final(rows)}
        N.write(P / "b6v7-tails-summary.json", result)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
