#!/usr/bin/env python3
"""Build checksum-pinned D18 fixed-system geometric-prior harness."""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import subprocess

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PKG = ROOT / "research/eta2_champion"
OUT = pathlib.Path("/tmp/prism-wave6-d18-build")
OUT.mkdir(parents=True, exist_ok=True)


def sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


source = (PKG / "source/prism_eta2.cu").read_text()
assert hashlib.sha256(source.encode()).hexdigest() == "22c18359a526526ae0a5b5109187878ab1cef33b453f6bbddc2aa92597a607d8"
manifest = json.loads((PKG / "source_manifest.json").read_text())
assert all(sha(PKG / "source/headers" / name) == digest
           for name, digest in manifest["headers_sha256"].items())
parts = []
for start, end in [
    ("__device__ __forceinline__ void MFVinv(", "// GAP-4090 F2"),
    ("__global__ void MFVinvApply(", "// Map camera traversal"),
    ("template <int CD, class HT>\n__global__ void MFPass2(", "__global__ void MFBackSub"),
    ("template <int CD, typename HT>\n__global__ void MFBlockSchur(", '#include "pcg_camera.cuh"'),
]:
    begin = source.index(start)
    finish = source.index(end, begin)
    parts.append(source[begin:finish])
(OUT / "reference.cuh").write_text("\n".join(parts))
binary = OUT / "geometric_prior_fixed"
command = [
    "nvcc", "-O3", "-DNDEBUG", "-std=c++17", "-arch=sm_89",
    "-I/usr/include/eigen3", f"-I{OUT}", str(HERE / "geometric_prior_fixed.cu"),
    "-o", str(binary), "-lcublas",
]
with (OUT / "build.log").open("w") as log:
    subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True,
                   env={**os.environ, "TMPDIR": "/dev/shm"})
record = {
    "command": command,
    "frozen_source_sha256": hashlib.sha256(source.encode()).hexdigest(),
    "reference_sha256": sha(OUT / "reference.cuh"),
    "source_sha256": sha(HERE / "geometric_prior_fixed.cu"),
    "binary_sha256": sha(binary),
    "protocol_sha256": sha(ROOT / "research/eta2_wave6/D18_GEOMETRIC_PRIOR_PROTOCOL.md"),
}
(HERE / "build-manifest.json").write_text(json.dumps(record, indent=2) + "\n")
print(json.dumps(record, indent=2))
