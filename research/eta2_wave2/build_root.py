from pathlib import Path
import hashlib,importlib.util,json,os,subprocess
P=Path(__file__).resolve().parent;C=P.parent/'eta2_research_20260912';F=P.parent/'eta2_champion'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
spec=importlib.util.spec_from_file_location('wave2_opening_build',P/'build.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
s,count=m.derive();patches=[]
def patch(a,b):
 global s
 assert s.count(a)==1,(a[:100],s.count(a));s=s.replace(a,b);patches.append((a,b))
patch('#include "wave_trace.cuh"','#include "wave_trace.cuh"\n#include "root_policy.h"')
anchor='  bool wave_jumped=false;'
patch(anchor,anchor+'''
  const int wave_root_mode=getenv("OCA_W2_ROOT")?atoi(getenv("OCA_W2_ROOT")):0;
  if(wave_root_mode<0||wave_root_mode>3)throw std::runtime_error("W2 root mode0=off,1=coupled,2=frozen,3=opening coupled");
  WaveRootPolicy wave_root;
''')
anchor='   WaveAttempt wave(wave_trace.get(),attempt_clock,k,retries,n_accept);'
patch(anchor,anchor+'''
   const bool root_active=wave_root_mode==1||wave_root_mode==2||(wave_root_mode==3&&n_accept<3);
   wave_root.Start(k,lam_cam);
''')
anchor='    if(classical_lm&&!attr_split)tau_eff=lam_cam;'
patch(anchor,anchor+'\n    if(root_active&&wave_root_mode==2)tau_eff=wave_root.tau;')
anchor='        if(!front && !(wave_unclip && n_accept<3) && attr_raw_norm>attr_R)'
patch(anchor,'''        if(root_active){
          const double next=wave_root.Next(lam_cam,attr_raw_norm,attr_R);
          if(next>0){
            std::printf("W2_RESOLVE attempt=%zu outer=%d update=%d lambda=%.17g next_lambda=%.17g tau=%.17g raw=%.17g radius=%.17g\\n",wave_trace?wave_trace->rows.size():0,k,wave_root.updates,(double)lam_cam,next,(double)tau_eff,attr_raw_norm,attr_R);
            lam_cam=next;prev_bnorm=numeric_prior_bnorm;need_assembly=false;
            if(wave_root_mode!=2)factor_cached=false;
            continue;
          }
          if(wave_root.active && (attr_raw_norm>attr_R||attr_raw_norm<.5*attr_R))
            std::printf("W2_FALLBACK attempt=%zu outer=%d updates=%d raw=%.17g radius=%.17g\\n",wave_trace?wave_trace->rows.size():0,k,wave_root.updates,attr_raw_norm,attr_R);
        }
'''+anchor)
b=P/'build';src=b/'prism_wave_root.cu';src.write_text(s)
cmd=['nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3','-I'+str(P),'-I'+str(C/'frontload'),'-I'+str(F/'source/headers'),str(src),'-o',str(b/'prism-wave-root'),'-lcublas','-lcusolver']
env=os.environ.copy();env['TMPDIR']='/dev/shm'
with (b/'root-build.log').open('w') as f:subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
ans=dict(command=cmd,source_sha256=sha(src),binary_sha256=sha(b/'prism-wave-root'),
 protocol_sha256=sha(P/'ROOT_NATIVE_PROTOCOL.md'),parent_source=(P/'build_manifest.json').read_text(),
 sources={str(p):sha(p) for p in [P/'build_root.py',P/'root_policy.h',P/'wave_trace.cuh',P/'build.py']})
(P/'root_build_manifest.json').write_text(json.dumps(ans,indent=2)+'\n');print('BUILT ROOT',ans['binary_sha256'],flush=True)
