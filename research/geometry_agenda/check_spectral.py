import json
import pathlib
import numpy as np
from spectral import response, full_matrix
from reference_ba import synthetic, Linearization

rng = np.random.default_rng(811); rows = []
for n in [7, 21]:
    Q, _ = np.linalg.qr(rng.normal(size=(n, n)))
    values = np.r_[0., np.logspace(-8, 3, n-1)]
    H = (Q*values)@Q.T
    Z = rng.normal(size=(n, n)); M = Z.T@Z+np.eye(n)
    L = np.linalg.cholesky(M); A = np.linalg.solve(L, np.linalg.solve(L, H).T).T
    h, V = np.linalg.eigh(A); h = np.maximum(h, 0.)
    b = rng.normal(size=n); bh = V.T@np.linalg.solve(L, b)
    for lam in [.01, .1, 10.]:
        u = np.zeros(n)
        for k in range(8):
            u = np.linalg.solve(H+lam*M, b+lam*M@u)
            closed = np.linalg.solve(L.T, V@(response(h, lam, k)*bh))
            error = np.linalg.norm(u-closed)/np.linalg.norm(u)
            assert error < 2e-8, (n, lam, k, error)
            rows.append({'n': n, 'lambda': lam, 'k': k, 'relative_error': float(error)})
assert response(np.array([0.]), 2., 0)[0] == .5 and response(np.array([0.]), 2., 7)[0] == 4.
_, s, obs = synthetic(1, nc=4, np_=15); lin = Linearization(s, obs)
H, M, b, ids = full_matrix(lin); root = np.sqrt(M)
h, V = np.linalg.eigh(H/root[:, None]/root[None, :]); h = np.maximum(h, 0)
factor = lin.factor(.1); dc = np.zeros((lin.nc, 6)); dp = np.zeros((lin.np, 3)); errors = []
for k in range(8):
    dc, dp = factor.solve(lin.gc-.1*lin.Dc*dc, lin.gp-.1*lin.Dp*dp)
    u = np.r_[dc.ravel(), dp.ravel()][ids]
    closed = (V@(response(h, .1, k)*(V.T@(b/root))))/root
    errors.append(float(np.linalg.norm(u-closed)/np.linalg.norm(u)))
assert max(errors) < 1e-8
S1 = lin.factor(.1).S; S2 = lin.factor(.2).S
nonshift = S2-S1-.1*np.diag(lin.Dc[1:].ravel())
nonshift_fraction = np.linalg.norm(nonshift)/np.linalg.norm(S2-S1)
assert nonshift_fraction > .01
result = {'passed': True, 'psd_and_metric': rows, 'ba_relative_errors': errors, 'non_scalar_schur_change_fraction': float(nonshift_fraction)}
pathlib.Path(__file__).with_name('spectral_checks.json').write_text(json.dumps(result, indent=2)+'\n')
print('filter/metric/gauge/Schur tests passed; max BA error', max(errors), 'nonshift fraction', nonshift_fraction)
