#!/usr/bin/env python3
"""Build the preregistered B2 FP32-correction/FP64-residual overlay."""
from pathlib import Path
import hashlib, json, os, subprocess

P=Path(__file__).resolve().parent
F=P.parent/"eta2_champion"
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def derive():
    original=source=(F/"source"/"prism_eta2.cu").read_text();changes=[]
    def patch(before,after,count=1):
        nonlocal source
        assert source.count(before)==count,(before[:140],source.count(before),count)
        source=source.replace(before,after);changes.append((before,after,count))

    patch('#include "point_prep_candidate.cuh"',
          '#include "point_prep_candidate.cuh"\n#include "sqrt_schur.cuh"\n#include "mixed_ir.cuh"')
    patch('  Fragment *Gp=nullptr,*Gc=nullptr,*Bo=nullptr;',r'''  Fragment *Gp=nullptr,*Gc=nullptr,*Bo=nullptr;
  const bool w5_ir=[](){const char* e=getenv("OCA_W5_IR");return e&&atoi(e)!=0;}();
  Fragment *w5_ir_J=nullptr;float *w5_ir_Rf=nullptr,*w5_ir_B=nullptr,*w5_ir_x=nullptr,
    *w5_ir_r=nullptr,*w5_ir_p=nullptr,*w5_ir_Ap=nullptr,*w5_ir_z=nullptr,*w5_ir_raw=nullptr,
    *w5_ir_tacc=nullptr,*w5_ir_u=nullptr;
  Scalar *w5_ir_R0=nullptr,*w5_ir_Rd=nullptr,*w5_ir_xd=nullptr,*w5_ir_dd=nullptr,
    *w5_ir_rd=nullptr,*w5_ir_Axd=nullptr;
  bool w5_ir_obs_dirty=true;long w5_ir_attempts=0,w5_ir_sweeps=0,w5_ir_fallbacks=0,
    w5_ir_nonmonotone=0,w5_ir_low_iters=0;''')
    patch(r'''  if(compact_mode<0 || compact_mode>2)
    throw std::runtime_error("OCA_COMPACT_FRAGMENTS must be 0, 1, or 2");''',r'''  if(compact_mode<0 || compact_mode>2)
    throw std::runtime_error("OCA_COMPACT_FRAGMENTS must be 0, 1, or 2");
  if(w5_ir && (CD!=9 || compact_mode!=2 || mf_fp32 || shared_intr || rk || !classical_lm ||
      !use_equil || !pcg || pcg->schur || k2mask!=0.0 || block_eq || getenv("OCA_JIT_J") ||
      getenv("OCA_RHS_DIAG_CAMERA") || getenv("OCA_SCORE_STRIDE") || getenv("OCA_TAU_LAM_COND") ||
      getenv("OCA_TAU_LAM_MAXOBS") || getenv("OCA_RI_OPEN")))
    throw std::runtime_error("wave5 iterative refinement requires frozen single-shift Eta2");''')
    patch(r'''  static const bool tau_split = [](){ const char* e=getenv("OCA_TAU_SPLIT");
    return e ? atoi(e)!=0 : true; }();''',r'''  static const bool tau_split = [](){ const char* e=getenv("OCA_TAU_SPLIT");
    return e ? atoi(e)!=0 : true; }();
  if(w5_ir && !tau_split)throw std::runtime_error("wave5 iterative refinement requires split point factors");''')
    patch(r'''  if(CD==9&&intr_damp>0.0){ M((void**)&r2acc,ncam*sizeof(Scalar)); M((void**)&obscnt,ncam*sizeof(Scalar)); }''',r'''  if(CD==9&&intr_damp>0.0){ M((void**)&r2acc,ncam*sizeof(Scalar)); M((void**)&obscnt,ncam*sizeof(Scalar)); }
  if(w5_ir){
    M((void**)&w5_ir_J,(size_t)W5_SQRT_VALUES*nobs*sizeof(Fragment));
    M((void**)&w5_ir_Rf,6ul*npt*sizeof(float));M((void**)&w5_ir_B,81ul*ncam*sizeof(float));
    for(float** q:{&w5_ir_x,&w5_ir_r,&w5_ir_p,&w5_ir_Ap,&w5_ir_z,&w5_ir_raw})M((void**)q,(size_t)n_c*sizeof(float));
    M((void**)&w5_ir_tacc,(size_t)n_p*sizeof(float));M((void**)&w5_ir_u,(size_t)n_p*sizeof(float));
    M((void**)&w5_ir_R0,6ul*npt*sizeof(Scalar));M((void**)&w5_ir_Rd,6ul*npt*sizeof(Scalar));
    for(Scalar** q:{&w5_ir_xd,&w5_ir_dd,&w5_ir_rd,&w5_ir_Axd})M((void**)q,(size_t)n_c*sizeof(Scalar));
    std::printf("  [w5-ir] active low_jacobian_values=%d low_arithmetic=fp32 residual=fp64 max_sweeps=2\n",W5_SQRT_VALUES);
  }''')
    patch('  int L = nshifts_env > 0 ? nshifts_env : n_shifts;',r'''  int L = nshifts_env > 0 ? nshifts_env : n_shifts;
  if(w5_ir && L!=1)throw std::runtime_error("wave5 iterative refinement is registered for one shift");''')
    patch(r'''    if(r2acc) KernelDampIntr9<<<GridSize(ncam),256>>>(Hcc,INTR_F(p,s),r2acc,obscnt,ncam,intr_damp,k2mask);
    pf_obs_dirty=true;   // Bo/Cdiag just rebuilt''',r'''    if(r2acc) KernelDampIntr9<<<GridSize(ncam),256>>>(Hcc,INTR_F(p,s),r2acc,obscnt,ncam,intr_damp,k2mask);
    if(w5_ir)W5StoreJacobian9<Fragment><<<GridSize(nobs),256>>>(p.cam_idx,p.pt_idx,p.uv,s.R,s.t,s.X,
        INTR_F(p,s),INTR_K1(p,s),INTR_K2(p,s),p.obs2cslot,nobs,w5_ir_J,k2mask,rk,rk_a2);
    pf_obs_dirty=true;w5_ir_obs_dirty=true;   // observation factors just rebuilt''')
    patch(r'''    else if(mf_fp32) MFPointFactor<float><<<GridSize(npt),256>>>(Bo32,Cdiag,p.point_obs_offsets,p.point_obs_list,tau_eff,npt,Rf,okf);
    else        MFPointFactor<Fragment><<<GridSize(npt),256>>>(Bo,Cdiag,p.point_obs_offsets,p.point_obs_list,tau_eff,npt,Rf,okf);
    // b' = b_c - H_cp V^-1 b_p''',r'''    else if(mf_fp32) MFPointFactor<float><<<GridSize(npt),256>>>(Bo32,Cdiag,p.point_obs_offsets,p.point_obs_list,tau_eff,npt,Rf,okf);
    else        MFPointFactor<Fragment><<<GridSize(npt),256>>>(Bo,Cdiag,p.point_obs_offsets,p.point_obs_list,tau_eff,npt,Rf,okf);
    if(w5_ir){
      if(w5_ir_obs_dirty){MFPointFactorObsSqrt9<Fragment><<<GridSize(npt),256>>>(w5_ir_J,p.obs2cslot,p.point_obs_offsets,p.point_obs_list,npt,nobs,w5_ir_R0,nullptr);w5_ir_obs_dirty=false;}
      MFPointFactorTau<<<GridSize(npt),256>>>(Cdiag,w5_ir_R0,tau_eff,npt,w5_ir_Rd,okf);
      W5CastD2F<<<GridSize(6*npt),256>>>(w5_ir_Rd,w5_ir_Rf,6*npt);
    }
    // b' = b_c - H_cp V^-1 b_p''')
    patch(r'''    auto KvS=[&](const Scalar* vin,Scalar* vout){
      if(!use_equil){ Kv(vin,vout); return; }''',r'''    auto KvS=[&](const Scalar* vin,Scalar* vout){
      if(!use_equil){ Kv(vin,vout); return; }''')
    # Add the low-precision shifted operator after the high bare-operator lambda.
    anchor=r'''      MFScaleVec<<<GridSize(n_c),256>>>(vout,E,n_c);
    };
    if(poly_on){'''
    replacement=r'''      MFScaleVec<<<GridSize(n_c),256>>>(vout,E,n_c);
    };
    auto W5LowKv=[&](const float* vin,float* vout,Scalar shift){
      W5ScaleInputF<<<GridSize(n_c),256>>>(vin,E,n_c,w5_ir_raw);
      CUDA_CHECK(cudaMemset(w5_ir_tacc,0,(size_t)n_p*sizeof(float)));
      W5SqrtPass1F<<<GridSize(nobs),256>>>(w5_ir_J,fragment_cams,fragment_points,w5_ir_raw,nobs,w5_ir_tacc);
      W5VinvF<<<GridSize(npt),256>>>(w5_ir_Rf,w5_ir_tacc,npt,w5_ir_u);
      W5SqrtPass2F<<<ncam,128>>>(w5_ir_J,p.mf_cspt,p.mf_coff,w5_ir_u,w5_ir_raw,nobs,
          INTR_F(p,s),r2acc,obscnt,intr_damp,k2mask,vout);
      W5ScaleShiftF<<<GridSize(n_c),256>>>(vout,E,vin,(float)shift,n_c);++st.matvecs;
    };
    if(poly_on){'''
    patch(anchor,replacement)

    # Run refinement before the frozen PCG block.  A failed high-residual gate
    # leaves projected_ok false and falls through to the untouched solver.
    anchor=r'''    if(!projected_ok){
    if(recycle_mode){'''
    replacement=r'''    if(!projected_ok && w5_ir){
      if(prof){cudaDeviceSynchronize();t0=now();}
      ++w5_ir_attempts;W5BuildPcgF<<<GridSize(ncam),256>>>(Hcc,E,shifts[0],ncam,w5_ir_B);
      auto LowSolve=[&](const Scalar* rhs,Scalar* sol,Scalar tol)->int{
        W5CastD2F<<<GridSize(n_c),256>>>(rhs,w5_ir_r,n_c);CUDA_CHECK(cudaMemset(w5_ir_x,0,(size_t)n_c*sizeof(float)));
        CUDA_CHECK(cudaMemcpy(w5_ir_p,w5_ir_r,(size_t)n_c*sizeof(float),cudaMemcpyDeviceToDevice));
        W5ApplyPcgF<<<GridSize(ncam),256>>>(w5_ir_B,w5_ir_r,ncam,w5_ir_z);
        CUDA_CHECK(cudaMemcpy(w5_ir_p,w5_ir_z,(size_t)n_c*sizeof(float),cudaMemcpyDeviceToDevice));
        float bn=0,rzf=0;cublasSnrm2(blas,n_c,w5_ir_r,1,&bn);cublasSdot(blas,n_c,w5_ir_r,1,w5_ir_z,1,&rzf);
        if(!(bn>0)&&std::isfinite(bn)){CUDA_CHECK(cudaMemset(sol,0,(size_t)n_c*sizeof(Scalar)));return 0;}
        int used=0;
        for(int it=0;it<maxck;++it){
          W5LowKv(w5_ir_p,w5_ir_Ap,shifts[0]);float pap=0,ppf=0;cublasSdot(blas,n_c,w5_ir_p,1,w5_ir_Ap,1,&pap);cublasSdot(blas,n_c,w5_ir_p,1,w5_ir_p,1,&ppf);
          if(!(pap>1e-6f*ppf)&&ppf>0)return -1;const float al=rzf/pap,mal=-al;
          cublasSaxpy(blas,n_c,&al,w5_ir_p,1,w5_ir_x,1);cublasSaxpy(blas,n_c,&mal,w5_ir_Ap,1,w5_ir_r,1);used=it+1;
          float rn=0;cublasSnrm2(blas,n_c,w5_ir_r,1,&rn);if(!std::isfinite(rn))return -1;if(rn<=tol*bn)break;
          W5ApplyPcgF<<<GridSize(ncam),256>>>(w5_ir_B,w5_ir_r,ncam,w5_ir_z);float next=0;cublasSdot(blas,n_c,w5_ir_r,1,w5_ir_z,1,&next);
          const float be=next/rzf;cublasSscal(blas,n_c,&be,w5_ir_p,1);const float one=1;cublasSaxpy(blas,n_c,&one,w5_ir_z,1,w5_ir_p,1);rzf=next;
        }
        W5CastF2D<<<GridSize(n_c),256>>>(w5_ir_x,sol,n_c);return used;
      };
      CUDA_CHECK(cudaMemset(w5_ir_xd,0,(size_t)n_c*sizeof(Scalar)));CUDA_CHECK(cudaMemcpy(w5_ir_rd,bprime,(size_t)n_c*sizeof(Scalar),cudaMemcpyDeviceToDevice));
      const Scalar inner_tol=std::min((Scalar).1,std::max((Scalar).5*eta,(Scalar)1e-3));
      Scalar prior_rel=1.0,final_rel=1.0;int sweeps=0,total_low=0;bool low_ok=true;
      for(int sw=0;sw<2;++sw){
        const int its=LowSolve(w5_ir_rd,w5_ir_dd,inner_tol);if(its<0){low_ok=false;break;}
        ++sweeps;total_low+=its;cublasDaxpy(blas,n_c,&(const Scalar&){1.0},w5_ir_dd,1,w5_ir_xd,1);
        KvS(w5_ir_xd,w5_ir_Axd);{const Scalar sh=shifts[0];cublasDaxpy(blas,n_c,&sh,w5_ir_xd,1,w5_ir_Axd,1);}
        CUDA_CHECK(cudaMemcpy(w5_ir_rd,bprime,(size_t)n_c*sizeof(Scalar),cudaMemcpyDeviceToDevice));{const Scalar m=-1;cublasDaxpy(blas,n_c,&m,w5_ir_Axd,1,w5_ir_rd,1);}
        Scalar rn=0;cublasDnrm2(blas,n_c,w5_ir_rd,1,&rn);final_rel=rn/std::max(nb,(Scalar)1e-300);
        if(!(final_rel<prior_rel)){++w5_ir_nonmonotone;low_ok=false;break;}prior_rel=final_rel;if(final_rel<=1.01*eta)break;
      }
      w5_ir_sweeps+=sweeps;w5_ir_low_iters+=total_low;
      if(low_ok && final_rel<=1.01*eta){
        Scalar bx=0,xax=0;cublasDdot(blas,n_c,bprime,1,w5_ir_xd,1,&bx);cublasDdot(blas,n_c,w5_ir_xd,1,w5_ir_Axd,1,&xax);
        preds[0]=bx-.5*xax;CUDA_CHECK(cudaMemcpy(xs[0],w5_ir_xd,(size_t)n_c*sizeof(Scalar),cudaMemcpyDeviceToDevice));
        // The legacy PCG path clips and scores inside the !projected_ok
        // block below.  A successful refinement deliberately bypasses that
        // block, so it must perform the same terminal candidate work here.
        // Retained-Krylov paths already score before setting projected_ok;
        // mirror that contract rather than silently returning a zero step.
        if(attr_radius){
          cublasDnrm2(blas,n_c,xs[0],1,&attr_raw_norm);
          if(!(attr_R>0))attr_R=std::isfinite(attr_raw_norm)&&attr_raw_norm>0?attr_raw_norm:1;
          attr_old_R=attr_R;
          if(attr_raw_norm>attr_R){const Scalar scale=attr_R/attr_raw_norm;cublasDscal(blas,n_c,&scale,xs[0],1);}
        }
        Score(xs[0],0,total_low);
        projected_ok=true;cg_broke=true;cg_it=total_low;if(pcg)pcg->last_depth=total_low;
      }else ++w5_ir_fallbacks;
      std::printf("W5_IR_ATTEMPT outer=%d retry=%d sweeps=%d low_iters=%d high_rel=%.9g eta=%.9g fallback=%d\n",
          k,retries,sweeps,total_low,(double)final_rel,(double)eta,(int)!projected_ok);
      if(prof){cudaDeviceSynchronize();t_mv+=std::chrono::duration<double>(now()-t0).count();}
    }
    if(!projected_ok){
    if(recycle_mode){'''
    # Compound-literal addresses are not C++; use a normal scoped constant.
    replacement=replacement.replace('cublasDaxpy(blas,n_c,&(const Scalar&){1.0},w5_ir_dd,1,w5_ir_xd,1);',
                                    '{const Scalar one=1;cublasDaxpy(blas,n_c,&one,w5_ir_dd,1,w5_ir_xd,1);}')
    patch(anchor,replacement)
    patch(r'''  if(prof) std::printf("  [PROFILE] assembly=%.3fs pointfactor+rhs=%.3fs krylov=%.3fs candidates=%.3fs\n",
                       t_asm,t_fac,t_mv,t_cand);''',r'''  if(prof) std::printf("  [PROFILE] assembly=%.3fs pointfactor+rhs=%.3fs krylov=%.3fs candidates=%.3fs\n",
                       t_asm,t_fac,t_mv,t_cand);
  if(w5_ir)std::printf("W5_IR_SUMMARY attempts=%ld sweeps=%ld fallbacks=%ld nonmonotone=%ld low_iters=%ld\n",
      w5_ir_attempts,w5_ir_sweeps,w5_ir_fallbacks,w5_ir_nonmonotone,w5_ir_low_iters);''')
    patch('  cudaFree(Hcc);cudaFree(Cdiag);cudaFree(Gp);cudaFree(Gc);cudaFree(Bo);cudaFree(fragment_slots);cudaFree(fragment_camera_ids);',r'''  cudaFree(Hcc);cudaFree(Cdiag);cudaFree(Gp);cudaFree(Gc);cudaFree(Bo);
  cudaFree(w5_ir_J);cudaFree(w5_ir_Rf);cudaFree(w5_ir_B);cudaFree(w5_ir_x);cudaFree(w5_ir_r);cudaFree(w5_ir_p);cudaFree(w5_ir_Ap);cudaFree(w5_ir_z);cudaFree(w5_ir_raw);cudaFree(w5_ir_tacc);cudaFree(w5_ir_u);
  cudaFree(w5_ir_R0);cudaFree(w5_ir_Rd);cudaFree(w5_ir_xd);cudaFree(w5_ir_dd);cudaFree(w5_ir_rd);cudaFree(w5_ir_Axd);cudaFree(fragment_slots);cudaFree(fragment_camera_ids);''')

    restored=source
    for before,after,count in reversed(changes):
        assert restored.count(after)==count
        restored=restored.replace(after,before)
    assert restored==original
    return source,len(changes)


def main():
    subprocess.run(["python3",str(F/"build.py"),"--check-only"],check=True)
    source,count=derive();build=P/"build";build.mkdir(exist_ok=True);src=build/"b2.cu";binary=build/"prism-b2";src.write_text(source)
    command=["nvcc","-O3","-DNDEBUG","-std=c++17","-arch=sm_89","-I/usr/include/eigen3",
      "-I"+str(F/"source"/"headers"),"-I"+str(P),str(src),"-o",str(binary),"-lcublas","-lcusolver"]
    with (build/"b2-build.log").open("w") as log:
      subprocess.run(command,env=dict(os.environ,TMPDIR="/dev/shm"),stdout=log,stderr=subprocess.STDOUT,check=True)
    manifest={"command":command,"source_sha256":sha(src),"binary_sha256":sha(binary),
      "frozen_source_sha256":sha(F/"source"/"prism_eta2.cu"),"champion_sha256":sha(F/"champion.json"),
      "reversible_patch_count":count,"sources":{str(P/"build_b2.py"):sha(P/"build_b2.py"),
      str(P/"sqrt_schur.cuh"):sha(P/"sqrt_schur.cuh"),str(P/"mixed_ir.cuh"):sha(P/"mixed_ir.cuh")},
      "protocol_sha256":sha(P/"B2_PROTOCOL.md")}
    (P/"b2-build-manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print("BUILT B2",manifest["binary_sha256"],flush=True)
if __name__=="__main__":main()
