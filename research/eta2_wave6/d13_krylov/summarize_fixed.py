#!/usr/bin/env python3
"""Parse D13 fixed-system logs and freeze the selection evidence."""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import statistics

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
EVIDENCE = HERE / "evidence"


def scalar(value: str):
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return value


def parse_line(line: str) -> dict:
    row = {}
    for key, value in re.findall(r"([A-Za-z_]+)=([^ ]+)", line.strip()):
        row[key] = scalar(value)
    return row


rows = {}
for path in sorted(EVIDENCE.glob("*.log")):
    if "-gmres8" in path.name:
        scene = path.name.removesuffix("-gmres8.log")
        arm = "gmres8"
        prefix = "GMRES "
    else:
        match = re.match(r"(.+)-(none|one4|one8|one16|one32|periodic8)\.log$", path.name)
        if not match:
            continue
        scene, arm = match.groups()
        prefix = "RESTART "
    parsed = [parse_line(line) for line in path.read_text().splitlines() if line.startswith(prefix)]
    assert len(parsed) == 3, path
    rows.setdefault(scene, {})[arm] = {
        "repetitions": parsed,
        "median_total_ms": statistics.median(row["total_ms"] for row in parsed),
        "median_iterations": statistics.median(row["iterations"] for row in parsed),
        "median_products": statistics.median(
            row.get("products", row.get("solve_products")) for row in parsed
        ),
        "all_hit": all(row["hit"] == 1 for row in parsed),
        "log_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }

muell = ("muell-o11", "muell-o12")
product_sums = {
    arm: sum(rows[scene][arm]["median_products"] for scene in muell)
    for arm in rows[muell[0]]
}
wall_sums = {
    arm: sum(rows[scene][arm]["median_total_ms"] for scene in muell)
    for arm in rows[muell[0]]
}
summary = {
    "protocol": "D13_KRYLOV_RESTART_PROTOCOL.md",
    "fixed_system_rows": rows,
    "hard_system_product_sums": product_sums,
    "hard_system_median_wall_sums_ms": wall_sums,
    "selected_restart_arm": "periodic8",
    "selected_native_arm": "gmres8",
    "selection_reason": (
        "Periodic8 dominates one-shot restart8 on Muell outer11 and ties it on outer12. "
        "Low-memory right-preconditioned GMRES8 then dominates periodic8 on both hard systems, "
        "uses nine stored camera vectors, and passes explicit-residual and orthogonality checks."
    ),
    "build_manifest_sha256": hashlib.sha256((EVIDENCE / "build_manifest.json").read_bytes()).hexdigest(),
    "restart_run_manifest_sha256": hashlib.sha256((EVIDENCE / "fixed_run_manifest.json").read_bytes()).hexdigest(),
    "gmres_run_manifest_sha256": hashlib.sha256((EVIDENCE / "gmres_run_manifest.json").read_bytes()).hexdigest(),
}
(ROOT / "d13-krylov-results.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps({"product_sums": product_sums, "wall_sums_ms": wall_sums}, indent=2))
