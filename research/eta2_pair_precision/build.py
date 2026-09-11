#!/usr/bin/env python3
"""Reproducible default-off derivation; no frozen solver files are edited."""
import fcntl, hashlib, json, subprocess
from pathlib import Path
P=Path(__file__).resolve().parent;D=P.parent/'eta2_depth_rescue';F=P.parent/'eta2_champion'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def patch(s,a,b):
    assert s.count(a)==1,(a[:100],s.count(a));return s.replace(a,b)
def main():
    subprocess.run(['python3',str(F/'build.py'),'--check-only'],check=True)
    parent=D/'build/prism_depth.cu'
    assert sha(parent)==json.loads((D/'provenance/build_manifest.json').read_text())['source_sha256']
    s=parent.read_text()
    anchor='template <int CD>\nRunLog SolveMFreeShiftedCG('
    s=patch(s,anchor,(P/'cross64.cuh').read_text()+'\n'+anchor)
    anchor='  int depth_pending=0,depth_active=0;'
    s=patch(s,anchor,'''  const bool depth_pair=getenv("OCA_DEPTH_PAIR") && atoi(getenv("OCA_DEPTH_PAIR"))!=0;
  const bool depth_fp64=getenv("OCA_DEPTH_FP64") && atoi(getenv("OCA_DEPTH_FP64"))!=0;
  if(depth_pair && !depth_stop)throw std::runtime_error("pair requires stop probe");
  if(depth_fp64 && ((!depth_stop&&!depth_declip)||jit_on||attr_split||
     (getenv("OCA_RHS_DIAG_CAMERA") && atoi(getenv("OCA_RHS_DIAG_CAMERA")))))
    throw std::runtime_error("FP64 probe requires registered plain Eta2 preparation");
  double depth_saved_lambda=0,depth_saved_radius=0;int depth_saved_outer=-1;
  Scalar* depth_G64=nullptr;long depth_cross_builds=0;
'''+anchor)
    anchor='     if(depth_active==1)lam_cam=std::clamp(depth_requested_center,numeric_floor,1e16);'
    s=patch(s,anchor,'''     if(depth_active==1){
       lam_cam=std::clamp(depth_requested_center,numeric_floor,1e16);
       if(depth_pair){
         attr_R=depth_saved_radius*std::sqrt(depth_saved_lambda/lam_cam);
         std::printf("PAIR_RESTORE o=%d saved_outer=%d saved_lambda=%.17g saved_radius=%.17g lambda=%.17g radius=%.17g floor=%.17g\\n",
           k,depth_saved_outer,depth_saved_lambda,depth_saved_radius,(double)lam_cam,attr_R,(double)numeric_floor);
       }
     }''')
    anchor='   const int depth_kind_this_attempt=depth_active;'
    s=patch(s,anchor,anchor+'\n   const bool depth_cross_active=depth_active && depth_fp64;')
    anchor='    const bool reuse_factor=cache_eligible && factor_cached &&'
    s=patch(s,anchor,'''    if(depth_cross_active){
      if(!depth_G64)M((void**)&depth_G64,27ul*nobs*sizeof(Scalar));
      DepthCross64<<<GridSize(nobs),256>>>(p.cam_idx,p.pt_idx,p.uv,s.R,s.t,s.X,
        INTR_F(p,s),INTR_K1(p,s),INTR_K2(p,s),fragment_o2slot,nobs,k2mask,depth_G64);
      factor_cached=false;++depth_cross_builds;
      std::printf("DEPTH_PRECISION o=%d kind=%d cross_bits=64 bytes=%zu builds=%ld\\n",
        k,depth_active,27ul*nobs*sizeof(Scalar),depth_cross_builds);
    }
'''+anchor)
    s=patch(s,'const bool prep_fused = CD==9 && use_equil && !e_dead && !rhs_diag_camera;',
        'const bool prep_fused = CD==9 && use_equil && !e_dead && !rhs_diag_camera && !depth_cross_active;')
    anchor='      if(mf_fp32) MFRhsPrime<CD,float>'
    s=patch(s,anchor,'''      if(depth_cross_active) MFRhsPrime<CD,double><<<GridSize(nobs),256>>>(depth_G64,fragment_cams,fragment_points,uu,nobs,corr);
      else if(mf_fp32) MFRhsPrime<CD,float>''')
    # Classical LM replaces this diagonal with Hcc anyway. Skip dead work only on probes.
    s=patch(s,'      if(!rhs_diag_camera && !prep_fused){',
        '      if(!rhs_diag_camera && !prep_fused && !depth_cross_active){')
    anchor='      } else if(mf_fp32){ MFPass1<CD,float>'
    s=patch(s,anchor,'''      } else if(depth_cross_active){
        MFPass1<CD,double><<<GridSize(nobs),256>>>(depth_G64,fragment_cams,fragment_points,vf,nobs,tacc);
        MFVinvApply<<<GridSize(npt),256>>>(Rf,tacc,npt,uu);
        MFPass2<CD,double><<<ncam,256>>>(depth_G64,p.mf_cspt,p.mf_coff,uu,Hcc,vf,nobs,wf,fragment_slots);
      } else if(mf_fp32){ MFPass1<CD,float>''')
    anchor='        if(mf_fp32) MFPass1<CD,float><<<GridSize(nobs),256>>>(Gp32,fragment_cams,fragment_points,xc_un,nobs,tacc);'
    s=patch(s,anchor,'''        if(depth_cross_active) MFPass1<CD,double><<<GridSize(nobs),256>>>(depth_G64,fragment_cams,fragment_points,xc_un,nobs,tacc);
        else '''+anchor.strip())
    anchor='    if(ftol_streak==0) depth_flat_center=depth_attempt_center;'
    s=patch(s,anchor,anchor+'''
    if(depth_pair && !depth_kind_this_attempt && accepted &&
       last_rel>std::max(1e-4,10*ftol_env) && attr_R>0 &&
       std::isfinite(attr_R) && lam_cam>0 && std::isfinite(lam_cam)){
      depth_saved_lambda=lam_cam;depth_saved_radius=attr_R;depth_saved_outer=k+1;
    }
''')
    s=patch(s,'    if(converged && depth_stop && !depth_stop_spent && k+1<max_iter){',
        '    if(converged && depth_stop && !depth_stop_spent && k+1<max_iter && (!depth_pair||depth_saved_outer>=0)){')
    s=patch(s,'      depth_pending=1;depth_requested_center=depth_flat_center;',
        '      depth_pending=1;depth_requested_center=depth_pair?depth_saved_lambda:depth_flat_center;')
    anchor='        depth_requested_center,(double)lam_cam);'
    s=patch(s,anchor,anchor+'''
      if(depth_pair)std::printf("PAIR_WITNESS outer=%d saved_outer=%d saved_lambda=%.17g saved_radius=%.17g current_lambda=%.17g current_radius=%.17g\\n",
        k+1,depth_saved_outer,depth_saved_lambda,depth_saved_radius,(double)lam_cam,attr_R);''')
    anchor='      if(won){++depth_wins;depth_active=0;ftol_streak=0;stuck=0;}'
    s=patch(s,anchor,'''      std::printf("DEPTH_LINEAR o=%d cross_bits=%d pAp=%.17g pp=%.17g raw_norm=%.17g radius=%.17g\\n",
        k,depth_cross_active?64:32,nc_pAp,nc_pp,attr_raw_norm,attr_old_R);
'''+anchor)
    anchor='  if(depth_stop||depth_declip)std::printf("DEPTH_SUMMARY'
    s=patch(s,anchor,'''  if(depth_G64)CUDA_CHECK(cudaFree(depth_G64));
'''+anchor)
    b=P/'build';b.mkdir(exist_ok=True);source=b/'prism_pair.cu';source.write_text(s)
    cmd=['nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3',
      '-I'+str(F/'source/headers'),str(source),'-o',str(b/'prism-pair'),'-lcublas','-lcusolver']
    with open('/tmp/prism_gpu.lock','w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        with (b/'build.log').open('w') as log:subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True)
    (b/'manifest.json').write_text(json.dumps(dict(command=cmd,source_sha256=sha(source),
      binary_sha256=sha(b/'prism-pair'),parent_source_sha256=sha(parent),
      frozen_source_sha256=sha(F/'source/prism_eta2.cu'),protocol_sha256=sha(P/'PROTOCOL.md')),indent=2)+'\n')
    print('BUILT',sha(b/'prism-pair'),flush=True)
if __name__=='__main__':main()
