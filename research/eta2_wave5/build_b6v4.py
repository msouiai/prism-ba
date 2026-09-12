#!/usr/bin/env python3
"""Build the preregistered wave-5 preparation-pruning/fusion overlay."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess

P = Path(__file__).resolve().parent
F = P.parent / "eta2_champion"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_b6v2():
    spec = importlib.util.spec_from_file_location("build_b6v2", P / "build_b6v2.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def derive():
    base = load_b6v2()
    source, count = base.derive()
    intermediate = source
    changes = []

    def patch(before, after):
        nonlocal source
        assert source.count(before) == 1, (before[:120], source.count(before))
        source = source.replace(before, after)
        changes.append((before, after))

    patch(
        '#include "point_prep_candidate.cuh"\n'
        'template <int CD>\n'
        '__global__ void MFDiagHcc',
        '#include "point_prep_candidate.cuh"\n'
        '#include "prep_latency.cuh"\n'
        'template <int CD>\n'
        '__global__ void MFDiagHcc',
    )

    patch(
        '''  if(w5_cg_dots){
    if(CD!=9||shared_intr||L!=1||!pcg||block_on||!classical_lm)throw std::runtime_error("B6v2 dot batching requires champion-like CD9 single-shift PCG");
    cublasCreate(&w5_blas);cublasSetPointerMode(w5_blas,CUBLAS_POINTER_MODE_DEVICE);CUDA_CHECK(cudaMalloc(&w5_dots,2*sizeof(Scalar)));
    std::printf("W5_CG_DOTS active n=%d\\n",n_c);
  }
  // ---- robust kernel state''',
        '''  if(w5_cg_dots){
    if(CD!=9||shared_intr||L!=1||!pcg||block_on||!classical_lm)throw std::runtime_error("B6v2 dot batching requires champion-like CD9 single-shift PCG");
    cublasCreate(&w5_blas);cublasSetPointerMode(w5_blas,CUBLAS_POINTER_MODE_DEVICE);CUDA_CHECK(cudaMalloc(&w5_dots,2*sizeof(Scalar)));
    std::printf("W5_CG_DOTS active n=%d\\n",n_c);
  }
  const bool w5_prep_fuse=[](){const char* e=getenv("OCA_W5_PREP_FUSE");return e&&std::atoi(e)!=0;}();
  long w5_prep_calls=0;
  if(w5_prep_fuse){
    if(CD!=9||shared_intr||L!=1||!pcg||block_on||psw||!classical_lm||!use_equil||!tau_split||mf_fp32||equil_floor>0.0||
       getenv("OCA_TAU_LAM_MAXOBS")||getenv("OCA_TAU_LAM_COND")||getenv("OCA_RHS_DIAG_CAMERA")||getenv("OCA_F3_OFF"))
      throw std::runtime_error("B6v4 prep fusion requires frozen champion-like CD9 classical diagonal path");
    std::printf("W5_PREP_FUSE active ncam=%d npt=%d nobs=%d\\n",ncam,npt,nobs);
  }
  // ---- robust kernel state''',
    )

    patch(
        '''      else
        MFPointFactorTau<<<GridSize(npt),256>>>(Cdiag,R0f,tau_eff,npt,Rf,okf);
    }
    else if(mf_fp32) MFPointFactor<float><<<GridSize(npt),256>>>(Bo32,Cdiag,p.point_obs_offsets,p.point_obs_list,tau_eff,npt,Rf,okf);
    else        MFPointFactor<Fragment><<<GridSize(npt),256>>>(Bo,Cdiag,p.point_obs_offsets,p.point_obs_list,tau_eff,npt,Rf,okf);
    // b' = b_c - H_cp V^-1 b_p
    MFVinvApply<<<GridSize(npt),256>>>(Rf,bp,npt,uu);''',
        '''      else if(w5_prep_fuse)
        W5PointFactorTauRhs<<<GridSize(npt),256>>>(Cdiag,R0f,bp,tau_eff,npt,Rf,okf,uu);
      else
        MFPointFactorTau<<<GridSize(npt),256>>>(Cdiag,R0f,tau_eff,npt,Rf,okf);
    }
    else if(mf_fp32) MFPointFactor<float><<<GridSize(npt),256>>>(Bo32,Cdiag,p.point_obs_offsets,p.point_obs_list,tau_eff,npt,Rf,okf);
    else        MFPointFactor<Fragment><<<GridSize(npt),256>>>(Bo,Cdiag,p.point_obs_offsets,p.point_obs_list,tau_eff,npt,Rf,okf);
    // b' = b_c - H_cp V^-1 b_p
    if(!w5_prep_fuse) MFVinvApply<<<GridSize(npt),256>>>(Rf,bp,npt,uu);''',
    )

    patch(
        '''    if(prep_fused){
      CUDA_CHECK(cudaMemset(corr,0,(size_t)n_cf*sizeof(Scalar)));
      CUDA_CHECK(cudaMemset(dk,0,(size_t)n_cf*sizeof(Scalar)));
      MFRhsDiagFused<<<GridSize(nobs),256>>>(mf_fp32?Gp32:Gp,fragment_cams,fragment_points,Rf,uu,nobs,corr,dk);
    } else if(rhs_diag_camera){''',
        '''    if(prep_fused){
      CUDA_CHECK(cudaMemset(corr,0,(size_t)n_cf*sizeof(Scalar)));
      if(w5_prep_fuse){
        MFRhsPrime<CD,Fragment><<<GridSize(nobs),256>>>(Gp,fragment_cams,fragment_points,uu,nobs,corr);
        ++w5_prep_calls;
      } else {
        CUDA_CHECK(cudaMemset(dk,0,(size_t)n_cf*sizeof(Scalar)));
        MFRhsDiagFused<<<GridSize(nobs),256>>>(mf_fp32?Gp32:Gp,fragment_cams,fragment_points,Rf,uu,nobs,corr,dk);
      }
    } else if(rhs_diag_camera){''',
    )

    patch(
        '''    } else {
      CUDA_CHECK(cudaMemcpy(bprime,bc,(size_t)n_cf*sizeof(Scalar),cudaMemcpyDeviceToDevice));
      { const Scalar m1=-1.0; cublasDaxpy(blas,n_cf,&m1,corr,1,bprime,1); }
    }
    if(use_equil){''',
        '''    } else if(!w5_prep_fuse) {
      CUDA_CHECK(cudaMemcpy(bprime,bc,(size_t)n_cf*sizeof(Scalar),cudaMemcpyDeviceToDevice));
      { const Scalar m1=-1.0; cublasDaxpy(blas,n_cf,&m1,corr,1,bprime,1); }
    }
    if(use_equil){''',
    )

    patch(
        '''      if(classical_lm)CUDA_CHECK(cudaMemset(dk,0,(size_t)n_cf*sizeof(Scalar)));
      MFDiagHcc<CD><<<GridSize(ncam),256>>>(Hcc,ncam,dk);
      // Equilibrate the diagonal the CG actually sees: B^T diag(S) B when the
      // intrinsics are shared, diag(S) otherwise.
      const Scalar* dk_eq=dk;
      if(shared_intr){ Reduce(dk,bcast_in); dk_eq=bcast_in; }
      if(equil_floor>0.0&&!shared_intr)
        MFMakeEquilBlocked<CD><<<GridSize(ncam),256>>>(dk,ncam,equil_floor,E);
      else
        MFMakeEquil<<<GridSize(n_c),256>>>(dk_eq,n_c,E);''',
        '''      if(w5_prep_fuse){
        W5MakeEquilHcc<CD><<<GridSize(n_c),256>>>(Hcc,ncam,E);
      } else {
        if(classical_lm)CUDA_CHECK(cudaMemset(dk,0,(size_t)n_cf*sizeof(Scalar)));
        MFDiagHcc<CD><<<GridSize(ncam),256>>>(Hcc,ncam,dk);
        // Equilibrate the diagonal the CG actually sees: B^T diag(S) B when the
        // intrinsics are shared, diag(S) otherwise.
        const Scalar* dk_eq=dk;
        if(shared_intr){ Reduce(dk,bcast_in); dk_eq=bcast_in; }
        if(equil_floor>0.0&&!shared_intr)
          MFMakeEquilBlocked<CD><<<GridSize(ncam),256>>>(dk,ncam,equil_floor,E);
        else
          MFMakeEquil<<<GridSize(n_c),256>>>(dk_eq,n_c,E);
      }''',
    )

    patch(
        '''      } else
      MFScaleVec<<<GridSize(n_c),256>>>(bprime,E,n_c);
    }
    cached_tau=tau_eff;''',
        '''      } else if(w5_prep_fuse)
        W5ReducedRhsEquil<<<GridSize(n_c),256>>>(bc,corr,E,n_c,bprime);
      else
        MFScaleVec<<<GridSize(n_c),256>>>(bprime,E,n_c);
    }
    cached_tau=tau_eff;''',
    )

    patch(
        '''  if(w5_cg_dots)std::printf("W5_CG_DOTS summary dot_pairs=%ld\\n",w5_dot_pairs);''',
        '''  if(w5_cg_dots)std::printf("W5_CG_DOTS summary dot_pairs=%ld\\n",w5_dot_pairs);
  if(w5_prep_fuse)std::printf("W5_PREP_FUSE summary calls=%ld\\n",w5_prep_calls);''',
    )

    restored = source
    for before, after in reversed(changes):
        assert restored.count(after) == 1
        restored = restored.replace(after, before)
    assert restored == intermediate
    return source, count + len(changes)


def main():
    subprocess.run(["python3", str(F / "build.py"), "--check-only"], check=True)
    build = P / "build"; build.mkdir(exist_ok=True)
    src = build / "b6v4.cu"; binary = build / "prism-b6v4"
    source, count = derive(); src.write_text(source)
    cmd = ["nvcc", "-O3", "-DNDEBUG", "-std=c++17", "-arch=sm_89",
           "-I/usr/include/eigen3", "-I" + str(F / "source" / "headers"),
           "-I" + str(P), str(src), "-o", str(binary), "-lcublas", "-lcusolver"]
    with (build / "b6v4-build.log").open("w") as log:
        subprocess.run(cmd, env=dict(os.environ, TMPDIR="/dev/shm"), stdout=log,
                       stderr=subprocess.STDOUT, check=True)
    manifest = {
        "command": cmd, "source_sha256": sha(src), "binary_sha256": sha(binary),
        "frozen_source_sha256": sha(F / "source" / "prism_eta2.cu"),
        "champion_sha256": sha(F / "champion.json"),
        "reversible_patch_count": count,
        "sources": {
            str(P / "build_b6v4.py"): sha(P / "build_b6v4.py"),
            str(P / "build_b6v2.py"): sha(P / "build_b6v2.py"),
            str(P / "prep_latency.cuh"): sha(P / "prep_latency.cuh"),
        },
        "protocol_sha256": sha(P / "B6V4_PROTOCOL.md"),
    }
    (P / "b6v4-build-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("BUILT B6V4", manifest["binary_sha256"])


if __name__ == "__main__":
    main()
