#!/usr/bin/env python3
"""Paired sequential Final3068 precision experiment."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import statistics

from bal_perturb import (load_bal, perturb, residual_distance, sha256,
                         state_from_bal, write_state)
from paired_sprt import PairedSprt

import sys
W5 = Path(__file__).resolve().parent.parent / "eta2_wave5"
sys.path.insert(0, str(W5))
import native_light as native


P = Path(__file__).resolve().parent
FROZEN = P.parent / "eta2_champion"
PROTOCOL = P / "D3_PROTOCOL.md"
FP32 = P / "build" / "prism-deterministic"
FP64 = P / "build" / "prism-deterministic-fp64-fragments"
INPUT = Path("/workspace/bal/final-3068.txt")
TARGET = 1744796.9841897595
CAP = 45.0
EPSILON = 1e-10
FIRST_SEED = 640000
MAX_PAIRS = 60
OPTIMIZED = json.loads((W5 / "optimized_candidate.json").read_text())
native.HERE = P


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def registration():
    value = {
        "protocol_sha256": sha256(PROTOCOL),
        "tool_sha256": sha256(__file__),
        "perturbation_tool_sha256": sha256(P / "bal_perturb.py"),
        "inference_tool_sha256": sha256(P / "paired_sprt.py"),
        "native_runner_sha256": sha256(W5 / "native_light.py"),
        "input": str(INPUT),
        "input_sha256": sha256(INPUT),
        "target": TARGET,
        "native_cap_seconds": CAP,
        "max_iter": 600,
        "epsilon": EPSILON,
        "seeds": [FIRST_SEED, FIRST_SEED + MAX_PAIRS - 1],
        "arm_order": "fp32 first on even pair, fp64 first on odd pair",
        "arms": {
            "fp32": {"binary": str(FP32), "sha256": sha256(FP32)},
            "fp64": {"binary": str(FP64), "sha256": sha256(FP64)},
        },
        "flags_overlay": OPTIMIZED["flags_overlay"] | {"OCA_W6_DETERMINISTIC": "1"},
        "sprt": {"q0": .5, "q1": .7, "alpha": .05, "beta": .10,
                 "max_pairs": MAX_PAIRS},
        "production_time_gate": 1.25,
    }
    target = P / "d3-registration.json"
    if target.exists():
        old = json.loads(target.read_text())
        if old != value:
            if (P / "d3-results.json").exists():
                return old
            raise RuntimeError("D3 registration changed")
    else:
        write(target, value)
    return value


def inference(pairs, registered):
    config = registered["sprt"]
    test = PairedSprt(q0=config["q0"], q1=config["q1"], alpha=config["alpha"],
                      beta=config["beta"], max_pairs=config["max_pairs"])
    for pair in pairs:
        if test.decision != "continue":
            break
        test.update(pair["arms"]["fp32"]["hit"], pair["arms"]["fp64"]["hit"])
    report = test.report()
    report["interpretation"] = {
        "noninferior": "evidence for q=0.70 benefit over q=0.50",
        "harmful": "evidence against the registered q=0.70 benefit; not a harm claim",
        "inconclusive_at_cap": "registered benefit unresolved at 60 total pairs",
        "continue": "continue sampling",
    }[report["decision"]]
    return report


def run_arm(folder, cell, arm, pair_index, binary, build_manifest):
    flags = dict(OPTIMIZED["flags_overlay"], OCA_W6_DETERMINISTIC="1")
    return native.run(folder, cell, arm, pair_index, binary, flags, PROTOCOL, build_manifest)


def execute(registered):
    pairs_path = P / "d3-results.json"
    pairs = json.loads(pairs_path.read_text()) if pairs_path.exists() else []
    problem = load_bal(INPUT)
    original = state_from_bal(problem)
    builds = {
        "fp32": json.loads((P / "deterministic-build-manifest.json").read_text()),
        "fp64": json.loads((P / "d2c-build-manifest.json").read_text()),
    }
    while len(pairs) < MAX_PAIRS and inference(pairs, registered)["decision"] == "continue":
        index = len(pairs)
        seed = FIRST_SEED + index
        cameras, points, scales = perturb(problem, seed, EPSILON)
        input_path = Path(f"/dev/shm/w6-d3-final-{seed}.txt")
        write_state(problem, input_path, cameras, points)
        input_hash = sha256(input_path)
        initial_distance = residual_distance(
            problem, original, state_from_bal(problem, cameras, points))
        cell = {
            "scene": "final-3068",
            "cell": f"final-3068-pair-{index:03d}",
            "path": str(input_path),
            "input_sha256": input_hash,
            "target": TARGET,
            "cap": CAP,
        }
        order = ["fp32", "fp64"] if index % 2 == 0 else ["fp64", "fp32"]
        rows = {}
        try:
            for arm in order:
                binary = FP32 if arm == "fp32" else FP64
                rows[arm] = run_arm(
                    P / "evidence" / "d3-precision" / f"pair-{index:03d}" / arm,
                    cell, arm, index, binary, builds[arm])
        finally:
            input_path.unlink(missing_ok=True)
        pair = {
            "pair": index,
            "seed": seed,
            "epsilon": EPSILON,
            "field_scales": scales,
            "input_sha256": input_hash,
            "initial_residual_distance": initial_distance,
            "arm_order": order,
            "arms": rows,
        }
        pairs.append(pair)
        write(pairs_path, pairs)
        current = inference(pairs, registered)
        print("PAIR", index, "fp32", rows["fp32"]["hit"], "fp64", rows["fp64"]["hit"],
              "sprt", current["decision"], "llr", current["log_likelihood_ratio"], flush=True)
    return pairs


def summarize(pairs, registered):
    test = inference(pairs, registered)
    double_hits = [pair for pair in pairs
                   if pair["arms"]["fp32"]["hit"] and pair["arms"]["fp64"]["hit"]]
    ratios = [pair["arms"]["fp64"]["target_seconds"] /
              pair["arms"]["fp32"]["target_seconds"] for pair in double_hits]
    all_wall_ratios = [pair["arms"]["fp64"]["native_seconds"] /
                       pair["arms"]["fp32"]["native_seconds"] for pair in pairs]
    summary = {
        "schema": 1,
        "pairs": len(pairs),
        "hits": {arm: sum(pair["arms"][arm]["hit"] for pair in pairs)
                 for arm in ("fp32", "fp64")},
        "sprt": test,
        "double_hit_pairs": len(double_hits),
        "double_hit_fp64_over_fp32_target_time": {
            "median": statistics.median(ratios) if ratios else None,
            "range": [min(ratios), max(ratios)] if ratios else None,
        },
        "all_pair_fp64_over_fp32_native_wall": {
            "median": statistics.median(all_wall_ratios) if all_wall_ratios else None,
            "range": [min(all_wall_ratios), max(all_wall_ratios)] if all_wall_ratios else None,
        },
        "median_endpoint_cost": {
            arm: statistics.median(pair["arms"][arm]["cost"] for pair in pairs)
            for arm in ("fp32", "fp64")
        },
        "median_work": {
            arm: {
                key: statistics.median(pair["arms"][arm][key] for pair in pairs)
                for key in ("outers", "rejects", "matvecs")
            } for arm in ("fp32", "fp64")
        },
    }
    time_ratio = summary["double_hit_fp64_over_fp32_target_time"]["median"]
    summary["production_gate_passed"] = bool(
        test["decision"] == "noninferior" and time_ratio is not None
        and time_ratio <= registered["production_time_gate"]
    )
    summary["decision"] = (
        "FP64 precision candidate passes" if summary["production_gate_passed"] else
        "No production precision candidate from D3"
    )
    write(P / "d3-summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("register", "run", "summarize"))
    args = parser.parse_args()
    registered = registration()
    if args.stage == "register":
        print(json.dumps(registered, indent=2)); return
    pairs = execute(registered) if args.stage == "run" else json.loads((P / "d3-results.json").read_text())
    print(json.dumps(summarize(pairs, registered), indent=2))


if __name__ == "__main__":
    main()
