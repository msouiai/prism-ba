import json
import pathlib
import numpy as np
from depth_smoothing import parallax_case, quadrature, smooth_evaluation
from reference_ba import Linearization
from geometry import retract, dot

rows = []
for kind in ['depth', 'isotropic']:
    for baseline in [.1, 1.]:
        _, s, obs = parallax_case(2, baseline)
        offsets, weights = quadrature(s, obs, kind, .1)
        assert abs(weights.sum()-1) < 1e-15
        assert np.max(np.abs(np.einsum('i,ijk->jk', weights, offsets))) < 1e-15
        lin0 = smooth_evaluation(s, obs, offsets, weights, 0, True); ordinary = Linearization(s, obs)
        relative = np.linalg.norm(lin0.E-ordinary.E)/np.linalg.norm(ordinary.E)
        assert relative < 1e-13
        lin = smooth_evaluation(s, obs, offsets, weights, 1, True)
        rng = np.random.default_rng(113); dc = rng.normal(0, .001, (len(s.R), 6)); dp = rng.normal(0, .001, s.X.shape)
        dc[0] = 0; dp[0, 2] = 0
        exact = dot(lin.gc, dc)+dot(lin.gp, dp); errors = []
        for h in [1e-2, 1e-3, 1e-4, 1e-5]:
            fd = (smooth_evaluation(retract(s, dc, dp, h), obs, offsets, weights, 1)-smooth_evaluation(retract(s, dc, dp, -h), obs, offsets, weights, 1))/(2*h)
            errors.append(abs(fd-exact)/max(1., abs(exact)))
        assert min(errors) < 1e-7
        invalid = s.copy(); invalid.X[:, 2] = 1
        assert not np.isfinite(smooth_evaluation(invalid, obs, offsets, weights, 1))
        rows.append({'kind': kind, 'baseline': baseline, 'zero_radius_schur_E_error': relative, 'gradient_errors': errors})
pathlib.Path(__file__).with_name('smoothing_checks.json').write_text(json.dumps({'passed': True, 'rows': rows}, indent=2)+'\n')
print('smoothing derivative, zero-radius identity, quadrature and invalid-domain checks passed')
