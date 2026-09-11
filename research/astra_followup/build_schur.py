"""Reuse checksum-verified frozen kernels; never modify the incumbent source."""
import hashlib,json,subprocess
from paths import ROOT,write_json
PKG=ROOT.parent/'eta2_champion';OLD=ROOT.parent/'schur_physics_control';BUILD=ROOT/'build'
BUILD.mkdir(exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest=json.loads((PKG/'source_manifest.json').read_text());source=PKG/'source/prism_eta2.cu'
assert sha(source)==manifest['source_sha256']
s=source.read_text();parts=[]
for start,end in [('__device__ __forceinline__ void MFVinv(', '// GAP-4090 F2'),('__global__ void MFVinvApply(', '// Map camera traversal'),('template <int CD, class HT>\n__global__ void MFPass2(', '__global__ void MFBackSub'),('template <int CD, typename HT>\n__global__ void MFBlockSchur(', '#include "pcg_camera.cuh"')]:
 a=s.index(start);b=s.index(end,a);parts.append(s[a:b])
(BUILD/'reference.cuh').write_text('\n'.join(parts))
cmd=['nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3',
     '-I'+str(BUILD),'-I'+str(OLD),str(ROOT/'residual_fixed.cu'),'-o',str(BUILD/'residual-fixed'),'-lcublas','-lcusolver']
with (BUILD/'compile.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
write_json(ROOT/'schur_build_manifest.json',{'command':cmd,'source_sha256':sha(ROOT/'residual_fixed.cu'),
 'frozen_manifest':manifest,'binary_sha256':sha(BUILD/'residual-fixed'),'reused_sources':{str(p.relative_to(ROOT.parent.parent)):sha(p) for p in [OLD/'fixed.cu',OLD/'coarse.cuh']},
 'generated_reference_sha256':sha(BUILD/'reference.cuh')})
print(BUILD/'residual-fixed')
