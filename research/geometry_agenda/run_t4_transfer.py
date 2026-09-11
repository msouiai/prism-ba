import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'; os.environ['OMP_NUM_THREADS'] = '1'
import argparse
import json
import pathlib
import time
import numpy as np
from collective import clustered, solve_t4
from partition import automatic_partition, partition_agreement
from reference_ba import valid_cost
from experiment import alignment_error

ROOT = pathlib.Path(__file__).resolve().parent
p = argparse.ArgumentParser(); p.add_argument('--size', choices=['small', 'larger'], default='small')
p.add_argument('--confidence', action='store_true'); p.add_argument('--development', action='store_true'); args = p.parse_args()
seeds = range(10) if args.development else range(300, 310) if args.confidence else range(200, 210)
suffix = args.size+('_v2' if args.confidence else '')+('_development' if args.development else '')
nc, np_ = (4, 60) if args.size == 'small' else (10, 300)
arms = ['fine', 'known-linear', 'known-nonlinear', 'auto-linear', 'auto-nonlinear']; rows = []
for bridges in [4, 16]:
    for seed in seeds:
        truth, initial, obs, true_c, true_p, bridge, _ = clustered(seed, bridges=bridges, cameras=nc, points=np_)
        target = valid_cost(truth, obs)+1e-4*(valid_cost(initial, obs)-valid_cost(truth, obs))
        for rep in range(3):
            offset = (seed+rep)%len(arms)
            for arm in arms[offset:]+arms[:offset]:
                start = time.perf_counter(); setup = 0.
                cg, pg = true_c, true_p
                if arm.startswith('auto'):
                    cg, pg = automatic_partition(initial, obs, confidence=args.confidence)
                    setup = time.perf_counter()-start
                final, result = solve_t4(initial, obs, cg, pg, arm.split('-')[-1], target, cap=max(0., 2-setup))
                result['seconds'] += setup
                result['trace'] = [{**r, 'seconds': r['seconds']+setup} for r in result['trace']]
                rows.append({'bridges': bridges, 'seed': seed, 'rep': rep, 'arm': arm, 'target': target,
                             'setup_seconds': setup, **result, **alignment_error(final, truth),
                             **partition_agreement(cg, pg, true_c, true_p)})
        print(args.size, bridges, seed, 'done', flush=True)
(ROOT/f't4_transfer_{suffix}.json').write_text(json.dumps({'rows': rows}, indent=2, allow_nan=False)+'\n')
summary = {}
for bridges in [4, 16]:
    summary[bridges] = {}
    for arm in arms:
        a = [r for r in rows if r['bridges'] == bridges and r['arm'] == arm]
        ratios = {}
        for base in ['fine', 'auto-linear']:
            pairs = []
            for seed in seeds:
                ours = [r for r in a if r['seed'] == seed]
                other = [r for r in rows if r['bridges'] == bridges and r['arm'] == base and r['seed'] == seed]
                if all(r['hit'] for r in ours+other): pairs.append(np.median([r['seconds'] for r in other])/np.median([r['seconds'] for r in ours]))
            ratios[base] = float(np.median(pairs)) if pairs else None
        summary[bridges][arm] = {'hits': sum(r['hit'] for r in a), 'runs': len(a), 'speedup': ratios,
                                 'geometric_failures': sum(r['point_nrmse'] > .15 for r in a),
                                 'point_nrmse_median': float(np.median([r['point_nrmse'] for r in a])),
                                 'partition_camera_min': min(r['camera_agreement'] for r in a),
                                 'partition_point_min': min(r['point_agreement'] for r in a),
                                 'setup_fraction': sum(r['setup_seconds'] for r in a)/sum(r['seconds'] for r in a)}
(ROOT/f't4_transfer_{suffix}_summary.json').write_text(json.dumps(summary, indent=2)+'\n'); print(json.dumps(summary, indent=2))
