#!/usr/bin/env python3
"""Reproduce the incumbent and capture a separate immutable diagnostic cohort."""
import csv
import fcntl
import hashlib
import json
import os
import pathlib
import re
import subprocess
import time

ROOT = pathlib.Path(__file__).resolve().parent
OUT = pathlib.Path(os.environ.get('PRISM_AGENDA_OUT', '/tmp/prism-geometry-agenda'))
OUT.mkdir(exist_ok=True)
cfg = json.loads((ROOT.parent/'eta2_champion/champion.json').read_text())
original = pathlib.Path('/tmp/prism-rl-actor/build/prism-tr')
diagnostic = ROOT/'build/prism-agenda-capture'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(original) == cfg['binary_sha256']
build = json.loads((ROOT/'build/capture-manifest.json').read_text())
assert sha(diagnostic) == build['binary_sha256']
base = {k: v for k, v in os.environ.items() if not k.startswith(('OCA_', 'CASPAR_', 'COLMAP_MFREE', 'MF_DEBUG'))}
cli = cfg['cli'].copy()
cli[cli.index('--max_iter')+1] = '12'
rows = []
with open('/tmp/prism_gpu.lock', 'w') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX)
    for scene in ['ladybug-49', 'dubrovnik-88', 'venice-52']:
        path = pathlib.Path('/workspace/bal')/(scene+'.txt')
        input_sha = sha(path)
        for rep in range(3):
            for arm in (['original', 'off'] if rep%2 == 0 else ['off', 'original']):
                binary = original if arm == 'original' else diagnostic
                folder = OUT/f't1-{scene}-{arm}-{rep}'
                folder.mkdir(exist_ok=True)
                record = folder/'result.json'
                if record.exists():
                    rows.append(json.loads(record.read_text()))
                    continue
                command = [str(binary), '--problem', str(path), *cli, '--csv', str(folder/'curve.csv')]
                started = time.monotonic()
                print('RUN', folder.name, flush=True)
                with (folder/'stdout.log').open('w') as out, (folder/'stderr.log').open('w') as err:
                    p = subprocess.run(command, env=base | cfg['flags'], stdout=out, stderr=err, timeout=60)
                text = (folder/'stdout.log').read_text()
                m = re.search(r'RESULT algo=\S+ iters=(\d+) final_cost=(\S+) solve_seconds=(\S+)', text)
                assert p.returncode == 0 and m, folder
                row = {'scene': scene, 'arm': arm, 'rep': rep, 'input_sha256': input_sha, 'binary_sha256': sha(binary),
                       'command': command, 'flags': cfg['flags'], 'returncode': p.returncode,
                       'process_seconds': time.monotonic()-started, 'outers': int(m[1]),
                       'cost': float(m[2]), 'native_seconds': float(m[3])}
                record.write_text(json.dumps(row, indent=2)+'\n')
                rows.append(row)
                print('RESULT', scene, arm, row['cost'], row['native_seconds'], flush=True)
        folder = OUT/f't1-{scene}-capture'
        folder.mkdir(exist_ok=True)
        record = folder/'result.json'
        if record.exists():
            continue
        captures = folder/'captures'
        captures.mkdir(exist_ok=True)
        flags = cfg['flags'] | {'OCA_AGENDA_CAPTURE': str(captures/'candidate'), 'OCA_AGENDA_OUTERS': '12'}
        command = [str(diagnostic), '--problem', str(path), *cli, '--csv', str(folder/'curve.csv')]
        print('CAPTURE', scene, flush=True)
        started = time.monotonic()
        with (folder/'stdout.log').open('w') as out, (folder/'stderr.log').open('w') as err:
            p = subprocess.run(command, env=base | flags, stdout=out, stderr=err, timeout=60)
        text = (folder/'stdout.log').read_text()
        m = re.search(r'RESULT algo=\S+ iters=(\d+) final_cost=(\S+) solve_seconds=(\S+)', text)
        assert p.returncode == 0 and m, folder
        row = {'scene': scene, 'arm': 'capture', 'rep': 0, 'input_sha256': input_sha,
               'binary_sha256': sha(diagnostic), 'command': command, 'flags': flags,
               'returncode': p.returncode, 'outers': int(m[1]), 'cost': float(m[2]),
               'native_seconds': float(m[3]), 'process_seconds': time.monotonic()-started,
               'captures': len(list(captures.glob('*.state')))}
        record.write_text(json.dumps(row, indent=2)+'\n')
        print('CAPTURED', scene, row['captures'], row['cost'], flush=True)
(OUT/'t1-baselines.json').write_text(json.dumps(rows, indent=2)+'\n')
print('DONE T1 capture cohort', flush=True)
