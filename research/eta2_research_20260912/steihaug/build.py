#!/usr/bin/env python3
"""Derive a runtime-optional STCG arm from the checksum-pinned Eta2 source."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

P = Path(__file__).resolve().parent
F = P.parent.parent / 'eta2_champion'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def derive():
    subprocess.run(['python3', str(F/'build.py'), '--check-only'], check=True)
    original = (F/'source/prism_eta2.cu').read_text()
    source, patches = original, []

    def patch(old, new):
        nonlocal source
        assert source.count(old) == 1, (old[:100], source.count(old))
        source = source.replace(old, new)
        patches.append((old, new))

    patch('#include "pcg_camera.cuh"',
          '#include "pcg_camera.cuh"\n#include "metric.cuh"\n#include "attempt_trace.h"')
    patch('  double attr_R=0,attr_old_R=0,attr_norm=0,attr_next_lambda=0,attr_raw_norm=0;',
          '  const bool stcg_on=getenv("OCA_STEIHAUG") && atoi(getenv("OCA_STEIHAUG"))!=0;\n'
          '  double attr_R=0,attr_old_R=0,attr_norm=0,attr_next_lambda=0,attr_raw_norm=0;')
    anchor = '  if(getenv("OCA_PCG"))pcg=std::make_unique<PrismPcg>(ncam);'
    patch(anchor, anchor + '''
  std::unique_ptr<StcgAttemptTrace> attempt_trace;
  if(const char* path=getenv("OCA_STCG_ATTEMPTS"))attempt_trace=std::make_unique<StcgAttemptTrace>(path);
  std::unique_ptr<PrismSteihaug> stcg;
  if(stcg_on){
    if(!pcg || !classical_lm || !attr_radius || !attr_strict || !numeric_guard ||
       CD!=9 || shared_intr || mf_fp32 || rk || getenv("OCA_PCG_REUSE") ||
       getenv("OCA_PCG_SCHUR") || (getenv("OCA_CG_STOP") && atoi(getenv("OCA_CG_STOP"))!=0))
      throw std::runtime_error("STCG requires frozen strict radius single-shift PCG configuration");
    stcg=std::make_unique<PrismSteihaug>(ncam);
    printf("STCG_CONFIG metric=actual_pcg_factor bootstrap=first_forcing_step floor=disabled variable_metric_radius=1\\n");
  }''')
    anchor = '   if(BudgetExpired()){std::printf("BUDGET stop=before_attempt outer=%d seconds=%.9g\\n",k,max_seconds);break;}'
    patch(anchor, anchor + '\n   StcgAttemptClock attempt_clock(attempt_trace.get(),k,retries,!need_assembly,&st.matvecs);')
    anchor = '    for(cg_it=0; cg_it<maxck; ++cg_it){\n      KvS(pv_,Ap_);'
    patch(anchor, '    for(cg_it=0; cg_it<maxck; ++cg_it){\n      if(attempt_trace)++attempt_clock.row.pcg_iterations;\n      KvS(pv_,Ap_);')
    anchor = '      if(!(pAp>1e-14*pp)){\n        if(model_capture'
    patch(anchor, '      if(!(pAp>1e-14*pp)){\n        if(attempt_trace)attempt_clock.row.cutoff=true;\n        if(model_capture')
    anchor = 'pcg->Prepare(Hcc,E,shifts[0],k,retries,Gp,fragment_points,p.mf_coff,Rf,nobs);pcg->Apply(r_);cublasDdot(blas,n_c,r_,1,pcg->z,1,&pcg->rz);CUDA_CHECK(cudaMemcpy(pv_,pcg->z,n_c*8ul,cudaMemcpyDeviceToDevice));'
    patch(anchor, anchor + '\n      if(stcg)stcg->Start(pcg->rz);')
    anchor = '        ++st.negcurv; trunc=true; nc_pAp=pAp; nc_pp=pp; break;'
    patch(anchor, '''        if(stcg){
          double g[3];stcg->Gram(pcg->B,xs[0],pv_,g);
          if(!(attr_R>0)){attr_R=stcg->bootstrap_gradient_radius;++stcg->bootstraps;}
          const double tau=prism_stcg::boundary_tau(g[0],g[1],g[2],attr_R);
          if(std::isfinite(pAp) && pp>0 && std::isfinite(tau)){
            if(rho_mode)preds[0]+=tau*pcg->rz-.5*tau*tau*pAp;
            cublasDaxpy(blas,n_c,&tau,pv_,1,xs[0],1);
            const double mt=-tau;cublasDaxpy(blas,n_c,&mt,Ap_,1,r_,1);
            cublasDdot(blas,n_c,r_,1,r_,1,&rr);
            stcg->attempt_reason=2;++stcg->curvature_boundaries;
          }else{stcg->attempt_reason=3;++stcg->invalid;}
          pcg->last_depth=cg_it+1;cg_broke=true;
          if(prof){cudaDeviceSynchronize();t_mv+=std::chrono::duration<double>(now()-t0).count();}
        }
''' + anchor)
    anchor = '      Scalar al=(pcg?pcg->rz:rr)/pAp;'
    patch(anchor, anchor + '''
      if(stcg && attr_R>0){
        double g[3];stcg->Gram(pcg->B,xs[0],pv_,g);
        const long double aa=al;
        stcg->trial_norm=(double)std::sqrt(std::max((long double)0,
          (long double)g[0]+2*aa*g[1]+aa*aa*g[2]));
        if(prism_stcg::crosses(g[0],g[1],g[2],al,attr_R)){
          const double tau=prism_stcg::boundary_tau(g[0],g[1],g[2],attr_R);
          if(std::isfinite(tau)){
            if(rho_mode)preds[0]+=tau*pcg->rz-.5*tau*tau*pAp;
            cublasDaxpy(blas,n_c,&tau,pv_,1,xs[0],1);
            const double mt=-tau;cublasDaxpy(blas,n_c,&mt,Ap_,1,r_,1);
            cublasDdot(blas,n_c,r_,1,r_,1,&rr);
            stcg->attempt_reason=1;++stcg->boundaries;
          }else{stcg->attempt_reason=3;++stcg->invalid;}
          pcg->last_depth=cg_it+1;cg_broke=true;
          if(prof){cudaDeviceSynchronize();t_mv+=std::chrono::duration<double>(now()-t0).count();}
          break;
        }
      }''')
    patch('    if(numeric_guard && trunc && numeric_rebuilds<32',
          '    if(!stcg && numeric_guard && trunc && numeric_rebuilds<32')
    anchor = '        lam_cam=numeric_floor;prev_bnorm=numeric_prior_bnorm;need_assembly=false;factor_cached=false;'
    patch(anchor, anchor + '\n        if(attempt_trace)attempt_clock.row.numeric_repair=true;')
    anchor = '    if(!accepted && retries<max_inner_retry){'
    patch(anchor, '    if(attempt_trace)attempt_clock.row.accepted=accepted;\n' + anchor)
    old = '''        cublasDnrm2(blas,n_c,xs[0],1,&attr_raw_norm);
        if(!(attr_R>0))attr_R=std::isfinite(attr_raw_norm)&&attr_raw_norm>0?attr_raw_norm:1;
        attr_old_R=attr_R;
        if(attr_raw_norm>attr_R){double scale=attr_R/attr_raw_norm;cublasDscal(blas,n_c,&scale,xs[0],1);}'''
    new = '''        if(stcg){
          attr_raw_norm=stcg->Norm(pcg->B,xs[0]);
          if(!(attr_R>0)){attr_R=std::isfinite(attr_raw_norm)&&attr_raw_norm>0?attr_raw_norm:1;++stcg->bootstraps;}
          attr_old_R=attr_R;
        }else{
''' + old + '\n        }'
    patch(old, new)
    anchor = '        cublasDnrm2(blas,n_c,xc_un,1,&attr_norm);'
    patch(anchor, '        if(stcg)attr_norm=stcg->Norm(pcg->B,xc_un);else\n' + anchor)
    anchor = '        attr_next_lambda=std::clamp(attr_next_lambda,numeric_guard?numeric_floor:1e-16,1e16);'
    patch(anchor, '        attr_next_lambda=std::clamp(attr_next_lambda,(!stcg && numeric_guard)?numeric_floor:1e-16,1e16);')
    anchor = '      std::printf("CLASSICAL_LM o=%d lambda=%.17g tau=%.17g prediction=%.17g rho=%.17g accept=%d\\n",k,(double)lam_cam,(double)tau_eff,lm_prediction,lm_rho,(int)have);'
    patch(anchor, '''      if(stcg)std::printf("STCG o=%d retry=%d reason=%d depth=%d cap=%d next_iterate_norm=%.17g norm=%.17g radius=%.17g accept=%d metric_seconds=%.9g grams=%ld\\n",
        k,retries,stcg->attempt_reason,cg_broke?cg_it+1:maxck,maxck,stcg->trial_norm,
        attr_norm,attr_old_R,(int)have,stcg->metric_seconds,stcg->gram_calls);
''' + anchor)
    anchor = '  if(numeric_guard)std::printf("NUMERIC_REPAIR summary rebuilds=%ld floor=%.17g\\n",numeric_rebuilds,numeric_floor);'
    patch(anchor, anchor + '''
  if(stcg)std::printf("STCG summary boundaries=%ld curvature_boundaries=%ld invalid=%ld bootstraps=%ld metric_seconds=%.9g grams=%ld\\n",
    stcg->boundaries,stcg->curvature_boundaries,stcg->invalid,stcg->bootstraps,stcg->metric_seconds,stcg->gram_calls);''')
    restored = source
    for old, new in reversed(patches):
        assert restored.count(new) == 1, ('inverse ambiguity', new[:100])
        restored = restored.replace(new, old)
    assert restored == original, 'Inverse patches do not recover frozen source'
    return source, patches


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--check-only', action='store_true')
    args = ap.parse_args()
    source, patches = derive()
    b = P/'build'
    b.mkdir(exist_ok=True)
    path = b/'prism_stcg.cu'
    path.write_text(source)
    manifest = dict(frozen_source_sha256=sha(F/'source/prism_eta2.cu'),
                    derived_source_sha256=sha(path), substitutions=len(patches),
                    inverse_patch_source_parity=True,
                    local_headers={x: sha(P/x) for x in ['boundary.h', 'metric.cuh', 'attempt_trace.h']},
                    protocol_draft_sha256=sha(P/'PROTOCOL_DRAFT.md'))
    if not args.check_only:
        cmd = ['nvcc', '-O3', '-DNDEBUG', '-std=c++17', '-arch=sm_89',
               '-I/usr/include/eigen3', '-I'+str(P), '-I'+str(F/'source/headers'),
               str(path), '-o', str(b/'prism-stcg'), '-lcublas', '-lcusolver']
        with (b/'build.log').open('w') as log:
            subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, check=True)
        assert manifest['local_headers'] == {x: sha(P/x) for x in ['boundary.h', 'metric.cuh', 'attempt_trace.h']}, \
            'A local header changed during compilation; rebuild before using this binary'
        assert manifest['protocol_draft_sha256'] == sha(P/'PROTOCOL_DRAFT.md'), \
            'Protocol changed during compilation'
        manifest.update(command=cmd, binary_sha256=sha(b/'prism-stcg'))
    (P/'build_manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
