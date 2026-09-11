import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'; os.environ['OMP_NUM_THREADS'] = '1'
import argparse
import json
import pathlib
import numpy as np
from reference_ba import synthetic, valid_cost, Linearization
from geometry import retract
from point_relaxation import solve_t3, polish, stationarity
from experiment import alignment_error

ROOT = pathlib.Path(__file__).resolve().parent
p = argparse.ArgumentParser(); p.add_argument('--split', choices=['development', 'held_out'], default='development'); args = p.parse_args()
seeds = range(10) if args.split == 'development' else range(100, 110)
arms = ['raw', 'post1', 'post3', 'pre1', 'pre3', 'selective']; rows = []; diagnostic = []
for mode in ['depth', 'rotation']:
    for seed in seeds:
        truth, initial, obs = synthetic(seed, mode)
        target = valid_cost(truth, obs)+1e-4*(valid_cost(initial, obs)-valid_cost(truth, obs))
        parent_copy = initial.copy(); lin = Linearization(initial, obs)
        for lam in [.025, .1, .4]:
            trial = retract(initial, *lin.factor(lam).solve())
            if np.isfinite(valid_cost(trial, obs)):
                for steps in [0, 1, 3, 30]:
                    result = polish(trial, obs, steps)
                    diagnostic.append({'family': mode, 'seed': seed, 'lambda': lam, 'steps': steps,
                                       'cost': valid_cost(result, obs), 'point_stationarity': stationarity(result, obs)})
        assert np.array_equal(initial.X, parent_copy.X) and np.array_equal(initial.R, parent_copy.R)
        for rep in range(3):
            offset = (seed+rep)%len(arms)
            for arm in arms[offset:]+arms[:offset]:
                final, result = solve_t3(initial, obs, arm, target)
                rows.append({'family': mode, 'seed': seed, 'rep': rep, 'arm': arm, 'target': target,
                             **result, **alignment_error(final, truth), 'point_stationarity': stationarity(final, obs)})
        print(mode, seed, 'done', flush=True)
(ROOT/f't3_{args.split}.json').write_text(json.dumps({'rows': rows, 'initial_point_references': diagnostic}, indent=2, allow_nan=False)+'\n')
summary = {}
for arm in arms:
    rr = [r for r in rows if r['arm'] == arm]; ratios = {}; comparison = ['raw', 'post1', 'post3']
    for base in comparison:
        v = []
        for family, seed in sorted(set((r['family'], r['seed']) for r in rr)):
            a = [r for r in rr if r['family'] == family and r['seed'] == seed]
            b = [r for r in rows if r['family'] == family and r['seed'] == seed and r['arm'] == base]
            if all(r['hit'] for r in a+b): v.append(np.median([r['seconds'] for r in b])/np.median([r['seconds'] for r in a]))
        ratios[base] = float(np.median(v)) if v else None
    summary[arm] = {'hits': sum(r['hit'] for r in rr), 'runs': len(rr), 'speedup': ratios,
                    'changed_winner_fraction': sum(r['changed_winners'] for r in rr)/sum(r['menus'] for r in rr),
                    'point_time_fraction': sum(r['work_seconds'].get('point_polish', 0) for r in rr)/sum(r['seconds'] for r in rr),
                    'geometric_failures': sum(r['point_nrmse'] > .15 for r in rr)}
(ROOT/f't3_{args.split}_summary.json').write_text(json.dumps(summary, indent=2)+'\n'); print(json.dumps(summary, indent=2))
