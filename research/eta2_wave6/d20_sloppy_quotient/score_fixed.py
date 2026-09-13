#!/usr/bin/env python3
"""Fixed-state nonlinear score for D20's direct sloppy-mode projection."""
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
PROTOCOL = ROOT / "research/eta2_wave6/D20_SLOPPY_QUOTIENT_PROTOCOL.md"
BAL = pathlib.Path("/workspace/bal/venice-52.txt")
sys.path[:0] = [str(ROOT / "research/eta2_wave2"),
                str(ROOT / "research/eta2_research_20260912/analysis"),
                str(ROOT / "research/eta2_research_20260912/coarse")]
from audit_capture import load_capture_state, CHART  # noqa: E402
from diagnostic import read_array  # noqa: E402
from spectrum import point_qr, point_inverse  # noqa: E402

spec = importlib.util.spec_from_file_location(
    "d20_score_core", ROOT / "research/eta2_research_20260912/separable_rescue/core.py")
S = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = S
assert spec.loader is not None
spec.loader.exec_module(S)


def sha(path: pathlib.Path) -> str:
    with pathlib.Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def aggregate(values, ids, count):
    flat = values.reshape(len(values), -1)
    return np.column_stack([
        np.bincount(ids, weights=flat[:, column], minlength=count)
        for column in range(flat.shape[1])]).reshape((count,) + values.shape[1:])


def score_case(index: int) -> dict:
    started = time.perf_counter()
    forensic_path = WAVE3 / f"forensics/venice-terminal-{index}.json"
    forensic = json.loads(forensic_path.read_text())
    record = forensic["archive_source"]
    archive = pathlib.Path(record["path"])
    if sha(archive) != record["sha256"]:
        raise RuntimeError("archive hash mismatch")
    with tempfile.TemporaryDirectory(prefix="d20-score-", dir="/dev/shm") as td:
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
        raw = -read_array(source / "eta2_raw_scaled.f64", (nc, 9))
        chart = CHART.make_chart(points, camera, "euclidean")
        residual, Jc, Jp, _ = CHART.observation_jacobians(
            camera, chart.H, chart.T, ci, pi, uv)
        tracks = np.bincount(pi, minlength=npt)
        multiplier = np.where(tracks >= 6, .3, 1.) if meta.get("static_replay", 0) else np.ones(npt)
        diagonal = np.maximum(Cdiag, .001 * np.maximum(
            Cdiag.mean(axis=1), 1e-32)[:, None])
        point_diagonal = meta["tau"] * multiplier[:, None] * diagonal
        _, inverse_R, _ = point_qr(Jp, pi, point_diagonal)

        # Recompute the direct local scaled Schur blocks independently.
        keys = ci.astype(np.int64) * npt + pi
        unique, inverse = np.unique(keys, return_inverse=True)
        pair_camera = unique // npt
        pair_point = unique % npt
        cross = aggregate(np.einsum("nri,nrj->nij", Jc, Jp), inverse, len(unique))
        camera_normal = aggregate(np.einsum("nri,nrj->nij", Jc, Jc), ci, nc)
        factor = np.einsum("nij,njk->nik", cross, inverse_R[pair_point])
        schur = camera_normal - aggregate(
            np.einsum("nik,njk->nij", factor, factor), pair_camera, nc)
        scaled = schur * E[:, :, None] * E[:, None, :]
        scaled = .5 * (scaled + scaled.transpose(0, 2, 1))
        eigenvalues, eigenvectors = np.linalg.eigh(scaled[:, :8, :8])

        energy = np.sum(raw[:, :8] ** 2, axis=1)
        top = int(np.argmax(energy))
        weakest = int(np.argmin(eigenvalues[:, 0]))
        q = eigenvectors[top, :, 0]
        archived_entry = next(x for x in forensic["top5"] if x["camera"] == top)
        archived_q = np.asarray(archived_entry["weakest_scaled_eigenvector"])
        alignment = float(abs(q @ archived_q))
        projected = raw.copy()
        coefficient = float(projected[top, :8] @ q)
        projected[top, :8] -= coefficient * q
        unchanged = bool(np.array_equal(
            projected[np.arange(nc) != top], raw[np.arange(nc) != top]))

        def complete(z):
            dc = E * z
            camera_residual = np.einsum("nri,ni->nr", Jc, dc[ci])
            rhs = aggregate(np.einsum("nri,nr->ni", Jp,
                                      residual + camera_residual), pi, npt)
            return dc, -point_inverse(inverse_R, rhs)

        rows = []
        for rep in range(3):
            for arm, z in (("control", raw), ("quotient", projected)):
                norm = float(np.linalg.norm(z))
                clip = min(1.0, meta["radius"] / max(norm, 1e-300))
                dc, dp = complete(z * clip)
                audit = S.audit(camera, points, ci, pi, uv, dc, dp, E)
                rows.append({
                    "index": index, "rep": rep, "arm": arm,
                    "raw_norm": norm, "raw_radius_ratio": norm / meta["radius"],
                    "global_clip_factor": clip,
                    **{k: (v if not isinstance(v, float) or np.isfinite(v) else None)
                       for k, v in audit.items()},
                })
    return {
        "index": index, "metadata": meta,
        "gate": {
            "raw_radius_ratio": float(np.linalg.norm(raw) / meta["radius"]),
            "top_camera": top, "weakest_camera": weakest,
            "top_energy_fraction": float(energy[top] / energy.sum()),
            "removed_total_energy_fraction": float(coefficient**2 / np.sum(raw * raw)),
            "other_cameras_exactly_unchanged": unchanged,
            "recomputed_archived_eigenvector_abs_dot": alignment,
            "archived_direct_gram_relative_error": archived_entry["direct_gram_relative_error"],
        },
        "rows": rows,
        "archive": str(archive), "archive_sha256": record["sha256"],
        "forensic_sha256": sha(forensic_path),
        "seconds": time.perf_counter() - started,
    }


def summarize(cases: list[dict]) -> dict:
    compact = []
    passes = []
    for case in cases:
        control = next(x for x in case["rows"] if x["arm"] == "control" and x["rep"] == 0)
        quotient = next(x for x in case["rows"] if x["arm"] == "quotient" and x["rep"] == 0)
        gain = ((quotient["true_decrease"] - control["true_decrease"])
                / max(abs(control["true_decrease"]), 1e-12))
        check = {
            "index": case["index"],
            "camera34_only": case["gate"]["top_camera"] == 34
                             and case["gate"]["weakest_camera"] == 34,
            "removed_energy_fraction": case["gate"]["removed_total_energy_fraction"],
            "post_raw_radius_ratio": quotient["raw_radius_ratio"],
            "other_cameras_exact": case["gate"]["other_cameras_exactly_unchanged"],
            "relative_true_decrease_gain": gain,
            "rho_delta": quotient["rho"] - control["rho"],
            "eigenvector_alignment": case["gate"]["recomputed_archived_eigenvector_abs_dot"],
        }
        check["passes"] = (
            check["camera34_only"] and check["removed_energy_fraction"] >= .99
            and check["post_raw_radius_ratio"] <= 10 and check["other_cameras_exact"]
            and gain > .0015 and check["rho_delta"] >= -1e-12
            and check["eigenvector_alignment"] >= 1 - 1e-8)
        passes.append(check)
        compact.extend([control, quotient])
    earned = all(x["passes"] for x in passes)
    return {
        "case_checks": passes,
        "native_arm_earned": earned,
        "decision": ("advance quotient projection to native Venice gate" if earned
                     else "stop quotient projection at fixed-state gate"),
        "compact_rows": compact,
    }


def main() -> None:
    cases = [score_case(index) for index in range(5)]
    summary = summarize(cases)
    provenance = {
        "protocol_sha256": sha(PROTOCOL),
        "script_sha256": sha(pathlib.Path(__file__)),
        "input_sha256": sha(BAL),
    }
    (ROOT / "research/eta2_wave6/d20-sloppy-quotient-results.json").write_text(
        json.dumps({"provenance": provenance, "cases": cases}, indent=2) + "\n")
    (ROOT / "research/eta2_wave6/d20-sloppy-quotient-summary.json").write_text(
        json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
