#!/usr/bin/env python3
"""Build the D2c deterministic binary with FP64 stored Jacobian fragments."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess


P = Path(__file__).resolve().parent
FROZEN = P.parent / "eta2_champion"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_base_builder():
    spec = importlib.util.spec_from_file_location("w6_build_deterministic", P / "build_deterministic.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def derive():
    source, inherited = load_base_builder().derive()
    replacements = {
        '#include "point_prep_candidate.cuh"': '#include "point_prep_generic.cuh"',
        '#include "pcg_camera.cuh"': '#include "pcg_camera_generic.cuh"',
        "using Fragment = float;": "using Fragment = double;",
        "MIXED_STORAGE fragments=fp32 arithmetic=fp64 state=fp64 acceptance=fp64":
            "MIXED_STORAGE fragments=fp64 arithmetic=fp64 state=fp64 acceptance=fp64",
        "storage=fp32 camera_reads=%s": "storage=fp64 camera_reads=%s",
        "MFRhsDiagFused<<<GridSize(nobs),256>>>(mf_fp32?Gp32:Gp,fragment_cams,fragment_points,Rf,uu,nobs,corr,dk);":
            "if(mf_fp32) MFRhsDiagFused<float><<<GridSize(nobs),256>>>(Gp32,fragment_cams,fragment_points,Rf,uu,nobs,corr,dk); else MFRhsDiagFused<Fragment><<<GridSize(nobs),256>>>(Gp,fragment_cams,fragment_points,Rf,uu,nobs,corr,dk);",
    }
    for before, after in replacements.items():
        if source.count(before) != 1:
            raise RuntimeError((before, source.count(before)))
        source = source.replace(before, after)
    return source, inherited + len(replacements)


def main():
    subprocess.run(["python3", str(FROZEN / "build.py"), "--check-only"], check=True)
    build = P / "build"
    build.mkdir(exist_ok=True)
    source_path = build / "deterministic_fp64_fragments.cu"
    binary = build / "prism-deterministic-fp64-fragments"
    source, patch_count = derive()
    source_path.write_text(source)
    command = ["nvcc", "-O3", "-DNDEBUG", "-std=c++17", "-arch=sm_89",
               "-I/usr/include/eigen3", "-I" + str(P),
               "-I" + str(FROZEN / "source" / "headers"),
               "-I" + str(P.parent / "eta2_wave5"),
               str(source_path), "-o", str(binary), "-lcublas", "-lcusolver"]
    with (build / "deterministic-fp64-build.log").open("w") as log:
        subprocess.run(command, env=dict(os.environ, TMPDIR="/dev/shm"),
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    manifest = {
        "command": command,
        "source_sha256": sha(source_path),
        "binary_sha256": sha(binary),
        "reversible_patch_count": patch_count,
        "base_builder_sha256": sha(P / "build_deterministic.py"),
        "builder_sha256": sha(__file__),
        "protocol_sha256": sha(P / "D2C_PROTOCOL.md"),
        "champion_sha256": sha(FROZEN / "champion.json"),
        "only_semantic_delta": "stored Fragment typedef float -> double; diagnostic labels updated",
    }
    (P / "d2c-build-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("BUILT", binary, manifest["binary_sha256"])


if __name__ == "__main__":
    main()
