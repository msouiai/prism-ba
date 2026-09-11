#!/usr/bin/env python3
"""Hash the installed shared libraries behind the frozen Ceres executable."""
import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess

P = Path(__file__).resolve().parent
binary = '/workspace/prism-novelty/ceres-frozen'
raw = subprocess.run(['ldd', binary], capture_output=True, text=True, check=True).stdout
paths = sorted(set(re.findall(r'(?:=> )?(/[^\s]+)', raw)))
records=[]
for name in paths:
    path=Path(name)
    if not path.is_file():
        continue
    with path.open('rb') as f:
        sha=hashlib.file_digest(f, 'sha256').hexdigest()
    records.append(dict(path=name, resolved=str(path.resolve()), bytes=path.stat().st_size, sha256=sha))
(P / 'ceres-shared-libraries.json').write_text(json.dumps(dict(
    recorded_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    binary=binary, ldd=raw, libraries=records), indent=2)+'\n')
print('Recorded',len(records),'Ceres shared-library hashes.')
