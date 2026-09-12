#!/usr/bin/env python3
"""Run the registered FP64-fragment diagnostic on Final3068."""
from __future__ import annotations

import argparse
import json
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
PROTOCOL = P / "D2D_PROTOCOL.md"
BINARY = P / "build" / "prism-deterministic-fp64-fragments"
BUILD = P / "d2c-build-manifest.json"
SCENE = Path("/workspace/bal/final-3068.txt")
SEEDS = list(range(620000, 620004))
DOSES = [1e-8, 1e-10, 1e-12]
harness.BINARY = BINARY
harness.PROTOCOL = PROTOCOL


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def registration():
    value = {
        "protocol_sha256": sha256(PROTOCOL),
        "tool_sha256": sha256(__file__),
        "shared_harness_sha256": sha256(P / "run_d2b.py"),
        "binary_sha256": sha256(BINARY),
        "build_manifest_sha256": sha256(BUILD),
        "scene": str(SCENE),
        "scene_sha256": sha256(SCENE),
        "seeds": SEEDS,
        "doses": DOSES,
        "max_iter": 10,
        "gate": "two extra slope>=0.75 outers, or eps1e-12 D10 >=100x smaller without earlier split",
    }
    target = P / "d2d-registration.json"
    if target.exists():
        old = json.loads(target.read_text())
        if old != value:
            if (P / "d2d-results.json").exists():
                return old
            raise RuntimeError("D2d registration changed")
    else:
        write(target, value)
    return value


def execute():
    problem = load_bal(SCENE)
    original = state_from_bal(problem)
    base, base_paths, base_dir = harness.run_trajectory(
        P / "evidence" / "d2d-final-fp64" / "base", SCENE, "base")
    base_states = [read_prism_state(path) for path in base_paths]
    rows = []
    try:
        for epsilon in DOSES:
            cohort = f"eps{epsilon:.0e}"
            for seed in SEEDS:
                cameras, points, scales = perturb(problem, seed, epsilon)
                fd, name = tempfile.mkstemp(prefix=f"w6-d2d-{cohort}-{seed}-",
                                            suffix=".txt", dir="/dev/shm")
                os.close(fd)
                perturbed = Path(name)
                write_state(problem, perturbed, cameras, points)
                initial = residual_distance(problem, original,
                                            state_from_bal(problem, cameras, points))
                run, paths, state_dir = harness.run_trajectory(
                    P / "evidence" / "d2d-final-fp64" / cohort / str(seed),
                    perturbed, f"{cohort}-{seed}")
                try:
                    distances = [residual_distance(problem, left, read_prism_state(right))
                                 for left, right in zip(base_states, paths)]
                finally:
                    shutil.rmtree(state_dir)
                    perturbed.unlink(missing_ok=True)
                row = {
                    "epsilon": epsilon,
                    "seed": seed,
                    "field_scales": scales,
                    "generated_initial_residual_distance": initial,
                    "binary_initial_residual_distance": distances[0],
                    "residual_distances": distances,
                    "D10": distances[10],
                    "A10": distances[10] / distances[0],
                    "trace_differences": {
                        key: harness.first_difference(base["trace_lines"][key], run["trace_lines"][key])
                        for key in base["trace_lines"]
                    },
                    "base": {key: base[key] for key in ("cost", "outers", "accepts", "rejects", "matvecs", "native_seconds")},
                    "perturbed": {key: run[key] for key in ("cost", "outers", "accepts", "rejects", "matvecs", "native_seconds")},
                }
                rows.append(row)
                write(P / "d2d-results.json", rows)
    finally:
        shutil.rmtree(base_dir)
    return rows


def median_curve(rows, source):
    result = []
    for epsilon in DOSES:
        group = [row for row in rows if row["epsilon"] == epsilon]
        result.append([statistics.median(row[source][outer] if source != "residual_distances"
                                         else row[source][outer] for row in group)
                       for outer in range(11)])
    return np.asarray(result)


def first_bad_slope(slopes):
    for outer, slope in enumerate(slopes):
        if not .75 <= slope <= 1.25:
            return outer
    return len(slopes)


def summarize(rows):
    fp32_all = json.loads((P / "d2b-results.json").read_text())
    fp32 = [row for row in fp32_all
            if row["scene"] == "final-3068" and row["epsilon"] in DOSES]
    curves = {}
    for name, cohort in (("fp32", fp32), ("fp64", rows)):
        med = median_curve(cohort, "residual_distances")
        slopes = [float(np.polyfit(np.log(DOSES), np.log(med[:, outer]), 1)[0])
                  for outer in range(11)]
        curves[name] = {
            "median_distances_by_dose": {str(e): med[i].tolist() for i, e in enumerate(DOSES)},
            "slopes_by_outer": slopes,
            "first_outer_outside_linear_slope": first_bad_slope(slopes),
            "median_D10_by_dose": {str(e): float(med[i, 10]) for i, e in enumerate(DOSES)},
        }
    extra = (curves["fp64"]["first_outer_outside_linear_slope"]
             - curves["fp32"]["first_outer_outside_linear_slope"])
    drop = (curves["fp32"]["median_D10_by_dose"][str(1e-12)]
            / curves["fp64"]["median_D10_by_dose"][str(1e-12)])
    def entry_outer(entry):
        if entry is None:
            return None
        fields = entry.split(":")
        if fields[0] in ("accept", "retry"):
            return int(fields[1]) - 1
        return int(fields[0])
    def first_split(group):
        outers = []
        for row in group:
            for difference in row["trace_differences"].values():
                if difference is not None:
                    values = [entry_outer(difference.get(side)) for side in ("base", "perturbed")]
                    outers.extend(value for value in values if value is not None)
        return min(outers) if outers else None
    fp32_first = first_split(fp32)
    fp64_first = first_split(rows)
    no_earlier = fp64_first is None or (fp32_first is not None and fp64_first >= fp32_first)
    gate = extra >= 2 or (drop >= 100 and no_earlier)
    groups = []
    for epsilon in DOSES:
        group = [row for row in rows if row["epsilon"] == epsilon]
        groups.append({
            "epsilon": epsilon,
            "N": len(group),
            "median_D10": statistics.median(row["D10"] for row in group),
            "D10_range": [min(row["D10"] for row in group), max(row["D10"] for row in group)],
            "global_splits": sum(row["trace_differences"]["global"] is not None for row in group),
            "cg_splits": sum(row["trace_differences"]["cg"] is not None for row in group),
            "point_safe_splits": sum(row["trace_differences"]["point_safe"] is not None for row in group),
            "first_discrete_split_outer": first_split(group),
        })
    result = {
        "schema": 1,
        "groups": groups,
        "curves": curves,
        "extra_linear_outers": extra,
        "eps1e-12_D10_drop_factor": drop,
        "first_discrete_split": {"fp32": fp32_first, "fp64": fp64_first},
        "registered_gate_passed": gate,
        "decision": "permit paired full-convergence precision test" if gate else "stop precision path for Final3068",
    }
    write(P / "d2d-summary.json", result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("register", "run", "summarize"))
    args = parser.parse_args()
    reg = registration()
    if args.stage == "register":
        print(json.dumps(reg, indent=2)); return
    rows = execute() if args.stage == "run" else json.loads((P / "d2d-results.json").read_text())
    print(json.dumps(summarize(rows), indent=2))


if __name__ == "__main__":
    main()
