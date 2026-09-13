#!/usr/bin/env python3
"""Build the checksum-pinned D14 fixed-system harness."""
from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FROZEN = ROOT / "research" / "eta2_champion"
OUT = pathlib.Path("/tmp/prism-wave6-d14")


def sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    subprocess.run(["python3", str(FROZEN / "build.py"), "--check-only"], check=True)
    subprocess.run(["python3", str(HERE / "test_math.py")], check=True)
    OUT.mkdir(parents=True, exist_ok=True)
    source = (FROZEN / "source" / "prism_eta2.cu").read_text()
    assert hashlib.sha256(source.encode()).hexdigest() == "22c18359a526526ae0a5b5109187878ab1cef33b453f6bbddc2aa92597a607d8"
    parts = []
    for start, end in [
        ("__device__ __forceinline__ void MFVinv(", "// GAP-4090 F2"),
        ("__global__ void MFVinvApply(", "// Map camera traversal"),
        ("template <int CD, class HT>\n__global__ void MFPass2(", "__global__ void MFBackSub"),
    ]:
        a = source.index(start)
        b = source.index(end, a)
        parts.append(source[a:b])
    reference = OUT / "reference.cuh"
    reference.write_text("\n".join(parts))
    binary = OUT / "ca_fixed"
    command = [
        "nvcc", "-O3", "-DNDEBUG", "-std=c++17", "-arch=sm_89",
        "-I/usr/include/eigen3", f"-I{OUT}", str(HERE / "ca_fixed.cu"),
        "-o", str(binary), "-lcublas",
    ]
    with (OUT / "build.log").open("w") as log:
        subprocess.run(command, env={**__import__("os").environ, "TMPDIR": "/dev/shm"},
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    record = {
        "command": command,
        "source_sha256": sha(HERE / "ca_fixed.cu"),
        "math_test_sha256": sha(HERE / "test_math.py"),
        "reference_sha256": sha(reference),
        "binary": str(binary),
        "binary_sha256": sha(binary),
        "frozen_source_sha256": sha(FROZEN / "source" / "prism_eta2.cu"),
        "protocol_sha256": sha(ROOT / "research" / "eta2_wave6" / "D14_CA_PCG_PROTOCOL.md"),
    }
    (HERE / "build-manifest.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
