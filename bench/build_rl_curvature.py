#!/usr/bin/env python3
"""Add host-only curvature features to the frozen trajectory-study binary."""
import argparse,json,pathlib,shutil,subprocess
from build_rl_damping import sha
BASE=pathlib.Path('/tmp/prism-rl-damping-trajectory/build-v2')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=pathlib.Path,required=True);a=ap.parse_args()
    m=json.loads((BASE/'manifest.json').read_text())
    assert sha(BASE/'source.cu')==m['source_sha256']
    assert all(sha(BASE/'headers'/k)==v for k,v in m['headers_sha256'].items())
    a.output.mkdir(parents=True,exist_ok=False);shutil.copytree(BASE/'headers',a.output/'headers')
    shutil.copyfile(pathlib.Path(__file__).parents[1]/'gpu/rl_curvature.h',a.output/'headers/rl_curvature.h')
    s=(BASE/'source.cu').read_text()
    def sub(old,new):
        nonlocal s
        assert s.count(old)==1,(old,s.count(old));s=s.replace(old,new)
    sub('#include "rl_damping.h"','#include "rl_curvature.h"')
    sub('  PrismRLDamping rld;','  PrismCurvatureDamping rld;')
    sub('    for(cg_it=0; cg_it<maxck; ++cg_it){','    if(rld.collect)rld.ResetCG();\n    for(cg_it=0; cg_it<maxck; ++cg_it){')
    sub('        ++st.negcurv; trunc=true; nc_pAp=pAp; nc_pp=pp; break;',
        '        if(rld.collect)rld.recurrence_valid=false;\n        ++st.negcurv; trunc=true; nc_pAp=pAp; nc_pp=pp; break;')
    sub('      static const bool menu_fuse = getenv("OCA_MENU_FUSE")!=nullptr && L<=MSMAX;',
        '      if(rld.collect)rld.ObserveCG(al,be,pAp/pp);\n      static const bool menu_fuse = getenv("OCA_MENU_FUSE")!=nullptr && L<=MSMAX;')
    sub('      lm_prediction=model.prediction;lm_rho=have&&lm_prediction>0?(cost-best_cost)/lm_prediction:-1;',
        '      if(rld.collect)rld.ObserveModel(model.slope,model.curvature);\n      lm_prediction=model.prediction;lm_rho=have&&lm_prediction>0?(cost-best_cost)/lm_prediction:-1;')
    (a.output/'source.cu').write_text(s)
    cmd=['nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3',
         '-I'+str(a.output/'headers'),str(a.output/'source.cu'),'-o',str(a.output/'prism-tr'),'-lcublas','-lcusolver']
    with (a.output/'build.log').open('x') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
    (a.output/'manifest.json').write_text(json.dumps(dict(command=cmd,parent=m,
        source_sha256=sha(a.output/'source.cu'),binary_sha256=sha(a.output/'prism-tr'),
        headers_sha256={p.name:sha(p) for p in (a.output/'headers').iterdir() if p.is_file()}),indent=2)+'\n')
    print(a.output/'prism-tr',flush=True)
if __name__=='__main__':main()
