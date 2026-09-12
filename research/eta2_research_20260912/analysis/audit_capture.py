#!/usr/bin/env python3
"""Independent CPU audit of Brief 0 fixed-state native directions.

No optimizer rollout, witness selection, policy tuning, GPU access or acceptance
decision. See ../PROTOCOL_00.md. True scores retain every original observation.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

import numpy as np

CHART_FILE = Path(__file__).resolve().parents[1] / "charts/reference.py"
SPEC = importlib.util.spec_from_file_location("eta2_chart_reference", CHART_FILE)
CHART = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = CHART
SPEC.loader.exec_module(CHART)
CameraState = CHART.CameraState
project_jacobian = CHART.project_jacobian


def file_sha256(path: Path) -> str:
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def read_metadata(path: Path) -> dict:
    out = {}
    for line in path.read_text().splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = float(value.strip())
    for name in ("ncam", "npt", "nobs"):
        if out[name] != int(out[name]) or out[name] < 1:
            raise ValueError(f"Invalid capture dimension {name}")
    return out


def map_f64(path: Path, shape: tuple) -> np.ndarray:
    expected = int(np.prod(shape)) * 8
    if path.stat().st_size != expected:
        raise ValueError(f"Wrong byte length for {path}: {path.stat().st_size} != {expected}")
    return np.memmap(path, mode="r", dtype="<f8", shape=shape)


def load_capture_state(capture: Path) -> tuple[CameraState, np.ndarray, dict]:
    meta = read_metadata(capture / "metadata.txt")
    nc, npt = int(meta["ncam"]), int(meta["npt"])
    R = map_f64(capture / "R_state.f64", (nc, 3, 3))
    t = map_f64(capture / "t_state.f64", (nc, 3))
    X = map_f64(capture / "X_state.f64", (npt, 3))
    intr = map_f64(capture / "intr_state.f64", (3, nc)).T
    if not np.isfinite(X).all():
        raise ValueError("Nonfinite captured point state")
    return CameraState(R, t, intr), X, meta


def read_native_rows(path: Path) -> list[dict]:
    out = []
    with path.open() as f:
        for row in csv.DictReader(f):
            converted = {}
            for key, value in row.items():
                if key in ("arm", "reason"):
                    converted[key] = value
                elif key in ("rep", "pcg_iterations", "certified"):
                    converted[key] = int(value)
                else:
                    converted[key] = float(value)
            out.append(converted)
    if len({(row["arm"], row["rep"]) for row in out}) != len(out):
        raise ValueError("Duplicate native arm/rep rows")
    return out


def geometry(cameras: CameraState, X: np.ndarray, ci: np.ndarray, pi: np.ndarray,
             pair_block: int = 256) -> dict:
    """Exact max viewing-ray angle, with bounded pairwise temporary storage.

    The scene radius is max camera distance from the arithmetic mean center.
    It is a displacement scale, not the saved scaled-camera trust radius.
    """
    start = time.perf_counter()
    centers = cameras.centers()
    center = np.mean(centers, axis=0)
    radius = float(np.max(np.linalg.norm(centers - center, axis=1)))
    npt = len(X)
    counts = np.bincount(pi, minlength=npt)
    order = np.argsort(pi, kind="stable")
    offsets = np.concatenate(([0], np.cumsum(counts)))
    angle = np.full(npt, np.nan)
    pair_count = 0
    for j in np.flatnonzero(counts >= 2):
        observed = ci[order[offsets[j]:offsets[j + 1]]]
        rays = X[j] - centers[observed]
        norm = np.linalg.norm(rays, axis=1)
        if np.any(norm == 0) or not np.isfinite(norm).all():
            continue
        rays /= norm[:, None]
        least_dot = 1.0
        # All unordered cross-camera pairs, including repeated camera entries.
        for a in range(0, len(rays), pair_block):
            ra = rays[a:a + pair_block]
            for b in range(0, a + 1, pair_block):
                rb = rays[b:b + pair_block]
                dots = ra @ rb.T
                least_dot = min(least_dot, float(np.min(dots)))
        angle[j] = np.degrees(np.arccos(np.clip(least_dot, -1.0, 1.0)))
        pair_count += len(rays) * (len(rays) - 1) // 2
    return {"centers": centers, "camera_center_centroid": center,
            "scene_radius": radius, "track_lengths": counts,
            "parallax_degrees": angle, "parallax_geometric_pairs": pair_count,
            "cpu_geometry_seconds": time.perf_counter() - start}


def _objective_terms(residual: np.ndarray) -> np.ndarray:
    with np.errstate(over="ignore", invalid="ignore"):
        sq = .5 * np.einsum("ni,ni->n", residual, residual)
    return np.where(np.isfinite(sq), sq, np.inf)


def _residual(cameras, X_obs, ci, uv):
    Y = np.einsum("nij,nj->ni", cameras.R[ci], X_obs) + cameras.t[ci]
    pred, dY, d_intr = project_jacobian(Y, cameras.intrinsics[ci])
    return pred - uv, Y, dY, d_intr


def _sum(values) -> float:
    return float(np.sum(values, dtype=np.longdouble))


def error_stats(values: np.ndarray, mask: np.ndarray | None = None) -> dict:
    a = values if mask is None else values[mask]
    finite = np.isfinite(a)
    pos = a > 0; neg = a < 0
    return {"points": int(len(a)), "nonfinite_points": int(np.count_nonzero(~finite)),
            "signed_sum": _sum(a), "absolute_sum": _sum(np.abs(a)),
            "positive_sum": _sum(a[pos]), "negative_sum": _sum(a[neg]),
            "positive_points": int(np.count_nonzero(pos)), "negative_points": int(np.count_nonzero(neg))}


def error_bins(values: np.ndarray, track_lengths: np.ndarray, parallax: np.ndarray) -> dict:
    length_masks = {"0-1": track_lengths <= 1, "2": track_lengths == 2,
                    "3-5": (track_lengths >= 3) & (track_lengths <= 5), ">5": track_lengths > 5}
    angle_masks = {"<1deg": parallax < 1, "1-5deg": (parallax >= 1) & (parallax <= 5),
                   ">5deg": parallax > 5, "undefined": ~np.isfinite(parallax)}
    return {"track_length": {name: error_stats(values, mask) for name, mask in length_masks.items()},
            "parallax": {name: error_stats(values, mask) for name, mask in angle_masks.items()}}


def roundoff_compare(cpu, native, scale, *, absolute_tolerance=1e-8,
                     relative_tolerance=5e-10) -> dict:
    """Heuristic agreement budget; explicitly not an interval-arithmetic bound.

    For prediction, scale is sum(abs(r*Jd)) + .5 sum((Jd)^2), so cancellation
    does not convert a tiny prediction into a meaningless relative discrepancy.
    """
    if native is None:
        return {"status": "unavailable", "cpu": cpu, "native": None}
    if not np.isfinite(cpu) or not np.isfinite(native) or not np.isfinite(scale):
        return {"status": "nonfinite", "cpu": cpu, "native": native, "scale": scale}
    tolerance = absolute_tolerance + relative_tolerance * max(1., abs(scale))
    error = abs(cpu - native)
    return {"status": "within_budget" if error <= tolerance else "mismatch", "cpu": cpu,
            "native": native, "absolute_error": error, "normalization_scale": scale,
            "normalized_error": error / max(1., abs(scale)), "tolerance": tolerance}


def audit_direction(cameras: CameraState, X: np.ndarray, ci: np.ndarray, pi: np.ndarray,
                    uv: np.ndarray, step: np.ndarray, meta: dict, geom: dict,
                    native: dict, *, chunk_size: int = 50000,
                    Cdiag: np.ndarray | None = None) -> tuple[dict, dict]:
    start = time.perf_counter()
    nc, npt = len(cameras.R), len(X)
    if step.shape != (9 * nc + 3 * npt,):
        raise ValueError("Direction shape mismatch")
    dc = step[:9 * nc].reshape(nc, 9)
    dp = step[9 * nc:].reshape(npt, 3)
    certified = bool(native.get("certified", 0))
    exact_arm = native["arm"].startswith("exact")
    base = {"arm": native["arm"], "rep": native["rep"], "native": native,
            "source_reference_solve_certified": certified if exact_arm else None,
            "direction_label": ("reference_with_certified_reduced_residual" if certified else "approximate_reference")
                              if exact_arm else "native_inexact",
            "clipped": native["arm"] == "exact_clip",
            "linear_certificate_applies_to": "source_unclipped_camera_solve" if exact_arm else None}
    if not np.isfinite(step).all() or np.any(dc[:, 8] != 0):
        base.update({"valid_finite_direction": False, "error": "nonfinite step or changed k2",
                     "nonfinite_step_entries": int(np.count_nonzero(~np.isfinite(step))),
                     "eligible_for_solve_model_conclusion": False})
        return base, {}
    proposed = cameras.retract(dc)
    costs = {key: np.longdouble(0) for key in ("initial", "full", "camera", "point")}
    decreases = {key: np.longdouble(0) for key in ("full", "camera", "point")}
    predictions = {key: np.longdouble(0) for key in ("full", "camera", "point")}
    pred_scales = {key: np.longdouble(0) for key in ("full", "camera", "point")}
    errors = {key: np.zeros(npt) for key in ("full", "camera", "point")}
    invalid_projection = {key: 0 for key in costs}
    behind = {key: 0 for key in costs}
    horizons = {key: 0 for key in costs}
    flips = {key: 0 for key in decreases}
    # Per-point flip counts refer to the full proposal only; all observations scored.
    point_flips = np.zeros(npt, dtype=np.int64)
    point_rhs = np.zeros((npt, 3))
    point_equation = np.zeros((npt, 3))
    point_diagonal = np.zeros((npt, 3)) if Cdiag is None else Cdiag
    for offset in range(0, len(ci), chunk_size):
        sl = slice(offset, offset + chunk_size)
        oi, oj, obs = ci[sl], pi[sl], uv[sl]
        xo = X[oj]
        r0, Y0, dY, d_intr = _residual(cameras, xo, oi, obs)
        RX = np.einsum("nij,nj->ni", cameras.R[oi], xo)
        camera_displacement = np.cross(dc[oi, :3], RX) + dc[oi, 3:6]
        yc = np.einsum("nij,nj->ni", dY, camera_displacement)
        yc += np.einsum("nij,nj->ni", d_intr, dc[oi, 6:9])
        point_displacement = np.einsum("nij,nj->ni", cameras.R[oi], dp[oj])
        yp = np.einsum("nij,nj->ni", dY, point_displacement)
        Jp = dY @ cameras.R[oi]
        rhs_residual = r0 + yc
        full_linear_residual = rhs_residual + yp
        for coordinate in range(3):
            jp = Jp[:, :, coordinate]
            point_rhs[:, coordinate] -= np.bincount(oj, weights=np.einsum("ni,ni->n", jp, rhs_residual), minlength=npt)
            point_equation[:, coordinate] += np.bincount(oj, weights=np.einsum("ni,ni->n", jp, full_linear_residual), minlength=npt)
            if Cdiag is None:
                point_diagonal[:, coordinate] += np.bincount(oj, weights=np.einsum("ni,ni->n", jp, jp), minlength=npt)
        costs["initial"] += np.sum(_objective_terms(r0), dtype=np.longdouble)
        invalid_projection["initial"] += int(np.count_nonzero(~np.isfinite(r0).all(axis=1)))
        behind["initial"] += int(np.count_nonzero(Y0[:, 2] > 0))
        horizons["initial"] += int(np.count_nonzero(Y0[:, 2] == 0))
        for name, cams, points, jd in (("full", proposed, xo + dp[oj], yc + yp),
                                       ("camera", proposed, xo, yc),
                                       ("point", cameras, xo + dp[oj], yp)):
            r1, Y1, _, _ = _residual(cams, points, oi, obs)
            invalid_projection[name] += int(np.count_nonzero(~np.isfinite(r1).all(axis=1)))
            behind[name] += int(np.count_nonzero(Y1[:, 2] > 0))
            horizons[name] += int(np.count_nonzero(Y1[:, 2] == 0))
            flip = np.isfinite(Y1[:, 2]) & np.isfinite(Y0[:, 2]) & (Y0[:, 2] * Y1[:, 2] < 0)
            flips[name] += int(np.count_nonzero(flip))
            if name == "full":
                point_flips += np.bincount(oj, weights=flip, minlength=npt).astype(np.int64)
            cost1 = _objective_terms(r1)
            costs[name] += np.sum(cost1, dtype=np.longdouble)
            with np.errstate(over="ignore", invalid="ignore"):
                # Stable difference of squared residuals before global reduction.
                delta_cost = .5 * np.einsum("ni,ni->n", r1 - r0, r1 + r0)
                linear = np.einsum("ni,ni->n", r0, jd)
                quad = .5 * np.einsum("ni,ni->n", jd, jd)
                pred = -linear - quad
                error = delta_cost + pred
            decreases[name] -= np.sum(delta_cost, dtype=np.longdouble)
            predictions[name] += np.sum(pred, dtype=np.longdouble)
            pred_scales[name] += np.sum(np.abs(r0 * jd), dtype=np.longdouble) + np.sum(quad, dtype=np.longdouble)
            errors[name] += np.bincount(oj, weights=error, minlength=npt)
    errors["cross"] = errors["full"] - errors["camera"] - errors["point"]
    scores = {name: float(value) for name, value in costs.items()}
    pred = {name: float(value) for name, value in predictions.items()}
    decrease = {name: float(value) for name, value in decreases.items()}
    rho = {name: decrease[name] / pred[name] if pred[name] != 0 else float("nan") for name in pred}
    checks = {
        "initial_cost": roundoff_compare(scores["initial"], meta.get("cost"), scores["initial"]),
        "candidate_cost": roundoff_compare(scores["full"], native.get("cost"), scores["full"]),
        "prediction": roundoff_compare(pred["full"], native.get("prediction"), float(pred_scales["full"])),
        "true_decrease": roundoff_compare(decrease["full"], native.get("decrease"), scores["initial"] + scores["full"]),
    }
    point_error = errors["point"]
    # Deterministic tie-break by point index; nonfinite errors rank first.
    ranking_magnitude = np.nan_to_num(np.abs(point_error), nan=np.inf, posinf=np.inf)
    ranking = np.lexsort((np.arange(npt), -ranking_magnitude))
    top = ranking[:min(200, npt)]
    total_abs = _sum(abs(point_error))
    top_abs = _sum(abs(point_error[top]))
    fraction = top_abs / total_abs if np.isfinite(total_abs) and total_abs > 0 else None
    displacement = np.linalg.norm(dp, axis=1)
    tau = meta.get("tau", meta["lambda"])
    damping_floor = tau * np.sum(point_diagonal, axis=1) / 3
    damping_floor = np.where(damping_floor > 0, damping_floor, 1e-32)
    point_damping = np.maximum(tau * point_diagonal, 1e-3 * damping_floor[:, None])
    point_equation += point_damping * dp
    equation_norm = float(np.linalg.norm(point_equation))
    rhs_norm = float(np.linalg.norm(point_rhs))
    point_equation_stats = {"absolute_residual_norm": equation_norm,
                            "rhs_norm": rhs_norm,
                            "relative_residual_norm": equation_norm / max(rhs_norm, 1e-300),
                            "maximum_point_absolute_residual_norm": float(np.max(np.linalg.norm(point_equation, axis=1))),
                            "diagonal_source": "saved_Cdiag" if Cdiag is not None else "recomputed_FP64_Jp",
                            "tau": tau, "tau_equals_lambda": tau == meta["lambda"],
                            "equation": "Jp^T (r+Jc dc+Jp dp) + diag(damping) dp = 0",
                            "scope": "independent residual of this actual direction, including clipped back-substitution; no stationarity certificate"}
    allchecks = all(v["status"] == "within_budget" for v in checks.values())
    finite = all(np.isfinite(v) for v in scores.values()) and all(np.isfinite(v) for v in pred.values())
    base.update({
        "valid_finite_direction": True, "finite_scores_and_predictions": finite,
        "eligible_for_solve_model_conclusion": bool(finite and allchecks and (certified or not exact_arm)),
        "costs": scores, "predictions": pred, "true_decreases": decrease, "rho": rho,
        "prediction_absolute_term_scales": {name: float(v) for name, v in pred_scales.items()},
        "native_agreement": checks,
        "model_error": {name: error_stats(v) for name, v in errors.items()},
        "point_error_bins": error_bins(point_error, geom["track_lengths"], geom["parallax_degrees"]),
        "top200_absolute_point_error": {"count": len(top), "absolute_sum": top_abs,
                                         "signed_sum": _sum(point_error[top]), "fraction_of_absolute_point_error": fraction,
                                         "point_indices": top.tolist(),
                                         "point_signed_errors": point_error[top].tolist(),
                                         "track_lengths": geom["track_lengths"][top].tolist(),
                                         "parallax_degrees": geom["parallax_degrees"][top].tolist()},
        "flings": {"scene_radius": geom["scene_radius"],
                    "count": int(np.count_nonzero(displacement > geom["scene_radius"])),
                    "maximum_displacement": float(np.max(displacement)),
                    "median_displacement": float(np.median(displacement)),
                    "p95_displacement": float(np.quantile(displacement, .95))},
        "cheirality_flip_observations": flips, "behind_camera_observations": behind,
        "projection_horizon_observations": horizons,
        "invalid_projection_observations": invalid_projection,
        "point_equation": point_equation_stats,
        "cpu_audit_seconds": time.perf_counter() - start,
    })
    arrays = {"D_full": errors["full"], "D_camera": errors["camera"],
              "D_point": errors["point"], "D_cross": errors["cross"],
              "euclidean_displacement": displacement, "full_cheirality_flip_count": point_flips}
    return base, arrays


def source_certification_screen(rows: list[dict]) -> dict:
    """Conservative per-repeat rho screen, not an attribution or performance verdict."""
    eta = next((row for row in rows if row["arm"] == "eta2"), None)
    if eta is None or not eta.get("eligible_for_solve_model_conclusion"):
        return {"status": "unresolved", "reason": "No finite independently agreeing Eta2 direction"}
    by_key = {(row["arm"], row["rep"]): row for row in rows}
    comparisons = []
    for row in rows:
        if row["arm"] != "exact":
            continue
        clip = by_key.get(("exact_clip", row["rep"]))
        if not row.get("eligible_for_solve_model_conclusion"):
            classification = "unresolved_uncertified_or_audit_mismatch"
        else:
            erho, qrho = eta["rho"]["full"], row["rho"]["full"]
            if erho < .1 and qrho > .5:
                if clip and clip.get("eligible_for_solve_model_conclusion") and clip["rho"]["full"] > .5:
                    classification = "solve_branch_supported_at_same_radius"
                else:
                    classification = "unclipped_reference_helped_radius_role_unresolved"
            elif erho < .1 and qrho < .1:
                classification = "both_model_ratios_poor_inspect_signed_decomposition"
            elif erho >= .1 and qrho >= .1:
                classification = "both_model_ratios_adequate_inspect_absolute_progress_and_radius"
            else:
                classification = "mixed_rho_regime"
        comparisons.append({"rep": row["rep"], "classification": classification})
    return {"status": "mechanism_screen_only", "comparisons": comparisons,
            "warning": "No causal block attribution, hit-rate claim, or solver promotion follows from this screen"}


def sanitize(value):
    """Preserve nonfinite status explicitly without nonstandard JSON numeric tokens."""
    if isinstance(value, dict):
        return {str(k): sanitize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize(v) for v in value]
    if isinstance(value, np.ndarray):
        return sanitize(value.tolist())
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (float, np.floating)) and not np.isfinite(value):
        return "NaN" if np.isnan(value) else ("Infinity" if value > 0 else "-Infinity")
    return value


def audit_capture(capture_dir: str | Path, bal_path: str | Path, *, output_path: str | Path | None = None,
                  chunk_size: int = 50000, save_point_arrays: bool = False,
                  per_capture_array_budget_mib: float = 20) -> dict:
    start = time.perf_counter()
    capture, bal = Path(capture_dir), Path(bal_path)
    cameras, X, meta = load_capture_state(capture)
    diagonal_path = capture / "Cdiag.f64"
    Cdiag = map_f64(diagonal_path, (len(X), 3)) if diagonal_path.exists() else None
    ci, pi, uv, dims = CHART.load_observations(bal)
    expected = (int(meta["ncam"]), int(meta["npt"]), int(meta["nobs"]))
    if dims != expected:
        raise ValueError("BAL and capture dimensions disagree")
    if np.any(ci < 0) or np.any(ci >= dims[0]) or np.any(pi < 0) or np.any(pi >= dims[1]):
        raise ValueError("Invalid observation indices")
    if not np.isfinite(uv).all():
        raise ValueError("Nonfinite observations")
    native_rows = read_native_rows(capture / "native_directions.csv")
    geom = geometry(cameras, X, ci, pi)
    rows, archives = [], []
    consumed = 0
    budget = int(per_capture_array_budget_mib * 1024**2)
    outpath = Path(output_path) if output_path is not None else None
    for native in native_rows:
        arm, rep = native["arm"], native["rep"]
        path = capture / f"{arm}-{rep}.step"
        step = map_f64(path, (9 * dims[0] + 3 * dims[1],))
        row, arrays = audit_direction(cameras, X, ci, pi, uv, step, meta, geom, native,
                                     chunk_size=chunk_size, Cdiag=Cdiag)
        row["direction_sha256"] = file_sha256(path)
        rows.append(row)
        if save_point_arrays and arrays:
            # No all-arm in-memory retention. Raw byte bound + conservative ZIP
            # overhead bounds each file without making and deleting large files.
            arrays.update({"track_length": geom["track_lengths"], "parallax_degrees": geom["parallax_degrees"]})
            worst_bytes = sum(v.nbytes for v in arrays.values()) + 65536
            if outpath is None:
                archives.append({"arm": arm, "rep": rep, "status": "skipped_no_output_directory"})
            elif consumed + worst_bytes > budget:
                archives.append({"arm": arm, "rep": rep, "status": "skipped_budget",
                                 "raw_plus_overhead_bound": worst_bytes, "remaining_bytes": budget - consumed})
            else:
                archive = outpath.with_name(outpath.stem + f"-{arm}-{rep}-points.npz")
                archive.parent.mkdir(parents=True, exist_ok=True)
                np.savez_compressed(archive, **arrays)
                size = archive.stat().st_size
                if size > worst_bytes:
                    raise RuntimeError("Unexpected compressed archive bound violation")
                consumed += size
                archives.append({"arm": arm, "rep": rep, "status": "saved", "path": str(archive),
                                 "bytes": size, "sha256": file_sha256(archive)})
    filenames = ("metadata.txt", "native_directions.csv", "R_state.f64", "t_state.f64", "X_state.f64", "intr_state.f64")
    report = {
        "kind": "Brief0 fixed-state independent CPU audit", "capture": str(capture), "bal": str(bal),
        "capture_sha256": {name: file_sha256(capture / name) for name in filenames},
        "source_sha256": file_sha256(Path(__file__)), "chart_reference_sha256": file_sha256(CHART_FILE),
        "baseline_verification": CHART.verify_frozen_baseline(), "metadata": meta,
        "objective": "All original SIMPLE_RADIAL pixel observations; unshared intrinsics; k2=0; no robust loss or cheirality rejection",
        "geometry": {name: value for name, value in geom.items()
                     if name not in ("centers", "track_lengths", "parallax_degrees")},
        "radius_definition": "max_i ||C_i - mean(C)||_2, C_i=-R_i^T t_i, initial witness state; distinct from controller radius",
        "parallax_definition": "initial maximum angle between X_j-C_i rays over all observation pairs, no absolute-dot folding; tracks<2 undefined",
        "agreement_tolerance": {"relative": 5e-10, "absolute": 1e-8,
                                "prediction_scale": "sum abs(r_l (Jd)_l) + 0.5 sum (Jd)_l^2",
                                "decrease_scale": "CPU initial plus candidate cost", "certified_error_bound": False},
        "rows": rows, "source_certification_screen": source_certification_screen(rows),
        "point_array_archives": archives, "point_array_bytes": consumed,
        "cpu_total_seconds": time.perf_counter() - start,
        "scope": "Fixed-state diagnostic only; instrumented/CPU elapsed time is not native solver performance",
    }
    report = sanitize(report)
    if outpath is not None:
        outpath.parent.mkdir(parents=True, exist_ok=True)
        outpath.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", required=True, type=Path)
    parser.add_argument("--bal", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--chunk-size", type=int, default=50000)
    parser.add_argument("--save-point-arrays", action="store_true")
    parser.add_argument("--point-array-budget-mib", type=float, default=20)
    args = parser.parse_args()
    if args.chunk_size <= 0 or args.point_array_budget_mib < 0:
        parser.error("chunk size must be positive and archive budget nonnegative")
    report = audit_capture(args.capture, args.bal, output_path=args.output, chunk_size=args.chunk_size,
                           save_point_arrays=args.save_point_arrays,
                           per_capture_array_budget_mib=args.point_array_budget_mib)
    print(json.dumps({"output": str(args.output), "directions": len(report["rows"]),
                      "screen": report["source_certification_screen"],
                      "cpu_seconds": report["cpu_total_seconds"]}, indent=2))


if __name__ == "__main__":
    main()
