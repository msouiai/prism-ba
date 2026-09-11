import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'; os.environ['OMP_NUM_THREADS'] = '1'
import argparse
import json
import pathlib
import numpy as np
from collective import clustered, solve_t4
from reference_ba import valid_cost
from geometry import project
from experiment import alignment_error

ROOT = pathlib.Path(__file__).resolve().parent
p = argparse.ArgumentParser(); p.add_argument('--split', choices=['development', 'held_out'], default='development'); args = p.parse_args()
seeds = range(10) if args.split == 'development' else range(100, 110)
arms = ['fine', 'linear', 'nonlinear']; rows = []
for bridges in [4, 16, 0]:
    for seed in seeds:
        truth, initial, obs, cg, pg, bridge, _ = clustered(seed, bridges=bridges)
        target = valid_cost(truth, obs)+1e-4*(valid_cost(initial, obs)-valid_cost(truth, obs))
        for rep in range(3):
            offset = (seed+rep)%len(arms)
            for arm in arms[offset:]+arms[:offset]:
                final, result = solve_t4(initial, obs, cg, pg, arm, target)
                residual = project(final, obs, 6)[0]
                rows.append({'bridges': bridges, 'seed': seed, 'rep': rep, 'arm': arm, 'target': target,
                             **result, **alignment_error(final, truth),
                             'bridge_rms': float(np.sqrt(np.mean(residual[bridge]**2))) if bridge.any() else None})
        print('bridges', bridges, seed, 'done', flush=True)
(ROOT/f't4_{args.split}.json').write_text(json.dumps({'rows': rows}, indent=2, allow_nan=False)+'\n')
summary = {}
for bridges in [4, 16, 0]:
    summary[bridges] = {}
    for arm in arms:
        a = [r for r in rows if r['bridges'] == bridges and r['arm'] == arm]
        ratios = {}
        for base in ['fine', 'linear']:
            pairs = []
            for seed in seeds:
                ours = [r for r in a if r['seed'] == seed]
                other = [r for r in rows if r['bridges'] == bridges and r['arm'] == base and r['seed'] == seed]
                if all(r['hit'] for r in ours+other): pairs.append(np.median([r['seconds'] for r in other])/np.median([r['seconds'] for r in ours]))
            ratios[base] = float(np.median(pairs)) if pairs else None
        summary[bridges][arm] = {'hits': sum(r['hit'] for r in a), 'runs': len(a), 'speedup': ratios,
                                 'point_nrmse_median': float(np.median([r['point_nrmse'] for r in a])),
                                 'geometric_failures': sum(r['point_nrmse'] > .15 for r in a),
                                 'coarse_fraction': sum(r['coarse_seconds'] for r in a)/sum(r['seconds'] for r in a)}
(ROOT/f't4_{args.split}_summary.json').write_text(json.dumps(summary, indent=2)+'\n'); print(json.dumps(summary, indent=2))
