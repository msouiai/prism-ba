"""Paired seed bootstrap; timing repeats are not independent scenes."""
import json
import pathlib
import numpy as np
ROOT = pathlib.Path(__file__).resolve().parent
specs = []
for size in ['small', 'larger']:
    for bridges in [4, 16]:
        for base in ['fine', 'auto-linear']:
            specs.append((f't4_transfer_{size}_v2', {'bridges': bridges}, base, 'auto-nonlinear'))
for family in ['depth', 'cluster', 'rotation']:
    for base in ['fresh', 'rule']:
        specs.append(('t8_held_out', {'family': family}, base, 'tree'))
rows = []; rng = np.random.default_rng(814)
for filename, filt, base, arm in specs:
    data = json.loads((ROOT/(filename+'.json')).read_text())['rows']
    data = [r for r in data if all(r.get(k) == v for k, v in filt.items())]
    ratios = []; missing = []
    for seed in sorted(set(r['seed'] for r in data)):
        a = [r for r in data if r['seed'] == seed and r['arm'] == arm]
        b = [r for r in data if r['seed'] == seed and r['arm'] == base]
        if all(r['hit'] for r in a+b):
            ratios.append(float(np.median([r.get('target_seconds') or r['seconds'] for r in b])/
                                np.median([r.get('target_seconds') or r['seconds'] for r in a])))
        else: missing.append(seed)
    boot = np.median(rng.choice(ratios, (10000, len(ratios)), replace=True), axis=1)
    rows.append({'file': filename, 'filter': filt, 'baseline': base, 'arm': arm,
                 'seed_ratios': ratios, 'excluded_miss_seeds': missing,
                 'median': float(np.median(ratios)), 'percentile95': np.quantile(boot, [.025, .975]).tolist()})
(ROOT/'paired_uncertainty.json').write_text(json.dumps({'scope': 'Conditional paired-seed bootstrap; ten seeds, N=3 median per arm. Not cross-host or population certainty. Failed pairs explicitly listed.', 'seed': 814, 'rows': rows}, indent=2)+'\n')
print(json.dumps(rows, indent=2))
