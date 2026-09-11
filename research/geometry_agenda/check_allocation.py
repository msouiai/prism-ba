import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'
import json
import pathlib
import numpy as np
from reference_ba import synthetic, valid_cost
from experiment import Work
from allocation import ACTIONS, prepare, perform, features, predict, fit_tree
import allocation

_, state, obs = synthetic(2, 'depth', nc=6, np_=40)
original = [a.copy() for a in [state.R, state.t, state.X, state.intr]]
cache = prepare(state, obs, .1, Work()); x = features(cache)
F = cache['F']; endpoints = {}
for action in ACTIONS:
    winner, _ = perform(cache, action, Work())
    assert all(np.array_equal(a, b) for a, b in zip(original, [state.R, state.t, state.X, state.intr]))
    if winner:
        assert valid_cost(winner['state'], obs) < F
        assert np.array_equal(winner['state'].R[0], state.R[0])
        assert np.array_equal(winner['state'].t[0], state.t[0])
        assert winner['state'].X[0, 2] == state.X[0, 2]
        assert winner['cost'] <= cache['base']['cost'] or not cache['base']['eligible']
    endpoints[action] = winner['cost'] if winner else F
fresh, _ = perform(cache, 'fresh', Work())
assert fresh['cost'] == endpoints['fresh']
original_coarse = allocation.coarse_solve
def failed_coarse(*args, **kwargs):
    raise np.linalg.LinAlgError('injected degenerate coarse metric')
allocation.coarse_solve = failed_coarse
fallback, diagnostic = perform(cache, 'coarse', Work())
allocation.coarse_solve = original_coarse
assert fallback['cost'] == endpoints['fresh']
assert 'numerical_failure' in diagnostic['coarse_candidates'][0]
X = np.arange(20)[:, None]*np.ones((1, 8)); U = np.zeros((20, 6)); U[:10, 0] = 1; U[10:, 2] = 1
tree = fit_tree(X, U)
assert predict(tree, X[2]) == 'fresh' and predict(tree, X[15]) == 'lambda'
report = {'immutable_parent': True, 'gauge_preserved': True, 'fallback_preserved': True,
          'failed_coarse_falls_back': True,
          'finite_features': bool(np.isfinite(x).all()), 'endpoint_costs': endpoints}
(pathlib.Path(__file__).resolve().parent/'allocation_checks.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))
