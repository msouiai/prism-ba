#!/usr/bin/env python3
"""Exact geometry diagnostics from immutable native proposals; no solver changes."""
import hashlib
import json
import os
import pathlib
import re
import statistics
import time
import numpy as np
from geometry import read_capture, read_observations, diagnostics

ROOT = pathlib.Path(__file__).resolve().parent
OUT = pathlib.Path(os.environ.get('PRISM_AGENDA_OUT', '/tmp/prism-geometry-agenda'))
rows = []
for scene in ['ladybug-49', 'dubrovnik-88', 'venice-52']:
    folder = OUT/f't1-{scene}-capture'
    dims, obs = read_observations(pathlib.Path('/workspace/bal')/(scene+'.txt'))
    expected = json.loads((folder/'result.json').read_text())['captures']
    items = sorted((folder/'captures').glob('*.state'), key=lambda p: int(p.stem.rsplit('-', 1)[1]))
    assert len(items) == expected
    print('AUDIT', scene, len(items), flush=True)
    for path in items:
        stem = path.with_suffix('')
        meta = json.loads(stem.with_suffix('.json').read_text())
        context = json.loads(pathlib.Path(str(stem)+'.meta.json').read_text())
        s, dc, dp, no = read_capture(stem)
        assert no == len(obs) and np.all(dc[:, 8] == 0)
        start = time.perf_counter()
        d = diagnostics(s, dc, dp, obs)
        d['cpu_diagnostic_seconds'] = time.perf_counter()-start
        d['parent_audit_relative'] = abs(d['cost']/meta['cost']-1)
        assert d['parent_audit_relative'] < 1e-7, (path, d['parent_audit_relative'])
        if meta['trial'] >= 0:
            assert d['trial_cost'] is not None
            d['trial_audit_relative'] = abs(d['trial_cost']/meta['trial']-1)
            assert d['trial_audit_relative'] < 1e-7, (path, d['trial_audit_relative'])
        else:
            assert d['trial_cost'] is None
        if d['finite']:
            assert d['decomposition_relative_error'] < 1e-7, path
        rows.append({'scene': scene, 'candidate': path.stem,
                     'parent_sha256': hashlib.sha256(path.read_bytes()).hexdigest(), **meta, **context, **d})
    print('AUDITED', scene, flush=True)
(ROOT/'t1_capture_diagnostics.json').write_text(json.dumps(rows, indent=2, allow_nan=False)+'\n')
baseline = json.loads((OUT/'t1-baselines.json').read_text())
summary = []
for scene in ['ladybug-49', 'dubrovnik-88', 'venice-52']:
    rr = [r for r in rows if r['scene'] == scene]
    bb = [r for r in baseline if r['scene'] == scene]
    original = statistics.median(r['cost'] for r in bb if r['arm'] == 'original')
    off = statistics.median(r['cost'] for r in bb if r['arm'] == 'off')
    capture = json.loads((OUT/f't1-{scene}-capture/result.json').read_text())
    summary.append({'scene': scene, 'original_median_cost': original, 'off_median_cost': off,
                    'off_relative_cost_difference': off/original-1,
                    'capture_cost': capture['cost'], 'capture_relative_cost_difference': capture['cost']/original-1,
                    'captures': len(rr), 'failed_cost': sum(r['failed_cost'] for r in rr),
                    'failed_strict_model': sum(r['failed_strict_model'] for r in rr),
                    'median_model_defect': statistics.median(r['model_defect'] for r in rr if r['finite']),
                    'max_parent_audit_relative': max(r['parent_audit_relative'] for r in rr),
                    'max_trial_audit_relative': max((r.get('trial_audit_relative', 0) for r in rr)),
                    'max_reduced_residual_difference': max(abs(r['raw_reduced_true_residual']-r['raw_reduced_recurrence_residual']) for r in rr)})
(ROOT/'t1_capture_summary.json').write_text(json.dumps(summary, indent=2)+'\n')
print(json.dumps(summary, indent=2))
