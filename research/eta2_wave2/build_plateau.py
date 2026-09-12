from pathlib import Path
import hashlib,json,os,subprocess
P=Path(__file__).resolve().parent;C=P.parent/'eta2_research_20260912';F=P.parent/'eta2_champion'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
subprocess.run(['python3',str(F/'build.py'),'--check-only'],check=True)
bm=json.loads((P/'geodesic_native_manifest.json').read_text());source=P/'build/prism_geodesic_native.cu';assert sha(source)==bm['source_sha256'];s=source.read_text()
def patch(a,b):
 global s
 assert s.count(a)==1,(a[:100],s.count(a));s=s.replace(a,b)
patch('#include "geodesic_native.cuh"','#include "geodesic_native.cuh"\n#include "root_policy.h"')
anchor='  std::unique_ptr<GeoNative> geo;'
patch(anchor,anchor+'''
  const bool plateau_on=getenv("OCA_PLATEAU")&&atoi(getenv("OCA_PLATEAU"));
  bool plateau_used=false;int plateau_phase=0,plateau_left=0;double plateau_cost=0;
  WaveRootPolicy plateau_root;
''')
patch('      if(geo){','''      if(plateau_phase==2 && !geo)geo=std::make_unique<GeoNative>(ncam,npt,nobs);
      if(geo && (!plateau_on || plateau_phase==2)){''')
anchor='        if(!front && !(wave_unclip && n_accept<3) && attr_raw_norm>attr_R)'
patch(anchor,'''        if(plateau_phase==1){
          plateau_root.Start(k,lam_cam);double next=plateau_root.Next(lam_cam,attr_raw_norm,attr_R);
          if(next>0){
            next=std::max(next,numeric_floor);
            std::printf("W8_ROOT attempt=%zu outer=%d lambda=%.17g next=%.17g raw=%.17g radius=%.17g\\n",wave_trace?wave_trace->rows.size():0,k,(double)lam_cam,next,attr_raw_norm,attr_R);
            lam_cam=next;prev_bnorm=numeric_prior_bnorm;need_assembly=false;factor_cached=false;continue;
          }
        }
'''+anchor)
anchor='    if(converged){ ++k; break; }'
patch(anchor,'''    if(plateau_on){
      if(plateau_phase){
        const double gain=(plateau_cost-cost)/std::max(plateau_cost,1e-300);
        std::printf("W8_PROGRESS outer=%d phase=%d cost=%.17g gain=%.17g\\n",k,plateau_phase,(double)cost,gain);
        if(gain>1e-4){plateau_phase=0;converged=false;ftol_streak=0;stuck=0;std::printf("W8_RESUME outer=%d gain=%.17g\\n",k,gain);}
        else if(plateau_phase==1){plateau_phase=2;plateau_left=2;converged=false;ftol_streak=0;stuck=0;}
        else if(--plateau_left>0){converged=false;ftol_streak=0;stuck=0;}
        else{plateau_phase=0;converged=true;std::printf("W8_EXHAUSTED outer=%d gain=%.17g\\n",k,gain);}
      }else if(converged&&!plateau_used&&target_cost>0&&cost>target_cost){
        plateau_used=true;plateau_phase=1;plateau_cost=cost;converged=false;ftol_streak=0;stuck=0;
        std::printf("W8_BOUNDARY outer=%d cost=%.17g seconds=%.17g lambda=%.17g radius=%.17g ratio=%.17g\\n",k,(double)cost,std::chrono::duration<double>(now()-budget_start).count(),(double)lam_cam,attr_R,attr_old_R>0?attr_raw_norm/attr_old_R:0);
      }
    }
'''+anchor)
b=P/'build';src=b/'prism_plateau.cu';src.write_text(s)
cmd=['nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3','-I'+str(P),'-I'+str(C/'frontload'),'-I'+str(F/'source/headers'),str(src),'-o',str(b/'prism-plateau'),'-lcublas','-lcusolver']
env=os.environ.copy();env['TMPDIR']='/dev/shm'
with (b/'plateau-build.log').open('w') as f:subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
record=dict(command=cmd,source_sha256=sha(src),binary_sha256=sha(b/'prism-plateau'),protocol_sha256=sha(P/'PLATEAU_PROTOCOL.md'),parent=bm,
 sources={str(p):sha(p) for p in [P/'build_plateau.py',P/'root_policy.h',P/'geodesic_native.cuh',P/'geodesic_analytic.cuh']})
(P/'plateau_manifest.json').write_text(json.dumps(record,indent=2)+'\n');print('BUILT PLATEAU',flush=True)
