#!/usr/bin/env python3
"""Conservative A1 locality gate from the immutable wave-4 attribution rows."""
from pathlib import Path
import hashlib, json

P = Path(__file__).resolve().parent
SOURCE = P.parent / "eta2_wave4" / "attribution"


def sha(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


rows = []
for path in sorted(SOURCE.glob("*.json")):
    data = json.loads(path.read_text())
    # Each flagged observation belongs to exactly one point.  Consequently
    # flagged_observations / npoints is a rigorous upper bound on the fraction
    # of distinct points the detector can select.  A1 further restricts this
    # set to two-observation tracks, so this bound is conservative.
    bound = data["flagged_observations"] / data["points"]
    rows.append({
        "label": data["label"],
        "source": str(path.relative_to(P.parent.parent)),
        "source_sha256": sha(path),
        "observations": data["observations"],
        "points": data["points"],
        "flagged_observations": data["flagged_observations"],
        "flagged_observation_fraction": data["flagged_fraction"],
        "distinct_flagged_point_fraction_upper_bound": bound,
        "tracked_point_250233_flagged": data.get("tracked_point_flagged"),
    })

healthy = [r for r in rows if r["label"].startswith("ladybug-healthy")]
e4 = [r for r in rows if r["label"] in {"final-e4-hit-6", "final-e4-miss-6"}]
result = {
    "method": "Conservative bound: number of distinct flagged points <= number of flagged observations; native A1 is a subset because it also requires track length two.",
    "threshold": 0.01,
    "healthy_states": len(healthy),
    "healthy_max_distinct_flagged_point_fraction_upper_bound": max(
        r["distinct_flagged_point_fraction_upper_bound"] for r in healthy
    ),
    "e4_target_detected_both_directions": all(
        r["tracked_point_250233_flagged"] for r in e4
    ) and len(e4) == 2,
    "gate_passed": max(
        r["distinct_flagged_point_fraction_upper_bound"] for r in healthy
    ) <= 0.01,
    "rows": rows,
}
(P / "a1-locality.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps({k: v for k, v in result.items() if k != "rows"}, indent=2))
