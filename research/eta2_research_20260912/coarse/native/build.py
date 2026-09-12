#!/usr/bin/env python3
"""Derive optional registered coarse PCG from the frozen source, never edit it."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

P=Path(__file__).resolve().parent
CAMPAIGN=P.parents[1]
F=P.parents[2]/'eta2_champion'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def derive():
    subprocess.run(['python3',str(F/'build.py'),'--check-only'],check=True)
    original=(F/'source/prism_eta2.cu').read_text();source=original;patches=[]
    def patch(old,new):
        nonlocal source
        assert source.count(old)==1,(old[:100],source.count(old))
        source=source.replace(old,new);patches.append((old,new))
    anchor='template <int CD>\nRunLog SolveMFreeShiftedCG('
    patch(anchor,'#include "coarse.cuh"\n\n'+anchor)
    anchor='  if(getenv("OCA_PCG"))pcg=std::make_unique<PrismPcg>(ncam);'
    patch(anchor,anchor+'''
  std::unique_ptr<prism_coarse::Native> coarse;
  const bool coarse_on=getenv("OCA_COARSE") && atoi(getenv("OCA_COARSE"))!=0;
  if(coarse_on){
    if(!pcg || CD!=9 || shared_intr || mf_fp32 || rk || !classical_lm || !attr_radius || !attr_strict ||
       getenv("OCA_PCG_REUSE") || getenv("OCA_PCG_SCHUR") || getenv("OCA_POLY_CONG"))
      throw std::runtime_error("coarse requires the frozen unshared single-shift classical Eta2 operator");
    coarse=std::make_unique<prism_coarse::Native>(ncam,npt,nobs);
    printf("COARSE_CONFIG K=8 accepts_at_least=8 last_rel_below=1e-3 lambda_below=1e-3 sticky=1 membership=activation operator=native_compact rank_cut=1e-10 fallback=whole_attempt_BJ\\n");
  }
  auto ApplyCoarsePcg=[&](const double* r){pcg->Apply(r);if(coarse)coarse->Apply(r,pcg->z);};''')
    anchor='  for(int k=replay_start;k<max_iter;){'
    patch(anchor,'''  PrismCoarseAttemptLedger coarse_trace(getenv("OCA_ATTEMPT_TRACE") && atoi(getenv("OCA_ATTEMPT_TRACE"))!=0);
'''+anchor)
    anchor='   if(BudgetExpired()){std::printf("BUDGET stop=before_attempt outer=%d seconds=%.9g\\n",k,max_seconds);break;}'
    patch(anchor,anchor+'''
   PrismCoarseAttemptLedger::Attempt coarse_attempt(coarse_trace,k,retries,n_accept,n_reject,st.matvecs,numeric_rebuilds);''')
    anchor='pcg->Prepare(Hcc,E,shifts[0],k,retries,Gp,fragment_points,p.mf_coff,Rf,nobs);pcg->Apply(r_);cublasDdot(blas,n_c,r_,1,pcg->z,1,&pcg->rz);CUDA_CHECK(cudaMemcpy(pv_,pcg->z,n_c*8ul,cudaMemcpyDeviceToDevice));'
    patch(anchor,'''pcg->Prepare(Hcc,E,shifts[0],k,retries,Gp,fragment_points,p.mf_coff,Rf,nobs);
      if(coarse){if(block_on || shared_intr || poly_on || L!=1)throw std::runtime_error("coarse incompatible active operator");
        coarse->Prepare(p,s,E,Hcc,Gp,fragment_o2slot,Rf,shifts[0],k,retries,n_accept,last_rel,blas,KvS);}
      ApplyCoarsePcg(r_);cublasDdot(blas,n_c,r_,1,pcg->z,1,&pcg->rz);CUDA_CHECK(cudaMemcpy(pv_,pcg->z,n_c*8ul,cudaMemcpyDeviceToDevice));''')
    anchor='      KvS(pv_,Ap_);'
    patch(anchor,'      ++coarse_attempt.pcg;\n'+anchor)
    anchor='if(pcg){pcg->Apply(r_);double next;cublasDdot(blas,n_c,r_,1,pcg->z,1,&next);be=next/pcg->rz;pcg->rz=next;pcg->last_depth=cg_it+1;}'
    patch(anchor,anchor.replace('pcg->Apply(r_)','ApplyCoarsePcg(r_)'))
    restored=source
    for old,new in reversed(patches):
        assert restored.count(new)==1
        restored=restored.replace(new,old)
    assert restored==original,'Inverse patch did not recover frozen source'
    return source,patches

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check-only',action='store_true');a=p.parse_args()
    source,patches=derive();b=P/'build';b.mkdir(exist_ok=True);path=b/'prism_coarse.cu';path.write_text(source)
    headers=['coarse.cuh','geometry.h','attempt_trace.h']
    manifest=dict(frozen_source_sha256=sha(F/'source/prism_eta2.cu'),derived_source_sha256=sha(path),
                  inverse_patch_source_parity=True,substitutions=len(patches),
                  local_headers={h:sha(P/h) for h in headers},protocol_sha256=sha(CAMPAIGN/'PROTOCOL_01_NATIVE.md'))
    if not a.check_only:
        cmd=['nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3','-I'+str(P),
             '-I'+str(F/'source/headers'),str(path),'-o',str(b/'prism-coarse'),'-lcublas','-lcusolver']
        with (b/'build.log').open('w') as out:subprocess.run(cmd,stdout=out,stderr=subprocess.STDOUT,check=True)
        assert manifest['local_headers']=={h:sha(P/h) for h in headers},'headers changed during build'
        manifest.update(command=cmd,binary_sha256=sha(b/'prism-coarse'))
    (P/'build_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest,indent=2))

if __name__=='__main__':main()
