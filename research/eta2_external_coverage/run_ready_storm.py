#!/usr/bin/env python3
"""Run a ready per-scene target stage without waiting for the other scene."""
import datetime
import fcntl
import json
from pathlib import Path
import statistics
import time
import run_eta2 as runner

P=Path(__file__).resolve().parent
scene='final-3068'
record=dict(recorded_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            amendment_sha256=runner.sha(P/'ORDER_NOTE_2.md'),
            original_protocol_sha256=runner.sha(P/'PROTOCOL.md'),
            native_helper_sha256=runner.sha(P/'run_eta2.py'),
            binary_sha256=runner.sha(runner.BINARY))
registration=P/'early-storm-order.json'
if registration.exists():
    assert json.loads(registration.read_text())['amendment_sha256']==record['amendment_sha256']
else:
    runner.write(registration,record)
files=[P/'evidence/ceres-storm'/f'{scene}-ceres-{profile}-600-{rep}.json'
       for profile in ['lm-10000','dogleg-10000'] for rep in range(1,4)]
print('Waiting for all six Final3068 Ceres endpoints.',flush=True)
while not all(f.exists() for f in files):
    time.sleep(10)
rows=[json.loads(f.read_text()) for f in files]
assert all(r['status']=='ok' for r in rows), 'A baseline failed; no early target certified.'
groups={profile:dict(rows=[r for r in rows if r['profile']==profile],
        median=statistics.median(r['cost'] for r in rows if r['profile']==profile))
        for profile in ['lm-10000','dogleg-10000']}
reference=min(groups,key=lambda k:groups[k]['median'])
first=groups[reference]['rows'][0]
target=1.01*groups[reference]['median']
ref=dict(target=target,reference_profile=reference,groups=groups,
         input_sha256=first['data_sha256'],initial=first['independent_score_init'])
path=P/'early-storm-targets.json'
if path.exists():
    assert json.loads(path.read_text())=={scene:ref}
else:
    runner.write(path,{scene:ref})
print('FROZEN',scene,target,'from',reference,'median',groups[reference]['median'],flush=True)
print('Waiting for the Final4585 initial audit to finish.',flush=True)
while 'RUN final-4585 ' not in (P/'ceres-progress.log').read_text():
    time.sleep(5)
with open('/tmp/prism_gpu.lock','w') as lock:
    print('Waiting for the next measurement boundary.',flush=True)
    fcntl.flock(lock,fcntl.LOCK_EX)
    runner.BATCH_LOCKED=True
    results=[runner.run(scene,'champion',rep,'storm',target,ref['input_sha256'],ref['initial'])
             for rep in range(10)]
    runner.write(P/'early-storm-results.json',results)
print('Final3068 target stage complete; the final controller will verify and reuse these rows.',flush=True)
