#!/usr/bin/env python3
"""Register, validate, and run the wave-6 finite-time Lyapunov diagnostic."""
from pathlib import Path
import argparse
import csv
import fcntl
import hashlib
import json
import math
import os
import re
import shutil
import socket
import statistics
import subprocess
import sys
import tempfile

P = Path(__file__).resolve().parent
W5 = P.parent / "eta2_wave5"
FROZEN = P.parent / "eta2_champion"
sys.path.insert(0, str(P))
sys.path.insert(0, str(W5))
from bal_perturb import (field_scales, load_bal, perturb, read_prism_state,
                         residual_distance, sha256, state_from_bal, write_state)
import native_light as N

PROTOCOL = P / "D2_PROTOCOL.md"
BINARY = P / "build" / "prism-deterministic"
BUILD = P / "deterministic-build-manifest.json"
CHAMPION = json.loads((FROZEN / "champion.json").read_text())
OPTIMIZED = json.loads((W5 / "optimized_candidate.json").read_text())
SCENES = {
    "venice-52": "/workspace/bal/venice-52.txt",
    "final-3068": "/workspace/bal/final-3068.txt",
}
SEEDS = list(range(620000, 620008))
DOSES = {"eps1e-12": {"epsilon": 1e-12, "seeds": SEEDS},
         "eps1e-10": {"epsilon": 1e-10, "seeds": SEEDS[:4]}}


def canonical_hash(value):
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(data.encode()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def registration():
    reg = {
        "protocol_sha256": sha256(PROTOCOL),
        "binary": str(BINARY), "binary_sha256": sha256(BINARY),
        "build_manifest_sha256": sha256(BUILD),
        "champion_sha256": sha256(FROZEN / "champion.json"),
        "optimized_candidate_sha256": sha256(W5 / "optimized_candidate.json"),
        "tool_sha256": {name: sha256(P / name) for name in
                         ("run_d2.py", "bal_perturb.py")},
        "scenes": {name: {"path": path, "input_sha256": sha256(path)}
                   for name, path in SCENES.items()},
        "doses": DOSES,
        "max_iter": 10, "dump_outers": list(range(10)),
        "instrument_validation": {"dump_off": 1, "dump_on": 2},
        "classification": {
            "positive": "median_A10 > 1e3 and median_gamma10 > 0.5",
            "stable": "median_A10 < 10 and median_gamma10 < 0.1",
            "dose_agreement": "same class/sign and median gamma5 within 25% relative",
        },
    }
    path = P / "d2-registration.json"
    if path.exists():
        assert json.loads(path.read_text()) == reg
    else:
        write(path, reg)
    return reg


def clean_environment(binary_dumps):
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("OCA_", "CASPAR_", "CERES_", "COLMAP_MFREE", "MF_DEBUG"))}
    env.update(CHAMPION["flags"])
    env.update(OPTIMIZED["flags_overlay"])
    env["OCA_W6_DETERMINISTIC"] = "1"
    if binary_dumps:
        env["OCA_W6_BINARY_DUMPS"] = "1"
    return env


def decisions(text):
    rows = []
    for line in text.splitlines():
        match = re.match(r"ATTR_RADIUS o=(\d+).* accept=(\d+)$", line.strip())
        if match:
            rows.append((int(match.group(1)), bool(int(match.group(2)))))
    return rows


def normalized_decisions(text):
    prefixes = ("PCG_PREP ", "ATTR_RADIUS ", "CLASSICAL_LM ", "POINT_SAFE o=",
                "MFCG it ", "NUMERIC_REPAIR ")
    return [line.strip() for line in text.splitlines()
            if line.strip().startswith(prefixes)]


def run_trajectory(folder, problem_path, label, binary_dumps=True):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    state_dir = Path(tempfile.mkdtemp(prefix="eta2-w6-d2-", dir="/dev/shm"))
    endpoint = state_dir / "endpoint.state"
    prefix = state_dir / "state"
    cmd = [str(BINARY), "--problem", str(problem_path), "--algo", "mfree_shifted_cg",
           "--dof9", "--zero_k2", "--lam0", "0.1", "--max_iter", "10",
           "--csv", str(folder / "curve.csv"), "--state_out", str(endpoint)]
    if binary_dumps:
        cmd += ["--dump_bal", str(prefix), "--dump_at", ",".join(map(str, range(10)))]
    manifest = {"command": cmd, "flags": clean_environment(binary_dumps),
                "binary_sha256": sha256(BINARY), "input_sha256": sha256(problem_path),
                "protocol_sha256": sha256(PROTOCOL), "host": socket.gethostname(),
                "label": label, "binary_dumps": binary_dumps}
    write(folder / "manifest.json", manifest)
    with open("/tmp/prism_gpu.lock", "w") as lock, (folder / "stdout.log").open("w") as out, \
         (folder / "stderr.log").open("w") as err:
        fcntl.flock(lock, fcntl.LOCK_EX)
        completed = subprocess.run(cmd, env=clean_environment(binary_dumps), stdout=out, stderr=err,
                                   timeout=180)
    text = (folder / "stdout.log").read_text()
    native = re.search(r"RESULT .*?iters=(\d+) final_cost=(\S+) solve_seconds=(\S+)", text)
    counts = re.search(r"MFCG: accepts=(\d+) rejects=(\d+) total_matvecs=(\d+)", text)
    if completed.returncode or not native or not counts:
        raise RuntimeError((completed.returncode, text[-1000:], (folder / "stderr.log").read_text()[-1000:]))
    curves = list(csv.DictReader(line for line in (folder / "curve.csv").read_text().splitlines()
                                 if not line.startswith("#")))
    state_paths = ([state_dir / f"state_it{k}.txt" for k in range(10)] + [endpoint]
                   if binary_dumps else [endpoint])
    if not all(path.exists() for path in state_paths):
        raise RuntimeError("missing compact state dump")
    result = {
        "label": label, "cost": float(native.group(2)), "outers": int(native.group(1)),
        "native_seconds": float(native.group(3)), "accepts": int(counts.group(1)),
        "rejects": int(counts.group(2)), "matvecs": int(counts.group(3)),
        "state_hashes": [sha256(path) for path in state_paths],
        "accepted_cost_strings": [row["cost"] for row in curves],
        "accepted_cost_hash": canonical_hash([row["cost"] for row in curves]),
        "decision_hash": canonical_hash(normalized_decisions(text)),
        "decisions": decisions(text),
        "input_sha256": sha256(problem_path),
    }
    write(folder / "result.json", result)
    return result, state_paths, state_dir


def validate(reg):
    output = {}
    for scene, item in reg["scenes"].items():
        rows = []
        for label, enabled in (("off", False), ("on-a", True), ("on-b", True)):
            result, paths, state_dir = run_trajectory(
                P / "evidence" / "d2-instrument-validation" / scene / label,
                item["path"], label, enabled)
            rows.append(result)
            shutil.rmtree(state_dir)
        keys = ("cost", "outers", "accepts", "rejects", "matvecs",
                "accepted_cost_hash", "decision_hash")
        endpoint_hashes = [row["state_hashes"][-1] for row in rows]
        passed = len(set(endpoint_hashes)) == 1 and all(
            len({json.dumps(row[key], sort_keys=True) for row in rows}) == 1 for key in keys)
        output[scene] = {"passed": passed, "endpoint_hashes": endpoint_hashes,
                         "rows": rows}
    result = {"passed": all(item["passed"] for item in output.values()), "scenes": output}
    write(P / "d2-instrument-validation.json", result)
    if not result["passed"]:
        raise SystemExit(2)
    return result


def first_decision_difference(left, right):
    for index in range(max(len(left), len(right))):
        a = left[index] if index < len(left) else None
        b = right[index] if index < len(right) else None
        if a != b:
            return {"attempt_index": index, "base": a, "perturbed": b}
    return None


def execute(reg):
    all_rows = []
    for scene, item in reg["scenes"].items():
        problem = load_bal(item["path"])
        original_state = state_from_bal(problem)
        base_result, base_paths, base_dir = run_trajectory(
            P / "evidence" / "d2-ftle" / scene / "base", item["path"], "base", True)
        base_states = [read_prism_state(path) for path in base_paths]
        try:
            for cohort, dose in reg["doses"].items():
                for seed in dose["seeds"]:
                    cameras, points, scales = perturb(problem, seed, dose["epsilon"])
                    fd, input_name = tempfile.mkstemp(prefix=f"w6-{scene}-{cohort}-{seed}-",
                                                      suffix=".txt", dir="/dev/shm")
                    os.close(fd)
                    perturbed_input = Path(input_name)
                    write_state(problem, perturbed_input, cameras, points)
                    perturbed_sha256 = sha256(perturbed_input)
                    generated_distance = residual_distance(
                        problem, original_state, state_from_bal(problem, cameras, points))
                    result, paths, state_dir = run_trajectory(
                        P / "evidence" / "d2-ftle" / scene / cohort / str(seed),
                        perturbed_input, f"{cohort}-{seed}", True)
                    try:
                        distances = [residual_distance(problem, base, read_prism_state(path))
                                     for base, path in zip(base_states, paths)]
                    finally:
                        shutil.rmtree(state_dir)
                        perturbed_input.unlink(missing_ok=True)
                    if not distances[0] > 0:
                        raise RuntimeError("zero initial residual-space perturbation")
                    amplification = [value / distances[0] for value in distances]
                    gamma = [None if k == 0 or value <= 0 else math.log(value) / k
                             for k, value in enumerate(amplification)]
                    row = {
                        "scene": scene, "cohort": cohort, "seed": seed,
                        "epsilon": dose["epsilon"], "field_scales": scales,
                        "perturbed_input_sha256": perturbed_sha256,
                        "generated_initial_residual_distance": generated_distance,
                        "binary_initial_residual_distance": distances[0],
                        "residual_distances": distances, "amplification": amplification,
                        "gamma": gamma, "A5": amplification[5], "A10": amplification[10],
                        "gamma5": gamma[5], "gamma10": gamma[10],
                        "first_decision_difference": first_decision_difference(
                            base_result["decisions"], result["decisions"]),
                        "base": {k: base_result[k] for k in
                                 ("cost", "outers", "accepts", "rejects", "matvecs")},
                        "perturbed": {k: result[k] for k in
                                      ("cost", "outers", "accepts", "rejects", "matvecs")},
                        "state_hashes": result["state_hashes"],
                    }
                    all_rows.append(row)
                    write(P / "d2-results.json", all_rows)
        finally:
            shutil.rmtree(base_dir)
    return all_rows


def classify(A10, gamma10):
    if A10 > 1e3 and gamma10 > .5:
        return "positive"
    if A10 < 10 and gamma10 < .1:
        return "stable"
    return "unresolved"


def summarize(rows):
    output = {}
    for scene in SCENES:
        output[scene] = {}
        for cohort in DOSES:
            group = [row for row in rows if row["scene"] == scene and row["cohort"] == cohort]
            med_A10 = statistics.median(row["A10"] for row in group)
            med_g10 = statistics.median(row["gamma10"] for row in group)
            med_g5 = statistics.median(row["gamma5"] for row in group)
            output[scene][cohort] = {
                "N": len(group), "median_A10": med_A10,
                "median_gamma10": med_g10, "median_gamma5": med_g5,
                "classification": classify(med_A10, med_g10),
                "decision_splits": sum(row["first_decision_difference"] is not None for row in group),
                "A10_range": [min(row["A10"] for row in group), max(row["A10"] for row in group)],
            }
        small, large = output[scene]["eps1e-12"], output[scene]["eps1e-10"]
        denom = max(abs(small["median_gamma5"]), abs(large["median_gamma5"]), 1e-300)
        relative = abs(small["median_gamma5"] - large["median_gamma5"]) / denom
        small["cross_dose"] = large["cross_dose"] = {
            "same_class": small["classification"] == large["classification"],
            "same_sign_gamma5": small["median_gamma5"] * large["median_gamma5"] > 0,
            "relative_gamma5_difference": relative,
            "passed": (small["classification"] == large["classification"]
                       and small["median_gamma5"] * large["median_gamma5"] > 0
                       and relative <= .25),
        }
    result = {"scenes": output}
    write(P / "d2-summary.json", result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("register", "validate", "run", "summarize"))
    args = parser.parse_args()
    reg = registration()
    if args.stage == "register":
        print(json.dumps(reg, indent=2)); return
    if args.stage == "validate":
        print(json.dumps(validate(reg), indent=2)); return
    rows = execute(reg) if args.stage == "run" else json.loads((P / "d2-results.json").read_text())
    print(json.dumps(summarize(rows), indent=2))


if __name__ == "__main__":
    main()
