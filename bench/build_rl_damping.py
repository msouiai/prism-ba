#!/usr/bin/env python3
"""Isolated guarded-LM damping intervention and accepted-boundary replay."""
import argparse, hashlib, json, pathlib, shutil, subprocess

BASE = pathlib.Path('/workspace/prism-model-followup/candidate')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--output',type=pathlib.Path,required=True)
    a=ap.parse_args(); m=json.loads((BASE/'manifest.json').read_text())
    assert sha(BASE/'source.cu')==m['source_sha256']
    assert all(sha(BASE/'headers'/k)==v for k,v in m['headers_sha256'].items())
    a.output.mkdir(parents=True,exist_ok=False)
    shutil.copytree(BASE/'headers',a.output/'headers')
    shutil.copyfile(pathlib.Path(__file__).parents[1]/'gpu/rl_damping.h',a.output/'headers/rl_damping.h')
    s=(BASE/'source.cu').read_text()
    def sub(old,new):
        nonlocal s
        assert s.count(old)==1,(old,s.count(old));s=s.replace(old,new)
    sub('#include <memory>','#include <memory>\n#include "rl_damping.h"')
    sub('  double numeric_floor=1e-16;', '  PrismRLDamping rld;\n  double numeric_floor=1e-16;')
    # New names avoid lifting the old unsupported-mode checks for legacy replay.
    sub('  const char* replay_save=getenv("OCA_REPLAY_SAVE");', '''  if(rld.enabled && (!classical_lm || !attr_radius || !attr_strict || !numeric_guard ||
      !attr_rescue || L!=1 || CD!=9 || shared_intr || mf_fp32 || rk || block_eq ||
      !pcg || pcg->reuse || pcg->schur || demand_mode || camera_tr || g_lp.on ||
      adaptive_menu || hyst_track || jit_on || fast_opening || ri_open || score_stride_env!=1))
    throw std::runtime_error("RLD requires frozen coupled guarded LM, fresh Hcc PCG, full L2 scoring");
  const char* replay_save=rld.enabled?getenv("OCA_RLD_SAVE"):getenv("OCA_REPLAY_SAVE");''')
    sub('  const char* replay_load=getenv("OCA_REPLAY_LOAD");',
        '  const char* replay_load=rld.enabled?getenv("OCA_RLD_LOAD"):getenv("OCA_REPLAY_LOAD");')
    sub('  const char* replay_at=getenv("OCA_REPLAY_AT");',
        '  const char* replay_at=rld.enabled?getenv("OCA_RLD_AT"):getenv("OCA_REPLAY_AT");')
    sub('  std::string replay_policy="PRISM_REPLAY_V1";',
        '  std::string replay_policy=rld.enabled?"PRISM_RLD_V1":"PRISM_REPLAY_V1";')
    sub('    const std::vector<std::string> allowed={','    std::vector<std::string> allowed={')
    sub('    extern char** environ;', '''    if(rld.enabled){
      const std::vector<std::string> extra={"OCA_CLASSICAL_LM","OCA_ATTR_RADIUS","OCA_ATTR_STRICT",
        "OCA_ATTR_RESCUE","OCA_SCHUR_NUMERIC_GUARD","OCA_COMPACT_FRAGMENTS","OCA_POINT_SAFEGUARD",
        "OCA_CAMERA_TR","OCA_CG_STOP","OCA_DEMAND_MENU","OCA_PCG","OCA_SWITCH_RESTART",
        "OCA_TR_RECURRENCE","OCA_BACKTRACK_REARM"};
      allowed.insert(allowed.end(),extra.begin(),extra.end());
    }
    extern char** environ;''')
    sub('      if(key.rfind("OCA_REPLAY_",0)==0 || key=="OCA_LEARN_LOG" || key=="OCA_BACKTRACK_REARM") continue;',
        '''      if(rld.enabled && (key.rfind("OCA_RLD_",0)==0 || key=="OCA_TARGET_COST" || key=="OCA_MAX_SECONDS"))continue;
      if(!rld.enabled && (key.rfind("OCA_REPLAY_",0)==0 || key=="OCA_LEARN_LOG" || key=="OCA_BACKTRACK_REARM")) continue;''')
    sub('    io.scalar(backtrack_trials);io.scalar(alpha_evals);io.scalar(st);io.scalar(learn_att_id);', '''    io.scalar(backtrack_trials);io.scalar(alpha_evals);io.scalar(st);io.scalar(learn_att_id);
    if(rld.enabled){
      io.scalar(attr_R);io.scalar(lm_nu);io.scalar(numeric_floor);io.scalar(numeric_rebuilds);
      io.scalar(pcg->last_depth);io.scalar(pcg->last_outer);
      io.scalar(rld.history);io.scalar(rld.history_count);io.scalar(rld.previous_accepted);
      io.scalar(rld.previous_action);io.scalar(rld.previous_lambda);
    }''')
    sub('    if(const char* steps=getenv("OCA_REPLAY_STEPS")) max_iter=replay_start+std::max(1,atoi(steps));', '''    if(const char* steps=getenv(rld.enabled?"OCA_RLD_STEPS":"OCA_REPLAY_STEPS")) max_iter=replay_start+std::max(1,atoi(steps));
    if(rld.enabled)rld.fork_outer=replay_start;''')
    sub('     if(const char* steps=getenv("OCA_REPLAY_STEPS")) max_iter=k+std::max(1,atoi(steps));',
        '     if(const char* steps=getenv(rld.enabled?"OCA_RLD_STEPS":"OCA_REPLAY_STEPS")) max_iter=k+std::max(1,atoi(steps));')
    sub('   if(demand_on){\n     if(backtrack_confirm)', '''   if(rld.enabled && need_assembly){
     rld.Begin(st.matvecs,n_reject,numeric_rebuilds,cost);
     if(rld.previous_accepted){
       const double baseline=lam_cam;
       const int action=rld.Action(k);
       if(action)lam_cam=std::clamp(baseline*std::pow(10.,action),numeric_floor,1e16);
       rld.previous_action=action;
       rld.Decision(k,baseline,lam_cam,attr_R,numeric_floor);
     }
   }
   if(demand_on){
     if(backtrack_confirm)''')
    sub('    CsvRow(k+1, (double)cost);\n    if(TargetReached(cost,k+1)) break;', '''    CsvRow(k+1, (double)cost);
    if(rld.enabled)rld.End(k+1,accepted,learn_lam_att,lam_cam,numeric_floor,lm_rho,lm_prediction,
      attr_raw_norm,attr_old_R,nb,eta,cg_it,maxck,st.matvecs,n_reject,numeric_rebuilds,cost,nobs,ncam,npt);
    if(TargetReached(cost,k+1)) break;''')
    # Populate legacy LM telemetry if used outside the strict RLD replay mode.
    sub('    // OCA_LEARN_LOG: one record per attempt, after the accept/reject decision', '''    if(learn_f){
      if(classical_lm){learn_rho=lm_rho;learn_predfull=lm_prediction;
        learn_fac=learn_lam_att>0?(double)lam_cam/learn_lam_att:0.;}
      if(!std::isfinite(learn_rho))learn_rho=0.;
      if(!std::isfinite(learn_fac))learn_fac=0.;
    }
    // OCA_LEARN_LOG: one record per attempt, after the accept/reject decision''')
    (a.output/'source.cu').write_text(s)
    cmd=['nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3',
         '-I'+str(a.output/'headers'),str(a.output/'source.cu'),'-o',str(a.output/'prism-tr'),'-lcublas','-lcusolver']
    with (a.output/'build.log').open('x') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
    (a.output/'manifest.json').write_text(json.dumps(dict(command=cmd,parent=m,
        source_sha256=sha(a.output/'source.cu'),binary_sha256=sha(a.output/'prism-tr'),
        headers_sha256={p.name:sha(p) for p in (a.output/'headers').iterdir() if p.is_file()}),indent=2)+'\n')
    print(a.output/'prism-tr',flush=True)

if __name__=='__main__':main()
