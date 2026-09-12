#!/usr/bin/env python3
"""Independent small normal-equation and exact-spectrum checks; CPU only."""
import json
import numpy as np
from scipy.linalg import null_space, solve_triangular
import spectrum


def main():
    rng = np.random.default_rng(92012)
    nc, np_, no = 3, 7, 35
    ci = rng.integers(nc, size=no)
    pi = np.arange(no) % np_
    Jc = rng.normal(size=(no, 2, 9)); Jp = rng.normal(size=(no, 2, 3))
    J = np.zeros((2 * no, nc * 9 + np_ * 3))
    for o in range(no):
        J[2*o:2*o+2, 9*ci[o]:9*ci[o]+9] = Jc[o]
        J[2*o:2*o+2, nc*9+3*pi[o]:nc*9+3*pi[o]+3] = Jp[o]
    diagonal = rng.uniform(.01, .5, size=(np_, 3))
    normal = J.T @ J + np.diag(np.r_[np.full(nc*9, .1), diagonal.ravel()])
    U, W, V = normal[:nc*9, :nc*9], normal[:nc*9, nc*9:], normal[nc*9:, nc*9:]
    _, inverse_R, _ = spectrum.point_qr(Jp, pi, diagonal)
    rhs_p = rng.normal(size=(np_, 3))
    solved = spectrum.point_inverse(inverse_R, rhs_p).ravel()
    point_error = float(np.max(np.abs(solved - np.linalg.solve(V, rhs_p.ravel()))))
    assert point_error < 1e-12
    factor = np.zeros_like(V)
    for j in range(np_):
        factor[3*j:3*j+3, 3*j:3*j+3] = inverse_R[j]
    A = U - (W @ factor) @ (W @ factor).T
    assert np.max(np.abs(A - (U - W @ np.linalg.solve(V, W.T)))) < 1e-12
    rhs = rng.normal(size=len(normal))
    camera_rhs = rhs[:nc*9] - W @ np.linalg.solve(V, rhs[nc*9:])
    schur_error = float(np.max(np.abs(np.linalg.solve(A, camera_rhs) - np.linalg.solve(normal, rhs)[:nc*9])))
    assert schur_error < 1e-12
    H = rng.normal(size=A.shape)
    L = np.linalg.cholesky(H @ H.T + np.eye(len(A)))
    left = solve_triangular(L, A, lower=True)
    whitened = solve_triangular(L, left.T, lower=True).T
    # Independently compare the symmetrically whitened spectrum to generalized eigs.
    import scipy.linalg
    generalized_error = float(np.max(np.abs(np.linalg.eigvalsh(whitened) - scipy.linalg.eigvalsh(A, L @ L.T))))
    assert generalized_error < 1e-12
    Y, _ = np.linalg.qr(rng.normal(size=(len(A), 5)), mode='reduced')
    AY = whitened @ Y
    Ac = Y.T @ AY
    D = whitened - AY @ np.linalg.solve(Ac, AY.T)
    complement = null_space(Y.T)
    restricted = complement.T @ D @ complement
    nonnull = np.linalg.eigvalsh(restricted)
    assert nonnull[0] > 0
    assert np.max(np.abs(D @ Y)) < 1e-12
    assert np.max(np.abs(np.linalg.eigvalsh(D)[5:] - nonnull)) < 1e-12
    ritz = spectrum.lanczos(restricted, rng.normal(size=len(restricted)), steps=50)
    spectral_error = float(np.max(np.abs(np.array(ritz['ritz_values']) - nonnull)))
    assert spectral_error < 1e-12
    assert ritz['orthogonality_error'] < 1e-12
    result = dict(point_inverse_error=point_error, full_vs_schur_solution_error=schur_error,
                  generalized_vs_whitened_spectrum_error=generalized_error,
                  full_dimension_lanczos_spectrum_error=spectral_error,
                  deflated_zero_dimension=5, positive_dimension=len(restricted), passed=True)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
