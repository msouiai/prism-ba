#!/usr/bin/env python3
"""Build the fixed-eta-compatible Schur-Jacobi scheduler overlay."""
from pathlib import Path
import hashlib, json, os, subprocess

P=Path(__file__).resolve().parent; F=P.parent/"eta2_champion"

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def derive():
    source_path=F/"source"/"prism_eta2.cu"; original=source=source_path.read_text()
    changes=[]
    def patch(before,after):
      nonlocal source
      assert source.count(before)==1,(before[:80],source.count(before));source=source.replace(before,after);changes.append((before,after))
    patch('''  std::unique_ptr<PrismPcg> pcg;
  if(getenv("OCA_PCG"))pcg=std::make_unique<PrismPcg>(ncam);''','''  std::unique_ptr<PrismPcg> pcg;
  if(getenv("OCA_PCG"))pcg=std::make_unique<PrismPcg>(ncam);
  const double w5_pcg_schur_lam=[](){const char* e=getenv("OCA_W5_PCG_SCHUR_LAM");return e?std::atof(e):0.;}();
  bool w5_pcg_schur_switched=false;
  if(w5_pcg_schur_lam>0 && !pcg)throw std::runtime_error("wave5 Schur scheduler requires OCA_PCG");''')
    patch('''    if(pcg){
      if(L!=1||CD!=9||shared_intr||block_on||(!camera_tr&&!classical_lm))throw std::runtime_error("PCG requires guarded unshared 9DOF single-shift diagonal-coordinate TR");''','''    if(pcg){
      if(w5_pcg_schur_lam>0 && !w5_pcg_schur_switched && lam_cam<=w5_pcg_schur_lam){
        w5_pcg_schur_switched=true;pcg->schur=true;
        std::printf("W5_PCG_SCHUR switch outer=%d lambda=%.17g threshold=%.17g\\n",k,(double)lam_cam,w5_pcg_schur_lam);
      }
      if(L!=1||CD!=9||shared_intr||block_on||(!camera_tr&&!classical_lm))throw std::runtime_error("PCG requires guarded unshared 9DOF single-shift diagonal-coordinate TR");''')
    restored=source
    for before,after in reversed(changes):assert restored.count(after)==1;restored=restored.replace(after,before)
    assert restored==original
    return source

def main():
    subprocess.run(["python3",str(F/"build.py"),"--check-only"],check=True)
    build=P/"build";build.mkdir(exist_ok=True);src=build/"b3.cu";binary=build/"prism-b3"
    src.write_text(derive())
    command=["nvcc","-O3","-DNDEBUG","-std=c++17","-arch=sm_89","-I/usr/include/eigen3",
             "-I"+str(F/"source"/"headers"),str(src),"-o",str(binary),"-lcublas","-lcusolver"]
    with (build/"b3-build.log").open("w") as log:
        subprocess.run(command,env=dict(os.environ,TMPDIR="/dev/shm"),stdout=log,stderr=subprocess.STDOUT,check=True)
    manifest={"command":command,"source_sha256":sha(src),"binary_sha256":sha(binary),
      "frozen_source_sha256":sha(F/"source"/"prism_eta2.cu"),"champion_sha256":sha(F/"champion.json"),
      "reversible_patch_count":2,"sources":{str(P/"build_b3.py"):sha(P/"build_b3.py")},
      "protocol_sha256":sha(P/"B3_PROTOCOL.md")}
    (P/"b3-build-manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print("BUILT B3",manifest["binary_sha256"],flush=True)

if __name__=="__main__":main()
