#!/usr/bin/env python3
"""Reproduce the exploratory D10 E4 per-track damage numbers."""
from pathlib import Path
import json
import sys
import tempfile

import numpy as np

P = Path(__file__).resolve().parent
W3 = P.parent / "eta2_wave3"
sys.path.insert(0, str(W3))
import forensics as F

ARCHIVE = Path("/workspace/eta2-wave3-evidence/e4-selected-snapshots.xor.tar.xz")
PROBLEM = Path("/workspace/bal/final-3068.txt")


def evaluate(folder, ci, pi, uv):
    camera, points, metadata = F.load_capture_state(folder)
    nc, np_ = len(camera.R), len(points)
    step = F.read_array(folder / "accepted.step", (9 * nc + 3 * np_,))
    dc = step[:9 * nc].reshape(nc, 9)
    dp = step[9 * nc:].reshape(np_, 3)
    proposed = camera.retract(dc)
    before = np.empty(len(ci)); after = np.empty(len(ci))
    for first in range(0, len(ci), 50_000):
        sl = slice(first, min(first + 50_000, len(ci)))
        c, p = ci[sl], pi[sl]
        r0, _ = F.S.residual(camera, points[p], c, uv[sl])
        r1, _ = F.S.residual(proposed, points[p] + dp[p], c, uv[sl])
        before[sl] = .5 * np.sum(r0 * r0, axis=1)
        after[sl] = .5 * np.sum(r1 * r1, axis=1)
    p0 = np.bincount(pi, weights=before, minlength=np_)
    p1 = np.bincount(pi, weights=after, minlength=np_)
    delta = np.maximum(0, p1 - p0)
    point = int(np.argmax(delta)); maximum = float(delta[point])
    positive = float(np.sum(delta, dtype=np.longdouble))
    gain = float(np.sum(before - after, dtype=np.longdouble))
    return {
        "score_before": float(np.sum(before, dtype=np.longdouble)),
        "score_after": float(np.sum(after, dtype=np.longdouble)),
        "global_gain": gain, "max_increase": maximum,
        "positive_sum": positive, "concentration": maximum / positive,
        "burden": maximum / gain, "max_point": point,
        "max_point_before": float(p0[point]), "max_point_after": float(p1[point]),
        "concentrated": maximum / positive > .05 and maximum / gain > .05,
        "metadata": metadata,
    }


def main():
    decision = json.loads((W3 / "miss-forensics/decision.json").read_text())
    assert F.sha(ARCHIVE) == decision["sha256"]
    wanted = {"hit/6", "miss/6"}
    ci, pi, uv, _ = F.CHART.load_observations(PROBLEM)
    with tempfile.TemporaryDirectory(prefix="d10-witness-", dir="/dev/shm") as name:
        root = Path(name)
        for member, raw in F.FA.decoded(ARCHIVE):
            if str(Path(member).parent) in wanted:
                path = root / member; path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
        rows = {label.split("/")[0]: evaluate(root / label, ci, pi, uv)
                for label in sorted(wanted)}
    result = {
        "scope": "Exploratory threshold selection before D10 native diagnostic",
        "archive": str(ARCHIVE), "archive_sha256": F.sha(ARCHIVE),
        "problem": str(PROBLEM), "problem_sha256": F.sha(PROBLEM),
        "thresholds": {"concentration": .05, "burden": .05}, "rows": rows,
    }
    (P / "d10-witness-prescreen.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
