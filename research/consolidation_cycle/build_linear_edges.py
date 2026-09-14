#!/usr/bin/env python3
"""Build a default-off linear-edge derivative without editing frozen Eta2."""
from pathlib import Path
import argparse,hashlib,json,os,subprocess

P=Path(__file__).resolve().parent; R=P.parent.parent
F=R/"research/eta2_champion/source/prism_eta2.cu"; OUT=P/"build"
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def replace(s,a,b):
  assert s.count(a)==1,(a[:80],s.count(a)); return s.replace(a,b)

def derive(base=None):
  s=F.read_text() if base is None else base
  s=replace(s,'#include "bal_hessian_generated.cuh"','#include "bal_hessian_generated.cuh"\n#include "linear_edge_math.h"')
  norm_call="PrismW6Dnrm2" if "PrismW6Dnrm2(blas,n_c,bprime" in s else "cublasDnrm2"
  dot_call="PrismW6Ddot" if "PrismW6Ddot(blas,n_c,r_" in s else "cublasDdot"
  norm_block='''    static const bool audit_linear_edges=[](){const char* e=getenv("OCA_AUDIT_LINEAR_EDGES");return e&&std::atoi(e)!=0;}();
    #ifdef PRISM_LINEAR_EDGE_TEST_FIXTURE
    static const bool audit_zero_fixture=[](){const char* e=getenv("OCA_AUDIT_ZERO_RHS_FIXTURE");return e&&std::atoi(e)!=0;}();
    if(audit_zero_fixture){if(!audit_linear_edges)throw std::runtime_error("zero fixture requires linear edges");CUDA_CHECK(cudaMemset(bprime,0,(size_t)n_c*sizeof(Scalar)));}
    #endif
    Scalar nb; bool audit_rhs_all_zero=false;
    if(audit_linear_edges){
      std::vector<Scalar> audit_rhs((size_t)n_c);CUDA_CHECK(cudaMemcpy(audit_rhs.data(),bprime,(size_t)n_c*sizeof(Scalar),cudaMemcpyDeviceToHost));
      const auto nr=prism_linear_edges::ScaledFiniteNorm(audit_rhs.data(),audit_rhs.size());nb=nr.norm;audit_rhs_all_zero=nr.all_zero;
    } else NORM_CALL(blas,n_c,bprime,1,&nb);'''.replace("NORM_CALL",norm_call)
  s=replace(s,f'    Scalar nb; {norm_call}(blas,n_c,bprime,1,&nb);',norm_block)
  s=replace(s,'''    Scalar eta = ew_eta_max;
    if(prev_bnorm>0.0){ Scalar q=(nb*nb)/(prev_bnorm*prev_bnorm); eta=std::min(ew_eta_max,(Scalar)0.9*q); }
    if(rld.enabled)eta=rld.Forcing(eta);''','''    if(audit_linear_edges&&!std::isfinite(prev_bnorm))throw std::runtime_error("nonfinite reduced-RHS norm history");
    const bool audit_zero_rhs=audit_linear_edges&&audit_rhs_all_zero&&pcg&&classical_lm&&L==1&&CD==9&&!shared_intr&&!block_on;
    Scalar eta=ew_eta_max;
    if(prev_bnorm>0.0){Scalar q=audit_linear_edges?prism_linear_edges::ForcingRatioSquared(nb,prev_bnorm):(nb*nb)/(prev_bnorm*prev_bnorm);eta=std::min(ew_eta_max,(Scalar)0.9*q);}
    if(rld.enabled)eta=rld.Forcing(eta);''')
  old_pcg='''    if(pcg){
      if(L!=1||CD!=9||shared_intr||block_on||(!camera_tr&&!classical_lm))throw std::runtime_error("PCG requires guarded unshared 9DOF single-shift diagonal-coordinate TR");
      pcg->Prepare(Hcc,E,shifts[0],k,retries,Gp,fragment_points,p.mf_coff,Rf,nobs);pcg->Apply(r_);DOT_CALL(blas,n_c,r_,1,pcg->z,1,&pcg->rz);CUDA_CHECK(cudaMemcpy(pv_,pcg->z,n_c*8ul,cudaMemcpyDeviceToDevice));
    }'''.replace("DOT_CALL",dot_call)
  new_pcg='''    if(pcg){
      if(L!=1||CD!=9||shared_intr||block_on||(!camera_tr&&!classical_lm))throw std::runtime_error("PCG requires guarded unshared 9DOF single-shift diagonal-coordinate TR");
      if(!audit_zero_rhs){pcg->Prepare(Hcc,E,shifts[0],k,retries,Gp,fragment_points,p.mf_coff,Rf,nobs);pcg->Apply(r_);DOT_CALL(blas,n_c,r_,1,pcg->z,1,&pcg->rz);CUDA_CHECK(cudaMemcpy(pv_,pcg->z,n_c*8ul,cudaMemcpyDeviceToDevice));}
    }
    if(audit_zero_rhs){cg_broke=true;if(verbose)std::printf("    [linear-edge] exact zero reduced RHS: converged at depth 0\\n");}'''.replace("DOT_CALL",dot_call)
  s=replace(s,old_pcg,new_pcg)
  s=replace(s,'    for(cg_it=0; cg_it<maxck; ++cg_it){','    for(cg_it=0; !audit_zero_rhs && cg_it<maxck; ++cg_it){')
  s=replace(s,'      Score(xs[0],0,cg_broke?cg_it+1:maxck);','      Score(xs[0],0,audit_zero_rhs?0:(cg_broke?cg_it+1:maxck));')
  return s

def main():
  ap=argparse.ArgumentParser();ap.add_argument("--fixture",action="store_true");args=ap.parse_args()
  OUT.mkdir(exist_ok=True); suffix="-fixture" if args.fixture else ""
  src=OUT/("prism_linear_edges"+suffix+".cu"); binary=OUT/("prism-linear-edges"+suffix);src.write_text(derive())
  cmd=["nvcc","-O3","-DNDEBUG","-std=c++17","-arch=sm_89"]
  if args.fixture:cmd.append("-DPRISM_LINEAR_EDGE_TEST_FIXTURE=1")
  cmd += ["-I/usr/include/eigen3","-I"+str(P),"-I"+str(R/"gpu"),"-I"+str(R/"research/eta2_champion/source/headers"),str(src),"-o",str(binary),"-lcublas","-lcusolver"]
  subprocess.run(cmd,env=dict(os.environ,TMPDIR="/dev/shm"),check=True)
  manifest={"base":"d3d42dcb803f104424a3343364cac414a7ab7342","frozen_sha256":sha(F),"source_sha256":sha(src),"binary_sha256":sha(binary),"helper_sha256":sha(P/"linear_edge_math.h"),"builder_sha256":sha(__file__),"command":cmd}
  (OUT/("manifest"+suffix+".json")).write_text(json.dumps(manifest,indent=2)+"\n")
if __name__=="__main__":main()
