#!/usr/bin/env python3
"""Capture an input linearization, without taking an optimization step."""
import fcntl,hashlib,json,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent;C=P.parent/'eta2_curvature_audit';F=P.parent/'eta2_champion'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def patch(s,a,b):
    assert s.count(a)==1,(a[:100],s.count(a));return s.replace(a,b)
def main():
    subprocess.run(['python3',str(F/'build.py'),'--check-only'],check=True)
    source=C/'build/prism_curvature.cu'
    assert sha(source)==json.loads((C/'build/manifest.json').read_text())['source_sha256']
    s=source.read_text()
    s=patch(s,'      if(!(pAp>1e-14*pp)){',
      '      if((getenv("OCA_CURVATURE_AT_START") && k==0 && cg_it==0) || !(pAp>1e-14*pp)){')
    s=patch(s,'        if(depth_active==2 && !curvature_captured && getenv("OCA_CURVATURE_CAPTURE")){',
      '        if((depth_active==2 || getenv("OCA_CURVATURE_AT_START")) && !curvature_captured && getenv("OCA_CURVATURE_CAPTURE")){')
    anchor='          std::printf("CURVATURE_CAPTURE outer=%d cg=%d quotient=%.17g cutoff=1e-14 directory=%s\\n",k,cg_it,pAp/pp,dir.c_str());\n        }}'
    s=patch(s,anchor,anchor+'\n        if(curvature_captured)break; // Forced input capture is not a negative-curvature event.')
    b=P/'build';b.mkdir(exist_ok=True);out=b/'prism_external.cu';out.write_text(s)
    cmd=['nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3',
      '-I'+str(F/'source/headers'),str(out),'-o',str(b/'prism-external'),'-lcublas','-lcusolver']
    with open('/tmp/prism_gpu.lock','w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        with (b/'external-build.log').open('w') as log:subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True)
    (b/'external-manifest.json').write_text(json.dumps(dict(command=cmd,source_sha256=sha(out),
      binary_sha256=sha(b/'prism-external'),parent_source_sha256=sha(source),protocol_sha256=sha(P/'PROTOCOL.md')),indent=2)+'\n')
    print('BUILT external',sha(b/'prism-external'),flush=True)
if __name__=='__main__':main()
