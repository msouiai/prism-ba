#!/usr/bin/env python3
"""Gate for fisheye_grad17_atan2: same two layers as validate_grad17.py, plus
the domain the smooth variant exists for -- incidence angles from 1 deg to
172 deg, including a band straddling the camera plane (89..91 deg), where the
original nu = x/z chain is singular. Also checks that for Pz > 0 the smooth
variant agrees with the original generated code to ~1e-10.

Run:  python3 validate_grad17_atan2.py
"""
import numpy as np
from math import atan2, sqrt
from fisheye_grad17_atan2_numpy import fisheye_residual_grad17_atan2
from fisheye_grad17_numpy import fisheye_residual_grad17

rng = np.random.default_rng(7)


def rodrigues(w):
    th = np.linalg.norm(w)
    K = np.array([[0, -w[2], w[1]], [w[2], 0, -w[0]], [-w[1], w[0], 0]])
    if th < 1e-14:
        return np.eye(3) + K + 0.5 * K @ K
    return (np.eye(3) + np.sin(th) / th * K
            + (1 - np.cos(th)) / th**2 * (K @ K))


def forward(R, t, X, intr, obs):
    """Independent OPENCV_FISHEYE forward chain via the incidence angle."""
    fx, fy, cx, cy, k1, k2, k3, k4 = intr
    P = R @ X + t
    rho = sqrt(P[0] ** 2 + P[1] ** 2)
    th = atan2(rho, P[2])
    th2 = th * th
    d = 1 + k1 * th2 + k2 * th2**2 + k3 * th2**3 + k4 * th2**4
    return np.array([fx * d * th * P[0] / rho + cx - obs[0],
                     fy * d * th * P[1] / rho + cy - obs[1]])


def random_state(theta_lo, theta_hi):
    R = rodrigues(rng.normal(0, 0.6, 3))
    t = rng.normal(0, 1.0, 3)
    theta = rng.uniform(theta_lo, theta_hi)
    phi = rng.uniform(0, 2 * np.pi)
    dist = rng.uniform(0.5, 8.0)
    pc = dist * np.array([np.sin(theta) * np.cos(phi),
                          np.sin(theta) * np.sin(phi), np.cos(theta)])
    X = np.linalg.solve(R, pc - t)
    intr = np.array([533 + rng.normal(0, 20), 534 + rng.normal(0, 20),
                     rng.normal(0, 30), rng.normal(0, 30),
                     0.08 + rng.normal(0, 0.02), -0.03 + rng.normal(0, 0.01),
                     0.012 + rng.normal(0, 0.005), -0.003 + rng.normal(0, 0.002)])
    obs = forward(R, t, X, intr, np.zeros(2)) + rng.normal(0, 2.0, 2)
    return R, t, X, intr, obs


def perturbed(R, t, X, intr, obs, delta):
    dw, dt = delta[0:3], delta[3:6]
    dintr, dX = delta[6:14], delta[14:17]
    return forward(rodrigues(dw) @ R, t + dt, X + dX, intr + dintr, obs)


def main():
    h = 1e-6
    bands = [("front  1..85 deg", np.radians(1), np.radians(85), True),
             ("rim   85..89.9 deg", np.radians(85), np.radians(89.9), True),
             ("plane 89.9..90.1 deg", np.radians(89.9), np.radians(90.1), False),
             ("behind 90.1..135 deg", np.radians(90.1), np.radians(135), False),
             ("deep  135..172 deg", np.radians(135), np.radians(172), False)]
    all_ok = True
    for name, lo, hi, cmp_orig in bands:
        N = 200
        worst = worst_val = worst_orig = 0.0
        for _ in range(N):
            R, t, X, intr, obs = random_state(lo, hi)
            gx, gy, rx, ry = fisheye_residual_grad17_atan2(*R.ravel(), *t, *X, *intr, *obs)
            r_ind = forward(R, t, X, intr, obs)
            worst_val = max(worst_val, abs(rx - r_ind[0]), abs(ry - r_ind[1]))
            if cmp_orig:
                gx0, gy0, rx0, ry0 = fisheye_residual_grad17(*R.ravel(), *t, *X, *intr, *obs)
                for a, b in ((gx, gx0), (gy, gy0)):
                    sc = np.maximum(1.0, np.abs(b))
                    worst_orig = max(worst_orig, float(np.max(np.abs(a - b) / sc)))
                worst_orig = max(worst_orig, abs(rx - rx0), abs(ry - ry0))
            for i in range(17):
                d = np.zeros(17); d[i] = h
                fd = (perturbed(R, t, X, intr, obs, d) - perturbed(R, t, X, intr, obs, -d)) / (2 * h)
                for row, g in ((0, gx), (1, gy)):
                    scale = max(1.0, abs(fd[row]), abs(g[i]))
                    worst = max(worst, abs(fd[row] - g[i]) / scale)
            if not (np.all(np.isfinite(gx)) and np.all(np.isfinite(gy))):
                worst = np.inf
        ok = worst < 5e-6 and worst_val < 1e-9 and worst_orig < 1e-8
        all_ok &= ok
        print(f"{'PASS' if ok else 'FAIL'} {name:22s} FD rel err {worst:.2e}  "
              f"residual mismatch {worst_val:.2e}" +
              (f"  vs original grad17 {worst_orig:.2e}" if cmp_orig else "  (original singular here)"))
    return 0 if all_ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
