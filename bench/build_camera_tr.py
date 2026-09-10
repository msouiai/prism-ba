#!/usr/bin/env python3
"""Isolated bounded camera trust-region menu prototype."""
import pathlib,subprocess,difflib
ROOT=pathlib.Path('/workspace/prism-camera-tr');GPU=pathlib.Path(__file__).resolve().parents[1]/'gpu'
def main():
 original=(ROOT/'source-before.cu').read_text();s=original
 def edit(a,b):
  nonlocal s
  assert s.count(a)==1,a[:100]
  s=s.replace(a,b)
 edit('#include "full_step_model.cuh"','#include "full_step_model.cuh"\n#include "camera_tr_diagnostic.cuh"')
 edit('  const bool full_model_rho=[]()', '  const bool camera_tr=getenv("OCA_CAMERA_TR") && atoi(getenv("OCA_CAMERA_TR"))!=0;\n  std::unique_ptr<PrismCameraTR> tr;\n  if(camera_tr)tr=std::make_unique<PrismCameraTR>(n_c);\n  const bool full_model_rho=[]()')
 edit('  if(full_model_rho)full_model=', '  if(full_model_rho || camera_tr)full_model=')
 edit('  const int recycle_mode=getenv("OCA_KRYLOV_REUSE")?', '''  if(camera_tr && (CD!=9 || shared_intr || mf_fp32 || rk || block_eq || !use_equil ||
      L!=5 || demand_mode!=0 || full_model_rho || repair_damping_mode || point_trust_mode ||
      subspace_mode || backtrack_policy || point_safeguard_mode!=1 ||
      getenv("OCA_REPLAY_LOAD") || getenv("OCA_REPLAY_SAVE") || getenv("OCA_KRYLOV_REUSE") ||
      getenv("OCA_ADAPTIVE_MENU") || getenv("OCA_PROGRESSIVE_DEPTH") || getenv("OCA_MENU_COVERAGE") ||
      getenv("OCA_CAND_PRUNE") || getenv("OCA_POLY_CONG") || getenv("OCA_LAMBDA_HYSTERESIS") ||
      getenv("OCA_SCORE_STRIDE") || getenv("OCA_TAU_LAM_COND") || getenv("OCA_TAU_LAM_MAXOBS")))
    throw std::runtime_error("camera TR requires plain FP64 diagonal five-shift mode with point safeguard 1");
  const int recycle_mode=getenv("OCA_KRYLOV_REUSE")?''')
 edit('    tau_used = tau_eff;', '''    if(camera_tr){
      if(!need_assembly && !tr->entries.empty())tau_eff=tr->tau;
      else {tr->entries.clear();tr->tau=tau_eff;}
      tr->Reset();
    }
    const bool tr_reuse=camera_tr && !tr->entries.empty();
    tau_used = tau_eff;''')
 edit('    auto ScoreAll=[&](int depth){', '''    auto ScoreAll=[&](int depth){
      if(camera_tr){
        if(!(tr->radius>0)){
          double central=0;cublasDnrm2(blas,n_c,xs[L/2],1,&central);
          tr->radius=std::isfinite(central)&&central>0?central:1.;
        }
        for(int l=0;l<L;++l)tr->Add(xs[l],l,depth,bprime,blas,KvS);
        return;
      }''')
 edit('    bool projected_ok=false;', '''    bool projected_ok=false;
    if(tr_reuse){tr->Reconsider(blas);projected_ok=true;}''')
 edit('    // History resolves near-ties across per-shift best checkpoint candidates.', '''    if(camera_tr){
      if(!tr_reuse){
        // Explicit Cauchy candidate guarantees reduced-model descent when SPD.
        double bb=0,bSb=0;cublasDdot(blas,n_c,bprime,1,bprime,1,&bb);
        KvS(bprime,tr->ax);++tr->model_evals;
        cublasDdot(blas,n_c,bprime,1,tr->ax,1,&bSb);
        double a=bSb>0?bb/bSb:1.;
        CUDA_CHECK(cudaMemcpy(tr->work,bprime,n_c*sizeof(Scalar),cudaMemcpyDeviceToDevice));
        cublasDscal(blas,n_c,&a,tr->work,1);
        if(!(tr->radius>0))tr->radius=1.;
        tr->Add(tr->work,-1,0,bprime,blas,KvS);
      }
      if(tr->best_prediction>0)Score(tr->best,tr->best_sh,tr->best_depth);
    }
    // History resolves near-ties across per-shift best checkpoint candidates.''')
 edit('    if(have && use_alpha && (!rho_mode || alpha_rho)){','    if(have && use_alpha && (!rho_mode || alpha_rho) && !camera_tr){')
 edit('    // ---- accept / reject (existing rule) ----', '''    double tr_rho=-1,tr_norm=0,tr_prediction=0,tr_old_radius=camera_tr?tr->radius:0;
    if(camera_tr){
      if(have){
        auto model=full_model->Evaluate(p,s,d_best,k2mask);++full_model_calls;
        tr_prediction=model.prediction;
        MFTRUnscale<<<GridSize(n_c),256>>>(d_best,E,tr->work,n_c);
        cublasDnrm2(blas,n_c,tr->work,1,&tr_norm);
        if(tr_prediction>0)tr_rho=(cost-best_cost)/tr_prediction;
        have=prism_camera_tr::accept(cost-best_cost,tr_prediction,tr_norm,tr_old_radius);
      }
      tr->radius=prism_camera_tr::radius_after(tr_old_radius,tr_norm,tr_rho);
      if(!have && tr->radius>=tr_old_radius)tr->radius=std::max(1e-14,.25*tr_old_radius);
      std::printf("CAMERA_TR o=%d reuse=%d bank=%zu radius=%.17g norm=%.17g prediction=%.17g rho=%.17g accept=%d next_radius=%.17g tau=%.17g\\n",
        k,(int)tr_reuse,tr->entries.size(),tr_old_radius,tr_norm,tr_prediction,tr_rho,(int)have,tr->radius,(double)tau_eff);
    }
    // ---- accept / reject (existing rule) ----''')
 edit('      if(backtrack_rescued){\n        // The Schur-only model', '''      if(camera_tr){
        const double anchor=tr->best_sh>=0?shifts[tr->best_sh]:lam_cam;
        lam_cam=std::clamp(anchor*std::pow(tr_old_radius/tr->radius,2.),(double)lam_floor,1e8);
      }
      else if(backtrack_rescued){
        // The Schur-only model''')
 edit('      lam_cam*=(Scalar)esc; ++n_reject; ++rej_streak;','      if(!camera_tr)lam_cam*=(Scalar)esc; ++n_reject; ++rej_streak;')
 edit('  if(full_model_rho)std::printf("FULL_MODEL summary', '''  if(camera_tr)std::printf("CAMERA_TR summary reuses=%ld model_matvecs=%ld full_predictions=%ld radius=%.17g\\n",tr->reuses,tr->model_evals,full_model_calls,tr->radius);
  if(full_model_rho)std::printf("FULL_MODEL summary''')
 (ROOT/'source-tr.cu').write_text(s)
 (ROOT/'diagnostic.patch').write_text(''.join(difflib.unified_diff(original.splitlines(True),s.splitlines(True),fromfile='source-before.cu',tofile='source-tr.cu')))
 cmd=['/usr/local/cuda/bin/nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I'+str(GPU),str(ROOT/'source-tr.cu'),'-o',str(ROOT/'prism-tr'),'-lcublas','-lcusolver']
 with (ROOT/'build.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
if __name__=='__main__':main()
