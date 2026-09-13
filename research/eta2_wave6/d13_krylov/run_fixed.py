#!/usr/bin/env python3
"""Run registered restart-depth cells under the shared GPU lock."""
from __future__ import annotations
import fcntl,hashlib,json,os,pathlib,subprocess,time

HERE=pathlib.Path(__file__).resolve().parent
BINARY=pathlib.Path('/tmp/prism-wave6-d13-build/restart_fixed')
CAP=pathlib.Path('/workspace/prism-schur-physics')
OUT=HERE/'evidence';OUT.mkdir(exist_ok=True)
scenes={'muell-o11':CAP/'muell-gba146-o11','muell-o12':CAP/'muell-gba146-o12',
        'ladybug-o8':CAP/'ladybug-598-o8','final-o0':CAP/'final-1936-o0'}
arms=[('none',0,False),('one4',4,False),('one8',8,False),('one16',16,False),('one32',32,False),('periodic8',8,True)]
manifest={}
with open('/tmp/prism_gpu.lock','w') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX)
    for scene,path in scenes.items():
        for name,depth,periodic in arms:
            log=OUT/f'{scene}-{name}.log';env=os.environ.copy()
            if depth:env['D13_RESTART_DEPTH']=str(depth)
            if periodic:env['D13_PERIODIC']='1'
            start=time.perf_counter()
            with log.open('w') as stream:
                subprocess.run([str(BINARY),str(path)],env=env,stdout=stream,stderr=subprocess.STDOUT,check=True,timeout=600)
            manifest[f'{scene}/{name}']={'wall_seconds':time.perf_counter()-start,'log_sha256':hashlib.sha256(log.read_bytes()).hexdigest(),
              'capture_manifest_sha256':hashlib.sha256((path/'capture_manifest.json').read_bytes()).hexdigest() if (path/'capture_manifest.json').exists() else None}
(OUT/'fixed_run_manifest.json').write_text(json.dumps({'binary_sha256':hashlib.sha256(BINARY.read_bytes()).hexdigest(),'rows':manifest},indent=2)+'\n')
print(json.dumps(manifest,indent=2))
