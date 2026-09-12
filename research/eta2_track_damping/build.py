#!/usr/bin/env python3
"""Hash-pinned, reversible static point-damping overlay; defaults remain off."""
from pathlib import Path
import hashlib,json,os,subprocess
P=Path(__file__).resolve().parent
F=P.parent/'eta2_champion'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def derive():
    subprocess.run(['python3',str(F/'build.py'),'--check-only'],check=True)
    original=(F/'source/prism_eta2.cu').read_text();s=original;patches=[]
    def patch(a,b):
        nonlocal s
        assert s.count(a)==1,(a[:100],s.count(a))
        s=s.replace(a,b);patches.append((a,b))
    a='template <int CD>\nRunLog SolveMFreeShiftedCG('
    patch(a,'#include "attempt_trace.h"\n#include "track_factor.cuh"\n'+a)
    a='  if(getenv("OCA_PCG"))pcg=std::make_unique<PrismPcg>(ncam);'
    patch(a,a+'''
  const bool track_tau=getenv("OCA_TRACK_TAU") && atoi(getenv("OCA_TRACK_TAU"))!=0;
  std::unique_ptr<StcgAttemptTrace> attempt_trace;
  if(const char* path=getenv("OCA_STCG_ATTEMPTS"))attempt_trace=std::make_unique<StcgAttemptTrace>(path);
  if(track_tau)std::printf("TRACK_TAU rule=1,1,0.3 classes=le2,3to5,ge6 scope=all_attempts\\n");''')
    a='   if(BudgetExpired()){std::printf("BUDGET stop=before_attempt outer=%d seconds=%.9g\\n",k,max_seconds);break;}'
    patch(a,a+'\n   StcgAttemptClock attempt_clock(attempt_trace.get(),k,retries,!need_assembly,&st.matvecs);')
    a='    tau_used = tau_eff;'
    patch(a,a+'''
    if(track_tau && (!tau_split || CD!=9 || shared_intr || mf_fp32 || rk ||
       !classical_lm || attr_split || !attr_radius || !attr_strict || !numeric_guard ||
       !pcg || block_on || camera_tr || L!=1 || tau_eff!=lam_cam ||
       tau_lam_maxobs>0 || tau_lam_cond>0 || point_trust_tau>0 || k2mask!=0 ||
       intr_damp!=1 || score_stride!=1 || rld.fixed_eta!=2 || rld.actor))
      throw std::runtime_error("track damping requires frozen coupled strict Eta2 configuration");''')
    a='      else\n        MFPointFactorTau<<<GridSize(npt),256>>>(Cdiag,R0f,tau_eff,npt,Rf,okf);'
    patch(a,'''      else if(track_tau)
        MFPointFactorTauTrack<<<GridSize(npt),256>>>(Cdiag,R0f,p.point_obs_offsets,tau_eff,npt,Rf,okf);
'''+a)
    a='    for(cg_it=0; cg_it<maxck; ++cg_it){\n      KvS(pv_,Ap_);'
    patch(a,a.replace('      KvS','      if(attempt_trace)++attempt_clock.row.pcg_iterations;\n      KvS'))
    a='      if(!(pAp>1e-14*pp)){\n        if(model_capture'
    patch(a,a.replace('        if(model_capture','        if(attempt_trace)attempt_clock.row.cutoff=true;\n        if(model_capture'))
    a='        lam_cam=numeric_floor;prev_bnorm=numeric_prior_bnorm;need_assembly=false;factor_cached=false;'
    patch(a,a+'\n        if(attempt_trace)attempt_clock.row.numeric_repair=true;')
    a='    if(!accepted && retries<max_inner_retry){'
    patch(a,'    if(attempt_trace)attempt_clock.row.accepted=accepted;\n'+a)
    restored=s
    for a,b in reversed(patches):
        assert restored.count(b)==1
        restored=restored.replace(b,a)
    assert restored==original
    return s,len(patches)
def main():
    source,count=derive();b=P/'build';b.mkdir(exist_ok=True)
    path=b/'prism_track_tau.cu';path.write_text(source)
    cmd=['nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3',
         '-I'+str(P),'-I'+str(F/'source/headers'),str(path),'-o',str(b/'prism-track-tau'),'-lcublas','-lcusolver']
    env=os.environ.copy();env['TMPDIR']='/dev/shm'
    with (b/'build.log').open('w') as out:subprocess.run(cmd,env=env,stdout=out,stderr=subprocess.STDOUT,check=True)
    m=dict(command=cmd,frozen_source_sha256=sha(F/'source/prism_eta2.cu'),
           champion_sha256=sha(F/'champion.json'),derived_source_sha256=sha(path),
           binary_sha256=sha(b/'prism-track-tau'),protocol_sha256=sha(P/'PROTOCOL.md'),
           headers={f:sha(P/f) for f in ('attempt_trace.h','track_factor.cuh')},
           inverse_source_parity=True,substitutions=count,default='off',rule=[1,1,.3])
    (P/'build_manifest.json').write_text(json.dumps(m,indent=2)+'\n');print('BUILT',m['binary_sha256'],flush=True)
if __name__=='__main__':main()
