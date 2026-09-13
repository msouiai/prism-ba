#!/usr/bin/env python3
"""Build D22 from the exact deterministic B6v7 source."""
from __future__ import annotations
import hashlib,importlib.util,json,os,pathlib,subprocess
HERE=pathlib.Path(__file__).resolve().parent;W6=HERE.parent;F=W6.parent/'eta2_champion';OUT=pathlib.Path('/tmp/prism-wave6-d22');OUT.mkdir(parents=True,exist_ok=True)
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
spec=importlib.util.spec_from_file_location('bd',W6/'build_deterministic.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);source,inherited=m.derive()
assert hashlib.sha256(source.encode()).hexdigest()==json.loads((W6/'deterministic-build-manifest.json').read_text())['source_sha256']
s=source;patches=[]
def patch(a,b):
 global s
 assert s.count(a)==1,(a[:140],s.count(a));s=s.replace(a,b);patches.append((a,b))
patch('#include "point_safeguard.cuh"','#include "point_safeguard.cuh"\n#include "d22_terminal_track_polish.cuh"')
patch('''  DeviceState s_new; AllocState(s_new,ncam,npt,CD==9);
  const bool batch_cost=getenv("OCA_BATCH_COST")!=nullptr;''','''  DeviceState s_new; AllocState(s_new,ncam,npt,CD==9);
  std::unique_ptr<D22TerminalTrackPolish> d22;
  if(getenv("OCA_D22_TERMINAL_TRACK_POLISH"))d22=std::make_unique<D22TerminalTrackPolish>(ncam,npt,nobs);
  const bool batch_cost=getenv("OCA_BATCH_COST")!=nullptr;''')
patch('''    if(converged){ ++k; break; }
    if(verbose)''','''    if(converged){
      if(d22){
        const double before=(double)cost;CopyState(s_new,s,ncam,npt);
        const auto q=d22->Apply(p,s,s_new);const double candidate=ComputeCost(p,s_new,rk,rk_a2);
        const bool commit=std::isfinite(candidate)&&candidate<cost;
        if(commit){CopyState(s,s_new,ncam,npt);cost=candidate;log.costs.back()=cost;CsvRow(k+1,(double)cost);}
        std::printf("D22_TERMINAL outer=%d before=%.17g candidate=%.17g decrease=%.17g eligible=%llu wins=%llu margin=%llu algebra=%llu local_decrease=%.17g commit=%d target=%d\\n",
          k+1,before,candidate,before-candidate,q.eligible,q.wins,q.margin_rejects,q.algebra_failures,q.improvement,(int)commit,(int)TargetReached(cost,k+1));
      }
      ++k; break;
    }
    if(verbose)''')
patch('''  if(final_lambda_out) *final_lambda_out = lam_cam;''','''  if(d22)d22->Final();
  if(final_lambda_out) *final_lambda_out = lam_cam;''')
restored=s
for a,b in reversed(patches):assert restored.count(b)==1;restored=restored.replace(b,a)
assert restored==source
src=OUT/'prism_d22.cu';binary=OUT/'prism-d22';src.write_text(s)
cmd=['nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3',f'-I{HERE}',f'-I{W6}',f'-I{F/"source/headers"}',f'-I{W6.parent/"eta2_wave5"}',str(src),'-o',str(binary),'-lcublas','-lcusolver']
with (OUT/'build.log').open('w') as log:subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True,env={**os.environ,'TMPDIR':'/dev/shm'})
record={'command':cmd,'parent_source_sha256':hashlib.sha256(source.encode()).hexdigest(),'derived_source_sha256':sha(src),'binary_sha256':sha(binary),'inherited_patch_count':inherited,'d22_patch_count':len(patches),'sources':{str(p):sha(p) for p in [HERE/'build.py',HERE/'d22_terminal_track_polish.cuh',W6.parent/'eta2_wave5/targeted_triangulation.cuh',W6/'build_deterministic.py']},'protocol_sha256':sha(W6/'D22_TERMINAL_TRACK_POLISH_PROTOCOL.md')}
(HERE/'build-manifest.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2))
