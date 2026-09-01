#!/usr/bin/env python3
"""Gate for fisheye_grad17: the generated gradient must match finite
differences of an INDEPENDENTLY written forward model.

Two layers, mirroring validate_grad12.py but stricter about independence:

  1. The forward residual here is a fresh implementation of COLMAP's
     OPENCV_FISHEYE chain (normalize, atan, theta/r, radial, fx/fy/cx/cy),
     NOT the sympy twin -- so a derivation error in gen_grad17_fisheye.py
     cannot cancel out of both sides. Residual values from the twin and from
     this implementation must agree to ~1e-12 first.

  2. Central finite differences of that independent forward model, with the
     pose columns stepped through the EXACT retraction (Rodrigues exp(dw) R0,
     t0 + dt) the solver uses, against the generated analytic columns.

Run:  python3 validate_grad17.py
"""
import numpy as np
from math import atan, sqrt
from fisheye_grad17_numpy import fisheye_residual_grad17

rng = np.random.default_rng(12)


def rodrigues(w):
    th = np.linalg.norm(w)
    K = np.array([[0, -w[2], w[1]], [w[2], 0, -w[0]], [-w[1], w[0], 0]])
    if th < 1e-14:
        return np.eye(3) + K + 0.5 * K @ K
    return (np.eye(3) + np.sin(th) / th * K
            + (1 - np.cos(th)) / th**2 * (K @ K))


def forward(R, t, X, intr, obs):
    """Independent COLMAP OPENCV_FISHEYE forward chain (+z)."""
    fx, fy, cx, cy, k1, k2, k3, k4 = intr
    P = R @ X + t
    nu, nv = P[0] / P[2], P[1] / P[2]
    r = sqrt(nu * nu + nv * nv + 1e-32)
    th = atan(r)
    s = th / r
    uu, vv = nu * s, nv * s
    th2 = th * th
    d = 1 + k1 * th2 + k2 * th2**2 + k3 * th2**3 + k4 * th2**4
    return np.array([fx * d * uu + cx - obs[0], fy * d * vv + cy - obs[1]])


def random_state():
    # Pose: modest rotation, camera a few units from origin.
    R = rodrigues(rng.normal(0, 0.6, 3))
    t = rng.normal(0, 1.0, 3)
    # Point placed IN FRONT (+z) with a fisheye-typical off-axis angle:
    # theta up to ~85 deg (r=tan(theta) up to ~11), avoiding the z~0 rim.
    theta = rng.uniform(0.02, 1.48)   # rad
    phi = rng.uniform(0, 2 * np.pi)
    depth = rng.uniform(0.5, 8.0)
    pc = depth * np.array([np.tan(theta) * np.cos(phi),
                           np.tan(theta) * np.sin(phi), 1.0])
    X = np.linalg.solve(R, pc - t)   # so R X + t = pc
    # Intrinsics near the Fuchsberg values, plus noise.
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
    N, h = 400, 1e-6
    worst = 0.0
    worst_val = 0.0
    for _ in range(N):
        R, t, X, intr, obs = random_state()
        gx, gy, rx, ry = fisheye_residual_grad17(
            *R.ravel(), *t, *X, *intr, *obs)
        # Layer 1: twin residual vs independent forward.
        r_ind = forward(R, t, X, intr, obs)
        worst_val = max(worst_val,
                        abs(rx - r_ind[0]), abs(ry - r_ind[1]))
        # Layer 2: FD columns vs analytic.
        for i in range(17):
            d = np.zeros(17); d[i] = h
            rp = perturbed(R, t, X, intr, obs, d)
            rm = perturbed(R, t, X, intr, obs, -d)
            fd = (rp - rm) / (2 * h)
            for row, g in ((0, gx), (1, gy)):
                scale = max(1.0, abs(fd[row]), abs(g[i]))
                worst = max(worst, abs(fd[row] - g[i]) / scale)
    ok = worst < 5e-6 and worst_val < 1e-9
    print(f"{'PASS' if ok else 'FAIL'}: {N} random states x 17 columns x 2 rows, "
          f"worst rel err {worst:.2e}, worst residual mismatch {worst_val:.2e}")
    print("column order: [dwx dwy dwz dtx dty dtz dfx dfy dcx dcy "
          "dk1 dk2 dk3 dk4 | dXx dXy dXz]")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
