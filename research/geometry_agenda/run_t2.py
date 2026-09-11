import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'; os.environ['OMP_NUM_THREADS'] = '1'
import argparse
import hashlib
import json
import pathlib
import numpy as np
from reference_ba import synthetic, valid_cost
from experiment import solve_t2, alignment_error

ROOT = pathlib.Path(__file__).resolve().parent
p = argparse.ArgumentParser(); p.add_argument('--split', choices=['development', 'held_out'], default='development'); args = p.parse_args()
seeds = range(10) if args.split == 'development' else range(100, 110)
arms = ['lm', 'geo', 'oca', 'lambda', 'hybrid']
rows = []
# Untimed warm-up, not a selected scene or reported timing.
_, s, obs = synthetic(991, 'rotation', nc=4, np_=15)
solve_t2(s, obs, 'geo', 0., max_attempts=2)
for mode in ['depth', 'rotation']:
    for seed in seeds:
        truth, s, obs = synthetic(seed, mode)
        target = valid_cost(truth, obs)+1e-4*(valid_cost(s, obs)-valid_cost(truth, obs))
        for rep in range(3):
            offset = (seed+rep)%len(arms)
            for arm in arms[offset:]+arms[:offset]:
                final, result = solve_t2(s, obs, arm, target)
                rows.append({'family': mode, 'seed': seed, 'rep': rep, 'arm': arm, 'target': target,
                             **result, **alignment_error(final, truth)})
        print(mode, seed, 'done', flush=True)
out = {'protocol_sha256': hashlib.sha256((ROOT/'T2_PROTOCOL.md').read_bytes()).hexdigest(), 'split': args.split, 'rows': rows}
(ROOT/f't2_{args.split}.json').write_text(json.dumps(out, indent=2, allow_nan=False)+'\n')
summary = {}
for mode in ['depth', 'rotation', 'all']:
    subset = [r for r in rows if mode == 'all' or r['family'] == mode]
    stats = {}
    for arm in arms:
        a = [r for r in subset if r['arm'] == arm]
        speed = []
        for family, seed in sorted(set((r['family'], r['seed']) for r in a)):
            ours = [r for r in a if r['seed'] == seed and r['family'] == family]
            base = [r for r in subset if r['seed'] == seed and r['family'] == family and r['arm'] == 'lm']
            if all(r['hit'] for r in ours+base): speed.append(float(np.median([r['seconds'] for r in base])/np.median([r['seconds'] for r in ours])))
        stats[arm] = {'hits': sum(r['hit'] for r in a), 'runs': len(a), 'geometric_failures': sum(r['point_nrmse'] > .15 for r in a),
                      'median_speedup_vs_lm': float(np.median(speed)) if speed else None,
                      'median_accepted': float(np.median([r['accepted'] for r in a])),
                      'median_rejected': float(np.median([r['rejected_attempts'] for r in a])),
                      'median_seconds': float(np.median([r['seconds'] for r in a]))}
    summary[mode] = stats
(ROOT/f't2_{args.split}_summary.json').write_text(json.dumps(summary, indent=2)+'\n')
print(json.dumps(summary, indent=2))
