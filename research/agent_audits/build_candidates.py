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
          '''    static const bool audit_linear_edges=[](){const char* e=getenv("OCA_AUDIT_LINEAR_EDGES");return e&&std::atoi(e)!=0;}();
    const bool audit_zero_rhs=audit_linear_edges && prism_agent_audit::IsExactZeroReducedRhs(nb);
    Scalar eta = ew_eta_max;
    if(prev_bnorm>0.0){ Scalar q=audit_linear_edges
        ? prism_agent_audit::ForcingRatioSquared(nb,prev_bnorm)
        : (nb*nb)/(prev_bnorm*prev_bnorm);
      eta=std::min(ew_eta_max,(Scalar)0.9*q); }
    if(rld.enabled)eta=rld.Forcing(eta);''')
    dot_call = "PrismW6Ddot" if "PrismW6Ddot(blas,n_c,r_,1,pcg->z" in source else "cublasDdot"
    patch(f'''    if(pcg){{
      if(L!=1||CD!=9||shared_intr||block_on||(!camera_tr&&!classical_lm))throw std::runtime_error("PCG requires guarded unshared 9DOF single-shift diagonal-coordinate TR");
      pcg->Prepare(Hcc,E,shifts[0],k,retries,Gp,fragment_points,p.mf_coff,Rf,nobs);pcg->Apply(r_);{dot_call}(blas,n_c,r_,1,pcg->z,1,&pcg->rz);CUDA_CHECK(cudaMemcpy(pv_,pcg->z,n_c*8ul,cudaMemcpyDeviceToDevice));
    }}''',
          f'''    if(pcg && !audit_zero_rhs){{
      if(L!=1||CD!=9||shared_intr||block_on||(!camera_tr&&!classical_lm))throw std::runtime_error("PCG requires guarded unshared 9DOF single-shift diagonal-coordinate TR");
      pcg->Prepare(Hcc,E,shifts[0],k,retries,Gp,fragment_points,p.mf_coff,Rf,nobs);pcg->Apply(r_);{dot_call}(blas,n_c,r_,1,pcg->z,1,&pcg->rz);CUDA_CHECK(cudaMemcpy(pv_,pcg->z,n_c*8ul,cudaMemcpyDeviceToDevice));
    }}
    if(audit_zero_rhs){{cg_broke=true;if(verbose)std::printf("    [linear-edge] exact zero reduced RHS: converged at depth 0\\n");}}''')
    patch('''    for(cg_it=0; cg_it<maxck; ++cg_it){''','''    for(cg_it=0; !audit_zero_rhs && cg_it<maxck; ++cg_it){''')
    patch('''      Score(xs[0],0,cg_broke?cg_it+1:maxck);''','''      Score(xs[0],0,audit_zero_rhs?0:(cg_broke?cg_it+1:maxck));''')
    restored=source
    for before,after in reversed(changes): restored=restored.replace(after,before)
    return source,len(changes)

def derive(kind):
    if kind in ("code","combined"):
        source,count=load(W6/"build_deterministic.py","audit_w6").derive()
    else:
        source,count=load(W5/"build_b6v7.py","audit_w5").derive()
    if kind in ("math","combined"):
        source,n=math_patch(source);count+=n
    return source,count

def main():
    ap=argparse.ArgumentParser();ap.add_argument("kind",choices=("code","math","combined"));args=ap.parse_args()
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
      "protocol_sha256":sha(P/"PROTOCOL.md"),"reversible_patch_count":count}
    (build/(args.kind+"-manifest.json")).write_text(json.dumps(manifest,indent=2)+"\n")
    print(binary,manifest["binary_sha256"])
if __name__=="__main__": main()
