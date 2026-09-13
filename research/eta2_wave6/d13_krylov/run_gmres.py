#!/usr/bin/env python3
"""Run the registered low-memory GMRES(8) mechanism control."""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import pathlib
import subprocess
import time

HERE = pathlib.Path(__file__).resolve().parent
BINARY = pathlib.Path("/tmp/prism-wave6-d13-build/restart_fixed")
CAPTURES = pathlib.Path("/workspace/prism-schur-physics")
OUT = HERE / "evidence"
OUT.mkdir(exist_ok=True)
SCENES = {
    "muell-o11": CAPTURES / "muell-gba146-o11",
    "muell-o12": CAPTURES / "muell-gba146-o12",
    "ladybug-o8": CAPTURES / "ladybug-598-o8",
    "final-o0": CAPTURES / "final-1936-o0",
}

rows = {}
with open("/tmp/prism_gpu.lock", "w") as lock:
    fcntl.flock(lock, fcntl.LOCK_EX)
    for scene, capture in SCENES.items():
        log = OUT / f"{scene}-gmres8.log"
        env = os.environ.copy()
        env["D13_GMRES"] = "8"
        start = time.perf_counter()
        with log.open("w") as stream:
            subprocess.run(
                [str(BINARY), str(capture)],
                env=env,
                stdout=stream,
                stderr=subprocess.STDOUT,
                check=True,
                timeout=600,
            )
        rows[scene] = {
            "wall_seconds": time.perf_counter() - start,
            "log_sha256": hashlib.sha256(log.read_bytes()).hexdigest(),
            "capture_manifest_sha256": (
                hashlib.sha256((capture / "capture_manifest.json").read_bytes()).hexdigest()
                if (capture / "capture_manifest.json").exists()
                else None
            ),
        }

manifest = {
    "binary_sha256": hashlib.sha256(BINARY.read_bytes()).hexdigest(),
    "basis_vectors": 9,
    "stored_preconditioned_vectors": 0,
    "rows": rows,
}
(OUT / "gmres_run_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
print(json.dumps(manifest, indent=2))
