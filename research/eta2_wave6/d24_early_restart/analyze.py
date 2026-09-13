#!/usr/bin/env python3
"""Fit D24 scalar rules on development; evaluate only a separately registered test."""
from __future__ import annotations
import argparse, csv, hashlib, json, math, pathlib, re, statistics

HERE = pathlib.Path(__file__).resolve().parent
W6 = HERE.parent
W5 = W6.parent / "eta2_wave5"
PROTOCOL = W6 / "D24_EARLY_RESTART_PREDICTOR_PROTOCOL.md"
SOURCE = W5 / "b6v7-extension-results.json"
INVENTORY = W6 / "d24-heldout-inventory.json"
TARGET = 1744796.9841897595
FEATURES = ["log10_lambda15", "max_log10_lambda10_15", "rejects15",
            "max_raw_radius10_15", "cost_ratio15"]
ATTEMPT = re.compile(
    r"ATTR_RADIUS o=(\d+) raw_norm=(\S+) norm=(\S+) radius=(\S+) "
    r"next_radius=(\S+) lambda=(\S+) next_lambda=(\S+) rho=(\S+) accept=(\d+)"
)


def sha(path: pathlib.Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def extract(folder: pathlib.Path, hit: bool, identity: int) -> dict:
    attempts = []
    for match in ATTEMPT.finditer((folder / "stdout.log").read_text()):
        attempts.append({"outer": int(match[1]), "raw": float(match[2]),
                         "radius": float(match[4]), "lambda": float(match[6]),
                         "next_lambda": float(match[7]), "rho": float(match[8]),
                         "accept": bool(int(match[9]))})
    early = [a for a in attempts if a["outer"] <= 14]
    window = [a for a in attempts if 9 <= a["outer"] <= 14]
    final15 = [a for a in attempts if a["outer"] == 14]
    curve = list(csv.DictReader(x for x in (folder / "curve.csv").read_text().splitlines()
                                if not x.startswith("#")))
    cost15 = [float(x["cost"]) for x in curve if int(x["iter"]) == 15]
    complete = bool(final15 and window and cost15)
    values = {
        "log10_lambda15": math.log10(final15[-1]["next_lambda"]) if complete else None,
        "max_log10_lambda10_15": max(math.log10(max(a["lambda"], a["next_lambda"]))
                                      for a in window) if complete else None,
        "rejects15": sum(not a["accept"] for a in early) if complete else None,
        "max_raw_radius10_15": max(a["raw"] / a["radius"] for a in window
                                    if a["radius"] > 0) if complete else None,
        "cost_ratio15": cost15[-1] / TARGET if complete else None,
    }
    return {"id": identity, "hit": bool(hit), "miss": not bool(hit),
            "complete": complete, "features": values,
            "stdout_sha256": sha(folder / "stdout.log"),
            "curve_sha256": sha(folder / "curve.csv")}


def metrics(rows: list[dict], feature: str, threshold: float, orientation: str) -> dict:
    def predicted(row):
        value = row["features"][feature]
        return value >= threshold if orientation == "high" else value <= threshold
    tp = sum(predicted(r) and r["miss"] for r in rows)
    fn = sum((not predicted(r)) and r["miss"] for r in rows)
    fp = sum(predicted(r) and not r["miss"] for r in rows)
    tn = sum((not predicted(r)) and not r["miss"] for r in rows)
    sensitivity = tp / (tp + fn) if tp + fn else None
    specificity = tn / (tn + fp) if tn + fp else None
    balanced = (sensitivity + specificity) / 2 if sensitivity is not None and specificity is not None else None
    return {"tp_miss": tp, "fn_miss": fn, "fp_hit": fp, "tn_hit": tn,
            "miss_sensitivity": sensitivity, "hit_specificity": specificity,
            "balanced_accuracy": balanced}


def fit(rows: list[dict], feature: str) -> dict:
    values = sorted({r["features"][feature] for r in rows})
    thresholds = [values[0] - max(1.0, abs(values[0])) * 1e-12]
    thresholds += [(a + b) / 2 for a, b in zip(values, values[1:])]
    thresholds += [values[-1] + max(1.0, abs(values[-1])) * 1e-12]
    candidates = []
    for threshold in thresholds:
        for orientation in ("high", "low"):
            candidates.append({"feature": feature, "threshold": threshold,
                               "orientation": orientation,
                               "metrics": metrics(rows, feature, threshold, orientation)})
    candidates.sort(key=lambda x: (-x["metrics"]["balanced_accuracy"], x["threshold"],
                                   0 if x["orientation"] == "high" else 1))
    return candidates[0]


def development() -> dict:
    source = json.loads(SOURCE.read_text())
    selected = sorted((r for r in source if r["arm"] == "gated"), key=lambda r: r["rep"])
    assert len(selected) == 130 and [r["rep"] for r in selected] == list(range(20, 150))
    rows = [extract(W5 / r["source"], r["hit"], r["rep"]) for r in selected]
    complete = all(r["complete"] for r in rows)
    train = [r for r in rows if r["id"] <= 99]
    validation = [r for r in rows if r["id"] >= 100]
    rules = []
    chosen = None
    for feature in FEATURES:
        rule = fit(train, feature)
        rule["validation"] = metrics(validation, feature, rule["threshold"], rule["orientation"])
        m, v = rule["metrics"], rule["validation"]
        rule["passes"] = bool(complete and m["balanced_accuracy"] >= .80 and
                              v["balanced_accuracy"] >= .75 and
                              v["miss_sensitivity"] >= .70 and v["hit_specificity"] >= .70)
        rules.append(rule)
        if chosen is None and rule["passes"]:
            chosen = {k: rule[k] for k in ("feature", "threshold", "orientation")}
    result = {"protocol_sha256": sha(PROTOCOL), "source": str(SOURCE),
              "source_sha256": sha(SOURCE), "inventory_sha256": sha(INVENTORY),
              "rows": len(rows), "train_rows": len(train), "validation_rows": len(validation),
              "complete": complete, "rules": rules, "chosen_rule": chosen,
              "advance": chosen is not None, "row_evidence": rows}
    out = W6 / "d24-development-results.json"
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "row_evidence"}, indent=2))
    return result


def wilson(successes: int, total: int, z: float = 1.959963984540054) -> list[float] | None:
    if not total:
        return None
    p = successes / total
    den = 1 + z*z/total
    center = (p + z*z/(2*total)) / den
    half = z * math.sqrt(p*(1-p)/total + z*z/(4*total*total)) / den
    return [center-half, center+half]


def heldout() -> dict:
    registration = json.loads((W6 / "d24-test-registration.json").read_text())
    development_result = W6 / "d24-development-results.json"
    assert registration["development_sha256"] == sha(development_result)
    assert registration["inventory_sha256"] == sha(INVENTORY)
    inventory = json.loads(INVENTORY.read_text())
    episodes = json.loads((W6 / "d21-results.json").read_text())
    assert len(episodes) == inventory["episodes"]
    rows = []
    for item, episode in zip(inventory["rows"], episodes):
        assert item["episode"] == episode["episode"]
        folder = W6 / item["folder"]
        assert all(sha(folder / name) == digest for name, digest in item["files"].items())
        rows.append(extract(folder, episode["attempts"][0]["hit"], episode["episode"]))
    rule = registration["rule"]
    outcome = metrics(rows, rule["feature"], rule["threshold"], rule["orientation"])
    outcome["miss_sensitivity_wilson95"] = wilson(outcome["tp_miss"], outcome["tp_miss"] + outcome["fn_miss"])
    outcome["hit_specificity_wilson95"] = wilson(outcome["tn_hit"], outcome["tn_hit"] + outcome["fp_hit"])
    passed = (all(r["complete"] for r in rows) and outcome["balanced_accuracy"] >= .75 and
              outcome["miss_sensitivity"] >= .70 and outcome["hit_specificity"] >= .70)
    result = {"registration_sha256": sha(W6 / "d24-test-registration.json"),
              "rule": rule, "rows": len(rows), "metrics": outcome,
              "passed": passed, "row_evidence": rows}
    (W6 / "d24-heldout-results.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "row_evidence"}, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("development", "heldout"))
    args = parser.parse_args()
    if args.stage == "development":
        development()
    else:
        heldout()


if __name__ == "__main__":
    main()
