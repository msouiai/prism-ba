#!/usr/bin/env python3
"""Two declared exploratory probes using the unchanged audited native helper."""
import fcntl
import json
from pathlib import Path
import time
import run_eta2 as runner

P = Path(__file__).resolve().parent
registration = P / 'probe-registration.json'
record = dict(protocol_sha256=runner.sha(P / 'PROBE_PROTOCOL.md'),
              native_helper_sha256=runner.sha(P / 'run_eta2.py'),
              binary_sha256=runner.sha(runner.BINARY),
              target=243740.27, reps=3, outer_cap=600, native_cap=60,
              primary_results_available_at_registration=len(list((P / 'evidence/venice').glob('*/result.json'))))
if registration.exists():
    assert json.loads(registration.read_text())['protocol_sha256'] == record['protocol_sha256']
else:
    runner.write(registration, record)
print('Registered two exploratory probes; waiting for the primary Venice stage.', flush=True)
while not (P / 'venice-results.json').exists():
    time.sleep(10)
with open('/tmp/prism_gpu.lock', 'w') as lock:
    print('Waiting for the next measurement boundary.', flush=True)
    fcntl.flock(lock, fcntl.LOCK_EX)
    runner.BATCH_LOCKED = True
    flags = dict(runner.CHAMP['flags'])
    ref = json.loads((P / 'provenance/venice-52-ceres-lm-10000-600-1.json').read_text())
    arms = ['probe_relaxed_ftol', 'probe_tighter_forcing']
    rows = []
    for rep in range(3):
        for arm in arms[rep % 2:] + arms[:rep % 2]:
            runner.CHAMP['flags'] = dict(flags)
            runner.CHAMP['flags']['OCA_FTOL'] = '1e-7' if arm == arms[0] else '0'
            if arm == arms[1]:
                runner.CHAMP['flags']['OCA_RLA_FIXED_ETA'] = '0.1'
            rows.append(runner.run('venice-52', arm, rep, 'venice-probes', 243740.27,
                        ref['data_sha256'], ref['independent_score_init']))
    runner.write(P / 'venice-probe-results.json', rows)
print('Exploratory probes complete; no champion changes.', flush=True)
