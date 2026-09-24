#!/usr/bin/env python3
"""Frozen numerical-guard derivative with two deliberately simple controls."""
import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess

BASE = pathlib.Path('/workspace/prism-model-followup/candidate')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', type=pathlib.Path, required=True)
    a = ap.parse_args()
    manifest = json.loads((BASE/'manifest.json').read_text())
    assert sha(BASE/'source.cu') == manifest['source_sha256']
    assert all(sha(BASE/'headers'/k) == v for k,v in manifest['headers_sha256'].items())
    a.output.mkdir(parents=True, exist_ok=False)
    shutil.copytree(BASE/'headers', a.output/'headers')
    s = (BASE/'source.cu').read_text()
    def sub(old, new):
        nonlocal s
        assert s.count(old) == 1, (old, s.count(old))
        s = s.replace(old, new)
    sub('  double numeric_floor=1e-16;', '''  const int recovery_mode=getenv("OCA_SCHUR_RECOVERY_MODE")?atoi(getenv("OCA_SCHUR_RECOVERY_MODE")):0;
  if(recovery_mode<0 || recovery_mode>2)throw std::runtime_error("recovery mode must be 0=Rayleigh, 1=x4 transient, 2=x4 retained");
  if(numeric_guard && recovery_mode)std::printf("RECOVERY_CONTROL mode=%d\\n",recovery_mode);
  double numeric_floor=1e-16;''')
    sub('const double repaired=std::clamp(4.*std::max((double)lam_cam,(double)lam_cam-nc_pAp/nc_pp),1e-14,1e16);',
        'const double repaired=recovery_mode?std::clamp(4.*(double)lam_cam,1e-14,1e16):std::clamp(4.*std::max((double)lam_cam,(double)lam_cam-nc_pAp/nc_pp),1e-14,1e16);')
    sub('        numeric_floor=std::max(numeric_floor,repaired);',
        '        if(recovery_mode!=1)numeric_floor=std::max(numeric_floor,repaired);')
    sub('nc_pAp/nc_pp,numeric_floor,cg_it,++numeric_rebuilds);',
        'nc_pAp/nc_pp,recovery_mode==1?repaired:numeric_floor,cg_it,++numeric_rebuilds);')
    sub('lam_cam=numeric_floor;prev_bnorm=numeric_prior_bnorm;',
        'lam_cam=recovery_mode==1?repaired:numeric_floor;prev_bnorm=numeric_prior_bnorm;')
    (a.output/'source.cu').write_text(s)
    cmd=['nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3',
         '-I'+str(a.output/'headers'),str(a.output/'source.cu'),'-o',str(a.output/'prism-tr'),'-lcublas','-lcusolver']
    with (a.output/'build.log').open('x') as f:
        subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
    (a.output/'manifest.json').write_text(json.dumps(dict(command=cmd,parent_binary=manifest['binary_sha256'],
        source_sha256=sha(a.output/'source.cu'),binary_sha256=sha(a.output/'prism-tr'),
        headers_sha256=manifest['headers_sha256'],modes={'0':'original Rayleigh + floor','1':'x4 transient','2':'x4 + floor'}),indent=2)+'\n')
    print(a.output/'prism-tr',flush=True)

if __name__=='__main__':
    main()
