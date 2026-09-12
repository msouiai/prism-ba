#!/usr/bin/env python3
"""Build the compact C1 verdict from the registered scene reports."""
from __future__ import annotations

import json
import math
from pathlib import Path


HERE = Path(__file__).resolve().parent
SCENES = ("ladybug-539", "final-3068", "venice-52", "dubrovnik-88")
WATCH = {
    "final-3068": (550, 853, 1458, 2816, 3041, 534, 379, 1645, 1476),
    "venice-52": (34, 49),
}


def main():
    reports = {name: json.loads((HERE / f"c1-{name}.json").read_text()) for name in SCENES}
    scenes = []
    watches = {}
    for name, report in reports.items():
        rows = {row["camera"]: row for row in report["all_cameras"]}
        limit = math.ceil(0.01 * report["dimensions"]["cameras"])
        scenes.append({
            "scene": name,
            "cameras": report["dimensions"]["cameras"],
            "edges": report["graph"]["undirected_camera_edges"],
            "selected": report["gate"]["selected_count"],
            "registered_ceiling": limit,
            "selected_cameras": report["gate"]["selected_cameras"],
            "resistance_vs_negative_track_count_spearman": report["summary_statistics"][
                "spearman_log_resistance_vs_negative_log_tracks"
            ],
            "analysis_seconds": report["timing"]["total_seconds"],
        })
        watches[name] = [rows[camera] for camera in WATCH.get(name, ())]

    final550 = watches["final-3068"][0]
    venice34 = watches["venice-52"][0]
    validation = reports["venice-52"]["exact_validation"]
    summary = {
        "schema": 1,
        "registered_predictions": {
            "venice_estimator_gate_passes": validation["passes_registered_gate"],
            "final_camera_550_selected": final550["selected"],
            "final_camera_550_resistance_rank": final550["effective_resistance_rank_desc"],
            "final_camera_550_track_count_rank": final550["unique_track_count_rank_asc"],
            "all_scene_gate_counts_within_ceiling": all(
                row["selected"] <= row["registered_ceiling"] for row in scenes
            ),
            "venice_camera_34_not_selected": not venice34["selected"],
        },
        "venice_exact_validation": {
            key: validation[key]
            for key in (
                "spearman_rank",
                "median_relative_error",
                "max_relative_error",
                "top_1pct_set_equal",
                "passes_registered_gate",
            )
        },
        "scenes": scenes,
        "watched_cameras": watches,
        "verdict": {
            "registered_gate_validated": all((
                validation["passes_registered_gate"],
                final550["selected"],
                not venice34["selected"],
                all(row["selected"] <= row["registered_ceiling"] for row in scenes),
            )),
            "effective_resistance_adds_failure_linked_information_over_count": False,
            "reason": (
                "For the pre-registered failure-linked camera 550, resistance rank 8 and "
                "track-count rank 7 are effectively the same; scene-wide rank correlations "
                "are 0.849 to 0.976. Structural outliers exist on control scenes, but no "
                "measured Eta2 failure is linked to them."
            ),
            "native_choice": (
                "Do not put the 256-projection effective-resistance estimator in Eta2. "
                "If a sparse local prior is tested, use a fixed count gate and preregister it separately."
            ),
        },
    }
    (HERE / "c1-summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary["registered_predictions"], indent=2))


if __name__ == "__main__":
    main()
