#!/usr/bin/env python3
"""Build default-off code, math, or combined agent-audit derivatives."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import subprocess

P = Path(__file__).resolve().parent
R = P.parent.parent
W5 = R / "research/eta2_wave5"
W6 = R / "research/eta2_wave6"
F = R / "research/eta2_champion"

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def math_patch(source):
    changes=[]
    def patch(before, after):
        nonlocal source
        assert source.count(before)==1, (before[:100], source.count(before))
        source=source.replace(before,after);changes.append((before,after))
    patch('#include "bal_hessian_generated.cuh"',
          '#include "bal_hessian_generated.cuh"\n#include "linear_edge_math.h"')
    patch('''    Scalar eta = ew_eta_max;
    if(prev_bnorm>0.0){ Scalar q=(nb*nb)/(prev_bnorm*prev_bnorm); eta=std::min(ew_eta_max,(Scalar)0.9*q); }
    if(rld.enabled)eta=rld.Forcing(eta);''',
          '''    if(audit_linear_edges && (!std::isfinite(nb)||!std::isfinite(prev_bnorm)))
      throw std::runtime_error("nonfinite reduced-RHS norm history");
    const bool audit_zero_rhs=audit_linear_edges && pcg && classical_lm && L==1 && CD==9 &&
      !shared_intr && !block_on && (camera_tr||classical_lm) &&
      prism_agent_audit::IsExactZeroReducedRhs(nb);
    Scalar eta = ew_eta_max;
    if(prev_bnorm>0.0){ Scalar q=audit_linear_edges
        ? prism_agent_audit::ForcingRatioSquared(nb,prev_bnorm)
        : (nb*nb)/(prev_bnorm*prev_bnorm);
      eta=std::min(ew_eta_max,(Scalar)0.9*q); }
    if(rld.enabled)eta=rld.Forcing(eta);''')
    dot_call = "PrismW6Ddot" if "PrismW6Ddot(blas,n_c,r_,1,pcg->z" in source else "cublasDdot"
    norm_call = "PrismW6Dnrm2" if "PrismW6Dnrm2(blas,n_c,bprime" in source else "cublasDnrm2"
    patch('''    CUDA_CHECK(cudaMemcpy(r_,bprime,(size_t)n_c*sizeof(Scalar),cudaMemcpyDeviceToDevice));''',
          '''    if(getenv("OCA_AUDIT_ZERO_RHS_FIXTURE")){
      const char* edge=getenv("OCA_AUDIT_LINEAR_EDGES");
      if(!edge||std::atoi(edge)==0)throw std::runtime_error("zero RHS fixture requires OCA_AUDIT_LINEAR_EDGES");
      CUDA_CHECK(cudaMemset(bprime,0,(size_t)n_c*sizeof(Scalar)));
    }
    CUDA_CHECK(cudaMemcpy(r_,bprime,(size_t)n_c*sizeof(Scalar),cudaMemcpyDeviceToDevice));''')
    patch(f'''    Scalar nb; {norm_call}(blas,n_c,bprime,1,&nb);''',
          f'''    static const bool audit_linear_edges=[](){{const char* e=getenv("OCA_AUDIT_LINEAR_EDGES");return e&&std::atoi(e)!=0;}}();
    Scalar nb; {norm_call}(blas,n_c,bprime,1,&nb);
    if(audit_linear_edges && (!std::isfinite(nb)||nb==0.0)){{
      std::vector<Scalar> audit_rhs((size_t)n_c);
      CUDA_CHECK(cudaMemcpy(audit_rhs.data(),bprime,(size_t)n_c*sizeof(Scalar),cudaMemcpyDeviceToHost));
      nb=prism_agent_audit::StableFiniteNorm(audit_rhs.data(),audit_rhs.size());
    }}''')
    patch(f'''    if(pcg){{
      if(L!=1||CD!=9||shared_intr||block_on||(!camera_tr&&!classical_lm))throw std::runtime_error("PCG requires guarded unshared 9DOF single-shift diagonal-coordinate TR");
      pcg->Prepare(Hcc,E,shifts[0],k,retries,Gp,fragment_points,p.mf_coff,Rf,nobs);pcg->Apply(r_);{dot_call}(blas,n_c,r_,1,pcg->z,1,&pcg->rz);CUDA_CHECK(cudaMemcpy(pv_,pcg->z,n_c*8ul,cudaMemcpyDeviceToDevice));
    }}''',
          f'''    if(pcg){{
      if(L!=1||CD!=9||shared_intr||block_on||(!camera_tr&&!classical_lm))throw std::runtime_error("PCG requires guarded unshared 9DOF single-shift diagonal-coordinate TR");
      if(!audit_zero_rhs){{pcg->Prepare(Hcc,E,shifts[0],k,retries,Gp,fragment_points,p.mf_coff,Rf,nobs);pcg->Apply(r_);{dot_call}(blas,n_c,r_,1,pcg->z,1,&pcg->rz);CUDA_CHECK(cudaMemcpy(pv_,pcg->z,n_c*8ul,cudaMemcpyDeviceToDevice));}}
    }}
    if(audit_zero_rhs){{cg_broke=true;if(verbose)std::printf("    [linear-edge] exact zero reduced RHS: converged at depth 0\\n");}}''')
    patch('''    for(cg_it=0; cg_it<maxck; ++cg_it){''','''    for(cg_it=0; !audit_zero_rhs && cg_it<maxck; ++cg_it){''')
    patch('''      Score(xs[0],0,cg_broke?cg_it+1:maxck);''','''      Score(xs[0],0,audit_zero_rhs?0:(cg_broke?cg_it+1:maxck));''')
    restored=source
    for before,after in reversed(changes): restored=restored.replace(after,before)
    return source,len(changes)

def workspace_patch(source):
    changes=[]
    def patch(before,after):
        nonlocal source
        assert source.count(before)==1,(before[:100],source.count(before))
        source=source.replace(before,after);changes.append((before,after))
    patch('''#include "deterministic_cost.cuh"''','''#define PRISM_AUDIT_WORKSPACE 1
#include "deterministic_cost.cuh"''')
    patch('''  int *edge_obs_d = nullptr, *edge_obs_e = nullptr;   // size sum_p C(D_p,2): observation-index pairs
};''','''  int *edge_obs_d = nullptr, *edge_obs_e = nullptr;   // size sum_p C(D_p,2): observation-index pairs
  Scalar* audit_cost_scratch = nullptr;  // owned by per-solve AuditCudaWorkspace
  Scalar* audit_cost_partials = nullptr;
  int audit_cost_capacity = 0;
  int audit_workspace_device = -1;
};

static bool AuditWorkspaceEnabled(){const char* e=getenv("OCA_AUDIT_WORKSPACE");return e&&std::atoi(e)!=0;}
struct AuditScopedCudaDevice {
  bool enabled=false; int previous=-1;
  explicit AuditScopedCudaDevice(bool on):enabled(on){if(enabled)CUDA_CHECK(cudaGetDevice(&previous));}
  ~AuditScopedCudaDevice(){if(enabled && previous>=0)cudaSetDevice(previous);}
};
struct AuditCudaWorkspace {
  Scalar* cost=nullptr;Scalar* partials=nullptr;int capacity=0; int owner=-1;
  void Init(int blocks){CUDA_CHECK(cudaGetDevice(&owner));capacity=blocks;
    CUDA_CHECK(cudaMalloc(&cost,sizeof(Scalar)));CUDA_CHECK(cudaMalloc(&partials,(size_t)blocks*sizeof(Scalar)));
    std::printf("AUDIT_WORKSPACE active device=%d cost_blocks=%d\\n",owner,blocks);}
  ~AuditCudaWorkspace(){if(!cost)return;int prior=-1;cudaGetDevice(&prior);cudaSetDevice(owner);
    cudaDeviceSynchronize();cudaFree(partials);cudaFree(cost);if(prior>=0)cudaSetDevice(prior);}
  AuditCudaWorkspace()=default;AuditCudaWorkspace(const AuditCudaWorkspace&)=delete;
  AuditCudaWorkspace& operator=(const AuditCudaWorkspace&)=delete;
};''')
    patch('''  // REVIEW 2026-09-02: persistent scalar (d_nf pattern). This function runs
  // thousands of times per solve; a cudaMalloc/Free pair per call serializes
  // the stream on allocator traffic (~3-15% of scoring wall at scale).
  static Scalar* d_cost = nullptr;
  if (!d_cost) CUDA_CHECK(cudaMalloc(&d_cost, sizeof(Scalar)));
  CUDA_CHECK(cudaMemset(d_cost, 0, sizeof(Scalar)));''','''  // Per-solve workspace is opt-in; the disabled branch preserves the legacy
  // process-global pointer exactly for compatibility.
  static Scalar* legacy_d_cost = nullptr;
  Scalar* d_cost=p.audit_cost_scratch;
  if(!d_cost){if(!legacy_d_cost)CUDA_CHECK(cudaMalloc(&legacy_d_cost,sizeof(Scalar)));d_cost=legacy_d_cost;}
  if(p.audit_cost_scratch){int dev=-1;CUDA_CHECK(cudaGetDevice(&dev));
    if(dev!=p.audit_workspace_device)throw std::runtime_error("cost workspace used on wrong CUDA device");}
  CUDA_CHECK(cudaMemset(d_cost, 0, sizeof(Scalar)));''')
    patch('''  DeviceProblem p; p.ncam = ncam; p.npt = npt; p.nobs = nobs; p.n = n;''','''  DeviceProblem p; p.ncam = ncam; p.npt = npt; p.nobs = nobs; p.n = n;
  AuditCudaWorkspace audit_workspace;
  if(AuditWorkspaceEnabled()){audit_workspace.Init(GridSize(nobs));p.audit_cost_scratch=audit_workspace.cost;
    p.audit_cost_partials=audit_workspace.partials;p.audit_cost_capacity=audit_workspace.capacity;p.audit_workspace_device=audit_workspace.owner;}''')
    patch('''  try {
    if (opt.gpu_index >= 0) CUDA_CHECK(cudaSetDevice(opt.gpu_index));

    DeviceArena arena;
    DeviceProblem p;''','''  try {
    AuditScopedCudaDevice audit_device(AuditWorkspaceEnabled());
    if (opt.gpu_index >= 0) CUDA_CHECK(cudaSetDevice(opt.gpu_index));
    AuditCudaWorkspace audit_workspace;
    DeviceArena arena;
    DeviceProblem p;''')
    patch('''    p.n = 6 * ncam + 3 * npt;
    p.cam_idx = static_cast<int*>(arena.Alloc(nobs * sizeof(int)));''','''    p.n = 6 * ncam + 3 * npt;
    if(AuditWorkspaceEnabled()){audit_workspace.Init(GridSize(nobs));p.audit_cost_scratch=audit_workspace.cost;
      p.audit_cost_partials=audit_workspace.partials;p.audit_cost_capacity=audit_workspace.capacity;p.audit_workspace_device=audit_workspace.owner;}
    p.cam_idx = static_cast<int*>(arena.Alloc(nobs * sizeof(int)));''')
    return source,len(changes)

def fused_patch(source):
    changes=[]
    def patch(before,after):
        nonlocal source
        assert source.count(before)==1,(before[:120],source.count(before))
        source=source.replace(before,after);changes.append((before,after))
    patch('''// Map camera traversal slots to the single point-major fragment store.''',
          '''#include "fused_pass1.cuh"
// Map camera traversal slots to the single point-major fragment store.''')
    patch('''    // ---- operator ----
    auto Kv=[&](const Scalar* vin,Scalar* vout){''','''    // ---- operator ----
    static const bool audit_fused=[](){const char* e=getenv("OCA_AUDIT_FUSED_PASS1");return e&&std::atoi(e)!=0;}();
    if(audit_fused && (CD!=9||shared_intr||compact_mode!=2||mf_fp32||jit_on))
      throw std::runtime_error("fused Pass1 requires compact2 compile-time Fragment CD9 unshared stored path");
    auto Kv=[&](const Scalar* vin,Scalar* vout){''')
    patch('''      CUDA_CHECK(cudaMemset(tacc,0,(size_t)n_p*sizeof(Scalar)));
      if(jit_on){''','''      if(!audit_fused) CUDA_CHECK(cudaMemset(tacc,0,(size_t)n_p*sizeof(Scalar)));
      if(jit_on){''')
    patch('''      else       { if(w6_deterministic)
                     W6DeterministicPass1<CD,Fragment><<<npt,32>>>(Gp,p.point_obs_offsets,p.point_obs_list,p.cam_idx,p.obs2cslot,vf,npt,nobs,tacc);
                   else MFPass1<CD,Fragment><<<GridSize(nobs),256>>>(Gp,fragment_cams,fragment_points,vf,nobs,tacc);
                   MFVinvApply<<<GridSize(npt),256>>>(Rf,tacc,npt,uu);''',
          '''      else       {
                   if(audit_fused){
                     AuditFusedPass1Vinv<CD,Fragment><<<GridSize(npt,4),128>>>(Gp,p.point_obs_offsets,p.point_obs_list,p.cam_idx,p.obs2cslot,vf,Rf,npt,nobs,uu);
                   } else {
                     if(w6_deterministic) W6DeterministicPass1<CD,Fragment><<<npt,32>>>(Gp,p.point_obs_offsets,p.point_obs_list,p.cam_idx,p.obs2cslot,vf,npt,nobs,tacc);
                     else MFPass1<CD,Fragment><<<GridSize(nobs),256>>>(Gp,fragment_cams,fragment_points,vf,nobs,tacc);
                     MFVinvApply<<<GridSize(npt),256>>>(Rf,tacc,npt,uu);
                   }''')
    return source,len(changes)

def derive(kind):
    if kind in ("code","combined","workspace","fused"):
        source,count=load(W6/"build_deterministic.py","audit_w6").derive()
    else:
        source,count=load(W5/"build_b6v7.py","audit_w5").derive()
    if kind in ("math","combined","workspace","fused"):
        source,n=math_patch(source);count+=n
    if kind in ("workspace","fused"):
        source,n=workspace_patch(source);count+=n
    if kind=="fused":
        source,n=fused_patch(source);count+=n
    return source,count

def main():
    ap=argparse.ArgumentParser();ap.add_argument("kind",choices=("code","math","combined","workspace","fused"));args=ap.parse_args()
    subprocess.run(["python3",str(F/"build.py"),"--check-only"],check=True)
    build=P/"build";build.mkdir(exist_ok=True)
    src=build/(args.kind+".cu");binary=build/("prism-"+args.kind)
    source,count=derive(args.kind);src.write_text(source)
    cmd=["nvcc","-O3","-DNDEBUG","-std=c++17","-arch=sm_89","-I/usr/include/eigen3",
         "-I"+str(P),"-I"+str(W6),"-I"+str(W5),"-I"+str(F/"source/headers"),
         str(src),"-o",str(binary),"-lcublas","-lcusolver"]
    log=build/(args.kind+"-build.log")
    with log.open("w") as out: subprocess.run(cmd,env=dict(os.environ,TMPDIR="/dev/shm"),stdout=out,stderr=subprocess.STDOUT,check=True)
    manifest={"kind":args.kind,"command":cmd,"binary_sha256":sha(binary),"source_sha256":sha(src),
      "frozen_source_sha256":sha(F/"source/prism_eta2.cu"),"champion_sha256":sha(F/"champion.json"),
      "protocol_sha256":sha(P/"PROTOCOL.md"),"reversible_patch_count":count,
      "audit_sources":{str(x.name):sha(x) for x in [P/"build_candidates.py",P/"linear_edge_math.h",
        P/"deterministic_cost.cuh",P/"fused_pass1.cuh"]}}
    (build/(args.kind+"-manifest.json")).write_text(json.dumps(manifest,indent=2)+"\n")
    print(binary,manifest["binary_sha256"])
if __name__=="__main__": main()
