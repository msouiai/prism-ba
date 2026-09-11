import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'; os.environ['OMP_NUM_THREADS'] = '1'
import argparse
import json
import pathlib
import numpy as np
from collective import clustered
from robust_continuation import robust_value, solve_t5
from experiment import alignment_error
from geometry import project

ROOT = pathlib.Path(__file__).resolve().parent
p = argparse.ArgumentParser(); p.add_argument('--split', choices=['development', 'held_out'], default='development'); args = p.parse_args()
seeds = range(10) if args.split == 'development' else range(100, 110)
arms = ['fixed', 'ordinary', 'residual', 'information']; rows = []
for scenario in ['correct', 'mixed', 'corrupt', 'disconnected']:
    for seed in seeds:
        truth, initial, obs, cg, pg, bridge, false = clustered(seed, bridges=0 if scenario == 'disconnected' else 4,
                                                            corrupt='mixed' if scenario == 'mixed' else 'all' if scenario == 'corrupt' else 'none')
        Fref = robust_value(truth, obs); target = Fref+1e-3*(robust_value(initial, obs)-Fref)
        for rep in range(3):
            offset = (seed+rep)%len(arms)
            for arm in arms[offset:]+arms[:offset]:
                final, result = solve_t5(initial, obs, cg, pg, arm, target)
                r, _ = project(final, obs, 6)
                rows.append({'scenario': scenario, 'seed': seed, 'rep': rep, 'arm': arm, 'target': target,
                             **result, **alignment_error(final, truth), 'false_inliers': int(np.count_nonzero(np.linalg.norm(r[false], axis=1) < 1.)),
                             'false_observations': int(false.sum())})
        print(scenario, seed, 'done', flush=True)
(ROOT/f't5_{args.split}.json').write_text(json.dumps({'rows': rows}, indent=2, allow_nan=False)+'\n')
summary = {}
for scenario in ['correct', 'mixed', 'corrupt', 'disconnected']:
    summary[scenario] = {}
    for arm in arms:
        a = [r for r in rows if r['scenario'] == scenario and r['arm'] == arm]; ratios = {}
        for base in ['ordinary', 'residual']:
            pairs = []
            for seed in seeds:
                ours = [r for r in a if r['seed'] == seed]
                other = [r for r in rows if r['scenario'] == scenario and r['arm'] == base and r['seed'] == seed]
                if all(r['hit'] for r in ours+other): pairs.append(np.median([r['target_seconds'] for r in other])/np.median([r['target_seconds'] for r in ours]))
            ratios[base] = {'median': float(np.median(pairs)) if pairs else None, 'common_scenes': len(pairs)}
        summary[scenario][arm] = {'hits': sum(r['hit'] for r in a), 'runs': len(a), 'speedup': ratios,
                                  'final_cost_median': float(np.median([r['cost'] for r in a])),
                                  'geometry_failures': sum(r['point_nrmse'] > .15 for r in a),
                                  'false_inliers_median': float(np.median([r['false_inliers'] for r in a])),
                                  'delays_median': float(np.median([r['delays'] for r in a])),
                                  'feature_fraction': sum(r['work_seconds'].get('information_feature', 0.)+r['work_seconds'].get('residual_feature', 0.) for r in a)/sum(r['seconds'] for r in a)}
(ROOT/f't5_{args.split}_summary.json').write_text(json.dumps(summary, indent=2)+'\n'); print(json.dumps(summary, indent=2))
