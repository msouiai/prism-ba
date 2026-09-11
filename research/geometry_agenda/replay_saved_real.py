"""Strict frozen-input/frozen-target T4 repeat; preserve published timings."""
import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'; os.environ['OMP_NUM_THREADS'] = '1'
import json
import pathlib
import time
import numpy as np
from geometry import State
from collective import solve_t4
from partition import automatic_partition

ROOT = pathlib.Path(__file__).resolve().parent
rows = []
for case in json.loads((ROOT/'t4_real_targets.json').read_text()):
    packed = np.load(ROOT/case['input'])
    initial = State(*[packed[k].copy() for k in ['R', 't', 'X', 'intr']]); obs = packed['observations']
    arms = ['fine', 'linear', 'nonlinear']
    for rep in range(3):
        for arm in arms[rep:]+arms[:rep]:
            start = time.perf_counter(); cg = pg = None
            if arm != 'fine': cg, pg = automatic_partition(initial, obs, confidence=True)
            setup = time.perf_counter()-start
            _, result = solve_t4(initial, obs, cg, pg, arm, case['target'], cap=max(0., 2-setup))
            result['seconds'] += setup
            result['trace'] = [{**t, 'seconds': t['seconds']+setup} for t in result['trace']]
            rows.append({'scene': case['scene'], 'rep': rep, 'arm': arm, 'target': case['target'],
                         'setup_seconds': setup, **result})
(ROOT/'t4_real_replay.json').write_text(json.dumps({'rows': rows}, indent=2, allow_nan=False)+'\n')
print('saved separate frozen-target replay')
