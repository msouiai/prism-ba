#!/usr/bin/env python3
import json,os,subprocess
from build import P,sha
b=P/'build';b.mkdir(exist_ok=True);headers={h:sha(P/h) for h in ('passenger.cuh','geometry.h','clusters.h','attempt_trace.h','toy.cu')}
cmd=['nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3','-I'+str(P),str(P/'toy.cu'),'-o',str(b/'passenger-toy')]
with (b/'toy-build.log').open('w') as out:subprocess.run(cmd,stdout=out,stderr=subprocess.STDOUT,env=dict(os.environ,TMPDIR='/dev/shm'),check=True)
assert headers=={h:sha(P/h) for h in headers}
(P/'toy_build_manifest.json').write_text(json.dumps(dict(command=cmd,local_headers=headers,binary_sha256=sha(b/'passenger-toy')),indent=2)+'\n')
