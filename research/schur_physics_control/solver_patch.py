"""Opt-in coarse inverse and optional read-only control diagnostics."""
from audit_patch import patch_gradient
def patch(s,headers):
    hpath=headers/'pcg_camera.cuh';h=hpath.read_text()
    h=h.replace('#pragma once','#pragma once\n#include "coarse.cuh"')
    h=h.replace('struct PrismPcg{','struct PrismPcg{\n PrismCoarse* coarse=nullptr;')
    old=' void Apply(const double*r){MFBlockSolve<9><<<(nc+255)/256,256>>>(B,r,nc,0,tmp);MFBlockSolve<9><<<(nc+255)/256,256>>>(B,tmp,nc,1,z);}'
    new=''' void Base(const double*r,double*out){MFBlockSolve<9><<<(nc+255)/256,256>>>(B,r,nc,0,tmp);MFBlockSolve<9><<<(nc+255)/256,256>>>(B,tmp,nc,1,out);}
 void Apply(const double*r){if(coarse)coarse->Apply(r,z,[&](const double*a,double*b){Base(a,b);});else Base(r,z);}'''
    assert old in h;h=h.replace(old,new);hpath.write_text(h)
    needle='  if(getenv("OCA_PCG"))pcg=std::make_unique<PrismPcg>(ncam);'
    assert s.count(needle)==1
    s=s.replace(needle,needle+'''
  std::unique_ptr<PrismCoarse> coarse;
  const int coarse_rank=getenv("OCA_COARSE_RANK")?atoi(getenv("OCA_COARSE_RANK")):0;
  if(coarse_rank){
    if(!pcg||CD!=9||shared_intr||pcg->reuse||pcg->schur)throw std::runtime_error("coarse requires fresh unshared 9DOF Hcc PCG");
    coarse=std::make_unique<PrismCoarse>(n_c,coarse_rank);pcg->coarse=coarse.get();
  }
''')
    needle='  const char* replay_save=rld.enabled?'
    assert s.count(needle)==1
    s=s.replace(needle,'''  if(coarse){
    if(!classical_lm || !rld.enabled || rld.fixed_eta!=2 || rld.actor || rld.collect || rld.controller ||
       rld.policy || rld.episode || compact_mode!=2 || getenv("OCA_RLD_ACTION") ||
       getenv("OCA_RLD_OPENING") || getenv("OCA_RLD_SAVE") || getenv("OCA_RLD_LOAD") ||
       getenv("OCA_REPLAY_SAVE") || getenv("OCA_REPLAY_LOAD"))
      throw std::runtime_error("coarse experiment requires frozen eta2 layout with no policy/replay");
  }
'''+needle)
    needle='pcg->Prepare(Hcc,E,shifts[0],k,retries,Gp,fragment_points,p.mf_coff,Rf,nobs);pcg->Apply(r_);'
    assert s.count(needle)==1
    s=s.replace(needle,'''pcg->Prepare(Hcc,E,shifts[0],k,retries,Gp,fragment_points,p.mf_coff,Rf,nobs);
      if(coarse){
        coarse->Prepare(blas,[&](const double*a,double*b){KvS(a,b);cublasDaxpy(blas,n_c,&shifts[0],a,1,b,1);});
        std::printf("COARSE_PREP outer=%d retry=%d rank=%d used=%d active=%d prior_depth=%d rejected=%d\\n",k,retries,coarse_rank,coarse->used,(int)coarse->active,coarse->previous_depth,coarse->rejects);
        coarse->StartCollection();
      }
      pcg->Apply(r_);''')
    needle='      if(capture_narrow) captured->Append(pv_,Ap_);'
    assert s.count(needle)==1
    s=s.replace(needle,needle+'\n      if(coarse)coarse->Observe(blas,pv_,Ap_,pp);')
    needle='    if(trunc && negcurv_reseed && sweep_attempt==0 && L>1){'
    assert s.count(needle)==1
    s=s.replace(needle,'    if(coarse)coarse->FinishCollection(cg_broke?cg_it+1:cg_it);\n'+needle)
    return patch_gradient(s)
