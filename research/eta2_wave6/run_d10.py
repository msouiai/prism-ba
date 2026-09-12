#!/usr/bin/env python3
"""Run the registered D10 track-damage diagnostic and paired filter screen."""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import re
import statistics
import sys

from bal_perturb import load_bal, perturb, sha256, write_state

P = Path(__file__).resolve().parent
W5 = P.parent / "eta2_wave5"
sys.path.insert(0, str(W5))
import native_light as native

PROTOCOL = P / "D10_TRACK_DAMAGE_FILTER_PROTOCOL.md"
CONTROL = P / "build" / "prism-deterministic"
BINARY = P / "build" / "prism-track-damage"
FINAL = Path("/workspace/bal/final-3068.txt")
VENICE = Path("/workspace/bal/venice-52.txt")
TARGET = 1744796.9841897595
EPSILON = 1e-10
OPT = json.loads((W5 / "optimized_candidate.json").read_text())
W5REG = json.loads((W5 / "b6v7-registration.json").read_text())
native.HERE = P

EVENT = re.compile(
    r"W6_TRACK_DAMAGE o=(\d+) accepts=(\d+) rho=(\S+) gain=(\S+) "
    r"max=(\S+) positive=(\S+) q=(\S+) burden=(\S+) point=(-?\d+) "
    r"old=(\S+) new=(\S+) increased=(\d+) concentrated=(\d+) filtered=(\d+)")
SUMMARY = re.compile(
    r"W6_TRACK_DAMAGE summary evals=(\d+) concentrated=(\d+) filtered=(\d+) seconds=(\S+)")


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True,
                                     allow_nan=False) + "\n")


def registration():
    manifest = json.loads((P / "d10-build-manifest.json").read_text())
    value = {
        "protocol_sha256": sha256(PROTOCOL),
        "runner_sha256": sha256(__file__),
        "build_manifest_sha256": sha256(P / "d10-build-manifest.json"),
        "binary": str(BINARY), "binary_sha256": sha256(BINARY),
        "control_binary": str(CONTROL), "control_binary_sha256": sha256(CONTROL),
        "manifest": manifest,
        "thresholds": {"concentration": .05, "burden": .05,
                       "opening_accepted_states": 10},
        "diagnostic": {"final_seeds": [660000, 660009], "epsilon": EPSILON,
                       "final_repetitions": 10, "venice_repetitions": 3,
                       "ladybug_repetitions": 3},
        "paired": {"final_seeds": [670000, 670019], "epsilon": EPSILON,
                   "pairs": 20, "target": TARGET, "cap": 45.0,
                   "arm_order": "control first on even pair, filter first on odd pair"},
        "flags_overlay": OPT["flags_overlay"] | {"OCA_W6_DETERMINISTIC": "1"},
    }
    target = P / "d10-registration.json"
    if target.exists():
        old = json.loads(target.read_text())
        if old != value:
            if (P / "d10-diagnostic-results.json").exists():
                return old
            raise RuntimeError("D10 registration changed")
    else:
        write(target, value)
    return value


def flags(mode=None):
    out = dict(OPT["flags_overlay"], OCA_W6_DETERMINISTIC="1")
    if mode is not None:
        out["OCA_W6_TRACK_DAMAGE"] = str(mode)
    return out


def parse_events(row):
    text = (P / row["source"] / "stdout.log").read_text()
    values = []
    for match in EVENT.finditer(text):
        event = {
            "outer": int(match[1]), "accepts_before": int(match[2]),
            "rho": float(match[3]), "gain": float(match[4]),
            "max_increase": float(match[5]), "positive_sum": float(match[6]),
            "concentration": float(match[7]), "burden": float(match[8]),
            "point": int(match[9]), "old_track": float(match[10]),
            "new_track": float(match[11]), "increased_tracks": int(match[12]),
            "concentrated": bool(int(match[13])), "filtered": bool(int(match[14])),
        }
        assert event["concentrated"] == (
            event["concentration"] > .05 and event["burden"] > .05)
        values.append(event)
    summary = SUMMARY.search(text)
    if summary:
        assert int(summary[1]) == len(values)
        assert int(summary[2]) == sum(x["concentrated"] for x in values)
        assert int(summary[3]) == sum(x["filtered"] for x in values)
        seconds = float(summary[4])
    else:
        seconds = None
    return values, seconds


def run(folder, cell, arm, rep, mode):
    row = native.run(folder, cell, arm, rep, BINARY, flags(mode), PROTOCOL,
                     json.loads((P / "d10-build-manifest.json").read_text()))
    row["damage_events"], row["damage_seconds"] = parse_events(row)
    write(P / row["source"] / "result.json", row)
    return row


def compatibility():
    cell = next(x for x in W5REG["practical"] if x["cell"] == "ladybug-539-1.01")
    rows = []
    parent_manifest = json.loads((P / "deterministic-build-manifest.json").read_text())
    child_manifest = json.loads((P / "d10-build-manifest.json").read_text())
    for rep in range(2):
        left = native.run(P / "evidence/d10-compatibility" / f"parent-{rep}", cell,
                          "parent", rep, CONTROL, flags(), PROTOCOL, parent_manifest)
        right = native.run(P / "evidence/d10-compatibility" / f"derived-off-{rep}", cell,
                           "derived-off", rep, BINARY, flags(), PROTOCOL, child_manifest)
        a = list(csv.DictReader(x for x in (P / left["source"] / "curve.csv").read_text().splitlines()
                                if not x.startswith("#")))
        b = list(csv.DictReader(x for x in (P / right["source"] / "curve.csv").read_text().splitlines()
                                if not x.startswith("#")))
        same_trace = [(x["iter"], x["cost"]) for x in a] == [(x["iter"], x["cost"]) for x in b]
        rows.append({"rep": rep, "same_trace": same_trace,
                     "same_state": left["state_sha256"] == right["state_sha256"],
                     "parent": left, "derived_off": right})
    result = {"rows": rows, "passed": all(x["same_trace"] and x["same_state"] for x in rows)}
    write(P / "d10-compatibility.json", result)
    native.OBSERVATIONS.clear()
    assert result["passed"]
    return result


def final_cell(path, index):
    return {"scene": "final-3068", "cell": f"final-3068-d10-{index:03d}",
            "path": str(path), "input_sha256": sha256(path),
            "target": TARGET, "cap": 45.0}


def perturbed_run(problem, seed, index, arm, mode, folder):
    cameras, points, _ = perturb(problem, seed, EPSILON)
    path = Path(f"/dev/shm/w6-d10-final-{seed}.txt")
    write_state(problem, path, cameras, points)
    try:
        return run(folder, final_cell(path, index), arm, index, mode)
    finally:
        path.unlink(missing_ok=True)
        native.OBSERVATIONS.clear()


def diagnostic():
    rows = []
    problem = load_bal(FINAL)
    for index, seed in enumerate(range(660000, 660010)):
        rows.append(perturbed_run(problem, seed, index, "log", 1,
                    P / "evidence/d10-diagnostic" / f"final-{index:02d}"))
        write(P / "d10-diagnostic-results.json", rows)
    simple = [
        (next(x for x in W5REG["practical"] if x["cell"] == "ladybug-539-1.01"), "ladybug"),
        (W5REG["tails"]["venice-52"], "venice"),
    ]
    for cell, label in simple:
        for rep in range(3):
            rows.append(run(P / "evidence/d10-diagnostic" / f"{label}-{rep}",
                            cell, "log", rep, 1))
            write(P / "d10-diagnostic-results.json", rows)
    return summarize_diagnostic(rows)


def summarize_diagnostic(rows):
    def early(row):
        return [e for e in row["damage_events"] if e["accepts_before"] < 10]
    final = [r for r in rows if r["scene"] == "final-3068"]
    lady = [r for r in rows if r["scene"] == "ladybug-539"]
    venice = [r for r in rows if r["scene"] == "venice-52"]
    hit = [r for r in final if r["hit"]]; miss = [r for r in final if not r["hit"]]
    run_rate = lambda group: (sum(any(e["concentrated"] for e in early(r)) for r in group)/len(group)
                              if group else None)
    all_lady = [e for r in lady for e in early(r)]
    result = {
        "rows": len(rows), "final_hits": sum(r["hit"] for r in final),
        "final_runs": len(final),
        "final_runs_with_early_event": sum(any(e["concentrated"] for e in early(r)) for r in final),
        "event_run_rate_by_endpoint": {"hit": run_rate(hit), "miss": run_rate(miss)},
        "ladybug_early_event_fraction": (sum(e["concentrated"] for e in all_lady)/len(all_lady)
                                           if all_lady else None),
        "venice_runs_with_early_event": sum(any(e["concentrated"] for e in early(r)) for r in venice),
        "diagnostic_damage_seconds_median": statistics.median(r["damage_seconds"] for r in rows),
    }
    rates = result["event_run_rate_by_endpoint"]
    result["gate_passed"] = bool(
        result["final_runs_with_early_event"] >= 1 and all_lady and
        result["ladybug_early_event_fraction"] <= .05 and hit and miss and
        rates["miss"] > rates["hit"])
    result["next_stage"] = "paired active screen" if result["gate_passed"] else "stop without threshold tuning"
    write(P / "d10-diagnostic-summary.json", result)
    return result


def paired():
    diagnostic_summary = json.loads((P / "d10-diagnostic-summary.json").read_text())
    assert diagnostic_summary["gate_passed"], diagnostic_summary
    path = P / "d10-paired-results.json"
    pairs = json.loads(path.read_text()) if path.exists() else []
    problem = load_bal(FINAL)
    while len(pairs) < 20:
        index = len(pairs); seed = 670000 + index
        cameras, points, _ = perturb(problem, seed, EPSILON)
        input_path = Path(f"/dev/shm/w6-d10-pair-{seed}.txt")
        write_state(problem, input_path, cameras, points)
        cell = final_cell(input_path, index)
        order = ["control", "filter"] if index % 2 == 0 else ["filter", "control"]
        arms = {}
        try:
            for arm in order:
                arms[arm] = run(P / "evidence/d10-paired" / f"pair-{index:02d}" / arm,
                                cell, arm, index, 1 if arm == "control" else 2)
        finally:
            input_path.unlink(missing_ok=True); native.OBSERVATIONS.clear()
        pairs.append({"pair": index, "seed": seed, "order": order, "arms": arms})
        write(path, pairs)
        print("PAIR", index, "control", arms["control"]["hit"], "filter", arms["filter"]["hit"],
              "filtered", sum(e["filtered"] for e in arms["filter"]["damage_events"]), flush=True)
    return summarize_paired(pairs)


def summarize_paired(pairs):
    double = [p for p in pairs if p["arms"]["control"]["hit"] and p["arms"]["filter"]["hit"]]
    ratios = [p["arms"]["filter"]["target_seconds"] / p["arms"]["control"]["target_seconds"]
              for p in double]
    co = sum(p["arms"]["control"]["hit"] and not p["arms"]["filter"]["hit"] for p in pairs)
    fo = sum(p["arms"]["filter"]["hit"] and not p["arms"]["control"]["hit"] for p in pairs)
    result = {
        "pairs": len(pairs),
        "hits": {a: sum(p["arms"][a]["hit"] for p in pairs) for a in ("control", "filter")},
        "outcomes": {"double_hit": len(double), "control_only": co, "filter_only": fo,
                     "double_miss": sum(not p["arms"]["control"]["hit"] and
                                        not p["arms"]["filter"]["hit"] for p in pairs)},
        "filtered_steps": sum(e["filtered"] for p in pairs for e in p["arms"]["filter"]["damage_events"]),
        "double_hit_target_time_ratio": {"median": statistics.median(ratios) if ratios else None,
                                          "range": [min(ratios), max(ratios)] if ratios else None},
        "median_endpoint": {a: statistics.median(p["arms"][a]["cost"] for p in pairs)
                            for a in ("control", "filter")},
    }
    result["promotion_gate_passed"] = bool(
        fo - co >= 3 and result["filtered_steps"] > 0 and ratios and statistics.median(ratios) <= 1.2)
    result["next_stage"] = "Venice N10 and practical panel" if result["promotion_gate_passed"] else "stop without threshold sweep"
    write(P / "d10-paired-summary.json", result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("register", "compatibility", "diagnostic", "paired", "summarize"))
    args = parser.parse_args(); reg = registration()
    if args.stage == "register": result = reg
    elif args.stage == "compatibility": result = compatibility()
    elif args.stage == "diagnostic": result = diagnostic()
    elif args.stage == "paired": result = paired()
    else:
        rows = json.loads((P / "d10-diagnostic-results.json").read_text())
        result = summarize_diagnostic(rows)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
