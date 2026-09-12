#!/usr/bin/env python3
"""Run the preregistered five-dose opening-map scale ladder."""
from __future__ import annotations

import argparse
import csv
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import socket
import statistics
import subprocess
import tempfile

import numpy as np

from bal_perturb import (load_bal, perturb, read_prism_state, residual_distance,
                         sha256, state_from_bal, write_state)


P = Path(__file__).resolve().parent
FROZEN = P.parent / "eta2_champion"
W5 = P.parent / "eta2_wave5"
PROTOCOL = P / "D2B_PROTOCOL.md"
BINARY = P / "build" / "prism-deterministic"
CHAMPION = json.loads((FROZEN / "champion.json").read_text())
OPTIMIZED = json.loads((W5 / "optimized_candidate.json").read_text())
SCENES = {
    "venice-52": Path("/workspace/bal/venice-52.txt"),
    "final-3068": Path("/workspace/bal/final-3068.txt"),
}
SEEDS = list(range(620000, 620004))
NEW_DOSES = (1e-8, 1e-9, 1e-11)
ALL_DOSES = (1e-8, 1e-9, 1e-10, 1e-11, 1e-12)


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def canonical_hash(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def clean_environment():
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(("OCA_", "CASPAR_", "CERES_", "COLMAP_MFREE", "MF_DEBUG"))}
    env.update(CHAMPION["flags"])
    env.update(OPTIMIZED["flags_overlay"])
    env["OCA_W6_DETERMINISTIC"] = "1"
    env["OCA_W6_BINARY_DUMPS"] = "1"
    return env


def registration():
    result = {
        "protocol_sha256": sha256(PROTOCOL),
        "tool_sha256": sha256(__file__),
        "perturbation_tool_sha256": sha256(P / "bal_perturb.py"),
        "binary": str(BINARY),
        "binary_sha256": sha256(BINARY),
        "champion_sha256": sha256(FROZEN / "champion.json"),
        "optimized_candidate_sha256": sha256(W5 / "optimized_candidate.json"),
        "prior_d2_results_sha256": sha256(P / "d2-results.json"),
        "scenes": {name: {"path": str(path), "sha256": sha256(path)}
                   for name, path in SCENES.items()},
        "seeds": SEEDS,
        "new_doses": NEW_DOSES,
        "reused_doses": (1e-10, 1e-12),
        "max_iter": 10,
        "classification": {
            "smooth": "three consecutive slopes in [0.75,1.25], A ratio <=3, no decisions differ",
            "finite_jump": "smallest-three-dose slope <=0.25 and D10 max/min <=3",
            "otherwise": "piecewise/ambiguous",
        },
    }
    serial_result = json.loads(json.dumps(result))
    target = P / "d2b-registration.json"
    if target.exists():
        if json.loads(target.read_text()) != serial_result:
            if (P / "d2b-new-results.json").exists():
                raise RuntimeError("existing D2b registration differs after scored rows exist")
            write(target, result)
    else:
        write(target, result)
    return serial_result


def normalized_lines(text, prefix):
    return [line.strip() for line in text.splitlines() if line.strip().startswith(prefix)]


def first_difference(left, right):
    for index in range(max(len(left), len(right))):
        a = left[index] if index < len(left) else None
        b = right[index] if index < len(right) else None
        if a != b:
            return {"index": index, "base": a, "perturbed": b}
    return None


def run_trajectory(folder, problem_path, label):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    state_dir = Path(tempfile.mkdtemp(prefix="eta2-w6-d2b-", dir="/dev/shm"))
    endpoint = state_dir / "endpoint.state"
    prefix = state_dir / "state"
    cmd = [str(BINARY), "--problem", str(problem_path), "--algo", "mfree_shifted_cg",
           "--dof9", "--zero_k2", "--lam0", "0.1", "--max_iter", "10",
           "--csv", str(folder / "curve.csv"), "--state_out", str(endpoint),
           "--dump_bal", str(prefix), "--dump_at", ",".join(map(str, range(10)))]
    manifest = {
        "command": cmd,
        "flags": clean_environment(),
        "binary_sha256": sha256(BINARY),
        "input_sha256": sha256(problem_path),
        "protocol_sha256": sha256(PROTOCOL),
        "host": socket.gethostname(),
        "label": label,
    }
    write(folder / "manifest.json", manifest)
    with open("/tmp/prism_gpu.lock", "w") as lock, (folder / "stdout.log").open("w") as out, \
            (folder / "stderr.log").open("w") as err:
        fcntl.flock(lock, fcntl.LOCK_EX)
        completed = subprocess.run(cmd, env=clean_environment(), stdout=out, stderr=err, timeout=180)
    stdout = (folder / "stdout.log").read_text()
    native = re.search(r"RESULT .*?iters=(\d+) final_cost=(\S+) solve_seconds=(\S+)", stdout)
    counts = re.search(r"MFCG: accepts=(\d+) rejects=(\d+) total_matvecs=(\d+)", stdout)
    if completed.returncode or not native or not counts:
        raise RuntimeError((completed.returncode, stdout[-2000:], (folder / "stderr.log").read_text()[-2000:]))
    state_paths = [state_dir / f"state_it{k}.txt" for k in range(10)] + [endpoint]
    if not all(path.exists() for path in state_paths):
        raise RuntimeError("missing compact state")
    categories = {
        "global": normalized_lines(stdout, "ATTR_RADIUS "),
        "cg": normalized_lines(stdout, "MFCG it "),
        "point_safe": normalized_lines(stdout, "POINT_SAFE o="),
    }
    result = {
        "label": label,
        "cost": float(native.group(2)),
        "outers": int(native.group(1)),
        "native_seconds": float(native.group(3)),
        "accepts": int(counts.group(1)),
        "rejects": int(counts.group(2)),
        "matvecs": int(counts.group(3)),
        "state_hashes": [sha256(path) for path in state_paths],
        "trace_hashes": {key: canonical_hash(value) for key, value in categories.items()},
        "trace_lines": categories,
    }
    write(folder / "result.json", result)
    return result, state_paths, state_dir


def execute():
    rows = []
    for scene, path in SCENES.items():
        problem = load_bal(path)
        original_state = state_from_bal(problem)
        base, base_paths, base_dir = run_trajectory(
            P / "evidence" / "d2b-scale" / scene / "base", path, "base")
        base_states = [read_prism_state(state) for state in base_paths]
        try:
            for epsilon in NEW_DOSES:
                cohort = f"eps{epsilon:.0e}"
                for seed in SEEDS:
                    cameras, points, scales = perturb(problem, seed, epsilon)
                    fd, input_name = tempfile.mkstemp(
                        prefix=f"w6-{scene}-{cohort}-{seed}-", suffix=".txt", dir="/dev/shm")
                    os.close(fd)
                    perturbed_path = Path(input_name)
                    write_state(problem, perturbed_path, cameras, points)
                    generated_distance = residual_distance(
                        problem, original_state, state_from_bal(problem, cameras, points))
                    run, state_paths, state_dir = run_trajectory(
                        P / "evidence" / "d2b-scale" / scene / cohort / str(seed),
                        perturbed_path, f"{cohort}-{seed}")
                    try:
                        distances = [residual_distance(problem, left, read_prism_state(right))
                                     for left, right in zip(base_states, state_paths)]
                    finally:
                        shutil.rmtree(state_dir)
                        perturbed_path.unlink(missing_ok=True)
                    amplification = [distance / distances[0] for distance in distances]
                    trace_differences = {
                        key: first_difference(base["trace_lines"][key], run["trace_lines"][key])
                        for key in base["trace_lines"]
                    }
                    row = {
                        "scene": scene,
                        "epsilon": epsilon,
                        "seed": seed,
                        "field_scales": scales,
                        "generated_initial_residual_distance": generated_distance,
                        "binary_initial_residual_distance": distances[0],
                        "residual_distances": distances,
                        "amplification": amplification,
                        "D5": distances[5],
                        "D10": distances[10],
                        "A5": amplification[5],
                        "A10": amplification[10],
                        "trace_differences": trace_differences,
                        "base": {key: base[key] for key in ("cost", "outers", "accepts", "rejects", "matvecs")},
                        "perturbed": {key: run[key] for key in ("cost", "outers", "accepts", "rejects", "matvecs")},
                    }
                    rows.append(row)
                    write(P / "d2b-new-results.json", rows)
        finally:
            shutil.rmtree(base_dir)
    return rows


def prior_trace_difference(scene, cohort, seed, category):
    base_path = P / "evidence" / "d2-ftle" / scene / "base" / "stdout.log"
    run_path = P / "evidence" / "d2-ftle" / scene / cohort / str(seed) / "stdout.log"
    prefix = {"global": "ATTR_RADIUS ", "cg": "MFCG it ", "point_safe": "POINT_SAFE o="}[category]
    return first_difference(normalized_lines(base_path.read_text(), prefix),
                            normalized_lines(run_path.read_text(), prefix))


def merge_prior(new_rows):
    prior = json.loads((P / "d2-results.json").read_text())
    merged = list(new_rows)
    cohort_for = {1e-10: "eps1e-10", 1e-12: "eps1e-12"}
    for row in prior:
        if row["seed"] not in SEEDS or row["epsilon"] not in cohort_for:
            continue
        merged.append({
            "scene": row["scene"],
            "epsilon": row["epsilon"],
            "seed": row["seed"],
            "field_scales": row["field_scales"],
            "generated_initial_residual_distance": row["generated_initial_residual_distance"],
            "binary_initial_residual_distance": row["binary_initial_residual_distance"],
            "residual_distances": row["residual_distances"],
            "amplification": row["amplification"],
            "D5": row["residual_distances"][5],
            "D10": row["residual_distances"][10],
            "A5": row["A5"],
            "A10": row["A10"],
            "trace_differences": {
                category: prior_trace_difference(
                    row["scene"], cohort_for[row["epsilon"]], row["seed"], category)
                for category in ("global", "cg", "point_safe")
            },
            "base": row["base"],
            "perturbed": row["perturbed"],
            "source": "reused registered D2 row",
        })
    merged.sort(key=lambda row: (row["scene"], -row["epsilon"], row["seed"]))
    write(P / "d2b-results.json", merged)
    return merged


def dose_group(rows, scene, epsilon):
    return [row for row in rows if row["scene"] == scene and row["epsilon"] == epsilon]


def summarize(rows):
    output = {}
    for scene in SCENES:
        doses = []
        medians = []
        for epsilon in ALL_DOSES:
            group = dose_group(rows, scene, epsilon)
            if len(group) != len(SEEDS):
                raise RuntimeError((scene, epsilon, len(group)))
            median_d10 = statistics.median(row["D10"] for row in group)
            median_a10 = statistics.median(row["A10"] for row in group)
            medians.append(median_d10)
            doses.append({
                "epsilon": epsilon,
                "N": len(group),
                "median_D5": statistics.median(row["D5"] for row in group),
                "median_D10": median_d10,
                "D10_range": [min(row["D10"] for row in group), max(row["D10"] for row in group)],
                "median_A10": median_a10,
                "global_split_count": sum(row["trace_differences"]["global"] is not None for row in group),
                "cg_split_count": sum(row["trace_differences"]["cg"] is not None for row in group),
                "point_safe_split_count": sum(row["trace_differences"]["point_safe"] is not None for row in group),
            })
        x = np.log(np.asarray(ALL_DOSES))
        y = np.log(np.asarray(medians))
        full_slope = float(np.polyfit(x, y, 1)[0])
        adjacent = [float((y[i + 1] - y[i]) / (x[i + 1] - x[i])) for i in range(len(x) - 1)]
        small_slope = float(np.polyfit(x[-3:], y[-3:], 1)[0])
        small_ratio = float(max(medians[-3:]) / min(medians[-3:]))
        finite_jump = small_slope <= .25 and small_ratio <= 3
        smooth = False
        smooth_windows = []
        for start in range(3):
            window_slopes = adjacent[start:start + 2]
            window = doses[start:start + 3]
            amp = [row["median_A10"] for row in window]
            no_decisions = all(row["global_split_count"] == 0 and row["cg_split_count"] == 0
                               and row["point_safe_split_count"] == 0 for row in window)
            passed = (all(.75 <= slope <= 1.25 for slope in window_slopes)
                      and max(amp) / min(amp) <= 3 and no_decisions)
            smooth_windows.append({"start_epsilon": window[0]["epsilon"], "passed": passed})
            smooth |= passed
        classification = "finite-jump plateau" if finite_jump else (
            "smooth linear regime" if smooth else "piecewise/ambiguous")
        output[scene] = {
            "doses": doses,
            "full_log_log_slope": full_slope,
            "adjacent_decade_slopes": adjacent,
            "smallest_three_slope": small_slope,
            "smallest_three_D10_ratio": small_ratio,
            "smooth_windows": smooth_windows,
            "classification": classification,
        }
    result = {"schema": 1, "scenes": output}
    write(P / "d2b-summary.json", result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("register", "run", "summarize"))
    args = parser.parse_args()
    reg = registration()
    if args.stage == "register":
        print(json.dumps(reg, indent=2)); return
    if args.stage == "run":
        new_rows = execute()
        rows = merge_prior(new_rows)
    else:
        rows = json.loads((P / "d2b-results.json").read_text())
    print(json.dumps(summarize(rows), indent=2))


if __name__ == "__main__":
    main()
