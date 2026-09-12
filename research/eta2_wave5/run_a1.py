#!/usr/bin/env python3
"""Registered native A1 compatibility, tail, and practical-panel cohorts."""
from pathlib import Path
import argparse, json, math, re, statistics, subprocess

import native_light as N

P = Path(__file__).resolve().parent
BINARY = P / "build" / "prism-a1"
PARENT = Path(N.CHAMPION["binary"])
ARMS = {"off": {}, "targeted": {"OCA_W5_TARGET_TRIANGULATION": "1"}}


def register():
    subprocess.run(["python3", str(N.FROZEN / "build.py"), "--check-only"], check=True)
    build = json.loads((P / "a1-build-manifest.json").read_text())
    assert N.sha(BINARY) == build["binary_sha256"]
    assert N.sha(PARENT) == N.CHAMPION["binary_sha256"]
    assert all(N.sha(path) == digest for path, digest in build["sources"].items())
    old = json.loads((P.parent / "eta2_wave4" / "aside-registration.json").read_text())
    reg = {
        "arms": ARMS,
        "cells": {k: old["cells"][k] for k in ("venice-52", "final-3068")},
        "practical": old["practical"], "tail_repetitions": 5, "panel_repetitions": 3,
        "binary": str(BINARY), "binary_sha256": N.sha(BINARY),
        "parent_binary": str(PARENT), "parent_binary_sha256": N.sha(PARENT),
        "build_manifest": build, "protocol_sha256": N.sha(P / "A1_REPLAY_PROTOCOL.md"),
        "cohort_rule": "Fresh paired rows; alternate arm order and reverse cell order on odd repetitions",
    }
    path = P / "a1-registration.json"
    if path.exists(): assert json.loads(path.read_text()) == reg
    else: N.write(path, reg)
    return reg


def enrich(row):
    log = (P / row["source"] / "stdout.log").read_text()
    match = re.search(r"W5_A1 summary calls=(\d+) flagged=(\d+) eligible=(\d+) wins=(\d+) "
                      r"margin=(\d+) algebra=(\d+) track_decrease=(\S+) seconds=(\S+)", log)
    row["a1"] = ({"calls": int(match[1]), "flagged": int(match[2]),
                  "eligible": int(match[3]), "wins": int(match[4]),
                  "margin_rejects": int(match[5]), "algebra_failures": int(match[6]),
                  "track_decrease": float(match[7]), "seconds": float(match[8])}
                 if match else None)
    N.write(P / row["source"] / "result.json", row)
    return row


def execute(reg, stage, cells, arms, repetitions):
    rows = []
    for rep in range(repetitions):
        ordered_cells = list(cells); ordered_arms = list(arms)
        if rep % 2: ordered_cells.reverse(); ordered_arms.reverse()
        for cell in ordered_cells:
            for arm in ordered_arms:
                binary = PARENT if arm == "parent-off" else BINARY
                flags = {} if arm == "parent-off" else ARMS[arm]
                folder = P / "evidence" / stage / f"{cell.get('cell',cell['scene'])}-{arm}-{rep}"
                row = enrich(N.run(folder, cell, arm, rep, binary, flags,
                                   P / "A1_REPLAY_PROTOCOL.md", reg["build_manifest"]))
                rows.append(row); N.write(P / f"{stage}-results.json", rows)
    return rows


def group(rows, scene, arm):
    values = [r for r in rows if r["scene"] == scene and r["arm"] == arm]
    times = [r["target_seconds"] for r in values if r["hit"]]
    return {"scene": scene, "arm": arm, "n": len(values),
            "hits": sum(r["hit"] for r in values),
            "median_endpoint": statistics.median(r["cost"] for r in values),
            "endpoint_range": [min(r["cost"] for r in values), max(r["cost"] for r in values)],
            "conditional_median_target_seconds": statistics.median(times) if times else None,
            "target_seconds_range": [min(times), max(times)] if times else None,
            "median_native_seconds": statistics.median(r["native_seconds"] for r in values),
            "median_rejects": statistics.median(r["rejects"] for r in values),
            "median_matvecs": statistics.median(r["matvecs"] for r in values),
            "median_a1_seconds": (statistics.median(r["a1"]["seconds"] for r in values)
                                  if arm == "targeted" else None),
            "total_a1_eligible": sum((r["a1"] or {}).get("eligible", 0) for r in values),
            "total_a1_wins": sum((r["a1"] or {}).get("wins", 0) for r in values)}


def summarize_tails(rows):
    groups = [group(rows, scene, arm) for scene in ("venice-52", "final-3068") for arm in ARMS]
    by = {(g["scene"], g["arm"]): g for g in groups}
    tail_gain = any(by[(s,"targeted")]["hits"] > by[(s,"off")]["hits"]
                    for s in ("venice-52", "final-3068"))
    no_hit_loss = all(by[(s,"targeted")]["hits"] >= by[(s,"off")]["hits"]
                      for s in ("venice-52", "final-3068"))
    result = {"rows": len(rows), "groups": groups,
              "proceed_to_panel": tail_gain and no_hit_loss,
              "gate": "At least one strict tail hit-rate gain and no hit-rate loss"}
    N.write(P / "a1-tails-summary.json", result); return result


def summarize_panel(rows):
    cells=[];ratios=[];slower=faster=0
    for cid in sorted({r["cell"] for r in rows}):
        record={"cell":cid}
        for arm in ARMS:
            vals=[r["target_seconds"] for r in rows if r["cell"]==cid and r["arm"]==arm]
            assert all(v is not None for v in vals),(cid,arm)
            record[arm]={"median":statistics.median(vals),"range":[min(vals),max(vals)]}
        ratio=record["targeted"]["median"]/record["off"]["median"]
        ratios.append(ratio);record["ratio"]=ratio
        faster+=record["targeted"]["range"][1]<record["off"]["range"][0]
        slower+=record["targeted"]["range"][0]>record["off"]["range"][1]
        cells.append(record)
    result={"rows":len(rows),"geometric_mean_ratio":math.exp(sum(map(math.log,ratios))/len(ratios)),
            "faster_disjoint_cells":faster,"slower_disjoint_cells":slower,"cells":cells}
    N.write(P/"a1-practical-summary.json",result);return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument("stage",choices=["compatibility","smoke","tails","practical"])
    args=parser.parse_args();reg=register()
    calm=next(x for x in reg["practical"] if x["cell"]=="ladybug-539-1.01")
    if args.stage=="compatibility":
        rows=execute(reg,"a1-compatibility",[calm],["off","parent-off"],3)
        med={a:statistics.median(r["cost"] for r in rows if r["arm"]==a) for a in ("off","parent-off")}
        rel=med["off"]/med["parent-off"]-1
        result={"rows":len(rows),"medians":med,"relative_delta":rel,"passed":abs(rel)<.0015}
        N.write(P/"a1-compatibility-summary.json",result);assert result["passed"],result
    elif args.stage=="smoke":
        assert json.loads((P/"a1-compatibility-summary.json").read_text())["passed"]
        rows=execute(reg,"a1-smoke",[calm],["targeted"],1)
        result={"passed":rows[0]["a1"] is not None,"a1":rows[0]["a1"]}
        N.write(P/"a1-smoke-summary.json",result);assert result["passed"],result
    elif args.stage=="tails":
        assert json.loads((P/"a1-smoke-summary.json").read_text())["passed"]
        result=summarize_tails(execute(reg,"a1-tails",list(reg["cells"].values()),list(ARMS),5))
    else:
        tails=json.loads((P/"a1-tails-summary.json").read_text())
        if not tails["proceed_to_panel"]:
            result={"skipped":True,"reason":"Preregistered tail gate failed"};N.write(P/"a1-practical-summary.json",result)
        else: result=summarize_panel(execute(reg,"a1-practical",reg["practical"],list(ARMS),3))
    print(json.dumps(result,indent=2),flush=True)


if __name__ == "__main__": main()
