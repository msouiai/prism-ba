#!/usr/bin/env python3
"""Build fixed-order baseline/current derivatives from an archived W6 checkout."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,os,subprocess
P=Path(__file__).resolve().parent;R=P.parent.parent
def load(path,name):
  s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
ap=argparse.ArgumentParser();ap.add_argument("--archive",default="/tmp/prism-ba-agent-integration");a=ap.parse_args();A=Path(a.archive)
w6=load(A/"research/eta2_wave6/build_deterministic.py","w6_current_parity");edge=load(P/"build_linear_edges.py","edge_current_parity")
baseline,_=w6.derive(); current=edge.derive(baseline);out=P/"build";out.mkdir(exist_ok=True)
rows={}
for label,source in (("fixed-baseline",baseline),("fixed-linear-edges",current)):
  src=out/(label+".cu");binary=out/label;src.write_text(source)
  cmd=["nvcc","-O3","-DNDEBUG","-std=c++17","-arch=sm_89","-I/usr/include/eigen3","-I"+str(P),"-I"+str(A/"research/eta2_wave6"),"-I"+str(A/"research/eta2_wave5"),"-I"+str(R/"research/eta2_champion/source/headers"),str(src),"-o",str(binary),"-lcublas","-lcusolver"]
  subprocess.run(cmd,env=dict(os.environ,TMPDIR="/dev/shm"),check=True);rows[label]={"source_sha256":sha(src),"binary_sha256":sha(binary),"command":cmd}
(P/"FIXED_PARITY_BUILD.json").write_text(json.dumps(rows,indent=2)+"\n")
