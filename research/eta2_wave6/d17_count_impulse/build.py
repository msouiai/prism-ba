#!/usr/bin/env python3
"""Build D17 from the exact D0v3 deterministic source."""
from __future__ import annotations
import hashlib,importlib.util,json,os,pathlib,subprocess

HERE=pathlib.Path(__file__).resolve().parent;W6=HERE.parent;F=W6.parent/'eta2_champion';OUT=pathlib.Path('/tmp/prism-wave6-d17');OUT.mkdir(parents=True,exist_ok=True)
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
spec=importlib.util.spec_from_file_location('bd',W6/'build_deterministic.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);source,inherited=m.derive()
assert hashlib.sha256(source.encode()).hexdigest()==json.loads((W6/'deterministic-build-manifest.json').read_text())['source_sha256']
s=source;patches=[]
def patch(a,b):
 global s
 assert s.count(a)==1,(a[:120],s.count(a));s=s.replace(a,b);patches.append((a,b))
patch('#include "pcg_camera.cuh"','#include "pcg_camera.cuh"\n#include "d17_count_impulse.cuh"')
patch('''  std::unique_ptr<PrismPcg> pcg;
  if(getenv("OCA_PCG"))pcg=std::make_unique<PrismPcg>(ncam);''','''  std::unique_ptr<PrismPcg> pcg;
  if(getenv("OCA_PCG"))pcg=std::make_unique<PrismPcg>(ncam);
  std::unique_ptr<D17CountImpulse> d17;
  if(getenv("OCA_D17_COUNT_IMPULSE"))d17=std::make_unique<D17CountImpulse>(ncam,p.mf_coff,p.mf_cspt);''')
patch('''      if(attr_radius){
        PrismW6Dnrm2(blas,n_c,xs[0],1,&attr_raw_norm);
        if(!(attr_R>0))attr_R=std::isfinite(attr_raw_norm)&&attr_raw_norm>0?attr_raw_norm:1;
        attr_old_R=attr_R;
        if(attr_raw_norm>attr_R){double scale=attr_R/attr_raw_norm;cublasDscal(blas,n_c,&scale,xs[0],1);}
      }''','''      if(attr_radius){
        PrismW6Dnrm2(blas,n_c,xs[0],1,&attr_raw_norm);
        if(!(attr_R>0))attr_R=std::isfinite(attr_raw_norm)&&attr_raw_norm>0?attr_raw_norm:1;
        if(d17&&!d17->spent){
          auto q=d17->Inspect(xs[0],attr_R);const bool trigger=q.ratio>100&&q.gated_fraction>.5;double post=q.norm;
          if(trigger){d17->Project(xs[0]);PrismW6Dnrm2(blas,n_c,xs[0],1,&post);attr_raw_norm=post;}
          std::printf("D17_TEST o=%d retry=%d ratio=%.17g gated_fraction=%.17g raw=%.17g radius=%.17g trigger=%d post_raw=%.17g post_ratio=%.17g\\n",k,retries,q.ratio,q.gated_fraction,q.norm,attr_R,(int)trigger,post,post/attr_R);
        }
        attr_old_R=attr_R;
        if(attr_raw_norm>attr_R){double scale=attr_R/attr_raw_norm;cublasDscal(blas,n_c,&scale,xs[0],1);}
      }''')
patch('  if(final_lambda_out) *final_lambda_out = lam_cam;','  if(d17)d17->Final();\n  if(final_lambda_out) *final_lambda_out = lam_cam;')
restored=s
for a,b in reversed(patches):assert restored.count(b)==1;restored=restored.replace(b,a)
assert restored==source
src=OUT/'prism_d17.cu';binary=OUT/'prism-d17';src.write_text(s)
cmd=['nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3',f'-I{HERE}',f'-I{W6}',f'-I{F/"source/headers"}',f'-I{W6.parent/"eta2_wave5"}',str(src),'-o',str(binary),'-lcublas','-lcusolver']
with (OUT/'build.log').open('w') as log:subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True,env={**os.environ,'TMPDIR':'/dev/shm'})
record={'command':cmd,'parent_source_sha256':hashlib.sha256(source.encode()).hexdigest(),'derived_source_sha256':sha(src),'binary_sha256':sha(binary),'inherited_patch_count':inherited,'d17_patch_count':len(patches),'sources':{str(p):sha(p) for p in [HERE/'build.py',HERE/'d17_count_impulse.cuh',W6/'build_deterministic.py']},'protocol_sha256':sha(W6/'D17_COUNT_IMPULSE_PROTOCOL.md')}
(HERE/'build-manifest.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2))
