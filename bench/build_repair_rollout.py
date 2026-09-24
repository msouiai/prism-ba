#!/usr/bin/env python3
"""Build an isolated diagnostic replay/probe variant; never edit the solver default."""
import pathlib,subprocess,difflib
ROOT=pathlib.Path('/workspace/prism-repair-rollout')
GPU=pathlib.Path(__file__).resolve().parents[1]/'gpu'

def main():
    original=(ROOT/'source-before.cu').read_text();s=original
    def replace(old,new):
        nonlocal s
        assert s.count(old)==1,old[:100]
        s=s.replace(old,new)
    replace('  if(point_safeguard_mode && (!backtrack_on || CD!=9 || shared_intr || mf_fp32 || rk ||\n      point_trust_mode || full_model_rho || subspace_mode || backtrack_policy!=0 ||\n      getenv("OCA_REPLAY_LOAD") || getenv("OCA_REPLAY_SAVE")))',
        '  if(point_safeguard_mode && (!backtrack_on || CD!=9 || shared_intr || mf_fp32 || rk ||\n      point_trust_mode || full_model_rho || subspace_mode || backtrack_policy!=0))')
    replace('std::string replay_policy="PRISM_REPLAY_V1";', 'std::string replay_policy="PRISM_REPAIR_REPLAY_V2";\n  const bool repair_probe=getenv("OCA_REPLAY_REPAIR_PROBE") && atoi(getenv("OCA_REPLAY_REPAIR_PROBE"))!=0;\n  if(repair_probe && (!replay_load || point_safeguard_mode!=1 || L!=5))\n    throw std::runtime_error("repair probe requires a five-shift replay with point safeguard 1");')
    replace('"OCA_MULTI_RHS","OCA_DIAG_NORM","OCA_NSHIFTS","OCA_MENU_BACKTRACK"};',
        '"OCA_MULTI_RHS","OCA_DIAG_NORM","OCA_MENU_BACKTRACK",\n      "OCA_POINT_SAFEGUARD","OCA_COMPACT_FRAGMENTS","OCA_MAX_SECONDS","OCA_DEMAND_MENU","OCA_SWITCH_RESTART"};')
    replace('if(key.rfind("OCA_REPLAY_",0)==0 || key=="OCA_LEARN_LOG" || key=="OCA_BACKTRACK_REARM") continue;',
        'if(key.rfind("OCA_REPLAY_",0)==0 || key=="OCA_LEARN_LOG" || key=="OCA_BACKTRACK_REARM" || key=="OCA_NSHIFTS") continue;')
    replace('match(L);match(lam0);',
        'int saved_L=L;io.scalar(saved_L);\n    if(saved_L!=L && !(read && saved_L==1 && L==5))\n      throw std::runtime_error("only single-to-five menu intervention is supported");\n    match(lam0);')
    replace('io.scalar(tau_lam_off);io.scalar(tau_lam_floor_cur);io.scalar(last_win_sh);io.scalar(last_rel);',
        'io.scalar(tau_lam_off);io.scalar(tau_lam_floor_cur);io.scalar(last_win_sh);io.scalar(last_rel);\n    if(read && saved_L==1 && L==5 && last_win_sh==0)last_win_sh=2;')
    marker='    if(adaptive_menu){\n      if(backtrack_rescued) adaptive_policy.force=true;'
    probe='''    // Diagnostic intervention only at the first replayed outer. At fixed
    // new cameras, choose old/full point positions by complete track cost.
    // The full objective and Armijo slope must certify a strict improvement.
    if(repair_probe && k==replay_start && have && !backtrack_rescued){
      const auto probe_start=now();const Scalar ordinary=best_cost;
      CUDA_CHECK(cudaMemcpy(dfull,d_best,(size_t)n*sizeof(Scalar),cudaMemcpyDeviceToDevice));
      DoRetract(dfull,s_new);
      const auto frozen=point_safeguard->Choose(p,s,s_new,dfull,0);
      Scalar dc=0,dp=0;
      cublasDdot(blas,n_cf,bc,1,dfull,1,&dc);
      cublasDdot(blas,n_p,bp,1,dfull+n_cf,1,&dp);
      const Scalar slope=dc+dp;
      DoRetract(dfull,s_new);const Scalar candidate=ComputeCost(p,s_new,rk,rk_a2);
      ++backtrack_evals;++point_safeguard_evals;++point_safeguard_calls;
      point_safeguard_frozen+=frozen;
      const bool won=frozen && std::isfinite(candidate) && std::isfinite(slope) &&
        slope<0 && candidate<ordinary && candidate<=cost+(Scalar)1e-4*slope;
      if(won){best_cost=candidate;std::swap(d_best,dfull);
        backtrack_rescued=true;backtrack_alpha=1;++backtrack_rescues;++point_safeguard_wins;}
      const double elapsed=std::chrono::duration<double>(now()-probe_start).count();
      point_safeguard_seconds+=elapsed;
      std::printf("REPAIR_PROBE o=%d current=%.17g ordinary=%.17g candidate=%.17g slope=%.17g frozen=%llu won=%d seconds=%.9g\\n",
        k,(double)cost,(double)ordinary,(double)candidate,(double)slope,frozen,(int)won,elapsed);
    }
'''
    replace(marker,probe+marker)
    (ROOT/'source-rollout.cu').write_text(s)
    (ROOT/'diagnostic.patch').write_text(''.join(difflib.unified_diff(original.splitlines(True),s.splitlines(True),fromfile='source-before.cu',tofile='source-rollout.cu')))
    cmd=['/usr/local/cuda/bin/nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89',
         '-I'+str(GPU),str(ROOT/'source-rollout.cu'),'-o',str(ROOT/'prism-rollout'),'-lcublas','-lcusolver']
    with (ROOT/'build.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)

if __name__=='__main__':main()
