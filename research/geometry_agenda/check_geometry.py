#!/usr/bin/env python3
"""Discriminating checks of projection identities and the actual BAL chart."""
import json
import pathlib
import numpy as np
from geometry import State, exp_so3, project, retract, diagnostics

rng = np.random.default_rng(761)
q = rng.normal(size=(10000, 3))
q[:, 2] = -rng.uniform(.2, 10, len(q))
dq = rng.normal(size=q.shape)*.1
gamma = rng.uniform(-.8, .8, len(q))
dq[:, 2] = gamma*q[:, 2]
uv = -q[:, :2]/q[:, 2, None]
delta = -(q+dq)[:, :2]/(q+dq)[:, 2, None]-uv
linear = -(dq[:, :2]-q[:, :2]*gamma[:, None])/q[:, 2, None]
error = np.linalg.norm(delta-linear/(1+gamma[:, None]))/np.linalg.norm(delta)
assert error < 1e-12
defect = np.linalg.norm(delta-linear, axis=1)
bound = .8/.2*np.linalg.norm(linear, axis=1)
assert np.all(defect <= bound+1e-12)
checks = {'pinhole_identity_relative_error': error, 'bound_cases': len(q), 'derivatives': []}
for k1 in [0., .025]:
    nc, np_ = 4, 20
    s = State(exp_so3(rng.normal(0, .1, (nc, 3))), rng.normal(0, .1, (nc, 3)),
              rng.normal(size=(np_, 3)), np.tile([500., k1, 0.], (nc, 1)))
    s.X[:, 2] = -rng.uniform(3, 8, np_)
    obs = np.array([[i, p, 0., 0.] for i in range(nc) for p in range(np_)])
    obs[:, 2:] = project(s, obs)[0]+rng.normal(0, 1, (len(obs), 2))
    dc = rng.normal(0, .02, (nc, 9)); dc[:, 6] *= 100; dc[:, 7] *= .1; dc[:, 8] = 0
    dp = rng.normal(0, .03, (np_, 3))
    r, _, jc, jp, _, _ = project(s, obs, jacobian=True)
    ci = obs[:, 0].astype(int); pi = obs[:, 1].astype(int)
    Jd = np.einsum('nij,nj->ni', jc, dc[ci])+np.einsum('nij,nj->ni', jp, dp[pi])
    fd = {}
    for h in [1e-2, 1e-3, 1e-4, 1e-5, 1e-6]:
        v = (project(retract(s, dc, dp, h), obs)[0]-project(retract(s, dc, dp, -h), obs)[0])/(2*h)
        fd[str(h)] = float(np.linalg.norm(v-Jd)/np.linalg.norm(Jd))
    assert min(fd.values()) < 1e-8
    d = diagnostics(s, dc, dp, obs)
    assert d['identity_relative_error'] < 1e-12
    assert d['decomposition_relative_error'] < 1e-9
    # Parent snapshots must remain unchanged by every trial evaluation.
    before = b''.join(v.tobytes() for v in [s.R, s.t, s.X, s.intr])
    retract(s, dc, dp)
    assert before == b''.join(v.tobytes() for v in [s.R, s.t, s.X, s.intr])
    checks['derivatives'].append({'k1': k1, 'finite_difference_relative_errors': fd,
                                  'decomposition_relative_error': d['decomposition_relative_error']})
pathlib.Path(__file__).with_name('geometry_checks.json').write_text(json.dumps(checks, indent=2)+'\n')
print(json.dumps(checks, indent=2))
