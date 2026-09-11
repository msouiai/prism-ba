import json
import pathlib
import numpy as np
from collective import clustered, transform, coarse_linearization
from geometry import project

rows = []
for seed in range(4):
    truth, s, obs, cg, pg, bridge, _ = clustered(seed, cameras=3, points=15)
    copy = s.copy(); rng = np.random.default_rng(seed+61); u = rng.normal(0, .1, 14)
    trial = transform(s, cg, pg, u)
    r = project(s, obs, 6)[0]; rt = project(trial, obs, 6)[0]
    invariant = np.max(np.abs(rt[~bridge]-r[~bridge])); assert invariant < 1e-10
    _, _, K, _, _ = coarse_linearization(s, obs, cg, pg)
    errors = []
    for h in [1e-2, 1e-3, 1e-4, 1e-5]:
        fd = (project(transform(s, cg, pg, h*u), obs, 6)[0]-project(transform(s, cg, pg, -h*u), obs, 6)[0])/(2*h)
        errors.append(float(np.linalg.norm(fd.ravel()-K@u)/np.linalg.norm(K@u)))
    assert min(errors) < 1e-7
    assert np.array_equal(s.X, copy.X) and np.array_equal(s.R, copy.R)
    assert np.array_equal(s.X[pg == 0], trial.X[pg == 0])
    assert np.array_equal(s.R[cg == 0], trial.R[cg == 0])
    rows.append({'seed': seed, 'within_cluster_max_projection_change': float(invariant), 'derivative_errors': errors})
pathlib.Path(__file__).with_name('collective_checks.json').write_text(json.dumps({'passed': True, 'rows': rows}, indent=2)+'\n')
print('collective invariance, tangent derivatives, gauge, and independent-state checks passed')
