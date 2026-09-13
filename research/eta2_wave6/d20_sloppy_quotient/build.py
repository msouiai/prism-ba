#!/usr/bin/env python3
"""Build D20 from the exact deterministic B6v7 source."""
from __future__ import annotations
import hashlib,importlib.util,json,os,pathlib,subprocess

HERE=pathlib.Path(__file__).resolve().parent;W6=HERE.parent;F=W6.parent/'eta2_champion';OUT=pathlib.Path('/tmp/prism-wave6-d20');OUT.mkdir(parents=True,exist_ok=True)
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
spec=importlib.util.spec_from_file_location('bd',W6/'build_deterministic.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);source,inherited=m.derive()
assert hashlib.sha256(source.encode()).hexdigest()==json.loads((W6/'deterministic-build-manifest.json').read_text())['source_sha256']
s=source;patches=[]
def patch(a,b):
 global s
 assert s.count(a)==1,(a[:120],s.count(a));s=s.replace(a,b);patches.append((a,b))
patch('#include "pcg_camera.cuh"','#include "pcg_camera.cuh"\n#include "d20_sloppy_quotient.cuh"')
patch('''  std::unique_ptr<PrismPcg> pcg;
  if(getenv("OCA_PCG"))pcg=std::make_unique<PrismPcg>(ncam);''','''  std::unique_ptr<PrismPcg> pcg;
  if(getenv("OCA_PCG"))pcg=std::make_unique<PrismPcg>(ncam);
  std::unique_ptr<D20SloppyQuotient> d20;
  if(getenv("OCA_D20_SLOPPY_QUOTIENT"))d20=std::make_unique<D20SloppyQuotient>(ncam);''')
patch('''      if(attr_radius){
        PrismW6Dnrm2(blas,n_c,xs[0],1,&attr_raw_norm);
        if(!(attr_R>0))attr_R=std::isfinite(attr_raw_norm)&&attr_raw_norm>0?attr_raw_norm:1;
        attr_old_R=attr_R;
        if(attr_raw_norm>attr_R){double scale=attr_R/attr_raw_norm;cublasDscal(blas,n_c,&scale,xs[0],1);}
      }''','''      if(attr_radius){
        PrismW6Dnrm2(blas,n_c,xs[0],1,&attr_raw_norm);
        if(!(attr_R>0))attr_R=std::isfinite(attr_raw_norm)&&attr_raw_norm>0?attr_raw_norm:1;
        if(d20){
          auto q=d20->Inspect(xs[0],attr_R);bool preliminary=q.ratio>100&&q.top_fraction>.99;
          D20SloppyQuotient::Projection p20;double post=q.norm;
          if(preliminary){
            if(mf_fp32)p20=d20->BuildAndProject<float>(Gc32,p.mf_cspt,p.mf_coff,Rf,Hcc,E,nobs,xs[0],q.top);
            else p20=d20->BuildAndProject<Fragment>(Gc?Gc:Gp,p.mf_cspt,p.mf_coff,Rf,Hcc,E,nobs,xs[0],q.top,fragment_slots);
            if(p20.trigger){PrismW6Dnrm2(blas,n_c,xs[0],1,&post);attr_raw_norm=post;}
          }
          std::printf("D20_TEST o=%d retry=%d ratio=%.17g top=%d top_fraction=%.17g preliminary=%d weakest=%d trigger=%d removed_fraction=%.17g post_raw=%.17g post_ratio=%.17g\\n",k,retries,q.ratio,q.top,q.top_fraction,(int)preliminary,p20.weakest,(int)p20.trigger,p20.removed_fraction,post,post/attr_R);
        }
        attr_old_R=attr_R;
        if(attr_raw_norm>attr_R){double scale=attr_R/attr_raw_norm;cublasDscal(blas,n_c,&scale,xs[0],1);}
      }''')
patch('  if(final_lambda_out) *final_lambda_out = lam_cam;','  if(d20)d20->Final();\n  if(final_lambda_out) *final_lambda_out = lam_cam;')
restored=s
for a,b in reversed(patches):assert restored.count(b)==1;restored=restored.replace(b,a)
assert restored==source
src=OUT/'prism_d20.cu';binary=OUT/'prism-d20';src.write_text(s)
cmd=['nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3',f'-I{HERE}',f'-I{W6}',f'-I{F/"source/headers"}',f'-I{W6.parent/"eta2_wave5"}',str(src),'-o',str(binary),'-lcublas','-lcusolver']
with (OUT/'build.log').open('w') as log:subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True,env={**os.environ,'TMPDIR':'/dev/shm'})
record={'command':cmd,'parent_source_sha256':hashlib.sha256(source.encode()).hexdigest(),'derived_source_sha256':sha(src),'binary_sha256':sha(binary),'inherited_patch_count':inherited,'d20_patch_count':len(patches),'sources':{str(p):sha(p) for p in [HERE/'build.py',HERE/'d20_sloppy_quotient.cuh',W6/'build_deterministic.py']},'protocol_sha256':sha(W6/'D20_NATIVE_PROTOCOL.md')}
(HERE/'build-manifest.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2))
