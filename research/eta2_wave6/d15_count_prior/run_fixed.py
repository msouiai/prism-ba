#!/usr/bin/env python3
"""Run the preregistered D15 witness solve under the shared GPU lock."""
from __future__ import annotations
import fcntl, hashlib, json, pathlib, subprocess, time

HERE=pathlib.Path(__file__).resolve().parent
CAPTURE=pathlib.Path('/workspace/prism-wave6-d15')
BINARY=pathlib.Path('/tmp/prism-wave6-d15-build/count_prior_fixed')

def sha(path):
    with pathlib.Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

rows={}
with open('/tmp/prism_gpu.lock','w') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX)
    for rep in (0,5,6):
        source=CAPTURE/f'final-3068-{rep}';out=source/'prior-solutions';out.mkdir(exist_ok=True)
        log=out/'fixed.log';start=time.perf_counter()
        with log.open('w') as stream:
            subprocess.run([str(BINARY),str(source),str(out)],stdout=stream,stderr=subprocess.STDOUT,check=True,timeout=600)
        rows[str(rep)]={'wall_seconds':time.perf_counter()-start,'log_sha256':sha(log),
            'capture_manifest_sha256':sha(source/'capture_manifest.json'),
            'solutions':{p.name:{'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(out.glob('solution-*.f64'))}}
        print('D15_FIXED',rep,'seconds',rows[str(rep)]['wall_seconds'],'solutions',len(rows[str(rep)]['solutions']),flush=True)
manifest={'binary_sha256':sha(BINARY),'build_manifest_sha256':sha(HERE/'build-manifest.json'),
          'capture_manifest_sha256':sha(HERE/'capture-manifest.json'),'runs':rows}
(HERE/'fixed-run-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(rows,indent=2))
