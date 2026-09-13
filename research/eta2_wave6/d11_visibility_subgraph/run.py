#!/usr/bin/env python3
"""Run registered fixed-system GSP cells under the shared GPU lock."""
from __future__ import annotations
import fcntl, hashlib, json, pathlib, subprocess, time

HERE=pathlib.Path(__file__).resolve().parent
CAPTURE=pathlib.Path('/workspace/prism-schur-eta2')
BINARY=pathlib.Path('/tmp/prism-wave6-d11-build/gsp_fixed')
OUT=HERE/'evidence'
scenes=['muell-gba146','ladybug-598']
assert BINARY.exists()
rows={}
with open('/tmp/prism_gpu.lock','w') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX)
    for scene in scenes:
        log=OUT/f'{scene}.log'
        start=time.perf_counter()
        with log.open('w') as stream:
            subprocess.run([str(BINARY),str(CAPTURE/scene)],stdout=stream,stderr=subprocess.STDOUT,check=True,timeout=1800)
        rows[scene]={'wall_seconds':time.perf_counter()-start,'log_sha256':hashlib.sha256(log.read_bytes()).hexdigest(),
                     'capture_manifest_sha256':hashlib.sha256((CAPTURE/scene/'capture_manifest.json').read_bytes()).hexdigest()}
(OUT/'run_manifest.json').write_text(json.dumps({'binary_sha256':hashlib.sha256(BINARY.read_bytes()).hexdigest(),'scenes':rows},indent=2)+'\n')
print(json.dumps(rows,indent=2))
