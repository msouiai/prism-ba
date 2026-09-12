#!/usr/bin/env python3
"""Derive observational witness instrumentation from hash-pinned Eta2."""
from pathlib import Path
import hashlib,json,subprocess
P=Path(__file__).resolve().parent;F=P.parent/'eta2_champion'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def patch(s,a,b):
    assert s.count(a)==1,(a[:100],s.count(a));return s.replace(a,b)
def main():
    subprocess.run(['python3',str(F/'build.py'),'--check-only'],check=True)
    s=(F/'source/prism_eta2.cu').read_text()
    anchor='template <int CD>\nRunLog SolveMFreeShiftedCG('
    s=patch(s,anchor,(P/'diagnostic_kernels.cuh').read_text()+'\n'+anchor)
    s=patch(s,'  double numeric_floor=1e-16;',
      '  bool brief_pending=false,brief_capture_active=false,brief_complete=false; double* brief_raw=nullptr;\n  double numeric_floor=1e-16;')
    s=patch(s,'   const double numeric_prior_bnorm=prev_bnorm;',
      '   brief_capture_active=getenv("OCA_BRIEF0_DIR") && (brief_pending || (getenv("OCA_BRIEF0_OUTER") && k==atoi(getenv("OCA_BRIEF0_OUTER"))));\n   const double numeric_prior_bnorm=prev_bnorm;')
    s=patch(s,'    if(numeric_guard && trunc && numeric_rebuilds<32',
      '    if(!brief_capture_active && numeric_guard && trunc && numeric_rebuilds<32')
    s=patch(s,'        cublasDnrm2(blas,n_c,xs[0],1,&attr_raw_norm);',
      '        if(brief_capture_active){CUDA_CHECK(cudaMalloc(&brief_raw,8ul*n_c));CUDA_CHECK(cudaMemcpy(brief_raw,xs[0],8ul*n_c,cudaMemcpyDeviceToDevice));}\n        cublasDnrm2(blas,n_c,xs[0],1,&attr_raw_norm);')
    anchor='      Score(xs[0],0,cg_broke?cg_it+1:maxck);'
    s=patch(s,anchor,anchor+'\n'+(P/'capture.inc').read_text())
    anchor='    if(converged){ ++k; break; }'
    s=patch(s,anchor,'    if(converged && getenv("OCA_BRIEF0_DIR") && !getenv("OCA_BRIEF0_OUTER") && !brief_pending){\n      brief_pending=true;converged=false;max_iter=std::max(max_iter,k+2);\n      printf("BRIEF0_TERMINAL outer=%d cost=%.17g lambda=%.17g radius=%.17g previous_rhs=%.17g\\n",k,(double)cost,(double)lam_cam,attr_R,(double)prev_bnorm);\n    }\n'+anchor)
    b=P/'build';b.mkdir(exist_ok=True);source=b/'prism_brief0.cu';source.write_text(s)
    cmd=['nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3',
      '-I'+str(F/'source/headers'),str(source),'-o',str(b/'prism-brief0'),'-lcublas','-lcusolver']
    with (b/'build.log').open('w') as out:subprocess.run(cmd,stdout=out,stderr=subprocess.STDOUT,check=True)
    manifest=dict(command=cmd,source_sha256=sha(source),frozen_source_sha256=sha(F/'source/prism_eta2.cu'),
      binary_sha256=sha(b/'prism-brief0'),protocol_sha256=sha(P/'PROTOCOL_00.md'))
    (b/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print('BUILT',manifest['binary_sha256'],flush=True)
if __name__=='__main__':main()
