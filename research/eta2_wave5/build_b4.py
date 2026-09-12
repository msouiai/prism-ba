#!/usr/bin/env python3
"""Build the preregistered small dense-Schur dispatch overlay."""
from pathlib import Path
import hashlib, json, os, subprocess

P=Path(__file__).resolve().parent;F=P.parent/"eta2_champion"
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def derive():
    original=source=(F/"source"/"prism_eta2.cu").read_text();changes=[]
    def patch(before,after):
        nonlocal source
        assert source.count(before)==1,(before[:100],source.count(before))
        source=source.replace(before,after);changes.append((before,after))
    patch("""template <int CD, class HT>
__global__ void MFPass1(""","""#include "direct_schur.cuh"
template <int CD, class HT>
__global__ void MFPass1(""")
    patch("""  cublasHandle_t blas; cublasCreate(&blas);
  // ---- robust kernel state""","""  cublasHandle_t blas; cublasCreate(&blas);
  const int w5_direct_max=[](){const char* e=getenv("OCA_W5_DIRECT_MAX");return e?std::atoi(e):0;}();
  const bool w5_direct=w5_direct_max>0 && n_c<=w5_direct_max;
  if(w5_direct && (CD!=9 || shared_intr || compact_mode!=2 || mf_fp32 || L!=1 || !use_equil || !classical_lm))
    throw std::runtime_error("B4 direct dispatch requires champion-like unshared CD9 compact2 FP64 single-shift classical LM");
  Scalar *w5_S=nullptr,*w5_audit_mv=nullptr,*w5_audit_dense=nullptr;
  cusolverDnHandle_t w5_solver=nullptr;std::unique_ptr<CholeskyWorkspace>w5_ws;
  long w5_solves=0,w5_fallbacks=0;double w5_form_s=0,w5_factor_s=0;
  if(w5_direct){
    CUDA_CHECK(cudaMalloc(&w5_S,(size_t)n_c*n_c*sizeof(Scalar)));
    cusolverDnCreate(&w5_solver);w5_ws=std::make_unique<CholeskyWorkspace>();w5_ws->Init(w5_solver,n_c);
    if(getenv("OCA_W5_DIRECT_AUDIT")){CUDA_CHECK(cudaMalloc(&w5_audit_mv,n_c*sizeof(Scalar)));CUDA_CHECK(cudaMalloc(&w5_audit_dense,n_c*sizeof(Scalar)));}
    std::printf("W5_DIRECT active n_c=%d threshold=%d dense_mib=%.3f\\n",n_c,w5_direct_max,(double)((size_t)n_c*n_c*sizeof(Scalar))/1048576.0);
  }
  // ---- robust kernel state""")
    patch("""    if(!projected_ok){
    if(recycle_mode){""","""    if(!projected_ok && w5_direct){
      if(prof){cudaDeviceSynchronize();t0=now();}
      CUDA_CHECK(cudaMemset(w5_S,0,(size_t)n_c*n_c*sizeof(Scalar)));
      W5DenseInit<CD><<<GridSize(ncam*CD*CD),256>>>(Hcc,E,shifts[0],ncam,n_c,w5_S);
      W5DenseDiag<CD,Fragment><<<ncam,96>>>(Gp,p.mf_cspt,p.mf_coff,Rf,E,nobs,n_c,w5_S);
      W5DenseEdges<CD,Fragment><<<p.n_edges,96>>>(Gp,p.pt_idx,fragment_o2slot,p.edge_ci,p.edge_cj,
        p.edge_offsets,p.edge_obs_d,p.edge_obs_e,Rf,E,p.n_edges,nobs,n_c,w5_S);
      if(prof){cudaDeviceSynchronize();w5_form_s+=std::chrono::duration<double>(now()-t0).count();t0=now();}
      if(w5_audit_mv && w5_solves==0){
        KvS(bprime,w5_audit_mv);{const Scalar sh=shifts[0];cublasDaxpy(blas,n_c,&sh,bprime,1,w5_audit_mv,1);}const Scalar one=1,zero=0;
        CUBLAS_CHECK(cublasDgemv(blas,CUBLAS_OP_N,n_c,n_c,&one,w5_S,n_c,bprime,1,&zero,w5_audit_dense,1));
        W5DenseDifference<<<GridSize(n_c),256>>>(w5_audit_dense,w5_audit_mv,Ap_,n_c);
        Scalar nd=0,nr=0;cublasDnrm2(blas,n_c,Ap_,1,&nd);cublasDnrm2(blas,n_c,w5_audit_mv,1,&nr);
        std::printf("W5_DIRECT_AUDIT relative_l2=%.17g absolute_l2=%.17g reference_l2=%.17g\\n",(double)(nd/std::max(nr,(Scalar)1e-300)),(double)nd,(double)nr);
      }
      const bool pd=CholeskyFactor(*w5_ws,w5_S);
      if(pd){
        CUDA_CHECK(cudaMemcpy(xs[0],bprime,(size_t)n_c*sizeof(Scalar),cudaMemcpyDeviceToDevice));
        CholeskySolveVec(*w5_ws,w5_S,xs[0]);++w5_solves;
        Scalar bd=0;cublasDdot(blas,n_c,bprime,1,xs[0],1,&bd);preds[0]=.5*bd;
        if(attr_radius){
          cublasDnrm2(blas,n_c,xs[0],1,&attr_raw_norm);
          if(!(attr_R>0))attr_R=std::isfinite(attr_raw_norm)&&attr_raw_norm>0?attr_raw_norm:1;
          attr_old_R=attr_R;
          if(attr_raw_norm>attr_R){double scale=attr_R/attr_raw_norm;cublasDscal(blas,n_c,&scale,xs[0],1);}
        }
        Score(xs[0],0,-4);projected_ok=true;cg_broke=true;cg_it=0;
      }else{++w5_fallbacks;std::printf("W5_DIRECT fallback reason=potrf outer=%d retry=%d\\n",k,retries);}
      if(prof){cudaDeviceSynchronize();w5_factor_s+=std::chrono::duration<double>(now()-t0).count();}
    }
    if(!projected_ok){
    if(recycle_mode){""")
    patch("""    if (build_edge_csr && algo == "oca_round2") {""","""    if ((build_edge_csr && algo == "oca_round2") ||
        (algo == "mfree_shifted_cg" && std::getenv("OCA_W5_DIRECT_MAX") &&
         9*ncam <= std::atoi(std::getenv("OCA_W5_DIRECT_MAX")))) {""")
    patch("""  if(prof) std::printf("  [PROFILE] assembly=%.3fs pointfactor+rhs=%.3fs krylov=%.3fs candidates=%.3fs\\n",
                       t_asm,t_fac,t_mv,t_cand);""","""  if(prof) std::printf("  [PROFILE] assembly=%.3fs pointfactor+rhs=%.3fs krylov=%.3fs candidates=%.3fs\\n",
                       t_asm,t_fac,t_mv,t_cand);
  if(w5_direct)std::printf("W5_DIRECT summary solves=%ld fallbacks=%ld form_seconds=%.9g factor_solve_seconds=%.9g\\n",
                           w5_solves,w5_fallbacks,w5_form_s,w5_factor_s);""")
    patch("""  cudaFree(s_new.R);cudaFree(s_new.t);cudaFree(s_new.X);cudaFree(s_new.intr);
  cublasDestroy(blas);""","""  cudaFree(s_new.R);cudaFree(s_new.t);cudaFree(s_new.X);cudaFree(s_new.intr);
  cudaFree(w5_S);cudaFree(w5_audit_mv);cudaFree(w5_audit_dense);
  if(w5_ws){cudaFree(w5_ws->d_work);cudaFree(w5_ws->d_info);}if(w5_solver)cusolverDnDestroy(w5_solver);
  cublasDestroy(blas);""")
    restored=source
    for before,after in reversed(changes):assert restored.count(after)==1;restored=restored.replace(after,before)
    assert restored==original
    return source,len(changes)

def main():
    subprocess.run(["python3",str(F/"build.py"),"--check-only"],check=True)
    build=P/"build";build.mkdir(exist_ok=True);src=build/"b4.cu";binary=build/"prism-b4"
    source,count=derive();src.write_text(source)
    command=["nvcc","-O3","-DNDEBUG","-std=c++17","-arch=sm_89","-I/usr/include/eigen3",
      "-I"+str(F/"source"/"headers"),"-I"+str(P),str(src),"-o",str(binary),"-lcublas","-lcusolver"]
    with (build/"b4-build.log").open("w") as log:
      subprocess.run(command,env=dict(os.environ,TMPDIR="/dev/shm"),stdout=log,stderr=subprocess.STDOUT,check=True)
    manifest={"command":command,"source_sha256":sha(src),"binary_sha256":sha(binary),
      "frozen_source_sha256":sha(F/"source"/"prism_eta2.cu"),"champion_sha256":sha(F/"champion.json"),
      "reversible_patch_count":count,"sources":{str(P/"build_b4.py"):sha(P/"build_b4.py"),str(P/"direct_schur.cuh"):sha(P/"direct_schur.cuh")},
      "protocol_sha256":sha(P/"B4_PROTOCOL.md")}
    (P/"b4-build-manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print("BUILT B4",manifest["binary_sha256"],flush=True)
if __name__=="__main__":main()
