"""Matched native W2a/W3 arms derived reversibly from frozen Eta2."""
from pathlib import Path
import hashlib, importlib.util, json, os, subprocess
P=Path(__file__).resolve().parent
C=P.parent/'eta2_research_20260912';F=P.parent/'eta2_champion'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def derive():
    spec=importlib.util.spec_from_file_location('wave1_frontload_build',C/'frontload/build.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    original,prior=m.derive();s=original;patches=[]
    def patch(a,b):
        nonlocal s
        assert s.count(a)==1,(a[:100],s.count(a));s=s.replace(a,b);patches.append((a,b))
    patch('#include "attempt_trace.h"','#include "attempt_trace.h"\n#include "wave_trace.cuh"')
    anchor='  FrontloadTotals frontload_totals;'
    patch(anchor,anchor+'''
  const int wave_interior=getenv("OCA_W2_INTERIOR")?atoi(getenv("OCA_W2_INTERIOR")):0;
  const bool wave_force=getenv("OCA_W3_FORCE")&&atoi(getenv("OCA_W3_FORCE"));
  const bool wave_unclip=getenv("OCA_W3_UNCLIP")&&atoi(getenv("OCA_W3_UNCLIP"));
  const bool wave_jump=getenv("OCA_W3_JUMP")&&atoi(getenv("OCA_W3_JUMP"));
  bool wave_jumped=false;
  std::unique_ptr<WaveTrace> wave_trace;
  if(const char* p=getenv("OCA_WAVE_TRACE"))wave_trace=std::make_unique<WaveTrace>(p);
  if(wave_interior<0||wave_interior>2)throw std::runtime_error("wave interior:0=off,1=always,2=first3 accepts");''')
    anchor='   StcgAttemptClock attempt_clock(attempt_trace.get(),k,retries,!need_assembly,&st.matvecs);'
    patch(anchor,anchor+'''
   WaveAttempt wave(wave_trace.get(),attempt_clock,k,retries,n_accept);
   if(wave_jump && !wave_jumped && k==1){lam_cam=std::min(1e16,16.*(double)lam_cam);wave_jumped=true;}
''')
    patch('    if(front)eta=.05;','    if(front || (wave_force && n_accept<3))eta=.05;')
    anchor='    if(numeric_guard && trunc && numeric_rebuilds<32'
    patch(anchor,'''    wave.row.lambda=lam_cam;wave.row.tau=tau_eff;wave.row.radius=attr_R;wave.row.eta=eta;
    if(wave_trace)wave_trace->Observe(wave.row,s,E,xs[0],ncam);
'''+anchor)
    patch('        if(!front && attr_raw_norm>attr_R)',
          '        if(!front && !(wave_unclip && n_accept<3) && attr_raw_norm>attr_R)')
    anchor='        if(have&&attr_norm<.8*attr_old_R&&lm_rho>=.25)'
    patch(anchor,'        if(!(wave_interior==1 || (wave_interior==2 && n_accept<3)) && have&&attr_norm<.8*attr_old_R&&lm_rho>=.25)')
    anchor='    if(attempt_trace)attempt_clock.row.accepted=accepted;'
    patch(anchor,anchor+'\n    wave.row.rho=lm_rho;')
    restored=s
    for a,b in reversed(patches):assert restored.count(b)==1;restored=restored.replace(b,a)
    assert restored==original
    return s,len(prior)+len(patches)

def main():
    s,count=derive();b=P/'build';b.mkdir(exist_ok=True);src=b/'prism_wave2.cu';src.write_text(s)
    cmd=['nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3',
         '-I'+str(P),'-I'+str(C/'frontload'),'-I'+str(F/'source/headers'),str(src),
         '-o',str(b/'prism-wave2'),'-lcublas','-lcusolver']
    env=os.environ.copy();env['TMPDIR']='/dev/shm'
    local={str(p):sha(p) for p in [P/'build.py',P/'wave_trace.cuh',C/'frontload/build.py',C/'frontload/frontload.cuh',C/'frontload/coherent_rows.cuh',C/'frontload/attempt_trace.h']}
    with (b/'build.log').open('w') as f:subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
    assert local=={p:sha(p) for p in local}
    record=dict(command=cmd,source_sha256=sha(src),binary_sha256=sha(b/'prism-wave2'),
        frozen_source_sha256=sha(F/'source/prism_eta2.cu'),champion_sha256=sha(F/'champion.json'),
        protocol_sha256=sha(P/'PROTOCOL.md'),local_headers_and_builders=local,
        reversible_patch_count=count,default_off=True)
    (P/'build_manifest.json').write_text(json.dumps(record,indent=2)+'\n')
    print('BUILT',record['binary_sha256'],flush=True)
if __name__=='__main__':main()
