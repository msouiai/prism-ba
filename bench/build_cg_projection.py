#!/usr/bin/env python3
import pathlib,subprocess,json,shutil
from build_tr_candidate import REPO,sha
ROOT=pathlib.Path('/workspace/prism-tr-cg-stop/projection')
def main():
 assert not (ROOT/'stop-manifest.json').exists(),'Refusing to overwrite a completed build'
 ROOT.mkdir(exist_ok=True);base=pathlib.Path('/workspace/prism-tr-cg-stop/build');shutil.copytree(base/'headers',ROOT/'headers',dirs_exist_ok=True);s=(base/'source.cu').read_text()
 s=s.replace('static void prism_cg_save(', '#include "cg_tr_projection.cuh"\nstatic void prism_cg_save(',1)
 marker='  using Fragment = float;';s=s.replace(marker,'  std::unique_ptr<PrismCgProjection> cg_projection;\n  if(getenv("OCA_CG_STOP") && atoi(getenv("OCA_CG_STOP"))==2)cg_projection=std::make_unique<PrismCgProjection>(n_c);\n'+marker,1)
 marker='    for(cg_it=0; cg_it<maxck; ++cg_it){';assert s.count(marker)==1;s=s.replace(marker,'    if(cg_projection)cg_projection->Reset();\n'+marker)
 marker='      if(capture_narrow) captured->Append(pv_,Ap_);';assert s.count(marker)==1;s=s.replace(marker,'      if(cg_projection)cg_projection->Append(r_,Ap_,rr,be_prev,shifts[0]);\n'+marker)
 s=s.replace('#include "tr_cg_stop.inc"','#include "cg_tr_projection_step.inc"\nif(!cg_projection){\n#include "tr_cg_stop.inc"\n}')
 for f in ['cg_tr_projection.cuh','cg_tr_projection_step.inc']:shutil.copy2(REPO/'gpu'/f,ROOT/'headers'/f)
 source=ROOT/'source.cu';source.write_text(s);cmd=['/usr/local/cuda/bin/nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3','-I'+str(ROOT/'headers'),str(source),'-o',str(ROOT/'prism-tr'),'-lcublas','-lcusolver']
 with (ROOT/'build.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
 (ROOT/'stop-manifest.json').write_text(json.dumps(dict(command=cmd,source_sha256=sha(source),binary_sha256=sha(ROOT/'prism-tr'),base_source_sha256=sha(base/'source.cu'),headers_sha256={p.name:sha(p) for p in (ROOT/'headers').iterdir()}),indent=2));print(ROOT/'prism-tr')
if __name__=='__main__':main()
