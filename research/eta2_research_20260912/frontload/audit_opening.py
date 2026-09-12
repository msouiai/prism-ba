#!/usr/bin/env python3
"""Read-only attribution audit of the already completed Venice frontload traces."""
import csv
import hashlib
import json
import re
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(arm, rep):
    path = CAMPAIGN / "evidence/frontload/tail" / f"venice-52-{arm}-{rep}"
    lines = (path / "stdout.log").read_text().splitlines()
    attrs = [{k: float(v) for k, v in re.findall(r"(\w+)=([^ ]+)", line)}
             for line in lines if line.startswith("ATTR_RADIUS ")]
    models = [{k: float(v) for k, v in re.findall(r"(\w+)=([^ ]+)", line)}
              for line in lines if line.startswith("CLASSICAL_LM ")]
    attempts = json.loads((path / "attempts.json").read_text())["rows"]
    curves = list(csv.DictReader(line for line in (path / "curve.csv").read_text().splitlines()
                                if not line.startswith("#")))
    result = json.loads((path / "result.json").read_text())
    opening, accepted = [], 0
    # Later numerical-repair attempts need not emit ATTR_RADIUS; stop at the
    # opening before such an event and explicitly validate row alignment.
    for radius, model, attempt in zip(attrs, models, attempts):
        assert radius["o"] == model["o"] == attempt["outer"]
        assert bool(radius["accept"]) == bool(model["accept"]) == attempt["accepted"]
        assert radius["lambda"] == model["lambda"]
        row = dict(radius, **attempt)
        row["prediction"] = model["prediction"]
        row["proposal_decrease"] = model["prediction"] * model["rho"]
        row["oversized_raw"] = radius["raw_norm"] > radius["radius"] * (1 + 1e-12)
        row["was_clipped"] = radius["raw_norm"] > radius["norm"] * (1 + 1e-12)
        opening.append(row)
        accepted += attempt["accepted"]
        if accepted == 3:
            break
    assert accepted == 3
    return {
        "arm": arm, "rep": rep, "source": str(path.relative_to(CAMPAIGN)),
        "inputs": {name: sha(path / name) for name in
                   ("stdout.log", "attempts.json", "curve.csv", "result.json")},
        "score_init": result["score_init"],
        "cost_after_accept": [float(row["cost"]) for row in curves[:4]],
        "opening": opening,
        "opening_pcg": sum(row["pcg_iterations"] for row in opening),
        "opening_matvecs": sum(row["matvecs"] for row in opening),
        "opening_attempt_seconds": sum(row["seconds"] for row in opening),
        "handoff_lambda": opening[-1]["next_lambda"],
        "handoff_radius": opening[-1]["next_radius"],
        "endpoint": result["cost"], "target_hit": result["hit"],
        "registered_target_seconds": result["target_seconds"],
        "native_seconds": result["native_seconds"],
        "outers": result["outers"], "total_pcg": result["attempts"]["pcg_iterations"],
        "total_matvecs": result["matvecs"],
    }


def main():
    rows = [audit(arm, rep) for rep in range(5) for arm in ("off", "on")]
    summary = {}
    for arm in ("off", "on"):
        group = [row for row in rows if row["arm"] == arm]
        summary[arm] = {
            "target_hits": sum(row["target_hit"] for row in group),
            "n": len(group),
            "opening_pcg_values": sorted(set(row["opening_pcg"] for row in group)),
            "opening_matvec_values": sorted(set(row["opening_matvecs"] for row in group)),
            "opening_seconds_median": statistics.median(row["opening_attempt_seconds"] for row in group),
            "opening_seconds_range": [min(row["opening_attempt_seconds"] for row in group),
                                      max(row["opening_attempt_seconds"] for row in group)],
            "costs_after_accept_median": [statistics.median(row["cost_after_accept"][i] for row in group)
                                           for i in range(4)],
            "handoff_lambda_range": [min(row["handoff_lambda"] for row in group),
                                     max(row["handoff_lambda"] for row in group)],
            "handoff_radius_range": [min(row["handoff_radius"] for row in group),
                                     max(row["handoff_radius"] for row in group)],
        }
    output = {"scope": "Existing N5 traces only; no new solver run or causal attribution claim",
              "recommendation": "First-three-accepted-outer unclipping only; retain original precision, forcing and strict radius acceptance",
              "summary": summary, "rows": rows}
    (HERE / "results/opening_attribution.json").write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
