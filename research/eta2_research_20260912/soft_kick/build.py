#!/usr/bin/env python3
"""Exact-source overlay for the registered single terminal soft kick."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
P=Path(__file__).resolve().parent
CAMPAIGN=P.parent
F=CAMPAIGN.parent/'eta2_champion'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def derive():
 subprocess.run(['python3',str(F/'build.py'),'--check-only'],check=True)
 original=(F/'source/prism_eta2.cu').read_text();source=original;patches=[]
 def patch(old,new):
  nonlocal source
  assert source.count(old)==1,(old[:140],source.count(old))
  source=source.replace(old,new);patches.append((old,new))
 anchor='template <int CD>\nRunLog SolveMFreeShiftedCG('
 patch(anchor,'#include "soft_kick.cuh"\n\n'+anchor)
 anchor='  if(getenv("OCA_PCG"))pcg=std::make_unique<PrismPcg>(ncam);'
 patch(anchor,anchor+'''
  std::unique_ptr<prism_soft::Native> soft;
  if(getenv("OCA_SOFT_KICK") && atoi(getenv("OCA_SOFT_KICK"))!=0){
    if(CD!=9 || !pcg || shared_intr || mf_fp32 || rk || !classical_lm || !attr_radius || !attr_strict ||
       getenv("OCA_PCG_REUSE") || getenv("OCA_PCG_SCHUR") || getenv("OCA_POLY_CONG"))
      throw std::runtime_error("soft kick requires frozen unshared FP64 single-shift Eta2");
    soft=std::make_unique<prism_soft::Native>(ncam,npt,nobs);
    printf("SOFT_KICK_CONFIG K=8 once=1 trigger=surviving_FTOL energy=0.1 finite_bound=2 current_history=1 return_best=1\\n");
  }
  bool soft_pending=false,soft_used=false;double soft_last_gain=0,soft_budget=0;
  std::unique_ptr<StcgAttemptTrace> attempt_trace;
  if(const char* path=getenv("OCA_STCG_ATTEMPTS"))attempt_trace=std::make_unique<StcgAttemptTrace>(path);''')
 anchor='   if(BudgetExpired()){std::printf("BUDGET stop=before_attempt outer=%d seconds=%.9g\\n",k,max_seconds);break;}'
 patch(anchor,anchor+'''
   StcgAttemptClock attempt_clock(attempt_trace.get(),k,retries,!need_assembly,&st.matvecs);
   bool soft_ftol_reason=false;
   const auto soft_attempt_start=std::chrono::steady_clock::now();
   const size_t soft_trace_index=attempt_trace?attempt_trace->rows.size():0;''')
 anchor='    int sweep_attempt=0; Scalar nc_pAp=0, nc_pp=0;'
 patch(anchor,'''    if(soft_pending){
      if(!need_assembly || retries || L!=1 || block_on || poly_on || shared_intr || shifts[0]!=lam_cam)
        throw std::runtime_error("soft kick requires fresh unshifted single-camera assembly");
      soft_pending=false;
      const double hold_lambda=lam_cam,hold_radius=attr_R,hold_floor=numeric_floor,
                   hold_bnorm=prev_bnorm,hold_rel=last_rel;
      const bool hold_confirm=backtrack_confirm;
      const long scores_before=soft->scores,models_before=soft->models;
      pcg->Prepare(Hcc,E,shifts[0],k,retries,Gp,fragment_points,p.mf_coff,Rf,nobs);
      const bool applied=soft->Try(p,s,s_new,E,Hcc,Gp,fragment_o2slot,Rf,pcg->B,shifts[0],attr_R,
        soft_budget,k,blas,KvS,*full_model,k2mask,w,uu,cost);
      st.cand_evals+=soft->scores-scores_before;full_model_calls+=soft->models-models_before;
      if(lam_cam!=hold_lambda || attr_R!=hold_radius || numeric_floor!=hold_floor ||
         prev_bnorm!=hold_bnorm || last_rel!=hold_rel || backtrack_confirm!=hold_confirm)
        throw std::runtime_error("soft kick changed current controller history");
      printf("SOFT_KICK_ATTEMPT trace_index=%zu o=%d admitted=%d ordinary_LM=0 fresh_assembly=1 history_preserved=1 retry_entry=%d seconds=%.9g\\n",
        soft_trace_index,k,(int)applied,(int)attempt_clock.row.retry_entry,
        std::chrono::duration<double>(std::chrono::steady_clock::now()-soft_attempt_start).count());
      if(!applied){converged=true;break;}
      converged=false;ftol_streak=0;stuck=0;prev_cost=cost;
      need_assembly=true;factor_cached=false;pf_obs_dirty=true;retries=0;
      CsvRow(k,cost);
      if(TargetReached(cost,k))break;
      continue;
    }
'''+anchor)
 anchor='    for(cg_it=0; cg_it<maxck; ++cg_it){\n      KvS(pv_,Ap_);'
 patch(anchor,'    for(cg_it=0; cg_it<maxck; ++cg_it){\n      if(attempt_trace)++attempt_clock.row.pcg_iterations;\n      KvS(pv_,Ap_);')
 anchor='      if(!(pAp>1e-14*pp)){\n        if(model_capture'
 patch(anchor,'      if(!(pAp>1e-14*pp)){\n        if(attempt_trace)attempt_clock.row.cutoff=true;\n        if(model_capture')
 anchor='        lam_cam=numeric_floor;prev_bnorm=numeric_prior_bnorm;need_assembly=false;factor_cached=false;'
 patch(anchor,anchor+'\n        if(attempt_trace)attempt_clock.row.numeric_repair=true;')
 anchor='    // AUDIT 2026-08-22: retry this outer step rather than spending it.'
 patch(anchor,'    if(attempt_trace)attempt_clock.row.accepted=accepted;\n    if(soft && accepted)soft_last_gain=std::max(0.,(double)learn_cost_att-(double)cost);\n'+anchor)
 anchor='         (prev_cost-cost) < func_tolerance*prev_cost && FlatOverWindow()){\n        converged=true;'
 patch(anchor,anchor+'\n        if(soft)soft_ftol_reason=true;')
 anchor='        if(ftol_streak>=ftol_k_env){\n          converged=true;'
 patch(anchor,anchor+'\n          if(soft)soft_ftol_reason=true;')
 anchor='      converged=true;\n      if(verbose) std::printf("  MFCG: converged (OCA_FTOL: %d flat/rejected outers)\\n",'
 patch(anchor,'      converged=true;\n      if(soft)soft_ftol_reason=true;\n      if(verbose) std::printf("  MFCG: converged (OCA_FTOL: %d flat/rejected outers)\\n",')
 anchor='    if(converged){ ++k; break; }'
 patch(anchor,'''    if(soft && converged && soft_ftol_reason && !soft_used){
      soft_pending=true;soft_used=true;converged=false;
      soft_budget=.1*std::max(soft_last_gain,1e-12*(double)cost);
      printf("SOFT_KICK_PENDING after_outer=%d cost=%.17g lambda=%.17g radius=%.17g floor=%.17g prev_bnorm=%.17g last_rel=%.17g confirm=%d last_gain=%.17g budget=%.17g\\n",
        k+1,(double)cost,(double)lam_cam,attr_R,numeric_floor,(double)prev_bnorm,(double)last_rel,(int)backtrack_confirm,soft_last_gain,soft_budget);
    }
'''+anchor)
 anchor='  int cheir1=CountCheiralityViolations(p,s);\n  if(prof_score && ts_n>0)'
 patch(anchor,'''  if(soft){
    const long scores_before=soft->scores;
    const bool restored=soft->RestoreBest(p,s,cost);st.cand_evals+=soft->scores-scores_before;
    if(!log.costs.empty())log.costs.back()=cost;
    if(restored)CsvRow(log.iters.empty()?0:log.iters.back(),cost);
  }
'''+anchor)
 restored=source
 for old,new in reversed(patches):assert restored.count(new)==1;restored=restored.replace(new,old)
 assert restored==original,'inverse patch did not recover frozen source'
 return source,patches

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--check-only',action='store_true');a=ap.parse_args()
 src,patches=derive();b=P/'build';b.mkdir(exist_ok=True);path=b/'prism_soft_kick.cu';path.write_text(src)
 local=['soft_kick.cuh','mode_math.h','attempt_trace.h']
 reused=['coarse/native/coarse.cuh','coarse/native/geometry.h','coarse/native/attempt_trace.h']
 manifest=dict(frozen_source_sha256=sha(F/'source/prism_eta2.cu'),derived_source_sha256=sha(path),
   inverse_patch_source_parity=True,substitutions=len(patches),local_headers={h:sha(P/h) for h in local},
   reused_headers={h:sha(CAMPAIGN/h) for h in reused},protocol_sha256=sha(CAMPAIGN/'PROTOCOL_11.md'),
   implementation_notes_sha256=sha(P/'IMPLEMENTATION_NOTES.md'))
 if not a.check_only:
  temp=Path('/dev/shm/prism-soft-kick-tmp');temp.mkdir(exist_ok=True)
  env=dict(os.environ,TMPDIR=str(temp))
  cmd=['nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3','-I'+str(P),
    '-I'+str(F/'source/headers'),str(path),'-o',str(b/'prism-soft-kick'),'-lcublas','-lcusolver']
  with (b/'build.log').open('w') as out:subprocess.run(cmd,stdout=out,stderr=subprocess.STDOUT,check=True,env=env)
  assert manifest['local_headers']=={h:sha(P/h) for h in local}
  assert manifest['reused_headers']=={h:sha(CAMPAIGN/h) for h in reused}
  manifest.update(command=cmd,binary_sha256=sha(b/'prism-soft-kick'))
 (P/'build_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest,indent=2))

if __name__=='__main__':main()
