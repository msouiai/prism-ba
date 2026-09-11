#!/usr/bin/env python3
"""Endpoint and identical-target tables; never count rejected Ceres trials."""
import csv
import json
import math
from pathlib import Path
import re
import statistics

P = Path(__file__).resolve().parent
targets = json.loads((P / 'storm-targets.json').read_text()) if (P / 'storm-targets.json').exists() else {}
rows = []
for f in sorted((P / 'evidence/ceres-storm').glob('*.json')):
    if f.name == 'preregistered.json':
        continue
    r = json.loads(f.read_text())
    row = dict(scene=r['scene'], arm=r.get('profile', r['arm'].removeprefix('ceres-').rsplit('-', 1)[0]),
               rep=r['rep'], stage='ceres-storm', valid=r['status'] == 'ok',
               source=str(f.relative_to(P)), solver='ceres', hit=None, target=None, target_seconds=None)
    if r['scene'] in targets:
        row.update(target=targets[r['scene']]['target'], hit=False)
    if row['valid']:
        log = f.with_suffix('.log').read_text()
        trace = [dict(iter=int(i), cost=float(c), seconds=float(t), accepted=bool(int(a)))
                 for i, c, t, a in re.findall(r'TRACE iter=(\d+) cost=(\S+) seconds=(\S+) accepted=(\d+)', log)]
        accepted = [t for t in trace if t['accepted']]
        assert accepted and all(math.isfinite(t['cost']) for t in accepted)
        assert all(b['cost'] <= a['cost'] + 1e-8 * max(1, a['cost']) for a, b in zip(accepted, accepted[1:]))
        assert abs(accepted[-1]['cost'] - r['cost']) / max(1, r['cost']) < 1e-6
        assert r['native_cost_relerr'] < 1e-6
        termination = re.search(r'Termination:\s*(.+)', log)
        row.update(cost=r['cost'], native_seconds=r['seconds'], setup_seconds=r['setup_seconds'],
                   outers=sum(t['iter'] > 0 for t in trace),
                   accepts=sum(t['iter'] > 0 and t['accepted'] for t in trace),
                   rejects=sum(t['iter'] > 0 and not t['accepted'] for t in trace),
                   stop_reason=termination[1] if termination else 'unparsed',
                   exit_reason=r['exit_reason'], cap_hit=r['exit_reason'] == 1,
                   trace_accepted=accepted, audit_relative_error=r['native_cost_relerr'])
        if r['scene'] in targets:
            target = targets[r['scene']]['target']
            crossing = next((t['seconds'] for t in accepted if t['cost'] <= target), None)
            row.update(target=target, target_seconds=crossing, hit=crossing is not None,
                       target_gap=r['cost'] / target - 1)
    rows.append(row)

for stage in ['venice', 'storm', 'venice-probes']:
    for f in sorted((P / 'evidence' / stage).glob('*/result.json')):
        r = json.loads(f.read_text())
        r['solver'] = 'eta2'
        rows.append(r)

summary = []
for key in sorted({(r['stage'], r['scene'], r['arm']) for r in rows}):
    rr = [r for r in rows if (r['stage'], r['scene'], r['arm']) == key]
    good = [r for r in rr if r['valid']]
    hits = [r['target_seconds'] for r in good if r['hit']]
    target_registered = all(r.get('target') is not None for r in rr)
    item = dict(stage=key[0], scene=key[1], arm=key[2], n=len(rr), valid=len(good),
                target_registered=target_registered, hits=len(hits) if target_registered else None)
    for field in ['cost', 'native_seconds', 'outers', 'accepts', 'rejects', 'matvecs']:
        values = [r[field] for r in good if field in r]
        if values:
            item[field] = dict(median=statistics.median(values), min=min(values), max=max(values))
    item['target_seconds'] = dict(median=statistics.median(hits), min=min(hits), max=max(hits)) if hits else None
    item['stops'] = {s:sum(r.get('stop_reason') == s for r in rr) for s in sorted({r.get('stop_reason', 'invalid') for r in rr})}
    summary.append(item)

(P / 'all-results.json').write_text(json.dumps(rows, indent=2, allow_nan=False) + '\n')
(P / 'summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n')
flat = [{k:v for k,v in r.items() if not isinstance(v, (dict, list))} for r in rows]
if flat:
    with (P / 'runs.csv').open('w') as f:
        writer = csv.DictWriter(f, fieldnames=sorted(set().union(*(r.keys() for r in flat))), lineterminator='\n')
        writer.writeheader()
        writer.writerows(flat)
for r in summary:
    print(r['stage'], r['scene'], r['arm'], 'N', r['n'], 'hits', r['hits'],
          'cost', r.get('cost'), 'target_seconds', r['target_seconds'])
