#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,subprocess
P=Path(__file__).resolve().parent
BASE=Path('/tmp/prism-ba-coarse/research/eta2_wave5/build/b6v7.cu')
EXPECTED='c04bb4ed1a7fcbb6dcae5c9d016189612f854d91e92c34155a66114be62e23bb'
OUT=P/'build/native-timing.cu'; BIN=P/'build/native-timing'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def patch(s,a,b):
 assert s.count(a)==1,(a[:100],s.count(a));return s.replace(a,b)
def main():
 assert sha(BASE)==EXPECTED
 s=BASE.read_text()
 s=patch(s,'  BalData bal = LoadBal(problem_path);','''  const bool setup_phase_profile=getenv("OCA_NATIVE_PHASE_PROFILE")!=nullptr;
  auto setup_mark=std::chrono::steady_clock::now();
  BalData bal = LoadBal(problem_path);
  if(setup_phase_profile){auto q=std::chrono::steady_clock::now();std::printf("SETUP_PHASE parse_ms=%.9g\\n",1e3*std::chrono::duration<double>(q-setup_mark).count());setup_mark=q;}''')
 s=patch(s,'  DeviceProblem p; p.ncam = ncam; p.npt = npt; p.nobs = nobs; p.n = n;','''  DeviceProblem p; p.ncam = ncam; p.npt = npt; p.nobs = nobs; p.n = n;''')
 s=patch(s,'''    MemMark("context + problem data (baseline)");''','''    MemMark("context + problem data (baseline)");
    if(setup_phase_profile){CUDA_CHECK(cudaDeviceSynchronize());auto q=std::chrono::steady_clock::now();std::printf("SETUP_PHASE problem_alloc_h2d_unclassified_ms=%.9g\\n",1e3*std::chrono::duration<double>(q-setup_mark).count());setup_mark=q;}''')
 s=patch(s,'''    if (algo == "mfree_shifted_cg") {
      BuildMFreeIndex(p, bal.cam_idx.data(), bal.pt_idx.data(), order, ncam, nobs);
    }''','''    if (algo == "mfree_shifted_cg") {
      BuildMFreeIndex(p, bal.cam_idx.data(), bal.pt_idx.data(), order, ncam, nobs);
    }
    if(setup_phase_profile){CUDA_CHECK(cudaDeviceSynchronize());auto q=std::chrono::steady_clock::now();std::printf("SETUP_PHASE index_build_alloc_h2d_unclassified_ms=%.9g\\n",1e3*std::chrono::duration<double>(q-setup_mark).count());setup_mark=q;}''')
 s=patch(s,'  double t_asm=0,t_fac=0,t_mv=0,t_cand=0,t_alpha=0;', '''  double t_asm=0,t_fac=0,t_mv=0,t_cand=0,t_alpha=0;
  const bool native_phase_profile=getenv("OCA_NATIVE_PHASE_PROFILE")!=nullptr;
  cudaEvent_t npe[9]{}; double nptm[8]={}; long npcalls=0; bool np_active=false;
  if(native_phase_profile)for(auto& e:npe)CUDA_CHECK(cudaEventCreate(&e));
  auto NP=[&](int i){if(native_phase_profile&&np_active)CUDA_CHECK(cudaEventRecord(npe[i]));};
  auto NPFinish=[&](){if(!native_phase_profile||!np_active)return;CUDA_CHECK(cudaEventSynchronize(npe[8]));for(int i=0;i<8;++i){float ms=0;CUDA_CHECK(cudaEventElapsedTime(&ms,npe[i],npe[i+1]));nptm[i]+=ms;}++npcalls;np_active=false;};''')
 s=patch(s,'''    if(prof){cudaDeviceSynchronize();t0=now();}
    CUDA_CHECK(cudaMemset(Hcc,0,(size_t)CD*CD*ncam*sizeof(Scalar)));''','''    if(prof){cudaDeviceSynchronize();t0=now();}
    np_active=native_phase_profile; NP(0);
    CUDA_CHECK(cudaMemset(Hcc,0,(size_t)CD*CD*ncam*sizeof(Scalar)));''')
 s=patch(s,'''    // Student-t: refresh the scale from the CURRENT state, then freeze it for
    // this outer.''','''    NP(1);
    // Student-t: refresh the scale from the CURRENT state, then freeze it for
    // this outer.''')
 s=patch(s,'''    if(r2acc) KernelDampIntr9<<<GridSize(ncam),256>>>(Hcc,INTR_F(p,s),r2acc,obscnt,ncam,intr_damp,k2mask);
    pf_obs_dirty=true;''','''    NP(2);
    if(r2acc) KernelDampIntr9<<<GridSize(ncam),256>>>(Hcc,INTR_F(p,s),r2acc,obscnt,ncam,intr_damp,k2mask);
    NP(3);
    pf_obs_dirty=true;''')
 s=patch(s,'''    ++factor_builds;
    if(tau_split){''','''    ++factor_builds;
    NP(4);
    if(tau_split){''')
 s=patch(s,'''    // OCA_RHO_PT=1 (math review 2026-09-02, finding 1):''','''    NP(5);
    // OCA_RHO_PT=1 (math review 2026-09-02, finding 1):''')
 s=patch(s,'''    // bc and corr live in the full space; the reduced rhs is B^T (bc - corr).''','''    NP(6);
    // bc and corr live in the full space; the reduced rhs is B^T (bc - corr).''')
 s=patch(s,'''    cached_tau=tau_eff; cached_floor=selected_floor; cached_pred_pt=pred_pt;''','''    NP(7);
    cached_tau=tau_eff; cached_floor=selected_floor; cached_pred_pt=pred_pt;''')
 s=patch(s,'''    factor_cached=cache_eligible;
    } // factor/RHS rebuild''','''    factor_cached=cache_eligible;
    NP(8); NPFinish();
    } // factor/RHS rebuild''')
 s=patch(s,'''  if(prof) std::printf("  [PROFILE] assembly=%.3fs pointfactor+rhs=%.3fs krylov=%.3fs candidates=%.3fs\\n",
                       t_asm,t_fac,t_mv,t_cand);''','''  if(prof) std::printf("  [PROFILE] assembly=%.3fs pointfactor+rhs=%.3fs krylov=%.3fs candidates=%.3fs\\n",t_asm,t_fac,t_mv,t_cand);
  if(native_phase_profile){std::printf("NATIVE_PHASE calls=%ld clears_ms=%.9g assemble_ms=%.9g intrinsics_damp_ms=%.9g pre_factor_gap_ms=%.9g point_factor_rhs_ms=%.9g reduced_rhs_ms=%.9g equilibration_ms=%.9g finalize_ms=%.9g\\n",npcalls,nptm[0],nptm[1],nptm[2],nptm[3],nptm[4],nptm[5],nptm[6],nptm[7]);for(auto e:npe)cudaEventDestroy(e);}''')
 OUT.parent.mkdir(exist_ok=True);OUT.write_text(s)
 cmd=['nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3','-I/tmp/prism-ba-coarse/research/eta2_champion/source/headers','-I/tmp/prism-ba-coarse/research/eta2_wave5',str(OUT),'-o',str(BIN),'-lcublas','-lcusolver']
 subprocess.run(cmd,check=True)
 (P/'NATIVE_TIMING_BUILD.json').write_text(json.dumps({'base_sha256':EXPECTED,'source_sha256':sha(OUT),'binary_sha256':sha(BIN),'command':cmd},indent=2)+'\n')
if __name__=='__main__':main()
