#!/usr/bin/env python3
"""Build an opt-in GMRES(8) overlay on the checksum-pinned Eta2 source."""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import subprocess

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FROZEN = ROOT / "research" / "eta2_champion"
BUILD = pathlib.Path("/tmp/prism-wave6-d13-native")


def sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def derive() -> tuple[str, int]:
    original = (FROZEN / "source" / "prism_eta2.cu").read_text()
    assert hashlib.sha256(original.encode()).hexdigest() == (
        "22c18359a526526ae0a5b5109187878ab1cef33b453f6bbddc2aa92597a607d8"
    )
    source = original
    changes: list[tuple[str, str]] = []

    def patch(before: str, after: str) -> None:
        nonlocal source
        assert source.count(before) == 1, (before[:120], source.count(before))
        source = source.replace(before, after)
        changes.append((before, after))

    patch(
        '#include "selective_reuse.h"',
        '#include "selective_reuse.h"\n#include "gmres_camera.cuh"',
    )
    patch(
        '''  std::unique_ptr<PrismPcg> pcg;
  if(getenv("OCA_PCG"))pcg=std::make_unique<PrismPcg>(ncam);''',
        '''  std::unique_ptr<PrismPcg> pcg;
  if(getenv("OCA_PCG"))pcg=std::make_unique<PrismPcg>(ncam);
  const int d13_gmres_m=[](){const char* e=getenv("OCA_PCG_GMRES");return e?std::atoi(e):0;}();
  if(d13_gmres_m<0 || d13_gmres_m>16)
    throw std::runtime_error("OCA_PCG_GMRES must be in 1..16, or zero/off");
  std::unique_ptr<PrismD13GmresWorkspace> d13_gmres;
  if(d13_gmres_m)d13_gmres=std::make_unique<PrismD13GmresWorkspace>(n_c,d13_gmres_m);
  long d13_gmres_solves=0,d13_gmres_iterations=0,d13_gmres_products=0;''',
    )
    patch(
        '''    if(cg_projection){cg_projection->Reset();legacy_tr->Reset();}
    if(rld.collect)rld.ResetCG();
    for(cg_it=0; cg_it<maxck; ++cg_it){''',
        '''    if(cg_projection){cg_projection->Reset();legacy_tr->Reset();}
    if(rld.collect)rld.ResetCG();
    if(d13_gmres){
#include "gmres_native.inc"
    } else
    for(cg_it=0; cg_it<maxck; ++cg_it){''',
    )
    patch(
        '''  if(numeric_guard)std::printf("NUMERIC_REPAIR summary rebuilds=%ld floor=%.17g\\n",numeric_rebuilds,numeric_floor);''',
        '''  if(d13_gmres)std::printf("D13_GMRES summary solves=%ld iterations=%ld products=%ld basis_vectors=%d\\n",
    d13_gmres_solves,d13_gmres_iterations,d13_gmres_products,d13_gmres_m+1);
  if(numeric_guard)std::printf("NUMERIC_REPAIR summary rebuilds=%ld floor=%.17g\\n",numeric_rebuilds,numeric_floor);''',
    )

    restored = source
    for before, after in reversed(changes):
        assert restored.count(after) == 1
        restored = restored.replace(after, before)
    assert restored == original
    return source, len(changes)


def main() -> None:
    subprocess.run(["python3", str(FROZEN / "build.py"), "--check-only"], check=True)
    BUILD.mkdir(parents=True, exist_ok=True)
    source_path = BUILD / "d13_gmres.cu"
    binary = BUILD / "prism-d13-gmres"
    source, patch_count = derive()
    source_path.write_text(source)
    command = [
        "nvcc", "-O3", "-DNDEBUG", "-std=c++17", "-arch=sm_89",
        "-I/usr/include/eigen3",
        "-I" + str(FROZEN / "source" / "headers"),
        "-I" + str(HERE),
        str(source_path), "-o", str(binary), "-lcublas", "-lcusolver",
    ]
    with (BUILD / "build.log").open("w") as log:
        subprocess.run(command, env=dict(os.environ, TMPDIR="/dev/shm"),
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    manifest = {
        "command": command,
        "source_sha256": sha(source_path),
        "binary": str(binary),
        "binary_sha256": sha(binary),
        "frozen_source_sha256": sha(FROZEN / "source" / "prism_eta2.cu"),
        "champion_sha256": sha(FROZEN / "champion.json"),
        "reversible_patch_count": patch_count,
        "sources": {
            str(HERE / "build_native.py"): sha(HERE / "build_native.py"),
            str(HERE / "gmres_camera.cuh"): sha(HERE / "gmres_camera.cuh"),
            str(HERE / "gmres_native.inc"): sha(HERE / "gmres_native.inc"),
        },
        "protocol_sha256": sha(ROOT / "research" / "eta2_wave6" /
                               "D13_KRYLOV_RESTART_PROTOCOL.md"),
    }
    evidence = HERE / "evidence"
    evidence.mkdir(exist_ok=True)
    (evidence / "native_build_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
