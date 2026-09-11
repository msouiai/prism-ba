import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'; os.environ['OMP_NUM_THREADS'] = '1'
import json
import pathlib
import numpy as np
from geometry import project
from experiment import alignment_error
from allocation import ACTIONS, solve_t8
from t8_replay import cases

ROOT = pathlib.Path(__file__).resolve().parent
tree = json.loads((ROOT/'t8_frozen_policy.json').read_text())['tree']
arms = ACTIONS+['rule', 'tree']; rows = []
for family, seed, truth, initial, obs, ref, target in cases('held_out'):
    for rep in range(3):
        offset = (seed+rep)%len(arms)
        for arm in arms[offset:]+arms[:offset]:
            final, result = solve_t8(initial, obs, arm, target, tree)
            geometry = alignment_error(final, truth) if truth is not None else {}
            rows.append({'family': family, 'seed': seed, 'rep': rep, 'arm': arm,
                         'target': target, 'reference': ref, **result, **geometry,
                         'invalid_final_depths': int(np.count_nonzero(project(final, obs, 6)[1][:, 2] >= -1e-8))})
    print(family, seed, 'done', flush=True)
(ROOT/'t8_held_out.json').write_text(json.dumps({'rows': rows}, indent=2, allow_nan=False)+'\n')
summary = {}
for family in sorted(set(r['family'] for r in rows)):
    summary[family] = {}
    for arm in arms:
        subset = [r for r in rows if r['family'] == family and r['arm'] == arm]; ratios = {}
        for base in ['fresh', 'rule']:
            pairs = []
            for seed in sorted(set(r['seed'] for r in subset)):
                a = [r for r in subset if r['seed'] == seed]
                b = [r for r in rows if r['family'] == family and r['seed'] == seed and r['arm'] == base]
                if all(r['hit'] for r in a+b): pairs.append(np.median([r['seconds'] for r in b])/np.median([r['seconds'] for r in a]))
            ratios[base] = float(np.median(pairs)) if pairs else None
        summary[family][arm] = {'hits': sum(r['hit'] for r in subset), 'runs': len(subset), 'speedup': ratios,
                                'geometric_failures': sum(r.get('point_nrmse', 0) > .15 for r in subset) if 'point_nrmse' in subset[0] else None,
                                'cost_median': float(np.median([r['cost'] for r in subset])),
                                'seconds_median': float(np.median([r['seconds'] for r in subset])),
                                'feature_fraction': sum(r['work_seconds'].get('features', 0)+r['work_seconds'].get('inference', 0) for r in subset)/sum(r['seconds'] for r in subset),
                                'actions': {a: sum(d['action'] == a for r in subset for d in r['decisions']) for a in ACTIONS}}
(ROOT/'t8_held_out_summary.json').write_text(json.dumps(summary, indent=2)+'\n'); print(json.dumps(summary, indent=2))
