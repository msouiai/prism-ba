"""Post-result geometry-only replay; never replaces registered timing rows."""
import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'; os.environ['OMP_NUM_THREADS'] = '1'
import json
import pathlib
import numpy as np
from collective import clustered, solve_t4
from reference_ba import valid_cost
from experiment import alignment_error

ROOT = pathlib.Path(__file__).resolve().parent
original = json.loads((ROOT/'t4_held_out.json').read_text())['rows']
rows = []
for bridges in [4, 16, 0]:
    for seed in range(100, 110):
        truth, initial, obs, cg, pg, *_ = clustered(seed, bridges=bridges)
        ref = valid_cost(truth, obs); target = ref+1e-4*(valid_cost(initial, obs)-ref)
        for arm in ['fine', 'linear', 'nonlinear']:
            final, result = solve_t4(initial, obs, cg, pg, arm, target)
            gauge = alignment_error(final, truth)
            ratios = []
            for group in range(3):
                X = final.X[pg == group]; Y = truth.X[pg == group]
                ratios.append(float(np.sqrt(np.mean(np.sum((X-X.mean(axis=0))**2, axis=1)) /
                                            np.mean(np.sum((Y-Y.mean(axis=0))**2, axis=1)))))
            relative_log = np.log(np.array(ratios)/ratios[0])
            old = [r['cost'] for r in original if r['bridges'] == bridges and r['seed'] == seed and r['arm'] == arm]
            disagreement = abs(result['cost']-np.median(old))/max(1., abs(np.median(old)))
            rows.append({'bridges': bridges, 'seed': seed, 'arm': arm, 'cost': result['cost'],
                         'original_endpoint_relative_difference': float(disagreement),
                         'globally_scaled_cluster_size_ratios': (gauge['global_scale']*np.array(ratios)).tolist(),
                         'relative_cluster_log_scale_errors': relative_log.tolist(),
                         'max_abs_relative_log_scale_error': float(np.max(np.abs(relative_log))), **gauge})
            np.savez_compressed(ROOT/'evidence'/f't4-final-{bridges}-{seed}-{arm}.npz', R=final.R, t=final.t,
                                X=final.X, intr=final.intr, observations=obs, camera_groups=cg, point_groups=pg)
summary = {}
for bridges in [4, 16, 0]:
    summary[bridges] = {arm: float(np.median([r['max_abs_relative_log_scale_error'] for r in rows
                                             if r['bridges'] == bridges and r['arm'] == arm])) for arm in ['fine', 'linear', 'nonlinear']}
result = {'scope': 'Post-result, geometry-only N=1 replay of previously registered seeds; original timing unchanged.',
          'metric': 'Within-cluster RMS point radius ratio relative to cluster0; no independent cluster fit/alignment. Measures size, also affected by internal distortion.',
          'max_endpoint_relative_difference': max(r['original_endpoint_relative_difference'] for r in rows),
          'summary': summary, 'rows': rows}
(ROOT/'t4_relative_scale_audit.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
print(json.dumps({'max_endpoint_relative_difference': result['max_endpoint_relative_difference'], 'summary': summary}, indent=2))
