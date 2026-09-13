#!/usr/bin/env python3
"""Complete and score every D18 direction on the archived full objective."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import pathlib
import sys
import tarfile
import tempfile
import time

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
WAVE3 = ROOT / "research/eta2_wave3"
CAPTURE = pathlib.Path("/workspace/prism-wave6-d18")
SOLUTIONS = CAPTURE / "fixed-solutions"
BAL = pathlib.Path("/workspace/bal/venice-52.txt")
sys.path[:0] = [str(ROOT / "research/eta2_wave2"),
                str(ROOT / "research/eta2_research_20260912/analysis"),
                str(ROOT / "research/eta2_research_20260912/coarse")]
from audit_capture import load_capture_state, CHART  # noqa: E402
from diagnostic import read_array  # noqa: E402
from spectrum import point_qr, point_inverse  # noqa: E402

spec = importlib.util.spec_from_file_location(
    "d18_score_core", ROOT / "research/eta2_research_20260912/separable_rescue/core.py")
S = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = S
assert spec.loader is not None
spec.loader.exec_module(S)

ARMS = ["0", "01", "1", "10", "100", "inf"]
FINITE = ["01", "1", "10", "100"]


def sha(path: pathlib.Path) -> str:
    with pathlib.Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def aggregate(values, ids, count):
    flat = values.reshape(len(values), -1)
    return np.column_stack([
        np.bincount(ids, weights=flat[:, column], minlength=count)
        for column in range(flat.shape[1])]).reshape((count,) + values.shape[1:])


def score_case(index: int, fixed: dict) -> dict:
    started = time.perf_counter()
    forensic_path = WAVE3 / f"forensics/venice-terminal-{index}.json"
    forensic = json.loads(forensic_path.read_text())
    record = forensic["archive_source"]
    archive = pathlib.Path(record["path"])
    if sha(archive) != record["sha256"]:
        raise RuntimeError("archive hash mismatch")
    with tempfile.TemporaryDirectory(prefix="d18-score-", dir="/dev/shm") as td:
        root = pathlib.Path(td)
        with tarfile.open(archive) as handle:
            handle.extractall(root, filter="data")
        source = root / "0"
        for name, digest in record["member_sha256"].items():
            if sha(root / name) != digest:
                raise RuntimeError(("member hash", name))
        camera, points, meta = load_capture_state(source)
        ci, pi, uv, dims = CHART.load_observations(BAL)
        nc, npt = len(camera.R), len(points)
        assert dims == (nc, npt, len(ci))
        E = read_array(source / "E.f64", (nc, 9))
        Cdiag = read_array(source / "Cdiag.f64", (npt, 3))
        archived = -read_array(source / "eta2_raw_scaled.f64", (nc, 9))
        chart = CHART.make_chart(points, camera, "euclidean")
        residual, Jc, Jp, _ = CHART.observation_jacobians(
            camera, chart.H, chart.T, ci, pi, uv)
        diagonal = np.maximum(Cdiag, .001 * np.maximum(
            Cdiag.mean(axis=1), 1e-32)[:, None])
        _, inverse_R, _ = point_qr(Jp, pi, meta["tau"] * diagonal)

        def complete(z):
            dc = E * z
            camera_residual = np.einsum("nri,ni->nr", Jc, dc[ci])
            rhs = aggregate(np.einsum("nri,nr->ni", Jp,
                                      residual + camera_residual), pi, npt)
            return dc, -point_inverse(inverse_R, rhs)

        gate = np.zeros(nc, dtype=bool)
        gate[fixed["system"]["gate_ids"]] = True
        folder = SOLUTIONS / f"venice-terminal-{index}"
        raw = {}
        solution_hashes = {}
        for arm in ARMS:
            for rep in range(3):
                path = folder / f"solution-a{arm}-r{rep}.f64"
                stored = np.fromfile(path, dtype="<f8").reshape(nc, 9)
                raw[(arm, rep)] = -stored
                solution_hashes[f"{arm}-{rep}"] = sha(path)
        base = raw[("0", 0)]
        direction_error = float(np.linalg.norm(base - archived)
                                / max(np.linalg.norm(archived), 1e-300))
        base_free = float(np.linalg.norm(base[~gate]))
        rows = []
        for arm in ARMS:
            for rep in range(3):
                z = raw[(arm, rep)]
                norm = float(np.linalg.norm(z))
                clip = min(1.0, meta["radius"] / max(norm, 1e-300))
                dc, dp = complete(z * clip)
                audit = S.audit(camera, points, ci, pi, uv, dc, dp, E)
                free = float(np.linalg.norm(z[~gate]))
                gate_energy = float(np.sum(z[gate] * z[gate]))
                total = float(np.sum(z * z))
                rows.append({
                    "index": index, "arm": arm, "rep": rep,
                    "raw_norm": norm, "radius": meta["radius"],
                    "raw_radius_ratio": norm / meta["radius"],
                    "global_clip_factor": clip,
                    "gated_energy_fraction": gate_energy / max(total, 1e-300),
                    "ungated_raw_norm": free,
                    "ungated_norm_retention": free / max(base_free, 1e-300),
                    **{k: (v if not isinstance(v, float) or np.isfinite(v) else None)
                       for k, v in audit.items()},
                })
        baseline = next(x for x in rows if x["arm"] == "0" and x["rep"] == 0)
        repeat_spread = {}
        for arm in ARMS:
            selected = [x for x in rows if x["arm"] == arm]
            repeat_spread[arm] = {
                key: max(x[key] for x in selected) - min(x[key] for x in selected)
                for key in ("raw_norm", "true_decrease", "rho", "cost")}
        validation = {
            "direction_replay_relative_error": direction_error,
            "initial_cost_relative_error": abs(baseline["score_init"] - meta["cost"])
                                           / max(abs(meta["cost"]), 1.0),
            "solution_sha256": solution_hashes,
            "repeat_spread": repeat_spread,
        }
        if validation["initial_cost_relative_error"] > 1e-8 or direction_error > 1e-5:
            raise RuntimeError(("invalid D18 replay", index, validation))
    return {
        "index": index, "metadata": meta, "system": fixed["system"],
        "validation": validation, "rows": rows,
        "archive": str(archive), "archive_sha256": record["sha256"],
        "seconds": time.perf_counter() - started,
    }


def summarize(cases: list[dict]) -> dict:
    by = {case["index"]: {
        arm: next(x for x in case["rows"] if x["arm"] == arm and x["rep"] == 0)
        for arm in ARMS} for case in cases}
    gate_ok = all(case["system"]["gated"] == 1
                  and case["system"]["gate_ids"] == [34] for case in cases)
    checks = {}
    for arm in FINITE:
        per_case = []
        for index in range(5):
            base, row = by[index]["0"], by[index][arm]
            gain = ((row["true_decrease"] - base["true_decrease"])
                    / max(abs(base["true_decrease"]), 1e-12))
            per_case.append({
                "index": index, "raw_radius_ratio": row["raw_radius_ratio"],
                "ungated_norm_retention": row["ungated_norm_retention"],
                "relative_true_decrease_gain": gain,
                "rho_delta": row["rho"] - base["rho"],
            })
        checks[arm] = {
            "cases": per_case,
            "ratio_pass_count": sum(x["raw_radius_ratio"] <= 10 for x in per_case),
            "decrease_pass_count": sum(x["relative_true_decrease_gain"] > .0015
                                       for x in per_case),
            "all_healthy_retained": all(x["ungated_norm_retention"] >= .95
                                        for x in per_case),
            "all_rho_nondecreasing": all(x["rho_delta"] >= -1e-12 for x in per_case),
        }
        checks[arm]["passes"] = (
            gate_ok and checks[arm]["ratio_pass_count"] >= 4
            and checks[arm]["decrease_pass_count"] >= 4
            and checks[arm]["all_healthy_retained"]
            and checks[arm]["all_rho_nondecreasing"])
    selected = next((arm for arm in FINITE if checks[arm]["passes"]), None)
    compact = []
    for index in range(5):
        for arm in ARMS:
            row = by[index][arm]
            compact.append({k: row[k] for k in (
                "index", "arm", "raw_radius_ratio", "gated_energy_fraction",
                "ungated_norm_retention", "true_decrease", "prediction", "rho", "cost")})
    return {
        "gate_selects_camera34_all": gate_ok,
        "dose_checks": checks,
        "selected_finite_dose": selected,
        "native_arm_earned": selected is not None,
        "decision": ("advance geometric prior to native gate" if selected
                     else "stop geometric prior at fixed-state gate"),
        "compact_rows": compact,
    }


def main() -> None:
    fixed_manifest = json.loads((HERE / "fixed-run-manifest.json").read_text())
    cases = [score_case(case["index"], case) for case in fixed_manifest["cases"]]
    summary = summarize(cases)
    provenance = {
        "protocol_sha256": sha(ROOT / "research/eta2_wave6/D18_GEOMETRIC_PRIOR_PROTOCOL.md"),
        "amendment_sha256": sha(ROOT / "research/eta2_wave6/D18_CAPTURE_RADIUS_AMENDMENT.md"),
        "capture_manifest_sha256": sha(HERE / "capture-manifest.json"),
        "build_manifest_sha256": sha(HERE / "build-manifest.json"),
        "fixed_run_manifest_sha256": sha(HERE / "fixed-run-manifest.json"),
    }
    (ROOT / "research/eta2_wave6/d18-geometric-prior-results.json").write_text(
        json.dumps({"provenance": provenance, "cases": cases}, indent=2) + "\n")
    (ROOT / "research/eta2_wave6/d18-geometric-prior-summary.json").write_text(
        json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
