#!/usr/bin/env python3
"""Preserve completed measurements only, at a native measurement boundary."""
import fcntl
from pathlib import Path
import re
import subprocess
import sys

P=Path(__file__).resolve().parent
repo=P.parents[1]
branch='research/eta2-external-coverage'
with open('/tmp/prism_gpu.lock','w') as lock:
    print('Waiting for a measurement boundary to publish the expanded ledger.',flush=True)
    fcntl.flock(lock,fcntl.LOCK_EX)
    assert subprocess.check_output(['git','branch','--show-current'],cwd=repo,text=True).strip()==branch
    staged=subprocess.check_output(['git','diff','--cached','--name-only'],cwd=repo,text=True).splitlines()
    assert all(f.startswith('research/eta2_external_coverage/') for f in staged), 'Unrelated staged changes; do not include them.'
    for script in ['summarize.py','same_target_ledger.py','report.py','ceres_setup/report.py']:
        subprocess.run([sys.executable,str(P/script)],cwd=repo,check=True)
    paths=[f for f in P.iterdir() if f.is_file() and f.suffix in ['.py','.md','.json','.csv']]
    paths += [P/'banked',P/'.gitattributes']
    paths += [f for f in (P/'ceres_setup').iterdir() if f.is_file() and f.suffix in ['.py','.md','.json','.cc','.txt']]
    for result in (P/'ceres_setup/evidence').glob('*/result.json'):
        paths += [f for f in result.parent.iterdir() if f.suffix in ['.json','.csv','.log']]
    for stage in ['venice','storm','venice-probes']:
        for result in (P/'evidence'/stage).glob('*/result.json'):
            paths += [f for f in result.parent.iterdir() if f.suffix in ['.json','.csv','.log']]
    for f in (P/'evidence/ceres-storm').glob('*.json'):
        paths.append(f)
        if f.name!='preregistered.json':paths += [f.with_suffix('.log'),f.with_suffix('.stderr')]
    subprocess.run(['git','add','--',*[str(f.relative_to(repo)) for f in paths if f.exists()]],cwd=repo,check=True)
    subprocess.run(['git','diff','--cached','--check'],cwd=repo,check=True)
    dirty=subprocess.run(['git','diff','--cached','--quiet'],cwd=repo).returncode
    if dirty:
        subprocess.run(['git','-c','user.name=Codex','-c','user.email=codex@localhost','commit','-m',
          'Record identical-target Caspar32 and MFREE outcomes with timing provenance'],cwd=repo,check=True)
    result=subprocess.run(['git','push','-u','origin',branch],cwd=repo,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    output=re.sub(r'https://[^\s/@]+@','https://[redacted]@',result.stdout)
    output=re.sub(r'(?:github_pat_|ghp_)[A-Za-z0-9_]+','[redacted]',output)
    print(output,flush=True)
    raise SystemExit(result.returncode)
