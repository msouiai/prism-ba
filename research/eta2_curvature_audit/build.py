#!/usr/bin/env python3
"""Add observational capture to the frozen, already-tested depth prototype."""
import fcntl,hashlib,json,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent;D=P.parent/'eta2_depth_rescue';F=P.parent/'eta2_champion'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def replace(s,a,b):
    assert s.count(a)==1,(a[:80],s.count(a));return s.replace(a,b)
def main():
    subprocess.run(['python3',str(F/'build.py'),'--check-only'],check=True)
    manifest=json.loads((D/'provenance/build_manifest.json').read_text())
    parent=D/'build/prism_depth.cu';assert sha(parent)==manifest['source_sha256']
    s=parent.read_text()
    anchor='template <int CD>\nRunLog SolveMFreeShiftedCG('
    s=replace(s,anchor,(P/'capture_kernel.cuh').read_text()+'\n'+anchor)
    s=replace(s,'  int depth_pending=0,depth_active=0;','  bool curvature_captured=false;\n  int depth_pending=0,depth_active=0;')
    anchor='      if(!(pAp>1e-14*pp)){'
    s=replace(s,anchor,anchor+'\n'+(P/'capture.inc').read_text())
    anchor='    if(trunc && negcurv_reseed && sweep_attempt==0 && L>1){'
    s=replace(s,anchor,'    if(curvature_captured){std::printf("CURVATURE_AUDIT diagnostic_complete\\n");break;}\n'+anchor)
    p=P/'build';p.mkdir(exist_ok=True);source=p/'prism_curvature.cu';source.write_text(s)
    cmd=['nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3',
         '-I'+str(F/'source/headers'),str(source),'-o',str(p/'prism-curvature'),'-lcublas','-lcusolver']
    with open('/tmp/prism_gpu.lock','w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        with (p/'build.log').open('w') as log:subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True)
    (p/'manifest.json').write_text(json.dumps(dict(command=cmd,source_sha256=sha(source),
        binary_sha256=sha(p/'prism-curvature'),parent_source_sha256=sha(parent),protocol_sha256=sha(P/'PROTOCOL.md')),indent=2)+'\n')
    print('BUILT',sha(p/'prism-curvature'),flush=True)
if __name__=='__main__':main()
