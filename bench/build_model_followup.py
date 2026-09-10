#!/usr/bin/env python3
"""Isolated model captures and coherent fragment-precision experiment."""
import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess

REPO = pathlib.Path(__file__).resolve().parents[1]
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--base',type=pathlib.Path,default=pathlib.Path('/tmp/prism-model-followup/build'))
    ap.add_argument('--output',type=pathlib.Path,required=True)
    ap.add_argument('--double-fragments',action='store_true')
    a=ap.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    manifest=json.loads((a.base/'manifest.json').read_text())
    assert sha(a.base/'source.cu')==manifest['source_sha256']
    assert all(sha(a.base/'headers'/k)==v for k,v in manifest['headers_sha256'].items())
    shutil.copytree(a.base/'headers',a.output/'headers')
    shutil.copy(REPO/'gpu/model_followup_capture.cuh',a.output/'headers')
    s=(a.base/'source.cu').read_text()
    def sub(old,new):
        nonlocal s
        assert s.count(old)==1,(old,s.count(old));s=s.replace(old,new)
    sub('#include "full_step_model.cuh"','#include "full_step_model.cuh"\n#include "model_followup_capture.cuh"')
    sub('  double lm_nu=2,lm_rho=0,lm_prediction=0;', '''  double lm_nu=2,lm_rho=0,lm_prediction=0;
  const char* model_capture=getenv("OCA_MODEL_CAPTURE");
  int model_good=0,model_bad=0,model_later=0,model_negative=0;
  if(model_capture && (!classical_lm || CD!=9 || shared_intr || mf_fp32 || rk))throw std::runtime_error("model captures require frozen unshared FP64 L2 LM engine");
''')
    sub('      if(backtrack_ready && !have &&\n', '''      if(model_capture){
        const char* tag=nullptr;
        if(!model_good && k==0){tag="opening";++model_good;}
        else if(!model_bad && std::isfinite(c) && c>=cost && k>=3){tag="failed";++model_bad;}
        else if(!model_later && k>=6){tag="later";++model_later;}
        if(tag)PrismModelCapture(std::string(model_capture)+"-"+tag,p,s,dfull,nullptr,k,cost,c,lam_cam,tau_eff);
      }
      if(backtrack_ready && !have &&
''')
    old='      if(!(pAp>1e-14*pp)){ ++st.negcurv; trunc=true; nc_pAp=pAp; nc_pp=pp; break; }   // Steihaug-Toint'
    sub(old,'''      if(!(pAp>1e-14*pp)){
        if(model_capture && model_negative<2){
          // KvS leaves w=E*p and uu=C_tau^-1 W^T w on the frozen diagonal path.
          if(block_on || poly_on || shared_intr)throw std::runtime_error("negative probe requires diagonal coordinates");
          CUDA_CHECK(cudaMemcpy(dfull,w,n_cf*sizeof(double),cudaMemcpyDeviceToDevice));
          CUDA_CHECK(cudaMemcpy(dfull+n_cf,uu,n_p*sizeof(double),cudaMemcpyDeviceToDevice));
          KernelNegateInPlace<<<GridSize(n_p),256>>>(dfull+n_cf,n_p);
          PrismModelCapture(std::string(model_capture)+"-negative-"+std::to_string(++model_negative),p,s,dfull,Cdiag,k,cost,-1,shifts[0],tau_eff,pAp,pp);
        }
        ++st.negcurv; trunc=true; nc_pAp=pAp; nc_pp=pp; break;
      }   // Original Steihaug-Toint test; diagnostic is read-only.
''')
    sub('    if(classical_lm){\n      if(attr_radius){', '''    if(classical_lm){
      if(model_capture)std::printf("MODEL_LINEAR o=%d cg=%d residual=%.17g tolerance=%.17g trunc=%d lambda=%.17g\\n",k,cg_it,std::sqrt(rr)/std::max(1e-300,(double)nb),(double)eta,(int)trunc,(double)lam_cam);
      if(attr_radius){''')
    # A measured-direction repair, not a global positive-definiteness certificate.
    # Keep all policy changes gated; off retains the archived arithmetic and branches.
    sub('  double attr_R=0,attr_old_R=0,attr_norm=0,attr_next_lambda=0,attr_raw_norm=0;', '''  double attr_R=0,attr_old_R=0,attr_norm=0,attr_next_lambda=0,attr_raw_norm=0;
  const bool numeric_guard=getenv("OCA_SCHUR_NUMERIC_GUARD") && atoi(getenv("OCA_SCHUR_NUMERIC_GUARD"))!=0;
  if(numeric_guard && (!attr_radius || !classical_lm || !attr_strict))throw std::runtime_error("numeric guard requires coupled strict radius controller");
  double numeric_floor=1e-16;
  long numeric_rebuilds=0;
''')
    sub('   if(BudgetExpired()){std::printf("BUDGET stop=before_attempt outer=%d seconds=%.9g\\n",k,max_seconds);break;}',
        '   const double numeric_prior_bnorm=prev_bnorm;\n   if(BudgetExpired()){std::printf("BUDGET stop=before_attempt outer=%d seconds=%.9g\\n",k,max_seconds);break;}')
    sub('    if(classical_lm){\n      if(model_capture)', '''    if(numeric_guard && trunc && numeric_rebuilds<32 && nc_pp>0 && std::isfinite(nc_pAp)){
      // In a fixed Schur matrix, this raises the failed Rayleigh quotient
      // strictly above zero. Rebuild point damping as well: the actual next
      // system is coupled and must be checked again, not assumed SPD.
      const double repaired=std::clamp(4.*std::max((double)lam_cam,(double)lam_cam-nc_pAp/nc_pp),1e-14,1e16);
      if(repaired>lam_cam){
        numeric_floor=std::max(numeric_floor,repaired);
        std::printf("NUMERIC_REPAIR o=%d lambda=%.17g rayleigh=%.17g next_lambda=%.17g cg=%d rebuild=%ld\\n",k,(double)lam_cam,nc_pAp/nc_pp,numeric_floor,cg_it,++numeric_rebuilds);
        lam_cam=numeric_floor;prev_bnorm=numeric_prior_bnorm;need_assembly=false;factor_cached=false;
        continue;
      }
    }
    if(classical_lm){
      if(model_capture)''')
    sub('        attr_next_lambda=std::clamp(attr_next_lambda,1e-16,1e16);',
        '        attr_next_lambda=std::clamp(attr_next_lambda,numeric_guard?numeric_floor:1e-16,1e16);')
    sub('  if(prof) std::printf("  [PROFILE] assembly=',
        '  if(numeric_guard)std::printf("NUMERIC_REPAIR summary rebuilds=%ld floor=%.17g\\n",numeric_rebuilds,numeric_floor);\n  if(prof) std::printf("  [PROFILE] assembly=')
    if a.double_fragments:
        sub('  using Fragment = float;','  using Fragment = double;')
        sub('MFRhsDiagFused<<<GridSize(nobs),256>>>(mf_fp32?Gp32:Gp,fragment_cams,fragment_points,Rf,uu,nobs,corr,dk);',
            'if(mf_fp32)MFRhsDiagFused<<<GridSize(nobs),256>>>(Gp32,fragment_cams,fragment_points,Rf,uu,nobs,corr,dk); else MFRhsDiagFused<<<GridSize(nobs),256>>>(Gp,fragment_cams,fragment_points,Rf,uu,nobs,corr,dk);')
        # Make the three optimized helpers generic; arithmetic and guards stay identical.
        p=a.output/'headers/point_prep_candidate.cuh';h=p.read_text()
        h=h.replace('__global__ void MFPointFactorGuarded(const float* Bo', 'template<class F> __global__ void MFPointFactorGuarded(const F* Bo')
        h=h.replace('__global__ void MFRhsDiagFused(const float* W', 'template<class F> __global__ void MFRhsDiagFused(const F* W')
        p.write_text(h)
        p=a.output/'headers/pcg_camera.cuh';h=p.read_text()
        h=h.replace(' void Prepare(', ' template<class F> void Prepare(').replace('const float*W','const F*W').replace('MFBlockSchurCM<9,float>','MFBlockSchurCM<9,F>')
        p.write_text(h)
        s=s.replace('storage=fp32 camera_reads=', 'storage=fp64 camera_reads=')
    (a.output/'source.cu').write_text(s)
    cmd=['nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3','-I'+str(a.output/'headers'),str(a.output/'source.cu'),'-o',str(a.output/'prism-tr'),'-lcublas','-lcusolver']
    with (a.output/'build.log').open('x') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
    (a.output/'manifest.json').write_text(json.dumps(dict(command=cmd,parent_binary=manifest['binary_sha256'],source_sha256=sha(a.output/'source.cu'),binary_sha256=sha(a.output/'prism-tr'),headers_sha256={p.name:sha(p) for p in (a.output/'headers').iterdir()},double_fragments=a.double_fragments),indent=2)+'\n')
    print(a.output/'prism-tr',flush=True)

if __name__=='__main__':main()
