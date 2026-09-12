#!/usr/bin/env python3
"""Independent algebra checks for D9's eliminated lifted residual block."""
import math
import random

import numpy as np


def transformed(r, j, w, tau2, lam):
    r2 = float(r @ r)
    den = r2 + 2 * tau2 * w * w + lam
    h = (2 * tau2 * w * w + lam) / den
    root = math.sqrt(h)
    rank = (1 - root) / r2 if r2 else 0.0
    L = abs(w) * (np.eye(2) - rank * np.outer(r, r))
    gfac = w*w * (1 - (r2 + tau2*(w*w-1)) / den)
    q = gfac / (abs(w)*root) * r
    return L @ j, q


def explicit(r, j, w, tau2, lam):
    r2 = float(r @ r)
    den = r2 + 2*tau2*w*w + lam
    C = w*w * (np.eye(2) - np.outer(r, r)/den)
    gfac = w*w * (1 - (r2 + tau2*(w*w-1))/den)
    return j.T @ C @ j, j.T @ (gfac*r)


def phi(r, w, tau2):
    return 0.5*(w*w*float(r@r) + 0.5*tau2*(w*w-1)**2)


def main():
    rng = np.random.default_rng(20260912)
    worst_h = worst_g = worst_fd = 0.0
    for _ in range(5000):
        r = rng.normal(size=2)
        j = rng.normal(size=(2, 12))
        w = float(10**rng.uniform(-2, .2))
        tau2 = float(10**rng.uniform(-3, 3))
        lam = float(10**rng.uniform(-8, 2))
        jt, q = transformed(r, j, w, tau2, lam)
        he, ge = explicit(r, j, w, tau2, lam)
        ha, ga = jt.T @ jt, jt.T @ q
        worst_h = max(worst_h, np.linalg.norm(ha-he)/max(1.,np.linalg.norm(he)))
        worst_g = max(worst_g, np.linalg.norm(ga-ge)/max(1.,np.linalg.norm(ge)))

        d = rng.normal(size=12)*1e-4
        rlin = r + j @ d
        den = float(r@r) + 2*tau2*w*w + lam
        dw = -w*(float(r@r)+tau2*(w*w-1)+float(r@(j@d)))/den
        # The formula must solve the scalar damped normal equation at the
        # linearisation, including H_wx d.
        normal = w*(float(r@r)+tau2*(w*w-1)+float(r@(j@d))) + den*dw
        worst_fd = max(worst_fd, abs(normal))
        assert math.isfinite(phi(rlin, w+dw, tau2))
    assert worst_h < 2e-12, worst_h
    assert worst_g < 2e-12, worst_g
    assert worst_fd < 2e-12, worst_fd
    print({"cases": 5000, "max_hessian_rel": worst_h,
           "max_rhs_rel": worst_g, "max_weight_normal_residual": worst_fd})


if __name__ == "__main__":
    main()
