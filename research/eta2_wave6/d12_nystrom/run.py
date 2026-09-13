#!/usr/bin/env python3
"""Run D12 fixed systems under the shared GPU lock."""
from __future__ import annotations
import fcntl,hashlib,json,os,pathlib,subprocess,time

HERE=pathlib.Path(__file__).resolve().parent
CAPTURE=pathlib.Path('/workspace/prism-schur-eta2')
BINARY=pathlib.Path('/tmp/prism-wave6-d12-build/nystrom_fixed')
OUT=HERE/'evidence';OUT.mkdir(exist_ok=True)
rows={}
with open('/tmp/prism_gpu.lock','w') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX)
    for scene in ('muell-gba146','ladybug-598','final-1936'):
        log=OUT/f'{scene}.log';env=os.environ.copy()
        if scene!='muell-gba146':env['D12_DISPATCH_ONLY']='1'
        start=time.perf_counter()
        with log.open('w') as stream:
            subprocess.run([str(BINARY),str(CAPTURE/scene)],env=env,stdout=stream,stderr=subprocess.STDOUT,check=True,timeout=1800)
        rows[scene]={'wall_seconds':time.perf_counter()-start,'log_sha256':hashlib.sha256(log.read_bytes()).hexdigest(),
          'capture_manifest_sha256':hashlib.sha256((CAPTURE/scene/'capture_manifest.json').read_bytes()).hexdigest()}
(OUT/'run_manifest.json').write_text(json.dumps({'binary_sha256':hashlib.sha256(BINARY.read_bytes()).hexdigest(),'scenes':rows},indent=2)+'\n')
print(json.dumps(rows,indent=2))
