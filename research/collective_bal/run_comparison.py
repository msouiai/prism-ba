import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'; os.environ['OMP_NUM_THREADS'] = '1'
import json
import time
import numpy as np
from paths import ROOT
from geometry import State, project
from reference_ba import valid_cost
from experiment import solve_t2
from collective import coarse_solve
from partition import automatic_partition
from bridge_coarse import solve_bridge, selection_features

ARMS = ['fine', 'linear8', 'nonlinear8', 'bridge8', 'selective']

def run(initial, obs, target, arm):
    start = time.perf_counter(); cap = 5.; state = initial.copy()
    trace = [{'seconds': 0., 'cost': valid_cost(state, obs)}]
    partition_seconds = feature_seconds = coarse_seconds = 0.
    features = None; coarse = None; failure = None; skip = False
    if arm != 'fine':
        try:
            t0 = time.perf_counter(); cg, pg = automatic_partition(state, obs, confidence=True)
            partition_seconds = time.perf_counter()-t0
            if arm == 'selective':
                t0 = time.perf_counter(); features = selection_features(state, obs, cg, pg)
                feature_seconds = time.perf_counter()-t0; skip = not features['selected']
            if not skip:
                offset = time.perf_counter()-start
                if arm in ['bridge8', 'selective']:
                    state, coarse = solve_bridge(state, obs, cg, pg, target=target, deadline=start+cap)
                else:
                    state, coarse = coarse_solve(state, obs, cg, pg, nonlinear=arm == 'nonlinear8',
                                                 target=target, deadline=start+cap)
                coarse_seconds = coarse['seconds']
                trace += [{**r, 'seconds': r['seconds']+offset} for r in coarse['trace']]
        except np.linalg.LinAlgError as error:
            state = initial.copy(); failure = str(error)
    offset = time.perf_counter()-start
    final, fine = solve_t2(state, obs, 'lm', target, cap=max(0., cap-offset), max_attempts=80)
    trace += [{**r, 'seconds': r['seconds']+offset} for r in fine['trace'][1:]]
    elapsed = time.perf_counter()-start
    # Validation cost is part of total elapsed time in the bridge solver. This
    # read-only final domain diagnostic is outside all arms' timed solve.
    q = project(final, obs, 6)[1]
    return {'arm': arm, 'seconds': elapsed, 'target_seconds': elapsed if fine['hit'] else None,
            'hit': fine['hit'], 'cost': fine['cost'], 'cap_hit': fine['cap_hit'],
            'partition_seconds': partition_seconds, 'feature_seconds': feature_seconds,
            'coarse_seconds': coarse_seconds, 'coarse': coarse, 'fine': fine,
            'selector': features, 'skipped': skip, 'failure': failure, 'trace': trace,
            'invalid_final_depths': int(np.sum(q[:, 2] >= -1e-8))}

rows = []; geometry = []
for case in json.loads((ROOT/'frozen_cases.json').read_text())['cases']:
    a = np.load(ROOT/case['path']); initial = State(*[a[k].copy() for k in ['R','t','X','intr']]); obs = a['observations']
    # Pure explanatory diagnostics are outside timing; deployed selective arm
    # independently pays its own partition and feature costs inside run().
    cg, pg = automatic_partition(initial, obs, confidence=True)
    feature = selection_features(initial, obs, cg, pg)
    geometry.append({'scene': case['scene'], 'seed': case['seed'], **feature})
    np.savez_compressed(ROOT/'evidence'/f"partition-{case['scene']}-{case['seed']}.npz", cg=cg, pg=pg)
    for rep in range(3):
        offset = (case['seed']+rep)%len(ARMS)
        for arm in ARMS[offset:]+ARMS[:offset]:
            result = run(initial, obs, case['target'], arm)
            rows.append({'scene': case['scene'], 'seed': case['seed'], 'rep': rep,
                         'target': case['target'], **result})
    (ROOT/'results.json').write_text(json.dumps({'geometry': geometry, 'rows': rows}, indent=2, allow_nan=False)+'\n')
    print(case['scene'], case['seed'], feature, flush=True)
    print({arm: round(float(np.median([r['seconds'] for r in rows if r['scene']==case['scene'] and r['seed']==case['seed'] and r['arm']==arm])),4) for arm in ARMS}, flush=True)

summary = {}
for scene in ['ladybug-49', 'dubrovnik-88', 'venice-52', 'all']:
    summary[scene] = {}
    subset = [r for r in rows if scene == 'all' or r['scene'] == scene]
    for arm in ARMS:
        a = [r for r in subset if r['arm'] == arm]; comparisons = {}
        for base in ['fine', 'nonlinear8']:
            ratios = []; misses = []
            for sc, seed in sorted(set((r['scene'], r['seed']) for r in a)):
                x = [r for r in a if r['scene']==sc and r['seed']==seed]
                y = [r for r in subset if r['scene']==sc and r['seed']==seed and r['arm']==base]
                if all(r['hit'] for r in x+y): ratios.append(float(np.median([r['seconds'] for r in y])/np.median([r['seconds'] for r in x])))
                else: misses.append([sc,seed])
            comparisons[base] = {'median_speedup': float(np.median(ratios)) if ratios else None,
                                 'paired_ratios': ratios, 'failed_pairs': misses}
        summary[scene][arm] = {'hits': sum(r['hit'] for r in a), 'runs': len(a),
            'seconds_median': float(np.median([r['seconds'] for r in a])), 'cost_median': float(np.median([r['cost'] for r in a])),
            'comparisons': comparisons, 'partition_fraction': sum(r['partition_seconds'] for r in a)/sum(r['seconds'] for r in a),
            'coarse_fraction': sum(r['coarse_seconds'] for r in a)/sum(r['seconds'] for r in a),
            'coarse_seconds_median': float(np.median([r['coarse_seconds'] for r in a])),
            'fine_accepted_median': float(np.median([r['fine']['accepted'] for r in a])),
            'fine_reject_median': float(np.median([r['fine']['rejected_attempts'] for r in a])),
            'max_full_cost_disagreement': max([r['coarse']['full_cost_relative_disagreement'] for r in a if r['coarse'] and 'full_cost_relative_disagreement' in r['coarse']], default=0.),
            'invalid_final_depths': sum(r['invalid_final_depths'] for r in a),
            'numerical_failures': sum(r['failure'] is not None for r in a), 'skipped': sum(r['skipped'] for r in a)}
(ROOT/'summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False)+'\n')
print(json.dumps(summary, indent=2))
