#!/usr/bin/env python3
"""Build wave-5 B1 as a reversible overlay on the frozen Eta2 source."""
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
        assert source.count(before) == count, (before[:120], source.count(before), count)
        source = source.replace(before, after)
        changes.append((before, after, count))

    patch('#include "point_prep_candidate.cuh"',
          '#include "point_prep_candidate.cuh"\n#include "factored_fragments.cuh"')
    patch('  Fragment *Gp=nullptr,*Gc=nullptr,*Bo=nullptr;', r'''  Fragment *Gp=nullptr,*Gc=nullptr,*Bo=nullptr;
  Fragment *w5_factored=nullptr;
  Scalar *w5_factored_audit_out=nullptr;
  const bool w5_factored_on=[](){const char* e=getenv("OCA_W5_FACTORED_J");return e&&atoi(e)!=0;}();
  const bool w5_factored_audit=[](){const char* e=getenv("OCA_W5_FACTORED_AUDIT");return e&&atoi(e)!=0;}();
  bool w5_factored_audited=false;''')
    patch(r'''  if(compact_mode<0 || compact_mode>2)
    throw std::runtime_error("OCA_COMPACT_FRAGMENTS must be 0, 1, or 2");''', r'''  if(compact_mode<0 || compact_mode>2)
    throw std::runtime_error("OCA_COMPACT_FRAGMENTS must be 0, 1, or 2");
  if(w5_factored_on && (CD!=9 || compact_mode!=2 || mf_fp32 || shared_intr || rk ||
      !classical_lm || !use_equil || !pcg || pcg->schur || k2mask!=0.0 || block_eq ||
      getenv("OCA_JIT_J") || getenv("OCA_RHS_DIAG_CAMERA") || getenv("OCA_SCORE_STRIDE")))
    throw std::runtime_error("wave5 factored fragments require the frozen L2 single-shift Eta2 layout");
  if(w5_factored_audit && !w5_factored_on)
    throw std::runtime_error("wave5 factored audit requires OCA_W5_FACTORED_J=1");''')
    patch(r'''  if(mf_fp32){ M((void**)&Gp32,(size_t)3*CD*nobs*sizeof(float));M((void**)&Gc32,(size_t)3*CD*nobs*sizeof(float));
               M((void**)&Bo32,6ul*nobs*sizeof(float)); }
  else       { M((void**)&Gp,(size_t)3*CD*nobs*sizeof(Fragment));
               if(!compact_fragments) M((void**)&Gc,(size_t)3*CD*nobs*sizeof(Fragment));
               M((void**)&Bo,6ul*nobs*sizeof(Fragment)); }''', r'''  if(mf_fp32){ M((void**)&Gp32,(size_t)3*CD*nobs*sizeof(float));M((void**)&Gc32,(size_t)3*CD*nobs*sizeof(float));
               M((void**)&Bo32,6ul*nobs*sizeof(float)); }
  else       { if(w5_factored_on) M((void**)&w5_factored,(size_t)W5_FACTORED_VALUES*nobs*sizeof(Fragment));
               else { M((void**)&Gp,(size_t)3*CD*nobs*sizeof(Fragment));
                      if(!compact_fragments) M((void**)&Gc,(size_t)3*CD*nobs*sizeof(Fragment)); }
               M((void**)&Bo,6ul*nobs*sizeof(Fragment)); }
  if(w5_factored_audit)M((void**)&w5_factored_audit_out,4*sizeof(Scalar));
  if(w5_factored_on)std::printf("  [w5-factored] active values_per_obs=%d cross_bytes_saved=%zu total_fragment_bytes_saved=%zu\n",
    W5_FACTORED_VALUES,(size_t)nobs*(27-W5_FACTORED_VALUES)*sizeof(Fragment),
    (size_t)nobs*(33-(W5_FACTORED_VALUES+6))*sizeof(Fragment));''')
    patch('  int L = nshifts_env > 0 ? nshifts_env : n_shifts;', r'''  int L = nshifts_env > 0 ? nshifts_env : n_shifts;
  if(w5_factored_on && L!=1)throw std::runtime_error("wave5 factored fragments are registered for one shift");''')

    # The three assembly sites have different indentation.  Only the final one
    # is used by the frozen champion; patching all three keeps optional RI code
    # from dereferencing the intentionally unallocated W buffer.
    patch(r'''      else        MFAssemble<CD,Fragment><<<GridSize(nobs),256>>>(p.cam_idx,p.pt_idx,p.uv,s.R,s.t,s.X,
          INTR_F(p,s),INTR_K1(p,s),INTR_K2(p,s),
          fragment_o2slot,p.obs2cslot,nobs,Hcc,Cdiag,Gp,Gc,Bo,bc,bp,k2mask,r2acc,obscnt,rk,rk_a2);''', r'''      else if(w5_factored_on) MFAssembleFactored9<Fragment><<<GridSize(nobs),256>>>(p.cam_idx,p.pt_idx,p.uv,s.R,s.t,s.X,
          INTR_F(p,s),INTR_K1(p,s),INTR_K2(p,s),fragment_o2slot,nobs,Hcc,Cdiag,w5_factored,Bo,bc,bp,k2mask,r2acc,obscnt,rk,rk_a2);
      else        MFAssemble<CD,Fragment><<<GridSize(nobs),256>>>(p.cam_idx,p.pt_idx,p.uv,s.R,s.t,s.X,
          INTR_F(p,s),INTR_K1(p,s),INTR_K2(p,s),
          fragment_o2slot,p.obs2cslot,nobs,Hcc,Cdiag,Gp,Gc,Bo,bc,bp,k2mask,r2acc,obscnt,rk,rk_a2);''')
    patch(r'''        else        MFAssemble<CD,Fragment><<<GridSize(nobs),256>>>(p.cam_idx,p.pt_idx,p.uv,s.R,s.t,s.X,
            INTR_F(p,s),INTR_K1(p,s),INTR_K2(p,s),
            fragment_o2slot,p.obs2cslot,nobs,Hcc,Cdiag,Gp,Gc,Bo,bc,bp,k2mask,r2acc,obscnt,rk,rk_a2);''', r'''        else if(w5_factored_on) MFAssembleFactored9<Fragment><<<GridSize(nobs),256>>>(p.cam_idx,p.pt_idx,p.uv,s.R,s.t,s.X,
            INTR_F(p,s),INTR_K1(p,s),INTR_K2(p,s),fragment_o2slot,nobs,Hcc,Cdiag,w5_factored,Bo,bc,bp,k2mask,r2acc,obscnt,rk,rk_a2);
        else        MFAssemble<CD,Fragment><<<GridSize(nobs),256>>>(p.cam_idx,p.pt_idx,p.uv,s.R,s.t,s.X,
            INTR_F(p,s),INTR_K1(p,s),INTR_K2(p,s),
            fragment_o2slot,p.obs2cslot,nobs,Hcc,Cdiag,Gp,Gc,Bo,bc,bp,k2mask,r2acc,obscnt,rk,rk_a2);''')
    patch(r'''    else        MFAssemble<CD,Fragment><<<GridSize(nobs),256>>>(p.cam_idx,p.pt_idx,p.uv,s.R,s.t,s.X,
        INTR_F(p,s),INTR_K1(p,s),INTR_K2(p,s),
        fragment_o2slot,p.obs2cslot,nobs,Hcc,Cdiag,Gp,Gc,Bo,bc,bp,k2mask,r2acc,obscnt,rk,rk_a2);''', r'''    else if(w5_factored_on) MFAssembleFactored9<Fragment><<<GridSize(nobs),256>>>(p.cam_idx,p.pt_idx,p.uv,s.R,s.t,s.X,
        INTR_F(p,s),INTR_K1(p,s),INTR_K2(p,s),fragment_o2slot,nobs,Hcc,Cdiag,w5_factored,Bo,bc,bp,k2mask,r2acc,obscnt,rk,rk_a2);
    else        MFAssemble<CD,Fragment><<<GridSize(nobs),256>>>(p.cam_idx,p.pt_idx,p.uv,s.R,s.t,s.X,
        INTR_F(p,s),INTR_K1(p,s),INTR_K2(p,s),
        fragment_o2slot,p.obs2cslot,nobs,Hcc,Cdiag,Gp,Gc,Bo,bc,bp,k2mask,r2acc,obscnt,rk,rk_a2);''')
    patch(r'''    if(r2acc) KernelDampIntr9<<<GridSize(ncam),256>>>(Hcc,INTR_F(p,s),r2acc,obscnt,ncam,intr_damp,k2mask);''', r'''    if(r2acc) KernelDampIntr9<<<GridSize(ncam),256>>>(Hcc,INTR_F(p,s),r2acc,obscnt,ncam,intr_damp,k2mask);
    if(w5_factored_audit && !w5_factored_audited){
      CUDA_CHECK(cudaMemset(w5_factored_audit_out,0,4*sizeof(Scalar)));
      W5FactoredAudit9<Fragment><<<GridSize(nobs),256>>>(p.cam_idx,p.pt_idx,p.uv,s.R,s.t,s.X,
        INTR_F(p,s),INTR_K1(p,s),INTR_K2(p,s),fragment_o2slot,w5_factored,nobs,w5_factored_audit_out);
      Scalar h[4];CUDA_CHECK(cudaMemcpy(h,w5_factored_audit_out,4*sizeof(Scalar),cudaMemcpyDeviceToHost));
      std::printf("W5_FACTORED_AUDIT rel_frob=%.17g max_abs=%.17g max_reference=%.17g observations=%d\n",
        std::sqrt(h[0]/std::max(h[1],(Scalar)1e-300)),h[2],h[3],nobs);
      w5_factored_audited=true;
    }''')

    patch(r'''    const bool prep_fused = CD==9 && use_equil && !e_dead && !rhs_diag_camera;
    if(prep_fused){''', r'''    const bool prep_fused = CD==9 && use_equil && !e_dead && !rhs_diag_camera;
    if(w5_factored_on && !prep_fused)throw std::runtime_error("wave5 factored path requires fused RHS/diagonal preparation");
    if(prep_fused){''')
    patch('      MFRhsDiagFused<<<GridSize(nobs),256>>>(mf_fp32?Gp32:Gp,fragment_cams,fragment_points,Rf,uu,nobs,corr,dk);', r'''      if(w5_factored_on)MFRhsDiagFusedFactored9<Fragment><<<(nobs+127)/128,128>>>(w5_factored,fragment_cams,fragment_points,s.R,Rf,uu,nobs,corr,dk);
      else MFRhsDiagFused<<<GridSize(nobs),256>>>(mf_fp32?Gp32:Gp,fragment_cams,fragment_points,Rf,uu,nobs,corr,dk);''')
    patch(r'''      else       { MFPass1<CD,Fragment><<<GridSize(nobs),256>>>(Gp,fragment_cams,fragment_points,vf,nobs,tacc);
                   MFVinvApply<<<GridSize(npt),256>>>(Rf,tacc,npt,uu);
                   MFPass2<CD,Fragment><<<ncam,256>>>(Gc?Gc:Gp,p.mf_cspt,p.mf_coff,uu,Hcc,vf,nobs,wf,fragment_slots); }''', r'''      else if(w5_factored_on){ MFPass1Factored9<Fragment><<<GridSize(nobs),256>>>(w5_factored,fragment_cams,fragment_points,s.R,vf,nobs,tacc);
                   MFVinvApply<<<GridSize(npt),256>>>(Rf,tacc,npt,uu);
                   MFPass2Factored9<Fragment><<<ncam,128>>>(w5_factored,p.mf_cspt,p.mf_coff,s.R,uu,Hcc,vf,nobs,wf); }
      else       { MFPass1<CD,Fragment><<<GridSize(nobs),256>>>(Gp,fragment_cams,fragment_points,vf,nobs,tacc);
                   MFVinvApply<<<GridSize(npt),256>>>(Rf,tacc,npt,uu);
                   MFPass2<CD,Fragment><<<ncam,256>>>(Gc?Gc:Gp,p.mf_cspt,p.mf_coff,uu,Hcc,vf,nobs,wf,fragment_slots); }''')
    patch('        else        MFPass1<CD,Fragment><<<GridSize(nobs),256>>>(Gp,fragment_cams,fragment_points,xc_un,nobs,tacc);', r'''        else if(w5_factored_on) MFPass1Factored9<Fragment><<<GridSize(nobs),256>>>(w5_factored,fragment_cams,fragment_points,s.R,xc_un,nobs,tacc);
        else        MFPass1<CD,Fragment><<<GridSize(nobs),256>>>(Gp,fragment_cams,fragment_points,xc_un,nobs,tacc);''')
    patch('        else        MFPass1Multi<CD,Fragment><<<GridSize(nobs),256>>>(Gp,fragment_cams,fragment_points,XCU,n_cf,na,nobs,TACC,n_p); });', r'''        else if(w5_factored_on) MFPass1MultiFactored9<Fragment><<<GridSize(nobs),256>>>(w5_factored,fragment_cams,fragment_points,s.R,XCU,n_cf,na,nobs,TACC,n_p);
        else        MFPass1Multi<CD,Fragment><<<GridSize(nobs),256>>>(Gp,fragment_cams,fragment_points,XCU,n_cf,na,nobs,TACC,n_p); });''')
    patch(r'''        CUDA_CHECK(cudaMemset(TACC,0,(size_t)na*n_p*sizeof(Scalar)));
        MFPass1Multi<CD,Fragment><<<GridSize(nobs),256>>>(Gp,fragment_cams,fragment_points,XCU,n_cf,na,nobs,TACC,n_p);
        for(int a=0;a<na;++a){''', r'''        CUDA_CHECK(cudaMemset(TACC,0,(size_t)na*n_p*sizeof(Scalar)));
        if(w5_factored_on)MFPass1MultiFactored9<Fragment><<<GridSize(nobs),256>>>(w5_factored,fragment_cams,fragment_points,s.R,XCU,n_cf,na,nobs,TACC,n_p);
        else MFPass1Multi<CD,Fragment><<<GridSize(nobs),256>>>(Gp,fragment_cams,fragment_points,XCU,n_cf,na,nobs,TACC,n_p);
        for(int a=0;a<na;++a){''')
    patch('  cudaFree(Hcc);cudaFree(Cdiag);cudaFree(Gp);cudaFree(Gc);cudaFree(Bo);cudaFree(fragment_slots);cudaFree(fragment_camera_ids);',
          '  cudaFree(Hcc);cudaFree(Cdiag);cudaFree(Gp);cudaFree(Gc);cudaFree(Bo);cudaFree(w5_factored);cudaFree(w5_factored_audit_out);cudaFree(fragment_slots);cudaFree(fragment_camera_ids);')

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
    src = build / "b1v2.cu"
    binary = build / "prism-b1v2"
    src.write_text(source)
    command = ["nvcc", "-O3", "-DNDEBUG", "-std=c++17", "-arch=sm_89",
               "-I/usr/include/eigen3", "-I" + str(F / "source" / "headers"),
               "-I" + str(P), str(src), "-o", str(binary), "-lcublas", "-lcusolver"]
    with (build / "b1v2-build.log").open("w") as log:
        subprocess.run(command, env=dict(os.environ, TMPDIR="/dev/shm"),
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    manifest = {
        "command": command, "source_sha256": sha(src), "binary_sha256": sha(binary),
        "frozen_source_sha256": sha(F / "source" / "prism_eta2.cu"),
        "champion_sha256": sha(F / "champion.json"), "reversible_patch_count": count,
        "sources": {str(P / "build_b1.py"): sha(P / "build_b1.py"),
                    str(P / "factored_fragments.cuh"): sha(P / "factored_fragments.cuh")},
        "protocol_sha256": sha(P / "B1V2_PROTOCOL.md"),
    }
    (P / "b1v2-build-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("BUILT B1V2", manifest["binary_sha256"], flush=True)


if __name__ == "__main__":
    main()
