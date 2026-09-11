import json
import pathlib
import numpy as np
from reference_ba import synthetic, valid_cost, Linearization
from geometry import retract
from point_relaxation import polish, point_values, stationarity

rows = []
for seed in range(4):
    _, s, obs = synthetic(seed, 'depth', nc=4, np_=15)
    parent = s.copy(); lin = Linearization(s, obs)
    candidates = [retract(s, *lin.factor(l).solve()) for l in [.025, .1, .4]]
    outcomes = [polish(c, obs, 3) for c in candidates]
    reverse = [polish(candidates[i], obs, 3) for i in [2, 1, 0]][::-1]
    for c, o, r in zip(candidates, outcomes, reverse):
        assert np.array_equal(o.X, r.X), 'candidate evaluation order changed state'
        assert np.all(point_values(o, obs) <= point_values(c, obs)+1e-10)
        assert np.array_equal(o.R, c.R) and np.array_equal(o.t, c.t)
        assert o.X[0, 2] == c.X[0, 2]
        before, after = valid_cost(c, obs), valid_cost(o, obs)
        if not np.isfinite(before):
            assert not np.isfinite(after) and np.array_equal(o.X, c.X)
        rows.append({'before': before if np.isfinite(before) else None,
                     'after': after if np.isfinite(after) else None,
                     'invalid_input_retained': bool(not np.isfinite(before))})
    assert np.array_equal(s.X, parent.X) and np.array_equal(s.R, parent.R)
pathlib.Path(__file__).with_name('point_checks.json').write_text(json.dumps({'passed': True, 'rows': rows}, indent=2, allow_nan=False)+'\n')
print('point monotonicity, gauge, camera freezing, parent and order independence passed')
