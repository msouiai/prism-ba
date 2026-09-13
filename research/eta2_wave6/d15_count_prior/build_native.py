#!/usr/bin/env python3
"""Derive the registered D15 native arm from the checksum-pinned champion."""
from __future__ import annotations
import hashlib,json,os,pathlib,subprocess

HERE=pathlib.Path(__file__).resolve().parent
ROOT=HERE.parents[2]
PKG=ROOT/'research/eta2_champion'
OUT=pathlib.Path('/tmp/prism-wave6-d15-native');OUT.mkdir(parents=True,exist_ok=True)

def sha(path):return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()

source=(PKG/'source/prism_eta2.cu').read_text()
assert hashlib.sha256(source.encode()).hexdigest()=='22c18359a526526ae0a5b5109187878ab1cef33b453f6bbddc2aa92597a607d8'
manifest=json.loads((PKG/'source_manifest.json').read_text())
assert all(sha(PKG/'source/headers'/name)==digest for name,digest in manifest['headers_sha256'].items())
s=source;patches=[]
def patch(old,new,count=1):
    global s
    assert s.count(old)==count,(old[:100],s.count(old),count)
    s=s.replace(old,new);patches.append((old,new,count))

patch('#include "pcg_camera.cuh"','#include "d15_pcg_camera.cuh"\n#include "d15_count_prior.cuh"')
patch('''  std::unique_ptr<PrismPcg> pcg;
  if(getenv("OCA_PCG"))pcg=std::make_unique<PrismPcg>(ncam);''','''  std::unique_ptr<PrismPcg> pcg;
  if(getenv("OCA_PCG"))pcg=std::make_unique<PrismPcg>(ncam);
  std::unique_ptr<D15CountPrior> d15;
  if(getenv("OCA_D15_COUNT_PRIOR"))d15=std::make_unique<D15CountPrior>(ncam,p.mf_coff,p.mf_cspt);''')
patch('''  for(int k=replay_start;k<max_iter;){
   const double numeric_prior_bnorm=prev_bnorm;''','''  for(int k=replay_start;k<max_iter;){
   if(d15){d15->Reset();if(pcg)pcg->SetPrior(nullptr);}
   const double numeric_prior_bnorm=prev_bnorm;''')
# Wrap the scaled bare operator.  Delta is in exactly these scaled coordinates.
anchor='''    auto KvS=[&](const Scalar* vin,Scalar* vout){'''
start=s.index(anchor);end=s.index('\n    };',start)+len('\n    };')
body=s[start:end]
renamed=body.replace('auto KvS=','auto D15KvSBase=',1)
patch(body,renamed+'''\n    auto KvS=[&](const Scalar* vin,Scalar* vout){D15KvSBase(vin,vout);if(d15)d15->Add(vin,vout);};''')
patch('''      pcg->Prepare(Hcc,E,shifts[0],k,retries,Gp,fragment_points,p.mf_coff,Rf,nobs);pcg->Apply(r_);''','''      if(d15)pcg->SetPrior(d15->active?d15->delta:nullptr);
      pcg->Prepare(Hcc,E,shifts[0],k,retries,Gp,fragment_points,p.mf_coff,Rf,nobs);pcg->Apply(r_);''')
patch('''      if(attr_radius){
        cublasDnrm2(blas,n_c,xs[0],1,&attr_raw_norm);''','''      if(attr_radius){
        cublasDnrm2(blas,n_c,xs[0],1,&attr_raw_norm);
        if(d15 && !d15->active && attr_R>0){
          auto q=d15->Inspect(xs[0],attr_R);
          std::printf("D15_TEST o=%d retry=%d ratio=%.17g gated_fraction=%.17g raw=%.17g radius=%.17g trigger=%d\\n",k,retries,q.ratio,q.gated_fraction,q.norm,attr_R,(int)(q.ratio>100&&q.gated_fraction>.5));
          if(q.ratio>100 && q.gated_fraction>.5){
            if(mf_fp32)d15->Build<float>(Gc32,p.mf_cspt,p.mf_coff,Rf,Hcc,E,nobs);
            else d15->Build<Fragment>(Gc?Gc:Gp,p.mf_cspt,p.mf_coff,Rf,Hcc,E,nobs,fragment_slots);
            pcg->SetPrior(d15->delta);std::fill(preds.begin(),preds.end(),(Scalar)0.0);goto sweep_restart;
          }
        }''')
patch('''  if(final_lambda_out) *final_lambda_out = lam_cam;''','''  if(d15)d15->Final();
  if(final_lambda_out) *final_lambda_out = lam_cam;''')
restored=s
for old,new,count in reversed(patches):
    assert restored.count(new)==count
    restored=restored.replace(new,old)
assert restored==source
src=OUT/'prism_d15.cu';src.write_text(s);binary=OUT/'prism-d15'
command=['nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3',f'-I{HERE}',f'-I{PKG/"source/headers"}',str(src),'-o',str(binary),'-lcublas','-lcusolver']
with (OUT/'build.log').open('w') as log:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,env={**os.environ,'TMPDIR':'/dev/shm'})
record={'command':command,'frozen_source_sha256':hashlib.sha256(source.encode()).hexdigest(),'derived_source_sha256':sha(src),'binary_sha256':sha(binary),'reversible_patch_count':len(patches),
    'protocol_sha256':sha(ROOT/'research/eta2_wave6/D15_COUNT_PRIOR_PROTOCOL.md'),'sources':{str(p):sha(p) for p in [HERE/'build_native.py',HERE/'d15_count_prior.cuh',HERE/'d15_pcg_camera.cuh']}}
(HERE/'native-build-manifest.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2))
