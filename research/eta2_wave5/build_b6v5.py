#!/usr/bin/env python3
"""Build the reduction-order-safe preparation fusion follow-up."""
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


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def derive():
    base = load(P / "build_b6v4.py", "build_b6v4")
    source, count = base.derive(); intermediate = source; changes = []

    def patch(before, after):
        nonlocal source
        assert source.count(before) == 1, (before[:120], source.count(before))
        source = source.replace(before, after); changes.append((before, after))

    patch(
        '''  const bool w5_prep_fuse=[](){const char* e=getenv("OCA_W5_PREP_FUSE");return e&&std::atoi(e)!=0;}();
  long w5_prep_calls=0;
  if(w5_prep_fuse){''',
        '''  const bool w5_prep_fuse=[](){const char* e=getenv("OCA_W5_PREP_FUSE");return e&&std::atoi(e)!=0;}();
  const bool w5_prep_safe=[](){const char* e=getenv("OCA_W5_PREP_SAFE");return e&&std::atoi(e)!=0;}();
  if(w5_prep_fuse&&w5_prep_safe)throw std::runtime_error("choose one B6v4/v5 preparation mode");
  const bool w5_prep_any=w5_prep_fuse||w5_prep_safe;
  long w5_prep_calls=0;
  if(w5_prep_any){''',
    )
    patch(
        '''    std::printf("W5_PREP_FUSE active ncam=%d npt=%d nobs=%d\\n",ncam,npt,nobs);''',
        '''    std::printf("W5_PREP_FUSE active mode=%s ncam=%d npt=%d nobs=%d\\n",w5_prep_safe?"safe":"prune",ncam,npt,nobs);''',
    )
    patch('''      else if(w5_prep_fuse)
        W5PointFactorTauRhs''', '''      else if(w5_prep_any)
        W5PointFactorTauRhs''')
    patch('''    if(!w5_prep_fuse) MFVinvApply''', '''    if(!w5_prep_any) MFVinvApply''')
    patch(
        '''      if(w5_prep_fuse){
        MFRhsPrime<CD,Fragment><<<GridSize(nobs),256>>>(Gp,fragment_cams,fragment_points,uu,nobs,corr);
        ++w5_prep_calls;
      } else {
        CUDA_CHECK(cudaMemset(dk,0,(size_t)n_cf*sizeof(Scalar)));
        MFRhsDiagFused<<<GridSize(nobs),256>>>(mf_fp32?Gp32:Gp,fragment_cams,fragment_points,Rf,uu,nobs,corr,dk);
      }''',
        '''      if(w5_prep_fuse)
        MFRhsPrime<CD,Fragment><<<GridSize(nobs),256>>>(Gp,fragment_cams,fragment_points,uu,nobs,corr);
      else {
        CUDA_CHECK(cudaMemset(dk,0,(size_t)n_cf*sizeof(Scalar)));
        MFRhsDiagFused<<<GridSize(nobs),256>>>(mf_fp32?Gp32:Gp,fragment_cams,fragment_points,Rf,uu,nobs,corr,dk);
      }
      if(w5_prep_any)++w5_prep_calls;''',
    )
    patch('''    } else if(!w5_prep_fuse) {''', '''    } else if(!w5_prep_any) {''')
    patch('''      if(w5_prep_fuse){
        W5MakeEquilHcc''', '''      if(w5_prep_any){
        W5MakeEquilHcc''')
    patch('''      } else if(w5_prep_fuse)
        W5ReducedRhsEquil''', '''      } else if(w5_prep_any)
        W5ReducedRhsEquil''')
    patch(
        '''  if(w5_prep_fuse)std::printf("W5_PREP_FUSE summary calls=%ld\\n",w5_prep_calls);''',
        '''  if(w5_prep_any)std::printf("W5_PREP_FUSE summary mode=%s calls=%ld\\n",w5_prep_safe?"safe":"prune",w5_prep_calls);''',
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
    src = build / "b6v5.cu"; binary = build / "prism-b6v5"
    source, count = derive(); src.write_text(source)
    cmd = ["nvcc", "-O3", "-DNDEBUG", "-std=c++17", "-arch=sm_89",
           "-I/usr/include/eigen3", "-I" + str(F / "source" / "headers"),
           "-I" + str(P), str(src), "-o", str(binary), "-lcublas", "-lcusolver"]
    with (build / "b6v5-build.log").open("w") as log:
        subprocess.run(cmd, env=dict(os.environ, TMPDIR="/dev/shm"), stdout=log,
                       stderr=subprocess.STDOUT, check=True)
    manifest = {
        "command": cmd, "source_sha256": sha(src), "binary_sha256": sha(binary),
        "frozen_source_sha256": sha(F / "source" / "prism_eta2.cu"),
        "champion_sha256": sha(F / "champion.json"),
        "reversible_patch_count": count,
        "sources": {
            str(P / "build_b6v5.py"): sha(P / "build_b6v5.py"),
            str(P / "build_b6v4.py"): sha(P / "build_b6v4.py"),
            str(P / "build_b6v2.py"): sha(P / "build_b6v2.py"),
            str(P / "prep_latency.cuh"): sha(P / "prep_latency.cuh"),
        },
        "protocol_sha256": sha(P / "B6V5_PROTOCOL.md"),
    }
    (P / "b6v5-build-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("BUILT B6V5", manifest["binary_sha256"])


if __name__ == "__main__":
    main()
