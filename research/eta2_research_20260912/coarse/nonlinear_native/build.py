#!/usr/bin/env python3
"""One-shot confirmed-stop passenger overlay; frozen source remains untouched."""
from pathlib import Path
import argparse,hashlib,json,subprocess,os
P=Path(__file__).resolve().parent;C=P.parents[1];F=C.parent/'eta2_champion'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def derive():
    subprocess.run(['python3',str(F/'build.py'),'--check-only'],check=True)
    original=(F/'source/prism_eta2.cu').read_text();source=original;patches=[]
    def patch(old,new):
        nonlocal source
        assert source.count(old)==1,(old[:100],source.count(old));source=source.replace(old,new);patches.append((old,new))
    anchor='template <int CD>\nRunLog SolveMFreeShiftedCG('
    patch(anchor,'#include "passenger.cuh"\n\n'+anchor)
    anchor='  if(getenv("OCA_PCG"))pcg=std::make_unique<PrismPcg>(ncam);'
    patch(anchor,anchor+'''
  const bool passenger_on=getenv("OCA_PASSENGER") && atoi(getenv("OCA_PASSENGER"))!=0;
  bool passenger_spent=false,passenger_pending=false,passenger_continuation=false;
  std::unique_ptr<StcgAttemptTrace> attempt_trace;
  if(const char* path=getenv("OCA_STCG_ATTEMPTS"))attempt_trace=std::make_unique<StcgAttemptTrace>(path);
  if(passenger_on)std::printf("PASSENGER_CONFIG trigger=first_confirmed_ftol fresh_assembly=1 K=8 attempts=3 halvings=8 metric=fixed_joint original_radius_clip=0\\n");''')
    anchor='   if(BudgetExpired()){std::printf("BUDGET stop=before_attempt outer=%d seconds=%.9g\\n",k,max_seconds);break;}'
    patch(anchor,anchor+'''
   StcgAttemptClock attempt_clock(attempt_trace.get(),k,retries,!need_assembly,&st.matvecs);
   bool passenger_ftol_reason=false;
   if(passenger_continuation){
     std::printf("PASSENGER_EVENT event=fine_continuation outer=%d trace_row=%zu unchanged_state_retry=0 raw_retry_entry=%d\\n",k,attempt_trace?attempt_trace->rows.size():0,(int)!need_assembly);
     passenger_continuation=false;
   }''')
    anchor='    int sweep_attempt=0; Scalar nc_pAp=0, nc_pp=0;'
    patch(anchor,'''    if(passenger_pending){
      if(!pcg || !classical_lm || !attr_radius || !attr_strict || !numeric_guard ||
         CD!=9 || shared_intr || mf_fp32 || rk || !use_equil || L!=1 || block_on ||
         pcg->reuse || pcg->schur || attr_split || camera_tr || recycle_mode || jit_on ||
         k2mask!=0 || intr_damp!=1 || score_stride!=1 || tau_eff!=lam_cam ||
         (getenv("OCA_POLY_CONG") && atoi(getenv("OCA_POLY_CONG"))!=0) ||
         rld.actor || rld.fixed_eta!=2 ||
         (getenv("OCA_CG_STOP") && atoi(getenv("OCA_CG_STOP"))!=0))
        throw std::runtime_error("passenger requires frozen unshared SIMPLE_RADIAL coupled strict Eta2 configuration");
      passenger_pending=false;passenger_spent=true;
      const auto probe_begin=now();const double before_lambda=lam_cam,before_R=attr_R,before_floor=numeric_floor,before_forcing=prev_bnorm,before_rel=last_rel;
      const int before_confirmation=backtrack_confirm;bool improved=false;
      { prism_passenger::Native correction(ncam,npt,nobs);improved=correction.Run(p,s,E,Cdiag,lam_cam,tau_eff,cost,k); }
      const double probe_seconds=std::chrono::duration<double>(now()-probe_begin).count();
      std::printf("PASSENGER_EVENT event=probe outer=%d trace_row=%zu accepted=%d seconds=%.9g pcg_products=0 ordinary_lm_attempt=0\\n",k,attempt_trace?attempt_trace->rows.size():0,(int)improved,probe_seconds);
      std::printf("PASSENGER_CONTROL outer=%d lambda_before=%.17g lambda_after=%.17g radius_before=%.17g radius_after=%.17g floor_before=%.17g floor_after=%.17g forcing_before=%.17g forcing_after=%.17g last_rel_before=%.17g last_rel_after=%.17g confirm_before=%d confirm_after=%d\\n",
        k,before_lambda,(double)lam_cam,before_R,attr_R,before_floor,numeric_floor,before_forcing,(double)prev_bnorm,before_rel,(double)last_rel,before_confirmation,(int)backtrack_confirm);
      if(!improved){std::printf("PASSENGER_STOP reason=no_coarse_accept outer=%d\\n",k);break;}
      converged=false;ftol_streak=0;stuck=0;prev_cost=cost;
      need_assembly=true;factor_cached=false;pf_obs_dirty=true;
      log.iters.push_back(k);log.costs.push_back(cost);CsvRow(k,(double)cost);
      if(TargetReached(cost,k))break;
      passenger_continuation=true;continue;
    }
'''+anchor)
    anchor='    for(cg_it=0; cg_it<maxck; ++cg_it){\n      KvS(pv_,Ap_);'
    patch(anchor,'    for(cg_it=0; cg_it<maxck; ++cg_it){\n      if(attempt_trace)++attempt_clock.row.pcg_iterations;\n      KvS(pv_,Ap_);')
    anchor='      if(!(pAp>1e-14*pp)){\n        if(model_capture'
    patch(anchor,'      if(!(pAp>1e-14*pp)){\n        if(attempt_trace)attempt_clock.row.cutoff=true;\n        if(model_capture')
    anchor='        lam_cam=numeric_floor;prev_bnorm=numeric_prior_bnorm;need_assembly=false;factor_cached=false;'
    patch(anchor,anchor+'\n        if(attempt_trace)attempt_clock.row.numeric_repair=true;')
    anchor='    if(!accepted && retries<max_inner_retry){'
    patch(anchor,'    if(attempt_trace)attempt_clock.row.accepted=accepted;\n'+anchor)
    for anchor in ('(prev_cost-cost) < func_tolerance*prev_cost && FlatOverWindow()){\n        converged=true;',
                   'if(ftol_streak>=ftol_k_env){\n          converged=true;',
                   '// streak, matching the offline simulation (which saw only best-so-far).\n      converged=true;'):
        patch(anchor,anchor+'passenger_ftol_reason=true;')
    anchor='    if(converged){ ++k; break; }'
    patch(anchor,'''    if(converged && passenger_ftol_reason && passenger_on && !passenger_spent){
      passenger_pending=true;converged=false;need_assembly=true;
      std::printf("PASSENGER_EVENT event=pending outer=%d next_outer=%d lambda=%.17g radius=%.17g cost=%.17g confirmation=%d\\n",k,k+1,(double)lam_cam,attr_R,(double)cost,(int)backtrack_confirm);
    }
'''+anchor)
    restored=source
    for old,new in reversed(patches):assert restored.count(new)==1;restored=restored.replace(new,old)
    assert restored==original
    return source,patches

def main():
    p=argparse.ArgumentParser();p.add_argument('--check-only',action='store_true');a=p.parse_args()
    source,patches=derive();b=P/'build';b.mkdir(exist_ok=True);path=b/'prism_passenger.cu';path.write_text(source)
    assert sha(P/'attempt_trace.h')==sha(C/'steihaug/attempt_trace.h')
    headers={h:sha(P/h) for h in ('passenger.cuh','geometry.h','clusters.h','attempt_trace.h')}
    manifest=dict(frozen_source_sha256=sha(F/'source/prism_eta2.cu'),derived_source_sha256=sha(path),inverse_patch_source_parity=True,
                  substitutions=len(patches),local_headers=headers,exact_common_attempt_trace_sha256=sha(P/'attempt_trace.h'),protocol_sha256=sha(C/'PROTOCOL_09_NATIVE.md'))
    if not a.check_only:
        cmd=['nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3','-I'+str(P),'-I'+str(F/'source/headers'),str(path),'-o',str(b/'prism-passenger'),'-lcublas','-lcusolver']
        env=dict(os.environ,TMPDIR='/dev/shm')
        with (b/'build.log').open('w') as out:subprocess.run(cmd,stdout=out,stderr=subprocess.STDOUT,env=env,check=True)
        assert headers=={h:sha(P/h) for h in headers};manifest.update(command=cmd,binary_sha256=sha(b/'prism-passenger'))
    (P/'build_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest,indent=2))

if __name__=='__main__':main()
