from pathlib import Path
import hashlib,importlib.util,json,os,subprocess
P=Path(__file__).resolve().parent;C=P.parent/'eta2_research_20260912';F=P.parent/'eta2_champion'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
spec=importlib.util.spec_from_file_location('w5_native_base',P/'build.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);s,count=m.derive()
def patch(a,b):
 global s
 assert s.count(a)==1,(a[:100],s.count(a));s=s.replace(a,b)
patch('#include "wave_trace.cuh"','#include "wave_trace.cuh"\n#include "geodesic_native.cuh"')
anchor='  FrontloadTotals frontload_totals;'
patch(anchor,anchor+'''
  std::unique_ptr<GeoNative> geo;
  if(getenv("OCA_GEODESIC")&&atoi(getenv("OCA_GEODESIC"))){
    if(CD!=9||!pcg||!classical_lm||!attr_radius||!attr_strict||!numeric_guard||shared_intr||mf_fp32||rk||k2mask!=0||frontload_on)
      throw std::runtime_error("geodesic requires frozen single-shift Eta2 without other interventions");
    geo=std::make_unique<GeoNative>(ncam,npt,nobs);
  }
''')
anchor='  int L = nshifts_env > 0 ? nshifts_env : n_shifts;'
patch(anchor,anchor+'\n  if(geo && L!=1)throw std::runtime_error("geodesic requires single shift");')
anchor='      Score(xs[0],0,cg_broke?cg_it+1:maxck);';patch(anchor,anchor+'\n'+(P/'geodesic_native.inc').read_text())
b=P/'build';src=b/'prism_geodesic_native.cu';src.write_text(s)
cmd=['nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3','-I'+str(P),'-I'+str(C/'frontload'),'-I'+str(F/'source/headers'),str(src),'-o',str(b/'prism-geodesic-native'),'-lcublas','-lcusolver']
env=os.environ.copy();env['TMPDIR']='/dev/shm'
with (b/'geodesic-native-build.log').open('w') as f:subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
record=dict(command=cmd,source_sha256=sha(src),binary_sha256=sha(b/'prism-geodesic-native'),protocol_sha256=sha(P/'GEODESIC_NATIVE_PROTOCOL.md'),
 sources={str(p):sha(p) for p in [P/'build_geodesic_native.py',P/'geodesic_native.cuh',P/'geodesic_native.inc',P/'geodesic_analytic.cuh',P/'build.py',P/'wave_trace.cuh']})
(P/'geodesic_native_manifest.json').write_text(json.dumps(record,indent=2)+'\n');print('BUILT NATIVE GEODESIC',flush=True)
