import pathlib,shutil,json,subprocess
from build_tr_candidate import sha
base=pathlib.Path('/workspace/prism-tr-preconditioner/pcg-v2');root=pathlib.Path('/workspace/prism-tr-novelty-ablation/build');root.mkdir();m=json.loads((base/'stop-manifest.json').read_text());assert sha(base/'source.cu')==m['source_sha256'];assert all(sha(base/'headers'/k)==v for k,v in m['headers_sha256'].items());shutil.copytree(base/'headers',root/'headers');s=(base/'source.cu').read_text()
def sub(a,b):
 global s
 assert s.count(a)==1,(a,s.count(a));s=s.replace(a,b)
sub('  const bool camera_tr=getenv(', '  const bool classical_lm=getenv("OCA_CLASSICAL_LM")!=nullptr;\n  double lm_nu=2,lm_rho=0,lm_prediction=0;\n  const bool camera_tr=getenv(')
sub('  if(full_model_rho || camera_tr)full_model=', '  if(full_model_rho || camera_tr || classical_lm)full_model=')
sub('if(!camera_tr || mf_fp32) throw', 'if((!camera_tr && !classical_lm) || mf_fp32) throw')
sub('subspace_mode || backtrack_policy || point_safeguard_mode!=1 ||','subspace_mode || backtrack_policy || (point_safeguard_mode!=0 && point_safeguard_mode!=1) ||')
sub('    if(point_trust_tau>0)tau_eff=point_trust_tau;', '    if(point_trust_tau>0)tau_eff=point_trust_tau;\n    if(classical_lm)tau_eff=lam_cam;')
sub('      MFDiagHcc<CD><<<GridSize(ncam),256>>>(Hcc,ncam,dk);','      if(classical_lm)CUDA_CHECK(cudaMemset(dk,0,(size_t)n_cf*sizeof(Scalar)));\n      MFDiagHcc<CD><<<GridSize(ncam),256>>>(Hcc,ncam,dk);')
sub('    for(int l=0;l<L;++l) shifts[l]=lam_cam*std::pow(10.0,(double)(l-grid_down));','    for(int l=0;l<L;++l) shifts[l]=classical_lm?lam_cam:lam_cam*std::pow(10.0,(double)(l-grid_down));')
sub('if(L!=1||CD!=9||shared_intr||block_on||!cg_projection)throw','if(L!=1||CD!=9||shared_intr||block_on||(!camera_tr&&!classical_lm))throw')
sub('      while(ci_<ckpts_eff.size() && cg_it+1==ckpts_eff[ci_]){','      while(!classical_lm && ci_<ckpts_eff.size() && cg_it+1==ckpts_eff[ci_]){')
sub('    if(trunc){ ScoreAll(cg_it); }','    if(classical_lm){Score(xs[0],0,cg_broke?cg_it+1:maxck);}\n    else if(trunc){ ScoreAll(cg_it); }')
sub('    // ---- accept / reject (existing rule) ----','''    if(classical_lm){
      auto model=full_model->Evaluate(p,s,have?d_best:dfull,k2mask);++full_model_calls;
      lm_prediction=model.prediction;lm_rho=have&&lm_prediction>0?(cost-best_cost)/lm_prediction:-1;
      have=have&&std::isfinite(lm_rho)&&lm_prediction>0&&lm_rho>0;
      std::printf("CLASSICAL_LM o=%d lambda=%.17g tau=%.17g prediction=%.17g rho=%.17g accept=%d\\n",k,(double)lam_cam,(double)tau_eff,lm_prediction,lm_rho,(int)have);
    }
    // ---- accept / reject (existing rule) ----''')
sub('      if(camera_tr){\n        const double anchor=', '''      if(classical_lm){
        double f=std::max(1./3.,1.-std::pow(2*lm_rho-1.,3.));lam_cam=std::clamp((double)lam_cam*f,1e-16,1e16);lm_nu=2;
      }
      else if(camera_tr){
        const double anchor=''')
sub('      if(!camera_tr)lam_cam*=(Scalar)esc; ++n_reject; ++rej_streak;', '      if(classical_lm){lam_cam=std::min(1e16,(double)lam_cam*lm_nu);lm_nu=std::min(1e8,lm_nu*2);}\n      else if(!camera_tr)lam_cam*=(Scalar)esc; ++n_reject; ++rej_streak;')
# Camera diagonal scaling is based on Hcc in LM; fused kernel work retained for a conservative implementation match.
# Guard the baseline against accidental inheritance of hybrid controllers.
sub('  const int recycle_mode=getenv(', '''  if(classical_lm && (camera_tr || point_safeguard_mode || backtrack_on || tr_fast_model || full_model_rho || L!=1 || CD!=9 || shared_intr || !use_equil || !pcg))throw std::runtime_error("classical LM requires plain 9DOF single-shift PCG with no TR/safeguard/backtracking");
  const int recycle_mode=getenv(''')
(root/'source.cu').write_text(s);cmd=['nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3','-I'+str(root/'headers'),str(root/'source.cu'),'-o',str(root/'prism-tr'),'-lcublas','-lcusolver'];
with (root/'build.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
(root/'manifest.json').write_text(json.dumps(dict(command=cmd,source_sha256=sha(root/'source.cu'),binary_sha256=sha(root/'prism-tr'),headers_sha256={p.name:sha(p) for p in (root/'headers').iterdir()},parent=m['source_sha256'],scope='Frozen winner plus isolated classical LM switch and relaxed safeguard/projection ablation guards. Same kernels and PCG. LM: point damping=lambda, camera damping=lambda*diag(Hcc), Nielsen updates, one terminal step, full GN prediction, no point safeguard or backtracking. Existing numerical diagonal floors retained.'),indent=2))
