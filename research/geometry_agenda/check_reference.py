#!/usr/bin/env python3
"""Schur/QR/direct equivalence, fixed-factor new RHS, and cross-block penalty."""
import json
import pathlib
import numpy as np
from reference_ba import synthetic, Linearization

truth, s, obs = synthetic(6, nc=4, np_=15)
results = []
for penalty in [0., .1]:
    l = Linearization(s, obs, depth_penalty=penalty)
    lam = .1
    f = l.factor(lam)
    dc, dp = f.solve()
    B, C = l.B.copy(), l.C.copy()
    B[:, np.arange(6), np.arange(6)] += lam*l.Dc
    C[:, np.arange(3), np.arange(3)] += lam*l.Dp
    n = 6*l.nc+3*l.np
    A = np.zeros((n, n))
    for i in range(l.nc): A[6*i:6*i+6, 6*i:6*i+6] = B[i]
    for i in range(l.np): A[6*l.nc+3*i:6*l.nc+3*i+3, 6*l.nc+3*i:6*l.nc+3*i+3] = C[i]
    A[:6*l.nc, 6*l.nc:] = l.E; A[6*l.nc:, :6*l.nc] = l.E.T
    active = np.ones(n, dtype=bool); active[:6] = False; active[6*l.nc+2] = False
    g = np.r_[l.gc.ravel(), l.gp.ravel()]
    d = np.r_[dc.ravel(), dp.ravel()]
    direct = np.linalg.solve(A[np.ix_(active, active)], -g[active])
    rel = np.linalg.norm(d[active]-direct)/np.linalg.norm(direct)
    residual = np.linalg.norm(A[np.ix_(active, active)]@d[active]+g[active])/np.linalg.norm(g[active])
    assert rel < 1e-9 and residual < 1e-11
    # A new RHS must reuse unchanged factors and match a separate direct solve.
    rng = np.random.default_rng(931)
    gc = rng.normal(size=l.gc.shape); gp = rng.normal(size=l.gp.shape)
    c2, p2 = f.solve(gc, gp)
    g2 = np.r_[gc.ravel(), gp.ravel()]; d2 = np.r_[c2.ravel(), p2.ravel()]
    direct2 = np.linalg.solve(A[np.ix_(active, active)], -g2[active])
    rel2 = np.linalg.norm(d2[active]-direct2)/np.linalg.norm(direct2)
    assert rel2 < 1e-9
    row = {'penalty_beta': penalty, 'schur_direct_relative': rel,
           'numerical_residual_relative': residual, 'new_rhs_relative': rel2}
    if penalty == 0:
        J = np.zeros((len(obs)*2, n))
        for k, (ci, pi, _, _) in enumerate(obs):
            J[2*k:2*k+2, int(ci)*6:int(ci)*6+6] = l.jc[k]
            J[2*k:2*k+2, 6*l.nc+int(pi)*3:6*l.nc+int(pi)*3+3] = l.jp[k]
        D = np.r_[l.Dc.ravel(), l.Dp.ravel()]
        aug = np.r_[J[:, active], np.diag(np.sqrt(lam*D[active]))]
        rhs = np.r_[-l.r.ravel(), np.zeros(active.sum())]
        qr = np.linalg.lstsq(aug, rhs, rcond=None)[0]
        row['augmented_lstsq_relative'] = float(np.linalg.norm(qr-direct)/np.linalg.norm(direct))
        assert row['augmented_lstsq_relative'] < 1e-9
    results.append(row)
pathlib.Path(__file__).with_name('reference_checks.json').write_text(json.dumps(results, indent=2)+'\n')
print(json.dumps(results, indent=2))
