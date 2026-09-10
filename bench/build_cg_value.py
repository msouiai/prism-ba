#!/usr/bin/env python3
import argparse,json,pathlib,shutil,subprocess
from build_rl_damping import sha
BASE=pathlib.Path('/tmp/prism-reference-forcing/build-v2')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=pathlib.Path,required=True);a=ap.parse_args()
 m=json.loads((BASE/'manifest.json').read_text());assert sha(BASE/'source.cu')==m['source_sha256']
 assert all(sha(BASE/'headers'/k)==v for k,v in m['headers_sha256'].items())
 a.output.mkdir(parents=True,exist_ok=False);shutil.copytree(BASE/'headers',a.output/'headers')
 shutil.copy2(pathlib.Path(__file__).parents[1]/'gpu/cg_value.h',a.output/'headers/cg_value.h')
 s=(BASE/'source.cu').read_text()
 def sub(old,new):
  nonlocal s
  assert s.count(old)==1,(old,s.count(old));s=s.replace(old,new)
 sub('#include "reference_forcing.h"','#include "reference_forcing.h"\n#include "cg_value.h"')
 sub('PrismBAAccuracy bac;','PrismCGValue cgv; std::chrono::steady_clock::time_point cgv_attempt,cgv_cg,cgv_post;\n  PrismBAAccuracy bac;')
 sub('if((rld.enabled || rrf.mode) &&','if((rld.enabled || rrf.mode || cgv.mode) &&')
 sub('   const double numeric_prior_bnorm=prev_bnorm;',
     '   if(cgv.mode)cgv_attempt=std::chrono::steady_clock::now();\n   const double numeric_prior_bnorm=prev_bnorm;')
 sub('    if(rld.collect)rld.ResetCG();','''    if(rld.collect)rld.ResetCG();
    if(cgv.mode){cgv_cg=std::chrono::steady_clock::now();cgv.Begin(std::chrono::duration<double>(cgv_cg-cgv_attempt).count(),retries,numeric_rebuilds);}''')
 sub('      Scalar al=(pcg?pcg->rz:rr)/pAp;',
     '      Scalar al=(pcg?pcg->rz:rr)/pAp;\n      const double cgv_delta=cgv.mode?.5*al*(pcg?pcg->rz:rr):0.;')
 sub('      if(sqrt(rr_new)<=eta*nb){',r'''      bool cgv_stop=false;
      if(cgv.mode){
        cgv_stop=cgv.Observe(cgv_delta,std::chrono::duration<double>(std::chrono::steady_clock::now()-cgv_cg).count(),std::sqrt(rr_new)/std::max(1e-300,(double)nb),eta);
        if(cgv.verify){
          KvS(xs[0],pcg->tmp);
          cublasDaxpy(blas,n_c,&shifts[0],xs[0],1,pcg->tmp,1);
          double bx,xa;cublasDdot(blas,n_c,bprime,1,xs[0],1,&bx);cublasDdot(blas,n_c,xs[0],1,pcg->tmp,1,&xa);
          double direct=bx-.5*xa,err=std::abs(direct-cgv.gain)/std::max(1.,std::abs(direct));
          cgv.max_error=std::max(cgv.max_error,err);++cgv.checks;
          if(!std::isfinite(err)||err>1e-6)throw std::runtime_error("CG accumulated model gain identity failed");
        }
      }
      const double cgv_stop_eta=cgv_stop?.5:(double)eta;
      if(cgv_stop || sqrt(rr_new)<=eta*nb){''')
 sub('true_norm>1.01*eta*nb','true_norm>1.01*cgv_stop_eta*nb')
 sub('    if(classical_lm){\n      if(model_capture)',
     '    if(cgv.mode)cgv_post=std::chrono::steady_clock::now();\n    if(classical_lm){\n      if(model_capture)')
 sub('    // OCA_LEARN_LOG: one record per attempt, after the accept/reject decision',
     '''    if(cgv.mode)cgv.Finish(accepted,lm_rho,std::chrono::duration<double>(std::chrono::steady_clock::now()-cgv_post).count());
    // OCA_LEARN_LOG: one record per attempt, after the accept/reject decision''')
 sub('  cudaFree(reference_E);',
 '''  if(cgv.mode)std::printf("CG_VALUE_SUMMARY mode=%d attempts=%ld observations=%ld proposals=%ld stops=%ld checks=%ld identity_error=%.17g disabled=%d extra_bytes=0\\n",cgv.mode,cgv.attempts,cgv.observations,cgv.proposals,cgv.stops,cgv.checks,cgv.max_error,(int)cgv.disabled);
  cudaFree(reference_E);''')
 (a.output/'source.cu').write_text(s)
 cmd=['nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3','-I'+str(a.output/'headers'),str(a.output/'source.cu'),'-o',str(a.output/'prism-tr'),'-lcublas','-lcusolver']
 with (a.output/'build.log').open('x') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
 (a.output/'manifest.json').write_text(json.dumps(dict(command=cmd,parent=m,source_sha256=sha(a.output/'source.cu'),binary_sha256=sha(a.output/'prism-tr'),headers_sha256={p.name:sha(p) for p in (a.output/'headers').iterdir() if p.is_file()}),indent=2)+'\n')
if __name__=='__main__':main()
