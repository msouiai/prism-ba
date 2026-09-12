#!/usr/bin/env python3
"""CPU-only rigid-cluster projection diagnostic for registered Brief-0 captures.

No optimization, preconditioning, endpoint change, or GPU calls occur here.
The projection metric is ||E^-1 dc||_2, with fixed captured E.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import time

import numpy as np
from scipy.spatial.transform import Rotation


FD_STEP = 1e-5
RANK_RTOL = 1e-10
LLOYD_CAP = 100


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_baseline() -> dict:
    root = Path(__file__).resolve().parents[2] / "eta2_champion"
    manifest = json.loads((root / "source_manifest.json").read_text())
    config = json.loads((root / "champion.json").read_text())
    source_hash = sha256(root / "source/prism_eta2.cu")
    if source_hash != manifest["source_sha256"]:
        raise ValueError("Frozen champion source does not match its manifest")
    for name, expected in manifest["headers_sha256"].items():
        if sha256(root / "source/headers" / name) != expected:
            raise ValueError(f"Frozen champion header mismatch: {name}")
    return dict(source_sha256=source_hash,
                header_count=len(manifest["headers_sha256"]),
                champion_json_sha256=sha256(root / "champion.json"),
                flags=config["flags"], cli=config["cli"],
                binary_not_run=True)


def centers(R: np.ndarray, t: np.ndarray) -> np.ndarray:
    return -np.einsum("nji,nj->ni", R, t)


def _distances(points: np.ndarray, means: np.ndarray) -> np.ndarray:
    # Fixed three-coordinate reduction, rather than BLAS-dependent expansion
    # ||x||^2+||y||^2-2x.y, which also cancels for nearby camera centers.
    d = points[:, None, :] - means[None, :, :]
    return np.sum(d * d, axis=2)


def cluster_centers(C: np.ndarray, requested_k: int) -> tuple[np.ndarray, dict]:
    C = np.asarray(C, dtype=np.float64)
    if C.ndim != 2 or C.shape[1] != 3 or not len(C) or not np.isfinite(C).all():
        raise ValueError("Camera centers must be finite nonempty (n,3)")
    if requested_k < 1:
        raise ValueError("K must be positive")
    n = len(C)
    k = min(requested_k, n)
    if k == n:
        labels = np.arange(n, dtype=np.int64)
        return labels, dict(requested_k=requested_k, capped_k=k, actual_k=k,
                            iterations=0, converged=True, empty_reassignments=0,
                            cluster_sizes=[1] * n, singleton_shortcut=True)
    if k == 1:
        labels = np.zeros(n, dtype=np.int64)
        return labels, dict(requested_k=requested_k, capped_k=1, actual_k=1,
                            iterations=0, converged=True, empty_reassignments=0,
                            cluster_sizes=[n], singleton_shortcut=False)
    # Center coordinates before all geometric arithmetic. No random state.
    normalized = C - C.mean(axis=0)
    first = int(np.argmax(np.sum(normalized * normalized, axis=1)))
    selected = np.zeros(n, dtype=bool)
    selected[first] = True
    seed_ids = [first]
    nearest = np.sum((normalized - normalized[first]) ** 2, axis=1)
    for _ in range(1, k):
        candidates = np.where(selected, -np.inf, nearest)
        index = int(np.argmax(candidates))  # earliest index resolves ties
        seed_ids.append(index)
        selected[index] = True
        nearest = np.minimum(nearest, np.sum((normalized - normalized[index]) ** 2, axis=1))
    means = normalized[seed_ids].copy()
    previous = None
    empty_reassignments = 0
    converged = False
    for iteration in range(1, LLOYD_CAP + 1):
        labels = np.empty(n, dtype=np.int64)
        errors = np.empty(n)
        for start in range(0, n, 2048):
            distances = _distances(normalized[start:start + 2048], means)
            if not np.isfinite(distances).all():
                raise ValueError("Center-distance arithmetic overflow")
            own = np.argmin(distances, axis=1)
            labels[start:start + len(own)] = own
            errors[start:start + len(own)] = distances[np.arange(len(own)), own]
        counts = np.bincount(labels, minlength=k)
        for empty in np.flatnonzero(counts == 0):
            # Split the farthest member of a nonsingleton donor; lowest camera
            # index resolves equal errors. Also works for coincident centers.
            eligible = counts[labels] > 1
            donor = int(np.argmax(np.where(eligible, errors, -np.inf)))
            counts[labels[donor]] -= 1
            labels[donor] = int(empty)
            counts[empty] += 1
            errors[donor] = 0.0
            empty_reassignments += 1
        means = np.asarray([normalized[labels == j].mean(axis=0) for j in range(k)])
        if previous is not None and np.array_equal(labels, previous):
            converged = True
            break
        previous = labels.copy()
    return labels, dict(requested_k=requested_k, capped_k=k, actual_k=len(np.unique(labels)),
                        iterations=iteration, converged=converged,
                        empty_reassignments=empty_reassignments,
                        cluster_sizes=np.bincount(labels, minlength=k).tolist(),
                        initialization_camera_ids=seed_ids, singleton_shortcut=False)


def similarity_action(R: np.ndarray, C: np.ndarray, centroid: np.ndarray,
                      parameters: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """World action with mode order omega(3), world translation(3), log scale."""
    parameters = np.asarray(parameters, dtype=np.float64)
    Q = Rotation.from_rotvec(parameters[:3]).as_matrix()
    scale = np.exp(parameters[6])
    moved_C = centroid + scale * ((C - centroid) @ Q.T) + parameters[3:6]
    moved_R = R @ Q.T
    moved_t = -np.einsum("nij,nj->ni", moved_R, moved_C)
    return moved_R, moved_t, moved_C


def finite_difference_modes(R: np.ndarray, t: np.ndarray,
                            step: float = FD_STEP) -> tuple[np.ndarray, dict]:
    """Differentiate the exact world action in the solver's left-SO(3) chart."""
    C = centers(R, t)
    centroid = C.mean(axis=0)
    n = len(R)
    result = np.zeros((n, 9, 7))
    analytic = np.zeros_like(result)
    per_mode_error = []
    for mode in range(7):
        parameter = np.zeros(7)
        parameter[mode] = step
        Rp, _, _ = similarity_action(R, C, centroid, parameter)
        Rm, _, _ = similarity_action(R, C, centroid, -parameter)
        def native_translation_increment(a):
            # Exact algebra for t_new-t at C=-R^T t. Computing both huge t_new
            # values and subtracting them loses translation modes on Final3068.
            # This also leaves singleton log-scale modes exactly zero.
            Q = Rotation.from_rotvec(a[:3]).as_matrix()
            world_delta = (-np.expm1(a[6]) * (C - centroid)
                           + (np.eye(3) - Q.T) @ centroid - Q.T @ a[3:6])
            return np.einsum("nij,nj->ni", R, world_delta)
        tp = native_translation_increment(parameter)
        tm = native_translation_increment(-parameter)
        # The native increment satisfies Exp(dw) R = R_new.
        plus_w = Rotation.from_matrix(Rp @ R.transpose(0, 2, 1)).as_rotvec()
        minus_w = Rotation.from_matrix(Rm @ R.transpose(0, 2, 1)).as_rotvec()
        result[:, :3, mode] = (plus_w - minus_w) / (2 * step)
        result[:, 3:6, mode] = (tp - tm) / (2 * step)
        unit = np.zeros(7)
        unit[mode] = 1.0
        omega, v, scale = unit[:3], unit[3:6], unit[6]
        analytic[:, :3, mode] = -np.einsum("nij,j->ni", R, omega)
        analytic[:, 3:6, mode] = np.einsum("nij,nj->ni", R,
                                                    np.cross(omega, centroid) - v - scale * (C - centroid))
        error = np.linalg.norm(result[:, :, mode] - analytic[:, :, mode])
        denominator = max(np.linalg.norm(analytic[:, :, mode]), 1.0)
        per_mode_error.append(float(error / denominator))
    return result, dict(centroid=centroid.tolist(), fd_step=step,
                        finite_difference_vs_analytic_scaled_errors=per_mode_error,
                        max_fd_analytic_error=max(per_mode_error))


def build_blocks(R: np.ndarray, t: np.ndarray, E: np.ndarray,
                 labels: np.ndarray) -> tuple[list[dict], dict]:
    blocks = []
    rows = []
    for cluster in np.unique(labels):
        ids = np.flatnonzero(labels == cluster)
        raw, check = finite_difference_modes(R[ids], t[ids])
        scaled = (raw / E[ids, :, None]).reshape(-1, 7)
        raw_singular = np.linalg.svd(scaled, compute_uv=False)
        column_norms = np.linalg.norm(scaled, axis=0)
        normalized = np.zeros_like(scaled)
        nonzero = column_norms > 0
        normalized[:, nonzero] = scaled[:, nonzero] / column_norms[nonzero]
        U, singular, _ = np.linalg.svd(normalized, full_matrices=False)
        threshold = float(singular[0] * RANK_RTOL) if singular.size else 0.0
        rank = int(np.sum(singular > threshold))
        Q = U[:, :rank]
        blocks.append(dict(ids=ids, Q=Q))
        rows.append(dict(cluster=int(cluster), camera_ids=ids.tolist(), rank=rank,
                         singular_values=raw_singular.tolist(),
                         column_normalized_singular_values=singular.tolist(),
                         scaled_column_norms=column_norms.tolist(), rank_threshold=threshold,
                         **check))
    return blocks, dict(clusters=rows, rank=sum(x["rank"] for x in rows),
                        max_fd_analytic_error=max(x["max_fd_analytic_error"] for x in rows))


def project_blocks(vector: np.ndarray, blocks: list[dict]) -> np.ndarray:
    answer = np.zeros_like(vector)
    for block in blocks:
        ids, Q = block["ids"], block["Q"]
        local = vector[ids].reshape(-1)
        answer[ids] = (Q @ (Q.T @ local)).reshape(-1, 9)
    return answer


def projection_report(delta: np.ndarray, blocks: list[dict], global_blocks: list[dict],
                      reference_scale: float) -> dict:
    norm = float(np.linalg.norm(delta))
    zero_threshold = float(100 * np.finfo(float).eps * max(reference_scale, 1.0))
    projection = project_blocks(delta, blocks)
    global_part = project_blocks(delta, global_blocks)
    nonglobal = delta - global_part
    nonglobal_norm = float(np.linalg.norm(nonglobal))
    remaining_projection = project_blocks(nonglobal, blocks)
    pn = float(np.linalg.norm(projection))
    gn = float(np.linalg.norm(global_part))
    ngpn = float(np.linalg.norm(remaining_projection))
    return dict(norm=norm, projected_norm=pn,
                fraction=None if norm <= zero_threshold else pn / norm,
                near_zero_threshold=zero_threshold,
                negligible_difference=norm <= zero_threshold,
                global_similarity_norm=gn,
                global_similarity_fraction=None if norm <= zero_threshold else gn / norm,
                after_global_removal_norm=nonglobal_norm,
                after_global_removal_fraction=(None if nonglobal_norm <= zero_threshold
                                               else ngpn / nonglobal_norm),
                extrinsic_norm=float(np.linalg.norm(delta[:, :6])),
                intrinsic_norm=float(np.linalg.norm(delta[:, 6:])),
                orthogonal_residual_norm=float(np.linalg.norm(delta - projection)))


def read_metadata(path: Path) -> dict[str, float]:
    result = {}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = float(value)
    return result


def read_array(path: Path, shape: tuple[int, ...]) -> np.ndarray:
    size = int(np.prod(shape))
    if path.stat().st_size != 8 * size:
        raise ValueError(f"{path}: expected {8 * size} bytes for {shape}")
    data = np.fromfile(path, dtype="<f8").reshape(shape)
    if not np.isfinite(data).all():
        raise ValueError(f"Nonfinite input in {path}")
    return data


def diagnose_capture(folder: Path, requested=(8, 32, 128)) -> dict:
    folder = folder.resolve()
    start = time.perf_counter()
    baseline = verify_baseline()
    meta = read_metadata(folder / "metadata.txt")
    nc, np_ = int(meta["ncam"]), int(meta["npt"])
    if nc < 1 or np_ < 0 or nc != meta["ncam"] or np_ != meta["npt"]:
        raise ValueError("Invalid capture dimensions")
    shapes = {"R_state.f64": (nc, 3, 3), "t_state.f64": (nc, 3),
              "X_state.f64": (np_, 3), "intr_state.f64": (3, nc), "E.f64": (nc, 9),
              "eta2_raw_scaled.f64": (nc, 9), "eta2-0.step": (9 * nc + 3 * np_,)}
    arrays = {name: read_array(folder / name, shape) for name, shape in shapes.items()}
    R, t, E = arrays["R_state.f64"], arrays["t_state.f64"], arrays["E.f64"]
    if np.any(E <= 0):
        raise ValueError("Captured E must be positive on all stored camera slots")
    if np.any(arrays["intr_state.f64"][2] != 0):
        raise ValueError("Capture changes the registered k2=0 objective")
    rotation_error = float(np.max(np.abs(R @ R.transpose(0, 2, 1) - np.eye(3))))
    if rotation_error > 1e-7 or np.any(np.linalg.det(R) < 0.999999):
        raise ValueError("Captured camera matrices are not proper rotations")
    eta = arrays["eta2-0.step"][:9 * nc].reshape(nc, 9)
    if np.any(eta[:, 8] != 0):
        raise ValueError("Eta2 step changes k2")
    input_paths = [folder / "metadata.txt"] + [folder / name for name in shapes]
    native_scores = {}
    if (folder / "native_directions.csv").exists():
        with (folder / "native_directions.csv").open(newline="") as stream:
            for row in csv.DictReader(stream):
                native_scores[(row["arm"], int(row["rep"]))] = row
        input_paths.append(folder / "native_directions.csv")
    references = []
    for exact_path in sorted(folder.glob("exact-*.step"),
                             key=lambda p: int(p.stem.split("-")[-1])):
        repeat = int(exact_path.stem.split("-")[-1])
        clip_path = folder / f"exact_clip-{repeat}.step"
        exact = read_array(exact_path, (9 * nc + 3 * np_,))[:9 * nc].reshape(nc, 9)
        clipped = read_array(clip_path, (9 * nc + 3 * np_,))[:9 * nc].reshape(nc, 9)
        if np.any(exact[:, 8] != 0) or np.any(clipped[:, 8] != 0):
            raise ValueError("Reference step changes k2")
        # Saved raw CG vector has the positive-gradient solve convention.
        # Physical raw camera tangent is minus E times that vector.
        deltas = {"exact_minus_eta2": exact / E - eta / E,
                  "exact_clip_minus_eta2": clipped / E - eta / E,
                  "exact_minus_eta2_raw": exact / E + arrays["eta2_raw_scaled.f64"]}
        scale = max(np.linalg.norm(exact / E), np.linalg.norm(clipped / E),
                    np.linalg.norm(eta / E), np.linalg.norm(arrays["eta2_raw_scaled.f64"]))
        references.append(dict(repeat=repeat, deltas=deltas, scale=float(scale),
                               native_reference_record=native_scores.get(("exact", repeat))))
        input_paths.extend([exact_path, clip_path])
    if not references:
        raise ValueError("No completed exact-N.step/exact_clip-N.step reference pair")
    C = centers(R, t)
    global_blocks, global_info = build_blocks(R, t, E, np.zeros(nc, dtype=np.int64))
    result = dict(schema_version=1, capture=str(folder), metadata=meta,
                  implementation_sha256=sha256(Path(__file__)),
                  baseline=baseline, settings=dict(K=list(requested), fd_step=FD_STEP,
                  native_translation_difference="algebraic increment, avoiding subtraction of huge translated states",
                  rank_relative_threshold=RANK_RTOL, lloyd_cap=LLOYD_CAP),
                  metric="Euclidean in z=E^-1 dc; equivalent native camera Dc metric",
                  mode_order=["world_rotation_x", "world_rotation_y", "world_rotation_z",
                              "world_translation_x", "world_translation_y", "world_translation_z", "log_scale"],
                  rotation_orthogonality_max_abs=rotation_error,
                  global_similarity_basis=global_info, cells=[],
                  caveats=["Camera projections only; point differences are not projected.",
                           "Global similarity modes are retained and separately reported; damping means they are not exact null modes.",
                           "K=ncam generally spans every extrinsic camera direction and may make a high fraction trivial.",
                           "Projection fraction is not a model-decrease, target-hit, spectral, or speed certificate.",
                           "Uncertified or missing reference certification cannot establish the solve-branch decision.",
                           "After-global-removal projects the residual onto the full cluster span; finite-difference gauge-containment error is reported."])
    for k in requested:
        cell_start = time.perf_counter()
        labels, cluster_info = cluster_centers(C, k)
        blocks, basis_info = build_blocks(R, t, E, labels)
        containment = 0.0
        global_Q = global_blocks[0]["Q"]
        for col in range(global_Q.shape[1]):
            g = global_Q[:, col].reshape(nc, 9)
            containment = max(containment, float(np.linalg.norm(g - project_blocks(g, blocks))))
        rows = []
        for reference in references:
            rows.append(dict(repeat=reference["repeat"],
                             native_reference_record=reference["native_reference_record"],
                             differences={name: projection_report(delta, blocks, global_blocks, reference["scale"])
                                          for name, delta in reference["deltas"].items()}))
        result["cells"].append(dict(clustering=cluster_info, basis=basis_info,
                                    global_basis_max_unrepresented_norm=containment,
                                    rank_fraction_of_extrinsic_dimension=basis_info["rank"] / (6 * nc),
                                    references=rows, diagnostic_cpu_seconds=time.perf_counter() - cell_start))
    result["input_sha256"] = {str(p.relative_to(folder)): sha256(p) for p in input_paths}
    result["diagnostic_cpu_seconds_including_loading_hashes"] = time.perf_counter() - start
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite existing diagnostic: {args.output}")
    result = diagnose_capture(args.capture)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(args.output)


if __name__ == "__main__":
    main()
