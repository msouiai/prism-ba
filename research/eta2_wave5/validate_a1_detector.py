#!/usr/bin/env python3
"""Validate the preregistered mean-floor rational detector on saved states."""
from pathlib import Path
import json, sys, tempfile
import numpy as np

P = Path(__file__).resolve().parent
W3 = P.parent / "eta2_wave3"
W4 = P.parent / "eta2_wave4"
sys.path.insert(0, str(W3))
import forensics as F


def analyze(folder, problem, label, step_name="accepted.step", target=None):
    cam, points, meta = F.load_capture_state(folder)
    nc, np_ = len(cam.R), len(points)
    step = F.read_array(folder / step_name, (9 * nc + 3 * np_,))
    dc, dp = step[:9*nc].reshape(nc, 9), step[9*nc:].reshape(np_, 3)
    ci, pi, uv, dims = F.CHART.load_observations(problem)
    assert dims == (nc, np_, len(ci)) and not np.any(dc[:, 8])
    current_sq = np.empty(len(ci)); disagreement = np.empty(len(ci))
    intrinsic = cam.intrinsics + dc[:, 6:9]
    for first in range(0, len(ci), 50000):
        sl = slice(first, min(first + 50000, len(ci))); c = ci[sl]; p = pi[sl]
        rx = np.einsum("nij,nj->ni", cam.R[c], points[p])
        y = rx + cam.t[c]
        pixel, jy, ji = F.S.chart.project_jacobian(y, cam.intrinsics[c])
        residual = pixel - uv[sl]
        dy = np.cross(dc[c, :3], rx) + dc[c, 3:6]
        dy += np.einsum("nij,nj->ni", cam.R[c], dp[p])
        jd = np.einsum("nij,nj->ni", jy, dy)
        jd += np.einsum("nij,nj->ni", ji, dc[c, 6:9])
        rational = F.S.chart.project_jacobian(y + dy, intrinsic[c])[0] - uv[sl]
        current_sq[sl] = np.sum(residual * residual, axis=1)
        disagreement[sl] = np.sum((rational - residual - jd) ** 2, axis=1)
    mean_sq = float(np.mean(current_sq, dtype=np.longdouble))
    flags = disagreement / np.maximum(current_sq, mean_sq) > 0.5
    lengths = np.bincount(pi, minlength=np_)
    selected = np.unique(pi[flags & (lengths[pi] == 2)])
    return {
        "label": label, "score_init": meta["cost"], "observations": len(ci), "points": np_,
        "mean_residual_squared": mean_sq, "flagged_observations": int(flags.sum()),
        "flagged_fraction": float(flags.mean()), "selected_two_view_points": int(len(selected)),
        "selected_point_fraction": float(len(selected) / np_),
        "target_point": target,
        "target_flagged": bool(np.any(flags[pi == target])) if target is not None else None,
        "target_selected": bool(target in selected) if target is not None else None,
    }


def main():
    rows = []
    problem = Path("/workspace/bal/final-3068.txt")
    decision = json.loads((W3 / "miss-forensics" / "decision.json").read_text())
    assert F.sha(decision["archive"]) == decision["sha256"]
    wanted = {"hit/6", "miss/6"}
    with tempfile.TemporaryDirectory(prefix="a1-detector-e4-", dir="/dev/shm") as temp:
        root = Path(temp)
        for name, raw in F.FA.decoded(decision["archive"]):
            if str(Path(name).parent) in wanted:
                path = root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
        for name in sorted(wanted):
            print("DETECT", name, flush=True)
            rows.append(analyze(root / name, problem, "final-e4-" + name.replace("/", "-"),
                                target=250233))
    registration = json.loads((P.parent / "eta2_wave3" / "registration.json").read_text())
    healthy_problem = Path(next(x["path"] for x in registration["practical"]
                                if x["cell"] == "ladybug-539-1.005"))
    for record in json.loads((W4 / "healthy-captures" / "index.json").read_text()):
        assert F.sha(record["archive"]) == record["sha256"]
        with tempfile.TemporaryDirectory(prefix="a1-detector-healthy-", dir="/dev/shm") as temp:
            root = Path(temp); F.FA.restore(record["archive"], root)
            for attempt in record["selected_attempts"]:
                label = f"ladybug-healthy-{record['rep']}-{attempt}"
                print("DETECT", label, flush=True)
                rows.append(analyze(root / str(attempt), healthy_problem, label))
    healthy = [x for x in rows if x["label"].startswith("ladybug")]
    e4 = [x for x in rows if x["label"].startswith("final")]
    result = {
        "definition": "squared linear-fractional-vs-linear residual gap / max(current squared residual, global mean squared residual) > 0.5; two-view tracks only",
        "threshold": 0.5, "scale_floor": "2*F_current/nobs", "locality_limit": 0.01,
        "e4_target_selected_both": len(e4) == 2 and all(x["target_selected"] for x in e4),
        "healthy_max_selected_point_fraction": max(x["selected_point_fraction"] for x in healthy),
        "gate_passed": (len(e4) == 2 and all(x["target_selected"] for x in e4)
                        and max(x["selected_point_fraction"] for x in healthy) <= 0.01),
        "rows": rows,
    }
    (P / "a1-native-detector-validation.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, indent=2))
    assert result["gate_passed"]


if __name__ == "__main__":
    main()
