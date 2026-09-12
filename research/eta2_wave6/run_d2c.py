#!/usr/bin/env python3
"""Run the registered FP64-fragment opening sensitivity attribution."""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import shutil
import statistics
import tempfile

import numpy as np

import run_d2b as harness
from bal_perturb import (load_bal, perturb, read_prism_state, residual_distance,
                         sha256, state_from_bal, write_state)


P = Path(__file__).resolve().parent
PROTOCOL = P / "D2C_PROTOCOL.md"
BINARY = P / "build" / "prism-deterministic-fp64-fragments"
BUILD = P / "d2c-build-manifest.json"
SCENE = Path("/workspace/bal/venice-52.txt")
SEEDS = list(range(620000, 620004))
DOSES = [1e-8, 1e-10, 1e-12]

# Reuse the already audited process/parse harness with this experiment's binary
# and protocol so every per-run manifest points at D2c rather than D2b.
harness.BINARY = BINARY
harness.PROTOCOL = PROTOCOL


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def registration():
    result = {
        "protocol_sha256": sha256(PROTOCOL),
        "tool_sha256": sha256(__file__),
        "shared_harness_sha256": sha256(P / "run_d2b.py"),
        "perturbation_tool_sha256": sha256(P / "bal_perturb.py"),
        "binary": str(BINARY),
        "binary_sha256": sha256(BINARY),
        "build_manifest_sha256": sha256(BUILD),
        "scene": str(SCENE),
        "scene_sha256": sha256(SCENE),
        "seeds": SEEDS,
        "doses": DOSES,
        "max_iter": 10,
        "repeatability_runs": 2,
        "classification": {
            "fp32_explains": "slope>=0.75, A medians within 5x, no discrete split, eps1e-12 D10 >=100x smaller",
            "fp32_does_not_explain": "slope<=0.25 and D10 max/min<=3",
            "otherwise": "partial attribution",
        },
    }
    target = P / "d2c-registration.json"
    if target.exists():
        registered = json.loads(target.read_text())
        if registered != result:
            if (P / "d2c-results.json").exists():
                return registered
            raise RuntimeError("D2c registration differs before scored rows")
    else:
        write(target, result)
    return result


def validate():
    rows = []
    for label in ("a", "b"):
        result, _, state_dir = harness.run_trajectory(
            P / "evidence" / "d2c-fp64" / "validation" / label, SCENE, label)
        rows.append(result)
        shutil.rmtree(state_dir)
    fixed = ("cost", "outers", "accepts", "rejects", "matvecs", "state_hashes", "trace_hashes")
    passed = all(rows[0][key] == rows[1][key] for key in fixed)
    result = {"passed": passed, "compared_fields": fixed, "rows": rows}
    write(P / "d2c-validation.json", result)
    if not passed:
        raise RuntimeError("FP64-fragment deterministic repeatability gate failed")
    return result


def execute():
    problem = load_bal(SCENE)
    original = state_from_bal(problem)
    base, base_paths, base_dir = harness.run_trajectory(
        P / "evidence" / "d2c-fp64" / "base", SCENE, "base")
    base_states = [read_prism_state(path) for path in base_paths]
    rows = []
    try:
        for epsilon in DOSES:
            cohort = f"eps{epsilon:.0e}"
            for seed in SEEDS:
                cameras, points, scales = perturb(problem, seed, epsilon)
                fd, name = tempfile.mkstemp(prefix=f"w6-d2c-{cohort}-{seed}-", suffix=".txt",
                                            dir="/dev/shm")
                os.close(fd)
                perturbed = Path(name)
                write_state(problem, perturbed, cameras, points)
                initial = residual_distance(problem, original,
                                            state_from_bal(problem, cameras, points))
                run, paths, state_dir = harness.run_trajectory(
                    P / "evidence" / "d2c-fp64" / cohort / str(seed),
                    perturbed, f"{cohort}-{seed}")
                try:
                    distances = [residual_distance(problem, left, read_prism_state(right))
                                 for left, right in zip(base_states, paths)]
                finally:
                    shutil.rmtree(state_dir)
                    perturbed.unlink(missing_ok=True)
                amplification = [distance / distances[0] for distance in distances]
                row = {
                    "epsilon": epsilon,
                    "seed": seed,
                    "field_scales": scales,
                    "generated_initial_residual_distance": initial,
                    "binary_initial_residual_distance": distances[0],
                    "residual_distances": distances,
                    "amplification": amplification,
                    "D10": distances[10],
                    "A10": amplification[10],
                    "trace_differences": {
                        key: harness.first_difference(base["trace_lines"][key], run["trace_lines"][key])
                        for key in base["trace_lines"]
                    },
                    "base": {key: base[key] for key in ("cost", "outers", "accepts", "rejects", "matvecs", "native_seconds")},
                    "perturbed": {key: run[key] for key in ("cost", "outers", "accepts", "rejects", "matvecs", "native_seconds")},
                }
                rows.append(row)
                write(P / "d2c-results.json", rows)
    finally:
        shutil.rmtree(base_dir)
    return rows


def summarize(rows):
    groups = []
    medians_d = []
    medians_a = []
    for epsilon in DOSES:
        group = [row for row in rows if row["epsilon"] == epsilon]
        if len(group) != len(SEEDS):
            raise RuntimeError((epsilon, len(group)))
        md = statistics.median(row["D10"] for row in group)
        ma = statistics.median(row["A10"] for row in group)
        medians_d.append(md)
        medians_a.append(ma)
        groups.append({
            "epsilon": epsilon,
            "N": len(group),
            "median_D10": md,
            "D10_range": [min(row["D10"] for row in group), max(row["D10"] for row in group)],
            "median_A10": ma,
            "global_splits": sum(row["trace_differences"]["global"] is not None for row in group),
            "cg_splits": sum(row["trace_differences"]["cg"] is not None for row in group),
            "point_safe_splits": sum(row["trace_differences"]["point_safe"] is not None for row in group),
            "median_native_seconds": statistics.median(row["perturbed"]["native_seconds"] for row in group),
        })
    slope = float(np.polyfit(np.log(DOSES), np.log(medians_d), 1)[0])
    d_ratio = float(max(medians_d) / min(medians_d))
    a_ratio = float(max(medians_a) / min(medians_a))
    no_discrete = all(
        difference is None
        for row in rows for difference in row["trace_differences"].values()
    )
    fp32_rows = json.loads((P / "d2b-results.json").read_text())
    fp32 = {}
    for epsilon in DOSES:
        group = [row for row in fp32_rows
                 if row["scene"] == "venice-52" and row["epsilon"] == epsilon]
        fp32[str(epsilon)] = statistics.median(row["D10"] for row in group)
    fp32_slope = float(np.polyfit(np.log(DOSES), np.log([fp32[str(e)] for e in DOSES]), 1)[0])
    smallest_drop = fp32[str(1e-12)] / medians_d[-1]
    explains = slope >= .75 and a_ratio <= 5 and no_discrete and smallest_drop >= 100
    does_not = slope <= .25 and d_ratio <= 3
    classification = "FP32 fragments explain the jump" if explains else (
        "FP32 fragments do not explain the jump" if does_not else "partial attribution")
    result = {
        "schema": 1,
        "groups": groups,
        "fp64_log_log_slope": slope,
        "fp64_D10_ratio": d_ratio,
        "fp64_A10_ratio": a_ratio,
        "no_discrete_choice_differences": no_discrete,
        "fp32_comparison": {
            "median_D10": fp32,
            "log_log_slope": fp32_slope,
            "eps1e-12_D10_drop_factor": smallest_drop,
        },
        "classification": classification,
    }
    write(P / "d2c-summary.json", result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("register", "validate", "run", "summarize"))
    args = parser.parse_args()
    reg = registration()
    if args.stage == "register":
        print(json.dumps(reg, indent=2)); return
    if args.stage == "validate":
        print(json.dumps(validate(), indent=2)); return
    rows = execute() if args.stage == "run" else json.loads((P / "d2c-results.json").read_text())
    print(json.dumps(summarize(rows), indent=2))


if __name__ == "__main__":
    main()
