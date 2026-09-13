#!/usr/bin/env python3
"""Build opt-in periodic exact-residual replacement on frozen Eta2."""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import subprocess

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FROZEN = ROOT / "research" / "eta2_champion"
BUILD = pathlib.Path("/tmp/prism-wave6-d13b-native")


def sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def derive() -> tuple[str, int]:
    original = (FROZEN / "source" / "prism_eta2.cu").read_text()
    assert hashlib.sha256(original.encode()).hexdigest() == (
        "22c18359a526526ae0a5b5109187878ab1cef33b453f6bbddc2aa92597a607d8"
    )
    source = original
    changes: list[tuple[str, str]] = []

    def patch(before: str, after: str) -> None:
        nonlocal source
        assert source.count(before) == 1, (before[:120], source.count(before))
        source = source.replace(before, after)
        changes.append((before, after))

    patch(
        '''  std::unique_ptr<PrismPcg> pcg;
  if(getenv("OCA_PCG"))pcg=std::make_unique<PrismPcg>(ncam);''',
        '''  std::unique_ptr<PrismPcg> pcg;
  if(getenv("OCA_PCG"))pcg=std::make_unique<PrismPcg>(ncam);
  const int d13_restart_depth=[](){const char* e=getenv("OCA_PCG_RESTART_DEPTH");return e?std::atoi(e):0;}();
  const bool d13_restart_periodic=[](){const char* e=getenv("OCA_PCG_RESTART_PERIODIC");return e&&std::atoi(e)!=0;}();
  if(d13_restart_depth<0 || d13_restart_depth>128 || (d13_restart_periodic&&!d13_restart_depth))
    throw std::runtime_error("invalid D13 PCG restart configuration");
  long d13_restart_solves=0,d13_restart_replacements=0,d13_restart_touched=0;''',
    )
    patch(
        '''    Scalar al_prev=1.0,be_prev=0.0; size_t ci_=0; int cg_it=0; bool trunc=false;
    int last_ck_fired=-1; bool cg_broke=false;''',
        '''    Scalar al_prev=1.0,be_prev=0.0; size_t ci_=0; int cg_it=0; bool trunc=false;
    int last_ck_fired=-1; bool cg_broke=false;
    bool d13_restart_fired=false; int d13_attempt_replacements=0;
    if(d13_restart_depth>0)++d13_restart_solves;''',
    )
    gate = '''      if(sqrt(rr_new)<=eta*nb){
        if(pcg){KvS(xs[0],pcg->tmp);cublasDaxpy(blas,n_c,&shifts[0],xs[0],1,pcg->tmp,1);const double minus=-1;cublasDaxpy(blas,n_c,&minus,bprime,1,pcg->tmp,1);double true_norm;cublasDnrm2(blas,n_c,pcg->tmp,1,&true_norm);if(!std::isfinite(true_norm)||true_norm>1.01*eta*nb)throw std::runtime_error("PCG residual estimate failed reference check");}
        cg_broke=true; break;
      }    // s2.7'''
    patch(
        gate,
        gate + '''
      if(d13_restart_depth>0){
        if(!pcg || L!=1 || CD!=9 || shared_intr || block_on || poly_on || mf_fp32 ||
           !classical_lm || recycle_mode || cg_projection)
          throw std::runtime_error("D13 PCG restart requires frozen single-shift Hcc-PCG classical LM");
        const int completed=cg_it+1;
        const bool fire=completed<maxck &&
          ((d13_restart_periodic && completed%d13_restart_depth==0) ||
           (!d13_restart_periodic && !d13_restart_fired && completed==d13_restart_depth));
        if(fire){
          KvS(xs[0],Ap_);
          cublasDaxpy(blas,n_c,&shifts[0],xs[0],1,Ap_,1);
          CUDA_CHECK(cudaMemcpy(r_,bprime,(size_t)n_c*sizeof(Scalar),cudaMemcpyDeviceToDevice));
          const Scalar minus_one=-1.0;cublasDaxpy(blas,n_c,&minus_one,Ap_,1,r_,1);
          cublasDdot(blas,n_c,r_,1,r_,1,&rr);
          ++d13_attempt_replacements;++d13_restart_replacements;d13_restart_fired=true;
          const double exact_relative=std::sqrt(std::max((Scalar)0,rr))/std::max((Scalar)1e-300,nb);
          std::printf("D13_RESTART o=%d retry=%d depth=%d replacement=%d true_relative=%.17g eta=%.17g\\n",
            k,retries,completed,d13_attempt_replacements,exact_relative,(double)eta);
          if(exact_relative<=eta){cg_broke=true;break;}
          pcg->Apply(r_);cublasDdot(blas,n_c,r_,1,pcg->z,1,&pcg->rz);
          CUDA_CHECK(cudaMemcpy(pv_,pcg->z,(size_t)n_c*sizeof(Scalar),cudaMemcpyDeviceToDevice));
          al_prev=1.0;be_prev=0.0;
        }
      }''',
    )
    patch(
        '''  if(numeric_guard)std::printf("NUMERIC_REPAIR summary rebuilds=%ld floor=%.17g\\n",numeric_rebuilds,numeric_floor);''',
        '''  if(d13_restart_depth>0){
    std::printf("D13_RESTART summary solves=%ld touched=%ld replacements=%ld depth=%d periodic=%d\\n",
      d13_restart_solves,d13_restart_touched,d13_restart_replacements,d13_restart_depth,(int)d13_restart_periodic);}
  if(numeric_guard)std::printf("NUMERIC_REPAIR summary rebuilds=%ld floor=%.17g\\n",numeric_rebuilds,numeric_floor);''',
    )
    # Count a touched solve immediately after the legacy loop, while the
    # attempt-local flag is still in scope.
    patch(
        '''    if(trunc && negcurv_reseed && sweep_attempt==0 && L>1){''',
        '''    if(d13_attempt_replacements>0)++d13_restart_touched;
    if(trunc && negcurv_reseed && sweep_attempt==0 && L>1){''',
    )

    restored = source
    for before, after in reversed(changes):
        assert restored.count(after) == 1
        restored = restored.replace(after, before)
    assert restored == original
    return source, len(changes)


def main() -> None:
    subprocess.run(["python3", str(FROZEN / "build.py"), "--check-only"], check=True)
    BUILD.mkdir(parents=True, exist_ok=True)
    source_path = BUILD / "d13b_restart.cu"
    binary = BUILD / "prism-d13b-restart"
    source, count = derive()
    source_path.write_text(source)
    command = [
        "nvcc", "-O3", "-DNDEBUG", "-std=c++17", "-arch=sm_89",
        "-I/usr/include/eigen3", "-I" + str(FROZEN / "source" / "headers"),
        str(source_path), "-o", str(binary), "-lcublas", "-lcusolver",
    ]
    with (BUILD / "build.log").open("w") as log:
        subprocess.run(command, env=dict(os.environ, TMPDIR="/dev/shm"),
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    manifest = {
        "command": command,
        "source_sha256": sha(source_path),
        "binary": str(binary),
        "binary_sha256": sha(binary),
        "frozen_source_sha256": sha(FROZEN / "source" / "prism_eta2.cu"),
        "champion_sha256": sha(FROZEN / "champion.json"),
        "reversible_patch_count": count,
        "sources": {str(HERE / "build_restart_native.py"): sha(HERE / "build_restart_native.py")},
        "protocol_sha256": sha(ROOT / "research" / "eta2_wave6" / "D13B_PERIODIC_PCG_PROTOCOL.md"),
    }
    evidence = HERE / "evidence"
    evidence.mkdir(exist_ok=True)
    (evidence / "restart_native_build_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
