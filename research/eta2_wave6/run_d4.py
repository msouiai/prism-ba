#!/usr/bin/env python3
"""Run the registered deterministic soft-acceptance experiment."""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import re
import statistics
import sys

from bal_perturb import (load_bal, perturb, residual_distance, sha256,
                         state_from_bal, write_state)
from paired_sprt import PairedSprt

W5 = Path(__file__).resolve().parent.parent / "eta2_wave5"
sys.path.insert(0, str(W5))
import native_light as native

P = Path(__file__).resolve().parent
PROTOCOL = P / "D4_PROTOCOL.md"
CONTROL = P / "build" / "prism-deterministic"
ACTIVE = P / "build" / "prism-soft-accept"
FINAL = Path("/workspace/bal/final-3068.txt")
LADYBUG = Path("/tmp/prism-speed-novelty/inputs/ladybug-539.txt")
TARGET = 1744796.9841897595
CAP = 45.0
EPSILON = 1e-10
FIRST_SEED = 650000
MAX_PAIRS = 60
THRESHOLD = .1
OPTIMIZED = json.loads((W5 / "optimized_candidate.json").read_text())
native.HERE = P

EVENT = re.compile(
    r"W6_SOFT_RHO o=(\d+) alpha=(\S+) old_rho=(\S+) scaled_rho=(\S+) "
    r"current=(\S+) old_candidate=(\S+) scaled_candidate=(\S+) "
    r"prediction=(\S+) commit=(\d+)")
SUMMARY = re.compile(r"W6_SOFT_RHO summary trials=(\d+) commits=(\d+) mean_alpha=(\S+)")


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True,
                                     allow_nan=False) + "\n")


def registration():
    value = {
        "protocol_sha256": sha256(PROTOCOL),
        "runner_sha256": sha256(__file__),
        "perturbation_tool_sha256": sha256(P / "bal_perturb.py"),
        "inference_tool_sha256": sha256(P / "paired_sprt.py"),
        "native_runner_sha256": sha256(W5 / "native_light.py"),
        "build_manifest_sha256": sha256(P / "d4-build-manifest.json"),
        "input": str(FINAL),
        "input_sha256": sha256(FINAL),
        "target": TARGET,
        "native_cap_seconds": CAP,
        "max_iter": 600,
        "epsilon": EPSILON,
        "seeds": [FIRST_SEED, FIRST_SEED + MAX_PAIRS - 1],
        "arm_order": "control first on even pair, soft first on odd pair",
        "arms": {
            "control": {"binary": str(CONTROL), "sha256": sha256(CONTROL),
                        "flags": {}},
            "soft": {"binary": str(ACTIVE), "sha256": sha256(ACTIVE),
                     "flags": {"OCA_W6_SOFT_RHO": str(THRESHOLD)}},
        },
        "flags_overlay": OPTIMIZED["flags_overlay"] | {"OCA_W6_DETERMINISTIC": "1"},
        "sprt": {"q0": .5, "q1": .7, "alpha": .05, "beta": .10,
                 "max_pairs": MAX_PAIRS},
        "production_time_gate": 1.20,
    }
    target = P / "d4-registration.json"
    if target.exists():
        old = json.loads(target.read_text())
        if old != value:
            if (P / "d4-results.json").exists():
                return old
            raise RuntimeError("D4 registration changed")
    else:
        write(target, value)
    return value


def soft_events(row):
    log = P / row["source"] / "stdout.log"
    text = log.read_text()
    events = []
    for match in EVENT.finditer(text):
        values = [float(match[i]) for i in range(2, 9)]
        alpha, old_rho, scaled_rho, current, old_candidate, scaled_candidate, prediction = values
        commit = bool(int(match[9]))
        assert 0 < old_rho <= THRESHOLD * (1 + 1e-12)
        assert abs(alpha - old_rho / THRESHOLD) <= 2e-14
        expected = ((current - scaled_candidate) / prediction
                    if prediction > 0 else -1.0)
        assert abs(scaled_rho - expected) <= 1e-11 * max(1.0, abs(expected))
        assert commit == (math.isfinite(scaled_candidate) and scaled_candidate < current
                           and math.isfinite(scaled_rho) and prediction > 0)
        if commit:
            assert scaled_candidate < current
        events.append({
            "outer": int(match[1]), "alpha": alpha, "old_rho": old_rho,
            "scaled_rho": scaled_rho, "current": current,
            "old_candidate": old_candidate, "scaled_candidate": scaled_candidate,
            "prediction": prediction, "commit": commit,
        })
    summary = SUMMARY.search(text)
    if summary:
        assert int(summary[1]) == len(events)
        assert int(summary[2]) == sum(event["commit"] for event in events)
    return events


def arm_flags(active):
    flags = dict(OPTIMIZED["flags_overlay"], OCA_W6_DETERMINISTIC="1")
    if active:
        flags["OCA_W6_SOFT_RHO"] = str(THRESHOLD)
    return flags


def run_arm(folder, cell, arm, rep, active):
    binary = ACTIVE if active else CONTROL
    build = json.loads((P / ("d4-build-manifest.json" if active else
                              "deterministic-build-manifest.json")).read_text())
    row = native.run(folder, cell, arm, rep, binary, arm_flags(active),
                     PROTOCOL, build)
    result = dict(row)
    result["soft_events"] = soft_events(row)
    return result


def compatibility():
    cell = {"scene": "ladybug-539", "cell": "ladybug-539-1.01",
            "path": str(LADYBUG), "input_sha256": sha256(LADYBUG),
            "target": 165617.73918321263, "cap": 5.0}
    rows = []
    # The derived binary is run with the active flag absent here.
    base_build = json.loads((P / "deterministic-build-manifest.json").read_text())
    derived_build = json.loads((P / "d4-build-manifest.json").read_text())
    for rep in range(2):
        off = native.run(P / "evidence" / "d4-compatibility" / f"control-{rep}",
                         cell, "control", rep, CONTROL, arm_flags(False), PROTOCOL,
                         base_build)
        derived = native.run(P / "evidence" / "d4-compatibility" / f"derived-off-{rep}",
                             cell, "derived-off", rep, ACTIVE, arm_flags(False),
                             PROTOCOL, derived_build)
        assert not soft_events(off) and not soft_events(derived)
        a = list(csv.DictReader(x for x in (P / off["source"] / "curve.csv").read_text().splitlines()
                                if not x.startswith("#")))
        b = list(csv.DictReader(x for x in (P / derived["source"] / "curve.csv").read_text().splitlines()
                                if not x.startswith("#")))
        assert [(x["iter"], x["cost"]) for x in a] == [(x["iter"], x["cost"]) for x in b]
        rows.append({"rep": rep, "control": off, "derived_off": derived,
                     "same_state_sha256": off["state_sha256"] == derived["state_sha256"],
                     "same_cost_trace": True})
    assert all(row["same_state_sha256"] for row in rows)
    write(P / "d4-compatibility.json", rows)
    native.OBSERVATIONS.clear()
    return rows


def smoke():
    cell = {"scene": "final-3068", "cell": "final-3068-smoke",
            "path": str(FINAL), "input_sha256": sha256(FINAL),
            "target": TARGET, "cap": CAP}
    row = run_arm(P / "evidence" / "d4-smoke" / "soft", cell, "soft", 0, True)
    assert row["soft_events"], "registered mechanism never fired"
    assert any(event["commit"] for event in row["soft_events"]), "no soft step committed"
    write(P / "d4-smoke.json", row)
    native.OBSERVATIONS.clear()
    return row


def inference(pairs, registered):
    config = registered["sprt"]
    test = PairedSprt(q0=config["q0"], q1=config["q1"], alpha=config["alpha"],
                      beta=config["beta"], max_pairs=config["max_pairs"])
    for pair in pairs:
        if test.decision != "continue":
            break
        test.update(pair["arms"]["control"]["hit"], pair["arms"]["soft"]["hit"])
    report = test.report()
    report["interpretation"] = {
        "noninferior": "evidence for q=0.70 benefit over q=0.50",
        "harmful": "evidence against the registered q=0.70 benefit; not a harm claim",
        "inconclusive_at_cap": "registered benefit unresolved at 60 total pairs",
        "continue": "continue sampling",
    }[report["decision"]]
    return report


def execute(registered):
    path = P / "d4-results.json"
    pairs = json.loads(path.read_text()) if path.exists() else []
    problem = load_bal(FINAL)
    original = state_from_bal(problem)
    while len(pairs) < MAX_PAIRS and inference(pairs, registered)["decision"] == "continue":
        index = len(pairs)
        seed = FIRST_SEED + index
        cameras, points, scales = perturb(problem, seed, EPSILON)
        input_path = Path(f"/dev/shm/w6-d4-final-{seed}.txt")
        write_state(problem, input_path, cameras, points)
        input_hash = sha256(input_path)
        initial_distance = residual_distance(problem, original,
                                             state_from_bal(problem, cameras, points))
        cell = {"scene": "final-3068", "cell": f"final-3068-pair-{index:03d}",
                "path": str(input_path), "input_sha256": input_hash,
                "target": TARGET, "cap": CAP}
        order = ["control", "soft"] if index % 2 == 0 else ["soft", "control"]
        rows = {}
        try:
            for arm in order:
                rows[arm] = run_arm(
                    P / "evidence" / "d4-soft" / f"pair-{index:03d}" / arm,
                    cell, arm, index, arm == "soft")
        finally:
            input_path.unlink(missing_ok=True)
            native.OBSERVATIONS.clear()
        pair = {"pair": index, "seed": seed, "epsilon": EPSILON,
                "field_scales": scales, "input_sha256": input_hash,
                "initial_residual_distance": initial_distance,
                "arm_order": order, "arms": rows}
        pairs.append(pair)
        write(path, pairs)
        current = inference(pairs, registered)
        print("PAIR", index, "control", rows["control"]["hit"],
              "soft", rows["soft"]["hit"], "events", len(rows["soft"]["soft_events"]),
              "commits", sum(x["commit"] for x in rows["soft"]["soft_events"]),
              "sprt", current["decision"], "llr", current["log_likelihood_ratio"],
              flush=True)
    return pairs


def summarize(pairs, registered):
    test = inference(pairs, registered)
    both = [pair for pair in pairs if pair["arms"]["control"]["hit"]
            and pair["arms"]["soft"]["hit"]]
    ratios = [pair["arms"]["soft"]["target_seconds"] /
              pair["arms"]["control"]["target_seconds"] for pair in both]
    events = [event for pair in pairs for event in pair["arms"]["soft"]["soft_events"]]
    summary = {
        "pairs": len(pairs),
        "hits": {arm: sum(pair["arms"][arm]["hit"] for pair in pairs)
                 for arm in ("control", "soft")},
        "sprt": test,
        "outcomes": {
            "double_hits": len(both),
            "control_only": sum(pair["arms"]["control"]["hit"] and
                                not pair["arms"]["soft"]["hit"] for pair in pairs),
            "soft_only": sum(pair["arms"]["soft"]["hit"] and
                             not pair["arms"]["control"]["hit"] for pair in pairs),
            "double_misses": sum(not pair["arms"]["soft"]["hit"] and
                                 not pair["arms"]["control"]["hit"] for pair in pairs),
        },
        "soft": {"trials": len(events),
                 "commits": sum(event["commit"] for event in events),
                 "median_alpha": statistics.median(event["alpha"] for event in events)
                 if events else None},
        "double_hit_soft_over_control_target_time": {
            "median": statistics.median(ratios) if ratios else None,
            "range": [min(ratios), max(ratios)] if ratios else None,
        },
        "median_endpoint_cost": {
            arm: statistics.median(pair["arms"][arm]["cost"] for pair in pairs)
            for arm in ("control", "soft")},
        "median_work": {arm: {
            key: statistics.median(pair["arms"][arm][key] for pair in pairs)
            for key in ("native_seconds", "outers", "rejects", "matvecs")}
            for arm in ("control", "soft")},
    }
    ratio = summary["double_hit_soft_over_control_target_time"]["median"]
    summary["production_gate_passed"] = bool(
        test["decision"] == "noninferior" and summary["soft"]["commits"] > 0
        and ratio is not None and ratio <= registered["production_time_gate"])
    summary["next_stage"] = ("run Venice and practical panel" if summary["production_gate_passed"]
                             else "stop D4 without tuning")
    write(P / "d4-summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("register", "compatibility", "smoke", "run", "summarize"))
    args = parser.parse_args()
    registered = registration()
    if args.stage == "register":
        print(json.dumps(registered, indent=2)); return
    if args.stage == "compatibility":
        print(json.dumps(compatibility(), indent=2)); return
    if args.stage == "smoke":
        print(json.dumps(smoke(), indent=2)); return
    pairs = execute(registered) if args.stage == "run" else json.loads((P / "d4-results.json").read_text())
    print(json.dumps(summarize(pairs, registered), indent=2))


if __name__ == "__main__":
    main()
