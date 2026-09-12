#!/usr/bin/env python3
"""Meaningful CPU checks of native tangents, rank, projection and capture signs."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile

import numpy as np
from scipy.spatial.transform import Rotation

import diagnostic as d


def state(n=21, seed=92):
    rng = np.random.default_rng(seed)
    R = Rotation.from_rotvec(rng.normal(size=(n, 3))).as_matrix()
    C = rng.normal(size=(n, 3)) * [17.0, 3.0, 2.0] + [1.0, -4.0, 8.0]
    t = -np.einsum("nij,nj->ni", R, C)
    E = np.exp(rng.normal(size=(n, 9)))
    return R, t, E, C


def test_native_tangent():
    R, t, E, C = state()
    basis, check = d.finite_difference_modes(R, t)
    assert check["max_fd_analytic_error"] < 2e-8, check
    assert np.count_nonzero(basis[:, 6:]) == 0
    # The world-rotation sign is independently checked in native left coordinates.
    np.testing.assert_allclose(basis[:, :3, :3], -R, atol=2e-10, rtol=2e-10)
    np.testing.assert_allclose(basis[:, 3:6, 3:6], -R, atol=2e-9, rtol=2e-9)
    direction = np.array([.13, -.21, .31, .7, -.2, .15, .23])
    native = np.einsum("nim,m->ni", basis, direction)
    centroid = C.mean(axis=0)
    errors = []
    for h in (2e-4, 1e-4, 5e-5):
        exact_R, exact_t, _ = d.similarity_action(R, C, centroid, h * direction)
        approx_R = Rotation.from_rotvec(h * native[:, :3]).as_matrix() @ R
        approx_t = t + h * native[:, 3:6]
        error = np.sqrt(np.linalg.norm(exact_R - approx_R)**2 + np.linalg.norm(exact_t - approx_t)**2)
        errors.append(float(error))
    ratios = np.array(errors[:-1]) / errors[1:]
    assert np.all((ratios > 3.7) & (ratios < 4.3)), (errors, ratios)
    # Exact global Sim3 leaves central projection unchanged: camera coordinates
    # scale uniformly, for arbitrarily rotated world-to-camera matrices.
    rng = np.random.default_rng(87)
    X = rng.normal(size=(len(R), 3)) * 9
    a = np.array([.17, -.12, .09, .5, .2, -.3, .11])
    new_R, new_t, _ = d.similarity_action(R, C, centroid, a)
    Q = Rotation.from_rotvec(a[:3]).as_matrix()
    moved_X = centroid + np.exp(a[6]) * ((X - centroid) @ Q.T) + a[3:6]
    old_y = np.einsum("nij,nj->ni", R, X) + t
    new_y = np.einsum("nij,nj->ni", new_R, moved_X) + new_t
    invariance = float(np.max(np.abs(new_y - np.exp(a[6]) * old_y)))
    assert invariance < 2e-13
    # World-origin offsets must not erase a unit translation finite difference.
    far_C = C + [1e10, -3e10, 2e10]
    far_t = -np.einsum("nij,nj->ni", R, far_C)
    far_basis, far_check = d.finite_difference_modes(R, far_t)
    assert far_check["max_fd_analytic_error"] < 2e-8
    np.testing.assert_allclose(far_basis[:, 3:6, 3:6], -R, atol=2e-13)
    return dict(fd_analytic_max_error=check["max_fd_analytic_error"],
                native_retraction_errors=errors, first_order_error_ratios=ratios.tolist(),
                similarity_camera_coordinate_error=invariance,
                large_world_origin_fd_analytic_error=far_check["max_fd_analytic_error"])


def test_clusters():
    _, _, _, C = state(21)
    cases = [C, np.zeros((12, 3)), np.repeat(C[:3], 4, axis=0)]
    details = []
    for case, points in enumerate(cases):
        for k in (1, 8, 32, 128):
            labels, info = d.cluster_centers(points, k)
            labels2, info2 = d.cluster_centers(points, k)
            assert np.array_equal(labels, labels2) and info == info2
            assert info["actual_k"] == min(k, len(points))
            assert min(info["cluster_sizes"]) >= 1
            assert info["converged"]
            details.append(dict(case=case, requested=k, actual=info["actual_k"],
                                empty_reassignments=info["empty_reassignments"]))
    return details


def test_projection():
    R, t, E, C = state(12)
    labels, info = d.cluster_centers(C, 4)
    blocks, basis_info = d.build_blocks(R, t, E, labels)
    rng = np.random.default_rng(76)
    vector = rng.normal(size=(12, 9))
    native_projection = d.project_blocks(vector, blocks)
    dense = np.zeros((12 * 9, basis_info["rank"]))
    offset = 0
    for block in blocks:
        ids, Q = block["ids"], block["Q"]
        rows = (ids[:, None] * 9 + np.arange(9)).reshape(-1)
        dense[np.ix_(rows, np.arange(offset, offset + Q.shape[1]))] = Q
        offset += Q.shape[1]
    np.testing.assert_allclose(dense.T @ dense, np.eye(offset), atol=3e-14)
    direct = (dense @ (dense.T @ vector.reshape(-1))).reshape(12, 9)
    discrepancy = float(np.max(np.abs(direct - native_projection)))
    assert discrepancy < 3e-14
    assert np.linalg.norm(d.project_blocks(native_projection, blocks) - native_projection) < 1e-13
    intrinsic = np.zeros_like(vector)
    intrinsic[:, 6:8] = rng.normal(size=(12, 2))
    assert np.linalg.norm(d.project_blocks(intrinsic, blocks)) < 1e-13
    all_blocks, all_info = d.build_blocks(R, t, E, np.arange(12))
    assert all_info["rank"] == 6 * 12
    assert all(x["rank"] == 6 for x in all_info["clusters"])
    extrinsic = np.zeros_like(vector)
    extrinsic[:, :6] = rng.normal(size=(12, 6))
    np.testing.assert_allclose(d.project_blocks(extrinsic, all_blocks), extrinsic, atol=2e-13)
    global_blocks, global_info = d.build_blocks(R, t, E, np.zeros(12, dtype=int))
    assert global_info["rank"] == 7
    global_vector = global_blocks[0]["Q"][:, 0].reshape(12, 9)
    report = d.projection_report(global_vector, blocks, global_blocks, 1.0)
    assert abs(report["global_similarity_fraction"] - 1) < 1e-13
    assert report["after_global_removal_fraction"] is None
    return dict(block_dense_projection_max_error=discrepancy,
                cluster_rank=basis_info["rank"], singleton_rank=all_info["rank"],
                global_similarity_rank=global_info["rank"])


def test_capture_sign_and_immutability():
    R, t, E, C = state(9)
    rng = np.random.default_rng(38)
    npt = 3
    raw = rng.normal(size=(9, 9))
    raw[:, 8] = 0
    exact_camera = -E * raw
    eta_camera = exact_camera * .5
    exact = np.r_[exact_camera.reshape(-1), np.zeros(3 * npt)]
    eta = np.r_[eta_camera.reshape(-1), np.zeros(3 * npt)]
    values = {"R_state.f64": R, "t_state.f64": t, "E.f64": E,
              "X_state.f64": rng.normal(size=(npt, 3)),
              "intr_state.f64": np.array([[800.0] * 9, [.001] * 9, [0.0] * 9]),
              "eta2_raw_scaled.f64": raw, "eta2-0.step": eta,
              "exact-0.step": exact, "exact_clip-0.step": eta}
    # Temporary files remain inside this agent's assigned coarse/ subtree.
    with tempfile.TemporaryDirectory(prefix="toy-", dir=Path(__file__).resolve().parent) as tmp:
        folder = Path(tmp)
        (folder / "metadata.txt").write_text("ncam=9\nnpt=3\nnobs=7\nlambda=0.1\n")
        for name, value in values.items():
            np.asarray(value, dtype="<f8").tofile(folder / name)
        before = {p.name: d.sha256(p) for p in folder.iterdir()}
        result = d.diagnose_capture(folder)
        json.dumps(result, allow_nan=False)  # The complete public output is serializable.
        after = {p.name: d.sha256(p) for p in folder.iterdir()}
        assert before == after
        assert result["input_sha256"] == before
        for cell in result["cells"]:
            diffs = cell["references"][0]["differences"]
            assert diffs["exact_minus_eta2_raw"]["negligible_difference"]
            assert diffs["exact_minus_eta2_raw"]["fraction"] is None
            assert diffs["exact_clip_minus_eta2"]["negligible_difference"]
            assert not diffs["exact_minus_eta2"]["negligible_difference"]
        # A nonzero k2 changes the objective and must not be silently repaired.
        bad = values["intr_state.f64"].copy()
        bad[2, 0] = 1e-8
        bad.tofile(folder / "intr_state.f64")
        try:
            d.diagnose_capture(folder)
        except ValueError as error:
            assert "k2" in str(error)
        else:
            raise AssertionError("Nonzero k2 was silently accepted")
    return dict(input_hashes_unchanged=True, raw_positive_CG_sign_checked=True,
                nonzero_k2_rejected=True, incomplete_certification_not_promoted=True)


def main():
    result = dict(native_tangent=test_native_tangent(), clustering=test_clusters(),
                  projections=test_projection(), capture=test_capture_sign_and_immutability(),
                  scope="Synthetic CPU verification only; no native capture or GPU benchmark")
    output = Path(__file__).with_name("verification.json")
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
