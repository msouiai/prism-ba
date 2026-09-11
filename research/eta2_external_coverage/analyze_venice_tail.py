#!/usr/bin/env python3
"""Read completed logs; distinguish tiny accepted progress from rejects."""
import csv
import json
from pathlib import Path
import re
import statistics

P = Path(__file__).resolve().parent
rows = json.loads((P / 'venice-results.json').read_text())
results = []
for r in rows:
    folder = P / r['source']
    with (folder / 'curve.csv').open() as f:
        curve = list(csv.DictReader(line for line in f if not line.startswith('#')))
    costs = [float(c['cost']) for c in curve]
    text = (folder / 'stdout.log').read_text()
    native = [dict(outer=int(o), norm=float(n), radius=float(rad), lam=float(l), rho=float(rho), accepted=int(a))
              for o,n,rad,l,rho,a in re.findall(r'ATTR_RADIUS o=(\d+) raw_norm=\S+ norm=(\S+) radius=(\S+) next_radius=\S+ lambda=(\S+) next_lambda=\S+ rho=(\S+) accept=(\d+)', text)]
    depths = [int(cg)+1 for cg in re.findall(r'MFCG it\s+\d+ cost=\S+ lam=\S+ tau=\S+ cg_it=(\d+)', text)]
    # In this binary cg_it is zero based on a forcing break. The final trace
    # reports cg_it=0 in the observed one-iteration tail; retain the raw log.
    last = native[-100:]
    gains = [a-b for a,b in zip(costs[-101:],costs[-100:])] if len(costs)>100 else []
    rr = dict(arm=r['arm'], rep=r['rep'], source=r['source'], hit=r['hit'],
              final_cost=r['cost'], outers=r['outers'], rejects=r['rejects'],
              last100_radius_rows=len(last), last100_accepts=sum(t['accepted'] for t in last),
              last100_max_norm_radius_ratio=max(t['norm']/t['radius'] for t in last),
              last100_median_rho=statistics.median(t['rho'] for t in last),
              final_lambda=last[-1]['lam'],
              last100_median_logged_cg_index=statistics.median(depths[-100:])-1,
              last100_median_gain=statistics.median(gains) if gains else None)
    results.append(rr)
(P / 'venice-tail-analysis.json').write_text(json.dumps(results, indent=2, allow_nan=False)+'\n')
for r in results:
    if r['arm']=='stop_disabled':
        print(r)
