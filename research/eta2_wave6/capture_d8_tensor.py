#!/usr/bin/env python3
"""Replay the preregistered D8 trajectory and retain exact boundary states."""
from __future__ import annotations

import csv
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time

P = Path(__file__).resolve().parent
FROZEN = P.parent / "eta2_champion"
W5 = P.parent / "eta2_wave5"
sys.path.insert(0, str(P))
from bal_perturb import load_bal, perturb, sha256, write_state

PROTOCOL = P / "D8_TENSOR_SECANT_PROTOCOL.md"
BINARY = P / "build/prism-deterministic"
INPUT = Path("/workspace/bal/final-3068.txt")
EVIDENCE = Path("/workspace/eta2-wave6-evidence/d8-tensor")
SEED = 640005
EPSILON = 1e-10
TARGET = 1744796.9841897595
CAP = 45.0
CURRENT = (37, 40, 43, 47, 51)
DUMP = tuple(sorted({value + offset for value in CURRENT for offset in (-1, 0, 1)
                     if value + offset < 52}))

ATTR = re.compile(
    r"ATTR_RADIUS o=(\d+) raw_norm=(\S+) norm=(\S+) radius=(\S+) "
    r"next_radius=(\S+) lambda=(\S+) next_lambda=(\S+) rho=(\S+) accept=(\d+)")
CLASSICAL = re.compile(
    r"CLASSICAL_LM o=(\d+) lambda=(\S+) tau=(\S+) prediction=(\S+) "
    r"rho=(\S+) accept=(\d+)")
RESULT = re.compile(r"RESULT .*?iters=(\d+) final_cost=(\S+) solve_seconds=(\S+)")


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True,
                               allow_nan=False) + "\n")


def cost_rows(path: Path):
    return [(row["iter"], row["cost"])
            for row in csv.DictReader(line for line in path.read_text().splitlines()
                                      if not line.startswith("#"))]


def parse_attempts(text: str):
    attrs = {}
    for match in ATTR.finditer(text):
        outer = int(match[1])
        row = dict(outer=outer, raw_norm=float(match[2]), feasible_norm=float(match[3]),
                   radius=float(match[4]), next_radius=float(match[5]),
                   lambda_value=float(match[6]), next_lambda=float(match[7]),
                   rho=float(match[8]), accepted=bool(int(match[9])))
        attrs.setdefault(outer, []).append(row)
    classical = {}
    for match in CLASSICAL.finditer(text):
        outer = int(match[1])
        row = dict(outer=outer, lambda_value=float(match[2]), tau=float(match[3]),
                   prediction=float(match[4]), rho=float(match[5]),
                   accepted=bool(int(match[6])))
        classical.setdefault(outer, []).append(row)
    selected = {}
    for outer in CURRENT:
        aa = [row for row in attrs.get(outer, []) if row["accepted"]]
        cc = [row for row in classical.get(outer, []) if row["accepted"]]
        if len(aa) != 1 or len(cc) != 1:
            raise RuntimeError(f"expected one committed attempt at outer {outer}: {len(aa)}, {len(cc)}")
        if abs(aa[0]["lambda_value"] - cc[0]["lambda_value"]) > 0:
            raise RuntimeError(f"lambda parse disagreement at outer {outer}")
        selected[str(outer)] = aa[0] | {"tau": cc[0]["tau"],
                                       "quadratic_prediction": cc[0]["prediction"]}
    return selected


def main():
    champion = json.loads((FROZEN / "champion.json").read_text())
    optimized = json.loads((W5 / "optimized_candidate.json").read_text())
    build = json.loads((P / "deterministic-build-manifest.json").read_text())
    old_pairs = json.loads((P / "d3-results.json").read_text())
    old = next(pair for pair in old_pairs if pair["seed"] == SEED)["arms"]["fp32"]
    if digest(BINARY) != build["binary_sha256"]:
        raise RuntimeError("deterministic binary hash mismatch")
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    temp_input = Path(f"/dev/shm/w6-d8-final-{SEED}.txt")
    problem = load_bal(INPUT)
    cameras, points, scales = perturb(problem, SEED, EPSILON)
    write_state(problem, temp_input, cameras, points)
    if sha256(temp_input) != "522398e82dae465e94d929acb29cabcb44c10f896b0b68eadc5f75a5997b39ea":
        raise RuntimeError("regenerated D3 input hash mismatch")

    prefix = EVIDENCE / "state"
    curve = EVIDENCE / "curve.csv"
    endpoint = EVIDENCE / "endpoint.state"
    stdout = EVIDENCE / "stdout.log"
    stderr = EVIDENCE / "stderr.log"
    for path in (curve, endpoint, stdout, stderr,
                 *(Path(str(prefix) + f"_it{k}.txt") for k in DUMP)):
        path.unlink(missing_ok=True)

    clean = {key: value for key, value in os.environ.items()
             if not key.startswith(("OCA_", "CASPAR_", "CERES_", "COLMAP_MFREE", "MF_DEBUG"))}
    flags = dict(champion["flags"], **optimized["flags_overlay"],
                 OCA_W6_DETERMINISTIC="1", OCA_W6_BINARY_DUMPS="1",
                 OCA_MAX_SECONDS=str(CAP), OCA_TARGET_COST=str(TARGET))
    clean.update(flags)
    command = [str(BINARY), "--problem", str(temp_input), *champion["cli"],
               "--csv", str(curve), "--state_out", str(endpoint),
               "--dump_bal", str(prefix),
               "--dump_at", ",".join(map(str, DUMP))]
    started = time.monotonic()
    try:
        with open("/tmp/prism_gpu.lock", "w") as lock, stdout.open("w") as out, stderr.open("w") as err:
            fcntl.flock(lock, fcntl.LOCK_EX)
            run = subprocess.run(command, env=clean, stdout=out, stderr=err,
                                 timeout=3 * CAP)
    finally:
        temp_input.unlink(missing_ok=True)
    if run.returncode != 0:
        raise RuntimeError(f"D8 replay failed: {run.returncode}")
    text = stdout.read_text()
    result = RESULT.search(text)
    if not result:
        raise RuntimeError("missing native result")
    if int(result[1]) != old["outers"] or float(result[2]) != old["native_cost"]:
        raise RuntimeError("replay endpoint scalar mismatch")
    if digest(endpoint) != old["state_sha256"]:
        raise RuntimeError("replay endpoint state mismatch")
    prior_curve = P / old["source"] / "curve.csv"
    if cost_rows(curve) != cost_rows(prior_curve):
        raise RuntimeError("replay cost trace mismatch")
    state_paths = {str(k): Path(str(prefix) + f"_it{k}.txt") for k in DUMP}
    if any(not path.exists() for path in state_paths.values()):
        raise RuntimeError("missing boundary state")

    manifest = {
        "schema": 1,
        "protocol_sha256": digest(PROTOCOL),
        "capture_tool_sha256": digest(Path(__file__)),
        "baseline": {
            "champion_sha256": digest(FROZEN / "champion.json"),
            "optimized_candidate_sha256": digest(W5 / "optimized_candidate.json"),
            "binary": str(BINARY), "binary_sha256": digest(BINARY),
        },
        "host": socket.gethostname(), "command": command, "flags": flags,
        "input": {"source": str(INPUT), "source_sha256": digest(INPUT),
                  "seed": SEED, "epsilon": EPSILON,
                  "regenerated_sha256": "522398e82dae465e94d929acb29cabcb44c10f896b0b68eadc5f75a5997b39ea",
                  "field_scales": scales},
        "selection": {"current_outers": CURRENT, "dumped_boundaries": DUMP,
                      "prior_result": old},
        "replay": {"outers": int(result[1]), "native_cost": float(result[2]),
                   "solve_seconds": float(result[3]),
                   "process_seconds": time.monotonic() - started,
                   "cost_trace_exact": True, "endpoint_state_exact": True,
                   "accepted_attempts": parse_attempts(text)},
        "files": {
            "curve": {"path": str(curve), "sha256": digest(curve), "bytes": curve.stat().st_size},
            "stdout": {"path": str(stdout), "sha256": digest(stdout), "bytes": stdout.stat().st_size},
            "stderr": {"path": str(stderr), "sha256": digest(stderr), "bytes": stderr.stat().st_size},
            "endpoint": {"path": str(endpoint), "sha256": digest(endpoint), "bytes": endpoint.stat().st_size},
            "states": {key: {"path": str(path), "sha256": digest(path), "bytes": path.stat().st_size}
                       for key, path in state_paths.items()},
        },
    }
    write_json(P / "d8-capture-manifest.json", manifest)
    print(json.dumps({"status": "captured", "states": len(state_paths),
                      "endpoint_cost": manifest["replay"]["native_cost"],
                      "endpoint_sha256": digest(endpoint),
                      "process_seconds": manifest["replay"]["process_seconds"]}, indent=2))


if __name__ == "__main__":
    main()
