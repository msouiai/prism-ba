#!/usr/bin/env python3
"""Build occupancy-gated deterministic preparation on top of B6v6."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess

P = Path(__file__).resolve().parent
F = P.parent / "eta2_champion"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_b6v6():
    spec = importlib.util.spec_from_file_location("build_b6v6", P / "build_b6v6.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def derive():
    base = load_b6v6()
    source, count = base.derive()
    intermediate = source
    changes = []

    def patch(before, after):
        nonlocal source
        assert source.count(before) == 1, (before[:120], source.count(before))
        source = source.replace(before, after)
        changes.append((before, after))

    patch(
        '''  const bool w5_prep_fuse=[](){const char* e=getenv("OCA_W5_PREP_FUSE");return e&&std::atoi(e)!=0;}();
  const bool w5_prep_camera=[](){const char* e=getenv("OCA_W5_PREP_CAMERA");return e&&std::atoi(e)!=0;}();
  long w5_prep_calls=0;
  if(w5_prep_camera && !w5_prep_fuse)
    throw std::runtime_error("B6v6 camera RHS requires B6v4 preparation fusion");
  if(w5_prep_fuse){''',
        '''  const bool w5_prep_requested=[](){const char* e=getenv("OCA_W5_PREP_FUSE");return e&&std::atoi(e)!=0;}();
  const bool w5_camera_requested=[](){const char* e=getenv("OCA_W5_PREP_CAMERA");return e&&std::atoi(e)!=0;}();
  const int w5_prep_min_cams=[](){const char* e=getenv("OCA_W5_PREP_MIN_CAMS");return e?std::max(0,std::atoi(e)):0;}();
  const bool w5_prep_fuse=w5_prep_requested && ncam>=w5_prep_min_cams;
  const bool w5_prep_camera=w5_camera_requested && w5_prep_fuse;
  long w5_prep_calls=0;
  if(w5_camera_requested && !w5_prep_requested)
    throw std::runtime_error("B6v7 camera RHS requires preparation fusion");
  if(w5_prep_requested && !w5_prep_fuse)
    std::printf("W5_PREP_FUSE gated_off ncam=%d min_cams=%d\\n",ncam,w5_prep_min_cams);
  if(w5_prep_fuse){''',
    )
    patch(
        '''    std::printf("W5_PREP_FUSE active ncam=%d npt=%d nobs=%d camera_rhs=%d\\n",ncam,npt,nobs,(int)w5_prep_camera);''',
        '''    std::printf("W5_PREP_FUSE active ncam=%d npt=%d nobs=%d camera_rhs=%d min_cams=%d\\n",ncam,npt,nobs,(int)w5_prep_camera,w5_prep_min_cams);''',
    )

    restored = source
    for before, after in reversed(changes):
        assert restored.count(after) == 1
        restored = restored.replace(after, before)
    assert restored == intermediate
    return source, count + len(changes)


def main():
    subprocess.run(["python3", str(F / "build.py"), "--check-only"], check=True)
    build = P / "build"
    build.mkdir(exist_ok=True)
    src = build / "b6v7.cu"
    binary = build / "prism-b6v7"
    source, count = derive()
    src.write_text(source)
    cmd = ["nvcc", "-O3", "-DNDEBUG", "-std=c++17", "-arch=sm_89",
           "-I/usr/include/eigen3", "-I" + str(F / "source" / "headers"),
           "-I" + str(P), str(src), "-o", str(binary), "-lcublas", "-lcusolver"]
    with (build / "b6v7-build.log").open("w") as log:
        subprocess.run(cmd, env=dict(os.environ, TMPDIR="/dev/shm"), stdout=log,
                       stderr=subprocess.STDOUT, check=True)
    manifest = {
        "command": cmd,
        "source_sha256": sha(src),
        "binary_sha256": sha(binary),
        "frozen_source_sha256": sha(F / "source" / "prism_eta2.cu"),
        "champion_sha256": sha(F / "champion.json"),
        "reversible_patch_count": count,
        "sources": {
            str(P / "build_b6v7.py"): sha(P / "build_b6v7.py"),
            str(P / "build_b6v6.py"): sha(P / "build_b6v6.py"),
            str(P / "build_b6v4.py"): sha(P / "build_b6v4.py"),
            str(P / "build_b6v2.py"): sha(P / "build_b6v2.py"),
            str(P / "prep_latency.cuh"): sha(P / "prep_latency.cuh"),
        },
        "protocol_sha256": sha(P / "B6V7_PROTOCOL.md"),
    }
    (P / "b6v7-build-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("BUILT B6V7", manifest["binary_sha256"])


if __name__ == "__main__":
    main()
