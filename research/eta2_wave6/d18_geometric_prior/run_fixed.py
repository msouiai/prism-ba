#!/usr/bin/env python3
"""Run the D18 fixed-system dose screen."""
from __future__ import annotations

import fcntl
import hashlib
import json
import pathlib
import re
import subprocess

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CAPTURE = pathlib.Path("/workspace/prism-wave6-d18")
BUILD = pathlib.Path("/tmp/prism-wave6-d18-build/geometric_prior_fixed")
OUT = pathlib.Path("/workspace/prism-wave6-d18/fixed-solutions")


def sha(path: pathlib.Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main() -> None:
    build = json.loads((HERE / "build-manifest.json").read_text())
    captures = json.loads((HERE / "capture-manifest.json").read_text())
    assert sha(BUILD) == build["binary_sha256"]
    OUT.mkdir(parents=True, exist_ok=True)
    results = []
    pattern = re.compile(
        r"D18 arm=(\S+) rep=(\d+) updates=(\d+) products=(\d+) "
        r"recursive_relative=(\S+) true_relative=(\S+) hit=(\d+) negative=(\d+) "
        r"min_curvature=(\S+) total_ms=(\S+) raw_norm=(\S+) gated_energy_fraction=(\S+)")
    with open("/tmp/prism_gpu.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        for index in range(5):
            capture = CAPTURE / f"venice-terminal-{index}"
            destination = OUT / f"venice-terminal-{index}"
            destination.mkdir(exist_ok=True)
            command = [str(BUILD), str(capture), str(destination)]
            process = subprocess.run(command, text=True, capture_output=True,
                                     check=True, timeout=180)
            (destination / "stdout.log").write_text(process.stdout)
            rows = []
            for match in pattern.finditer(process.stdout):
                arm, rep, updates, products, recursive, true, hit, negative, curvature, ms, norm, fraction = match.groups()
                rows.append({
                    "index": index, "arm": arm, "rep": int(rep),
                    "updates": int(updates), "products": int(products),
                    "recursive_relative": float(recursive), "true_relative": float(true),
                    "hit": bool(int(hit)), "negative": bool(int(negative)),
                    "min_curvature": float(curvature), "total_ms": float(ms),
                    "raw_norm": float(norm), "gated_energy_fraction": float(fraction),
                })
            system = re.search(
                r"SYSTEM .* gated=(\d+) mu_ref=(\S+) top_camera=(\d+) "
                r"weakest_camera=(\d+) raw_ratio=(\S+) top_energy_fraction=(\S+) ids=([^\n]*)",
                process.stdout)
            if not system or len(rows) != 18:
                raise RuntimeError(("D18 parse", index, len(rows), process.stdout[-1000:]))
            result = {
                "index": index,
                "system": {
                    "gated": int(system[1]), "mu_ref": float(system[2]),
                    "top_camera": int(system[3]), "weakest_camera": int(system[4]),
                    "raw_ratio": float(system[5]), "top_energy_fraction": float(system[6]),
                    "gate_ids": [int(x) for x in system[7].split(",") if x],
                },
                "rows": rows, "command": command,
                "stdout_sha256": sha(destination / "stdout.log"),
                "capture_manifest_sha256": sha(capture / "capture_manifest.json"),
            }
            results.append(result)
            print("D18_FIXED", index, result["system"], flush=True)
    record = {
        "protocol_sha256": sha(ROOT / "research/eta2_wave6/D18_GEOMETRIC_PRIOR_PROTOCOL.md"),
        "amendment_sha256": sha(ROOT / "research/eta2_wave6/D18_CAPTURE_RADIUS_AMENDMENT.md"),
        "build_manifest_sha256": sha(HERE / "build-manifest.json"),
        "capture_manifest_sha256": sha(HERE / "capture-manifest.json"),
        "binary_sha256": sha(BUILD), "cases": results,
    }
    (HERE / "fixed-run-manifest.json").write_text(json.dumps(record, indent=2) + "\n")


if __name__ == "__main__":
    main()
