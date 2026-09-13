#!/usr/bin/env python3
"""Rebuild frozen Eta2 fixed systems at the three archived Final3068 states."""
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

import numpy as np
from scipy.spatial.transform import Rotation

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
WAVE = ROOT / "research/eta2_wave6"
ARCHIVE = ROOT / "research/eta2_research_20260912/evidence/collect"
BAL = pathlib.Path("/workspace/bal/final-3068.txt")
OUT = pathlib.Path("/workspace/prism-wave6-d15")
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


BAL_IO = load_module("d15_bal_io", WAVE / "bal_perturb.py")
AUDIT = load_module(
    "d15_capture_io",
    ROOT / "research/eta2_research_20260912/analysis/audit_capture.py",
)


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
    assert dims["ncam"] == problem.ncam and dims["npt"] == problem.npt
    # The native state stores rotation matrices.  Conversion through the
    # principal rotation vector reproduces the same SO(3) element; the score
    # check below catches any convention or branch mismatch.
    cameras = np.empty((problem.ncam, 9), dtype=np.float64)
    cameras[:, :3] = Rotation.from_matrix(np.asarray(camera.R)).as_rotvec()
    cameras[:, 3:6] = camera.t
    cameras[:, 6:9] = camera.intrinsics
    cameras[:, 8] = 0.0
    BAL_IO.write_state(problem, destination, cameras, np.asarray(points))
    return {"temporary_bal_sha256": sha(destination), "temporary_bal_bytes": destination.stat().st_size}


def main() -> None:
    assert sha(CAPTURE) == CAPTURE_SHA256
    protocol = ROOT / "research/eta2_wave6/D15_COUNT_PRIOR_PROTOCOL.md"
    champ = json.loads((ROOT / "research/eta2_champion/champion.json").read_text())
    base_env = {k: v for k, v in os.environ.items()
                if not k.startswith(("OCA_", "CASPAR_", "COLMAP_MFREE", "MF_DEBUG"))}
    base_env.update(champ["flags"])
    OUT.mkdir(parents=True, exist_ok=True)
    runs = {}
    with open("/tmp/prism_gpu.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        for rep in (0, 5, 6):
            source = ARCHIVE / f"final-3068-capture-{rep}"
            meta = read_metadata(source / "metadata.txt")
            tmp = pathlib.Path(f"/dev/shm/d15-final-3068-{rep}.txt")
            reconstruction = make_bal(source, tmp)
            dest = OUT / f"final-3068-{rep}"
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
                subprocess.run(command, env=env, stdout=stream, stderr=subprocess.STDOUT,
                               check=True, timeout=180)
            text = log.read_text()
            match = re.search(r"FIXED_CAPTURE outer=0 cost=([^ ]+) tau=([^ ]+) lambda=([^ ]+) eta=([^\n]+)", text)
            if not match:
                raise RuntimeError(f"capture marker missing for rep {rep}")
            captured_cost, tau, lam, eta = map(float, match.groups())
            relative_cost_error = abs(captured_cost - meta["cost"]) / max(1.0, abs(meta["cost"]))
            if relative_cost_error > 1e-8:
                raise RuntimeError(("state reconstruction score mismatch", rep, captured_cost, meta["cost"]))
            files = {}
            for path in sorted(dest.iterdir()):
                if path.is_file():
                    files[path.name] = {"bytes": path.stat().st_size, "sha256": sha(path)}
            run = {
                "rep": rep,
                "archived_capture": str(source),
                "archived_metadata_sha256": sha(source / "metadata.txt"),
                "archived_state_files": {
                    name: sha(source / name)
                    for name in ("R_state.f64", "t_state.f64", "X_state.f64", "intr_state.f64")
                },
                "archived_cost": meta["cost"],
                "archived_radius": meta["radius"],
                "archived_lambda": meta["lambda"],
                "captured_cost": captured_cost,
                "relative_cost_error": relative_cost_error,
                "captured_tau": tau,
                "captured_lambda": lam,
                "captured_eta": eta,
                "command": command,
                "flags": {k: v for k, v in env.items() if k.startswith("OCA_")},
                "reconstruction": reconstruction,
                "files": files,
            }
            (dest / "capture_manifest.json").write_text(json.dumps(run, indent=2) + "\n")
            runs[str(rep)] = run
            tmp.unlink()
            print("D15_CAPTURE", rep, "cost_error", relative_cost_error,
                  "lambda", lam, "bytes", sum(v["bytes"] for v in files.values()), flush=True)
    manifest = {
        "protocol_sha256": sha(protocol),
        "capture_binary": str(CAPTURE),
        "capture_binary_sha256": sha(CAPTURE),
        "frozen_champion_sha256": sha(ROOT / "research/eta2_champion/champion.json"),
        "input": str(BAL),
        "input_sha256": sha(BAL),
        "runs": runs,
    }
    HERE.mkdir(parents=True, exist_ok=True)
    (HERE / "capture-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({k: {"cost_error": v["relative_cost_error"],
                          "lambda": v["captured_lambda"]} for k, v in runs.items()}, indent=2))


if __name__ == "__main__":
    main()
