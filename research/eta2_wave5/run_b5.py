#!/usr/bin/env python3
"""Registered B5 Jacobian-consistent square-root Schur measurements."""
from pathlib import Path
import argparse
import json
import re
import statistics
import subprocess

import native_light as N
import run_b1 as B

P = Path(__file__).resolve().parent
BINARY = P / "build" / "prism-b5"
PARENT = Path(N.CHAMPION["binary"])
PROTOCOL = P / "B5_PROTOCOL.md"
ARMS = {"off": {}, "sqrt": {"OCA_W5_SQRT": "1"}}


def register():
    subprocess.run(["python3", str(N.FROZEN / "build.py"), "--check-only"], check=True)
    build = json.loads((P / "b5-build-manifest.json").read_text())
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
        "registered_arm": "One FP32 2x12 Jacobian; all blocks and projected Schur products accumulated in FP64",
        "audit_thresholds": {"action_relative_l2": 1e-5, "curvature_relative": 1e-8},
    }
    path = P / "b5-registration.json"
    if path.exists():
        assert json.loads(path.read_text()) == reg
    else:
        N.write(path, reg)
    return reg


def enrich(row):
    log = (P / row["source"] / "stdout.log").read_text()
    active = re.search(r"\[w5-sqrt\] active values_per_obs=(\d+) bytes_saved=(\d+) arithmetic=(\S+) storage=(\S+)", log)
    audit = re.search(
        r"W5_SQRT_AUDIT action_relative_l2=(\S+) action_absolute_l2=(\S+) reference_l2=(\S+) "
        r"curvature=(\S+) sos=(\S+) curvature_relative=(\S+) obs=(\S+) point_damp=(\S+) intr=(\S+)", log)
    profile = re.search(
        r"\[PROFILE\] assembly=(\S+)s pointfactor\+rhs=(\S+)s krylov=(\S+)s candidates=(\S+)s", log)
    row["sqrt_active"] = bool(active)
    if active:
        row["sqrt_storage"] = {"values_per_observation": int(active[1]),
                               "bytes_saved": int(active[2]),
                               "arithmetic": active[3], "storage": active[4]}
    if audit:
        row["sqrt_audit"] = {
            "action_relative_l2": float(audit[1]), "action_absolute_l2": float(audit[2]),
            "reference_l2": float(audit[3]), "curvature": float(audit[4]),
            "sos": float(audit[5]), "curvature_relative": float(audit[6]),
            "obs_term": float(audit[7]), "point_damp_term": float(audit[8]),
            "intr_term": float(audit[9]),
        }
    if profile:
        row["profile_seconds"] = {"assembly": float(profile[1]),
                                  "pointfactor_rhs": float(profile[2]),
                                  "krylov": float(profile[3]),
                                  "candidates": float(profile[4])}
    N.write(P / row["source"] / "result.json", row)
    return row


def execute(reg, stage, cells, arms, reps, extra=None):
    rows = []; extra = extra or {}
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
        rows = execute(reg, "b5-compatibility", [calm], ["off", "parent-off"], 3)
        med = {arm: statistics.median(r["cost"] for r in rows if r["arm"] == arm)
               for arm in ("off", "parent-off")}
        result = {"rows": len(rows), "medians": med,
                  "relative_delta": med["off"] / med["parent-off"] - 1}
        result["passed"] = abs(result["relative_delta"]) < 1e-10
        N.write(P / "b5-compatibility-summary.json", result); assert result["passed"], result
    elif args.stage == "audit":
        rows = execute(reg, "b5-audit", [reg["audit"]], ["sqrt"], 1,
                       {"OCA_W5_SQRT_AUDIT": "1"})
        audit = rows[0].get("sqrt_audit", {})
        result = {"row": rows[0], "thresholds": reg["audit_thresholds"]}
        result["passed"] = bool(audit) and audit["curvature"] >= 0 and audit["sos"] >= 0 and \
            audit["action_relative_l2"] < reg["audit_thresholds"]["action_relative_l2"] and \
            audit["curvature_relative"] < reg["audit_thresholds"]["curvature_relative"]
        N.write(P / "b5-audit-summary.json", result); assert result["passed"], result
    elif args.stage == "panel":
        result = B.summarize(execute(reg, "b5-panel", reg["practical"], list(ARMS), 3),
                             ("off", "sqrt"))
        N.write(P / "b5-panel-summary.json", result)
    elif args.stage == "profile":
        traf = next(cell for cell in reg["practical"] if cell["cell"] == "trafalgar-138-1.005")
        rows = execute(reg, "b5-profile", [traf, reg["muell"]], list(ARMS), 3,
                       {"OCA_PROFILE": "1"})
        result = B.summarize(rows, ("off", "sqrt"))
        for cell in result["cells"]:
            for arm in ARMS:
                group = [r for r in rows if r["cell"] == cell["cell"] and r["arm"] == arm]
                cell[arm]["median_profile_seconds"] = {
                    phase: statistics.median(r["profile_seconds"][phase] for r in group)
                    for phase in ("assembly", "pointfactor_rhs", "krylov", "candidates")}
        N.write(P / "b5-profile-summary.json", result)
    elif args.stage == "muell":
        result = B.summarize(execute(reg, "b5-muell", [reg["muell"]], list(ARMS), 3),
                             ("off", "sqrt"))
        N.write(P / "b5-muell-summary.json", result)
    else:
        result = B.summarize(execute(reg, "b5-tails", list(reg["tails"].values()), list(ARMS), 5),
                             ("off", "sqrt"))
        N.write(P / "b5-tails-summary.json", result)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
