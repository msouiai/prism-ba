#!/usr/bin/env python3
"""Registered D13b periodic-PCG-restart native evaluation."""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess

import run_native as G

N = G.N
HERE = pathlib.Path(__file__).resolve().parent
WAVE6 = HERE.parent
WAVE5 = G.WAVE5
BINARY = pathlib.Path("/tmp/prism-wave6-d13b-native/prism-d13b-restart")
PARENT = pathlib.Path(N.CHAMPION["binary"])
PROTOCOL = WAVE6 / "D13B_PERIODIC_PCG_PROTOCOL.md"
BUILD_MANIFEST = HERE / "evidence" / "restart_native_build_manifest.json"
ARMS = {
    "control": {},
    "restart8": {
        "OCA_PCG_RESTART_DEPTH": "8",
        "OCA_PCG_RESTART_PERIODIC": "1",
    },
}


def register() -> dict:
    subprocess.run(["python3", str(N.FROZEN / "build.py"), "--check-only"], check=True)
    build = json.loads(BUILD_MANIFEST.read_text())
    assert N.sha(BINARY) == build["binary_sha256"]
    assert all(N.sha(path) == digest for path, digest in build["sources"].items())
    base = json.loads((WAVE5 / "b1-registration.json").read_text())
    reg = {
        "arms": ARMS,
        "practical": base["practical"],
        "tails": base["tails"],
        "muell": base["muell"],
        "final1936": {
            "scene": "final-1936",
            "cell": "final-1936",
            "path": "/workspace/bal/final-1936.txt",
            "input_sha256": N.sha("/workspace/bal/final-1936.txt"),
            "target": 5125687.352261469,
            "cap": 12,
        },
        "panel_repetitions": 3,
        "control_repetitions": 3,
        "tail_repetitions": 5,
        "binary": str(BINARY),
        "binary_sha256": N.sha(BINARY),
        "parent_binary": str(PARENT),
        "parent_binary_sha256": N.sha(PARENT),
        "build_manifest": build,
        "protocol_sha256": N.sha(PROTOCOL),
        "cohort_rule": "Fresh paired rows; alternate arms and reverse cells on odd repetitions",
        "registered_arm": "periodic exact residual replacement and valid Hcc-PCG restart every eight iterations",
    }
    path = WAVE6 / "d13b-native-registration.json"
    if path.exists():
        assert json.loads(path.read_text()) == reg
    else:
        N.write(path, reg)
    return reg


def configure_shared_runner() -> None:
    G.BINARY = BINARY
    G.PARENT = PARENT
    G.PROTOCOL = PROTOCOL
    G.ARMS = ARMS


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["compatibility", "panel", "controls", "tails"])
    args = parser.parse_args()
    reg = register()
    configure_shared_runner()
    calm = next(cell for cell in reg["practical"] if cell["cell"] == "ladybug-539-1.01")
    if args.stage == "compatibility":
        rows = G.execute(reg, "d13b-compatibility", [calm], ["control", "parent"], 3)
        summary = G.summarize(rows, ("parent", "control"))
        summary["passed"] = abs(summary["cells"][0]["endpoint_delta"]) < 0.0015
        N.write(WAVE6 / "d13b-compatibility-summary.json", summary)
        assert summary["passed"], summary
    elif args.stage == "panel":
        assert json.loads((WAVE6 / "d13b-compatibility-summary.json").read_text())["passed"]
        rows = G.execute(reg, "d13b-panel", reg["practical"], list(ARMS), 3)
        summary = G.summarize(rows, tuple(ARMS))
        N.write(WAVE6 / "d13b-panel-summary.json", summary)
    elif args.stage == "controls":
        rows = G.execute(reg, "d13b-controls", [reg["muell"], reg["final1936"]], list(ARMS), 3)
        summary = G.summarize(rows, tuple(ARMS))
        N.write(WAVE6 / "d13b-controls-summary.json", summary)
    else:
        rows = G.execute(reg, "d13b-tails", list(reg["tails"].values()), list(ARMS), 5)
        summary = G.summarize(rows, tuple(ARMS))
        N.write(WAVE6 / "d13b-tails-summary.json", summary)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
