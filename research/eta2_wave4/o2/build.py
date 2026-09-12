#!/usr/bin/env python3
"""Opt-in O2 source overlay. Frozen source and headers are never modified."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

P = Path(__file__).resolve().parent
F = P.parent.parent / 'eta2_champion'
C = P.parent.parent / 'eta2_research_20260912'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def derive():
    subprocess.run(['python3', str(F/'build.py'), '--check-only'], check=True)
    original = (F/'source/prism_eta2.cu').read_text()
    files = {'prism_o2.cu': original}
    for name in ['full_step_model.cuh', 'point_safeguard.cuh']:
        files[name] = (F/'source/headers'/name).read_text()
    bases = files.copy()
    patches = []

    def patch(name, old, new, kind):
        assert files[name].count(old) == 1, (name, old[:120], files[name].count(old))
        files[name] = files[name].replace(old, new)
        patches.append((name, old, new, kind))

    def source(old, new, kind):
        patch('prism_o2.cu', old, new, kind)

    def region(start, end, changes, kind):
        text = files['prism_o2.cu'];i = text.index(start);j = text.index(end, i)
        old = text[i:j];new = old
        for a, b in changes:
            assert new.count(a) == 1, (a[:80], new.count(a))
            new = new.replace(a, b)
        source(old, new, kind)

    anchor = '#include "bal_factored_grad.cuh"  // ROUND 10: 12-param GN gradient (pose 6 + f,k1,k2 + point 3)'
    source(anchor, anchor+'\n#include "projection.cuh"', 'shared_projection')
    region('__global__ void KernelCost(', '// Block-reduced cost kernel.', [
        ('int rk = 0, Scalar rk_a2 = 0.0)', 'int rk = 0, Scalar rk_a2 = 0.0, bool stage_objective = true)'),
        ('Scalar xp = -Px / Pz, yp = -Py / Pz;', 'Scalar den=stage_objective?O2Depth(o,Pz):Pz;\n  Scalar xp = -Px / den, yp = -Py / den;')], 'cost')
    region('__global__ void KernelCostBlockRed(', '\n}\n', [
        ('unsigned int* skipped = nullptr)', 'unsigned int* skipped = nullptr, bool stage_objective = true)'),
        ('Scalar xp = -Px / Pz, yp = -Py / Pz;', 'Scalar den=stage_objective?O2Depth(o,Pz):Pz;\n    Scalar xp = -Px / den, yp = -Py / den;')], 'cost')
    region('__global__ void MFAssemble(', '__device__ __forceinline__ void MFGivens', [
        ('Scalar xq=-Px/Pz,yq=-Py/Pz,r2=xq*xq+yq*yq;', 'Scalar den=O2Depth(o,Pz);\n  Scalar xq=-Px/den,yq=-Py/den,r2=xq*xq+yq*yq;'),
        ('BalResidualGrad12(Rc[0]', 'O2BalResidualGrad12(o,Rc[0]')], 'assembly_residual_jacobian_regularizer')
    text = files['prism_o2.cu'];i = text.index('Scalar ComputeCost(');j = text.index('#include "full_step_model.cuh"', i)
    original_cost = text[i:j].replace('Scalar ComputeCost(', 'Scalar ComputeOriginalCost(', 1)
    original_cost = original_cost.replace('rk, rk_a2);', 'rk, rk_a2, 0, nullptr, false);', 1)
    original_cost = original_cost.replace('rk, rk_a2);', 'rk, rk_a2, false);', 1)
    source('#include "full_step_model.cuh"', original_cost+'#include "runtime.cuh"\n#include "full_step_model.cuh"', 'original_score_and_runtime')
    patch('full_step_model.cuh', 'BalDirectional12(r,t+3*c', 'O2BalDirectional12(o,r,t+3*c', 'full_model')
    patch('point_safeguard.cuh', 'double u=-qx/qz,v=-qy/qz,s=u*u+v*v;',
          'double den=O2Depth(o,qz);\n  double u=-qx/den,v=-qy/den,s=u*u+v*v;', 'point_safeguard')

    # Environment whitelist ensures an alternate projection/solver path cannot
    # be silently selected by ambient research flags. Diagnostics may add paths
    # only once audited; no broad prefix allowance.
    config = json.loads((F/'champion.json').read_text())['flags']
    pairs = ',\n'.join('    {'+json.dumps(k)+','+json.dumps(v)+'}' for k, v in config.items())
    extras = ['OCA_O2','OCA_O2_AUDIT','OCA_TARGET_COST','OCA_MAX_SECONDS','OCA_STCG_ATTEMPTS','OCA_WAVE_TRACE','OCA_CSV',
              'OCA_CSV_DIR','OCA_PROFILE','OCA_PROFILE_SCORE','OCA_RLD_LOG']
    guard = '''
static void O2ValidateEnvironment(){
  const std::vector<std::pair<std::string,std::string>> required={
PAIRS
  };
  std::vector<std::string> allowed={EXTRAS};
  for(const auto& p:required){const char* v=getenv(p.first.c_str());
    if(!v || std::string(v)!=p.second)throw std::runtime_error("O2 frozen flag mismatch: "+p.first);
    allowed.push_back(p.first);}
  extern char** environ;
  for(char** e=environ;*e;++e){std::string entry=*e,key=entry.substr(0,entry.find('='));
    if(key.rfind("OCA_",0)==0 && std::find(allowed.begin(),allowed.end(),key)==allowed.end())
      throw std::runtime_error("O2 unsupported environment path: "+key);}
}
'''.replace('PAIRS', pairs).replace('EXTRAS', ','.join(json.dumps(x) for x in extras))
    anchor = 'template <int CD>\nRunLog SolveMFreeShiftedCG('
    source(anchor, '#include "attempt_trace.h"\n#include "audit.cuh"\n'+guard+'\n'+anchor, 'configuration_instrumentation')
    anchor = '  auto TargetReached=[&](Scalar objective,int outer){'
    source(anchor, anchor+'\n    if(o2_stage_host<1.)return false;', 'target_original_stage_only')
    anchor = '  if(getenv("OCA_PCG"))pcg=std::make_unique<PrismPcg>(ncam);'
    source(anchor, anchor+'''
  const bool o2_on=getenv("OCA_O2") && atoi(getenv("OCA_O2"))!=0;
  if(o2_on)O2ValidateEnvironment();
  std::unique_ptr<StcgAttemptTrace> attempt_trace;
  if(const char* path=getenv("OCA_STCG_ATTEMPTS"))attempt_trace=std::make_unique<StcgAttemptTrace>(path);
  long o2_backtrack_base=0;
''', 'configuration_instrumentation')
    anchor = '  RobustUpdateScale();   // the initial cost below already needs a valid scale'
    source(anchor, '''  if(o2_on && (CD!=9 || shared_intr || mf_fp32 || rk || k2mask!=0 || !use_equil ||
      intr_damp!=1 || lam0!=.1 || func_tolerance!=0 || max_consecutive_failures!=0 || fast_opening))
    throw std::runtime_error("O2 requires the frozen unshared CD9 SIMPLE_RADIAL Eta2 CLI");
  O2Runtime o2_runtime(o2_on,p,s,target_cost);
''' + anchor, 'stage_initialization')
    anchor = '  RunLog log; log.iters.push_back(0); log.costs.push_back(cost);\n  // OCA_LAM_FLOOR'
    source(anchor, '''  RunLog log; log.iters.push_back(0); log.costs.push_back(o2_on?o2_runtime.original_cost:cost);
  o2_runtime.Diagnostic(p,s,0,false,cost);
  // OCA_LAM_FLOOR''', 'original_score')
    # No opening changes may occur without the fixed single-shift guard already
    # enforced by native RLD checks, plus these CLI/environment checks.
    source('   const double numeric_prior_bnorm=prev_bnorm;',
           '   double numeric_prior_bnorm=prev_bnorm;', 'stage_numeric_history')
    anchor = '   if(BudgetExpired()){std::printf("BUDGET stop=before_attempt outer=%d seconds=%.9g\\n",k,max_seconds);break;}'
    source(anchor, anchor+'''
   if(o2_runtime.Due()){
     cost=o2_runtime.Transition(p,s,k,lam_cam,attr_R,numeric_floor);
     prev_bnorm=-1.;numeric_prior_bnorm=-1.;prev_cost=cost;ftol_streak=0;stuck=0;converged=false;
     last_rel=1.;backtrack_confirm=false;o2_backtrack_base=backtrack_rescues;
     rej_streak=0;lam_pre_streak=lam_cam;clean_streak=0;
     need_assembly=true;factor_cached=false;pf_obs_dirty=true;retries=0;
     rld.history_count=0;rld.previous_accepted=false;rld.previous_action=0;rld.previous_lambda=0;
     rld.history.fill(0);rld.previous_quad_alpha=0;rld.model_valid=false;rld.spectrum_valid=false;
     rld.initial_cost=cost;rld.current_cost=cost;rld.mark_outer=-1;
     o2_runtime.Diagnostic(p,s,k,false,cost);
     if(TargetReached(cost,k))break;
   }
   o2_runtime.Tick();
   StcgAttemptClock attempt_clock(attempt_trace.get(),k,retries,!need_assembly,&st.matvecs);
''', 'stage_transition')
    anchor = '    for(cg_it=0; cg_it<maxck; ++cg_it){\n      KvS(pv_,Ap_);'
    source(anchor, '    for(cg_it=0; cg_it<maxck; ++cg_it){\n      if(attempt_trace)++attempt_clock.row.pcg_iterations;\n      KvS(pv_,Ap_);', 'instrumentation')
    anchor = '      if(!(pAp>1e-14*pp)){\n        if(model_capture'
    source(anchor, '      if(!(pAp>1e-14*pp)){\n        if(attempt_trace)attempt_clock.row.cutoff=true;\n        if(model_capture', 'instrumentation')
    anchor = '        lam_cam=numeric_floor;prev_bnorm=numeric_prior_bnorm;need_assembly=false;factor_cached=false;'
    source(anchor, anchor+'\n        if(attempt_trace)attempt_clock.row.numeric_repair=true;', 'instrumentation')
    anchor = '    if(!accepted && retries<max_inner_retry){'
    source(anchor, '''    if(attempt_trace)attempt_clock.row.accepted=accepted;
    o2_runtime.Observe(accepted);
    o2_runtime.Diagnostic(p,s,k+1,accepted,cost);
    if(!accepted && retries<max_inner_retry && !o2_runtime.Due()){''', 'stage_attempts')
    anchor = '    log.iters.push_back(k+1); log.costs.push_back(cost);\n    CsvRow(k+1, (double)cost);\n    if(rld.enabled)'
    source(anchor, '''    const double original_logged=o2_on?o2_runtime.original_cost:(double)cost;
    log.iters.push_back(k+1); log.costs.push_back(original_logged);
    CsvRow(k+1, original_logged);
    if(rld.enabled)''', 'original_score')
    source('        k+1,(double)cost,(double)lam_cam,cg_it,(double)eta,best_sh,best_ck,alpha_win,',
           '        k+1,original_logged,(double)lam_cam,cg_it,(double)eta,best_sh,best_ck,alpha_win,', 'original_json_score')
    anchor = '    if(converged && backtrack_on && !backtrack_confirm && backtrack_rescues>0){'
    source(anchor, '''    if(converged && o2_runtime.Surrogate()){o2_runtime.Stop();converged=false;}
    if(converged && backtrack_on && !backtrack_confirm && backtrack_rescues>o2_backtrack_base){''', 'stage_stop')
    anchor = '  int cheir1=CountCheiralityViolations(p,s);\n  if(prof_score'
    source(anchor, '  o2_runtime.Finish();\n'+anchor, 'stage_accounting')
    anchor='    pf_obs_dirty=true;   // Bo/Cdiag just rebuilt'
    # Must run before KernelDampIntr9 modifies Hcc. The immediately preceding
    # conditional is unique in this solver section.
    start=files['prism_o2.cu'].index('RunLog SolveMFreeShiftedCG(')
    at=files['prism_o2.cu'].index(anchor,start)
    line_start=files['prism_o2.cu'].rfind('\n    if(r2acc) KernelDampIntr9',start,at)+1
    line_end=files['prism_o2.cu'].index('\n',line_start)
    old=files['prism_o2.cu'][line_start:line_end]
    # The same intrinsic damping line exists in other solvers, so include the
    # following unique dirty-cache comment for reversible identification.
    old += '\n'+anchor
    source(old, '    if(o2_on && getenv("OCA_O2_AUDIT"))O2AuditAssembly(p,s,o2_runtime,Hcc,Cdiag,Gp,Bo,bc,bp,fragment_o2slot);\n'+old,'tiny_correctness_audit')

    source('#include "attempt_trace.h"\n#include "audit.cuh"',
           '#include "attempt_trace.h"\n#include "audit.cuh"\n#include "wave_trace.h"','wave_instrumentation')
    anchor='  if(const char* path=getenv("OCA_STCG_ATTEMPTS"))attempt_trace=std::make_unique<StcgAttemptTrace>(path);'
    source(anchor,anchor+'''\n  std::unique_ptr<O2WaveTrace> wave_trace;
  if(const char* path=getenv("OCA_WAVE_TRACE"))wave_trace=std::make_unique<O2WaveTrace>(path);''','wave_instrumentation')
    anchor='   StcgAttemptClock attempt_clock(attempt_trace.get(),k,retries,!need_assembly,&st.matvecs);'
    source(anchor,anchor+'\n   O2WaveAttempt wave(wave_trace.get(),attempt_clock,o2_runtime,k,retries,n_accept,lam_cam,attr_R,numeric_floor,cost);','wave_instrumentation')
    anchor='    for(cg_it=0; cg_it<maxck; ++cg_it){\n      if(attempt_trace)++attempt_clock.row.pcg_iterations;'
    source(anchor,'''    if(wave_trace){wave.row.lambda=lam_cam;wave.row.tau=tau_eff;wave.row.eta=eta;}
    for(cg_it=0; cg_it<maxck; ++cg_it){
      if(attempt_trace || wave_trace)++attempt_clock.row.pcg_iterations;''','wave_instrumentation')
    for tail in ['cutoff=true;','numeric_repair=true;','accepted=accepted;']:
        source('if(attempt_trace)attempt_clock.row.'+tail,
               'if(attempt_trace || wave_trace)attempt_clock.row.'+tail,'wave_instrumentation')
    anchor='        attr_old_R=attr_R;'
    source(anchor,anchor+'\n        if(wave_trace){wave.row.raw_norm=attr_raw_norm;wave.row.observed=std::isfinite(attr_raw_norm);wave.row.radius_effective=attr_old_R;}','wave_instrumentation')
    anchor='      lm_prediction=model.prediction;lm_rho=have&&lm_prediction>0?(cost-best_cost)/lm_prediction:-1;'
    source(anchor,anchor+'\n      if(wave_trace)wave.row.rho=lm_rho;','wave_instrumentation')

    restored = files.copy()
    for name, old, new, _ in reversed(patches):
        assert restored[name].count(new) == 1, ('inverse', name, new[:80])
        restored[name] = restored[name].replace(new, old)
    assert restored == bases
    return files, patches


def main():
    ap = argparse.ArgumentParser();ap.add_argument('--check-only', action='store_true');args = ap.parse_args()
    files, patches = derive();b = P/'build';b.mkdir(exist_ok=True)
    for name, value in files.items(): (b/name).write_text(value)
    trace = C/'steihaug/attempt_trace.h'
    # Copy the EXACT common instrumentation, not a modified sibling.
    (b/'attempt_trace.h').write_bytes(trace.read_bytes())
    headers = {p.name: sha(p) for p in [P/'projection.h', P/'projection.cuh', P/'runtime.cuh', P/'audit.cuh', P/'wave_trace.h', b/'attempt_trace.h']}
    manifest = dict(frozen_source_sha256=sha(F/'source/prism_eta2.cu'),
                    source_manifest_sha256=sha(F/'source_manifest.json'),champion_sha256=sha(F/'champion.json'),
                    derived={name: sha(b/name) for name in files}, local_headers=headers,
                    protocol_sha256=sha(P/'PROTOCOL.md'), inverse_patch_source_and_header_parity=True,
                    substitutions=len(patches),substitution_kinds=[x[3] for x in patches],
                    flag='OCA_O2=1',default='off',status='source_only_not_validated')
    if not args.check_only:
        command = ['nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3',
                   '-I'+str(b),'-I'+str(P),'-I'+str(F/'source/headers'),str(b/'prism_o2.cu'),
                   '-o',str(b/'prism-o2'),'-lcublas','-lcusolver']
        env = os.environ.copy();env['TMPDIR'] = '/dev/shm'
        with (b/'build.log').open('w') as log:
            subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
        assert manifest['derived'] == {name: sha(b/name) for name in files}
        assert headers == {name: sha((b if name == 'attempt_trace.h' else P)/name) for name in headers}
        manifest.update(binary_sha256=sha(b/'prism-o2'),command=command,status='built_not_validated')
    (P/'build_manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':main()
