#!/usr/bin/env python3
"""Publish only completed evidence at a measurement boundary."""
import fcntl
from pathlib import Path
import re
import subprocess
import sys

P = Path(__file__).resolve().parent
repo = P.parents[1]
branch = 'research/eta2-external-coverage'
with open('/tmp/prism_gpu.lock', 'w') as lock:
    print('Waiting for a measurement boundary to preserve the completed Venice evidence.', flush=True)
    fcntl.flock(lock, fcntl.LOCK_EX)
    assert subprocess.check_output(['git','branch','--show-current'],cwd=repo,text=True).strip()==branch
    subprocess.run(['git','diff','--cached','--quiet'],cwd=repo,check=True)
    for script in ['summarize.py','report.py']:
        subprocess.run([sys.executable,str(P/script)],cwd=repo,check=True)
    paths=[f for f in P.iterdir() if f.is_file() and f.suffix in ['.py','.md','.json','.csv']]
    paths += [P/'evidence/venice',P/'figures']
    paths = [str(f.relative_to(repo)) for f in paths if f.exists()]
    subprocess.run(['git','add','--',*paths],cwd=repo,check=True)
    # Explicitly preserve complete baseline records referred to by the partial
    # report, without including a currently open solver output.
    for f in sorted((P/'evidence/ceres-storm').glob('*.json')):
        companions=[f]
        if f.name!='preregistered.json':
            companions += [f.with_suffix('.log'),f.with_suffix('.stderr')]
        subprocess.run(['git','add','--',*[str(q.relative_to(repo)) for q in companions if q.exists()]],cwd=repo,check=True)
    subprocess.run(['git','diff','--cached','--check'],cwd=repo,check=True)
    subprocess.run(['git','-c','user.name=Codex','-c','user.email=codex@localhost','commit','-m',
                    'Record completed Venice stopping test and preserve audited raw evidence'],cwd=repo,check=True)
    result=subprocess.run(['git','push','-u','origin',branch],cwd=repo,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    output=re.sub(r'https://[^\s/@]+@','https://[redacted]@',result.stdout)
    output=re.sub(r'(?:github_pat_|ghp_)[A-Za-z0-9_]+','[redacted]',output)
    print(output,flush=True)
    raise SystemExit(result.returncode)
