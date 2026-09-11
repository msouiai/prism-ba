import json
import pathlib
import numpy as np
from collective import clustered, fixed_metric
from robust_continuation import robust_value, information_loss
from reference_ba import Linearization
from geometry import project, retract, dot

rows = []
for seed in range(3):
    _, s, obs, cg, pg, _, _ = clustered(seed, cameras=3, points=15)
    rng = np.random.default_rng(seed+19)
    dc = rng.normal(0, .01, (len(s.R), 6)); dp = rng.normal(0, .01, s.X.shape)
    dc[0] = 0; dp[0, 2] = 0
    r = project(s, obs, 6)[0]
    for sigma in [1., 8., 32.]:
        w = 1/(1+np.sum(r*r, axis=1)/sigma**2)
        lin = Linearization(s, obs, w)
        derivative = dot(lin.gc, dc)+dot(lin.gp, dp)
        errors = []
        for h in [1e-2, 1e-3, 1e-4, 1e-5]:
            fd = (robust_value(retract(s, dc, dp, h), obs, sigma)-robust_value(retract(s, dc, dp, -h), obs, sigma))/(2*h)
            errors.append(abs(fd-derivative)/max(1., abs(derivative)))
        assert min(errors) < 1e-7
        rows.append({'seed': seed, 'sigma': sigma, 'derivative_errors': errors})
    info = information_loss(s, obs, cg, pg, fixed_metric(s, cg, pg), 32, 8)
    assert not info['unobservable'] and 0 < info['min_information_ratio'] <= 1
_, s, obs, cg, pg, _, _ = clustered(1, bridges=0)
assert information_loss(s, obs, cg, pg, fixed_metric(s, cg, pg), 32, 8)['unobservable']
pathlib.Path(__file__).with_name('robust_checks.json').write_text(json.dumps({'passed': True, 'rows': rows}, indent=2)+'\n')
print('robust derivative, information decrease and disconnected detection passed')
