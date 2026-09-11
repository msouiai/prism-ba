import json
import pathlib
import numpy as np
from reference_ba import synthetic, Linearization
from geometry import project, retract
from curvature import second_directional

rows = []
for cd in [6, 9]:
    for seed in range(5):
        _, s, obs = synthetic(seed, 'rotation', nc=4, np_=15)
        rng = np.random.default_rng(seed+130)
        dc = rng.normal(0, .1, (len(s.R), cd)); dp = rng.normal(0, .2, s.X.shape)
        if cd == 9:
            s.intr[:, 1] = .025
            dc[:, 6] *= 30; dc[:, 7] *= .1; dc[:, 8] = 0
        exact = second_directional(s, obs, dc, dp)
        r = project(s, obs, cd)[0]
        errors = []
        for h in np.logspace(-1, -5, 9):
            fd = (project(retract(s, dc, dp, h), obs, cd)[0]-2*r
                  +project(retract(s, dc, dp, -h), obs, cd)[0])/h**2
            errors.append(float(np.linalg.norm(fd-exact)/np.linalg.norm(exact)))
        assert min(errors) < 3e-6, (cd, seed, errors)
        rows.append({'dof': cd, 'seed': seed, 'h': np.logspace(-1, -5, 9).tolist(), 'relative_errors': errors})
pathlib.Path(__file__).with_name('curvature_checks.json').write_text(json.dumps({'passed': True, 'rows': rows}, indent=2)+'\n')
print('second derivative checks passed; worst best-step error', max(min(r['relative_errors']) for r in rows))
