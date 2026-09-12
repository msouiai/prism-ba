#!/usr/bin/env python3
"""Derive the D9 lifted robust opening from the validated B6v7 source."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess

P = Path(__file__).resolve().parent
W5 = P.parent / "eta2_wave5"
F = P.parent / "eta2_champion"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def parent_module():
    spec = importlib.util.spec_from_file_location("build_b6v7", W5 / "build_b6v7.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def derive():
    source, parent_count = parent_module().derive()
    original = source
    changes = []

    def patch(before, after, count=1):
        nonlocal source
        assert source.count(before) == count, (before[:140], source.count(before), count)
        source = source.replace(before, after)
        changes.append((before, after, count))

    lift = str(P / "lifted_robust.cuh")
    full = str(P / "lifted_full_model.cuh")
    patch('#include "cg_tr_projection.cuh"',
          '#include "cg_tr_projection.cuh"\n#include "' + lift + '"')
    lifted_cost_wrapper = r'''inline double W6LiftedCost(const DeviceProblem& p, const DeviceState& s,
                           const double* weights, double tau2) {
  static double* d_cost = nullptr;
  if (!d_cost) CUDA_CHECK(cudaMalloc(&d_cost, sizeof(double)));
  CUDA_CHECK(cudaMemset(d_cost, 0, sizeof(double)));
  W6LiftedCostKernel<<<GridSize(p.nobs),256>>>(p.cam_idx,p.pt_idx,p.uv,
      s.R,s.t,s.X,INTR_F(p,s),INTR_K1(p,s),INTR_K2(p,s),weights,p.nobs,
      tau2,d_cost);
  double result;
  CUDA_CHECK(cudaMemcpy(&result,d_cost,sizeof(double),cudaMemcpyDeviceToHost));
  return result;
}
'''
    patch('#include "full_step_model.cuh"', lifted_cost_wrapper + '#include "' + full + '"')

    patch(
        '''    int rk=0,Scalar rk_a2=0.0){''',
        '''    int rk=0,Scalar rk_a2=0.0,
    const Scalar* lift_weights=nullptr,Scalar lift_tau2=0.0,Scalar lift_lambda=0.0){''')

    old_irls = '''  // IRLS: sqrt-weight the residual AND the Jacobian rows, exactly as the CPU
  // port does (and after r2acc, which accumulates the geometric radius and is
  // independent of the weighting). Everything downstream -- Hcc, b, the point
  // block, the fragments -- is then the weighted GN system.
  if(rk){
    const Scalar sw = sqrt(OcaRobustW(rk, rk_a2, rx*rx + ry*ry));
    rx *= sw; ry *= sw;
    for(int i=0;i<CD+3;++i){ gx[i] *= sw; gy[i] *= sw; }
  }'''
    new_irls = '''  // D9: eliminate each persistent confidence increment exactly.  W6LiftRows
  // produces a square-root representation of the resulting 2x2 metric and a
  // residual whose normal-equation RHS is the eliminated lifted RHS.
  if(lift_weights){
    const Scalar raw_rx=rx,raw_ry=ry;
    W6LiftRows<CD+3>(raw_rx,raw_ry,lift_weights[o],lift_tau2,lift_lambda,gx,gy,rx,ry);
  } else if(rk){
    const Scalar sw = sqrt(OcaRobustW(rk, rk_a2, rx*rx + ry*ry));
    rx *= sw; ry *= sw;
    for(int i=0;i<CD+3;++i){ gx[i] *= sw; gy[i] *= sw; }
  }'''
    patch(old_irls, new_irls)

    patch(
        '''  Scalar rk_a2 = rk_scale2;''',
        '''  Scalar rk_a2 = rk_scale2;
  const bool lift_enabled=[](){const char* e=getenv("OCA_W6_LIFTED");return e&&std::atoi(e)!=0;}();
  const int lift_accept_limit=3;
  bool lift_active=lift_enabled;
  Scalar *lift_weights=nullptr,*lift_candidate=nullptr,*lift_best=nullptr;
  Scalar lift_tau2=0.0;
  long lift_retry_rebuilds=0;
  if(lift_enabled){
    if(!classical_lm||!attr_radius||!attr_strict||L!=1||rk!=0||shared_intr||CD!=9||mf_fp32||getenv("OCA_ALPHA_RHO")||
       demand_mode||batch_cost||batch_check||getenv("OCA_REPLAY_LOAD")||getenv("OCA_REPLAY_SAVE")||
       getenv("OCA_RI_OPEN")||getenv("OCA_RI_AT"))
      throw std::runtime_error("D9 lifted opening requires champion-like unshared CD9 single-shift full-scoring L2 path");
    M((void**)&lift_weights,(size_t)nobs*sizeof(Scalar));
    M((void**)&lift_candidate,(size_t)nobs*sizeof(Scalar));
    M((void**)&lift_best,(size_t)nobs*sizeof(Scalar));
    W6Fill<<<GridSize(nobs),256>>>(lift_weights,nobs,1.0);
    Scalar* sq=nullptr;M((void**)&sq,(size_t)nobs*sizeof(Scalar));
    KernelResidSq<<<GridSize(nobs),256>>>(p.cam_idx,p.pt_idx,p.uv,s.R,s.t,s.X,
      INTR_F(p,s),INTR_K1(p,s),INTR_K2(p,s),nobs,sq);
    std::vector<Scalar> host_sq(nobs);
    CUDA_CHECK(cudaMemcpy(host_sq.data(),sq,(size_t)nobs*sizeof(Scalar),cudaMemcpyDeviceToHost));
    cudaFree(sq);
    std::nth_element(host_sq.begin(),host_sq.begin()+host_sq.size()/2,host_sq.end());
    lift_tau2=std::max((Scalar)4.0*host_sq[host_sq.size()/2],(Scalar)1e-12);
    std::printf("W6_LIFT_INIT accepts=%d tau2=%.17g median_r2=%.17g objective=smooth-truncated-quadratic\\n",
      lift_accept_limit,(double)lift_tau2,(double)(lift_tau2/4.0));
  }''')

    patch(
        '''  Scalar cost=ComputeCost(p,s,rk,rk_a2);''',
        '''  Scalar cost=lift_active?W6LiftedCost(p,s,lift_weights,lift_tau2):ComputeCost(p,s,rk,rk_a2);''')

    # The lifted metric depends on lambda.  Set the prediction path every
    # attempt after any replay/demand action has selected the attempt lambda.
    patch(
        '''   if(need_assembly){
    if (g_bal_ptr''',
        '''   W6SetLift(lift_active,lift_weights,lift_tau2,lam_cam);
   if(need_assembly){
    if (g_bal_ptr''')

    old_main_assembly = '''    if(mf_fp32) MFAssemble<CD,float><<<GridSize(nobs),256>>>(p.cam_idx,p.pt_idx,p.uv,s.R,s.t,s.X,
        INTR_F(p,s),INTR_K1(p,s),INTR_K2(p,s),
        fragment_o2slot,p.obs2cslot,nobs,Hcc,Cdiag,Gp32,Gc32,Bo32,bc,bp,k2mask,r2acc,obscnt,rk,rk_a2);
    else        MFAssemble<CD,Fragment><<<GridSize(nobs),256>>>(p.cam_idx,p.pt_idx,p.uv,s.R,s.t,s.X,
        INTR_F(p,s),INTR_K1(p,s),INTR_K2(p,s),
        fragment_o2slot,p.obs2cslot,nobs,Hcc,Cdiag,Gp,Gc,Bo,bc,bp,k2mask,r2acc,obscnt,rk,rk_a2);
    if(r2acc) KernelDampIntr9'''
    new_main_assembly = '''    if(mf_fp32) MFAssemble<CD,float><<<GridSize(nobs),256>>>(p.cam_idx,p.pt_idx,p.uv,s.R,s.t,s.X,
        INTR_F(p,s),INTR_K1(p,s),INTR_K2(p,s),
        fragment_o2slot,p.obs2cslot,nobs,Hcc,Cdiag,Gp32,Gc32,Bo32,bc,bp,k2mask,r2acc,obscnt,rk,rk_a2,
        lift_active?lift_weights:nullptr,lift_tau2,lam_cam);
    else        MFAssemble<CD,Fragment><<<GridSize(nobs),256>>>(p.cam_idx,p.pt_idx,p.uv,s.R,s.t,s.X,
        INTR_F(p,s),INTR_K1(p,s),INTR_K2(p,s),
        fragment_o2slot,p.obs2cslot,nobs,Hcc,Cdiag,Gp,Gc,Bo,bc,bp,k2mask,r2acc,obscnt,rk,rk_a2,
        lift_active?lift_weights:nullptr,lift_tau2,lam_cam);
    if(r2acc) KernelDampIntr9'''
    patch(old_main_assembly, new_main_assembly)

    patch(
        '''      _ps(ts_retract,[&]{ DoRetract(dfull,s_new); });
      _ps(ts_cost,[&]{ c = score_stride>1 ? ComputeCostStride(p,s_new,score_stride,rk,rk_a2)
                                          : ComputeCost(p,s_new,rk,rk_a2); });''',
        '''      _ps(ts_retract,[&]{ DoRetract(dfull,s_new); });
      if(lift_active)
        W6ProposeWeights<CD><<<GridSize(nobs),256>>>(p.cam_idx,p.pt_idx,p.uv,s.R,s.t,s.X,
          INTR_F(p,s),INTR_K1(p,s),INTR_K2(p,s),dfull,lift_weights,nobs,ncam,k2mask,
          lift_tau2,lam_cam,lift_candidate);
      _ps(ts_cost,[&]{ c = lift_active ? W6LiftedCost(p,s_new,lift_candidate,lift_tau2)
                              : (score_stride>1 ? ComputeCostStride(p,s_new,score_stride,rk,rk_a2)
                                                : ComputeCost(p,s_new,rk,rk_a2)); });''')

    patch(
        '''        std::swap(d_best,dfull); }
    };
    auto Score=[''',
        '''        std::swap(d_best,dfull);
        if(lift_active)std::swap(lift_best,lift_candidate); }
    };
    auto Score=[''')

    patch(
        '''      DoRetract(d_best,s_new); CopyState(s,s_new,ncam,npt);
      cost=best_cost;''',
        '''      DoRetract(d_best,s_new); CopyState(s,s_new,ncam,npt);
      if(lift_active)CUDA_CHECK(cudaMemcpy(lift_weights,lift_best,(size_t)nobs*sizeof(Scalar),cudaMemcpyDeviceToDevice));
      cost=best_cost;''')

    # Close the opening immediately after the third accepted state, before any
    # stopping test can interpret a change of objective as convergence.
    patch(
        '''    if(learn_f){
      if(classical_lm){learn_rho=lm_rho;learn_predfull=lm_prediction;''',
        '''    if(lift_active && accepted && n_accept>=lift_accept_limit){
      std::vector<Scalar> hw(nobs);CUDA_CHECK(cudaMemcpy(hw.data(),lift_weights,(size_t)nobs*sizeof(Scalar),cudaMemcpyDeviceToHost));
      std::sort(hw.begin(),hw.end());
      long down50=std::count_if(hw.begin(),hw.end(),[](Scalar q){return std::abs(q)<0.5;});
      const Scalar lifted_cost=cost;
      cost=ComputeCost(p,s,0,0);best_cost=cost;lift_active=false;
      W6SetLift(false,nullptr,0,0);prev_cost=cost;last_rel=1;ftol_streak=0;stuck=0;converged=false;
      need_assembly=true;factor_cached=false;pf_obs_dirty=true;
      std::printf("W6_LIFT_HANDOFF accepts=%d lifted=%.17g l2=%.17g w_min=%.17g w_p10=%.17g w_med=%.17g w_p90=%.17g w_max=%.17g below_half=%ld retry_rebuilds=%ld\\n",
        n_accept,(double)lifted_cost,(double)cost,(double)hw.front(),(double)hw[hw.size()/10],
        (double)hw[hw.size()/2],(double)hw[(9*hw.size())/10],(double)hw.back(),down50,lift_retry_rebuilds);
    }
    if(learn_f){
      if(classical_lm){learn_rho=lm_rho;learn_predfull=lm_prediction;''')

    patch(
        '''    if(!accepted && retries<max_inner_retry){
      ++retries; need_assembly=false;
      if(verbose)
        std::printf("  MFCG it %3d  retry %d/%d  lam=%.3e tau_eff=%.3e  (assembly reused)\\n",
                    k+1,retries,max_inner_retry,(double)lam_cam,(double)tau_eff);''',
        '''    if(!accepted && retries<max_inner_retry){
      ++retries; need_assembly=lift_active;
      if(lift_active){factor_cached=false;pf_obs_dirty=true;++lift_retry_rebuilds;}
      if(verbose)
        std::printf("  MFCG it %3d  retry %d/%d  lam=%.3e tau_eff=%.3e  (%s)\\n",
                    k+1,retries,max_inner_retry,(double)lam_cam,(double)tau_eff,
                    lift_active?"lifted assembly rebuilt":"assembly reused");''')

    patch(
        '''        lam_cam=numeric_floor;prev_bnorm=numeric_prior_bnorm;need_assembly=false;factor_cached=false;
        continue;''',
        '''        lam_cam=numeric_floor;prev_bnorm=numeric_prior_bnorm;need_assembly=lift_active;factor_cached=false;
        if(lift_active){pf_obs_dirty=true;++lift_retry_rebuilds;}
        continue;''')

    # The CSV and RunLog are always the scored L2 objective, including the
    # first two lifted accepts.  Target certification waits for handoff.
    patch(
        '''    retries=0; need_assembly=true;
    log.iters.push_back(k+1); log.costs.push_back(cost);
    CsvRow(k+1, (double)cost);''',
        '''    retries=0; need_assembly=true;
    const Scalar reported_cost=lift_active?ComputeCost(p,s,0,0):cost;
    log.iters.push_back(k+1); log.costs.push_back(reported_cost);
    CsvRow(k+1, (double)reported_cost);''',
        count=1)
    patch('''    if(TargetReached(cost,k+1)) break;''',
          '''    if(!lift_active && TargetReached(cost,k+1)) break;''', count=1)

    # A diagnostic cap before three accepts must still return an L2 endpoint.
    patch(
        '''  int cheir1=CountCheiralityViolations(p,s);''',
        '''  if(lift_enabled && lift_active){
    cost=ComputeCost(p,s,0,0);if(!log.costs.empty())log.costs.back()=cost;
    W6SetLift(false,nullptr,0,0);
    std::printf("W6_LIFT_INCOMPLETE accepts=%d l2=%.17g retry_rebuilds=%ld\\n",n_accept,(double)cost,lift_retry_rebuilds);
  }
  int cheir1=CountCheiralityViolations(p,s);''')

    patch(
        '''  cudaFree(hyst_steps);cudaFree(dfull);cudaFree(d_best);cudaFree(r_);cudaFree(pv_);cudaFree(Ap_);cudaFree(okf);''',
        '''  cudaFree(lift_weights);cudaFree(lift_candidate);cudaFree(lift_best);
  cudaFree(hyst_steps);cudaFree(dfull);cudaFree(d_best);cudaFree(r_);cudaFree(pv_);cudaFree(Ap_);cudaFree(okf);''')

    restored = source
    for before, after, count in reversed(changes):
        assert restored.count(after) == count, (after[:140], restored.count(after), count)
        restored = restored.replace(after, before)
    assert restored == original
    return source, parent_count + len(changes)


def main():
    subprocess.run(["python3", str(F / "build.py"), "--check-only"], check=True)
    build = P / "build"
    build.mkdir(exist_ok=True)
    src = build / "lifted.cu"
    binary = build / "prism-lifted"
    source, count = derive()
    src.write_text(source)
    cmd = ["nvcc", "-O3", "-DNDEBUG", "-std=c++17", "-arch=sm_89",
           "-I/usr/include/eigen3", "-I" + str(F / "source" / "headers"),
           "-I" + str(W5), str(src), "-o", str(binary), "-lcublas", "-lcusolver"]
    with (build / "lifted-build.log").open("w") as log:
        subprocess.run(cmd, env=dict(os.environ, TMPDIR="/dev/shm"), stdout=log,
                       stderr=subprocess.STDOUT, check=True)
    manifest = {
        "command": cmd,
        "source_sha256": sha(src),
        "binary_sha256": sha(binary),
        "frozen_source_sha256": sha(F / "source" / "prism_eta2.cu"),
        "champion_sha256": sha(F / "champion.json"),
        "b6v7_binary_sha256": sha(W5 / "build" / "prism-b6v7"),
        "reversible_patch_count": count,
        "sources": {str(q): sha(q) for q in
                    [P / "build_lifted.py", P / "lifted_robust.cuh",
                     P / "lifted_full_model.cuh", P / "D9_IMPLEMENTATION_AMENDMENT.md",
                     W5 / "build_b6v7.py"]},
        "protocol_sha256": sha(P / "D9_LIFTED_ROBUST_PROTOCOL.md"),
    }
    (P / "d9-lifted-build-manifest.json").write_text(json.dumps(manifest, indent=2)+"\n")
    print("BUILT D9", manifest["binary_sha256"])


if __name__ == "__main__":
    main()
