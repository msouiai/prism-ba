#!/usr/bin/env python3
"""Build the preregistered PCG synchronization/launch overlay."""
from pathlib import Path
import hashlib,json,os,subprocess
P=Path(__file__).resolve().parent;F=P.parent/"eta2_champion"
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def derive():
  original=source=(F/"source"/"prism_eta2.cu").read_text();changes=[]
  def patch(before,after):
    nonlocal source
    assert source.count(before)==1,(before[:100],source.count(before));source=source.replace(before,after);changes.append((before,after))
  patch("""template <int CD>
RunLog SolveMFreeShiftedCG(""","""#include "cg_latency.cuh"
template <int CD>
RunLog SolveMFreeShiftedCG(""")
  patch("""  cublasHandle_t blas; cublasCreate(&blas);
  // ---- robust kernel state""","""  cublasHandle_t blas; cublasCreate(&blas);
  const bool w5_cg_batch=[](){const char* e=getenv("OCA_W5_CG_BATCH");return e&&std::atoi(e)!=0;}();
  cublasHandle_t w5_blas=nullptr;Scalar* w5_dots=nullptr;long w5_dot_pairs=0;
  if(w5_cg_batch){
    if(CD!=9||shared_intr||L!=1||!pcg||block_on||!classical_lm)throw std::runtime_error("B6 batched CG requires champion-like CD9 single-shift PCG");
    cublasCreate(&w5_blas);cublasSetPointerMode(w5_blas,CUBLAS_POINTER_MODE_DEVICE);CUDA_CHECK(cudaMalloc(&w5_dots,2*sizeof(Scalar)));
    std::printf("W5_CG_BATCH active n=%d\\n",n_c);
  }
  // ---- robust kernel state""")
  patch("""      Scalar pAp,pp; cublasDdot(blas,n_c,pv_,1,Ap_,1,&pAp); cublasDdot(blas,n_c,pv_,1,pv_,1,&pp);""","""      Scalar pAp,pp;
      if(w5_cg_batch){
        cublasDdot(w5_blas,n_c,pv_,1,Ap_,1,w5_dots);cublasDdot(w5_blas,n_c,pv_,1,pv_,1,w5_dots+1);
        Scalar h[2];CUDA_CHECK(cudaMemcpy(h,w5_dots,2*sizeof(Scalar),cudaMemcpyDeviceToHost));pAp=h[0];pp=h[1];++w5_dot_pairs;
      }else{cublasDdot(blas,n_c,pv_,1,Ap_,1,&pAp);cublasDdot(blas,n_c,pv_,1,pv_,1,&pp);}""")
  patch("""      cublasDaxpy(blas,n_c,&al,pv_,1,xs[0],1);
      Scalar mal=-al; cublasDaxpy(blas,n_c,&mal,Ap_,1,r_,1);
      Scalar rr_new; cublasDdot(blas,n_c,r_,1,r_,1,&rr_new);
      Scalar be=rr_new/rr;
      if(pcg){pcg->Apply(r_);double next;cublasDdot(blas,n_c,r_,1,pcg->z,1,&next);be=next/pcg->rz;pcg->rz=next;pcg->last_depth=cg_it+1;}""","""      if(w5_cg_batch)W5CgXR<<<GridSize(n_c),256>>>(xs[0],r_,pv_,Ap_,al,n_c);
      else{cublasDaxpy(blas,n_c,&al,pv_,1,xs[0],1);Scalar mal=-al;cublasDaxpy(blas,n_c,&mal,Ap_,1,r_,1);}
      Scalar rr_new,be;
      if(w5_cg_batch){
        pcg->Apply(r_);double next;
        cublasDdot(w5_blas,n_c,r_,1,r_,1,w5_dots);cublasDdot(w5_blas,n_c,r_,1,pcg->z,1,w5_dots+1);
        Scalar h[2];CUDA_CHECK(cudaMemcpy(h,w5_dots,2*sizeof(Scalar),cudaMemcpyDeviceToHost));rr_new=h[0];next=h[1];++w5_dot_pairs;
        be=next/pcg->rz;pcg->rz=next;pcg->last_depth=cg_it+1;
      }else{
        cublasDdot(blas,n_c,r_,1,r_,1,&rr_new);be=rr_new/rr;
        if(pcg){pcg->Apply(r_);double next;cublasDdot(blas,n_c,r_,1,pcg->z,1,&next);be=next/pcg->rz;pcg->rz=next;pcg->last_depth=cg_it+1;}
      }""")
  patch("""      cublasDscal(blas,n_c,&be,pv_,1);
      { const Scalar one=1.0; cublasDaxpy(blas,n_c,&one,pcg?pcg->z:r_,1,pv_,1); }""","""      if(w5_cg_batch)W5CgP<<<GridSize(n_c),256>>>(pv_,pcg?pcg->z:r_,be,n_c);
      else{cublasDscal(blas,n_c,&be,pv_,1);const Scalar one=1.0;cublasDaxpy(blas,n_c,&one,pcg?pcg->z:r_,1,pv_,1);}""")
  patch("""  if(prof) std::printf("  [PROFILE] assembly=%.3fs pointfactor+rhs=%.3fs krylov=%.3fs candidates=%.3fs\\n",
                       t_asm,t_fac,t_mv,t_cand);""","""  if(prof) std::printf("  [PROFILE] assembly=%.3fs pointfactor+rhs=%.3fs krylov=%.3fs candidates=%.3fs\\n",
                       t_asm,t_fac,t_mv,t_cand);
  if(w5_cg_batch)std::printf("W5_CG_BATCH summary dot_pairs=%ld\\n",w5_dot_pairs);""")
  patch("""  cudaFree(s_new.R);cudaFree(s_new.t);cudaFree(s_new.X);cudaFree(s_new.intr);
  cublasDestroy(blas);""","""  cudaFree(s_new.R);cudaFree(s_new.t);cudaFree(s_new.X);cudaFree(s_new.intr);
  cudaFree(w5_dots);if(w5_blas)cublasDestroy(w5_blas);cublasDestroy(blas);""")
  restored=source
  for before,after in reversed(changes):assert restored.count(after)==1;restored=restored.replace(after,before)
  assert restored==original;return source,len(changes)
def main():
  subprocess.run(["python3",str(F/"build.py"),"--check-only"],check=True);build=P/"build";build.mkdir(exist_ok=True)
  src=build/"b6.cu";binary=build/"prism-b6";source,count=derive();src.write_text(source)
  cmd=["nvcc","-O3","-DNDEBUG","-std=c++17","-arch=sm_89","-I/usr/include/eigen3","-I"+str(F/"source"/"headers"),"-I"+str(P),str(src),"-o",str(binary),"-lcublas","-lcusolver"]
  with (build/"b6-build.log").open("w") as log:subprocess.run(cmd,env=dict(os.environ,TMPDIR="/dev/shm"),stdout=log,stderr=subprocess.STDOUT,check=True)
  m={"command":cmd,"source_sha256":sha(src),"binary_sha256":sha(binary),"frozen_source_sha256":sha(F/"source"/"prism_eta2.cu"),"champion_sha256":sha(F/"champion.json"),"reversible_patch_count":count,"sources":{str(P/"build_b6.py"):sha(P/"build_b6.py"),str(P/"cg_latency.cuh"):sha(P/"cg_latency.cuh")},"protocol_sha256":sha(P/"B6_PROTOCOL.md")}
  (P/"b6-build-manifest.json").write_text(json.dumps(m,indent=2)+"\n");print("BUILT B6",m["binary_sha256"])
if __name__=="__main__":main()
