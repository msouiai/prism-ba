from pathlib import Path
import hashlib,json,os,subprocess
from geodesic_math import check
P=Path(__file__).resolve().parent;F=P.parent/'eta2_champion';b=P/'build'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
(P/'geodesic_formula_check.json').write_text(json.dumps(check(),indent=2)+'\n')
prior=json.loads((P/'witness_build_manifest.json').read_text());parent=b/'prism_wave_witness.cu';assert sha(parent)==prior['source_sha256']
s=parent.read_text();s=s.replace('#include "witness_kernels.cuh"','#include "witness_kernels.cuh"\n#include "geodesic_analytic.cuh"')
anchor='          WaveSecondResidual<<<GridSize(nobs),256>>>(p.cam_idx,p.pt_idx,p.uv,s_new.R,s_new.t,s_new.X,INTR_F(p,s_new),INTR_K1(p,s_new),INTR_K2(p,s_new),ref.residual,jd,nobs,h,second);'
assert s.count(anchor)==1
s=s.replace(anchor,'          WaveAnalyticSecond<<<GridSize(nobs),256>>>(p.cam_idx,p.pt_idx,s.R,s.t,s.X,INTR_F(p,s),INTR_K1(p,s),first,ncam,nobs,second);')
src=b/'prism_geodesic_analytic.cu';src.write_text(s)
cmd=['nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3','-I'+str(P),'-I'+str(F/'source/headers'),str(src),'-o',str(b/'prism-geodesic-analytic'),'-lcublas','-lcusolver']
env=os.environ.copy();env['TMPDIR']='/dev/shm'
with (b/'geodesic-analytic-build.log').open('w') as f:subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
record=dict(command=cmd,source_sha256=sha(src),binary_sha256=sha(b/'prism-geodesic-analytic'),
 protocol_sha256=sha(P/'GEODESIC_ANALYTIC_PROTOCOL.md'),parent_witness_manifest=prior,formula_check=check(),header_sha256=sha(P/'geodesic_analytic.cuh'))
(P/'geodesic_analytic_manifest.json').write_text(json.dumps(record,indent=2)+'\n');print('BUILT ANALYTIC',flush=True)
