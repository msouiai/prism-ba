#!/usr/bin/env python3
"""Build the preregistered wave-5 B5 square-root Schur overlay."""
from pathlib import Path
import hashlib
import json
import os
import subprocess

P = Path(__file__).resolve().parent
F = P.parent / "eta2_champion"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def derive():
    source_path = F / "source" / "prism_eta2.cu"
    source = original = source_path.read_text()
    changes = []

    def patch(before, after, count=1):
        nonlocal source
        assert source.count(before) == count, (before[:140], source.count(before), count)
        source = source.replace(before, after)
        changes.append((before, after, count))

    patch('#include "point_prep_candidate.cuh"',
          '#include "point_prep_candidate.cuh"\n#include "sqrt_schur.cuh"')
    patch('  Fragment *Gp=nullptr,*Gc=nullptr,*Bo=nullptr;', r'''  Fragment *Gp=nullptr,*Gc=nullptr,*Bo=nullptr;
  Fragment *w5_sqrt_J=nullptr;
  Scalar *w5_sqrt_ref=nullptr,*w5_sqrt_diff=nullptr,*w5_sqrt_sums=nullptr;
  const bool w5_sqrt=[](){const char* e=getenv("OCA_W5_SQRT");return e&&atoi(e)!=0;}();
  const bool w5_sqrt_audit=[](){const char* e=getenv("OCA_W5_SQRT_AUDIT");return e&&atoi(e)!=0;}();
  bool w5_sqrt_audited=false;''')
    patch(r'''  if(compact_mode<0 || compact_mode>2)
    throw std::runtime_error("OCA_COMPACT_FRAGMENTS must be 0, 1, or 2");''', r'''  if(compact_mode<0 || compact_mode>2)
    throw std::runtime_error("OCA_COMPACT_FRAGMENTS must be 0, 1, or 2");
  if(w5_sqrt && (CD!=9 || compact_mode!=2 || mf_fp32 || shared_intr || rk ||
      !classical_lm || !use_equil || !pcg || pcg->schur || k2mask!=0.0 || block_eq ||
      getenv("OCA_JIT_J") || getenv("OCA_RHS_DIAG_CAMERA") || getenv("OCA_SCORE_STRIDE") ||
      getenv("OCA_TAU_LAM_COND") || getenv("OCA_TAU_LAM_MAXOBS") || getenv("OCA_RI_OPEN")))
    throw std::runtime_error("wave5 square-root path requires the frozen L2 single-shift Eta2 layout");
  if(w5_sqrt_audit && !w5_sqrt)
    throw std::runtime_error("wave5 square-root audit requires OCA_W5_SQRT=1");''')
    patch(r'''  if(mf_fp32){ M((void**)&Gp32,(size_t)3*CD*nobs*sizeof(float));M((void**)&Gc32,(size_t)3*CD*nobs*sizeof(float));
               M((void**)&Bo32,6ul*nobs*sizeof(float)); }
  else       { M((void**)&Gp,(size_t)3*CD*nobs*sizeof(Fragment));
               if(!compact_fragments) M((void**)&Gc,(size_t)3*CD*nobs*sizeof(Fragment));
               M((void**)&Bo,6ul*nobs*sizeof(Fragment)); }''', r'''  if(mf_fp32){ M((void**)&Gp32,(size_t)3*CD*nobs*sizeof(float));M((void**)&Gc32,(size_t)3*CD*nobs*sizeof(float));
               M((void**)&Bo32,6ul*nobs*sizeof(float)); }
  else if(w5_sqrt) M((void**)&w5_sqrt_J,(size_t)W5_SQRT_VALUES*nobs*sizeof(Fragment));
  else       { M((void**)&Gp,(size_t)3*CD*nobs*sizeof(Fragment));
               if(!compact_fragments) M((void**)&Gc,(size_t)3*CD*nobs*sizeof(Fragment));
               M((void**)&Bo,6ul*nobs*sizeof(Fragment)); }
  if(w5_sqrt_audit){M((void**)&w5_sqrt_ref,(size_t)n_cf*sizeof(Scalar));
                    M((void**)&w5_sqrt_diff,(size_t)n_cf*sizeof(Scalar));
                    M((void**)&w5_sqrt_sums,3*sizeof(Scalar));}
  if(w5_sqrt)std::printf("  [w5-sqrt] active values_per_obs=%d bytes_saved=%zu arithmetic=fp64 storage=fp32\n",
    W5_SQRT_VALUES,(size_t)nobs*(33-W5_SQRT_VALUES)*sizeof(Fragment));''')
    patch(r'''  static const bool tau_split = [](){ const char* e=getenv("OCA_TAU_SPLIT");
    return e ? atoi(e)!=0 : true; }();''', r'''  static const bool tau_split = [](){ const char* e=getenv("OCA_TAU_SPLIT");
    return e ? atoi(e)!=0 : true; }();
  if(w5_sqrt && !tau_split)throw std::runtime_error("wave5 square-root path requires split point factorisation");''')
    patch('  int L = nshifts_env > 0 ? nshifts_env : n_shifts;', r'''  int L = nshifts_env > 0 ? nshifts_env : n_shifts;
  if(w5_sqrt && L!=1)throw std::runtime_error("wave5 square-root path is registered for one shift");''')

    # Main assembly plus the two dormant RI assembly sites.  RI itself is
    # rejected above, but keeping every site safe makes the overlay auditable.
    for indent in ("      ", "        ", "    "):
        before = indent + r'''else        MFAssemble<CD,Fragment><<<GridSize(nobs),256>>>(p.cam_idx,p.pt_idx,p.uv,s.R,s.t,s.X,
''' + indent + r'''    INTR_F(p,s),INTR_K1(p,s),INTR_K2(p,s),
''' + indent + r'''    fragment_o2slot,p.obs2cslot,nobs,Hcc,Cdiag,Gp,Gc,Bo,bc,bp,k2mask,r2acc,obscnt,rk,rk_a2);'''
        after = indent + r'''else if(w5_sqrt) MFAssembleSqrt9<Fragment><<<GridSize(nobs),256>>>(p.cam_idx,p.pt_idx,p.uv,s.R,s.t,s.X,
''' + indent + r'''    INTR_F(p,s),INTR_K1(p,s),INTR_K2(p,s),p.obs2cslot,nobs,Hcc,Cdiag,w5_sqrt_J,bc,bp,k2mask,r2acc,obscnt,rk,rk_a2);
''' + before
        patch(before, after)

    patch(r'''      if(pf_obs_dirty){
        if(mf_fp32) MFPointFactorObs<float><<<GridSize(npt),256>>>(Bo32,p.point_obs_offsets,p.point_obs_list,npt,R0f);
        else MFPointFactorGuarded<<<GridSize(npt),256>>>(Bo,p.point_obs_offsets,p.point_obs_list,npt,R0f,nullptr);
        pf_obs_dirty=false;
      }''', r'''      if(pf_obs_dirty){
        if(w5_sqrt) MFPointFactorObsSqrt9<Fragment><<<GridSize(npt),256>>>(w5_sqrt_J,p.obs2cslot,p.point_obs_offsets,p.point_obs_list,npt,nobs,R0f,nullptr);
        else if(mf_fp32) MFPointFactorObs<float><<<GridSize(npt),256>>>(Bo32,p.point_obs_offsets,p.point_obs_list,npt,R0f);
        else MFPointFactorGuarded<<<GridSize(npt),256>>>(Bo,p.point_obs_offsets,p.point_obs_list,npt,R0f,nullptr);
        pf_obs_dirty=false;
      }''')
    patch(r'''    const bool prep_fused = CD==9 && use_equil && !e_dead && !rhs_diag_camera;
    if(prep_fused){''', r'''    const bool prep_fused = CD==9 && use_equil && !e_dead && !rhs_diag_camera;
    if(w5_sqrt && !prep_fused)throw std::runtime_error("wave5 square-root path requires fused RHS/diagonal preparation");
    if(prep_fused){''')
    patch('      MFRhsDiagFused<<<GridSize(nobs),256>>>(mf_fp32?Gp32:Gp,fragment_cams,fragment_points,Rf,uu,nobs,corr,dk);', r'''      if(w5_sqrt)MFSqrtRhsDiag9<Fragment><<<GridSize(nobs),256>>>(w5_sqrt_J,fragment_cams,fragment_points,Rf,uu,nobs,corr,dk);
      else MFRhsDiagFused<<<GridSize(nobs),256>>>(mf_fp32?Gp32:Gp,fragment_cams,fragment_points,Rf,uu,nobs,corr,dk);''')
    patch(r'''      } else if(mf_fp32){ MFPass1<CD,float><<<GridSize(nobs),256>>>(Gp32,fragment_cams,fragment_points,vf,nobs,tacc);
                   MFVinvApply<<<GridSize(npt),256>>>(Rf,tacc,npt,uu);
                   MFPass2<CD,float><<<ncam,256>>>(Gc32,p.mf_cspt,p.mf_coff,uu,Hcc,vf,nobs,wf); }
      else       { MFPass1<CD,Fragment><<<GridSize(nobs),256>>>(Gp,fragment_cams,fragment_points,vf,nobs,tacc);
                   MFVinvApply<<<GridSize(npt),256>>>(Rf,tacc,npt,uu);
                   MFPass2<CD,Fragment><<<ncam,256>>>(Gc?Gc:Gp,p.mf_cspt,p.mf_coff,uu,Hcc,vf,nobs,wf,fragment_slots); }''', r'''      } else if(w5_sqrt){
        MFSqrtPass1<Fragment><<<GridSize(nobs),256>>>(w5_sqrt_J,fragment_cams,fragment_points,vf,nobs,tacc);
        MFVinvApply<<<GridSize(npt),256>>>(Rf,tacc,npt,uu);
        MFSqrtPass2<Fragment><<<ncam,128>>>(w5_sqrt_J,p.mf_cspt,p.mf_coff,uu,vf,nobs,
            INTR_F(p,s),r2acc,obscnt,intr_damp,k2mask,wf);
        if(w5_sqrt_audit && !w5_sqrt_audited){
          MFSqrtReferencePass2<Fragment><<<ncam,128>>>(w5_sqrt_J,p.mf_cspt,p.mf_coff,uu,Hcc,vf,nobs,w5_sqrt_ref);
          W5SqrtDifference<<<GridSize(n_cf),256>>>(wf,w5_sqrt_ref,w5_sqrt_diff,n_cf);
          Scalar nd=0,nr=0,curv=0;cublasDnrm2(blas,n_cf,w5_sqrt_diff,1,&nd);cublasDnrm2(blas,n_cf,w5_sqrt_ref,1,&nr);
          cublasDdot(blas,n_cf,vf,1,wf,1,&curv);CUDA_CHECK(cudaMemset(w5_sqrt_sums,0,3*sizeof(Scalar)));
          MFSqrtSosObs<Fragment><<<GridSize(nobs),256>>>(w5_sqrt_J,fragment_cams,fragment_points,vf,uu,nobs,w5_sqrt_sums);
          MFSqrtSosPoint<<<GridSize(npt),256>>>(Cdiag,uu,tau_eff,npt,w5_sqrt_sums);
          MFSqrtSosIntr<<<GridSize(ncam),256>>>(vf,INTR_F(p,s),r2acc,obscnt,ncam,intr_damp,k2mask,w5_sqrt_sums);
          Scalar hs[3];CUDA_CHECK(cudaMemcpy(hs,w5_sqrt_sums,3*sizeof(Scalar),cudaMemcpyDeviceToHost));
          const Scalar sos=hs[0]+hs[1]+hs[2],crel=fabs(curv-sos)/std::max(fabs(sos),(Scalar)1e-300);
          std::printf("W5_SQRT_AUDIT action_relative_l2=%.17g action_absolute_l2=%.17g reference_l2=%.17g curvature=%.17g sos=%.17g curvature_relative=%.17g obs=%.17g point_damp=%.17g intr=%.17g\n",
              (double)(nd/std::max(nr,(Scalar)1e-300)),(double)nd,(double)nr,(double)curv,(double)sos,(double)crel,
              (double)hs[0],(double)hs[1],(double)hs[2]);w5_sqrt_audited=true;
        }
      } else if(mf_fp32){ MFPass1<CD,float><<<GridSize(nobs),256>>>(Gp32,fragment_cams,fragment_points,vf,nobs,tacc);
                   MFVinvApply<<<GridSize(npt),256>>>(Rf,tacc,npt,uu);
                   MFPass2<CD,float><<<ncam,256>>>(Gc32,p.mf_cspt,p.mf_coff,uu,Hcc,vf,nobs,wf); }
      else       { MFPass1<CD,Fragment><<<GridSize(nobs),256>>>(Gp,fragment_cams,fragment_points,vf,nobs,tacc);
                   MFVinvApply<<<GridSize(npt),256>>>(Rf,tacc,npt,uu);
                   MFPass2<CD,Fragment><<<ncam,256>>>(Gc?Gc:Gp,p.mf_cspt,p.mf_coff,uu,Hcc,vf,nobs,wf,fragment_slots); }''')
    patch('        else        MFPass1<CD,Fragment><<<GridSize(nobs),256>>>(Gp,fragment_cams,fragment_points,xc_un,nobs,tacc);', r'''        else if(w5_sqrt) MFSqrtPass1<Fragment><<<GridSize(nobs),256>>>(w5_sqrt_J,fragment_cams,fragment_points,xc_un,nobs,tacc);
        else        MFPass1<CD,Fragment><<<GridSize(nobs),256>>>(Gp,fragment_cams,fragment_points,xc_un,nobs,tacc);''')
    patch('        else        MFPass1Multi<CD,Fragment><<<GridSize(nobs),256>>>(Gp,fragment_cams,fragment_points,XCU,n_cf,na,nobs,TACC,n_p); });', r'''        else if(w5_sqrt) MFSqrtPass1Multi<Fragment><<<GridSize(nobs),256>>>(w5_sqrt_J,fragment_cams,fragment_points,XCU,n_cf,na,nobs,TACC,n_p);
        else        MFPass1Multi<CD,Fragment><<<GridSize(nobs),256>>>(Gp,fragment_cams,fragment_points,XCU,n_cf,na,nobs,TACC,n_p); });''')
    patch(r'''        CUDA_CHECK(cudaMemset(TACC,0,(size_t)na*n_p*sizeof(Scalar)));
        MFPass1Multi<CD,Fragment><<<GridSize(nobs),256>>>(Gp,fragment_cams,fragment_points,XCU,n_cf,na,nobs,TACC,n_p);
        for(int a=0;a<na;++a){''', r'''        CUDA_CHECK(cudaMemset(TACC,0,(size_t)na*n_p*sizeof(Scalar)));
        if(w5_sqrt)MFSqrtPass1Multi<Fragment><<<GridSize(nobs),256>>>(w5_sqrt_J,fragment_cams,fragment_points,XCU,n_cf,na,nobs,TACC,n_p);
        else MFPass1Multi<CD,Fragment><<<GridSize(nobs),256>>>(Gp,fragment_cams,fragment_points,XCU,n_cf,na,nobs,TACC,n_p);
        for(int a=0;a<na;++a){''')
    patch('  cudaFree(Hcc);cudaFree(Cdiag);cudaFree(Gp);cudaFree(Gc);cudaFree(Bo);cudaFree(fragment_slots);cudaFree(fragment_camera_ids);',
          '  cudaFree(Hcc);cudaFree(Cdiag);cudaFree(Gp);cudaFree(Gc);cudaFree(Bo);cudaFree(w5_sqrt_J);cudaFree(w5_sqrt_ref);cudaFree(w5_sqrt_diff);cudaFree(w5_sqrt_sums);cudaFree(fragment_slots);cudaFree(fragment_camera_ids);')

    restored = source
    for before, after, count in reversed(changes):
        assert restored.count(after) == count
        restored = restored.replace(after, before)
    assert restored == original
    return source, len(changes)


def main():
    subprocess.run(["python3", str(F / "build.py"), "--check-only"], check=True)
    source, count = derive()
    build = P / "build"
    build.mkdir(exist_ok=True)
    src = build / "b5.cu"
    binary = build / "prism-b5"
    src.write_text(source)
    command = ["nvcc", "-O3", "-DNDEBUG", "-std=c++17", "-arch=sm_89",
               "-I/usr/include/eigen3", "-I" + str(F / "source" / "headers"),
               "-I" + str(P), str(src), "-o", str(binary), "-lcublas", "-lcusolver"]
    with (build / "b5-build.log").open("w") as log:
        subprocess.run(command, env=dict(os.environ, TMPDIR="/dev/shm"),
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    manifest = {
        "command": command, "source_sha256": sha(src), "binary_sha256": sha(binary),
        "frozen_source_sha256": sha(F / "source" / "prism_eta2.cu"),
        "champion_sha256": sha(F / "champion.json"), "reversible_patch_count": count,
        "sources": {str(P / "build_b5.py"): sha(P / "build_b5.py"),
                    str(P / "sqrt_schur.cuh"): sha(P / "sqrt_schur.cuh")},
        "protocol_sha256": sha(P / "B5_PROTOCOL.md"),
    }
    (P / "b5-build-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("BUILT B5", manifest["binary_sha256"], flush=True)


if __name__ == "__main__":
    main()
