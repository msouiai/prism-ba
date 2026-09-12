from pathlib import Path
import hashlib,json,os,subprocess
P=Path(__file__).resolve().parent;C=P.parent/'eta2_research_20260912';F=P.parent/'eta2_champion'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
subprocess.run(['python3',str(F/'build.py'),'--check-only'],check=True)
s=(F/'source/prism_eta2.cu').read_text()
anchor='template <int CD>\nRunLog SolveMFreeShiftedCG('
assert s.count(anchor)==1;s=s.replace(anchor,(C/'diagnostic_kernels.cuh').read_text()+'\n#include "witness_kernels.cuh"\n'+anchor)
anchor='    Diagnostics diag_init = ComputeDiagnostics(p, s);'
assert s.count(anchor)==1;s=s.replace(anchor,'''    if(const char* p0=getenv("OCA_W2_WITNESS")){
      WaveLoad(p0,"R_state.f64",s.R,9ul*ncam);WaveLoad(p0,"t_state.f64",s.t,3ul*ncam);
      WaveLoad(p0,"X_state.f64",s.X,3ul*npt);WaveLoad(p0,"intr_state.f64",s.intr,3ul*ncam);
    }
'''+anchor)
anchor='    // ---- operator ----\n    auto Kv='
assert s.count(anchor)==1;s=s.replace(anchor,(P/'witness.inc').read_text()+'\n'+anchor)
b=P/'build';b.mkdir(exist_ok=True);src=b/'prism_wave_witness.cu';src.write_text(s)
cmd=['nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3','-I'+str(P),'-I'+str(F/'source/headers'),str(src),'-o',str(b/'prism-wave-witness'),'-lcublas','-lcusolver']
env=os.environ.copy();env['TMPDIR']='/dev/shm'
with (b/'witness-build.log').open('w') as f:subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
manifest=dict(command=cmd,source_sha256=sha(src),binary_sha256=sha(b/'prism-wave-witness'),protocol_sha256=sha(P/'WITNESS_PROTOCOL.md'),
 frozen_source_sha256=sha(F/'source/prism_eta2.cu'),inputs={str(p):sha(p) for p in [P/'build_witness.py',P/'witness.inc',P/'witness_kernels.cuh',C/'diagnostic_kernels.cuh']})
(P/'witness_build_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print('BUILT',manifest['binary_sha256'],flush=True)
