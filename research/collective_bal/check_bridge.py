import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'; os.environ['OMP_NUM_THREADS'] = '1'
import json
import numpy as np
from paths import ROOT
from geometry import State, project, retract, dot
from collective import clustered, transform, coarse_linearization, coarse_solve
from partition import automatic_partition
from bridge_coarse import masks, solve_bridge
from reference_ba import valid_cost

rows = []
def check(label, s, obs, cg, pg):
    original = s.copy(); bridge = masks(obs, cg, pg)
    r, _, K, bc, bp = coarse_linearization(s, obs, cg, pg)
    rb, _, Kb, _, _ = coarse_linearization(s, obs[bridge], cg, pg)
    matrix_err = np.linalg.norm(K.T@K-Kb.T@Kb)/max(1., np.linalg.norm(K.T@K))
    rhs_err = np.linalg.norm(K.T@r.ravel()-Kb.T@rb.ravel())/max(1., np.linalg.norm(K.T@r.ravel()))
    u = np.random.default_rng(15).normal(0, .03, K.shape[1]); trial = transform(s, cg, pg, u)
    rt, _ = project(trial, obs, 6)
    invariant = np.linalg.norm(rt[~bridge]-r[~bridge])/max(1., np.linalg.norm(r[~bridge]))
    assert matrix_err < 1e-10 and rhs_err < 1e-10 and invariant < 1e-10
    nonlinear_full, a = coarse_solve(s, obs, cg, pg)
    nonlinear_fast, b = solve_bridge(s, obs, cg, pg)
    error = abs(a['cost']-b['cost'])/max(1., a['cost'])
    assert error < 1e-8 and not b['verification_fallback']
    assert all(np.array_equal(x, y) for x, y in zip([s.R,s.t,s.X,s.intr],[original.R,original.t,original.X,original.intr]))
    assert np.array_equal(nonlinear_fast.R[0], s.R[0]) and nonlinear_fast.X[0, 2] == s.X[0, 2]
    linear = retract(s, (bc@u).reshape(len(s.R), 6), (bp@u).reshape(len(s.X), 3))
    linear_drift = np.linalg.norm(project(linear, obs, 6)[0][~bridge]-r[~bridge])
    rows.append({'label': label, 'matrix_relative_error': float(matrix_err), 'rhs_relative_error': float(rhs_err),
                 'internal_residual_invariance_error': float(invariant), 'endpoint_relative_error': error,
                 'linear_internal_residual_drift': float(linear_drift), 'bridge_fraction': float(np.mean(bridge))})

for seed in range(3):
    _, s, obs, cg, pg, *_ = clustered(seed)
    check('synthetic'+str(seed), s, obs, cg, pg)
for case in json.loads((ROOT/'frozen_cases.json').read_text())['cases']:
    if case['seed'] != 60: continue
    a = np.load(ROOT/case['path']); s = State(*[a[k].copy() for k in ['R','t','X','intr']]); obs = a['observations']
    cg, pg = automatic_partition(s, obs, confidence=True)
    check(case['scene'], s, obs, cg, pg)
(ROOT/'bridge_checks.json').write_text(json.dumps({'passed': True, 'rows': rows}, indent=2, allow_nan=False)+'\n')
print(json.dumps(rows, indent=2))
