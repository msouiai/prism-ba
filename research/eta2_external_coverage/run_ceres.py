#!/usr/bin/env python3
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

P = Path(__file__).resolve().parent
B = Path('/workspace/prism-novelty/ceres-frozen')
old = json.loads((P / 'provenance/ceres-existing-protocol.json').read_text())
assert hashlib.sha256(B.read_bytes()).hexdigest() == old['binary_sha256']
env = {k: v for k, v in os.environ.items()
       if not k.startswith(('OCA_', 'CASPAR_', 'CERES_', 'COLMAP_MFREE', 'MF_DEBUG'))}
cmd = [sys.executable, str(P / 'provenance/novelty_external.py'), '--kind', 'ceres',
       '--binary', str(B), '--out', str(P / 'evidence/ceres-storm'),
       '--scenes', 'final-3068', 'final-4585', '--profiles', 'lm-10000', 'dogleg-10000',
       '--budgets', '600', '--reps', '3', '--timeout', '3600']
print('Starting frozen Ceres storm coverage: two scenes, two profiles, N=3.', flush=True)
subprocess.run(cmd, env=env, check=True)
