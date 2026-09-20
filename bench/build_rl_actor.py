#!/usr/bin/env python3
"""Frozen-source actor/forcing build; parent is the completed curvature study."""
import argparse,json,pathlib,shutil,subprocess
from build_rl_damping import sha
BASE=pathlib.Path('/tmp/prism-rl-curvature/build')
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=pathlib.Path,required=True);a=ap.parse_args()
    m=json.loads((BASE/'manifest.json').read_text());assert sha(BASE/'source.cu')==m['source_sha256']
    assert all(sha(BASE/'headers'/k)==v for k,v in m['headers_sha256'].items())
    a.output.mkdir(parents=True,exist_ok=False);shutil.copytree(BASE/'headers',a.output/'headers')
    shutil.copyfile(pathlib.Path(__file__).parents[1]/'gpu/rl_actor.h',a.output/'headers/rl_actor.h')
    s=(BASE/'source.cu').read_text()
    def sub(old,new):
        nonlocal s
        assert s.count(old)==1,(old,s.count(old));s=s.replace(old,new)
    sub('#include "rl_curvature.h"','#include "rl_actor.h"')
    sub('  PrismCurvatureDamping rld;','  PrismRLActor rld; rld.clock=budget_start;')
    sub('     rld.Begin(st.matvecs,n_reject,numeric_rebuilds,cost);',
        '     rld.Begin(st.matvecs,n_reject,numeric_rebuilds,cost);rld.Mark(k,cost);')
    sub('       if(action)lam_cam=std::clamp(baseline*std::pow(10.,action),numeric_floor,1e16);',
        '       if(action)lam_cam=std::clamp(baseline*rld.LambdaFactor(action),numeric_floor,1e16);')
    sub('    prev_bnorm=nb;\n    lp_nb=(double)nb; lp_eta=(double)eta;',
        '    if(rld.enabled)eta=rld.Forcing(eta);\n    prev_bnorm=nb;\n    lp_nb=(double)nb; lp_eta=(double)eta;')
    (a.output/'source.cu').write_text(s)
    cmd=['nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3',
         '-I'+str(a.output/'headers'),str(a.output/'source.cu'),'-o',str(a.output/'prism-tr'),'-lcublas','-lcusolver']
    with (a.output/'build.log').open('x') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
    (a.output/'manifest.json').write_text(json.dumps(dict(command=cmd,parent=m,
        source_sha256=sha(a.output/'source.cu'),binary_sha256=sha(a.output/'prism-tr'),
        headers_sha256={p.name:sha(p) for p in (a.output/'headers').iterdir() if p.is_file()}),indent=2)+'\n')
    print(a.output/'prism-tr',flush=True)
if __name__=='__main__':main()
