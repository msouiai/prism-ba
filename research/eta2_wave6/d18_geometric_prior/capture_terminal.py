#!/usr/bin/env python3
"""Capture fixed Eta2 systems at five archived Venice terminal states."""
from __future__ import annotations

import fcntl
import hashlib
import importlib.util
import json
import os
import pathlib
import re
import shutil
import subprocess
import tarfile
import tempfile

import numpy as np
from scipy.spatial.transform import Rotation

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
WAVE6 = ROOT / "research/eta2_wave6"
WAVE3 = ROOT / "research/eta2_wave3"
BAL = pathlib.Path("/workspace/bal/venice-52.txt")
OUT = pathlib.Path("/workspace/prism-wave6-d18")
CAPTURE = pathlib.Path("/tmp/prism-ba-schur/research/schur_preconditioner/build/capture")
CAPTURE_SHA256 = "f3fef8771e103afc8058858cba8b7c5edd4f7db9bd3f95934fd63055aa40a362"


def sha(path: pathlib.Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load_module(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


BAL_IO = load_module("d18_bal_io", WAVE6 / "bal_perturb.py")
AUDIT = load_module("d18_capture_io", ROOT / "research/eta2_research_20260912/analysis/audit_capture.py")


def read_metadata(path: pathlib.Path) -> dict[str, float]:
    out = {}
    for line in path.read_text().splitlines():
        if line.strip():
            key, value = line.split("=", 1)
            out[key] = float(value)
    return out


def make_bal(source: pathlib.Path, destination: pathlib.Path) -> dict:
    problem = BAL_IO.load_bal(BAL)
    camera, points, dims = AUDIT.load_capture_state(source)
    assert (dims["ncam"], dims["npt"]) == (problem.ncam, problem.npt)
    cameras = np.empty((problem.ncam, 9), dtype=np.float64)
    cameras[:, :3] = Rotation.from_matrix(np.asarray(camera.R)).as_rotvec()
    cameras[:, 3:6] = camera.t
    cameras[:, 6:9] = camera.intrinsics
    cameras[:, 8] = 0.0
    BAL_IO.write_state(problem, destination, cameras, np.asarray(points))
    return {"temporary_bal_sha256": sha(destination),
            "temporary_bal_bytes": destination.stat().st_size}


def main() -> None:
    assert sha(CAPTURE) == CAPTURE_SHA256
    champ_path = ROOT / "research/eta2_champion/champion.json"
    champ = json.loads(champ_path.read_text())
    base_env = {k: v for k, v in os.environ.items()
                if not k.startswith(("OCA_", "CASPAR_", "COLMAP_MFREE", "MF_DEBUG"))}
    base_env.update(champ["flags"])
    OUT.mkdir(parents=True, exist_ok=True)
    runs = {}
    with open("/tmp/prism_gpu.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        for index in range(5):
            forensic_path = WAVE3 / f"forensics/venice-terminal-{index}.json"
            forensic = json.loads(forensic_path.read_text())
            record = forensic["archive_source"]
            archive = pathlib.Path(record["path"])
            assert sha(archive) == record["sha256"]
            with tempfile.TemporaryDirectory(prefix="d18-state-", dir="/dev/shm") as td:
                root = pathlib.Path(td)
                with tarfile.open(archive) as handle:
                    handle.extractall(root, filter="data")
                source = root / "0"
                for name, digest in record["member_sha256"].items():
                    assert sha(root / name) == digest
                meta = read_metadata(source / "metadata.txt")
                tmp = pathlib.Path(f"/dev/shm/d18-venice-{index}.txt")
                reconstruction = make_bal(source, tmp)
                dest = OUT / f"venice-terminal-{index}"
                if dest.exists():
                    shutil.rmtree(dest)
                dest.mkdir()
                cli = list(champ["cli"])
                cli[cli.index("--lam0") + 1] = format(meta["lambda"], ".17g")
                cli[cli.index("--max_iter") + 1] = "1"
                command = [str(CAPTURE), "--problem", str(tmp), *cli]
                env = base_env | {
                    "OCA_CG_CAPTURE": str(dest),
                    "OCA_CG_CAPTURE_OUTER": "0",
                    "OCA_MAX_SECONDS": "60",
                }
                log = dest / "capture.log"
                with log.open("w") as stream:
                    subprocess.run(command, env=env, stdout=stream,
                                   stderr=subprocess.STDOUT, check=True, timeout=180)
                match = re.search(
                    r"FIXED_CAPTURE outer=0 cost=([^ ]+) tau=([^ ]+) lambda=([^ ]+) eta=([^\n]+)",
                    log.read_text())
                if not match:
                    raise RuntimeError(f"capture marker missing for {index}")
                captured_cost, tau, lam, eta = map(float, match.groups())
                cost_error = abs(captured_cost - meta["cost"]) / max(1.0, abs(meta["cost"]))
                if cost_error > 1e-8:
                    raise RuntimeError(("state score mismatch", index, captured_cost, meta["cost"]))
                shutil.copyfile(source / "eta2_raw_scaled.f64", dest / "eta2_raw_scaled.f64")
                (dest / "registered_radius.txt").write_text(format(meta["radius"], ".17g") + "\n")
                files = {path.name: {"bytes": path.stat().st_size, "sha256": sha(path)}
                         for path in sorted(dest.iterdir()) if path.is_file()}
                run = {
                    "index": index,
                    "forensic": str(forensic_path), "forensic_sha256": sha(forensic_path),
                    "archive": str(archive), "archive_sha256": sha(archive),
                    "archived_cost": meta["cost"], "archived_radius": meta["radius"],
                    "archived_lambda": meta["lambda"], "captured_cost": captured_cost,
                    "relative_cost_error": cost_error, "captured_tau": tau,
                    "captured_lambda": lam, "captured_eta": eta,
                    "command": command,
                    "flags": {k: v for k, v in env.items() if k.startswith("OCA_")},
                    "reconstruction": reconstruction, "files": files,
                }
                (dest / "capture_manifest.json").write_text(json.dumps(run, indent=2) + "\n")
                runs[str(index)] = run
                tmp.unlink(missing_ok=True)
                print("D18_CAPTURE", index, "cost_error", cost_error,
                      "lambda", lam, "bytes", sum(x["bytes"] for x in files.values()),
                      flush=True)
    manifest = {
        "protocol_sha256": sha(WAVE6 / "D18_GEOMETRIC_PRIOR_PROTOCOL.md"),
        "amendment_sha256": sha(WAVE6 / "D18_CAPTURE_RADIUS_AMENDMENT.md"),
        "capture_binary": str(CAPTURE), "capture_binary_sha256": sha(CAPTURE),
        "frozen_champion_sha256": sha(champ_path),
        "input": str(BAL), "input_sha256": sha(BAL), "runs": runs,
    }
    (HERE / "capture-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
