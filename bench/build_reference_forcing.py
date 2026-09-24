#!/usr/bin/env python3
import argparse,json,pathlib,shutil,subprocess
from build_rl_damping import sha
BASE=pathlib.Path('/tmp/prism-ba-accuracy/build')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=pathlib.Path,required=True);a=ap.parse_args()
 m=json.loads((BASE/'manifest.json').read_text());assert sha(BASE/'source.cu')==m['source_sha256']
 assert all(sha(BASE/'headers'/k)==v for k,v in m['headers_sha256'].items())
 a.output.mkdir(parents=True,exist_ok=False);shutil.copytree(BASE/'headers',a.output/'headers')
 shutil.copy2(pathlib.Path(__file__).parents[1]/'gpu/reference_forcing.h',a.output/'headers/reference_forcing.h')
 s=(BASE/'source.cu').read_text()
 def sub(old,new):
  nonlocal s
  assert s.count(old)==1,(old,s.count(old));s=s.replace(old,new)
 sub('#include "ba_accuracy.h"','#include "ba_accuracy.h"\n#include "reference_forcing.h"')
 sub('PrismBAAccuracy bac;','PrismBAAccuracy bac; PrismReferenceForcing rrf; Scalar* reference_E=nullptr;')
 sub('  M((void**)&E,(size_t)n_c*sizeof(Scalar));M((void**)&dk,(size_t)n_cf*sizeof(Scalar));',
 '  M((void**)&E,(size_t)n_c*sizeof(Scalar));M((void**)&dk,(size_t)n_cf*sizeof(Scalar));\n  if(rrf.mode)M((void**)&reference_E,(size_t)n_c*sizeof(Scalar));')
 sub('  if(rld.enabled && (!classical_lm','  if((rld.enabled || rrf.mode) && (!classical_lm')
 sub('  const char* replay_save=rld.enabled?',
 '  if(rrf.mode && (!tau_split || !use_equil || attr_split || getenv("OCA_POLY_CONG") || getenv("OCA_REPLAY_LOAD") || getenv("OCA_REPLAY_SAVE")))throw std::runtime_error("reference forcing requires standard split point factors and diagonal camera metric");\n  const char* replay_save=rld.enabled?')
 sub('    eta=bac.Forcing(k,eta,nb);',r'''    eta=bac.Forcing(k,eta,nb);
    if(rrf.mode && (rrf.NeedQuery(k,numeric_rebuilds) || rrf.verify)){
      if(selected_floor>0)throw std::runtime_error("reference forcing does not support selected point floors");
      auto ref_start=std::chrono::steady_clock::now();
      auto reference_norm_at=[&](double tau,const Scalar* metric){
        MFPointFactorTau<<<GridSize(npt),256>>>(Cdiag,R0f,tau,npt,Rf,okf);
        MFVinvApply<<<GridSize(npt),256>>>(Rf,bp,npt,uu);
        CUDA_CHECK(cudaMemset(corr,0,(size_t)n_cf*sizeof(Scalar)));
        MFRhsPrime<CD,Fragment><<<GridSize(nobs),256>>>(Gp,fragment_cams,fragment_points,uu,nobs,corr);
        CUDA_CHECK(cudaMemcpy(w,bc,(size_t)n_cf*sizeof(Scalar),cudaMemcpyDeviceToDevice));
        const double minus=-1; cublasDaxpy(blas,n_cf,&minus,corr,1,w,1);
        MFScaleVec<<<GridSize(n_c),256>>>(w,metric,n_c);
        double value; cublasDnrm2(blas,n_c,w,1,&value);return value;
      };
      if(rrf.NeedQuery(k,numeric_rebuilds))rrf.Reference(k,reference_norm_at(rrf.previous_tau,reference_E));
      if(rrf.verify){
        double check=reference_norm_at(tau_eff,E),err=std::abs(check-nb)/std::max(1e-100,(double)nb);
        rrf.max_identity_error=std::max(rrf.max_identity_error,err);++rrf.verifications;
        if(!std::isfinite(err)||err>1e-7)throw std::runtime_error("reference RHS identity failed");
      }
      MFPointFactorTau<<<GridSize(npt),256>>>(Cdiag,R0f,tau_eff,npt,Rf,okf);
      CUDA_CHECK(cudaDeviceSynchronize());
      rrf.probe_seconds+=std::chrono::duration<double>(std::chrono::steady_clock::now()-ref_start).count();
    }
    eta=rrf.Forcing(k,eta,numeric_rebuilds);''')
 sub('    if(TargetReached(cost,k+1)) break;',
 '''    if(rrf.Accept(accepted,nb,tau_eff)){CUDA_CHECK(cudaMemcpy(reference_E,E,(size_t)n_c*sizeof(Scalar),cudaMemcpyDeviceToDevice));CUDA_CHECK(cudaDeviceSynchronize());}
    if(TargetReached(cost,k+1)) break;''')
 sub('  cudaFree(bprime);cudaFree(corr);cudaFree(E);cudaFree(dk);',
 '''  if(rrf.mode)std::printf("REFERENCE_SUMMARY mode=%d queries=%ld probe_seconds=%.17g verifications=%ld identity_error=%.17g disabled=%d extra_bytes=%zu\\n",rrf.mode,rrf.queries,rrf.probe_seconds,rrf.verifications,rrf.max_identity_error,(int)rrf.disabled,(size_t)n_c*sizeof(Scalar));
  cudaFree(reference_E);
  cudaFree(bprime);cudaFree(corr);cudaFree(E);cudaFree(dk);''')
 (a.output/'source.cu').write_text(s)
 cmd=['nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3','-I'+str(a.output/'headers'),str(a.output/'source.cu'),'-o',str(a.output/'prism-tr'),'-lcublas','-lcusolver']
 with (a.output/'build.log').open('x') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
 (a.output/'manifest.json').write_text(json.dumps(dict(command=cmd,parent=m,source_sha256=sha(a.output/'source.cu'),binary_sha256=sha(a.output/'prism-tr'),headers_sha256={p.name:sha(p) for p in (a.output/'headers').iterdir() if p.is_file()}),indent=2)+'\n')
if __name__=='__main__':main()
