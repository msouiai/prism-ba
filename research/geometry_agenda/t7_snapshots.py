import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'; os.environ['OMP_NUM_THREADS'] = '1'
import argparse
import json
import pathlib
import numpy as np
from reference_ba import synthetic, Linearization, valid_cost
from spectral import GRID, spectral_measure, representatives, candidates
from experiment import solve_t2, Work

ROOT = pathlib.Path(__file__).resolve().parent
p = argparse.ArgumentParser(); p.add_argument('--split', choices=['development', 'held_out'], default='development'); args = p.parse_args()
seeds = range(10) if args.split == 'development' else range(100, 110)
rows = []; thresholds = [.01, .03, .1]
for family in ['depth', 'rotation']:
    for seed in seeds:
        _, initial, obs = synthetic(seed, family)
        later, _ = solve_t2(initial, obs, 'lm', -1, max_attempts=3)
        for snapshot, state in enumerate([initial, later]):
            lin = Linearization(state, obs); work = Work()
            full = candidates(lin, .1, range(len(GRID)), work)
            nodes, weights = spectral_measure(lin); enodes, eweights = spectral_measure(lin, True)
            F = valid_cost(state, obs); best = min([F]+[v['cost'] for v in full.values() if v['eligible']])
            records = []
            for t in thresholds:
                keep, distance = representatives(nodes, weights, .1, t)
                _, exact = representatives(enodes, eweights, .1, t)
                restricted = min([F]+[full[i]['cost'] for i in keep if full[i]['eligible']])
                agreement = bool(restricted <= best+.001*F and (best == F or restricted < F))
                merged = [(i, j) for i in range(len(GRID)) for j in keep if distance[i, j] <= t and i != j]
                records.append({'threshold': t, 'kept': keep, 'full_best': best, 'restricted_best': restricted,
                                'passes_quality': agreement, 'proxy_distance_max_error': float(np.max(np.abs(distance-exact))),
                                'max_exact_merged_distance': float(max([exact[i, j] for i, j in merged], default=0.))})
            rows.append({'family': family, 'seed': seed, 'snapshot': snapshot, 'parent_cost': F, 'pruning': records,
                         'outcomes': {i: {'cost': v['cost'] if np.isfinite(v['cost']) else None, 'eligible': v['eligible']} for i, v in full.items()}})
            np.savez_compressed(ROOT/'evidence'/f't7-{family}-{seed}-{snapshot}.npz', R=state.R, t=state.t, X=state.X,
                                intr=state.intr, observations=obs)
(ROOT/f't7_snapshots_{args.split}.json').write_text(json.dumps({'grid': GRID, 'rows': rows}, indent=2, allow_nan=False)+'\n')
summary = {}
for t in thresholds:
    a = [p for r in rows for p in r['pruning'] if p['threshold'] == t]
    summary[t] = {'parents': len(a), 'quality_passes': sum(p['passes_quality'] for p in a), 'mean_kept': float(np.mean([len(p['kept']) for p in a])),
                   'max_merged_true_distance': max(p['max_exact_merged_distance'] for p in a)}
if args.split == 'development':
    good = [t for t in thresholds if summary[t]['quality_passes'] == summary[t]['parents']]
    (ROOT/'t7_frozen_rule.json').write_text(json.dumps({'threshold': max(good) if good else 0., 'summary': summary}, indent=2)+'\n')
(ROOT/f't7_snapshots_{args.split}_summary.json').write_text(json.dumps(summary, indent=2)+'\n'); print(json.dumps(summary, indent=2))
