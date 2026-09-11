import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'; os.environ['OMP_NUM_THREADS'] = '1'
import argparse
import json
import pathlib
import numpy as np
from depth_smoothing import parallax_case, solve_t6
from reference_ba import valid_cost
from experiment import alignment_error

ROOT = pathlib.Path(__file__).resolve().parent
p = argparse.ArgumentParser(); p.add_argument('--split', choices=['development', 'held_out'], default='development'); args = p.parse_args()
seeds = range(10) if args.split == 'development' else range(100, 110)
arms = ['ordinary', 'depth:0.02', 'depth:0.10', 'isotropic:0.02', 'isotropic:0.10', 'multistart']; rows = []
for baseline in [.1, 1.]:
    for seed in seeds:
        truth, initial, obs = parallax_case(seed, baseline)
        Fref = valid_cost(truth, obs); target = Fref+1e-4*(valid_cost(initial, obs)-Fref)
        for rep in range(3):
            offset = (seed+rep)%len(arms)
            for arm in arms[offset:]+arms[:offset]:
                final, result = solve_t6(initial, obs, arm, target, seed)
                rows.append({'baseline': baseline, 'seed': seed, 'rep': rep, 'arm': arm, 'target': target,
                             **result, **alignment_error(final, truth)})
        print(baseline, seed, 'done', flush=True)
(ROOT/f't6_{args.split}.json').write_text(json.dumps({'rows': rows}, indent=2, allow_nan=False)+'\n')
summary = {}
for baseline in [.1, 1.]:
    summary[baseline] = {}
    for arm in arms:
        a = [r for r in rows if r['baseline'] == baseline and r['arm'] == arm]
        pairs = []
        for seed in seeds:
            ours = [r for r in a if r['seed'] == seed]
            other = [r for r in rows if r['baseline'] == baseline and r['arm'] == 'ordinary' and r['seed'] == seed]
            if all(r['hit'] for r in ours+other): pairs.append(np.median([r['target_seconds'] for r in other])/np.median([r['target_seconds'] for r in ours]))
        summary[baseline][arm] = {'hits': sum(r['hit'] for r in a), 'runs': len(a),
                                  'speedup_vs_ordinary': float(np.median(pairs)) if pairs else None,
                                  'final_cost_median': float(np.median([r['cost'] for r in a])),
                                  'point_nrmse_median': float(np.median([r['point_nrmse'] for r in a])),
                                  'geometry_failures': sum(r['point_nrmse'] > .15 for r in a),
                                  'invalid_trials': sum(r.get('invalid_trials', 0) for r in a),
                                  'minimum_terminal_attempts': min(r['terminal_attempts'] for r in a)}
(ROOT/f't6_{args.split}_summary.json').write_text(json.dumps(summary, indent=2)+'\n'); print(json.dumps(summary, indent=2))
