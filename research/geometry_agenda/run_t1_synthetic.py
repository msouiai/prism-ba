#!/usr/bin/env python3
"""Registered T1 predictive gate on independent pinhole seeds."""
import hashlib
import json
import pathlib
import time
import numpy as np
from reference_ba import synthetic, Linearization
from geometry import diagnostics
from predict_depth import fit_predict, auc

ROOT = pathlib.Path(__file__).resolve().parent
rows = []
for mode in ['depth', 'rotation']:
    for seed in list(range(10))+list(range(100, 110)):
        _, s, obs = synthetic(seed, mode)
        l = Linearization(s, obs)
        for lam in [1e-6, 1e-4, 1e-2, .1, 1., 10.]:
            start = time.perf_counter()
            f = l.factor(lam); dc, dp = f.solve()
            solve_seconds = time.perf_counter()-start
            rhs = -l.gc[1:].ravel()+f.E@f.point_solve(l.gp[..., None])[..., 0].ravel()
            linear_residual = np.linalg.norm(f.S@dc[1:].ravel()-rhs)/max(1e-300, np.linalg.norm(rhs))
            assert linear_residual < 1e-7
            d = diagnostics(s, dc, dp, obs)
            d['failed_valid_step'] = d['failed_strict_model'] or d['trial_wrong_depths'] > 0
            rows.append({'scene': mode, 'seed': seed, 'split': 'development' if seed < 100 else 'held_out',
                         'lambda': lam, 'raw_reduced_true_residual': linear_residual,
                         'solve_seconds': solve_seconds, **d})
    print('FINISHED family', mode, flush=True)
(ROOT/'t1_synthetic_diagnostics.json').write_text(json.dumps(rows, indent=2, allow_nan=False)+'\n')
y = np.array([int(r['failed_valid_step']) for r in rows])
train = np.array([r['seed'] < 100 for r in rows]); test = ~train
base = np.array([[np.log10(r['lambda']), np.log10(max(r['step_euclidean_norm'], 1e-300)),
                  np.log10(max(r['raw_reduced_true_residual'], 1e-16))] for r in rows])
depth = np.array([[np.log1p(r['prospective_abs_quantiles'][j]) for j in [2, 3, 4]] for r in rows])
predictions = {name: fit_predict(X[train], y[train], X[test]) for name, X in
               [('base', base), ('plus_depth', np.c_[base, depth])]}
groups = np.array([r['scene'] for r in rows])[test]
summary = {'counts': {'total': len(rows), 'held_out': int(test.sum()), 'held_out_failures': int(y[test].sum())},
           'protocol_sha256': hashlib.sha256((ROOT/'T1_SYNTHETIC_PROTOCOL.md').read_bytes()).hexdigest(),
           'pooled_auc': {name: auc(y[test], p) for name, p in predictions.items()}, 'families': {}}
for mode in ['depth', 'rotation']:
    mask = groups == mode
    summary['families'][mode] = {name: auc(y[test][mask], p[mask]) for name, p in predictions.items()}
summary['predictive_gate_passed'] = (summary['pooled_auc']['plus_depth']-summary['pooled_auc']['base'] >= .05
    and all(v['plus_depth'] is not None and v['base'] is not None
            and v['plus_depth'] >= v['base'] for v in summary['families'].values()))
(ROOT/'t1_synthetic_prediction.json').write_text(json.dumps(summary, indent=2)+'\n')
print(json.dumps(summary, indent=2))
