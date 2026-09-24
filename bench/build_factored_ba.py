#!/usr/bin/env python3
import pathlib,shutil,json,subprocess,argparse
from build_tr_candidate import REPO,sha
ROOT=pathlib.Path('/workspace/prism-tr-safeguard/factored')
def main():
 global ROOT
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=pathlib.Path,default=ROOT);a=ap.parse_args();ROOT=a.output
 base=pathlib.Path('/workspace/prism-tr-cg-stop/guarded');m=json.loads((base/'stop-manifest.json').read_text());assert sha(base/'source.cu')==m['source_sha256'];assert all(sha(base/'headers'/k)==v for k,v in m['headers_sha256'].items());ROOT.mkdir();shutil.copytree(base/'headers',ROOT/'headers');shutil.copy2(REPO/'gpu/bal_factored_grad.cuh',ROOT/'headers/bal_factored_grad.cuh');s=(base/'source.cu').read_text();s=s.replace('#include "bal_grad12_generated.cuh"','#include "bal_factored_grad.cuh"',1);(ROOT/'source.cu').write_text(s)
 h=ROOT/'headers/full_step_model.cuh';t=h.read_text();a=t.index('    double gx[12]');b=t.index('    gd=rx*jx+ry*jy;',a)
 t=t[:a]+'''    double rx,ry,jx,jy;
    BalDirectional12(r,t+3*c,x,f[c],k1[c],k2[c],uv[2*o],uv[2*o+1],step+9*c,step+9*nc+3*p,k2mask,rx,ry,jx,jy);
'''+t[b:];h.write_text(t)
 cmd=['/usr/local/cuda/bin/nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3','-I'+str(ROOT/'headers'),str(ROOT/'source.cu'),'-o',str(ROOT/'prism-tr'),'-lcublas','-lcusolver']
 with (ROOT/'build.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
 (ROOT/'stop-manifest.json').write_text(json.dumps(dict(command=cmd,source_sha256=sha(ROOT/'source.cu'),binary_sha256=sha(ROOT/'prism-tr'),base_source_sha256=m['source_sha256'],headers_sha256={p.name:sha(p) for p in (ROOT/'headers').iterdir()},policy='Frozen guarded TR with factored FP64 BalResidualGrad12 and direct FP64 directional Jd for full GN prediction. Same parameterization, acceptance and controller; no rounded-block prediction used.'),indent=2));print(ROOT/'prism-tr')
if __name__=='__main__':main()
