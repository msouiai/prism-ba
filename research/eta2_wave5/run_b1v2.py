#!/usr/bin/env python3
"""Registered B1 version-2 contraction measurements."""
from pathlib import Path
import argparse
import json
import re
import statistics
import subprocess

import native_light as N
import run_b1 as B

P = Path(__file__).resolve().parent
BINARY = P / "build" / "prism-b1v2"
PARENT = Path(N.CHAMPION["binary"])
PROTOCOL = P / "B1V2_PROTOCOL.md"
ARMS = {"off": {}, "factored": {"OCA_W5_FACTORED_J": "1"}}


def register():
    subprocess.run(["python3", str(N.FROZEN / "build.py"), "--check-only"], check=True)
    build = json.loads((P / "b1v2-build-manifest.json").read_text())
    assert N.sha(BINARY) == build["binary_sha256"]
    assert all(N.sha(path) == digest for path, digest in build["sources"].items())
    old = json.loads((P / "b1-registration.json").read_text())
    reg = {
        "arms": ARMS, "audit": old["audit"], "practical": old["practical"],
        "tails": old["tails"], "muell": old["muell"],
        "panel_repetitions": 3, "tail_repetitions": 5,
        "binary": str(BINARY), "binary_sha256": N.sha(BINARY),
        "parent_binary": str(PARENT), "parent_binary_sha256": N.sha(PARENT),
        "build_manifest": build, "protocol_sha256": N.sha(PROTOCOL),
        "cohort_rule": "Fresh paired rows; alternating arms and reversed cells on odd repetitions",
        "registered_arm": "B1 factors with associative contractions, two-solve 2x2 Schur diagonal, and 128-thread Pass2/preparation",
    }
    path = P / "b1v2-registration.json"
    if path.exists():
        assert json.loads(path.read_text()) == reg
    else:
        N.write(path, reg)
    return reg


def enrich(row):
    log = (P / row["source"] / "stdout.log").read_text()
    audit = re.search(
        r"W5_FACTORED_AUDIT rel_frob=(\S+) max_abs=(\S+) max_reference=(\S+) observations=(\d+)", log)
    profile = re.search(
        r"\[PROFILE\] assembly=(\S+)s pointfactor\+rhs=(\S+)s krylov=(\S+)s candidates=(\S+)s", log)
    row["factored_active"] = "[w5-factored] active" in log
    if audit:
        row["fragment_audit"] = {
            "relative_frobenius_error": float(audit[1]), "max_absolute_error": float(audit[2]),
            "max_reference_magnitude": float(audit[3]), "observations": int(audit[4]),
        }
    if profile:
        row["profile_seconds"] = {
            "assembly": float(profile[1]), "pointfactor_rhs": float(profile[2]),
            "krylov": float(profile[3]), "candidates": float(profile[4]),
        }
    N.write(P / row["source"] / "result.json", row)
    return row


def execute(reg, stage, cells, arms, reps, extra=None):
    rows = []
    extra = extra or {}
    for rep in range(reps):
        ordered_cells, ordered_arms = list(cells), list(arms)
        if rep % 2:
            ordered_cells.reverse(); ordered_arms.reverse()
        for cell in ordered_cells:
            for arm in ordered_arms:
                binary = PARENT if arm == "parent-off" else BINARY
                flags = {} if arm == "parent-off" else dict(ARMS[arm], **extra)
                folder = P / "evidence" / stage / f"{cell.get('cell', cell['scene'])}-{arm}-{rep}"
                rows.append(enrich(N.run(folder, cell, arm, rep, binary, flags,
                                         PROTOCOL, reg["build_manifest"])))
                N.write(P / f"{stage}-results.json", rows)
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["compatibility", "audit", "panel", "profile", "muell", "tails"])
    args = parser.parse_args(); reg = register()
    calm = next(cell for cell in reg["practical"] if cell["cell"] == "ladybug-539-1.01")
    if args.stage == "compatibility":
        rows = execute(reg, "b1v2-compatibility", [calm], ["off", "parent-off"], 3)
        med = {arm: statistics.median(row["cost"] for row in rows if row["arm"] == arm)
               for arm in ("off", "parent-off")}
        result = {"rows": len(rows), "medians": med,
                  "relative_delta": med["off"] / med["parent-off"] - 1}
        result["passed"] = abs(result["relative_delta"]) < 0.0015
        N.write(P / "b1v2-compatibility-summary.json", result); assert result["passed"], result
    elif args.stage == "audit":
        assert json.loads((P / "b1v2-compatibility-summary.json").read_text())["passed"]
        rows = execute(reg, "b1v2-audit", [reg["audit"]], ["factored"], 1,
                       {"OCA_W5_FACTORED_AUDIT": "1"})
        result = {"row": rows[0], "passed": "fragment_audit" in rows[0]}
        N.write(P / "b1v2-audit-summary.json", result); assert result["passed"], result
    elif args.stage == "panel":
        result = B.summarize(execute(reg, "b1v2-panel", reg["practical"], list(ARMS), 3))
        N.write(P / "b1v2-panel-summary.json", result)
    elif args.stage == "muell":
        result = B.summarize(execute(reg, "b1v2-muell", [reg["muell"]], list(ARMS), 3))
        N.write(P / "b1v2-muell-summary.json", result)
    elif args.stage == "tails":
        result = B.summarize(execute(reg, "b1v2-tails", list(reg["tails"].values()), list(ARMS), 5))
        N.write(P / "b1v2-tails-summary.json", result)
    else:
        traf = next(cell for cell in reg["practical"] if cell["cell"] == "trafalgar-138-1.005")
        rows = execute(reg, "b1v2-profile", [traf, reg["muell"]], list(ARMS), 3,
                       {"OCA_PROFILE": "1"})
        result = B.summarize(rows)
        for cell in result["cells"]:
            for arm in ARMS:
                group = [row for row in rows if row["cell"] == cell["cell"] and row["arm"] == arm]
                cell[arm]["median_profile_seconds"] = {
                    phase: statistics.median(row["profile_seconds"][phase] for row in group)
                    for phase in ("assembly", "pointfactor_rhs", "krylov", "candidates")
                }
        N.write(P / "b1v2-profile-summary.json", result)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
