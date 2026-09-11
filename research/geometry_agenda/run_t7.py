import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'; os.environ['OMP_NUM_THREADS'] = '1'
import argparse
import json
import pathlib
import numpy as np
from reference_ba import synthetic, valid_cost
from spectral import solve_t7
from experiment import alignment_error

ROOT = pathlib.Path(__file__).resolve().parent
p = argparse.ArgumentParser(); p.add_argument('--split', choices=['development', 'held_out'], default='development'); args = p.parse_args()
seeds = range(10) if args.split == 'development' else range(100, 110)
threshold = json.loads((ROOT/'t7_frozen_rule.json').read_text())['threshold']
arms = ['full', 'manual5', 'manual4', 'pruned']; rows = []
for family in ['depth', 'rotation']:
    for seed in seeds:
        truth, initial, obs = synthetic(seed, family)
        ref = valid_cost(truth, obs); target = ref+1e-4*(valid_cost(initial, obs)-ref)
        for rep in range(3):
            offset = (seed+rep)%len(arms)
            for arm in arms[offset:]+arms[:offset]:
                final, result = solve_t7(initial, obs, arm, target, threshold)
                rows.append({'family': family, 'seed': seed, 'rep': rep, 'arm': arm, 'target': target,
                             **result, **alignment_error(final, truth)})
        print(family, seed, 'done', flush=True)
(ROOT/f't7_{args.split}.json').write_text(json.dumps({'threshold': threshold, 'rows': rows}, indent=2, allow_nan=False)+'\n')
summary = {}
for family in ['depth', 'rotation', 'all']:
    subset = [r for r in rows if family == 'all' or r['family'] == family]; summary[family] = {}
    for arm in arms:
        a = [r for r in subset if r['arm'] == arm]; ratios = {}
        for base in ['full', 'manual5', 'manual4']:
            pairs = []
            for fam, seed in sorted(set((r['family'], r['seed']) for r in a)):
                ours = [r for r in a if r['seed'] == seed and r['family'] == fam]
                other = [r for r in subset if r['seed'] == seed and r['family'] == fam and r['arm'] == base]
                if all(r['hit'] for r in ours+other): pairs.append(np.median([r['seconds'] for r in other])/np.median([r['seconds'] for r in ours]))
            ratios[base] = float(np.median(pairs)) if pairs else None
        summary[family][arm] = {'hits': sum(r['hit'] for r in a), 'runs': len(a), 'speedup': ratios,
                                'geometric_failures': sum(r['point_nrmse'] > .15 for r in a),
                                'feature_fraction': sum(r['work_seconds'].get('spectral_feature', 0.)+r['work_seconds'].get('pruning', 0.) for r in a)/sum(r['seconds'] for r in a),
                                'mean_evaluations': float(np.mean([r['counts'].get('cost', 0) for r in a]))}
(ROOT/f't7_{args.split}_summary.json').write_text(json.dumps(summary, indent=2)+'\n'); print(json.dumps(summary, indent=2))
