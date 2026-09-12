#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,subprocess
P=Path(__file__).resolve().parent;F=P.parents[1]/'eta2_champion'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    subprocess.run(['python3',str(F/'build.py'),'--check-only'],check=True)
    original=(F/'source/prism_eta2.cu').read_text();s=original;patches=[]
    def patch(a,b):
        nonlocal s
        assert s.count(a)==1,(a[:80],s.count(a));s=s.replace(a,b);patches.append((a,b))
    patch('#include "pcg_camera.cuh"','#include "pcg_camera.cuh"\n#include "attempt_trace.h"')
    a='  if(getenv("OCA_PCG"))pcg=std::make_unique<PrismPcg>(ncam);'
    patch(a,a+'\n  std::unique_ptr<StcgAttemptTrace> attempt_trace;\n  if(const char* path=getenv("OCA_STCG_ATTEMPTS"))attempt_trace=std::make_unique<StcgAttemptTrace>(path);')
    a='   if(BudgetExpired()){std::printf("BUDGET stop=before_attempt outer=%d seconds=%.9g\\n",k,max_seconds);break;}'
    patch(a,a+'\n   StcgAttemptClock attempt_clock(attempt_trace.get(),k,retries,!need_assembly,&st.matvecs);')
    a='    for(cg_it=0; cg_it<maxck; ++cg_it){\n      KvS(pv_,Ap_);'
    patch(a,'    for(cg_it=0; cg_it<maxck; ++cg_it){\n      if(attempt_trace)++attempt_clock.row.pcg_iterations;\n      KvS(pv_,Ap_);')
    a='      if(!(pAp>1e-14*pp)){\n        if(model_capture'
    patch(a,'      if(!(pAp>1e-14*pp)){\n        if(attempt_trace)attempt_clock.row.cutoff=true;\n        if(model_capture')
    a='        lam_cam=numeric_floor;prev_bnorm=numeric_prior_bnorm;need_assembly=false;factor_cached=false;'
    patch(a,a+'\n        if(attempt_trace)attempt_clock.row.numeric_repair=true;')
    a='    if(!accepted && retries<max_inner_retry){'
    patch(a,'    if(attempt_trace)attempt_clock.row.accepted=accepted;\n'+a)
    patch('  double attr_R=0,attr_old_R=0,attr_norm=0,attr_next_lambda=0,attr_raw_norm=0;',
      '  const bool pi_radius=getenv("OCA_PI_RADIUS") && atoi(getenv("OCA_PI_RADIUS"))!=0;\n'
      '  double pi_previous_error=0; long pi_updates=0,pi_invalid=0;\n'
      '  double attr_R=0,attr_old_R=0,attr_norm=0,attr_next_lambda=0,attr_raw_norm=0;')
    a='        attr_R=prism_camera_tr::radius_after(attr_old_R,attr_norm,lm_rho);'
    patch(a,a+'''\n        if(pi_radius && have){
          double e=std::max(1e-6,std::fabs(1.-lm_rho));
          if(std::isfinite(e)){
            double previous=pi_previous_error>0?pi_previous_error:e;
            double factor=std::clamp(std::exp(.3*std::log(.3/e)+.4*std::log(previous/e)),.25,2.);
            attr_R=std::max(1e-14,attr_old_R*factor);
            pi_previous_error=e; ++pi_updates;
            printf("PI_RADIUS o=%d e=%.17g previous=%.17g factor=%.17g radius=%.17g next=%.17g\\n",k,e,previous,factor,attr_old_R,attr_R);
          } else ++pi_invalid;
        }''')
    undo=s
    for a,b in reversed(patches):assert undo.count(b)==1;undo=undo.replace(b,a)
    assert undo==original
    b=P/'build';b.mkdir(exist_ok=True);src=b/'prism_pi.cu';src.write_text(s)
    trace=P.parent/'steihaug/attempt_trace.h';tracehash=sha(trace)
    cmd=['nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3','-I'+str(F/'source/headers'),'-I'+str(trace.parent),str(src),'-o',str(b/'prism-pi'),'-lcublas','-lcusolver']
    with (b/'build.log').open('w') as out:subprocess.run(cmd,stdout=out,stderr=subprocess.STDOUT,check=True)
    out=dict(command=cmd,source_sha256=sha(src),binary_sha256=sha(b/'prism-pi'),frozen_source_sha256=sha(F/'source/prism_eta2.cu'),
      reverse_patch_byte_identity=True,protocol_sha256=sha(P/'PROTOCOL.md'),attempt_trace_sha256=tracehash)
    assert sha(trace)==tracehash,'Trace header changed during build'
    (b/'manifest.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
