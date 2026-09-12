#!/usr/bin/env python3
"""Read-only CPU spectral pre-test on a small native Brief-0 witness."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys
import time

import numpy as np
from scipy import sparse
from scipy.linalg import block_diag, null_space, solve_triangular

import diagnostic as coarse


def chart_module():
    path = Path(__file__).resolve().parents[1] / "charts/reference.py"
    spec = importlib.util.spec_from_file_location("brief0_chart_reference_for_spectrum", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module, path


def sum_tracks(values, indices, count):
    return np.column_stack([np.bincount(indices, weights=values[:, k], minlength=count)
                            for k in range(values.shape[1])])


def point_qr(Jp, point_ids, diagonal):
    n = len(diagonal)
    counts = np.bincount(point_ids, minlength=n)
    order = np.argsort(point_ids, kind="stable")
    offsets = np.r_[0, np.cumsum(counts)]
    sorted_J = Jp[order]
    R = np.empty((n, 3, 3))
    for length in np.unique(counts):
        ids = np.flatnonzero(counts == length)
        for begin in range(0, len(ids), 2048):
            batch = ids[begin:begin + 2048]
            rows = np.zeros((len(batch), 2 * length + 3, 3))
            if length:
                take = offsets[batch, None] + np.arange(length)
                rows[:, :2 * length] = sorted_J[take].reshape(len(batch), 2 * length, 3)
            for k in range(3):
                rows[:, 2 * length + k, k] = np.sqrt(diagonal[batch, k])
            R[batch] = np.linalg.qr(rows, mode="r")
    identity = np.broadcast_to(np.eye(3), R.shape)
    inverse_R = np.linalg.solve(R, identity)
    return R, inverse_R, counts


def point_inverse(inverse_R, rhs):
    temporary = np.einsum("nji,nj->ni", inverse_R, rhs)
    return np.einsum("nij,nj->ni", inverse_R, temporary)


def native_preconditioner(Hcc, E, lam):
    raw = Hcc * E[:, :, None] * E[:, None, :] + lam * np.eye(9)
    factors = []
    floors = 0
    fallbacks = 0
    for block in raw:
        block = .5 * (block + block.T)
        threshold = max(np.max(np.abs(np.diag(block))) * 1e-10, 1e-30)
        ids = np.diag_indices(9)
        floors += int(np.sum(block[ids] <= threshold))
        block[ids] = np.maximum(block[ids], threshold)
        try:
            L = np.linalg.cholesky(block)
        except np.linalg.LinAlgError:
            fallbacks += 1
            L = np.diag(np.sqrt(np.diag(block)))
        factors.append(L)
    return block_diag(*factors), dict(diagonal_floors=floors, diagonal_fallbacks=fallbacks)


def lanczos(matrix, initial, steps=50):
    norm = np.linalg.norm(initial)
    if norm == 0:
        return dict(start_norm=0.0, iterations=0, reason="zero_rhs", ritz_values=[])
    q = initial / norm
    basis = []
    products = []
    alphas = []
    betas = []
    previous = np.zeros_like(q)
    previous_beta = 0.0
    for _ in range(min(steps, len(q))):
        product = matrix @ q
        remainder = product - previous_beta * previous
        alpha = q @ remainder
        remainder -= alpha * q
        basis.append(q.copy())
        products.append(product)
        Q = np.column_stack(basis)
        for _ in range(2):
            remainder -= Q @ (Q.T @ remainder)
        beta = np.linalg.norm(remainder)
        alphas.append(float(alpha))
        if beta <= 100 * np.finfo(float).eps * max(np.linalg.norm(matrix, ord=np.inf), 1.0):
            break
        betas.append(float(beta))
        previous, q = q, remainder / beta
        previous_beta = beta
    Q, AQ = np.column_stack(basis), np.column_stack(products)
    projected = .5 * (Q.T @ AQ + AQ.T @ Q)
    values, vectors = np.linalg.eigh(projected)
    residuals = np.linalg.norm(AQ @ vectors - (Q @ vectors) * values[None, :], axis=0)
    tri = np.diag(alphas)
    if len(alphas) > 1:
        tri += np.diag(betas[:len(alphas) - 1], 1) + np.diag(betas[:len(alphas) - 1], -1)
    return dict(start_norm=float(norm), iterations=len(alphas),
                ritz_values=values.tolist(), ritz_residual_norms=residuals.tolist(),
                orthogonality_error=float(np.max(np.abs(Q.T @ Q - np.eye(len(alphas))))),
                projected_tridiagonal_max_error=float(np.max(np.abs(projected - tri))),
                rayleigh_quotient_checks_max_error=float(np.max(np.abs(np.diag(Q.T @ AQ) - alphas))))


def stats(values):
    return dict(min=float(values[0]), max=float(values[-1]),
                condition=float(values[-1] / values[0]) if values[0] > 0 else None,
                eigenvalues=values.tolist())


def run(folder: Path, bal: Path, *, refined_step: Path | None = None, refinement_only: bool = False):
    start = time.perf_counter()
    folder = folder.resolve()
    baseline = coarse.verify_baseline()
    module, module_path = chart_module()
    meta = coarse.read_metadata(folder / "metadata.txt")
    nc, np_, no = [int(meta[key]) for key in ("ncam", "npt", "nobs")]
    if nc > 100:
        raise ValueError("This registered dense audit is limited to small witnesses")
    shapes = {"R_state.f64": (nc, 3, 3), "t_state.f64": (nc, 3),
              "X_state.f64": (np_, 3), "intr_state.f64": (3, nc), "E.f64": (nc, 9),
              "Hcc.f64": (nc, 9, 9), "Cdiag.f64": (np_, 3),
              "exact-0.step": (9 * nc + 3 * np_,)}
    data = {name: coarse.read_array(folder / name, shape) for name, shape in shapes.items()}
    camera = module.CameraState(data["R_state.f64"], data["t_state.f64"], data["intr_state.f64"].T)
    ci, pi, uv, dims = module.load_observations(bal)
    if dims != (nc, np_, no):
        raise ValueError("BAL and capture dimensions differ")
    capture_manifest = json.loads((folder / "manifest.json").read_text())
    bal_hash = coarse.sha256(bal)
    if bal_hash != capture_manifest["input_sha256"]:
        raise ValueError("BAL observation input does not match capture manifest")
    X = data["X_state.f64"]
    H = np.column_stack([X, np.ones(np_)])
    tangent = np.zeros((np_, 4, 3)); tangent[:, :3] = np.eye(3)
    residual, Jc, Jp, Y = module.observation_jacobians(camera, H, tangent, ci, pi, uv)
    if not all(np.isfinite(value).all() for value in (residual, Jc, Jp)):
        raise ValueError("Nonfinite reference Jacobian")
    E, lam = data["E.f64"], meta["lambda"]
    U = np.zeros((nc, 9, 9))
    gc = np.zeros((nc, 9))
    counts = np.bincount(ci, minlength=nc)
    r2 = np.sum((Y[:, :2] / Y[:, 2, None])**2, axis=1)
    avg_r2 = np.maximum(np.bincount(ci, weights=r2, minlength=nc) / np.maximum(counts, 1), 1e-12)
    prior = np.zeros((nc, 9))
    active_camera = counts > 0
    prior[active_camera, 6] = 1 / (.5 * np.abs(camera.intrinsics[active_camera, 0]) + 1e-3)**2
    prior[active_camera, 7] = avg_r2[active_camera]**2
    for c in range(nc):
        ids = np.flatnonzero(ci == c)
        local = Jc[ids].reshape(-1, 9)
        U[c] = local.T @ local + np.diag(prior[c])
        gc[c] = local.T @ residual[ids].reshape(-1)
    gp = sum_tracks(np.einsum("nri,nr->ni", Jp, residual), pi, np_)
    Cdiag = data["Cdiag.f64"]
    floor = lam * np.sum(Cdiag, axis=1) / 3
    floor = np.where(floor > 0, floor, 1e-32)
    diagonal = np.maximum(lam * Cdiag, 1e-3 * floor[:, None])
    point_R, inverse_R, point_counts = point_qr(Jp, pi, diagonal)
    cross = np.einsum("nri,nrj->nij", Jc, Jp)
    rows = np.broadcast_to(9 * ci[:, None, None] + np.arange(9)[None, :, None], cross.shape).reshape(-1)
    cols = np.broadcast_to(3 * pi[:, None, None] + np.arange(3)[None, None, :], cross.shape).reshape(-1)
    W = sparse.coo_matrix((cross.reshape(-1), (rows, cols)), shape=(9 * nc, 3 * np_)).tocsr()
    Rinv_sparse = sparse.bsr_matrix((inverse_R, np.arange(np_), np.arange(np_ + 1)), shape=(3 * np_, 3 * np_)).tocsr()
    WE = W.multiply(E.reshape(-1, 1)).tocsr()
    scaled_factor = WE @ Rinv_sparse
    A = block_diag(*[E[c, :, None] * U[c] * E[c, None, :] + lam * np.eye(9) for c in range(nc)])
    A -= (scaled_factor @ scaled_factor.T).toarray()
    symmetry_error = np.max(np.abs(A - A.T))
    A = .5 * (A + A.T)
    b = -E.reshape(-1) * (gc.reshape(-1) - W @ point_inverse(inverse_R, gp).reshape(-1))

    def product(v):
        y = np.einsum("nri,ni->nr", Jc, (E * v.reshape(nc, 9))[ci])
        s = sum_tracks(np.einsum("nri,nr->ni", Jp, y), pi, np_)
        u = point_inverse(inverse_R, s)
        z = y - np.einsum("nri,ni->nr", Jp, u[pi])
        camera_action = sum_tracks(np.einsum("nri,nr->ni", Jc, z), ci, nc)
        return (E * camera_action + (lam + E**2 * prior) * v.reshape(nc, 9)).reshape(-1)

    saved = data["exact-0.step"]
    dc, dp = saved[:9 * nc].reshape(nc, 9), saved[9 * nc:].reshape(np_, 3)
    z_exact = (dc / E).reshape(-1)
    dense_residual = float(np.linalg.norm(b - A @ z_exact) / np.linalg.norm(b))
    jac_residual = float(np.linalg.norm(b - product(z_exact)) / np.linalg.norm(b))
    Jcd = np.einsum("nri,ni->nr", Jc, dc[ci])
    Jpd = np.einsum("nri,ni->nr", Jp, dp[pi])
    point_terms = sum_tracks(np.einsum("nri,nr->ni", Jp, Jcd + Jpd), pi, np_)
    point_equation = gp + point_terms + diagonal * dp
    point_error = float(np.linalg.norm(point_equation) / max(np.linalg.norm(gp), np.linalg.norm(point_terms), 1e-30))
    # Follow-up diagnosis does not alter the registered combined gate below.
    # Evaluate Jp.T(r + Jc*dc + Jp*dp) directly, before cancellation of large
    # separately accumulated gradient and Hessian-action vectors.
    conditional_rhs = -sum_tracks(np.einsum("nri,nr->ni", Jp, residual + Jcd), pi, np_)
    point_metric = diagonal / lam
    point_whiten = 1 / np.sqrt(point_metric)
    full_gradient_norm = np.hypot(np.linalg.norm(E * gc), np.linalg.norm(point_whiten * gp))
    point_gram = np.einsum('nji,njk->nik', point_R, point_R)
    point_gram_norm = np.linalg.norm(point_gram, axis=(1, 2))

    def point_audit(proposed):
        linear = residual + Jcd + np.einsum('nri,ni->nr', Jp, proposed[pi])
        stable = sum_tracks(np.einsum('nri,nr->ni', Jp, linear), pi, np_) + diagonal * proposed
        assembled = np.einsum('nij,nj->ni', point_gram, proposed) - conditional_rhs
        denominator = point_gram_norm * np.linalg.norm(proposed, axis=1) + np.linalg.norm(conditional_rhs, axis=1)
        camera_equation = sum_tracks(np.einsum('nri,nr->ni', Jc, linear), ci, nc)
        camera_equation += prior * dc + lam * dc / E**2
        point_norm = np.linalg.norm(point_whiten * stable)
        camera_norm = np.linalg.norm(E * camera_equation)
        return dict(stable_absolute_residual=float(np.linalg.norm(stable)),
                    conditional_rhs_norm=float(np.linalg.norm(conditional_rhs)),
                    stable_relative_conditional_rhs=float(np.linalg.norm(stable) / np.linalg.norm(conditional_rhs)),
                    global_normwise_backward_error=float(np.linalg.norm(stable) / np.linalg.norm(denominator)),
                    max_track_backward_error=float(np.max(np.linalg.norm(stable, axis=1) / np.maximum(denominator, 1e-300))),
                    stable_minus_assembled_norm=float(np.linalg.norm(stable - assembled)),
                    point_Dp_whitened_relative_full_gradient=float(point_norm / full_gradient_norm),
                    camera_E_scaled_relative_full_gradient=float(camera_norm / full_gradient_norm),
                    full_scaled_normal_relative_full_gradient=float(np.hypot(point_norm, camera_norm) / full_gradient_norm))

    fresh_dp = point_inverse(inverse_R, conditional_rhs)
    point_diagnosis = dict(saved_step=point_audit(dp), fresh_CPU_backsubstitution=point_audit(fresh_dp),
                          full_scaled_gradient_norm=float(full_gradient_norm),
                          fresh_minus_saved_point_norm=float(np.linalg.norm(fresh_dp - dp)),
                          note="Follow-up diagnosis only: original combined parity gate is retained unchanged; fresh points are not a native nonlinear proposal.")
    refined_record = None
    if refined_step is not None:
        if refined_step.exists():
            raise FileExistsError(refined_step)
        refined_step.parent.mkdir(parents=True, exist_ok=True)
        np.r_[dc.reshape(-1), fresh_dp.reshape(-1)].astype('<f8').tofile(refined_step)
        refined_record = dict(path=str(refined_step.resolve()), sha256=coarse.sha256(refined_step),
                              shape=[9 * nc + 3 * np_], dtype="little-endian float64",
                              source_camera_step_sha256=coarse.sha256(folder/'exact-0.step'),
                              unchanged_camera_direction=True,
                              measured_full_scaled_residual=point_diagnosis['fresh_CPU_backsubstitution']['full_scaled_normal_relative_full_gradient'],
                              certification="independent CPU full scaled normal residual, not interval arithmetic or native certification")
    if refinement_only:
        return dict(schema_version=1, kind="supplementary CPU point back-substitution at fixed source camera direction",
                    capture=str(folder), bal=str(bal.resolve()), baseline=baseline, metadata=meta,
                    refined_step=refined_record, followup_point_equation_diagnosis=point_diagnosis,
                    camera_residual=dict(dense=dense_residual, jacobian=jac_residual),
                    input_sha256={**{name:coarse.sha256(folder/name) for name in shapes},
                                  'metadata.txt':coarse.sha256(folder/'metadata.txt'),
                                  'manifest.json':coarse.sha256(folder/'manifest.json'),'BAL':bal_hash},
                    implementation_sha256={'spectrum.py':coarse.sha256(Path(__file__)),
                                           'charts/reference.py':coarse.sha256(module_path)},
                    cpu_seconds=time.perf_counter()-start)
    labels, clustering = coarse.cluster_centers(camera.centers(), 8)
    blocks, basis_info = coarse.build_blocks(camera.R, camera.t, E, labels)
    Z = np.zeros((nc * 9, basis_info["rank"]))
    offset = 0
    for block in blocks:
        ids, Q = block["ids"], block["Q"]
        row_ids = (9 * ids[:, None] + np.arange(9)).reshape(-1)
        Z[np.ix_(row_ids, np.arange(offset, offset + Q.shape[1]))] = Q
        offset += Q.shape[1]
    random = np.random.default_rng(92012)
    probes = [random.normal(size=9 * nc), b, z_exact, Z[:, 0]]
    product_checks = []
    for i, v in enumerate(probes):
        v = v / np.linalg.norm(v)
        applied = product(v)
        error = np.linalg.norm(applied - A @ v)
        product_checks.append(dict(probe=i, norm=float(np.linalg.norm(applied)),
                                   absolute_error=float(error), relative_error=float(error / max(np.linalg.norm(applied), 1e-30))))
    score = .5 * float(np.sum(residual**2))
    score_error = abs(score - meta["cost"]) / max(abs(meta["cost"]), 1.0)
    hcc_error = float(np.linalg.norm(U - data["Hcc.f64"]) / np.linalg.norm(data["Hcc.f64"]))
    validity = dict(score=score, score_relative_error=score_error,
                    coherent_camera_Hcc_relative_error=hcc_error,
                    saved_exact_dense_camera_residual=dense_residual,
                    saved_exact_jacobian_camera_residual=jac_residual,
                    saved_exact_point_equation_relative_error=point_error,
                    dense_symmetry_max_abs=float(symmetry_error), product_checks=product_checks)
    valid = max(score_error, hcc_error, dense_residual, jac_residual, point_error,
                max(x["relative_error"] for x in product_checks)) <= 1e-7
    camera_parity = max(score_error, hcc_error, dense_residual, jac_residual,
                        max(x['relative_error'] for x in product_checks)) <= 1e-7
    Lfull, preconditioner = native_preconditioner(data["Hcc.f64"], E, lam)
    active = np.flatnonzero(np.arange(nc * 9) % 9 != 8)
    L = Lfull[np.ix_(active, active)]
    active_A = A[np.ix_(active, active)]
    left = solve_triangular(L, active_A, lower=True)
    whitened = solve_triangular(L, left.T, lower=True).T
    whitened = .5 * (whitened + whitened.T)
    whitened_b = solve_triangular(L, b[active], lower=True)
    transformed_Z = L.T @ Z[active]
    Ycoarse, _ = np.linalg.qr(transformed_Z, mode="reduced")
    AY = whitened @ Ycoarse
    Ac = Ycoarse.T @ AY
    Ac = .5 * (Ac + Ac.T)
    coarse_factor = np.linalg.cholesky(Ac)
    coarse_inverse_AYt = solve_triangular(coarse_factor.T,
                             solve_triangular(coarse_factor, AY.T, lower=True), lower=False)
    deflated = whitened - AY @ coarse_inverse_AYt
    deflated = .5 * (deflated + deflated.T)
    complement = null_space(Ycoarse.T, rcond=1e-12)
    restricted = complement.T @ deflated @ complement
    restricted = .5 * (restricted + restricted.T)
    coarse_b = np.linalg.solve(Ac, Ycoarse.T @ whitened_b)
    deflated_b = whitened_b - AY @ coarse_b
    eigenvalues = np.linalg.eigvalsh(whitened)
    deflated_values = np.linalg.eigvalsh(deflated)
    positive_values = np.linalg.eigvalsh(restricted)
    result = dict(schema_version=1, capture=str(folder), bal=str(bal.resolve()), baseline=baseline,
                  settings=dict(K=8, lanczos_steps=50, lanczos_seed="whitened reduced RHS / deflated residual",
                                operator="coherent FP64 Jacobian; QR point factors; captured damping metric",
                                agreement_tolerance=1e-7),
                  validity=validity, cross_implementation_agreement_pass=bool(valid),
                  followup_camera_operator_agreement_pass=bool(camera_parity),
                  followup_point_equation_diagnosis=point_diagnosis,
                  refined_step=refined_record,
                  active_dimension=len(active), excluded_k2_dimensions=nc,
                  geometric_global_similarity_dimension=7,
                  gauge_note="Global similarity modes are retained with damping, not discarded as exact zero eigenvalues.",
                  coarse_rank=basis_info["rank"], clustering=clustering,
                  preconditioner=preconditioner, coarse_operator=stats(np.linalg.eigvalsh(Ac)),
                  spectral_baseline=stats(eigenvalues),
                  spectral_deflated_full=stats(deflated_values),
                  spectral_deflated_nonnull=stats(positive_values),
                  deflated_complement_dimension=complement.shape[1],
                  deflated_nullspace_max_error=float(np.max(np.abs(deflated @ Ycoarse))),
                  deflated_rhs_coarse_overlap=float(np.linalg.norm(Ycoarse.T @ deflated_b)),
                  baseline_lanczos=lanczos(whitened, whitened_b),
                  deflated_lanczos=lanczos(restricted, complement.T @ deflated_b),
                  input_sha256={**{name:coarse.sha256(folder/name) for name in shapes},
                                "metadata.txt":coarse.sha256(folder/'metadata.txt'),
                                "manifest.json":coarse.sha256(folder/'manifest.json'), "BAL":bal_hash},
                  implementation_sha256={"spectrum.py":coarse.sha256(Path(__file__)),
                                         "diagnostic.py":coarse.sha256(Path(coarse.__file__)),
                                         "charts/reference.py":coarse.sha256(module_path)},
                  cpu_seconds=time.perf_counter()-start,
                  limitations=["One fixed state; no nonlinear speed or hit-rate conclusion.",
                               "Deflation is not the additive preconditioner; spectra need not match that candidate.",
                               "Full spectra retain damped global-gauge modes; deflated zeros are excluded only via the explicit complement.",
                               "50-step Ritz values approximate a spectrum; they are not certified extremal eigenvalues.",
                               "If cross-implementation agreement fails, spectral interpretation is provisional."])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--bal", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--refined-step", type=Path)
    parser.add_argument("--refinement-only", action='store_true')
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = run(args.capture, args.bal, refined_step=args.refined_step, refinement_only=args.refinement_only)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    keys = ['refined_step', 'camera_residual', 'cpu_seconds'] if args.refinement_only else ['cross_implementation_agreement_pass','validity','active_dimension','coarse_rank','cpu_seconds']
    print(json.dumps({key:result[key] for key in keys}, indent=2))


if __name__ == '__main__':
    main()
