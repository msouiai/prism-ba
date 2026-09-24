#!/usr/bin/env python3
import argparse,json,pathlib,shutil,subprocess
from build_rl_damping import sha
BASE=pathlib.Path('/tmp/prism-rl-actor/build')
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=pathlib.Path,required=True);a=ap.parse_args()
    m=json.loads((BASE/'manifest.json').read_text());assert sha(BASE/'source.cu')==m['source_sha256']
    assert all(sha(BASE/'headers'/k)==v for k,v in m['headers_sha256'].items())
    a.output.mkdir(parents=True,exist_ok=False);shutil.copytree(BASE/'headers',a.output/'headers')
    shutil.copyfile(pathlib.Path(__file__).parents[1]/'gpu/ba_accuracy.h',a.output/'headers/ba_accuracy.h')
    s=(BASE/'source.cu').read_text()
    def sub(old,new):
        nonlocal s
        assert s.count(old)==1,(old,s.count(old));s=s.replace(old,new)
    sub('#include "rl_actor.h"','#include "rl_actor.h"\n#include "ba_accuracy.h"')
    sub('  PrismRLActor rld; rld.clock=budget_start;','  PrismRLActor rld; rld.clock=budget_start; PrismBAAccuracy bac;')
    sub('    pf_obs_dirty=true;   // Bo/Cdiag just rebuilt',
        '    if(bac.NeedsGradient()){double c,pn; cublasDnrm2(blas,n_cf,bc,1,&c); cublasDnrm2(blas,n_p,bp,1,&pn); bac.Gradient(c,pn);}\n    pf_obs_dirty=true;   // Bo/Cdiag just rebuilt')
    sub('    if(rld.enabled)eta=rld.Forcing(eta);','    if(rld.enabled)eta=rld.Forcing(eta);\n    eta=bac.Forcing(k,eta,nb);')
    sub('        attr_next_lambda=std::clamp(attr_next_lambda,numeric_guard?numeric_floor:1e-16,1e16);',
        '        attr_next_lambda=bac.NextLambda(have,lm_rho,lam_cam,attr_next_lambda);\n        attr_next_lambda=std::clamp(attr_next_lambda,numeric_guard?numeric_floor:1e-16,1e16);')
    (a.output/'source.cu').write_text(s)
    cmd=['nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3','-I'+str(a.output/'headers'),str(a.output/'source.cu'),'-o',str(a.output/'prism-tr'),'-lcublas','-lcusolver']
    with (a.output/'build.log').open('x') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
    (a.output/'manifest.json').write_text(json.dumps(dict(command=cmd,parent=m,source_sha256=sha(a.output/'source.cu'),binary_sha256=sha(a.output/'prism-tr'),headers_sha256={p.name:sha(p) for p in (a.output/'headers').iterdir() if p.is_file()}),indent=2)+'\n')
if __name__=='__main__':main()
