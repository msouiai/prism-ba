#!/usr/bin/env python3
"""Fresh N=10 settling cohort for rho_min=1e-3."""
from pathlib import Path
import json, statistics, subprocess

import native_light as N

P = Path(__file__).resolve().parent
W4 = P.parent / "eta2_wave4"
BINARY = W4 / "build" / "prism-aside"
ARMS = {"off": {}, "rho001": {"OCA_W4_RHO_MIN": "0.001"}}


def register():
    subprocess.run(["python3", str(N.FROZEN / "build.py"), "--check-only"], check=True)
    build = json.loads((W4 / "aside_build_manifest.json").read_text())
    assert N.sha(BINARY) == build["binary_sha256"]
    assert all(N.sha(path) == digest for path, digest in build["sources"].items())
    old = json.loads((W4 / "aside-registration.json").read_text())
    reg = {
        "arms": ARMS, "cells": {k: old["cells"][k] for k in ("venice-52", "final-3068")},
        "repetitions": 10, "binary": str(BINARY), "binary_sha256": N.sha(BINARY),
        "build_manifest": build, "protocol_sha256": N.sha(P / "A2_A4_PROTOCOL.md"),
        "cohort_rule": "Fresh rows only; alternate arm order and reverse scene order on odd repetitions",
    }
    path = P / "a4-registration.json"
    if path.exists():
        assert json.loads(path.read_text()) == reg
    else:
        N.write(path, reg)
    return reg


def summarize(rows):
    groups = []
    for scene in ("venice-52", "final-3068"):
        for arm in ARMS:
            g = [r for r in rows if r["scene"] == scene and r["arm"] == arm]
            hit_times = [r["target_seconds"] for r in g if r["hit"]]
            groups.append({
                "scene": scene, "arm": arm, "n": len(g),
                "hits": sum(r["hit"] for r in g),
                "median_endpoint": statistics.median(r["cost"] for r in g),
                "endpoint_range": [min(r["cost"] for r in g), max(r["cost"] for r in g)],
                "conditional_median_target_seconds": statistics.median(hit_times) if hit_times else None,
                "target_seconds_range": [min(hit_times), max(hit_times)] if hit_times else None,
                "median_native_seconds": statistics.median(r["native_seconds"] for r in g),
                "median_rejects": statistics.median(r["rejects"] for r in g),
                "median_matvecs": statistics.median(r["matvecs"] for r in g),
                "ftol_stops": sum(r["stop_ftol"] for r in g),
            })
    result = {
        "rows": len(rows), "groups": groups,
        "adoption_rule": "Adopt only if rho001 is not worse than off in the fresh N=10 tails; wave-4 practical N=3 remains separate support.",
    }
    N.write(P / "a4-summary.json", result)
    return result


def main():
    reg = register()
    rows = []
    for rep in range(reg["repetitions"]):
        scenes = list(reg["cells"])
        arms = list(ARMS)
        if rep % 2:
            scenes.reverse(); arms.reverse()
        for scene in scenes:
            for arm in arms:
                folder = P / "evidence" / "a4" / f"{scene}-{arm}-{rep}"
                rows.append(N.run(folder, reg["cells"][scene], arm, rep, BINARY,
                                  ARMS[arm], P / "A2_A4_PROTOCOL.md", reg["build_manifest"]))
                N.write(P / "a4-results.json", rows)
    print(json.dumps(summarize(rows), indent=2), flush=True)


if __name__ == "__main__":
    main()
