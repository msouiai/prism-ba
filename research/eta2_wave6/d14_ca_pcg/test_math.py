#!/usr/bin/env python3
"""Dense FP64 audit of the preconditioned Chronopoulos--Gear recurrence."""
from __future__ import annotations

import numpy as np


def standard(A: np.ndarray, M: np.ndarray, b: np.ndarray, steps: int):
    x = np.zeros_like(b)
    r = b.copy()
    u = np.linalg.solve(M, r)
    p = u.copy()
    gamma = float(r @ u)
    trace = []
    for _ in range(steps):
        s = A @ p
        alpha = gamma / float(p @ s)
        x += alpha * p
        r -= alpha * s
        u = np.linalg.solve(M, r)
        new_gamma = float(r @ u)
        beta = new_gamma / gamma
        p = u + beta * p
        gamma = new_gamma
        trace.append(x.copy())
    return trace


def chronopoulos_gear(A: np.ndarray, M: np.ndarray, b: np.ndarray, steps: int):
    x = np.zeros_like(b)
    r = b.copy()
    u = np.linalg.solve(M, r)
    w = A @ u
    gamma = float(r @ u)
    delta = float(w @ u)
    beta = 0.0
    alpha = gamma / delta
    p = u.copy()
    s = w.copy()
    trace = []
    for i in range(steps):
        x += alpha * p
        r -= alpha * s
        trace.append(x.copy())
        if i + 1 == steps:
            break
        u = np.linalg.solve(M, r)
        w = A @ u
        gamma_new = float(r @ u)
        delta_new = float(w @ u)
        beta = gamma_new / gamma
        denominator = delta_new - beta * gamma_new / alpha
        alpha = gamma_new / denominator
        p = u + beta * p
        s = w + beta * s
        gamma = gamma_new
    return trace


def main() -> None:
    rng = np.random.default_rng(20260913)
    worst_iterate = 0.0
    worst_residual = 0.0
    worst_direct = 0.0
    for n in (9, 31, 73):
        q, _ = np.linalg.qr(rng.normal(size=(n, n)))
        eig = np.geomspace(0.2, 30.0, n)
        A = q @ np.diag(eig) @ q.T
        q_m, _ = np.linalg.qr(rng.normal(size=(n, n)))
        M = q_m @ np.diag(np.geomspace(0.5, 5.0, n)) @ q_m.T
        b = rng.normal(size=n)
        steps = min(8, n)
        ref = standard(A, M, b, steps)
        got = chronopoulos_gear(A, M, b, steps)
        for xr, xg in zip(ref, got):
            rel = np.linalg.norm(xg - xr) / max(np.linalg.norm(xr), 1e-300)
            worst_iterate = max(worst_iterate, float(rel))
        rr = np.linalg.norm(b - A @ ref[-1])
        rg = np.linalg.norm(b - A @ got[-1])
        worst_residual = max(worst_residual, float(abs(rg - rr) / max(rr, 1e-300)))
        direct = np.linalg.solve(A, b)
        converged = chronopoulos_gear(A, M, b, 3 * n)[-1]
        worst_direct = max(
            worst_direct,
            float(np.linalg.norm(converged - direct) / np.linalg.norm(direct)),
        )
    # The n=9/eight-step case is already at a tiny residual, so recurrence
    # rounding is visible as a relative difference between two nearly
    # converged iterates.  The direct-solve check is the meaningful audit.
    assert worst_iterate < 5e-10, worst_iterate
    assert worst_residual < 5e-8, worst_residual
    assert worst_direct < 1e-11, worst_direct
    print(f"PASS worst_iterate_relative={worst_iterate:.17g} "
          f"worst_residual_relative={worst_residual:.17g} "
          f"worst_direct_relative={worst_direct:.17g}")


if __name__ == "__main__":
    main()
