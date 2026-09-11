#!/usr/bin/env python3
"""Complete the registered target stage once all Ceres endpoints are available."""
import json
from pathlib import Path
import subprocess
import sys
import time

P = Path(__file__).resolve().parent
expected = [P / 'evidence/ceres-storm' / f'{scene}-ceres-{profile}-600-{rep}.json'
            for scene in ['final-3068', 'final-4585']
            for profile in ['lm-10000', 'dogleg-10000'] for rep in range(1, 4)]
print('Waiting for the twelve registered Ceres endpoints; no new configuration.', flush=True)
while not all(p.exists() for p in expected):
    time.sleep(15)
rows = [json.loads(p.read_text()) for p in expected]
if not all(r['status'] == 'ok' for r in rows):
    print('Ceres failures retained; a complete baseline target cannot yet be certified.', flush=True)
    raise SystemExit(2)
subprocess.run([sys.executable, str(P / 'run_eta2.py'), 'storm', '--batch-lock'], check=True)
subprocess.run([sys.executable, str(P / 'summarize.py')], check=True)
print('Registered storm target stage complete.', flush=True)
