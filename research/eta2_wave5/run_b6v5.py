#!/usr/bin/env python3
"""Registered B6v5 reduction-order-safe preparation measurements."""
from pathlib import Path
import argparse
import json
import re
import statistics
import subprocess

import native_light as N
import run_b6 as B
import run_b6v4 as V4

P = Path(__file__).resolve().parent
BINARY = P / "build" / "prism-b6v5"
PARENT = Path(N.CHAMPION["binary"])
PROTOCOL = P / "B6V5_PROTOCOL.md"
ARMS = {
    "off": {},
    "safe": {"OCA_W5_PREP_SAFE": "1"},
    "dots": {"OCA_W5_CG_DOTS": "1"},
    "dots-safe": {"OCA_W5_CG_DOTS": "1", "OCA_W5_PREP_SAFE": "1"},
}
PAIRS = (("off", "safe"), ("dots", "dots-safe"), ("off", "dots"),
         ("off", "dots-safe"))


def register():
    subprocess.run(["python3", str(N.FROZEN / "build.py"), "--check-only"], check=True)
    build = json.loads((P / "b6v5-build-manifest.json").read_text())
    assert N.sha(BINARY) == build["binary_sha256"]
    assert all(N.sha(path) == digest for path, digest in build["sources"].items())
    old = json.loads((P / "b1-registration.json").read_text())
    reg = {
        "arms": ARMS, "practical": old["practical"], "tails": old["tails"],
        "muell": old["muell"], "panel_repetitions": 3,
        "tail_repetitions": {"final-3068": 20, "venice-52": 10},
        "binary": str(BINARY), "binary_sha256": N.sha(BINARY),
        "parent_binary": str(PARENT), "parent_binary_sha256": N.sha(PARENT),
        "build_manifest": build, "protocol_sha256": N.sha(PROTOCOL),
        "rounding_audit": V4.audit(),
        "cohort_rule": "Fresh four-arm rows; reverse cells and arm order on odd repetitions",
        "registered_arm": "Three bitwise preparation fusions with champion RHS atomic kernel retained",
    }
    path = P / "b6v5-registration.json"
    if path.exists():
        assert json.loads(path.read_text()) == reg
    else:
        N.write(path, reg)
    return reg


def enrich(row):
    log = (P / row["source"] / "stdout.log").read_text()
    prep = re.search(r"W5_PREP_FUSE active mode=(safe|prune) ncam=(\d+) npt=(\d+) nobs=(\d+)", log)
    calls = re.search(r"W5_PREP_FUSE summary mode=(safe|prune) calls=(\d+)", log)
    dots = re.search(r"W5_CG_DOTS active n=(\d+)", log)
    dot_pairs = re.search(r"W5_CG_DOTS summary dot_pairs=(\d+)", log)
    profile = re.search(
        r"\[PROFILE\] assembly=(\S+)s pointfactor\+rhs=(\S+)s krylov=(\S+)s candidates=(\S+)s", log)
    row["prep_mode"] = prep[1] if prep else "off"
    row["cg_dots_active"] = bool(dots)
    if calls:
        row["prep_calls"] = int(calls[2])
    if dot_pairs:
        row["batched_dot_pairs"] = int(dot_pairs[1])
    if profile:
        row["profile_seconds"] = {
            "assembly": float(profile[1]), "pointfactor_rhs": float(profile[2]),
            "krylov": float(profile[3]), "candidates": float(profile[4]),
        }
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
                row = N.run(folder, cell, arm, rep, binary, flags, PROTOCOL,
                            reg["build_manifest"])
                rows.append(enrich(row)); N.write(P / f"{stage}-results.json", rows)
    return rows


def comparisons(rows):
    return {f"{b}_vs_{a}": B.summarize(rows, (a, b)) for a, b in PAIRS}


def add_profiles(result, rows):
    for comparison in result.values():
        for cell in comparison["cells"]:
            for arm in ARMS:
                group = [r for r in rows if r["cell"] == cell["cell"] and r["arm"] == arm]
                if group and all("profile_seconds" in r for r in group):
                    cell.setdefault(arm, {})["median_profile_seconds"] = {
                        phase: statistics.median(r["profile_seconds"][phase] for r in group)
                        for phase in ("assembly", "pointfactor_rhs", "krylov", "candidates")
                    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["compatibility", "panel", "profile", "muell", "tails"])
    args = parser.parse_args(); reg = register()
    calm = next(c for c in reg["practical"] if c["cell"] == "ladybug-539-1.01")
    if args.stage == "compatibility":
        rows = execute(reg, "b6v5-compatibility", [calm], ["off", "parent-off"], 3)
        med = {a: statistics.median(r["cost"] for r in rows if r["arm"] == a)
               for a in ("off", "parent-off")}
        result = {"rows": len(rows), "medians": med,
                  "relative_delta": med["off"] / med["parent-off"] - 1}
        result["passed"] = abs(result["relative_delta"]) < .0015
        N.write(P / "b6v5-compatibility-summary.json", result); assert result["passed"]
    elif args.stage == "panel":
        assert json.loads((P / "b6v5-compatibility-summary.json").read_text())["passed"]
        result = comparisons(execute(reg, "b6v5-panel", reg["practical"], list(ARMS), 3))
        N.write(P / "b6v5-panel-summary.json", result)
    elif args.stage == "profile":
        traf = next(c for c in reg["practical"] if c["cell"] == "trafalgar-138-1.005")
        rows = execute(reg, "b6v5-profile", [traf, reg["muell"]], list(ARMS), 3,
                       {"OCA_PROFILE": "1"})
        result = comparisons(rows); add_profiles(result, rows)
        N.write(P / "b6v5-profile-summary.json", result)
    elif args.stage == "muell":
        result = comparisons(execute(reg, "b6v5-muell", [reg["muell"]], list(ARMS), 3))
        N.write(P / "b6v5-muell-summary.json", result)
    else:
        final_rows = execute(reg, "b6v5-tails-final", [reg["tails"]["final-3068"]],
                             list(ARMS), 20)
        venice_rows = execute(reg, "b6v5-tails-venice", [reg["tails"]["venice-52"]],
                              list(ARMS), 10)
        rows = final_rows + venice_rows
        N.write(P / "b6v5-tails-results.json", rows)
        result = comparisons(rows); N.write(P / "b6v5-tails-summary.json", result)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
