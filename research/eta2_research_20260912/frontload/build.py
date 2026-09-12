#!/usr/bin/env python3
"""Derive the registered opening-only coherent accuracy arm from frozen Eta2."""
from pathlib import Path
import argparse,hashlib,json,subprocess
P=Path(__file__).resolve().parent;C=P.parent;F=C.parent/'eta2_champion'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def derive():
    subprocess.run(['python3',str(F/'build.py'),'--check-only'],check=True)
    original=(F/'source/prism_eta2.cu').read_text();source=original;patches=[]
    def patch(old,new):
        nonlocal source
        assert source.count(old)==1,(old[:100],source.count(old))
        source=source.replace(old,new);patches.append((old,new))
    anchor='template <int CD>\nRunLog SolveMFreeShiftedCG('
    patch(anchor,'#include "frontload.cuh"\n#include "attempt_trace.h"\n\n'+anchor)
    anchor='  if(getenv("OCA_PCG"))pcg=std::make_unique<PrismPcg>(ncam);'
    patch(anchor,anchor+'''
  const bool frontload_on=getenv("OCA_FRONTLOAD") && atoi(getenv("OCA_FRONTLOAD"))!=0;
  FrontloadTotals frontload_totals;
  bool frontload_handoff_printed=false;
  std::unique_ptr<StcgAttemptTrace> attempt_trace;
  if(const char* path=getenv("OCA_STCG_ATTEMPTS"))attempt_trace=std::make_unique<StcgAttemptTrace>(path);
  if(frontload_on)std::printf("FRONTLOAD_CONFIG accepted_outers=3 eta=0.05 operator=coherent_fp64 clipping=off_strict_ball_retained native_assembly_retained=1\\n");''')
    anchor='   if(BudgetExpired()){std::printf("BUDGET stop=before_attempt outer=%d seconds=%.9g\\n",k,max_seconds);break;}'
    patch(anchor,anchor+'''
   StcgAttemptClock attempt_clock(attempt_trace.get(),k,retries,!need_assembly,&st.matvecs);
   const bool frontload_active=frontload_on && n_accept<3;
   if(frontload_on && !frontload_active && !frontload_handoff_printed){
     frontload_handoff_printed=true;
     std::printf("FRONTLOAD_HANDOFF outer=%d accepts=%d previous_rhs_norm=%.17g\\n",k,n_accept,(double)prev_bnorm);
   }''')
    anchor='    // ---- operator ----\n    auto Kv='
    patch(anchor,'''    std::unique_ptr<FrontloadAttempt> front;
    if(frontload_active){
      if(!pcg || !classical_lm || !attr_radius || !attr_strict || !numeric_guard ||
         CD!=9 || shared_intr || mf_fp32 || rk || !use_equil || L!=1 || block_on ||
         pcg->reuse || pcg->schur || attr_split || camera_tr || recycle_mode || jit_on ||
         k2mask!=0 || intr_damp!=1 || score_stride!=1 || tau_eff!=lam_cam ||
         (getenv("OCA_POLY_CONG") && atoi(getenv("OCA_POLY_CONG"))!=0) ||
         rld.actor || rld.fixed_eta!=2 ||
         (getenv("OCA_CG_STOP") && atoi(getenv("OCA_CG_STOP"))!=0))
        throw std::runtime_error("frontload requires frozen unshared SIMPLE_RADIAL coupled strict Eta2 configuration");
      front=std::make_unique<FrontloadAttempt>(p,s,E,Cdiag,r2acc,obscnt,lam_cam,k,retries,frontload_totals);
      CUDA_CHECK(cudaMemcpy(bprime,front->rhs,n_c*8ul,cudaMemcpyDeviceToDevice));
    }

'''+anchor)
    anchor='    auto KvS=[&](const Scalar* vin,Scalar* vout){'
    patch(anchor,anchor+'\n      if(front){front->ProductBase(vin,vout);++st.matvecs;return;}')
    anchor='      MFBackSub<<<GridSize(npt),256>>>(Rf,bp,tac,npt,xpv); });'
    patch(anchor,'      if(front)front->CompletePhysical(xcu,xpv);else\n'+anchor)
    anchor='''      Lift(x_scaled);
      _ps(ts_pass1,[&]{
      CUDA_CHECK(cudaMemset(tacc,0,(size_t)n_p*sizeof(Scalar)));'''
    patch(anchor,'''      Lift(x_scaled);
      _ps(ts_pass1,[&]{
      if(front)return; // coherent completion is performed in ScoreTail from actual xcu
      CUDA_CHECK(cudaMemset(tacc,0,(size_t)n_p*sizeof(Scalar)));''')
    anchor='    if(rld.enabled)eta=rld.Forcing(eta);\n    prev_bnorm=nb;'
    patch(anchor,'    if(rld.enabled)eta=rld.Forcing(eta);\n    if(front)eta=.05;\n    prev_bnorm=nb;')
    anchor='    for(cg_it=0; cg_it<maxck; ++cg_it){\n      KvS(pv_,Ap_);'
    patch(anchor,'    for(cg_it=0; cg_it<maxck; ++cg_it){\n      if(attempt_trace)++attempt_clock.row.pcg_iterations;\n      KvS(pv_,Ap_);')
    anchor='      if(!(pAp>1e-14*pp)){\n        if(model_capture'
    patch(anchor,'      if(!(pAp>1e-14*pp)){\n        if(attempt_trace)attempt_clock.row.cutoff=true;\n        if(front && model_capture)throw std::runtime_error("frontload uses separate coherent correctness harness; native mixed negative capture is incompatible");\n        if(model_capture')
    anchor='cublasDnrm2(blas,n_c,pcg->tmp,1,&true_norm);if(!std::isfinite(true_norm)'
    patch(anchor,'cublasDnrm2(blas,n_c,pcg->tmp,1,&true_norm);if(front)front->RecordFresh(true_norm,nb);if(!std::isfinite(true_norm)')
    anchor='    if(numeric_guard && trunc && numeric_rebuilds<32'
    patch(anchor,'''    if(front){
      front->EnsureFresh(blas,xs[0],nb,st.matvecs);
      std::printf("FRONTLOAD_LINEAR outer=%d retry=%d accepts_before=%d depth=%d cap=%d eta=%.17g recursive=%.17g fresh=%.17g rhs_norm=%.17g lambda=%.17g truncated=%d products=%ld\\n",
        k,retries,n_accept,trunc?cg_it+1:(cg_broke?cg_it+1:maxck),maxck,(double)eta,
        std::sqrt((double)rr)/std::max(1e-300,(double)nb),front->fresh_relative,(double)nb,(double)lam_cam,(int)trunc,front->products);
    }
'''+anchor)
    anchor='        lam_cam=numeric_floor;prev_bnorm=numeric_prior_bnorm;need_assembly=false;factor_cached=false;'
    patch(anchor,anchor+'\n        if(attempt_trace)attempt_clock.row.numeric_repair=true;')
    anchor='        if(attr_raw_norm>attr_R){double scale=attr_R/attr_raw_norm;cublasDscal(blas,n_c,&scale,xs[0],1);}'
    patch(anchor,anchor.replace('if(attr_raw_norm>attr_R)','if(!front && attr_raw_norm>attr_R)'))
    anchor='    if(!accepted && retries<max_inner_retry){'
    patch(anchor,'    if(front)front.reset(); // charge destruction before any target crossing timestamp\n    if(attempt_trace)attempt_clock.row.accepted=accepted;\n'+anchor)
    anchor='  if(numeric_guard)std::printf("NUMERIC_REPAIR summary rebuilds=%ld floor=%.17g\\n",numeric_rebuilds,numeric_floor);'
    patch(anchor,anchor+'\n  if(frontload_on)frontload_totals.Print();')
    restored=source
    for old,new in reversed(patches):
        assert restored.count(new)==1,('inverse ambiguous',new[:100])
        restored=restored.replace(new,old)
    assert restored==original
    return source,patches


def main():
    p=argparse.ArgumentParser();p.add_argument('--check-only',action='store_true');args=p.parse_args()
    source,patches=derive();b=P/'build';b.mkdir(exist_ok=True);path=b/'prism_frontload.cu';path.write_text(source)
    diag=(C/'diagnostic_kernels.cuh').read_text();assert (P/'coherent_rows.cuh').read_text()=='#pragma once\n'+diag[:diag.index('struct Brief0Reference {')]
    assert sha(P/'attempt_trace.h')==sha(C/'steihaug/attempt_trace.h')
    headers={n:sha(P/n) for n in ('frontload.cuh','coherent_rows.cuh','attempt_trace.h')}
    manifest=dict(frozen_source_sha256=sha(F/'source/prism_eta2.cu'),derived_source_sha256=sha(path),substitutions=len(patches),inverse_patch_source_parity=True,
                  local_headers=headers,diagnostic_kernels_source_sha256=sha(C/'diagnostic_kernels.cuh'),
                  exact_common_attempt_trace_sha256=sha(C/'steihaug/attempt_trace.h'),protocol_sha256=sha(C/'PROTOCOL_05_NATIVE.md'))
    if not args.check_only:
        cmd=['nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3','-I'+str(P),'-I'+str(F/'source/headers'),str(path),'-o',str(b/'prism-frontload'),'-lcublas','-lcusolver']
        with (b/'build.log').open('w') as log:subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True)
        assert headers=={n:sha(P/n) for n in headers},'local source changed while compiling'
        assert manifest['protocol_sha256']==sha(C/'PROTOCOL_05_NATIVE.md')
        manifest.update(command=cmd,binary_sha256=sha(b/'prism-frontload'))
    (P/'build_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest,indent=2))


if __name__=='__main__':main()
